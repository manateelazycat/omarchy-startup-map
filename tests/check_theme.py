"""Check real QML dialogs and live theme bindings without launching user apps."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


def main():
    source = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="startup-map-theme-") as directory:
        root = Path(directory)
        plugin = root / "Plugin"
        plugin.mkdir()
        for path in (*source.glob("*.qml"), *source.glob("*.js")):
            shutil.copy2(path, plugin / path.name)
        # A local side-panel integration may be present in the checkout.
        # Keep this test independent of other installed third-party plugins.
        service = plugin / "Service.qml"
        text = service.read_text()
        text = re.sub(r'^import .* as SidePanelUi.*\n', '', text, flags=re.M)
        text = re.sub(r'^.*SidePanelUi.PopupStyler.*\n', '', text, flags=re.M)
        text = text.replace('visible: root.opened && root.dialogScreenName === modelData.name', 'visible: false')
        service.write_text(text)
        shutil.copytree(source / "CompatUi", plugin / "CompatUi")
        for name in ("Commons", "Ui"):
            (root / name).symlink_to(Path('/usr/share/omarchy/shell') / name, target_is_directory=True)
        shutil.copy2(source / "tests/theme.qml", root / "shell.qml")
        env = {**os.environ, "QT_QPA_PLATFORM": "wayland", "QT_QUICK_BACKEND": "software",
               "XDG_CONFIG_HOME": str(root / "config"), "QS_DISABLE_FILE_WATCHER": "1"}
        result = subprocess.run(["quickshell", "-p", str(root), "--no-color"],
                                env=env, capture_output=True, text=True, timeout=15)
        output = result.stdout + result.stderr
        if result.returncode or "STARTUP_MAP_THEME_PASS" not in output or re.search(
                r"STARTUP_MAP_THEME_FAIL|TypeError|ReferenceError|Unable to assign|ERROR:|Cannot read property", output):
            raise SystemExit(output)
        print("PASS: main dialog, app picker, confirmation and controls follow dark/light theme colors")


if __name__ == '__main__':
    main()
