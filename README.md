# Music → Discord status

Windows app that mirrors **whitelisted music apps only** into Discord Rich Presence.

**Privacy model:** whitelist-only. Spotify, Deezer, Winamp, foobar2000, Apple Music, etc. are allowed. Everything else (browsers playing random/adult/personal video, VLC, Photos, …) is ignored unless you explicitly enable browsers — and even then a **music catalog match** is required.

## Where to see your status

Not the green Spotify bar. Click your avatar → profile card, or check a server member list.

### Playing a game at the same time

| `display_mode` | Behavior |
|----------------|----------|
| `override` (default) | **Playing** — competes with game status |
| `alongside` | **Listening** — game stays primary |
| `watching` | **Watching** |

## Whitelist

Default includes: Spotify, Apple Music, Amazon Music, Deezer, TIDAL, SoundCloud, Pandora, iHeart, Qobuz, Napster, YouTube Music (app/PWA), Winamp, foobar2000, MusicBee, AIMP, iTunes, MediaMonkey, and other local players.

```json
"allow_browsers": true,
"browser_require_catalog_match": true
```

Browsers (Brave/Chrome/…) stay off the music-app list unless `allow_browsers` is true. Browser sessions must match Deezer/iTunes as a real song, so porn / personal videos / random YouTube do not become presence.

## Install

See [docs/INSTALL.md](docs/INSTALL.md).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Build -ClientId YOUR_DISCORD_APP_ID -StartWithWindows -StartNow
```

## License

MIT
