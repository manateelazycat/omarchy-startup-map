#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
plugin_id="io.github.manateelazycat.startup-map"
plugin_dir="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/plugins/$plugin_id"
shell_config="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/shell.json"

if [[ -e "$plugin_dir" && ! -L "$plugin_dir" ]]; then
  echo "插件目录已存在，无法建立项目链接：$plugin_dir" >&2
  exit 1
fi
if [[ -L "$plugin_dir" && "$(readlink -f -- "$plugin_dir")" != "$project_dir" ]]; then
  echo "插件目录已经指向其他位置：$plugin_dir" >&2
  exit 1
fi

omarchy plugin validate "$project_dir"
mkdir -p -- "$(dirname -- "$plugin_dir")"
ln -sfn -- "$project_dir" "$plugin_dir"
export OMARCHY_SHELL_IPC_TIMEOUT=20s
omarchy-shell shell rescanPlugins

discovered=false
for ((attempt = 0; attempt < 20; attempt++)); do
  if omarchy plugin list --json 2>/dev/null | jq -e --arg id "$plugin_id" 'any(.[]; .id == $id)' >/dev/null; then
    discovered=true
    break
  fi
  sleep 1
done
if [[ "$discovered" != true ]]; then
  echo "Omarchy Shell 未能发现插件，请检查 shell 运行状态" >&2
  exit 1
fi

if [[ -f "$shell_config" ]]; then
  cp -p -- "$shell_config" "$shell_config.bak.startup-map.$(date +%Y%m%d%H%M%S)"
fi
omarchy plugin enable "$plugin_id"
omarchy bar move "$plugin_id" --section right
echo "Startup Map 已安装到任务栏右侧。"
