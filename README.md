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

Default includes: Spotify, Apple Music, Amazon Music, Deezer, TIDAL, SoundCloud, Pandora, iHeart, Qobuz, Napster, YouTube Music (app/PWA), **Jellyfin** (Media Player), Winamp, foobar2000, MusicBee, AIMP, iTunes, MediaMonkey, and other local players.

```json
"allow_browsers": true,
"browser_require_catalog_match": true
```

Browsers (Brave/Chrome/…) stay off the music-app list unless `allow_browsers` is true. Browser sessions must match Deezer/iTunes as a real song, so porn / personal videos / random YouTube do not become presence.

**Jellyfin** is supported via Jellyfin Media Player and the **web UI in a browser**. Web films/TV usually publish title-only metadata with a long runtime; those are treated as Jellyfin when `jellyfin` is on the whitelist. Random YouTube tabs (channel as artist) still need a music catalog match.

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
