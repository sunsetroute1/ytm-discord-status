import asyncio
from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager,
)


async def main() -> None:
    mgr = await MediaManager.request_async()
    sessions = list(mgr.get_sessions())
    print(f"sessions={len(sessions)}")
    for s in sessions:
        app = s.source_app_user_model_id
        props = await s.try_get_media_properties_async()
        info = s.get_playback_info()
        status = info.playback_status if info else None
        title = props.title if props else None
        artist = props.artist if props else None
        print(f"app={app!r} status={status} title={title!r} artist={artist!r}")
        tl = s.get_timeline_properties()
        if tl:
            pos = tl.position
            print(f"  pos={pos!r} type={type(pos)}")
            print("  attrs=", [a for a in dir(pos) if not a.startswith("_")])


if __name__ == "__main__":
    asyncio.run(main())
