import subprocess
import sys
import os
import time
import webbrowser
import threading

import urllib.request

def start_browser():
    # Wait until the Streamlit server starts and responds
    url = "http://localhost:8505"
    for _ in range(60):
        try:
            urllib.request.urlopen(url)
            print("\n[Krishna GeoSolar AI] Opening your web browser automatically...")
            webbrowser.open(url)
            break
        except Exception:
            time.sleep(1)

if __name__ == "__main__":
    app_path = os.path.join(os.path.dirname(__file__), "app.py")
    req_path = os.path.join(os.path.dirname(__file__), "requirements.txt")
    
    print("[Krishna GeoSolar AI] Getting everything ready for you! Please wait...")
    # Not using -q so users can see if pip is hanging or failing
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", req_path])
    
    # Start the browser opener in the background
    threading.Thread(target=start_browser, daemon=True).start()
    
    print("[Krishna GeoSolar AI] Launching the App...")
    try:
        subprocess.run([sys.executable, "-m", "streamlit", "run", app_path, "--server.port", "8505", "--server.headless", "true"])
    except KeyboardInterrupt:
        print("[Krishna GeoSolar AI] Successfully stopped.")
    except Exception as e:
        print(f"[Krishna GeoSolar AI] Failed to start: {e}")
    finally:
        print("\n[Krishna GeoSolar AI] Server exited.")
        input("Press Enter to close this window...")
