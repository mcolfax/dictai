#!/usr/bin/env python3
import json, os, socket, sys, threading, math, random
from AppKit import (NSApplication, NSBackingStoreBuffered, NSBorderlessWindowMask,
    NSColor, NSFont, NSMakeRect, NSPanel, NSTextAlignmentCenter, NSTextField,
    NSWindowCollectionBehaviorCanJoinAllSpaces, NSWindowCollectionBehaviorStationary,
    NSFloatingWindowLevel, NSVisualEffectView, NSScreen, NSNonactivatingPanelMask,
    NSView)
from Foundation import NSObject, NSTimer
from Quartz import (CALayer, CABasicAnimation, CATransaction, CAMediaTimingFunction,
    kCAMediaTimingFunctionEaseInEaseOut, CACurrentMediaTime)
from objc import python_method

DATA_DIR    = os.environ.get("APP_DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
SOCKET_PATH = os.path.join(DATA_DIR, "overlay.sock")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

BAR_COUNT   = 5
BAR_W       = 3
BAR_GAP     = 4
BAR_MIN_H   = 3.0
BAR_MAX_H   = 20.0

def load_position():
    try:
        cfg = json.load(open(CONFIG_FILE))
        return cfg.get("overlay_x"), cfg.get("overlay_y")
    except Exception:
        return None, None

def save_position(x, y):
    try:
        cfg = {}
        if os.path.exists(CONFIG_FILE):
            cfg = json.load(open(CONFIG_FILE))
        cfg["overlay_x"] = x; cfg["overlay_y"] = y
        with open(CONFIG_FILE, "w") as f: json.dump(cfg, f, indent=2)
    except Exception:
        pass


class WaveformView(NSView):
    """Animated bar waveform — responds to real audio levels when available."""

    # Per-bar phase offsets so bars oscillate at slightly different rates
    _PHASES = [0.0, 0.35, 0.7, 1.05, 1.4]

    @python_method
    def setup(self, width, height):
        self.setWantsLayer_(True)
        self._bars = []
        self._active = False
        self._level = 0.0          # 0.0 – 1.0 from audio RMS
        self._idle_t = 0.0         # time counter for idle animation
        total_w = BAR_COUNT * BAR_W + (BAR_COUNT - 1) * BAR_GAP
        start_x = (width - total_w) / 2
        cy = height / 2

        for i in range(BAR_COUNT):
            bar = CALayer.layer()
            bar.setCornerRadius_(BAR_W / 2)
            bar.setBackgroundColor_(NSColor.labelColor().CGColor())
            bx = start_x + i * (BAR_W + BAR_GAP)
            bar.setFrame_(((bx, cy - BAR_MIN_H / 2), (BAR_W, BAR_MIN_H)))
            bar.setAnchorPoint_((0.5, 0.5))
            self.layer().addSublayer_(bar)
            self._bars.append(bar)

    @python_method
    def start_wave(self):
        self._active = True
        self._idle_t = 0.0

    @python_method
    def stop_wave(self):
        self._active = False
        self._level = 0.0
        self._set_all_bars(BAR_MIN_H)

    @python_method
    def update_level(self, level: float):
        """Called from main thread with current audio level (0–1)."""
        self._level = max(0.0, min(1.0, level))

    @python_method
    def tick(self, dt: float):
        """Called by the 20 Hz display timer to advance animation."""
        if not self._active:
            return
        self._idle_t += dt
        lv = self._level
        # When level is low, do a gentle idle wave; scale up with real audio
        for i, bar in enumerate(self._bars):
            phase = self._PHASES[i]
            idle_factor = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(self._idle_t * 4.0 + phase))
            # Blend: at low levels use mostly idle animation; at high levels use raw level
            blend = lv ** 0.5          # sqrt makes lower levels more responsive
            height = BAR_MIN_H + (BAR_MAX_H - BAR_MIN_H) * (
                (1 - blend) * idle_factor * 0.5 + blend * (0.3 + 0.7 * idle_factor)
            )
            self._set_bar(bar, height)

    @python_method
    def _set_all_bars(self, h: float):
        for bar in self._bars:
            self._set_bar(bar, h)

    @python_method
    def _set_bar(self, bar, h: float):
        CATransaction.begin()
        CATransaction.setDisableActions_(True)
        f = bar.frame()
        cy = f.origin.y + f.size.height / 2
        bar.setFrame_(((f.origin.x, cy - h / 2), (BAR_W, h)))
        CATransaction.commit()


class OverlayDelegate(NSObject):
    def applicationDidFinishLaunching_(self, notification):
        self._pending_text  = None
        self._pending_level = None
        self._current_text  = None
        self._lock          = threading.Lock()
        self._last_tick     = CACurrentMediaTime()

        saved_x, saved_y = load_position()
        w, h = 210, 44
        if saved_x is not None and saved_y is not None:
            rect = NSMakeRect(saved_x, saved_y, w, h)
        else:
            screen = NSScreen.mainScreen().frame()
            x = (screen.size.width - w) / 2
            rect = NSMakeRect(x, 100, w, h)

        self._win = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            rect, NSBorderlessWindowMask | NSNonactivatingPanelMask, NSBackingStoreBuffered, False)
        self._win.setLevel_(NSFloatingWindowLevel)
        self._win.setOpaque_(False)
        self._win.setAlphaValue_(0.88)
        self._win.setBackgroundColor_(NSColor.clearColor())
        self._win.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces | NSWindowCollectionBehaviorStationary)
        self._win.setMovableByWindowBackground_(True)
        self._win.setHasShadow_(True)

        vfx = NSVisualEffectView.alloc().initWithFrame_(NSMakeRect(0, 0, w, h))
        vfx.setMaterial_(1)
        vfx.setBlendingMode_(0)
        vfx.setState_(1)
        vfx.setWantsLayer_(True)
        vfx.layer().setCornerRadius_(22.0)
        vfx.layer().setMasksToBounds_(True)
        self._win.setContentView_(vfx)

        # Mic icon (always visible)
        self._icon = NSTextField.alloc().initWithFrame_(NSMakeRect(14, 10, 24, 24))
        self._icon.setStringValue_("🎙")
        self._icon.setBezeled_(False); self._icon.setDrawsBackground_(False)
        self._icon.setEditable_(False); self._icon.setSelectable_(False)
        self._icon.setFont_(NSFont.systemFontOfSize_(16.0))
        vfx.addSubview_(self._icon)

        # Waveform bars (shown while listening)
        wave_x = 44
        wave_w = w - wave_x - 14
        self._wave = WaveformView.alloc().initWithFrame_(NSMakeRect(wave_x, 0, wave_w, h))
        self._wave.setup(wave_w, h)
        vfx.addSubview_(self._wave)

        # Text label (shown while processing)
        self._label = NSTextField.alloc().initWithFrame_(NSMakeRect(44, 10, w - 58, h - 20))
        self._label.setStringValue_("")
        self._label.setBezeled_(False); self._label.setDrawsBackground_(False)
        self._label.setEditable_(False); self._label.setSelectable_(False)
        self._label.setTextColor_(NSColor.secondaryLabelColor())
        self._label.setFont_(NSFont.systemFontOfSize_weight_(13.0, 0.0))
        self._label.setAlignment_(NSTextAlignmentCenter)
        self._label.setLineBreakMode_(3)
        self._label.setHidden_(True)
        vfx.addSubview_(self._label)

        # 20 Hz UI timer — drives waveform animation ticks
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.05, self, "pollUpdates:", None, True)
        threading.Thread(target=self._socket_server, daemon=True).start()

    @python_method
    def set_text(self, text):
        with self._lock: self._pending_text = text

    @python_method
    def set_level(self, level: float):
        with self._lock: self._pending_level = level

    def pollUpdates_(self, timer):
        now = CACurrentMediaTime()
        dt = now - self._last_tick
        self._last_tick = now

        with self._lock:
            text  = self._pending_text;  self._pending_text  = None
            level = self._pending_level; self._pending_level = None

        if level is not None:
            self._wave.update_level(level)

        self._wave.tick(dt)

        if text is None:
            return
        if text == self._current_text:
            return
        self._current_text = text

        if text == "Listening…":
            self._label.setHidden_(True)
            self._wave.setHidden_(False)
            self._wave.start_wave()
            app = NSApplication.sharedApplication()
            app.activateIgnoringOtherApps_(True)
            self._win.orderFrontRegardless()
            app.setActivationPolicy_(1)
        elif text:
            self._wave.stop_wave()
            self._wave.setHidden_(True)
            self._label.setStringValue_(text)
            self._label.setHidden_(False)
            app = NSApplication.sharedApplication()
            app.activateIgnoringOtherApps_(True)
            self._win.orderFrontRegardless()
            app.setActivationPolicy_(1)
        else:
            self._wave.stop_wave()
            self._win.orderOut_(None)
            origin = self._win.frame().origin
            threading.Thread(target=save_position, args=(origin.x, origin.y), daemon=True).start()

    @python_method
    def _socket_server(self):
        if os.path.exists(SOCKET_PATH): os.unlink(SOCKET_PATH)
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(SOCKET_PATH); server.listen(10); server.settimeout(1.0)
        while True:
            try:
                conn, _ = server.accept()
                data = b""
                while True:
                    chunk = conn.recv(4096)
                    if not chunk: break
                    data += chunk
                conn.close()
                if data:
                    msg = json.loads(data.decode("utf-8"))
                    if "level" in msg:
                        self.set_level(float(msg["level"]))
                    elif "text" in msg:
                        self.set_text(msg.get("text", ""))
            except socket.timeout: continue
            except Exception as e: print(f"[overlay] socket error: {e}", file=sys.stderr)

if __name__ == "__main__":
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(1)
    delegate = OverlayDelegate.alloc().init()
    app.setDelegate_(delegate)
    app.run()
