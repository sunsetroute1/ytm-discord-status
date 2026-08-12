# Install guide — YouTube Music → Discord status

## Where your status shows in Discord

Custom Rich Presence is **not** the green Spotify panel in the bottom-left.

You will see it as:

1. **User Settings → Activity Privacy** → enable **Display current activity as a status**
2. Click **your avatar (bottom-left)** → profile card → **Listening to YouTube Music** with song + artist
3. Or open a server and look at **yourself in the member list**

Name your Discord application **YouTube Music** so the label reads correctly.

### Games + music

Discord prioritizes game detection over Listening activities. Use `display_mode` in config:

- `override` (default) — send as Playing (competes with game status)
- `alongside` — Listening (game stays primary; music on full profile)
- `watching` — Watching activity type

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

## Whitelist-only privacy

Only apps on the whitelist are watched (Spotify, Deezer, Winamp, foobar2000, …).  
Everything else is ignored.

`allow_browsers: true` adds Brave/Chrome/etc., but `browser_require_catalog_match: true` (default) requires a Deezer/iTunes song match so personal/adult/random video tabs never become Discord presence.

---

The packaged exe is built with `--noconsole` (no terminal window).

- Start: Start Menu → **YouTube Music Discord Status**
- Stop: Start Menu → **Stop YouTube Music Discord Status**
- Logs: `%LOCALAPPDATA%\ytm-discord-status\ytm-discord.log`

From source without a console: double-click `run_hidden.vbs`.

## Album art

Discord shows `?` when it cannot fetch `large_image`. This app prefers **Deezer** then **iTunes** CDN URLs (those proxy cleanly). Catbox links are avoided because Discord often cannot load them.

Optional: set `artwork_webhook` in config to a Discord channel webhook to host exact media-session covers on `cdn.discordapp.com`.

You do **not** need to restart Discord for art/status changes — open your profile card (or Ctrl+R if the client UI looks stuck).

- Discord **desktop** app open (not only browser)
- music.youtube.com playing in Chrome / Edge / Brave / Firefox / Opera / Vivaldi
- This updater process running

---

## Uninstall

```powershell
powershell -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\Programs\ytm-discord-status\uninstall.ps1"
```

Config is kept in `%LOCALAPPDATA%\ytm-discord-status\` unless you delete it.
