#!/usr/bin/env python3
"""
app.py — Dictate menu bar app
First launch: silently installs dependencies with menu bar progress.
Subsequent launches: starts normally.
"""

import subprocess, sys, os, time, urllib.request, json, threading, shutil, re, traceback
from objc import python_method

APP_RESOURCES   = os.environ.get("APP_RESOURCES", os.path.dirname(os.path.abspath(__file__)))
APP_DATA_DIR    = os.environ.get("APP_DATA_DIR",  os.path.expanduser("~/.dictate"))
VENV_PYTHON     = os.path.join(APP_DATA_DIR, "venv", "bin", "python3")
def _runtime_path(fname):
    """Prefer ~/.dictate/ version (written by auto-update), fall back to bundle."""
    data = os.path.join(APP_DATA_DIR, fname)
    return data if os.path.exists(data) else os.path.join(APP_RESOURCES, fname)

SERVER_PATH     = _runtime_path("server.py")
SETTINGS_PATH   = _runtime_path("settings_window.py")
OLLAMA_BIN      = "/opt/homebrew/bin/ollama"
BREW_BIN        = "/opt/homebrew/bin/brew"

CURRENT_VERSION = "1.8.0"
GITHUB_USER     = "mcolfax"
GITHUB_REPO     = "dictate"
GITHUB_RAW      = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main"
VERSION_URL     = f"{GITHUB_RAW}/version.txt"
UPDATE_URL      = f"{GITHUB_RAW}/update.sh"

import rumps
from Foundation import NSObject

# ── POPOVER CONTROLLER ────────────────────────────────────────────────────────

class _PopoverController(NSObject):
    """Manages a WKWebView-backed NSPopover triggered by the menu bar icon."""

    @python_method
    def setup(self, status_item, menu, url_str):
        from AppKit import (NSPopover, NSViewController, NSView, NSMakeRect, NSMakeSize,
                            NSEventMaskLeftMouseDown, NSEventMaskRightMouseDown)
        from WebKit import WKWebView, WKWebViewConfiguration
        from Foundation import NSURL, NSURLRequest
        import objc

        self._status_item = status_item
        self._menu        = menu
        self._url_str     = url_str

        # Remove the rumps-set menu so button clicks are routed to our action
        status_item.setMenu_(None)

        btn = status_item.button()
        btn.setTarget_(self)
        btn.setAction_(objc.selector(
            self.popoverBtnClicked_,
            selector=b'popoverBtnClicked:',
            signature=b'v@:@'
        ))
        # Respond to both left and right mouse-down immediately
        btn.sendActionOn_(NSEventMaskLeftMouseDown | NSEventMaskRightMouseDown)

        # Build popover
        self._popover = NSPopover.alloc().init()
        self._popover.setBehavior_(1)  # NSPopoverBehaviorTransient
        w, h = 300, 260
        vc    = NSViewController.alloc().init()
        frame = NSMakeRect(0, 0, w, h)
        view  = NSView.alloc().initWithFrame_(frame)
        cfg   = WKWebViewConfiguration.alloc().init()
        self._wv = WKWebView.alloc().initWithFrame_configuration_(frame, cfg)
        self._wv.setAutoresizingMask_(18)  # NSViewWidthSizable | NSViewHeightSizable
        view.addSubview_(self._wv)
        vc.setView_(view)
        self._popover.setContentSize_(NSMakeSize(w, h))
        self._popover.setContentViewController_(vc)

        self._load_url()

    @python_method
    def _load_url(self):
        from Foundation import NSURL, NSURLRequest
        url = NSURL.URLWithString_(self._url_str)
        self._wv.loadRequest_(NSURLRequest.requestWithURL_(url))

    def popoverBtnClicked_(self, sender):
        # Any click (left or right) toggles the popover.
        if self._popover.isShown():
            self._popover.performClose_(sender)
        else:
            self._load_url()  # reload for fresh data
            btn = self._status_item.button()
            self._popover.showRelativeToRect_ofView_preferredEdge_(
                btn.bounds(), btn, 1)  # NSRectEdgeMinY — below the menu bar

    def menuBtnClicked_(self, sender):
        """Simple click handler: always pop up the rumps menu.
        Used when the popover is not needed — just need a click target so the
        status item menu can be detached from the item (required on macOS 26 for
        custom button images to render).
        """
        try:
            self._status_item.popUpStatusItemMenu_(self._menu)
        except Exception as e:
            print(f"[menu] menuBtnClicked_ error: {e}", flush=True)

# ── ICON REFRESHER ────────────────────────────────────────────────────────────
# Root cause of the macOS 26 icon issue: the LaunchServices app-context
# inherited when launched via `open Dictate.app` suppressed NSStatusItem
# rendering.  Fix: MacOS/Dictate launcher now uses `& disown; exit 0` so
# Python re-parents to launchd.  With that fix, a freshly-created
# NSStatusItem renders correctly; the existing rumps item still doesn't
# (it was initialised before the context was clean), so we create our own.

_refresh_icon_path = [os.path.join(APP_RESOURCES, "icon_menubar.png")]



class _IconRefresher(NSObject):
    """Creates and updates our custom NSStatusItem on the main thread."""

    def createStatusItem_(self, _):
        """One-time setup: create a fresh NSStatusItem and wire the menu."""
        try:
            import objc
            from AppKit import (NSApplication, NSStatusBar, NSImage,
                                NSVariableStatusItemLength,
                                NSEventMaskLeftMouseDown, NSEventMaskRightMouseDown)
            delegate   = NSApplication.sharedApplication().delegate()
            rumps_si   = getattr(delegate, 'nsstatusitem', None)
            rumps_menu = rumps_si.menu() if rumps_si else None

            # Hide the invisible-but-space-consuming rumps item
            if rumps_si:
                try: rumps_si.setLength_(0)
                except Exception: pass

            sb       = NSStatusBar.systemStatusBar()
            self._si = sb.statusItemWithLength_(NSVariableStatusItemLength)

            # Set initial icon (image only — no title)
            icon_path = _refresh_icon_path[0]
            img = NSImage.alloc().initWithContentsOfFile_(icon_path)
            if img:
                img.setTemplate_(True)
                self._si.button().setImage_(img)

            # Wire the nicer WKWebView popover (left-click) and plain menu (right-click)
            self._popover_ctrl = _PopoverController.alloc().init()
            self._popover_ctrl.setup(self._si, rumps_menu, "http://127.0.0.1:5001/popover")
        except Exception as e:
            print(f"[icon] createStatusItem_ error: {e}", flush=True)

    def refreshIcon_(self, _):
        """Update the custom status item's image."""
        try:
            si = getattr(self, '_si', None)
            if si is None:
                return
            btn = si.button()
            if btn is None:
                return
            from AppKit import NSImage
            icon_path = _refresh_icon_path[0]
            img = NSImage.alloc().initWithContentsOfFile_(icon_path)
            if img:
                img.setTemplate_("anim" not in os.path.basename(icon_path))
                btn.setImage_(img)
        except Exception as e:
            print(f"[icon] refreshIcon_ error: {e}", flush=True)


_icon_refresher = _IconRefresher.alloc().init()


# ── PATCH RUMPS DELEGATE (dock-click → open settings) ────────────────────────

def _patch_rumps_reopen():
    """Add applicationShouldHandleReopen to the rumps NSApp delegate class."""
    try:
        import objc, signal as _sig
        from rumps import rumps as _rumps_mod

        def applicationShouldHandleReopen_hasVisibleWindows_(self, app, hasWindows):
            lock = "/tmp/dictate_settings.lock"
            try:
                pid = int(open(lock).read().strip())
                os.kill(pid, 0)
                os.kill(pid, _sig.SIGUSR1)
            except Exception:
                subprocess.Popen([VENV_PYTHON, _runtime_path("settings_window.py")])
            return True

        objc.classAddMethods(
            _rumps_mod.NSApp,
            [applicationShouldHandleReopen_hasVisibleWindows_]
        )
    except Exception as e:
        print(f"Could not patch rumps delegate: {e}")

_patch_rumps_reopen()

def is_setup_complete():
    """Check if all dependencies are installed."""
    return (
        os.path.exists(VENV_PYTHON) and
        os.path.exists(OLLAMA_BIN) and
        os.path.exists(os.path.join(APP_DATA_DIR, "config.json"))
    )

class DictateApp(rumps.App):

    def _refresh_icon(self, icon_path=None):
        """Dispatch a menu-bar icon update to the main thread.

        icon_path — full path to the PNG to display, or None for the idle icon.
        Uses _IconRefresher (a proper NSObject subclass) so the ObjC selector is
        correctly registered — avoids the 'does not respond to selector' crash that
        classAddMethods caused silently.
        """
        try:
            if icon_path is not None:
                _refresh_icon_path[0] = icon_path
            else:
                _refresh_icon_path[0] = os.path.join(APP_RESOURCES, "icon_menubar.png")
            _icon_refresher.performSelectorOnMainThread_withObject_waitUntilDone_(
                b'refreshIcon:', None, False)
        except Exception as e:
            print(f"[icon] dispatch error: {e}", flush=True)

    def __init__(self):
        _icon_path = os.path.join(APP_RESOURCES, "icon_menubar.png")
        super().__init__("", icon=_icon_path, template=True, quit_button=None)
        self._enabled       = False
        self._recording     = False
        self._server_proc   = None
        self._ollama_proc   = None
        self._update_version = None
        self._current_icon  = "icon_menubar.png"
        self._anim_frame    = 0
        self._anim_frames   = 6
        self._setup_done    = is_setup_complete()

        self._last_text  = ""
        self.toggle_item = rumps.MenuItem("Enable Dictation", callback=self.toggle_dictation)
        self.update_item = rumps.MenuItem("", callback=self.do_update)
        self.update_item.hide()
        self.last_item   = rumps.MenuItem("No transcriptions yet", callback=self.copy_last)
        self.last_item._menuitem.setEnabled_(False)
        self.words_item  = rumps.MenuItem("0 words today")
        self.words_item._menuitem.setEnabled_(False)

        self.menu = [
            rumps.MenuItem("Open Dictate UI", callback=self.open_ui),
            self.toggle_item,
            None,
            self.last_item,
            self.words_item,
            None,
            self.update_item,
            rumps.MenuItem("About Dictate", callback=self.about),
            rumps.MenuItem("Quit", callback=self.quit_app),
        ]

        if not self._setup_done:
            threading.Thread(target=self._run_setup, daemon=True).start()
        else:
            threading.Thread(target=self._start_backend, daemon=True).start()
            threading.Thread(target=self._check_for_updates, daemon=True).start()
            threading.Thread(target=self._poll_state, daemon=True).start()

    # ── FIRST LAUNCH SETUP ────────────────────────────────────────────────────

    def _set_status(self, msg):
        """Show status in menu bar title during setup."""
        self.title = msg
        print(f"Setup: {msg}")

    def _run_setup(self):
        try:
            os.makedirs(APP_DATA_DIR, exist_ok=True)
            self._set_status("Setting up…")

            # 1. Homebrew
            if not os.path.exists(BREW_BIN):
                self._set_status("Installing Homebrew…")
                subprocess.run(
                    '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"',
                    shell=True, check=True
                )

            # 2. Ollama
            if not os.path.exists(OLLAMA_BIN):
                self._set_status("Installing Ollama…")
                subprocess.run([BREW_BIN, "install", "ollama"], check=True)

            # 3. ffmpeg
            if not shutil.which("ffmpeg"):
                self._set_status("Installing ffmpeg…")
                subprocess.run([BREW_BIN, "install", "ffmpeg"], check=True)

            # 4. Python venv
            if not os.path.exists(VENV_PYTHON):
                self._set_status("Setting up Python…")
                subprocess.run(["python3", "-m", "venv", os.path.join(APP_DATA_DIR, "venv")], check=True)
                subprocess.run([VENV_PYTHON, "-m", "pip", "install", "--quiet", "--upgrade", "pip"], check=True)
                self._set_status("Installing packages…")
                subprocess.run([
                    VENV_PYTHON, "-m", "pip", "install", "--quiet",
                    "mlx-whisper", "sounddevice", "scipy", "numpy",
                    "pynput", "flask", "rumps",
                    "pyobjc-framework-WebKit", "pyobjc-framework-Quartz",
                    "pyobjc-framework-AVFoundation",
                ], check=True)

            # 5. Ollama model
            self._set_status("Downloading AI model…")
            ollama_serve = subprocess.Popen(
                [OLLAMA_BIN, "serve"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            time.sleep(3)
            subprocess.run([OLLAMA_BIN, "pull", "llama3.2"], check=True)
            ollama_serve.terminate()

            # 6. Write default config
            config_path = os.path.join(APP_DATA_DIR, "config.json")
            if not os.path.exists(config_path):
                with open(config_path, "w") as f:
                    json.dump({
                        "mode": "toggle",
                        "hotkey": "alt_r",
                        "hotkey_label": "Right Option (\u2325)",
                        "hotkey_type": "keyboard",
                        "whisper_model": "mlx-community/whisper-small-mlx",
                        "ollama_model": "llama3.2:latest",
                        "tone": "neutral",
                        "cleanup": True,
                        "clipboard_only": False,
                        "sound_feedback": True,
                        "pause_detection": True,
                        "pause_seconds": 2.0,
                        "vocabulary": [],
                        "app_tones": {}
                    }, f, indent=2)

            self._set_status("")  # Clear title
            self.title = ""
            self._setup_done = True

            rumps.notification(
                "Dictate is ready!",
                "Setup complete",
                "Open http://localhost:5001 to configure your hotkey and settings.",
                sound=True
            )

            # Start normally
            threading.Thread(target=self._start_backend, daemon=True).start()
            threading.Thread(target=self._check_for_updates, daemon=True).start()
            threading.Thread(target=self._poll_state, daemon=True).start()

        except Exception as e:
            self.title = ""
            rumps.alert("Setup Failed", f"Could not complete setup:\n{e}\n\nPlease run install.sh manually.")

    # ── NORMAL STARTUP ────────────────────────────────────────────────────────

    def _start_backend(self):
        # Wait for rumps status bar, then create our fresh NSStatusItem.
        for _ in range(50):  # up to 5 s
            time.sleep(0.1)
            try:
                from AppKit import NSApplication
                delegate = NSApplication.sharedApplication().delegate()
                if delegate and getattr(delegate, 'nsstatusitem', None):
                    _icon_refresher.performSelectorOnMainThread_withObject_waitUntilDone_(
                        b'createStatusItem:', None, True)
                    break
            except Exception:
                pass

        try:
            urllib.request.urlopen("http://localhost:11434", timeout=1)
        except Exception:
            self._ollama_proc = subprocess.Popen(
                [OLLAMA_BIN, "serve"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            time.sleep(2)

        # Kill any orphaned server.py holding port 5001 (check it's actually our process first)
        try:
            result = subprocess.run(["lsof", "-ti", ":5001"], capture_output=True, text=True)
            for pid_str in result.stdout.strip().splitlines():
                try:
                    pid = int(pid_str)
                    # Verify it's a server.py process before killing
                    cmdline = subprocess.run(["ps", "-p", str(pid), "-o", "command="],
                                             capture_output=True, text=True).stdout
                    if "server.py" in cmdline or "dictate" in cmdline.lower():
                        os.kill(pid, 9)
                except Exception:
                    pass
            if result.stdout.strip():
                time.sleep(0.5)
        except Exception:
            pass

        env = os.environ.copy()
        env["PATH"]         = "/opt/homebrew/bin:" + env.get("PATH", "")
        env["APP_DATA_DIR"] = APP_DATA_DIR
        # Strip any inherited Python env vars that could conflict with the venv
        for key in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP"):
            env.pop(key, None)
        self._server_proc = subprocess.Popen(
            ["arch", "-arm64", VENV_PYTHON, _runtime_path("server.py")],
            cwd=APP_DATA_DIR, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

        for _ in range(20):
            try:
                urllib.request.urlopen("http://127.0.0.1:5001", timeout=1)
                self._open_settings_window()
                break
            except Exception:
                time.sleep(0.5)

    # ── POLL STATE ────────────────────────────────────────────────────────────

    def _poll_state(self):
        _crash_notified = False
        while True:
            # Detect server crash and restart
            if self._server_proc and self._server_proc.poll() is not None:
                if not _crash_notified:
                    _crash_notified = True
                    rumps.notification("Dictate", "Restarting…",
                        "The transcription server stopped unexpectedly.", sound=False)
                self._server_proc = None
                threading.Thread(target=self._start_backend, daemon=True).start()
                time.sleep(3)
                _crash_notified = False
                continue

            try:
                resp      = urllib.request.urlopen("http://127.0.0.1:5001/api/status", timeout=1)
                data      = json.loads(resp.read())
                enabled   = data.get("enabled", False)
                recording = data.get("recording", False)

                if recording:
                    self._anim_frame = (self._anim_frame + 1) % self._anim_frames
                    self._current_icon = "recording"
                    frame_path = os.path.join(APP_RESOURCES,
                                              f"icon_menubar_anim_{self._anim_frame}.png")
                    self._refresh_icon(frame_path)
                else:
                    self._anim_frame = 0
                    self._current_icon = "idle"
                    self._refresh_icon()  # idle waveform

                if enabled != self._enabled:
                    self._enabled = enabled
                    self.toggle_item.title = "Disable Dictation" if enabled else "Enable Dictation"

                history = data.get("history", [])
                if history:
                    last = history[0]["cleaned"]
                    self._last_text = last
                    snippet = last[:60] + ("…" if len(last) > 60 else "")
                    new_title = "\u201c" + snippet + "\u201d"
                    if self.last_item.title != new_title:
                        self.last_item.title = new_title
                        self.last_item._menuitem.setEnabled_(True)

                stats = data.get("stats", {})
                words = stats.get("words_today", 0)
                self.words_item.title = f"{words:,} words today"

            except Exception:
                # Server not ready yet — still keep the idle icon alive.
                self._refresh_icon()

            time.sleep(0.15)  # ~6 fps animation

    # ── UPDATE CHECKING ───────────────────────────────────────────────────────

    def _check_for_updates(self):
        while True:
            try:
                resp   = urllib.request.urlopen(VERSION_URL, timeout=5)
                latest = resp.read().decode().strip()
                if self._version_newer(latest, CURRENT_VERSION):
                    self._update_version = latest
                    # Fetch release notes from GitHub releases API
                    try:
                        api_url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases/tags/v{latest}"
                        req = urllib.request.Request(api_url, headers={"Accept": "application/vnd.github+json", "User-Agent": "Dictate-App"})
                        rel = json.loads(urllib.request.urlopen(req, timeout=5).read())
                        self._release_notes = rel.get("body", "")
                    except Exception:
                        self._release_notes = ""
                    rumps.notification(
                        "Dictate Update Available",
                        f"Version {latest} is ready",
                        "Click 'Update Available' in the menu bar to update.",
                        sound=False,
                    )
                    self.update_item.title = f"⬆️  Update to v{latest}"
                    self.update_item.show()
            except Exception:
                pass
            time.sleep(3600)

    def _version_newer(self, latest, current):
        try:
            return [int(x) for x in latest.split(".")] > [int(x) for x in current.split(".")]
        except Exception:
            return False

    def _show_update_sheet(self):
        """Show a Sparkle-style NSAlert with a scrollable release-notes accessory view."""
        try:
            from AppKit import (NSAlert, NSScrollView, NSTextView, NSMakeRect, NSColor,
                                NSFont, NSBezelStyleRounded)

            ver   = getattr(self, "_update_version", "latest")
            notes = getattr(self, "_release_notes", "") or "No release notes available."

            alert = NSAlert.alloc().init()
            alert.setMessageText_(f"Dictate {ver} is Available")
            alert.setInformativeText_(
                f"You have version {CURRENT_VERSION}. Would you like to update now?\n"
                "Dictate will download the update and restart."
            )
            alert.addButtonWithTitle_("Update Now")
            alert.addButtonWithTitle_("Later")

            # Scrollable release notes
            sv = NSScrollView.alloc().initWithFrame_(NSMakeRect(0, 0, 420, 180))
            sv.setHasVerticalScroller_(True)
            sv.setAutohidesScrollers_(True)
            sv.setBorderType_(1)  # NSBezelBorder

            tv = NSTextView.alloc().initWithFrame_(NSMakeRect(0, 0, 420, 180))
            tv.setEditable_(False)
            tv.setSelectable_(True)
            tv.setFont_(NSFont.systemFontOfSize_(11.5))
            tv.setTextColor_(NSColor.secondaryLabelColor())
            tv.setDrawsBackground_(False)
            tv.textStorage().mutableString().setString_(notes)
            tv.setTextContainerInset_((8, 8))

            sv.setDocumentView_(tv)
            alert.setAccessoryView_(sv)

            response = alert.runModal()
            return response == 1000  # NSAlertFirstButtonReturn
        except Exception as e:
            print(f"Update sheet error: {e}")
            # Fallback to plain alert
            response = rumps.alert(
                title=f"Update to v{getattr(self, '_update_version', 'latest')}",
                message="Dictate will download the latest version and restart.",
                ok="Update Now", cancel="Later"
            )
            return response == 1

    def do_update(self, _):
        confirmed = self._show_update_sheet()
        if not confirmed:
            return
        try:
            files_to_update = ["server.py", "overlay.py", "settings_window.py", "app.py", "make_icons.py"]
            bundle_resources = "/Applications/Dictate.app/Contents/Resources"
            for fname in files_to_update:
                url  = f"{GITHUB_RAW}/{fname}"
                dest = os.path.join(APP_DATA_DIR, fname)
                data = urllib.request.urlopen(url, timeout=15).read()
                with open(dest, "wb") as f:
                    f.write(data)
                # Also refresh the app bundle so the launcher picks up new code
                bundle_dest = os.path.join(bundle_resources, fname)
                if os.path.isdir(bundle_resources):
                    try:
                        with open(bundle_dest, "wb") as f:
                            f.write(data)
                    except Exception:
                        pass  # non-fatal — ~/.dictate/ copy is the live one
            # Regenerate animation icons
            subprocess.run([VENV_PYTHON, os.path.join(APP_DATA_DIR, "make_icons.py")],
                           cwd=APP_DATA_DIR, capture_output=True)
            # Write quit flag so settings_window closes itself cleanly
            try:
                with open(os.path.join(APP_DATA_DIR, "quit.flag"), "w") as _f: _f.write("quit")
            except Exception: pass
            try: os.unlink("/tmp/dictate_settings.lock")
            except Exception: pass
            if self._server_proc:
                try: os.kill(self._server_proc.pid, 9)
                except Exception: pass
            if self._ollama_proc:  self._ollama_proc.terminate()
            subprocess.Popen(["open", "/Applications/Dictate.app"])
            rumps.quit_application()
        except Exception as e:
            rumps.alert("Update Failed", "Could not download update. Check your internet connection and try again.")

    # ── CONTROLS ──────────────────────────────────────────────────────────────

    def copy_last(self, _):
        if not self._last_text:
            return
        try:
            from AppKit import NSPasteboard, NSPasteboardTypeString
            pb = NSPasteboard.generalPasteboard()
            pb.clearContents()
            pb.setString_forType_(self._last_text, NSPasteboardTypeString)
        except Exception:
            pass

    def about(self, _):
        rumps.alert(
            title=f"Dictate  v{CURRENT_VERSION}",
            message=(
                "Free, local AI dictation for macOS.\n"
                "No cloud. No subscription. No data leaves your machine.\n\n"
                "github.com/mcolfax/dictate"
            ),
            ok="Close"
        )

    def open_ui(self, _):
        self._open_settings_window()

    def _open_settings_window(self):
        subprocess.Popen([VENV_PYTHON, _runtime_path("settings_window.py")])

    def toggle_dictation(self, _):
        try:
            urllib.request.urlopen(
                urllib.request.Request("http://127.0.0.1:5001/api/toggle", method="POST"),
                timeout=2
            )
        except Exception as e:
            print(f"Toggle error: {e}")

    def quit_app(self, _):
        import subprocess as _sp, signal as _sig

        # Write quit flag — settings_window polls this every 0.1 s and exits cleanly
        try:
            quit_flag = os.path.join(APP_DATA_DIR, "quit.flag")
            with open(quit_flag, "w") as _f: _f.write("quit")
        except Exception: pass

        # Kill server with SIGKILL (SIGTERM may be ignored by the Obj-C run loop)
        if self._server_proc:
            try: os.kill(self._server_proc.pid, 9)
            except Exception: pass
        if self._ollama_proc:
            try: self._ollama_proc.terminate()
            except Exception: pass

        # Kill child processes (overlay, settings window)
        for name in ("overlay.py", "settings_window.py"):
            try:
                r = _sp.run(["pgrep", "-f", name], capture_output=True, text=True)
                for pid in r.stdout.strip().splitlines():
                    try: os.kill(int(pid), 9)
                    except Exception: pass
            except Exception:
                pass

        # Remove stale lock file
        try: os.unlink("/tmp/dictate_settings.lock")
        except Exception: pass
        rumps.quit_application()

if __name__ == "__main__":
    # ── Single-instance guard ─────────────────────────────────────────────────
    _LOCK = os.path.join(APP_DATA_DIR, "app.lock")
    try:
        _existing_pid = int(open(_LOCK).read().strip())
        os.kill(_existing_pid, 0)          # raises if process is gone
        # Another instance is running — kill it before starting fresh
        os.kill(_existing_pid, 9)
        time.sleep(0.3)
    except Exception:
        pass
    with open(_LOCK, "w") as _lf:
        _lf.write(str(os.getpid()))
    import atexit as _atexit
    _atexit.register(lambda: os.unlink(_LOCK) if os.path.exists(_LOCK) else None)
    # ── Suppress dock icon — Python.app binary shows in dock without this ────
    try:
        from AppKit import NSApplication
        NSApplication.sharedApplication().setActivationPolicy_(1)
    except Exception:
        pass
    # ── Handle SIGTERM from /api/quit (server signals us to quit) ─────────────
    import signal as _signal
    def _on_sigterm(sig, frame):
        # Write quit flag so settings_window polls and closes itself
        try:
            with open(os.path.join(APP_DATA_DIR, "quit.flag"), "w") as _f:
                _f.write("quit")
        except Exception: pass
        # Kill child windows
        try:
            import subprocess as _sp
            for _name in ("overlay.py", "settings_window.py"):
                _r = _sp.run(["pgrep", "-f", _name], capture_output=True, text=True)
                for _pid in _r.stdout.strip().splitlines():
                    try: os.kill(int(_pid), 9)
                    except Exception: pass
        except Exception: pass
        try: os.unlink("/tmp/dictate_settings.lock")
        except Exception: pass
        try: rumps.quit_application()
        except Exception: import sys; sys.exit(0)
    _signal.signal(_signal.SIGTERM, _on_sigterm)
    # ── Launch ────────────────────────────────────────────────────────────────
    DictateApp().run()
