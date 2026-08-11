from __future__ import annotations

import urllib.request

data = open(r"C:\Users\sunse\projects\ytm-discord-status\art_probe.bin", "rb").read()
print("data", len(data))


def post(url: str, fields: dict[str, str], file_field: str, filename: str, raw: bytes):
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    parts: list[bytes] = []
    for key, value in fields.items():
        parts.append(f"--{boundary}".encode())
        parts.append(f'Content-Disposition: form-data; name="{key}"'.encode())
        parts.append(b"")
        parts.append(str(value).encode())
    parts.append(f"--{boundary}".encode())
    parts.append(
        f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"'.encode()
    )
    parts.append(b"Content-Type: image/png")
    parts.append(b"")
    parts.append(raw)
    parts.append(f"--{boundary}--".encode())
    parts.append(b"")
    body = b"\r\n".join(parts)
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("User-Agent", "ytm-discord-status/0.1")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.status, resp.read().decode("utf-8", "replace")


for name, url, fields, ff in [
    (
        "litterbox",
        "https://litterbox.catbox.moe/resources/internals/api.php",
        {"reqtype": "fileupload", "time": "24h"},
        "fileToUpload",
    ),
    (
        "catbox",
        "https://catbox.moe/user/api.php",
        {"reqtype": "fileupload"},
        "fileToUpload",
    ),
    (
        "0x0",
        "https://0x0.st",
        {},
        "file",
    ),
]:
    try:
        status, text = post(url, fields, ff, "cover.png", data)
        print(name, status, text)
    except Exception as exc:  # noqa: BLE001
        print(name, "ERR", type(exc).__name__, exc)
