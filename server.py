import json
import socket
import threading
import time
from os import urandom

import cv2
import numpy as np
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from mss import MSS

from protocol import create_packet_header, header_struct_size

max_chunk_size = 1400 - header_struct_size

announcement_port = 26762
multicast_group = '224.67.67.67'
multicast_port = 20202
ttl = 1

broadcast_fps = 30

class Server:
    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)

        self.is_sharing_screen = False
        self.frame_id = 1
        self.should_keep_freezing = False

        self.encryption_salt = urandom(12)
        self.encryption_kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.encryption_salt,
            iterations=200_000,
        )
        self.key = None
        self.aesgcm = None

        self.multicast_info = {
            "port": multicast_port,
            "group": multicast_group,
            "salt": self.encryption_salt.hex()
        }
        self.announcement_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.announcement_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.announcement_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        threading.Thread(target=self.announce_multicast_group, args=[]).start()

    def announce_multicast_group(self):
        while True:
            self.announcement_socket.sendto(json.dumps(self.multicast_info).encode(), ("255.255.255.255", announcement_port))
            time.sleep(1)

    def start_screen_share(self):
        if (not self.key) or (not self.aesgcm):
            raise Exception("No Key or AESGCM set.")

        self.is_sharing_screen = True
        with MSS() as sct:
            while self.is_sharing_screen:
                success, frame = self._capture_screen_frame(sct)
                frame_bytes = frame.tobytes()

                if success:
                    self.frame_id += 1
                    try:
                        self.send_multicast_message(frame_bytes, self.frame_id)
                        print("Sent message")
                        time.sleep(1/broadcast_fps)

                    except OSError as e:
                        print(f"Error: {e}\nMessage length: {len(frame_bytes)}")
                        time.sleep(1)

    def stop_screen_share(self):
        self.is_sharing_screen = False

    def _capture_screen_frame(self, sct: MSS):
        frame = sct.grab(sct.monitors[1])
        array = np.array(frame)

        frame_bgr = cv2.cvtColor(array, cv2.COLOR_BGRA2BGR)

        success, jpg_img = cv2.imencode('.jpg', frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])

        return success, jpg_img


    def send_multicast_message(self, message: bytes, frame_id: int):
        if not self.aesgcm:
            raise Exception("No AESGCM set.")
        message, nonce = self.encrypt_message(message)

        total_chunks = (len(message) + max_chunk_size - 1) // max_chunk_size

        for chunk_index, i in enumerate(range(0, len(message), max_chunk_size)):
            chunk_end = min(i + max_chunk_size, len(message))
            chunk_size = chunk_end - i
            print(f"Sending chunk {i} to {(multicast_group, multicast_port)}\nChunk size: {chunk_size}")
            packet = create_packet_header(frame_id, chunk_index, total_chunks, nonce) + message[i:chunk_end]
            self.socket.sendto(packet, (multicast_group, multicast_port))


    def create_key(self, password: str):
        self.key = self.encryption_kdf.derive(password.encode())
        self.aesgcm = AESGCM(self.key)


    def encrypt_message(self, message: bytes):
        nonce = urandom(12)
        return self.aesgcm.encrypt(nonce, message, b""), nonce

    def kill_server_and_client(self):
        for i in range(5):
            payload, nonce = self.encrypt_message(json.dumps({"command": "kill"}).encode())
            message = create_packet_header(0, 0, 1, nonce) + payload
            self.socket.sendto(message, (multicast_group, multicast_port))
            time.sleep(1)

        self.socket.close()

    def start_freeze(self):
        self.should_keep_freezing = True
        while self.should_keep_freezing:
            payload, nonce = self.encrypt_message(json.dumps({"command": "freeze", "timestamp": time.time() + 5}).encode())
            message = create_packet_header(0, 0, 1, nonce) +  payload
            self.socket.sendto(message, (multicast_group, multicast_port))
            time.sleep(1)

    def stop_freeze(self):
        self.should_keep_freezing = False

    def send_shutdown_command(self):
        for i in range(5):
            payload, nonce = self.encrypt_message(json.dumps({"command": "death"}).encode())
            message = create_packet_header(0, 0, 1, nonce) + payload
            self.socket.sendto(message, (multicast_group, multicast_port))
            time.sleep(1)