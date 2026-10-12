"""Start the PhotoThin review app:  python -m webapp"""

import argparse
import threading
import webbrowser

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Run the PhotoThin review web app.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--no-browser", action="store_true", help="don't open the app in a browser"
    )
    args = parser.parse_args()

    # Only listen on this computer. The app reads and moves your files, so it
    # should not be reachable from other devices on the network.
    host = "127.0.0.1"
    url = f"http://{host}:{args.port}"
    print(f"PhotoThin is running at {url}  (press Ctrl+C to stop)")
    if not args.no_browser:
        threading.Timer(1.5, webbrowser.open, args=(url,)).start()

    uvicorn.run("webapp.server:create_app", factory=True, host=host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
