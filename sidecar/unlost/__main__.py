"""Entry point: python -m unlost --port 8765. Prints UNLOST_READY once the server accepts requests."""

from __future__ import annotations

import argparse
import logging
import sys

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(prog="unlost-sidecar")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stderr)
    from .server import app

    config = uvicorn.Config(app, host="127.0.0.1", port=args.port, log_level="warning")
    server = uvicorn.Server(config)

    original_startup = server.startup

    async def startup(sockets=None):
        await original_startup(sockets)
        print("UNLOST_READY", flush=True)

    server.startup = startup
    server.run()


if __name__ == "__main__":
    main()
