# Install guide — YouTube Music → Discord status

## Where your status shows in Discord

Custom Rich Presence is **not** the green Spotify panel in the bottom-left.

You will see it as:

1. **User Settings → Activity Privacy** → enable **Display current activity as a status**
2. Click **your avatar (bottom-left)** → profile card → **Listening to YouTube Music** with song + artist
3. Or open a server and look at **yourself in the member list**

Name your Discord application **YouTube Music** so the label reads “Listening to YouTube Music”.

---

## Quick install (Windows)

### Option A — installer script (recommended)

1. Install [Python 3.10+](https://www.python.org/downloads/) (check **Add python.exe to PATH**)
2. Open PowerShell in this folder
3. Run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Build -ClientId YOUR_APP_ID -StartWithWindows -StartNow
```

Replace `YOUR_APP_ID` with your Discord Application ID.

### Option B — run from source (dev)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
copy config.example.json config.json
notepad config.json   # set client_id
python -m ytm_discord
```

---

## Discord Application ID

1. Open https://discord.com/developers/applications
2. **New Application** → name it `YouTube Music`
3. Copy **Application ID** into `config.json` as `client_id`

---

## Requirements while running

- Discord **desktop** app open (not only browser)
- music.youtube.com playing in Chrome / Edge / Brave / Firefox / Opera / Vivaldi
- This updater process running

---

## Uninstall

```powershell
powershell -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\Programs\ytm-discord-status\uninstall.ps1"
```

Config is kept in `%LOCALAPPDATA%\ytm-discord-status\` unless you delete it.
