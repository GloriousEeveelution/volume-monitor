import sys
import time
import json
import os
import logging
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
from pystray import Icon, MenuItem, Menu
from PIL import Image
import threading

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

SAFE_VOLUMES_FILE = os.path.join(SCRIPT_DIR, "safe_volumes.json")
LOG_FILE = os.path.join(SCRIPT_DIR, "volume_monitor.log")

# Threshold above which the script reduces volume (0.0 to 1.0)
DEFAULT_THRESHOLD = 0.03
RESET_THRESHOLD = 0.1  # Threshold for detecting app resets (e.g., 10% change)

if not os.path.exists(LOG_FILE):
    open(LOG_FILE, "w").close()  # Ensure the log file exists

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def load_safe_volumes():
    #Loads the safe volumes from the JSON file.
    if os.path.exists(SAFE_VOLUMES_FILE):
        with open(SAFE_VOLUMES_FILE, "r") as file:
            logging.info("Loaded safe volumes from file.")
            return json.load(file)
    logging.info("No safe volumes file found. Starting fresh.")
    return {}

def save_safe_volumes(safe_volumes, force=False):
    #Saves the safe volumes to the JSON file if changes were made or forced.
    global last_saved_volumes
    if force or safe_volumes != last_saved_volumes:
        with open(SAFE_VOLUMES_FILE, "w") as file:
            json.dump(safe_volumes, file)
            last_saved_volumes = safe_volumes.copy()
            logging.info("Saved safe volumes to file.")

def get_application_volumes():
    #Fetches all currently running applications with audio sessions.
    sessions = AudioUtilities.GetAllSessions()
    app_volumes = {}
    for session in sessions:
        if session.Process:
            volume = session._ctl.QueryInterface(ISimpleAudioVolume)
            app_volumes[session.Process.name()] = volume
    return app_volumes

def monitor_and_set_volumes():
    global last_saved_volumes
    safe_volumes = load_safe_volumes()
    last_saved_volumes = safe_volumes.copy()

    while True:
        app_volumes = get_application_volumes()
        volumes_changed = False

        for app_name, volume_ctl in app_volumes.items():
            current_volume = volume_ctl.GetMasterVolume()

            if app_name not in safe_volumes:
                safe_volumes[app_name] = min(current_volume, DEFAULT_THRESHOLD)
                logging.info(f"New app detected: {app_name}. Set safe volume to {safe_volumes[app_name] * 100:.1f}%.")
                session = [s for s in AudioUtilities.GetAllSessions() if s.Process and s.Process.name() == app_name]
                if session:
                    session[0]._ctl.QueryInterface(ISimpleAudioVolume).SetMasterVolume(safe_volumes[app_name], None)
                volumes_changed = True
            
            # If the user manually sets the volume higher, stop enforcing the safe level
            elif current_volume != safe_volumes[app_name]:
                if current_volume - last_saved_volumes[app_name] > RESET_THRESHOLD:
                    logging.info(f"Detected abrupt reset for {app_name} to {current_volume * 100:.0f}% Setting volume back to {safe_volumes[app_name] * 100:.1f}%.")
                    session = [s for s in AudioUtilities.GetAllSessions() if s.Process and s.Process.name() == app_name]
                    if session:
                        session[0]._ctl.QueryInterface(ISimpleAudioVolume).SetMasterVolume(safe_volumes[app_name], None)
                        
                else:
                    logging.info(
                            f"User adjusted {app_name} volume to {current_volume * 100:.1f}%. Allowing user preference."
                        )
                    safe_volumes[app_name] = current_volume
                volumes_changed = True

        if volumes_changed:
            save_safe_volumes(safe_volumes)

        # Check every second
        time.sleep(1)

def create_image():
    return Image.open("F:/progg/resources/animal.png")

def on_quit(icon, item):
    icon.stop()
    try:
        logging.info("Script interrupted manually.")
        sys.exit()  # Exit the script gracefully
    except SystemExit:
        pass  # Ignore the SystemExit exception to prevent it from causing issues

def run_tray_icon():
    menu = Menu(MenuItem("Quit", on_quit))
    icon = Icon("Volume Monitor", create_image(), "Volume Monitor Running", menu)
    icon.run()

if __name__ == "__main__":
    try:
        logging.info("Starting application volume monitor...")
        tray_thread = threading.Thread(target=run_tray_icon, daemon=True)
        tray_thread.start()
        monitor_and_set_volumes()
    except KeyboardInterrupt:
        logging.info("Script interrupted manually.")
        sys.exit()  # Graceful exit if the script is interrupted
    except Exception as e:
        logging.error(f"Error occurred: {e}", exc_info=True)
