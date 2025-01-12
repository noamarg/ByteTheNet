"""
server.py
Implementation of the server side of the speed test application.
"""

import socket
import threading
import time
from app.common.constants import DEFAULT_UDP_PORT, DEFAULT_TCP_PORT, UDP_BROADCAST_INTERVAL
from app.common.packet_structs import pack_offer_message
from app.common.utils import get_local_ip, log_color

class SpeedTestServer:
    def __init__(self, udp_port=DEFAULT_UDP_PORT, tcp_port=DEFAULT_TCP_PORT):
        self.udp_port = udp_port
        self.tcp_port = tcp_port
        self.running = True

    def start(self):
        """
        Start the server: 
        1. Print initial message 
        2. Start broadcasting offers (UDP) in a thread
        3. Start listening on TCP socket
        4. Start listening on UDP socket
        """
        local_ip = get_local_ip()
        log_color(f"Server started, listening on IP address {local_ip}", "\033[92m")

        # Start offer broadcast thread
        threading.Thread(target=self._broadcast_offers, daemon=True).start()

        # Start TCP accept thread
        threading.Thread(target=self._tcp_listen, daemon=True).start()

        # Start UDP request handler thread
        threading.Thread(target=self._udp_listen, daemon=True).start()

        # Keep the main thread alive
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.running = False
            log_color("Server shutting down.", "\033[93m")

    def _broadcast_offers(self):
        """
        Broadcast offers on the UDP port once every UDP_BROADCAST_INTERVAL seconds.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
            udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            while self.running:
                try:
                    offer_packet = pack_offer_message(self.udp_port, self.tcp_port)
                    udp_socket.sendto(offer_packet, ('<broadcast>', self.udp_port))
                    time.sleep(UDP_BROADCAST_INTERVAL)
                except Exception as e:
                    log_color(f"Error broadcasting offer: {e}", "\033[91m")

    def _tcp_listen(self):
        """
        Listen for incoming TCP connections and handle them in new threads.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp_socket:
            tcp_socket.bind(('', self.tcp_port))
            tcp_socket.listen(5)
            while self.running:
                try:
                    client_sock, addr = tcp_socket.accept()
                    threading.Thread(target=self._handle_tcp_client, args=(client_sock, addr), daemon=True).start()
                except Exception as e:
                    log_color(f"Error accepting TCP connection: {e}", "\033[91m")

    def _handle_tcp_client(self, client_sock, addr):
        """
        Handle a single TCP client: read requested file size, send data, close socket.
        """
        log_color(f"Incoming TCP connection from {addr}", "\033[94m")
        try:
            with client_sock:
                # Read until newline to get file size
                data = b""
                while not data.endswith(b"\n"):
                    chunk = client_sock.recv(1024)
                    if not chunk:
                        return
                    data += chunk

                requested_size_str = data.strip().decode()
                requested_size = int(requested_size_str)  # in bytes

                # Send requested_size bytes
                chunk_size = 4096
                bytes_sent = 0
                while bytes_sent < requested_size:
                    to_send = min(chunk_size, requested_size - bytes_sent)
                    client_sock.sendall(b'a' * to_send)  # Send dummy data
                    bytes_sent += to_send

                log_color(f"Completed TCP transfer to {addr}, {bytes_sent} bytes sent.", "\033[92m")

        except Exception as e:
            log_color(f"TCP client error: {e}", "\033[91m")

    def _udp_listen(self):
        """
        Listen for UDP requests and spawn threads to handle them.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
            udp_socket.bind(('', self.udp_port))
            while self.running:
                try:
                    data, addr = udp_socket.recvfrom(2048)
                    threading.Thread(target=self._handle_udp_client, args=(udp_socket, data, addr), daemon=True).start()
                except Exception as e:
                    log_color(f"UDP recv error: {e}", "\033[91m")

    def _handle_udp_client(self, udp_socket, data, addr):
        """
        Handle a single UDP request by sending multiple payload packets.
        """
        # TODO: Parse the request, get requested file size, and send payload in chunks.
        log_color(f"Received UDP request from {addr}", "\033[94m")
        # Implementation placeholder ...
        # parse_request_message(data)
        # send multiple payload packets with sequence numbers

def main():
    server = SpeedTestServer()
    server.start()

if __name__ == "__main__":
    main()
