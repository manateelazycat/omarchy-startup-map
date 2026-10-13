"""Exercise QML paste gestures with a fake provider; never touch the real clipboard."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    source = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="startup-map-clipboard-") as directory:
        root = Path(directory)
        plugin = root / "Plugin"
        plugin.mkdir()
        shutil.copytree(source / "CompatUi", plugin / "CompatUi")
        shutil.copy2(source / "clipboard_read.py", plugin / "clipboard_read.py")
        for name in ("Commons", "Ui"):
            (root / name).symlink_to(Path("/usr/share/omarchy/shell") / name, target_is_directory=True)
        shutil.copy2(source / "tests/clipboard.qml", root / "shell.qml")
        reader = root / "wl-paste"
        reader.write_text(f"#!{sys.executable}\nimport sys, time\ntime.sleep(0.1)\n"
                          "print('primary' if '--primary' in sys.argv else '应用', end='')\n")
        reader.chmod(0o755)
        env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software",
               "XDG_CONFIG_HOME": str(root / "config"), "QS_DISABLE_FILE_WATCHER": "1",
               "PATH": str(root) + os.pathsep + os.environ["PATH"]}
        result = subprocess.run(["quickshell", "-p", str(root), "--no-color"],
                                env=env, capture_output=True, text=True, timeout=20)
        output = result.stdout + result.stderr
        if (result.returncode or "STARTUP_MAP_CLIPBOARD_PASS" not in output
                or "STARTUP_MAP_CLIPBOARD_FAIL" in output or "FAIL!" in output or "ERROR:" in output):
            raise SystemExit(output)
        print("PASS: keyboard, context menu and primary paste, typing, hidden fields and stale results")


if __name__ == "__main__":
    main()
