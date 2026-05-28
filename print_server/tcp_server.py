"""TCP server thread and per-client handler thread."""

import hashlib
import json
import os
import socket
import tempfile
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import QThread, pyqtSignal

from common.constants import (
    Cmd, CHUNK_SIZE, RECV_TIMEOUT, MAX_FILE_SIZE,
    MAX_CONNECTIONS, RECEIVED_DIR, ALLOWED_EXTENSIONS,
)
from common.protocol import encode_frame, recv_frame


def now() -> str:
    return datetime.now().strftime("%H:%M:%S")


class TcpServerThread(QThread):
    """Main server thread: accepts connections and spawns handler threads."""

    log = pyqtSignal(str, str, str)       # time, ip, message
    status = pyqtSignal(str)              # status text
    error = pyqtSignal(str)              # error message
    file_received = pyqtSignal(str, str, str, str)  # filename, size, type, path

    def __init__(self, host: str, port: int, parent=None):
        super().__init__(parent)
        self.host = host
        self.port = port
        self._running = False
        self._server_socket = None
        self._handlers: list["ClientHandlerThread"] = []

    def run(self):
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._server_socket.bind((self.host, self.port))
        except OSError as e:
            self.error.emit(f"绑定失败: {e}")
            return

        self._server_socket.listen(5)
        self._server_socket.settimeout(1.0)
        self._running = True
        self.status.emit("listening")
        self.log.emit(now(), "系统", f"服务已启动 {self.host}:{self.port}")

        while self._running:
            try:
                client_sock, addr = self._server_socket.accept()
                if len(self._handlers) >= MAX_CONNECTIONS:
                    client_sock.close()
                    self.log.emit(now(), addr[0], "拒绝连接: 已达最大连接数")
                    continue

                handler = ClientHandlerThread(client_sock, addr, self)
                handler.log.connect(self.log.emit)
                handler.file_received.connect(self.file_received.emit)
                handler.finished.connect(lambda h=handler: self._cleanup_handler(h))
                handler.start()
                self._handlers.append(handler)
                self.log.emit(now(), addr[0], "已连接")
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    self.error.emit(str(e))

    def stop(self):
        self._running = False
        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception:
                pass
        for h in self._handlers[:]:
            h.disconnect()
        self.wait(3000)
        self.log.emit(now(), "系统", "服务已停止")

    def _cleanup_handler(self, handler: "ClientHandlerThread"):
        if handler in self._handlers:
            self._handlers.remove(handler)
        handler.deleteLater()


class ClientHandlerThread(QThread):
    """Handles one client connection: receives file and triggers print."""

    log = pyqtSignal(str, str, str)
    file_received = pyqtSignal(str, str, str, str)

    def __init__(self, client_socket: socket.socket, addr: tuple, parent=None):
        super().__init__(parent)
        self.sock = client_socket
        self.addr = addr
        self.buffer = bytearray()

    def run(self):
        ip = self.addr[0]
        try:
            self.sock.settimeout(RECV_TIMEOUT)

            # Receive FILE_INFO
            cmd, payload = recv_frame(self.sock, self.buffer)
            if cmd != Cmd.FILE_INFO:
                self._send_error("协议错误: 等待文件信息")
                return

            info = json.loads(payload.decode("utf-8"))
            filename = info["filename"]
            filesize = info["filesize"]
            filetype = info.get("filetype", "")
            total_chunks = info.get("total_chunks", 1)

            # Validate
            ext = Path(filename).suffix.lower()
            if ext not in ALLOWED_EXTENSIONS:
                self._send_error(f"不支持的文件类型: {ext}")
                self.log.emit(now(), ip, f"拒绝: {filename} (类型不支持)")
                return

            if filesize > MAX_FILE_SIZE:
                self._send_error("文件过大")
                self.log.emit(now(), ip, f"拒绝: {filename} (文件过大)")
                return

            self.log.emit(now(), ip, f"接收中: {filename} ({self._format_size(filesize)})")

            # Ready to receive data
            self._send_ready()

            # Receive file data
            os.makedirs(RECEIVED_DIR, exist_ok=True)
            dest = os.path.join(RECEIVED_DIR, filename)
            md5 = hashlib.md5()
            received_size = 0
            chunks_received = 0

            with open(dest, "wb") as f:
                while chunks_received < total_chunks:
                    cmd, payload = recv_frame(self.sock, self.buffer)
                    if cmd == Cmd.FILE_COMPLETE:
                        # All chunks received, verify checksum
                        break
                    elif cmd == Cmd.FILE_DATA:
                        f.write(payload)
                        md5.update(payload)
                        received_size += len(payload)
                        chunks_received += 1
                        self._send_ready()
                    elif cmd == Cmd.ERROR:
                        self.log.emit(now(), ip, f"客户端错误: {payload.decode('utf-8', errors='replace')}")
                        return
                    else:
                        self._send_error(f"意外命令: {cmd:#x}")
                        return

            # Verify checksum
            if cmd == Cmd.FILE_COMPLETE:
                complete_info = json.loads(payload.decode("utf-8"))
                expected_md5 = complete_info.get("md5", "")
                actual_md5 = md5.hexdigest()
                if expected_md5 and actual_md5 != expected_md5:
                    self._send_error("校验和不匹配")
                    self.log.emit(now(), ip, f"校验失败: {filename}")
                    os.remove(dest)
                    return

            self._send_ack()
            size_str = self._format_size(filesize)
            self.log.emit(now(), ip, f"接收完成: {filename} ({size_str})")
            self.file_received.emit(filename, size_str, filetype, dest)

        except ConnectionError:
            self.log.emit(now(), ip, "连接断开")
        except json.JSONDecodeError:
            self.log.emit(now(), ip, "协议错误: 无效的JSON")
        except Exception as e:
            self.log.emit(now(), ip, f"错误: {e}")
        finally:
            self._cleanup()

    def disconnect(self):
        """Force disconnect this client."""
        try:
            self.sock.close()
        except Exception:
            pass

    def _send_ready(self):
        self.sock.sendall(encode_frame(Cmd.READY, b""))

    def _send_ack(self):
        self.sock.sendall(encode_frame(Cmd.ACK, b'{"status":"ok"}'))

    def _send_error(self, msg: str):
        payload = json.dumps({"message": msg}).encode("utf-8")
        try:
            self.sock.sendall(encode_frame(Cmd.ERROR, payload))
        except Exception:
            pass

    def _cleanup(self):
        try:
            self.sock.close()
        except Exception:
            pass

    @staticmethod
    def _format_size(size: int) -> str:
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.1f} MB"
