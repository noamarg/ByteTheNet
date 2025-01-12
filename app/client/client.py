"""
client.py
Implementation of the client side of the speed test application.
"""

import socket
import threading
import time
from app.common.constants import DEFAULT_UDP_PORT, MAGIC_COOKIE, MSG_TYPE_OFFER
from app.common.packet_structs import unpack_offer_message
from app.common.utils import log_color

class SpeedTestClient:
    def __init__(self, listen_port=DEFAULT_UDP_PORT):
        self.listen_port = listen_port
        self.running = True

    def start(self):
        """
        Start the client:
        1. Prompt user for input (file size, #tcp, #udp).
        2. Listen for offers (UDP).
        3. Once offer is received, connect and start speed tests.
        4. Print stats and loop again.
        """
        # 1. Prompt user
        self._prompt_user()

        # 2. Start listening for offers in a thread
        threading.Thread(target=self._listen_for_offers, daemon=True).start()

        # Just keep running until Ctrl+C
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.running = False
            log_color("Client shutting down.", "\033[93m")

    def _prompt_user(self):
        """
        Prompt user for file size, number of TCP connections, number of UDP connections.
        """
        log_color("Client started, listening for offer requests...", "\033[92m")
        # Example: store user inputs in instance variables
        # For now, just placeholders
        self.requested_file_size = 1_000_000  # 1MB
        self.num_tcp_conns = 1
        self.num_udp_conns = 1

    def _listen_for_offers(self):
        """
        Listen for UDP broadcast offers. Once received, parse, connect, run speed test.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
            # Allow address reuse if needed
            udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            udp_socket.bind(('', self.listen_port))

            while self.running:
                try:
                    data, addr = udp_socket.recvfrom(2048)
                    magic_cookie, msg_type, udp_port, tcp_port = unpack_offer_message(data)

                    if magic_cookie == MAGIC_COOKIE and msg_type == MSG_TYPE_OFFER:
                        log_color(f"Received offer from {addr[0]} (UDP port {udp_port}, TCP port {tcp_port})", "\033[94m")
                        # Launch speed test in separate threads
                        self._start_speed_test(addr[0], udp_port, tcp_port)
                except Exception as e:
                    log_color(f"Error receiving offer: {e}", "\033[91m")

    def _start_speed_test(self, server_ip, server_udp_port, server_tcp_port):
        """
        Create threads for TCP and UDP connections, measure speed, etc.
        """
        log_color(f"Connecting to server {server_ip} on ports UDP={server_udp_port}, TCP={server_tcp_port}", "\033[93m")
        # Placeholder for actual speed test threads
        # For example:
        threading.Thread(target=self._tcp_download, args=(server_ip, server_tcp_port)).start()
        threading.Thread(target=self._udp_download, args=(server_ip, server_udp_port)).start()

    def _tcp_download(self, server_ip, server_tcp_port):
        """
        Connect via TCP, request file size, measure speed.
        """
        try:
            start_time = time.time()
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp_sock:
                tcp_sock.connect((server_ip, server_tcp_port))
                # Send file size + newline
                tcp_sock.sendall(f"{self.requested_file_size}\n".encode())

                total_received = 0
                while total_received < self.requested_file_size:
                    data = tcp_sock.recv(4096)
                    if not data:
                        break
                    total_received += len(data)

            elapsed = time.time() - start_time
            speed = (8 * total_received) / elapsed  # bits per second
            log_color(f"TCP transfer finished, total time: {elapsed:.2f} seconds, speed: {speed:.2f} bps", "\033[92m")

        except Exception as e:
            log_color(f"TCP download error: {e}", "\033[91m")

    def _udp_download(self, server_ip, server_udp_port):
        """
        Send a UDP request, then receive payload packets until done. Measure speed, packet loss, etc.
        """
        # Placeholder for a real UDP-based request/response
        start_time = time.time()
        total_received = 0
        # ...
        time.sleep(3)  # Just a mock for demonstration
        elapsed = time.time() - start_time
        speed = (8 * total_received) / elapsed if elapsed > 0 else 0
        log_color(f"UDP transfer finished, total time: {elapsed:.2f} seconds, speed: {speed:.2f} bps", "\033[92m")

def main():
    client = SpeedTestClient()
    client.start()

if __name__ == "__main__":
    main()
