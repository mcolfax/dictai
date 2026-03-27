#!/usr/bin/env python3
# ui_patch.py — adds version footer + check for updates to server.py
# Run once: python3 ui_patch.py

path = '/Users/colfax/Documents/dictation/server.py'
content = open(path).read()

# 1. Add version constant after OLLAMA_URL line
old_ollama = 'OLLAMA_URL     = "http://localhost:11434/api/generate"'
new_ollama  = '''OLLAMA_URL     = "http://localhost:11434/api/generate"
APP_VERSION    = "1.0.0"
GITHUB_RAW     = "https://raw.githubusercontent.com/mcolfax/dictate/main"'''
content = content.replace(old_ollama, new_ollama)

# 2. Add /api/version endpoint before the index route
old_index = '@app.route("/")\ndef index(): return HTML'
new_index  = '''@app.route("/api/version")
def api_version():
    latest = None
    try:
        resp   = urllib.request.urlopen(f"{GITHUB_RAW}/version.txt", timeout=5)
        latest = resp.read().decode().strip()
    except Exception:
        pass
    return jsonify({"current": APP_VERSION, "latest": latest,
                    "update_available": latest and latest != APP_VERSION})

@app.route("/")
def index(): return HTML'''
content = content.replace(old_index, new_index)

# 3. Add footer + check for updates to the HTML, before </div>\n</body>
old_body = '''  <div class="divider"></div>

  <div class="history-header">'''
new_body  = '''  <div class="divider"></div>

  <!-- Version footer -->
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;">
    <div style="font-size:11px;color:var(--dim);letter-spacing:.05em;">
      dict<span style="color:var(--amber)">.</span>ate &nbsp;·&nbsp; <span id="versionBadge">v1.0.0</span>
    </div>
    <button onclick="checkForUpdates()" id="updateBtn"
      style="font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--dim);
             background:var(--muted);border:none;border-radius:3px;padding:4px 12px;
             cursor:pointer;font-family:\'JetBrains Mono\',monospace;transition:all .15s;">
      Check for Updates
    </button>
  </div>
  <div id="updateBanner" style="display:none;background:rgba(245,158,11,.08);border:1px solid var(--amber);
       border-radius:4px;padding:12px 16px;margin-bottom:24px;font-size:12px;
       display:none;align-items:center;justify-content:space-between;gap:16px;">
    <span id="updateMsg"></span>
    <a id="updateLink" href="#" style="color:var(--amber);text-decoration:none;
       font-size:10px;letter-spacing:.1em;text-transform:uppercase;white-space:nowrap;">
      View Release →
    </a>
  </div>

  <div class="divider"></div>

  <div class="history-header">'''
content = content.replace(old_body, new_body)

# 4. Add JS checkForUpdates function before fetchStatus(); at the bottom
old_js = 'fetchStatus();\nsetInterval(fetchStatus,1000);'
new_js  = '''async function checkForUpdates() {
  const btn = document.getElementById('updateBtn');
  btn.textContent = 'Checking…';
  btn.style.color = 'var(--amber)';
  try {
    const data = await (await fetch('/api/version')).json();
    document.getElementById('versionBadge').textContent = 'v' + data.current;
    const banner = document.getElementById('updateBanner');
    const msg    = document.getElementById('updateMsg');
    const link   = document.getElementById('updateLink');
    if (data.update_available) {
      msg.textContent = `✨ v${data.latest} is available (you have v${data.current})`;
      link.href = 'https://github.com/mcolfax/dictate/releases';
      banner.style.display = 'flex';
      btn.textContent = '⬆️ Update Available';
      btn.style.color = 'var(--amber)';
    } else if (data.latest) {
      msg.textContent = `✅ You're on the latest version (v${data.current})`;
      link.style.display = 'none';
      banner.style.display = 'flex';
      btn.textContent = 'Up to Date ✓';
      btn.style.color = 'var(--green)';
      setTimeout(() => {
        banner.style.display = 'none';
        link.style.display = '';
        btn.textContent = 'Check for Updates';
        btn.style.color = 'var(--dim)';
      }, 4000);
    } else {
      btn.textContent = 'No Internet';
      setTimeout(() => { btn.textContent = 'Check for Updates'; btn.style.color = 'var(--dim)'; }, 3000);
    }
  } catch(e) {
    btn.textContent = 'Error — try again';
    setTimeout(() => { btn.textContent = 'Check for Updates'; btn.style.color = 'var(--dim)'; }, 3000);
  }
}

fetchStatus();
setInterval(fetchStatus,1000);'''
content = content.replace(old_js, new_js)

open(path, 'w').write(content)
print("Done!")
