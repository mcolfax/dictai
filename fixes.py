#!/usr/bin/env python3
# fixes.py — run once to apply all fixes to server.py and app.py

import re

# ── server.py fixes ───────────────────────────────────────────────────────────
s = open('server.py').read()

# Fix 1: Version displayed dynamically on page load (not hardcoded)
s = s.replace(
    '<div style="font-size:11px;color:var(--dim)">dict<span style="color:var(--amber)">.</span>ate &nbsp;&middot;&nbsp; <span id="versionBadge">v1.0.0</span></div>',
    '<div style="font-size:11px;color:var(--dim)">dict<span style="color:var(--amber)">.</span>ate &nbsp;&middot;&nbsp; <span id="versionBadge">loading...</span></div>'
)

# Fix 2: Load version on page load
s = s.replace(
    'fetchStatus();setInterval(fetchStatus,1000);',
    '''// Load version on page load
fetch('/api/version').then(r=>r.json()).then(data=>{
  document.getElementById('versionBadge').textContent='v'+data.current;
}).catch(()=>{});
fetchStatus();setInterval(fetchStatus,1000);'''
)

# Fix 3: Speed — skip cleanup for very short transcriptions, add timeout hint
s = s.replace(
    '        if config.get("cleanup", True):\n            final = cleanup_with_ollama(corrected, active_tone)\n            print(f"✨ Cleaned: {final}")\n        else:\n            final = corrected',
    '''        if config.get("cleanup", True) and len(corrected.split()) > 3:
            final = cleanup_with_ollama(corrected, active_tone)
            print(f"✨ Cleaned: {final}")
        else:
            final = corrected'''
)

# Fix 4: Reduce Ollama timeout and add stream=False explicitly
s = s.replace(
    'with urllib.request.urlopen(req, timeout=30) as resp:',
    'with urllib.request.urlopen(req, timeout=15) as resp:'
)

open('server.py', 'w').write(s)
print("✅ server.py fixed")

# ── app.py fixes ──────────────────────────────────────────────────────────────
a = open('app.py').read()

# Fix 5: Update click — fix the update flow to restart correctly
old_update = '''    def do_update(self, _):
        """Download and run update.sh from GitHub."""
        response = rumps.alert(
            title=f"Update to v{self._update_version}",
            message="Dictate will download the update and restart. Continue?",
            ok="Update", cancel="Cancel"
        )
        if response != 1:
            return

        try:
            # Download update script
            update_script = urllib.request.urlopen(UPDATE_URL, timeout=10).read().decode()
            script_path   = os.path.join(APP_DATA_DIR, "update.sh")
            with open(script_path, "w") as f:
                f.write(update_script)
            os.chmod(script_path, 0o755)

            # Run update in background, quit this instance
            subprocess.Popen(
                ["bash", script_path, APP_DATA_DIR, APP_RESOURCES],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            if self._server_proc:
                self._server_proc.terminate()
            if self._ollama_proc:
                self._ollama_proc.terminate()
            rumps.quit_application()
        except Exception as e:
            rumps.alert("Update Failed", f"Could not download update:\\n{e}")'''

new_update = '''    def do_update(self, _):
        """Download and run update.sh from GitHub."""
        response = rumps.alert(
            title=f"Update to v{self._update_version}",
            message="Dictate will download the update and restart. Continue?",
            ok="Update", cancel="Cancel"
        )
        if response != 1:
            return

        try:
            # Download each file directly into the app bundle
            files_to_update = ["server.py", "app.py", "make_icons.py"]
            for fname in files_to_update:
                url  = f"{GITHUB_RAW}/{fname}"
                dest = os.path.join(APP_RESOURCES, fname)
                data = urllib.request.urlopen(url, timeout=15).read()
                with open(dest, "wb") as f:
                    f.write(data)
                print(f"✅ Updated {fname}")

            # Also update local dictation folder
            for fname in files_to_update:
                src  = os.path.join(APP_RESOURCES, fname)
                dest = os.path.join(APP_DATA_DIR, fname)
                import shutil
                shutil.copy2(src, dest)

            if self._server_proc:
                self._server_proc.terminate()
            if self._ollama_proc:
                self._ollama_proc.terminate()

            # Relaunch app
            subprocess.Popen(["open", "/Applications/Dictate.app"])
            rumps.quit_application()
        except Exception as e:
            rumps.alert("Update Failed", f"Could not download update:\\n{e}")'''

a = a.replace(old_update, new_update)
open('app.py', 'w').write(a)
print("✅ app.py fixed")
print("Done — now run: cp server.py app.py /Applications/Dictate.app/Contents/Resources/")
