#!/usr/bin/env python3
"""Read the signed-in LazyCat launcher's catalog without persisting credentials."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import ssl
import struct
import sys
import urllib.error
import urllib.parse
import urllib.request

MAX_RESPONSE = 8 * 1024 * 1024
APP_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,255}\Z")
# These are alternate window titles observed in the Linux launcher. Keep them
# separate from the editable entry name (and the server's English catalog).
ALIASES = {
    "cloud.lazycat.shell.files": ["懒猫网盘", "Cloud Drive"],
    "cloud.lazycat.lightos.entry": ["LCMD WebShell", "LightOS WebShell"],
    "cloud.lazycat.app.todolist": ["懒猫清单"],
    "cloud.lazycat.catlink.wechat": ["远程微信", "Remote WeChat"],
}
ALWAYS_HIDDEN = {"cloud.lazycat.shell.home", "cloud.lazycat.shell"}


def cache_root() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "omarchy/startup-map/lazycat"


def valid_app_id(value: str) -> bool:
    return bool(APP_ID.fullmatch(value))


def launch_uri(app_id: str) -> str:
    if not valid_app_id(app_id):
        raise ValueError("懒猫微服应用 ID 无效")
    return "lzc://client/app/open?" + urllib.parse.urlencode({"appId": app_id})


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_url(url: str, *, headers=None, data=None, limit=MAX_RESPONSE,
             context=None, timeout=4) -> tuple[bytes, str]:
    # Never route local session credentials through environment proxy settings,
    # or forward them to a redirect/login page.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
                                        urllib.request.HTTPSHandler(context=context))
    request = urllib.request.Request(url, headers=headers or {}, data=data)
    with opener.open(request, timeout=timeout) as response:
        body = response.read(limit + 1)
        if len(body) > limit:
            raise ValueError("懒猫微服响应过大")
        return body, response.headers.get_content_type()


class Client:
    def __init__(self):
        # The launcher itself uses ~/.config even when XDG_CONFIG_HOME differs.
        path = Path.home() / ".config/lzc-client-desktop/core.cfg"
        config = json.loads(path.read_text())
        if not isinstance(config, dict) or not isinstance(config.get("extra_headers"), dict):
            raise ValueError("懒猫微服启动器连接信息无效")
        port = config.get("http_port")
        token = config.get("extra_headers", {}).get("LZC_MISC_AUTH_TOKEN")
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535 or not isinstance(token, str) or not token:
            raise ValueError("懒猫微服启动器连接信息无效")
        self.local_origin = f"http://127.0.0.1:{port}"
        self.local_headers = {"LZC_MISC_AUTH_TOKEN": token}

    def local(self, path: str) -> dict:
        data, _ = read_url(self.local_origin + path, headers=self.local_headers, timeout=1)
        return json.loads(data)

    def box(self) -> dict:
        box = self.local("/default-box")
        if not isinstance(box, dict) or not box.get("boxId") or box.get("status") != 2:
            raise ValueError("请先在懒猫微服启动器中登录并连接微服")
        domain = str(box.get("boxDomain") or "")
        if not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?", domain):
            raise ValueError("微服域名无效")
        return box

    def session(self, box: dict) -> tuple[str, dict, ssl.SSLContext]:
        origin = "https://" + box["boxDomain"]
        info = self.local("/box-ext-info?" + urllib.parse.urlencode({"url": origin + "/"}))
        cookies = info.get("cookies", [])
        token = next((c.get("value", "") for c in cookies if c.get("name") == "Lzc-Auth-Token"), "")
        if not token or any(c in token for c in "\r\n;"):
            raise ValueError("请先在懒猫微服启动器中登录")
        context = ssl.create_default_context()
        addresses = {item[4][0] for item in socket.getaddrinfo(box["boxDomain"], 443, type=socket.SOCK_STREAM)}
        # LazyCat's authenticated overlay uses private certificates. Match the
        # launcher's behavior ONLY for its fc03::/16 overlay, never public TLS.
        overlay = ipaddress.ip_network("fc03::/16")
        if addresses and all(ipaddress.ip_address(address) in overlay for address in addresses):
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        # LC_ALL=C is commonly set by launch wrappers for machine-readable
        # output; LANGUAGE/LC_MESSAGES/LANG express the user's display language.
        language = (os.environ.get("LANGUAGE") or os.environ.get("LC_MESSAGES")
                    or os.environ.get("LANG") or "en").split(":")[0].split(".")[0].replace("_", "-")
        if language in ("C", "POSIX") or not re.fullmatch(r"[a-zA-Z-]+", language):
            language = "en"
        return origin, {"Cookie": "Lzc-Auth-Token=" + token, "Accept-Language": language}, context


def varint(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    for shift in range(0, 70, 7):
        if offset >= len(data):
            raise ValueError("微服协议数据不完整")
        byte = data[offset]
        offset += 1
        value |= (byte & 127) << shift
        if byte < 128:
            return value, offset
    raise ValueError("微服协议整数无效")


def fields(data: bytes):
    offset = 0
    while offset < len(data):
        tag, offset = varint(data, offset)
        number, wire = tag >> 3, tag & 7
        if number == 0:
            raise ValueError("微服协议字段无效")
        if wire == 0:
            value, offset = varint(data, offset)
        elif wire in (1, 2, 5):
            if wire == 2:
                size, offset = varint(data, offset)
            else:
                size = 8 if wire == 1 else 4
            if offset + size > len(data):
                raise ValueError("微服协议字段不完整")
            value = data[offset:offset + size]
            offset += size
        else:
            raise ValueError("微服协议字段类型无效")
        yield number, wire, value


def decode_apps(data: bytes) -> list[dict]:
    """Decode the small subset of PackageManager AppInfo used by the picker."""
    apps = []
    offset = 0
    status = None
    names = {1: "appId", 2: "status", 4: "name", 6: "icon", 7: "domain",
             14: "deployId", 19: "resourceOnly", 20: "hiddenFromLauncher"}
    while offset < len(data):
        if offset + 5 > len(data):
            raise ValueError("微服协议帧不完整")
        flags, size = data[offset], struct.unpack_from(">I", data, offset + 1)[0]
        offset += 5
        payload = data[offset:offset + size]
        if len(payload) != size:
            raise ValueError("微服协议帧不完整")
        offset += size
        if flags == 128:
            trailers = dict(line.split(":", 1) for line in payload.decode().splitlines() if ":" in line)
            status = trailers.get("grpc-status", "").strip()
            continue
        if flags != 0:
            raise ValueError("不支持的微服协议帧")
        for number, wire, value in fields(payload):
            if number != 1 or wire != 2:
                continue
            app = {}
            for number, wire, value in fields(value):
                if number in names:
                    expected = 0 if number in (2, 19, 20) else 2
                    if wire != expected:
                        raise ValueError("微服应用字段类型无效")
                    app[names[number]] = value.decode("utf-8") if wire == 2 else value
            apps.append(app)
    if status != "0":
        raise ValueError("微服应用查询失败，请检查启动器登录状态")
    return apps


def catalog_entries(apps: list[dict], box: dict) -> list[dict]:
    entries = {}
    for app in apps:
        app_id = str(app.get("appId") or "")
        if not valid_app_id(app_id) or app.get("status") != 4 or app.get("hiddenFromLauncher") or app.get("resourceOnly") or app_id in ALWAYS_HIDDEN:
            continue
        if app_id == "cloud.lazycat.shell.backup" and not box.get("isAdminLogin"):
            continue
        name = str(app.get("name") or app_id)
        aliases = ALIASES.get(app_id, [])
        entries[app_id] = {
            "id": "lazycat:" + box["boxId"] + ":" + app_id,
            "name": name, "execString": "xdg-open " + launch_uri(app_id), "icon": "",
            "keywords": ["懒猫", "微服", "lazycat", box.get("boxName", ""), *aliases],
            "source": "lazycat", "lazycatAppId": app_id, "lazycatBoxId": box["boxId"],
            "lazycatBoxName": str(box.get("boxName") or ""),
            "lazycatWindowTitles": list(dict.fromkeys([name, *aliases])),
        }
    return list(entries.values())


def load_catalog() -> dict:
    client = Client()
    box = client.box()
    origin, headers, context = client.session(box)
    raw, _ = read_url(origin + "/_lzc/runtime/grpc/cloud.lazycat.apis.sys.PackageManager/QueryApplication",
                      headers={**headers, "Content-Type": "application/grpc-web+proto", "X-Grpc-Web": "1"},
                      data=b"\0" * 5, context=context)
    apps = decode_apps(raw)
    entries = catalog_entries(apps, box)
    directory = cache_root() / hashlib.sha256(box["boxId"].encode()).hexdigest()[:20]
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)

    def icon(entry):
        # Use the launcher's canonical icon route, so credentials never go to
        # third-party URLs in app metadata. Cache only image bytes and metadata.
        path = directory / (entry["lazycatAppId"] + ".png")
        if not path.is_file():
            try:
                image, mime = read_url(origin + "/sys/icons/" + entry["lazycatAppId"] + ".png",
                                       headers=headers, limit=3 * 1024 * 1024, context=context, timeout=2)
                if mime == "image/png" and image.startswith(b"\x89PNG\r\n\x1a\n"):
                    temp = path.with_suffix(".tmp")
                    temp.write_bytes(image)
                    temp.replace(path)
            except (OSError, ValueError):
                pass  # An icon failure must not hide an otherwise usable app.
        if path.is_file():
            entry["icon"] = path.as_uri()
        return entry

    with ThreadPoolExecutor(max_workers=8) as pool:
        entries = list(pool.map(icon, entries))
    result = {"entries": entries, "warning": "", "boxName": box.get("boxName", "")}
    path = cache_root() / "catalog.json"
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(result, ensure_ascii=False))
    temp.replace(path)
    return result


def catalog() -> dict:
    try:
        return load_catalog()
    except (OSError, ValueError, KeyError, TypeError):
        # Do not emit exceptions containing authenticated URLs or headers.
        warning = "懒猫微服未连接；连接并登录启动器后重新打开搜索可刷新"
        try:
            cached = json.loads((cache_root() / "catalog.json").read_text())
            if isinstance(cached.get("entries"), list):
                return {**cached, "warning": warning + "（显示缓存）"}
        except (OSError, ValueError, AttributeError):
            pass
        return {"entries": [], "warning": warning if (Path.home() / ".config/lzc-client-desktop").exists() else ""}


if __name__ == "__main__":
    print(json.dumps(catalog(), ensure_ascii=False))
