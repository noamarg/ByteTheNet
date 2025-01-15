"""
utils.py
General helper functions and classes used by both client and server.
"""

import socket
import time

def get_local_ip() -> tuple[str, str]:
    """
    Returns the local IP address for the default route.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # This IP/port doesn't need to be reachable; we just want to force the OS to give us a default IP
        s.connect(("8.8.8.8", 80))
        ip, port = s.getsockname()
        s.close()
        return ip, port
    except Exception:
        log_color("Failed to get local IP address. Using fallback port '0'.", "\033[91m")
        return "127.0.0.1", "0"

def current_millis() -> int:
    """
    Returns the current time in milliseconds.
    """
    return int(round(time.time() * 1000))

def log_color(msg: str, color_code: str = "\033[0m"):
    """
    Prints a message with ANSI color codes.
    Example color codes:
      - "\033[92m" (Green)
      - "\033[93m" (Yellow)
      - "\033[91m" (Red)
      - "\033[0m"  (Reset)
    """
    print(f"{color_code}{msg}\033[0m")
