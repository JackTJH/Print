# Shared constants for TCP Print Server
import os

DEFAULT_PORT = 9090
CHUNK_SIZE = 65536  # 64 KB
MAGIC = b"PRNT"
HEADER_SIZE = 9  # 4 magic + 1 cmd + 4 payload_len
RECV_TIMEOUT = 10  # seconds
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB
MAX_CONNECTIONS = 10
BACKLOG = 5

ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".txt", ".csv",
    ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".gif",
}

# Direct-print types (via ShellExecute "print" verb)
DIRECT_PRINT_TYPES = {".pdf", ".docx", ".xls", ".xlsx", ".doc", ".txt", ".csv"}

# Image types
IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".gif"}

RECEIVED_DIR = os.path.join(
    os.path.expanduser("~"), "Desktop", "PrintReceived"
)


class Cmd:
    FILE_INFO = 0x01
    FILE_DATA = 0x02
    FILE_COMPLETE = 0x03
    ACK = 0x10
    READY = 0x11
    ERROR = 0xFF
