import json
import tkinter as tk
import time
import os
import pystray
import requests
import sqlite3

from tkinter import filedialog
from pypresence import Presence
from pystray import MenuItem as item
from io import BytesIO
from PIL import Image

CONFIG_FILE = "config.json"
CLIENT_ID = '1249052449394659450'
LOCK_FILE = "lockfile"

def load_config():
    with open(CONFIG_FILE, "r") as file:
        return json.load(file)

def save_config(config):
    with open(CONFIG_FILE, "w") as file:
        json.dump(config, file, indent=4)

def create_lock_file():
    with open(LOCK_FILE, "w") as lock_file:
        lock_file.write(str(os.getpid()))
    os.system(f"attrib +h {LOCK_FILE}")

def remove_lock():
    if os.path.isfile(LOCK_FILE):
        os.remove(LOCK_FILE)

def check_lock_file():
    if os.path.isfile(LOCK_FILE):
        print("→ Another instance is already running.")
        os._exit(0)
    else:
        with open(LOCK_FILE, 'w') as f:
            f.write(str(os.getpid()))

def prompt_user_for_directory():
    root = tk.Tk()
    root.withdraw()
    return filedialog.askdirectory(title="Select Wuthering Waves Game directory")

def find_local_storage_db(game_dir):
    for root, _, files in os.walk(game_dir):
        if "LocalStorage.db" in files:
            return os.path.join(root, "LocalStorage.db")
    return None

def extract_level_and_region(value):
    try:
        data = json.loads(value)
        if "Content" in data and isinstance(data["Content"], list):
            for item in data["Content"]:
                if isinstance(item, list) and len(item) > 1:
                    details = item[1]
                    if isinstance(details, list) and len(details) > 0:
                        region = details[0].get("Region")
                        level = details[0].get("Level")
                        return region, level
    except json.JSONDecodeError as e:
        print(f"→ {e}")
    except Exception as e:
        print(f"→ {e}")
    return None, None

def extract_patch_version(value):
    try:
        return value.strip('"')
    except Exception as e:
        print(f"→ {e}")
    return None

def process_database(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    region = None
    level = None
    patch_version = None

    cursor.execute("SELECT * FROM LocalStorage WHERE key = 'SdkLevelData'")
    rows = cursor.fetchall()
    for row in rows:
        key, value = row
        region, level = extract_level_and_region(value)
        if region and level:
            print(f"{region}, {level}")

    cursor.execute("SELECT * FROM LocalStorage WHERE key = 'PatchVersion'")
    rows = cursor.fetchall()
    for row in rows:
        key, value = row
        patch_version = extract_patch_version(value)
        if patch_version:
            print(patch_version)

    conn.close()
    return region, level, patch_version

def update_presence(region, level, patch_version):
    rpc = Presence(CLIENT_ID)
    rpc.connect()
    rpc.update(
        state=f"Region: {region}",
        details=f"Union Level: {level}",
        large_image="logo",
        large_text=f"Wuthering Waves {patch_version}",
        start=int(time.time())
    )
    print("→ Discord Rich Presence updated.")
    return rpc

def main():
    check_lock_file()
    create_lock_file()

    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as file:
            json.dump({"path":""}, file)

    config = load_config()
    db_path = config.get("path", "")

    if not db_path:
        game_dir = prompt_user_for_directory()

        if not game_dir:
            print("→ User canceled folder selection.")
            return

        print(game_dir)
        db_path = find_local_storage_db(game_dir)

        if not db_path:
            print("→ Failed to locate LocalStorage.db in the provided directory.")
            return

        config["path"] = db_path
        save_config(config)
    else:
        print(db_path)

    try:
        region, level, patch_version = process_database(db_path)
        if region and level and patch_version:
            rpc = update_presence(region, level, patch_version)
            create_tray(rpc)
            try:
                while True:
                    time.sleep(60)
            except KeyboardInterrupt:
                print("→ Exiting...")
                rpc.close()
        else:
            print("→ No valid data extracted from the database.")
    except Exception as e:
        print(f"→ {e}")

def create_tray_icon():
    try:
        response = requests.get("https://files.catbox.moe/wiiuuy.png")
        if response.status_code == 200:
            image = Image.open(BytesIO(response.content))
            return image
        else:
            print(response.status_code)
            return None
    except Exception as e:
        print(f"→ {e}")
        return None

def on_exit(icon, rpc):
    icon.visible = False 
    icon.stop()
    rpc.close()
    remove_lock()
    print("→ Exiting...")
    os._exit(0)

def create_tray(rpc):
    icon_image = create_tray_icon()
    if icon_image:
        icon = pystray.Icon("WutheringWavesRPC", icon_image, "Wuthering Waves RPC")
        icon.menu = pystray.Menu(item('Exit', lambda icon, item: on_exit(icon, rpc)))
        icon.run()
    else:
        print("→ Tray icon could not be created.")

if __name__ == "__main__":
    main()
