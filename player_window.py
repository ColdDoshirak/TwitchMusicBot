
import sys
import webview
import os
import time

def main():
    if len(sys.argv) < 2:
        print("Usage: player_window.py <html_file_path>")
        return
        
    html_path = sys.argv[1]
    if not os.path.exists(html_path):
        print(f"HTML file not found: {html_path}")
        return
    
    # Create and start the WebView window
    window = webview.create_window(
        "Music Bot Player",
        html_path,
        width=800,
        height=600,
        resizable=True,
        min_size=(400, 300)
    )
    
    # Start webview
    webview.start()
    
if __name__ == "__main__":
    main()
