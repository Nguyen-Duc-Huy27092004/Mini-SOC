import argparse
import os
import socket
import subprocess
import sys
import time
from pathlib import Path


def find_available_port(host: str, start_port: int, max_attempts: int = 20) -> int:
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No available port found between {start_port} and {start_port + max_attempts - 1}")


def launch_backend(host: str, start_port: int, max_attempts: int = 20) -> subprocess.Popen:
    backend_dir = Path(__file__).resolve().parent
    python_exe = sys.executable

    for port in range(start_port, start_port + max_attempts):
        print(f"Starting backend on {host}:{port}")
        proc = subprocess.Popen(
            [python_exe, "-m", "uvicorn", "main:app", "--host", host, "--port", str(port)],
            cwd=backend_dir,
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print(f"Backend is running on {host}:{port}")
            return proc

        if proc.returncode in (0, 130):
            return proc

        print(f"Port {port} is busy or failed to start, trying {port + 1}...")

    raise RuntimeError(f"Unable to start backend after {max_attempts} attempts")


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the Mini-SOC backend without crashing on a busy port")
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    parser.add_argument("--max-attempts", type=int, default=20)
    args = parser.parse_args()

    host = args.host
    start_port = args.port

    proc = launch_backend(host, start_port, args.max_attempts)
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("Server stopped")
        sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Server stopped")
        sys.exit(0)
