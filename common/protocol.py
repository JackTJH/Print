"""Binary frame protocol shared by server and client."""

import struct
from .constants import MAGIC, HEADER_SIZE, Cmd


def encode_frame(cmd: int, payload: bytes) -> bytes:
    """Encode a command + payload into a wire-format frame."""
    return struct.pack("!4sBI", MAGIC, cmd, len(payload)) + payload


def decode_frame(data: bytearray) -> tuple[int, bytes] | None:
    """
    Try to decode one frame from the buffer.
    Returns (cmd, payload) if a complete frame is available.
    Returns None if more data is needed.
    Raises ValueError on invalid magic or corrupt frame.
    """
    if len(data) < HEADER_SIZE:
        return None

    magic = bytes(data[0:4])
    if magic != MAGIC:
        raise ValueError(f"Invalid magic bytes: {magic!r}")

    cmd = data[4]
    payload_len = struct.unpack("!I", data[5:9])[0]

    if len(data) < HEADER_SIZE + payload_len:
        return None

    payload = bytes(data[HEADER_SIZE:HEADER_SIZE + payload_len])
    del data[:HEADER_SIZE + payload_len]

    return cmd, payload


def recv_frame(sock, buffer: bytearray) -> tuple[int, bytes]:
    """
    Read from socket until a complete frame is received.
    Returns (cmd, payload). Raises on invalid frame or connection closed.
    """
    while True:
        frame = decode_frame(buffer)
        if frame is not None:
            return frame
        chunk = sock.recv(65536)
        if not chunk:
            raise ConnectionError("Connection closed by peer")
        buffer.extend(chunk)
