"""Run the chat app: ``python -m ferrero.web`` (http://127.0.0.1:8000, or FERRERO_PORT)."""
from __future__ import annotations

import argparse
import logging
import os


def main(argv: list[str] | None = None) -> None:
    import uvicorn

    from ..config import get_settings
    from .app import create_app

    get_settings()  # loads .env, so FERRERO_PORT can come from there too
    parser = argparse.ArgumentParser(prog="ferrero-web", description="Run the Ferrero assistant web app.")
    parser.add_argument("--host", default="127.0.0.1", help="interface to bind (default 127.0.0.1: this machine only)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("FERRERO_PORT") or 8000))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    uvicorn.run(create_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
