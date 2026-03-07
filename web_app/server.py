#!/usr/bin/env python3
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent
    server = ThreadingHTTPServer(("127.0.0.1", 8000), lambda *args, **kwargs: SimpleHTTPRequestHandler(*args, directory=str(root), **kwargs))
    print("Serving on http://127.0.0.1:8000")
    server.serve_forever()


if __name__ == "__main__":
    main()
