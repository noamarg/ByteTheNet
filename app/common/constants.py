"""
constants.py
This module holds shared constants used across the client and server.
"""

# Magic Cookie for Offer/Request/Payload
MAGIC_COOKIE = 0xabcddcba

# Message Types
MSG_TYPE_OFFER = 0x2
MSG_TYPE_REQUEST = 0x3
MSG_TYPE_PAYLOAD = 0x4

# Default Ports
DEFAULT_UDP_PORT = 13117
DEFAULT_TCP_PORT = 5555

# Others
UDP_BROADCAST_INTERVAL = 1  # in seconds
UDP_PAYLOAD_SIZE = 1024     # bytes (example)
