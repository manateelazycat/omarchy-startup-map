# Omarchy Startup Map

English | [简体中文](README.zh-CN.md)

![Startup Map monitor and application settings](preview.png)

![Search installed applications by name](app-search.jpg)

Launch applications at login into a numbered workspace position on each monitor. Positions start at 1 on every monitor and are mapped to Hyprland workspace IDs internally. Multiple apps can share a position. Positions do not control app launch order.

## Requirements

- Omarchy Quattro with Quickshell and Hyprland Lua support.
- `python3`, `hyprctl`, and `uwsm-app` for launching apps at login; `gtk-launch` for apps selected from the search dialog.
- `jq` only when using the local `./install.sh` script.

## Install

Install from GitHub with `omarchy plugin add https://github.com/manateelazycat/omarchy-startup-map --enable --yes`. From a local checkout, run `./install.sh`. The plugin places its icon on the right side of the Omarchy bar.

Click the icon to edit entries. On multiple monitors, select a monitor from the diagram first. Each entry has a name, launch command, and monitor-local workspace position. The command accepts an absolute executable path or a `.desktop` `Exec` line. The search button filters installed apps and fills the name and `Exec` line. Deleting a filled entry requires confirmation; empty entries are removed immediately. Save writes `~/.config/omarchy/startup-map.json`; changes take effect at the next login.

Run `omarchy-shell io.github.manateelazycat.startup-map show` to open the dialog from a terminal.
Remove the plugin with `omarchy plugin remove io.github.manateelazycat.startup-map --yes`.

The launcher uses Hyprland startup rules and follows the first new window that retains its launch token, preferring a window whose initial title matches the entry name. Later windows keep their normal Hyprland window rules. Apps that reuse another process or create windows through a separate service may need a direct executable command instead of a `.desktop` launch so the window retains the token.

## Check

```bash
python3 -m unittest discover -s tests -v
omarchy plugin validate .
/usr/lib/qt6/bin/qmllint -I /usr/share/omarchy/shell Service.qml BarWidget.qml
python3 startup_map.py dry-run
```

GPL-3.0-only. Monitor diagram geometry is adapted from [Omarchy Display Reset](https://github.com/manateelazycat/omarchy-display-reset).
