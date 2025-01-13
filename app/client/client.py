"""
client.py
Implementation of the client side of the speed test application.
"""

import socket
import threading
import time
from app.common.constants import DEFAULT_UDP_BROADCAST_PORT, MAGIC_COOKIE, MSG_TYPE_OFFER, MSG_TYPE_PAYLOAD
from app.common.packet_structs import unpack_offer_message, pack_request_message, unpack_payload_message
from app.common.utils import log_color

class SpeedTestClient:
    def __init__(self, listen_port=DEFAULT_UDP_BROADCAST_PORT):
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

        # Example of more interactive input:
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
        log_color(
            f"Connecting to server {server_ip} on ports UDP={server_udp_port}, TCP={server_tcp_port}",
            "\033[93m"
        )

        tcp_threads = []
        for i in range(self.num_tcp_conns):
            t = threading.Thread(
                target=self._tcp_download,
                args=(server_ip, server_tcp_port, i + 1)  # pass an ID for logging
            )
            tcp_threads.append(t)
            t.start()

        # If you want parallel UDP as well, do the same here:
        udp_threads = []
        for i in range(self.num_udp_conns):
            t = threading.Thread(
                target=self._udp_download,
                args=(server_ip, server_udp_port, i + 1)
            )
            udp_threads.append(t)
            t.start()

        # Wait for all TCP threads to finish
        for t in tcp_threads:
            t.join()

        # Similarly wait for UDP if you launched them
        for t in udp_threads:
            t.join()

        log_color("All transfers complete, listening for offer requests...", "\033[92m")


    def _tcp_download(self, server_ip, server_tcp_port, connection_id=1):
        """
        Connect via TCP, request file size, measure speed.
        :param connection_id: used for labeling multiple TCP transfers
        """
        try:
            start_time = time.time()

            # 1. Create the TCP socket and connect
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp_sock:
                tcp_sock.connect((server_ip, server_tcp_port))

                # 2. Send file size + newline
                tcp_sock.sendall(f"{self.requested_file_size}\n".encode())

                # 3. Receive data until the requested number of bytes have arrived
                total_received = 0
                while total_received < self.requested_file_size:
                    data = tcp_sock.recv(4096)
                    if not data:
                        # Server closed the connection unexpectedly or we’ve reached the end
                        break
                    total_received += len(data)

            # 4. Compute elapsed time and average speed
            elapsed = time.time() - start_time
            if elapsed <= 0:
                elapsed = 0.000001  # prevent division by zero
            speed_bps = (8 * total_received) / elapsed  # bits per second

            # 5. Log the result
            log_color(
                f"TCP transfer #{connection_id} finished. "
                f"Total time: {elapsed:.2f} s, "
                f"Speed: {speed_bps:.2f} bps, "
                f"Bytes received: {total_received}.",
                "\033[92m"
            )

        except Exception as e:
            log_color(f"TCP download error (conn #{connection_id}): {e}", "\033[91m")


    def _udp_download(self, server_ip, server_udp_port, connection_id=1):
        """
        Send a UDP request for a file, then receive payload packets until done.
        Measure speed, packet loss, etc.
        
        :param connection_id: identifies this UDP transfer in logs.
        """
        start_time = time.time()
        total_received_bytes = 0
        received_segments = 0
        total_segments = None  # We'll learn this from the first payload packet
        
        # 1. Create a UDP socket and set a 1-second timeout
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_sock:
            udp_sock.settimeout(1.0)

            # 2. Send a "request" packet to the server, containing the requested file size
            request_packet = pack_request_message(self.requested_file_size)
            udp_sock.sendto(request_packet, (server_ip, server_udp_port))

            # 3. Loop until we timeout (indicating no more data is coming)
            while True:
                try:
                    data, addr = udp_sock.recvfrom(65535)  # Large buffer for UDP
                except socket.timeout:
                    # No data received for 1 second - assume transfer is complete
                    break

                # 4. Parse payload packets
                try:
                    magic_cookie, msg_type, seg_count, seg_index, payload = unpack_payload_message(data)
                except Exception:
                    # Ignore malformed packets
                    continue

                # 5. Validate the packet
                if magic_cookie != MAGIC_COOKIE or msg_type != MSG_TYPE_PAYLOAD:
                    # Not a valid payload packet for this protocol
                    continue

                # total_segments is in seg_count if the server set "total segment count"
                if total_segments is None:
                    total_segments = seg_count

                # 6. Tally statistics
                received_segments += 1
                total_received_bytes += len(payload)

            # End of while loop

        # 7. Compute final stats
        elapsed = time.time() - start_time
        if elapsed == 0:
            elapsed = 1e-9  # prevent division-by-zero
        speed_bps = (8 * total_received_bytes) / elapsed  # bits per second

        # If total_segments was never set, treat it as received_segments for 100% success
        total_segments = total_segments if total_segments else received_segments
        packet_loss_percent = 0.0
        if total_segments > 0:
            packet_loss_percent = 100.0 * (1 - (received_segments / total_segments))

        # 8. Print the results
        log_color(
            f"UDP transfer #{connection_id} finished. "
            f"Time: {elapsed:.2f}s, "
            f"Speed: {speed_bps:.2f} bps, "
            f"Payload bytes received: {total_received_bytes}, "
            f"Packets received: {received_segments}/{total_segments} "
            f"({100 - packet_loss_percent:.2f}% OK)",
            "\033[92m"
        )

def main():
    client = SpeedTestClient(listen_port=13118)
    client.start()

if __name__ == "__main__":
    main()
