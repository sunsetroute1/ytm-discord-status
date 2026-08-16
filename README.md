# Music → Discord status

Windows app that mirrors now-playing media into Discord Rich Presence.

**Privacy model (default):** `media_mode: "whitelist"` — Spotify, Deezer, Winamp, foobar2000, Apple Music, Jellyfin, etc. Everything else is ignored. Browsers need a **music catalog match** when enabled.

**All-media mode:** `media_mode: "blacklist"` — mirrors any SMTC session except blocked apps (VLC, Photos, Movies & TV, meetings, …). Sensitive keywords and browser catalog gates still apply.

## Where to see your status

Not the green Spotify bar. Click your avatar → profile card, or check a server member list.

### Playing a game at the same time

| `display_mode` | Behavior |
|----------------|----------|
| `override` (default) | **Playing** — primary card; competes with game status (music and Jellyfin) |
| `alongside` | **Listening** / **Watching** — game stays primary |
| `watching` | **Watching** |

## Media modes

| `media_mode` | Behavior |
|--------------|----------|
| `whitelist` (default) | Only listed music/media apps (+ optional browsers) |
| `blacklist` | All media except `blacklist` apps |

Installer: `install.ps1 -MediaMode whitelist` or `-MediaMode blacklist` (prompts if omitted on first setup).

## Whitelist

Default includes: Spotify, Apple Music, Amazon Music, Deezer, TIDAL, SoundCloud, Pandora, iHeart, Qobuz, Napster, YouTube Music (app/PWA), **Jellyfin** (Media Player), Winamp, foobar2000, MusicBee, AIMP, iTunes, MediaMonkey, and other local players.

```json
"allow_browsers": true,
"browser_require_catalog_match": true
```

Browsers (Brave/Chrome/…) stay off the music-app list unless `allow_browsers` is true. Browser sessions must match Deezer/iTunes as a real song, so porn / personal videos / random YouTube do not become presence.

**Jellyfin** is supported via Jellyfin Media Player and the **web UI in a browser**. Presence is app-aware: films/TV use the Jellyfin Discord app (header shows **Jellyfin**); music stays on your music app. For real `S2E3` episode codes and Jellyfin posters, set:

```json
"jellyfin": {
  "base_url": "https://your-jellyfin-host",
  "api_key": "YOUR_API_KEY"
}
```

Create the API key in Jellyfin → Dashboard → API Keys. `client_id` defaults to the project Jellyfin Discord Application — override only if you maintain your own.

Web films/TV are detected as title-only + long runtime when `jellyfin` is whitelisted (or in blacklist mode). Random YouTube tabs (channel as artist) still need a music catalog match.

YouTube Music in a browser often reports a **playlist/channel name** as the artist and `Real Artist - Song` as the title. The catalog gate unwraps that pattern so legitimate tracks still show, without relaxing the privacy check.

## Listen along

Friends get a **Listen along** button, and clicking the **album art** opens the track on YouTube Music (search link).

```json
"listen_button": {
  "enabled": true,
  "label": "Listen along",
  "target": "youtube_music"
}
```

`target` can be `youtube_music`, `deezer`, or `spotify`. The button is often hidden on *your own* profile; art click / friend view is the reliable check.

## Install

See [docs/INSTALL.md](docs/INSTALL.md).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Build -ClientId YOUR_DISCORD_APP_ID -StartNow
```

## License

MIT
