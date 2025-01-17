"""
client.py
Implementation of the client side of the speed test application.
"""

import socket
import threading
import time
from app.common.config import get_config
from app.common.packet_structs import unpack_offer_message, pack_request_message, unpack_payload_message
from app.common.utils import log_color, get_local_ip


class SpeedTestClient:
    def __init__(self, config: dict[str, any]):
        self.config = config
        self.state: dict[str, any] = {}
        self.running = True

    def start(self):
        """
        1. Prompt user for input
        2. Listen for offers (UDP)
        3. Connect & run speed tests
        4. Loop again
        """
        self._prompt_user()

        local_ip, _ = get_local_ip()
        self.state['local_ip'] = local_ip

        # Listen for broadcast offers in a background thread
        threading.Thread(target=self._listen_for_offers, daemon=True).start()

        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.running = False
            log_color("Client shutting down.", "\033[93m")

    def _prompt_user(self):
        log_color("Client started, listening for offer requests...", "\033[92m")
        try:
            self.requested_file_size = int(input("Enter file size in bytes (default 1MB = 1000000): ") or "1000000")
            self.num_tcp_conns = int(input("Enter number of TCP connections (default 1): ") or "1")
            self.num_udp_conns = int(input("Enter number of UDP connections (default 1): ") or "1")
        except ValueError:
            log_color("Invalid input. Falling back to defaults.", "\033[91m")
            self.requested_file_size = 1_000_000
            self.num_tcp_conns = 1
            self.num_udp_conns = 1

    def _listen_for_offers(self):
        """
        Listen for broadcast offers from servers.
        """
        local_ip : int = self.state['local_ip']
        broadcast_port : int = self.config['BROADCAST_PORT']
        expected_magic_cookie : int = self.config['MAGIC_COOKIE']
        expected_msg_type : int = self.config['MSG_TYPE_OFFER']

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
            udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            udp_socket.bind((local_ip, broadcast_port))

            while self.running:
                try:
                    data, addr = udp_socket.recvfrom(1024)
                    # Get the UDP and TCP ports from the server
                    magic_cookie, msg_type, udp_port, tcp_port = unpack_offer_message(data)

                    # If valid offer, spin up speed tests
                    if magic_cookie == expected_magic_cookie and msg_type == expected_msg_type:
                        log_color(
                            f"Received offer from {addr[0]} (UDP port {udp_port}, TCP port {tcp_port})",
                            "\033[94m"
                        )
                        self._start_speed_test(addr[0], udp_port, tcp_port)
                except Exception as e:
                    log_color(f"Error receiving offer: {e}", "\033[91m")

    def _start_speed_test(self, server_ip, server_udp_port, server_tcp_port):
        log_color(
            f"Connecting to server {server_ip} on UDP={server_udp_port}, TCP={server_tcp_port}",
            "\033[93m"
        )

        # Launch multiple TCP downloads
        tcp_threads = []
        for i in range(self.num_tcp_conns):
            t = threading.Thread(
                target=self._tcp_download,
                args=(server_ip, server_tcp_port, i + 1)
            )
            tcp_threads.append(t)
            t.start()

        # Launch multiple UDP downloads
        udp_threads = []
        for i in range(self.num_udp_conns):
            t = threading.Thread(
                target=self._udp_download,
                args=(server_ip, server_udp_port, i + 1)
            )
            udp_threads.append(t)
            t.start()

        # Wait for all threads
        for t in tcp_threads:
            t.join()
        for t in udp_threads:
            t.join()

        log_color("All transfers complete, listening for offer requests...", "\033[92m")

    def _tcp_download(self, server_ip, server_tcp_port, connection_id=1):
        try:
            start_time = time.time()
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp_sock:
                tcp_sock.connect((server_ip, server_tcp_port))
                tcp_sock.sendall(f"{self.requested_file_size}\n".encode())

                total_received = 0
                while total_received < self.requested_file_size:
                    data = tcp_sock.recv(1024)
                    if not data:
                        break
                    total_received += len(data)

            elapsed = time.time() - start_time
            # Set small value to the test time in case the result is negative
            if elapsed <= 0:
                elapsed = 1e-6
            # Calculate the download speed
            speed_bps = (8 * total_received) / elapsed

            log_color(
                f"TCP #{connection_id} finished. "
                f"Time: {elapsed:.2f}s, "
                f"Speed: {speed_bps:.2f} bps, "
                f"Bytes: {total_received}",
                "\033[92m"
            )

        except Exception as e:
            log_color(f"TCP download error (#{connection_id}): {e}", "\033[91m")

    def _udp_download(self, server_ip, server_udp_port, connection_id=1):
        expected_magic_cookie = self.config['MAGIC_COOKIE']
        expected_msg_type = self.config['MSG_TYPE_PAYLOAD']

        start_time = time.time()
        total_received_bytes = 0
        received_segments = 0
        total_segments = None

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_sock:
            udp_sock.settimeout(1.0)

            # Send request
            request_packet = pack_request_message(self.requested_file_size)
            udp_sock.sendto(request_packet, (server_ip, server_udp_port))

            while True:
                try:
                    data, addr = udp_sock.recvfrom(65535)
                except socket.timeout:
                    # No data => transfer done
                    break

                try:
                    magic_cookie, msg_type, seg_count, seg_index, payload = unpack_payload_message(data)
                except Exception:
                    # Malformed or unexpected
                    continue

                if magic_cookie != expected_magic_cookie or msg_type != expected_msg_type:
                    continue

                if total_segments is None:
                    total_segments = seg_count

                received_segments += 1
                total_received_bytes += len(payload)

        elapsed = time.time() - start_time
        if elapsed <= 0:
            elapsed = 1e-9
        speed_bps = (8 * total_received_bytes) / elapsed

        # If server doesn't send total_segments in every packet,
        # we fallback to received_segments as the total
        total_segments = total_segments if total_segments else received_segments
        if total_segments > 0:
            packet_loss = 100.0 * (1 - (received_segments / total_segments))
        else:
            packet_loss = 0.0

        log_color(
            f"UDP #{connection_id} finished. "
            f"Time: {elapsed:.2f}s, "
            f"Speed: {speed_bps:.2f} bps, "
            f"Bytes: {total_received_bytes}, "
            f"Packets: {received_segments}/{total_segments} "
            f"({100 - packet_loss:.2f}% OK)",
            "\033[92m"
        )


def main():
    config = get_config()
    client = SpeedTestClient(config)
    client.start()


if __name__ == "__main__":
    main()
