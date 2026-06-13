import struct
from typing import Tuple

header_format = "!IHH12s"
header_struct = struct.Struct(header_format)
header_struct_size = header_struct.size

def create_packet_header(
        frame_id: int,
        chunk_id: int,
        total_chunks_count: int,
        nonce: bytes) -> bytes:

    return header_struct.pack(
        frame_id,
        chunk_id,
        total_chunks_count,
        nonce
    )

def extract_header_and_payload(packet_data: bytes) -> Tuple[tuple, bytes]:
    header_bytes, payload_bytes = packet_data[:header_struct_size], packet_data[header_struct_size:]
    parsed_header_tuple = header_struct.unpack(header_bytes)

    return parsed_header_tuple, payload_bytes
