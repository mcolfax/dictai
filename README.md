# 🎤 Dictate — Local AI Dictation for macOS

Free, private, system-wide voice dictation powered by Whisper + Ollama.  
No cloud. No subscriptions. No API keys. Everything runs on your Mac.

---

## Requirements

- macOS with **Apple Silicon** (M1/M2/M3/M4)
- ~5GB free disk space (for AI models)
- Internet connection during install only

---

## Install

```bash
# 1. Download and unzip the latest release
# 2. Open Terminal and run:
cd ~/Downloads/Dictate
chmod +x install.sh
./install.sh
```

The installer handles everything automatically:
- Homebrew, Ollama, ffmpeg
- Python virtual environment + all packages
- Whisper transcription model
- Ollama llama3.2 language model (~2GB)
- Builds and installs Dictate.app to /Applications

**Total install time: ~5 minutes** depending on internet speed.

---

## First Launch

1. Open **Dictate.app** from `/Applications`  
   *(right-click → Open the first time to bypass Gatekeeper)*
2. Grant **Microphone** permission when prompted
3. Go to **System Settings → Privacy & Security → Accessibility** and enable **Dictate**
4. Open **http://localhost:5001** in your browser to configure settings

---

## Usage

| Action | Default |
|--------|---------|
| Start recording | Press **Right Option (⌥)** |
| Stop recording | Press **Right Option (⌥)** again |
| Open settings UI | http://localhost:5001 |

Text is automatically transcribed, cleaned up by AI, and pasted into whatever app you're using.

---

## Features

- 🎙️ **System-wide** — works in any app (Slack, Mail, Notes, browser, etc.)
- ✨ **AI cleanup** — fixes punctuation, removes filler words (um, uh, like)
- 🔑 **Custom hotkey** — assign any key or mouse button
- 🎭 **Tone profiles** — neutral, professional, casual, concise
- 📱 **Per-app tones** — different style per application
- 📖 **Custom vocabulary** — fix words Whisper consistently mishears
- 🤫 **Pause detection** — auto-stops after configurable silence
- 📊 **Session stats** — words and sessions tracked
- 🔇 **Clipboard mode** — copy without auto-pasting
- 🔈 **Sound feedback** — audio cues on start/stop/done
- 🔄 **Auto-update** — notifies you when a new version is available

---

## Auto-start at Login

**System Settings → General → Login Items → add Dictate.app**

---

## Updating

Dictate checks for updates automatically. When a new version is available you'll see **"⬆️ Update Available"** in the menu bar. Click it to update in one step.

You can also check manually from the settings UI at http://localhost:5001 (bottom of the page).

---

## Uninstall

```bash
rm -rf /Applications/Dictate.app
rm -rf ~/.dictate
```

To also remove Ollama models: `rm -rf ~/.ollama`

---

## How it works

```
Your voice
    ↓
Whisper (Apple Silicon, runs locally)
    ↓
Raw transcription
    ↓
Vocabulary corrections
    ↓
Ollama / llama3.2 (runs locally)
    ↓
Cleaned text → pasted into your app
```

All processing happens on your Mac. Nothing is sent to any server.

---

## Troubleshooting

**Hotkey not working?**  
→ System Settings → Privacy & Security → Accessibility → make sure Dictate is enabled

**Mic not picking up audio?**  
→ Use the Mic Test in the settings UI to check your input level  
→ System Settings → Privacy & Security → Microphone → enable Dictate

**Ollama errors?**  
→ Make sure Ollama is running: `ollama serve`  
→ Make sure the model is downloaded: `ollama pull llama3.2`

---

Built by [@mcolfax](https://github.com/mcolfax)
