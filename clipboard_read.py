"""Read Wayland text outside the shell, with a byte cap and total deadline."""
import json
import ctypes
import os
import selectors
import signal
import subprocess
import sys
import time

MAX_BYTES = 64 * 1024
TIMEOUT = 2.0


def terminate_with_parent(parent_pid):
    # A Loader can destroy Quickshell's Process with SIGKILL. Ensure its
    # wl-paste child exits too, even when Python cannot run its finally block.
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:  # PR_SET_PDEATHSIG
        raise OSError(ctypes.get_errno(), "Cannot set clipboard process lifetime")
    if os.getppid() != parent_pid:
        os.kill(os.getpid(), signal.SIGKILL)


def read_clipboard(primary=False):
    command = ["wl-paste", "--no-newline", "--type", "text"]
    if primary:
        command.append("--primary")
    deadline = time.monotonic() + TIMEOUT
    parent_pid = os.getpid()
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          preexec_fn=lambda: terminate_with_parent(parent_pid)) as process:
        try:
            os.set_blocking(process.stdout.fileno(), False)
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                data = bytearray()
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 or not selector.select(remaining):
                        raise TimeoutError("Clipboard transfer timed out")
                    chunk = os.read(process.stdout.fileno(), min(4096, MAX_BYTES + 1 - len(data)))
                    if not chunk:
                        if process.wait(timeout=max(0.001, deadline - time.monotonic())):
                            raise ValueError("Clipboard text unavailable")
                        return data.decode("utf-8", errors="strict")
                    data.extend(chunk)
                    if len(data) > MAX_BYTES:
                        raise ValueError("Clipboard text exceeds 64 KiB")
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()


def main():
    # Quickshell cancels an in-flight paste when its field loses focus.
    def cancel(signum, frame):
        raise SystemExit(1)

    signal.signal(signal.SIGTERM, cancel)
    try:
        print(json.dumps({"ok": True, "text": read_clipboard("--primary" in sys.argv[1:])}))
    except (OSError, ValueError, TimeoutError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"ok": False, "error": str(error)}))


if __name__ == "__main__":
    main()
