"""
packet_structs.py
Helper functions to pack and unpack packet data using Python's struct module.
"""

import struct
from app.common.config import get_config

CONFIG = get_config()

def pack_offer_message(udp_port: int, tcp_port: int) -> bytes:
    """
    Pack an offer message:
    [ magic cookie (4 bytes), msg type (1 byte), server UDP port (2 bytes), server TCP port (2 bytes) ]
    """
    # '!IBHH' => Network Byte Order, 4-byte int, 1-byte int, 2-byte short, 2-byte short
    return struct.pack('!IBHH', CONFIG['MAGIC_COOKIE'], CONFIG['MSG_TYPE_OFFER'], udp_port, tcp_port)

def unpack_offer_message(data: bytes):
    """
    Unpack an offer message. Returns (magic_cookie, msg_type, udp_port, tcp_port).
    Raises struct.error if the data is malformed.
    """
    magic_cookie, msg_type, udp_port, tcp_port = struct.unpack('!IBHH', data)
    return magic_cookie, msg_type, udp_port, tcp_port

def pack_request_message(file_size: int) -> bytes:
    """
    Pack a request message:
    [ magic cookie (4 bytes), msg type (1 byte), file size (8 bytes) ]
    """
    return struct.pack('!IBQ', CONFIG['MAGIC_COOKIE'], CONFIG['MSG_TYPE_REQUEST'], file_size)

def unpack_request_message(data: bytes):
    """
    Unpack a request message. Returns (magic_cookie, msg_type, file_size).
    """
    magic_cookie, msg_type, file_size = struct.unpack('!IBQ', data)
    return magic_cookie, msg_type, file_size

def pack_payload_message(total_segments: int, current_segment: int, payload: bytes) -> bytes:
    """
    Pack a payload message:
    [ magic cookie (4 bytes), msg type (1 byte), total_segments (8 bytes),
      current_segment (8 bytes), payload (variable) ]
    """
    header = struct.pack('!IBQQ', CONFIG['MAGIC_COOKIE'], CONFIG['MSG_TYPE_PAYLOAD'], total_segments, current_segment)
    return header + payload

def unpack_payload_message(data: bytes):
    """
    Unpack a payload message. Returns (magic_cookie, msg_type, total_segments, current_segment, payload).
    """
    header_size = struct.calcsize('!IBQQ')
    header = data[:header_size]
    payload = data[header_size:]
    magic_cookie, msg_type, total_segments, current_segment = struct.unpack('!IBQQ', header)
    return magic_cookie, msg_type, total_segments, current_segment, payload
