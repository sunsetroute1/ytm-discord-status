# YouTube Music → Discord status

Windows app that reads the track playing on [music.youtube.com](https://music.youtube.com) and shows it on Discord as **Listening to YouTube Music**.

## Where to see your status

This is **not** the green Spotify bar in Discord’s bottom-left (that UI is Spotify-only).

1. **User Settings → Activity Privacy → Display current activity as a status** = ON  
2. Click **your avatar (bottom-left)** → profile card shows song + artist  
3. Or check yourself in a server **member list**

Name the Discord app **YouTube Music** so it reads correctly.

### Playing a game at the same time

Discord prioritizes detected games over **Listening**, so music can disappear from the compact status while you game.

Set `display_mode` in `config.json`:

| Mode | Behavior |
|------|----------|
| `override` (default) | Sends as **Playing** so music competes with the game for the primary activity line |
| `alongside` | Sends as **Listening**; game stays primary; music still on your full profile |
| `watching` | Sends as **Watching** (middle ground) |

We cannot remove Discord’s game activity — both can exist; the client picks what to emphasize.

## Install

Full steps: [docs/INSTALL.md](docs/INSTALL.md)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Build -ClientId YOUR_DISCORD_APP_ID -StartWithWindows -StartNow
```

## Run from source

```powershell
copy config.example.json config.json
# set client_id in config.json
python -m ytm_discord
```

## How it works

- Polls Windows **System Media Transport Controls** for browser/YTM sessions  
- Updates Discord via **Rich Presence** IPC (`pypresence`)  
- Clears presence when playback stops (configurable)
- Pushes album art from the media session (hosted for Discord; iTunes fallback)

## License

MIT
