"""Client file sender thread."""

import hashlib
import json
import socket
from pathlib import Path

from PyQt5.QtCore import QThread, pyqtSignal

from common.constants import Cmd, CHUNK_SIZE, RECV_TIMEOUT, HEADER_SIZE
from common.protocol import encode_frame, decode_frame


class FileSenderThread(QThread):
    progress = pyqtSignal(int, int)       # bytes_sent, total_bytes
    log = pyqtSignal(str)                 # message
    done = pyqtSignal(bool)               # success

    def __init__(self, host: str, port: int, filepath: str, parent=None):
        super().__init__(parent)
        self.host = host
        self.port = port
        self.filepath = filepath
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        sock = None
        try:
            filepath = Path(self.filepath)
            if not filepath.is_file():
                self.log.emit(f"文件不存在: {self.filepath}")
                self.done.emit(False)
                return

            filesize = filepath.stat().st_size
            filetype = filepath.suffix.lower().lstrip(".")
            total_chunks = max(1, (filesize + CHUNK_SIZE - 1) // CHUNK_SIZE)

            self.log.emit(f"连接到 {self.host}:{self.port}...")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.settimeout(10)
            sock.connect((self.host, self.port))

            # 1. Send FILE_INFO
            info = json.dumps({
                "filename": filepath.name,
                "filesize": filesize,
                "filetype": filetype,
                "total_chunks": total_chunks,
                "chunk_size": CHUNK_SIZE,
            }).encode("utf-8")
            sock.sendall(encode_frame(Cmd.FILE_INFO, info))
            print(f"[CLI] 已发送FILE_INFO，等待READY...", flush=True)
            self._expect(sock, Cmd.READY)
            print(f"[CLI] 收到READY，开始发送数据", flush=True)
            self.log.emit(f"开始发送: {filepath.name} ({self._fmt_size(filesize)})")

            # 2. Send chunks
            md5 = hashlib.md5()
            sent = 0
            with open(filepath, "rb") as f:
                while not self._cancel:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    md5.update(chunk)
                    sock.sendall(encode_frame(Cmd.FILE_DATA, chunk))
                    self._expect(sock, Cmd.READY)
                    sent += len(chunk)
                    self.progress.emit(sent, filesize)

            if self._cancel:
                self.log.emit("发送已取消")
                self.done.emit(False)
                return

            # 3. Send FILE_COMPLETE
            complete = json.dumps({"md5": md5.hexdigest()}).encode("utf-8")
            sock.sendall(encode_frame(Cmd.FILE_COMPLETE, complete))
            self._expect(sock, Cmd.ACK)
            self.log.emit("传输完成，等待打印...")
            self.done.emit(True)

        except ConnectionRefusedError:
            self.log.emit(f"连接被拒绝 ({self.host}:{self.port})，请检查服务端是否已启动")
            self.done.emit(False)
        except socket.timeout:
            self.log.emit(f"连接超时 ({self.host}:{self.port})")
            self.done.emit(False)
        except Exception as e:
            self.log.emit(f"错误: {type(e).__name__}: {e}")
            self.done.emit(False)
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

    def _expect(self, sock: socket.socket, expected_cmd: int):
        """Receive and validate a response frame."""
        buffer = bytearray()
        sock.settimeout(RECV_TIMEOUT)
        while True:
            frame = decode_frame(buffer)
            if frame is not None:
                cmd, payload = frame
                if cmd == Cmd.ERROR:
                    msg = json.loads(payload.decode("utf-8", errors="replace")).get("message", "未知错误")
                    raise RuntimeError(f"服务端错误: {msg}")
                if cmd != expected_cmd:
                    raise RuntimeError(f"协议错误: 期望 {expected_cmd:#x}, 收到 {cmd:#x}")
                return
            chunk = sock.recv(65536)
            if not chunk:
                raise ConnectionError("连接已断开")
            self.log.emit(f"[调试] 收到 {len(chunk)} 字节: {chunk[:20].hex()}")

    @staticmethod
    def _fmt_size(size: int) -> str:
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.1f} MB"
