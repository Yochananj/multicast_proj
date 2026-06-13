import json
import platform
import socket
import struct
import subprocess
import threading
import time

import cv2
import numpy as np
import pynput
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from constants import announcement_port
from protocol import extract_header_and_payload


class Client:
    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(("", announcement_port))
        self.socket.settimeout(1)

        self.key = None
        self.aesgcm = None
        self.password = None

        self.last_displayed_frame = 1
        self.frames: dict[int, Frame] = {}

        self.frozen_until = 0
        self.freezing_thread = None

        print("Waiting for multicast announcement...")
        try:
            servers = self.listen_for_multicast_announcement()
            for i in range(len(servers)):
                print(f"Multicast {i+1}: {servers[i][0]}:{servers[i][1]}")
            chosen_server = int(input("Enter the number of the multicast server you want to connect to: ")) - 1
            group, port, self.salt = servers[chosen_server]

            self.salt = bytes.fromhex(self.salt)

            self.key = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=self.salt,
                iterations=200_000,
            ).derive(input(f"Enter password for {group}:{port}:\n").strip().encode())
            self.aesgcm = AESGCM(self.key)
            print("Password accepted. Starting to receive messages...")
        except Exception as e:
            print(f"Error: {e}, Type: {type(e)}")
            print("Exiting...")
            exit()

        self.socket.close()

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(("", port))
        self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, struct.pack("4sl", socket.inet_aton(group), socket.INADDR_ANY))
        self.get_messages()

        self.socket.close()
        cv2.destroyAllWindows()
        exit(0)

    def listen_for_multicast_announcement(self):
        servers = []
        end_time = time.time() + 5
        while time.time() < end_time:
            try:
                chunk, addr = self.socket.recvfrom(2048)
            except TimeoutError:
                continue

            try:
                info = json.loads(chunk.decode())
                if len(servers) > 0 and info["group"] in servers[:][0]:
                    continue
                servers.append((info["group"], info["port"], info["salt"]))
            except json.JSONDecodeError:
                continue
            except KeyError:
                continue

        if len(servers) == 0:
            raise Exception("Could not find multicast announcement")
        else:
            return servers


    def get_messages(self):
        while True:
            chunk, addr = self.socket.recvfrom(2048)
            print(f"recived chunk from {addr}")
            packet = Packet(chunk, self.aesgcm)

            match packet.is_video_frame:
                case True:
                    print(f"Received frame {packet.frame_id}")
                    if packet.frame_id < self.last_displayed_frame:
                        continue

                    if packet.frame_id not in self.frames.keys():
                        self.frames[packet.frame_id] = Frame(packet)
                    else:
                        self.frames[packet.frame_id] += packet

                    frame = self.frames[packet.frame_id]

                    if frame.total_packets_count == frame.packets_count:
                        try:
                            constructed_frame = self.construct_frame(frame)
                            if self.display_frame(constructed_frame): return
                            self.last_displayed_frame = frame.frame_id
                        except Exception as e:
                            print(f"Decryption failed for frame {frame.frame_id}: {e}")


                        keys_to_remove = [k for k in self.frames.keys() if k <= frame.frame_id]
                        for k in keys_to_remove:
                            self.frames.pop(k)
                case False:
                    print(f"Received command: {packet.payload}")
                    match packet.payload["command"]:
                        case "freeze":
                             if not self.freezing_thread or self.frozen_until < time.time():
                                self.freezing_thread = threading.Thread(target=self.freeze_keyboard_and_mouse, args=[packet.payload["timestamp"]])
                                self.freezing_thread.start()
                             else:
                                 self.frozen_until = packet.payload["timestamp"]
                             print(time.time(), packet.payload["timestamp"], packet.payload["timestamp"] - time.time())
                             pass
                        case "kill":
                            return
                        case "death":
                            match platform.system():
                                case "Windows":
                                    subprocess.run(["shutdown", "/s"])
                                case "Linux" | "Darwin":
                                    subprocess.run(["shutdown", "-h", "now"])
                                case _:
                                    print("Unsupported platform")
                                    exit(1)
                        case _:
                            print(f"Unknown command: {packet.payload['command']}")

    def construct_frame(self, frame: Frame):
        # Sort packets by chunk_id and join them
        frame.packets.sort(key=lambda p: p.chunk_id)
        message = b"".join(p.payload for p in frame.packets)
        message = self.aesgcm.decrypt(frame.nonce, message, b"")

        array = np.frombuffer(message, dtype=np.uint8)
        array = cv2.imdecode(array, cv2.IMREAD_COLOR)
        frame = cv2.cvtColor(array, cv2.COLOR_BGR2RGB)
        return frame

    def display_frame(self, constructed_frame):
        cv2.imshow("Video Broadcast", constructed_frame)
        if cv2.waitKey(1) & 0xFF == 27:
            return True
        return False

    def freeze_keyboard_and_mouse(self, timestamp):

        def return_none(a, b, c):
            return None

        self.frozen_until = timestamp

        mouse_supressor = pynput.mouse.Listener(suppress=True, darwin_suppress=return_none)
        mouse_supressor.start()
        keyboard_supressor = pynput.keyboard.Listener(suppress=True)
        keyboard_supressor.start()

        while self.frozen_until > time.time():
            time.sleep(self.frozen_until - time.time())

        mouse_supressor.stop()
        keyboard_supressor.stop()

class Packet:
    def __init__(self, message: bytes, aesgcm: AESGCM = None):
        extracted_header_and_payload = extract_header_and_payload(message)

        self.frame_id: int = extracted_header_and_payload[0][0]
        self.chunk_id: int = extracted_header_and_payload[0][1]
        self.total_chunks_count: int = extracted_header_and_payload[0][2]
        self.nonce: bytes = extracted_header_and_payload[0][3]
        self.payload: bytes = extracted_header_and_payload[1]

        self.is_video_frame: bool = (self.frame_id != 0)

        if not self.is_video_frame:
            self.payload = json.loads(aesgcm.decrypt(self.nonce, self.payload, b"").decode())


class Frame:
    def __init__(self, packet: Packet):
        self.frame_id = packet.frame_id
        self.total_packets_count = packet.total_chunks_count
        self.packets_count = 1
        self.packets = [packet]
        self.nonce = packet.nonce

    def __add__(self, other):
        if isinstance(other, Packet):
            if self.frame_id != other.frame_id:
                raise ValueError("Packet frame_id mismatch")
            self.packets.append(other)
            self.packets_count += 1
        elif isinstance(other, Frame):
            if self.frame_id != other.frame_id:
                raise ValueError("Frames must have the same frame_id")
            self.packets.extend(other.packets)
            self.packets_count += other.packets_count
        return self



if __name__ == "__main__":
    client = Client()
    client.get_messages()