"""Run the existing mock and assistant together; stop both on exit."""

import os
import signal
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv


def main():
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    children = []
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        for module, port in [("northstar.api", "8001"), ("starter.agent", "8000")]:
            env = {**os.environ, "PORT": port}
            children.append(subprocess.Popen([sys.executable, "-m", module], env=env))
        print(
            "Demo: http://localhost:8000 (each conversation uses a fresh synthetic session)",
            flush=True,
        )
        while all(child.poll() is None for child in children):
            try:
                children[0].wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == "__main__":
    main()
