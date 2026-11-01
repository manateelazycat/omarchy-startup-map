"""Exercise delay editing and repeated saves using an isolated real QML service."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


def main():
    source = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='startup-map-save-') as directory:
        root = Path(directory)
        plugin = root / 'Plugin'
        plugin.mkdir()
        for path in (*source.glob('*.qml'), *source.glob('*.js')):
            shutil.copy2(path, plugin / path.name)
        text = (plugin / 'Service.qml').read_text()
        text = text.replace('property var shell: null', 'property var shell: null\n  property alias testWindows: testWindows\n  property alias testFile: configFile')
        text = text.replace('  Variants {', '  Variants {\n    id: testWindows')
        text = text.replace('id: delayField', 'id: delayField\n                    objectName: "delayField"')
        text = text.replace('id: closeButton', 'id: closeButton\n            objectName: "closeButton"')
        text = text.replace('text: root.saving ? "保存中…" : "保存"', 'objectName: "saveButton"\n                text: root.saving ? "保存中…" : "保存"')
        (plugin / 'Service.qml').write_text(text)
        shutil.copytree(source / 'CompatUi', plugin / 'CompatUi')
        shutil.copy2(source / 'clipboard_read.py', plugin / 'clipboard_read.py')
        for name in ('Commons', 'Ui'):
            (root / name).symlink_to(Path('/usr/share/omarchy/shell') / name, target_is_directory=True)
        config = root / 'config/omarchy/startup-map.json'
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({'version': 1, 'entries': [dict(id='test', name='LightOS',
            command='xdg-open lzc://client/app/open?appId=test.app', monitor='TEST', position=1,
            delaySeconds=0, lazycatAppId='test.app', lazycatBoxId='test-box')]}))
        shutil.copy2(source / 'tests/save.qml', root / 'shell.qml')
        env = {**os.environ, 'QT_QPA_PLATFORM': 'wayland', 'QT_QUICK_BACKEND': 'software',
               'XDG_CONFIG_HOME': str(root / 'config'), 'QS_DISABLE_FILE_WATCHER': '1'}
        result = subprocess.run(['quickshell', '-p', str(root), '--no-color'], env=env,
                                capture_output=True, text=True, timeout=12)
        output = result.stdout + result.stderr
        if result.returncode or 'STARTUP_MAP_SAVE_PASS' not in output or re.search(
                r'STARTUP_MAP_SAVE_FAIL|FAIL!|TypeError|ReferenceError|Unable to assign|ERROR:', output):
            raise SystemExit(output)
        saved = json.loads(config.read_text())
        assert saved['entries'][0]['delaySeconds'] == 10, saved
        print('PASS: save and repeat save keep dialog open; close button closes or confirms unsaved edits')


if __name__ == '__main__':
    main()
