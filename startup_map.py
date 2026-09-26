#!/usr/bin/env python3
"""Login launcher for the Omarchy Startup Map shell plugin."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
import uuid


MAX_WORKSPACE = 100
TOKEN_NAME = "OMARCHY_STARTUP_MAP_TOKEN"


def config_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "omarchy" / "startup-map.json"


def hypr_json(command: str) -> list | dict:
    result = subprocess.run(
        ["hyprctl", "-j", command], capture_output=True, text=True, timeout=6, check=True
    )
    return json.loads(result.stdout)


def snapshot() -> dict:
    return {"monitors": hypr_json("monitors"), "activeWindow": hypr_json("activewindow")}


def enabled_monitors(monitors: list[dict]) -> list[dict]:
    return sorted(
        (
            monitor for monitor in monitors
            if monitor.get("name") and not monitor.get("disabled")
            and monitor.get("mirrorOf", "none") in ("", "none", None)
        ),
        key=lambda monitor: (monitor.get("y", 0), monitor.get("x", 0)),
    )


def rule_monitor(rule: dict, monitors: list[dict]) -> str:
    selector = str(rule.get("monitor") or "")
    for monitor in monitors:
        if selector == monitor.get("name"):
            return selector
        if selector.startswith("desc:") and str(monitor.get("description") or "").startswith(selector[5:]):
            return str(monitor["name"])
    return ""


def validate_entries(raw: dict) -> list[dict]:
    if not isinstance(raw, dict) or raw.get("version") != 1:
        raise ValueError("配置版本无效")
    entries = raw.get("entries")
    if not isinstance(entries, list):
        raise ValueError("应用列表无效")
    clean = []
    for index, entry in enumerate(entries, 1):
        if not isinstance(entry, dict):
            raise ValueError(f"第 {index} 条应用无效")
        name = str(entry.get("name") or "").strip()
        command = str(entry.get("command") or "").strip()
        monitor = str(entry.get("monitor") or "").strip()
        position = entry.get("position")
        if not name or not command or not monitor:
            raise ValueError(f"第 {index} 条应用缺少名称、启动命令或显示器")
        if isinstance(position, bool) or not isinstance(position, int) or not 1 <= position <= MAX_WORKSPACE:
            raise ValueError(f"第 {index} 条应用的工作区位置无效")
        clean.append({
            "id": str(entry.get("id") or index), "name": name, "command": command,
            "desktopId": str(entry.get("desktopId") or "").strip(),
            "monitor": monitor, "position": position,
        })
    return clean


def plan(entries: list[dict], monitors: list[dict], workspaces: list[dict], rules: list[dict]) -> dict:
    """Map each display's 1-based positions to unique Hyprland workspace IDs."""
    connected = enabled_monitors(monitors)
    connected_names = {monitor["name"] for monitor in connected}
    wanted = {entry["monitor"] for entry in entries if entry["monitor"] in connected_names}
    if not wanted:
        return {"entries": [], "newSlots": []}

    reserved: set[int] = set()
    owned: dict[str, set[int]] = {monitor["name"]: set() for monitor in connected}
    owner_of: dict[int, str] = {}
    for rule in rules:
        value = str(rule.get("workspaceString") or "")
        if not rule.get("enabled", True) or not value.isdecimal():
            continue
        wid = int(value)
        if not 1 <= wid <= MAX_WORKSPACE:
            continue
        reserved.add(wid)
        monitor_name = rule_monitor(rule, connected)
        if monitor_name:
            owner_of[wid] = monitor_name
            owned[monitor_name].add(wid)

    for workspace in workspaces:
        wid = workspace.get("id")
        if not isinstance(wid, int) or not 1 <= wid <= MAX_WORKSPACE:
            continue
        reserved.add(wid)
        monitor_name = str(workspace.get("monitor") or "")
        if monitor_name in owned:
            previous = owner_of.get(wid)
            if previous and previous != monitor_name:
                owned[previous].discard(wid)
            owner_of[wid] = monitor_name
            owned[monitor_name].add(wid)

    for monitor in connected:
        wid = (monitor.get("activeWorkspace") or {}).get("id")
        if isinstance(wid, int) and 1 <= wid <= MAX_WORKSPACE:
            reserved.add(wid)
            name = monitor["name"]
            previous = owner_of.get(wid)
            if previous and previous != name:
                owned[previous].discard(wid)
            owner_of[wid] = name
            owned[name].add(wid)

    next_id = max(reserved, default=0) + 1
    if next_id > MAX_WORKSPACE:
        next_id = 1
    mapped: dict[tuple[str, int], int] = {}
    new_slots = []
    for monitor in connected:
        name = monitor["name"]
        if name not in wanted:
            continue
        existing = sorted(owned[name])
        maximum = max(entry["position"] for entry in entries if entry["monitor"] == name)
        for position in range(1, maximum + 1):
            if position <= len(existing):
                wid = existing[position - 1]
            else:
                searched = 0
                while next_id in reserved:
                    next_id += 1
                    if next_id > MAX_WORKSPACE:
                        next_id = 1
                    searched += 1
                if searched >= MAX_WORKSPACE:
                    raise ValueError("可用工作区序号已用尽（上限 100）")
                wid = next_id
                reserved.add(wid)
                next_id += 1
                if next_id > MAX_WORKSPACE:
                    next_id = 1
                new_slots.append({"monitor": name, "position": position, "workspaceId": wid})
            mapped[name, position] = wid

    return {
        "entries": [
            {**entry, "workspaceId": mapped[entry["monitor"], entry["position"]]}
            for entry in entries if entry["monitor"] in wanted
        ],
        "newSlots": new_slots,
    }


def desktop_exec_to_command(command: str, name: str = "") -> str:
    """Turn common Desktop Entry Exec field codes into a launchable command."""
    command = command.strip()
    if command.startswith("Exec="):
        command = command[5:].lstrip()
    if command.startswith("/") and Path(command).is_file():
        return shlex.quote(command)
    tokens = shlex.split(command)
    result = []
    for token in tokens:
        if token == "%i":
            continue
        token = token.replace("%%", "\0")
        token = token.replace("%c", name)
        token = re.sub(r"%[fFuUdDnNickvm]", "", token)
        token = token.replace("\0", "%")
        if token:
            result.append(token)
    if not result:
        raise ValueError("启动命令为空")
    return shlex.join(result)


def launch_command(entry: dict, token: str) -> str:
    desktop_id = entry.get("desktopId", "")
    if desktop_id:
        app = desktop_id if desktop_id.endswith(".desktop") else desktop_id + ".desktop"
        command = "gtk-launch " + shlex.quote(app)
    else:
        command = desktop_exec_to_command(entry["command"], entry["name"])
    return f"uwsm-app -- env {TOKEN_NAME}={shlex.quote(token)} sh -c {shlex.quote(command)}"


def lua_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def eval_lua(code: str) -> None:
    result = subprocess.run(["hyprctl", "eval", code], capture_output=True, text=True, timeout=8)
    if result.returncode or result.stdout.strip() != "ok":
        raise RuntimeError((result.stderr or result.stdout or "hyprctl eval 失败").strip())


def launch_entry(entry: dict, token: str) -> None:
    cmd = launch_command(entry, token)
    workspace = f'{entry["workspaceId"]} silent'
    monitor = f'{entry["monitor"]} silent'
    eval_lua(
        f'hl.exec_cmd({lua_string(cmd)}, '
        f'{{ workspace = {lua_string(workspace)}, monitor = {lua_string(monitor)} }})'
    )


def provision_new_slots(slots: list[dict]) -> None:
    if not slots:
        return
    statements = [
        "hl.workspace_rule({ workspace = " + lua_string(str(slot["workspaceId"]))
        + ", monitor = " + lua_string(slot["monitor"]) + ", persistent = true })"
        for slot in slots
    ]
    eval_lua("\n".join(statements))


def proc_token(pid: int) -> str:
    try:
        values = (Path("/proc") / str(pid) / "environ").read_bytes().split(b"\0")
    except (OSError, ValueError):
        return ""
    prefix = (TOKEN_NAME + "=").encode()
    for value in values:
        if value.startswith(prefix):
            return value[len(prefix):].decode("utf-8", "replace")
    return ""


def place_window(address: str, entry: dict) -> None:
    if not re.fullmatch(r"0x[0-9a-fA-F]+", address):
        return
    wid = str(entry["workspaceId"])
    monitor = entry["monitor"]
    eval_lua(
        "hl.dispatch(hl.dsp.window.move({ workspace = " + lua_string(wid)
        + ", follow = false, window = " + lua_string("address:" + address) + " }))\n"
        + "hl.dispatch(hl.dsp.workspace.move({ workspace = " + lua_string(wid)
        + ", monitor = " + lua_string(monitor) + " }))"
    )


def watch_new_windows(token_to_entry: dict[str, dict], baseline: set[str], monitor_ids: dict[str, int]) -> None:
    if not token_to_entry:
        return
    deadline = time.monotonic() + 45
    seen = set(baseline)
    matched = set()
    completed_at = None
    while time.monotonic() < deadline:
        time.sleep(0.4)
        try:
            clients = hypr_json("clients")
        except (OSError, subprocess.SubprocessError, ValueError):
            continue
        for client in clients:
            address = str(client.get("address") or "")
            if not address or address in seen:
                continue
            seen.add(address)
            token = proc_token(client.get("pid") or 0)
            entry = token_to_entry.get(token)
            if not entry:
                continue
            matched.add(token)
            if (client.get("workspace") or {}).get("id") == entry["workspaceId"] \
                    and client.get("monitor") == monitor_ids.get(entry["monitor"]):
                continue
            try:
                place_window(address, entry)
            except RuntimeError as error:
                print(f"放置窗口失败：{entry['name']}：{error}", file=sys.stderr)
        if len(matched) == len(token_to_entry):
            if completed_at is None:
                completed_at = time.monotonic()
            elif time.monotonic() - completed_at >= 5:
                break


def mark_session_once() -> bool:
    signature = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if not signature or not runtime:
        raise RuntimeError("找不到 Hyprland 会话或 XDG_RUNTIME_DIR")
    digest = hashlib.sha256(signature.encode()).hexdigest()[:20]
    marker = Path(runtime) / f"omarchy-startup-map-{digest}.started"
    try:
        fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w") as stream:
        stream.write(str(os.getpid()))
    return True


def run(dry_run: bool = False) -> int:
    path = config_path()
    if not path.exists():
        if dry_run:
            print('{"entries": [], "newSlots": []}')
        else:
            mark_session_once()
        return 0
    entries = validate_entries(json.loads(path.read_text()))
    monitors = hypr_json("monitors")
    workspaces = hypr_json("workspaces")
    rules = hypr_json("workspacerules")
    planned = plan(entries, monitors, workspaces, rules)
    if dry_run:
        print(json.dumps(planned, ensure_ascii=False, indent=2))
        return 0
    if not mark_session_once():
        return 0
    if not planned["entries"]:
        return 0

    try:
        provision_new_slots(planned["newSlots"])
    except RuntimeError as error:
        print(f"创建工作区位置失败：{error}", file=sys.stderr)

    baseline = {str(client.get("address")) for client in hypr_json("clients")}
    monitor_ids = {monitor["name"]: monitor["id"] for monitor in monitors}
    token_to_entry = {}
    for entry in planned["entries"]:
        token = uuid.uuid4().hex
        token_to_entry[token] = entry
        try:
            launch_entry(entry, token)
        except (RuntimeError, ValueError) as error:
            print(f"启动失败：{entry['name']}：{error}", file=sys.stderr)
            del token_to_entry[token]
    watch_new_windows(token_to_entry, baseline, monitor_ids)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("snapshot", "launch", "dry-run"))
    args = parser.parse_args()
    try:
        if args.action == "snapshot":
            print(json.dumps(snapshot(), ensure_ascii=False))
            return 0
        return run(dry_run=args.action == "dry-run")
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
