import os
import random
import threading


class ShareState:
    def __init__(self):
        self.lock = threading.Lock()
        self.shared_files = []
        self.relay_files = {}
        self.connected_clients = {}  # { websocket: {"name": str, "authenticated": bool} }
        self.gui_instance = None
        self.clipboard_text = ""
        self.active_uploads = {}
        self.save_dir = os.path.join(os.path.expanduser("~"), "Downloads", "Webdrop_Received")
        self.incoming_mode = "Normal"
        self.pin_enabled = False
        self.current_pin = str(random.randint(100000, 999999))
        self.authenticated_tokens = set()
        self.failed_attempts = {}
        self.lockout_until = {}
        self.server_loop = None


state = ShareState()