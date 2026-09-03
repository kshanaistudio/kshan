import os
import sys
import threading
import time
import socket
import urllib.request
import webview

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def start_django_server(port: int):
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kshan_project.settings')
    try:
        from django.core.management import execute_from_command_line
        # Run server with noreload to avoid subprocess conflicts inside pywebview desktop shell
        execute_from_command_line(['manage.py', 'runserver', f'127.0.0.1:{port}', '--noreload'])
    except Exception as e:
        print(f"Error starting Django server: {e}", file=sys.stderr)

def wait_for_server(url: str, timeout: float = 20.0) -> bool:
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as resp:
                if resp.status in (200, 301, 302, 404):
                    return True
        except Exception:
            time.sleep(0.3)
    return False

def main():
    # Setup working directory to this script's directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)
    sys.path.insert(0, base_dir)

    port = 8000
    # If 8000 is occupied, pick a free port
    if is_port_in_use(port):
        # Try port 8080 or dynamically assign
        for p in range(8001, 8090):
            if not is_port_in_use(p):
                port = p
                break

    target_url = f"http://127.0.0.1:{port}/"

    # Start Django in a background daemon thread
    server_thread = threading.Thread(target=start_django_server, args=(port,), daemon=True)
    server_thread.start()

    print(f"🚀 Initializing KSHAN Studio on {target_url}...")
    wait_for_server(target_url, timeout=15.0)

    # Create Native Desktop Window (uses Microsoft Edge WebView2 on Windows)
    window = webview.create_window(
        title="KSHAN — AI Face Discovery & Photography Studio",
        url=target_url,
        width=1380,
        height=880,
        min_size=(960, 640),
        resizable=True,
        confirm_close=False,
        easy_drag=True
    )

    # Start native UI loop (blocks until window is closed)
    webview.start(debug=False, gui='edgechromium')
    print("Desktop application closed.")
    sys.exit(0)

if __name__ == "__main__":
    main()
