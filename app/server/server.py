"""
server.py
Implementation of the server side of the speed test application.
"""

import socket
import threading
import time
from app.common.constants import DEFAULT_UDP_LISTEN_PORT, DEFAULT_UDP_BROADCAST_PORT, DEFAULT_TCP_PORT, UDP_BROADCAST_INTERVAL, MAGIC_COOKIE, MSG_TYPE_REQUEST
from app.common.packet_structs import pack_offer_message, unpack_request_message, pack_payload_message
from app.common.utils import get_local_ip, log_color

class SpeedTestServer:
    def __init__(self, udp_listen_port=DEFAULT_UDP_LISTEN_PORT, udp_broadcast_port=DEFAULT_UDP_BROADCAST_PORT, tcp_port=DEFAULT_TCP_PORT):
        self.udp_listen_port = udp_listen_port
        self.udp_broadcast_port = udp_broadcast_port
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
        server_ip, server_port = get_local_ip()
        log_color(f"Server started, listening on IP address {server_ip} on Port={server_port}", "\033[92m")

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
                    offer_packet = pack_offer_message(self.udp_listen_port, self.tcp_port)
                    # Print the byte hex data
                    udp_socket.sendto(offer_packet, ('<broadcast>', self.udp_broadcast_port))
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
            udp_socket.bind(('', self.udp_listen_port))
            while self.running:
                try:
                    data, addr = udp_socket.recvfrom(2048)
                    threading.Thread(target=self._handle_udp_client, args=(udp_socket, data, addr), daemon=True).start()
                except Exception as e:
                    log_color(f"UDP recv error: {e}", "\033[91m")

    def _handle_udp_client(self, udp_socket, data, addr):
        # Unpack the client request
        magic_cookie, msg_type, requested_size = unpack_request_message(data)
        if magic_cookie != MAGIC_COOKIE or msg_type != MSG_TYPE_REQUEST:
            return  # Invalid request

        segment_size = 1024
        total_segments = (requested_size + segment_size - 1) // segment_size  # integer ceil
        bytes_sent = 0

        for seg_index in range(1, total_segments + 1):
            to_send = min(segment_size, requested_size - bytes_sent)
            payload_data = b'a' * to_send  # dummy data
            
            packet = pack_payload_message(total_segments, seg_index, payload_data)
            udp_socket.sendto(packet, addr)

            bytes_sent += to_send

        log_color(f"UDP transfer to {addr} complete, total bytes sent: {bytes_sent}", "\033[92m")


def main():
    server = SpeedTestServer(udp_listen_port=13117, udp_broadcast_port=13118, tcp_port=5555)
    server.start()

if __name__ == "__main__":
    main()
