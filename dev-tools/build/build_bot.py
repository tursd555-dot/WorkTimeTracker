
# build_bot.py
from PyInstaller.__main__ import run
import os

if __name__ == "__main__":
    root = os.path.dirname(os.path.abspath(__file__))
    main_script = os.path.join(root, "bot_launcher.py")

    opts = [
        main_script,
        "--name=WorkTimeTracker_Bot",
        "--onefile",
        "--noconsole",
        "--clean",
        "--add-data", ".env;.",
        "--add-data", "secret_creds.zip;.",
        "--icon", "user_app\\sberhealf.ico",
    ]

    run(opts)