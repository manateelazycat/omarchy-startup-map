import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import clipboard_read


class ClipboardReadTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.reader = Path(self.directory.name) / "wl-paste"
        self.environment = mock.patch.dict(os.environ, {
            "PATH": self.directory.name + os.pathsep + os.environ["PATH"]})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def provider(self, body):
        self.reader.write_text(f"#!{sys.executable}\nimport os, sys, time\n" + body)
        self.reader.chmod(0o755)

    def test_unicode_and_primary_selection(self):
        self.provider("assert '--primary' in sys.argv\nsys.stdout.buffer.write('应用'.encode())\n")
        self.assertEqual(clipboard_read.read_clipboard(True), "应用")

    def test_exact_byte_limit(self):
        self.provider("sys.stdout.buffer.write(b'x' * 65536)\n")
        self.assertEqual(len(clipboard_read.read_clipboard()), clipboard_read.MAX_BYTES)

    def test_oversize_is_rejected(self):
        self.provider("sys.stdout.buffer.write(b'x' * 65537)\n")
        with self.assertRaisesRegex(ValueError, "64 KiB"):
            clipboard_read.read_clipboard()

    def test_stalled_provider(self):
        self.provider("time.sleep(30)\n")
        with mock.patch.object(clipboard_read, "TIMEOUT", 0.2):
            start = time.monotonic()
            with self.assertRaises(TimeoutError):
                clipboard_read.read_clipboard()
            self.assertLess(time.monotonic() - start, 1)

    def test_trickling_provider_uses_total_deadline(self):
        self.provider("while True:\n os.write(1, b'x')\n time.sleep(0.02)\n")
        with mock.patch.object(clipboard_read, "TIMEOUT", 0.2):
            with self.assertRaises(TimeoutError):
                clipboard_read.read_clipboard()

    def test_failed_transfer_does_not_insert_partial_text(self):
        self.provider("sys.stdout.write('partial')\nsys.exit(1)\n")
        with self.assertRaisesRegex(ValueError, "unavailable"):
            clipboard_read.read_clipboard()

    def test_invalid_utf8_is_rejected(self):
        self.provider("sys.stdout.buffer.write(b'\\xff')\n")
        with self.assertRaises(UnicodeDecodeError):
            clipboard_read.read_clipboard()

    def test_cancel_kills_provider(self):
        pid_file = Path(self.directory.name) / "pid"
        self.provider(f"open({str(pid_file)!r}, 'w').write(str(os.getpid()))\ntime.sleep(30)\n")
        with subprocess.Popen([sys.executable, clipboard_read.__file__], stdout=subprocess.PIPE) as process:
            try:
                deadline = time.monotonic() + 2
                while not pid_file.exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(pid_file.exists())
                process.terminate()
                process.wait(timeout=2)
                with self.assertRaises(ProcessLookupError):
                    os.kill(int(pid_file.read_text()), 0)
            finally:
                if process.poll() is None:
                    process.kill()


    def test_destroyed_helper_kills_provider(self):
        pid_file = Path(self.directory.name) / "pid"
        self.provider(f"open({str(pid_file)!r}, 'w').write(str(os.getpid()))\ntime.sleep(30)\n")
        with subprocess.Popen([sys.executable, clipboard_read.__file__], stdout=subprocess.PIPE) as process:
            try:
                deadline = time.monotonic() + 2
                while not pid_file.exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(pid_file.exists())
                child_pid = int(pid_file.read_text())
                process.kill()
                process.wait(timeout=2)
                status = Path(f"/proc/{child_pid}/stat")
                deadline = time.monotonic() + 2
                while status.exists() and status.read_text().split()[2] != "Z" and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(not status.exists() or status.read_text().split()[2] == "Z")
            finally:
                if process.poll() is None:
                    process.kill()


if __name__ == "__main__":
    unittest.main()
