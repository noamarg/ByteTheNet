"""
server.py
Implementation of the server side of the speed test application, using ephemeral ports.
"""

import socket
import threading
import time
from app.common.constants import (
    DEFAULT_UDP_BROADCAST_PORT,
    UDP_BROADCAST_INTERVAL,
    MAGIC_COOKIE,
    MSG_TYPE_REQUEST
)
from app.common.packet_structs import (
    pack_offer_message,
    unpack_request_message,
    pack_payload_message
)
from app.common.utils import get_local_ip, log_color

class SpeedTestServer:
    def __init__(self):
        self.running = True
        # We'll create and bind sockets later in start()

    def start(self):
        """
        1. Create + bind TCP socket (ephemeral port).
        2. Create + bind UDP 'listening' socket (ephemeral port).
        3. Start threads: broadcast offers, accept TCP, handle UDP.
        """
        server_ip, _ = get_local_ip()

        # --- 1) Create TCP socket on ephemeral port ---
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.bind(('', 0))  # 0 => ephemeral port
        self.tcp_port = self.tcp_socket.getsockname()[1]
        self.tcp_socket.listen(5)

        # --- 2) Create UDP socket on ephemeral port (for incoming requests) ---
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.bind(('', 0))  # ephemeral
        self.udp_listen_port = self.udp_socket.getsockname()[1]

        log_color(
            f"Server started, listening on IP address {server_ip}. "
            f"TCP Port={self.tcp_port}, UDP Port={self.udp_listen_port}",
            "\033[92m"
        )

        # Start threads
        threading.Thread(target=self._broadcast_offers, daemon=True).start()
        threading.Thread(target=self._tcp_listen, daemon=True).start()
        threading.Thread(target=self._udp_listen, daemon=True).start()

        # Keep main thread alive
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.running = False
            log_color("Server shutting down.", "\033[93m")

    def _broadcast_offers(self):
        """
        Broadcast offers to the fixed broadcast port (DEFAULT_UDP_BROADCAST_PORT)
        once every UDP_BROADCAST_INTERVAL seconds.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as broadcast_socket:
            broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            # We can also bind to an ephemeral port here if we want to:
            broadcast_socket.bind(('', 0))  # not strictly necessary

            while self.running:
                try:
                    # The offer must contain the ephemeral UDP & TCP ports
                    # so the client knows where to connect.
                    offer_packet = pack_offer_message(self.udp_listen_port, self.tcp_port)

                    # Send to <broadcast>, on the *fixed* broadcast port 13118
                    broadcast_socket.sendto(offer_packet, ('<broadcast>', DEFAULT_UDP_BROADCAST_PORT))

                    time.sleep(UDP_BROADCAST_INTERVAL)
                except Exception as e:
                    log_color(f"Error broadcasting offer: {e}", "\033[91m")

    def _tcp_listen(self):
        """
        Listen for incoming TCP connections on our ephemeral TCP socket.
        """
        while self.running:
            try:
                client_sock, addr = self.tcp_socket.accept()
                threading.Thread(
                    target=self._handle_tcp_client, 
                    args=(client_sock, addr), 
                    daemon=True
                ).start()
            except Exception as e:
                log_color(f"Error accepting TCP connection: {e}", "\033[91m")

    def _handle_tcp_client(self, client_sock, addr):
        """
        Handle a single TCP client: read requested file size, send data, close socket.
        """
        log_color(f"Incoming TCP connection from {addr}", "\033[94m")
        try:
            with client_sock:
                data = b""
                while not data.endswith(b"\n"):
                    chunk = client_sock.recv(1024)
                    if not chunk:
                        return
                    data += chunk

                requested_size_str = data.strip().decode()
                requested_size = int(requested_size_str)

                # Send requested_size bytes
                chunk_size = 4096
                bytes_sent = 0
                while bytes_sent < requested_size:
                    to_send = min(chunk_size, requested_size - bytes_sent)
                    client_sock.sendall(b'a' * to_send)
                    bytes_sent += to_send

                log_color(f"Completed TCP transfer to {addr}, {bytes_sent} bytes sent.", "\033[92m")

        except Exception as e:
            log_color(f"TCP client error: {e}", "\033[91m")

    def _udp_listen(self):
        """
        Listen for UDP requests on our ephemeral UDP socket and handle them.
        """
        while self.running:
            try:
                data, addr = self.udp_socket.recvfrom(2048)
                threading.Thread(
                    target=self._handle_udp_client, 
                    args=(data, addr), 
                    daemon=True
                ).start()
            except Exception as e:
                log_color(f"UDP recv error: {e}", "\033[91m")

    def _handle_udp_client(self, data, addr):
        """
        Parse the client's request and send multiple payload packets as needed.
        """
        try:
            magic_cookie, msg_type, requested_size = unpack_request_message(data)
            if magic_cookie != MAGIC_COOKIE or msg_type != MSG_TYPE_REQUEST:
                return  # Invalid request
        except Exception:
            return  # Malformed packet

        segment_size = 1024
        total_segments = (requested_size + segment_size - 1) // segment_size
        bytes_sent = 0

        for seg_index in range(1, total_segments + 1):
            to_send = min(segment_size, requested_size - bytes_sent)
            payload_data = b'a' * to_send
            packet = pack_payload_message(total_segments, seg_index, payload_data)
            self.udp_socket.sendto(packet, addr)
            bytes_sent += to_send

        log_color(f"UDP transfer to {addr} complete, total bytes sent: {bytes_sent}", "\033[92m")


def main():
    server = SpeedTestServer()
    server.start()

if __name__ == "__main__":
    main()
