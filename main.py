import customtkinter as ctk
from gui import TwitchBotGUI
import os
import sys
import subprocess

# Check and install required packages if needed
def ensure_packages_installed():
    required_packages = [
        "pillow",
        "pytube",
        "yt-dlp",  # Более надежная альтернатива для получения метаданных YouTube
        "requests",
        "customtkinter",
        "twitchio",
        "yandex-music"  # Add Yandex Music API support
    ]
    
    for package in required_packages:
        try:
            module_name = package.replace("-", "_").replace("yt-dlp", "yt_dlp").replace("customtkinter", "customtkinter")
            __import__(module_name)
        except ImportError:
            print(f"Installing {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

    # Check PIL version to ensure LANCZOS is available
    try:
        import PIL
        if not hasattr(PIL.Image, 'Resampling'):
            print("Upgrading Pillow to newer version...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pillow"])
    except Exception as e:
        print(f"Error checking PIL version: {e}")

# Disable SSL verification for PyTube (may be needed on some systems)
os.environ['PYTHONHTTPSVERIFY'] = '0'

def main():
    # Ensure required packages are installed
    ensure_packages_installed()
    
    # Set appearance mode and default color theme
    ctk.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
    ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"
    
    # Create the application window
    root = ctk.CTk()
    app = TwitchBotGUI(root)
    
    # Start the application
    root.mainloop()

if __name__ == "__main__":
    main()