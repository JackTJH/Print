"""TCP server thread and per-client handler thread."""

import hashlib
import json
import os
import queue
import socket
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import QThread, Qt, pyqtSignal

from common.constants import (
    Cmd, CHUNK_SIZE, RECV_TIMEOUT, MAX_FILE_SIZE,
    MAX_CONNECTIONS, RECEIVED_DIR, ALLOWED_EXTENSIONS,
)
from common.protocol import encode_frame, recv_frame


def now() -> str:
    return datetime.now().strftime("%H:%M:%S")


class ClientHandlerThread(QThread):
    """Handles one client connection: receives file and triggers print."""

    srv_log = pyqtSignal(str, str, str)          # time, ip, message

    def __init__(self, client_socket: socket.socket, addr: tuple,
                 print_queue: queue.Queue, parent=None):
        super().__init__(parent)
        self.sock = client_socket
        self.addr = addr
        self.buffer = bytearray()
        self._print_queue = print_queue

    def run(self):
        ip = self.addr[0]
        filepath_saved = None
        try:
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.sock.settimeout(RECV_TIMEOUT)

            # 1. Receive FILE_INFO
            self.srv_log.emit(now(), ip, "等待上传信息...")
            cmd, payload = recv_frame(self.sock, self.buffer)
            self.srv_log.emit(now(), ip, f"收到命令: {cmd:#x}")

            if cmd != Cmd.FILE_INFO:
                self._send_error("协议错误")
                return

            info = json.loads(payload.decode("utf-8"))
            filename = info["filename"]
            filesize = info["filesize"]
            filetype = info.get("filetype", "")
            total_chunks = info.get("total_chunks", 1)
            self.srv_log.emit(now(), ip, f"文件: {filename} ({self._fmt(filesize)})")

            # 2. Validate
            ext = Path(filename).suffix.lower()
            if ext not in ALLOWED_EXTENSIONS:
                self._send_error(f"不支持的类型: {ext}")
                self.srv_log.emit(now(), ip, f"拒绝: 类型不支持")
                return
            if filesize > MAX_FILE_SIZE:
                self._send_error("文件过大")
                self.srv_log.emit(now(), ip, "拒绝: 文件过大")
                return

            # 3. Receive file data
            self._send_ready()
            self.srv_log.emit(now(), ip, "已就绪，接收数据...")

            os.makedirs(RECEIVED_DIR, exist_ok=True)
            dest = os.path.join(RECEIVED_DIR, filename)
            md5 = hashlib.md5()
            chunks_received = 0

            with open(dest, "wb") as f:
                while chunks_received < total_chunks:
                    cmd, payload = recv_frame(self.sock, self.buffer)
                    if cmd == Cmd.FILE_COMPLETE:
                        break
                    elif cmd == Cmd.FILE_DATA:
                        f.write(payload)
                        md5.update(payload)
                        chunks_received += 1
                        self._send_ready()
                    elif cmd == Cmd.ERROR:
                        self.srv_log.emit(now(), ip, "客户端错误")
                        return
                    else:
                        self._send_error(f"意外命令: {cmd:#x}")
                        return

            # 4. Verify checksum
            if cmd == Cmd.FILE_COMPLETE:
                complete_info = json.loads(payload.decode("utf-8"))
                expected_md5 = complete_info.get("md5", "")
                if expected_md5 and md5.hexdigest() != expected_md5:
                    self._send_error("校验和不匹配")
                    self.srv_log.emit(now(), ip, "校验失败")
                    os.remove(dest)
                    return

            self._send_ack()
            # 等 200ms 确保 ACK 数据完全发出
            import time
            time.sleep(0.2)
            filepath_saved = dest
            self.srv_log.emit(now(), ip, f"接收完成 ({self._fmt(filesize)})")

        except ConnectionError:
            self.srv_log.emit(now(), ip, "连接断开")
        except Exception as e:
            self.srv_log.emit(now(), ip, f"错误: {e}")
        finally:
            self._cleanup()
            if filepath_saved:
                filetype = Path(filepath_saved).suffix.lower().lstrip(".")
                size = self._fmt(os.path.getsize(filepath_saved))
                name = Path(filepath_saved).name
                self._print_queue.put((name, size, filetype, filepath_saved))

    def disconnect(self):
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
    def _fmt(size: int) -> str:
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.1f} MB"


class TcpServerThread(QThread):
    """Main server thread: accepts connections and spawns handler threads."""

    error = pyqtSignal(str)
    srv_log = pyqtSignal(str, str, str)

    def __init__(self, host: str, port: int,
                 log_model, file_model, print_queue, parent=None):
        super().__init__(parent)
        self.host = host
        self.port = port
        self._log_model = log_model
        self._file_model = file_model
        self._print_queue = print_queue
        self._running = False
        self._server_socket = None
        self._handlers: list[ClientHandlerThread] = []

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
        self.srv_log.emit(now(), "系统", f"服务已启动 {self.host}:{self.port}")

        while self._running:
            try:
                client_sock, addr = self._server_socket.accept()
                if len(self._handlers) >= MAX_CONNECTIONS:
                    client_sock.close()
                    self.srv_log.emit(now(), addr[0], "拒绝: 连接数已满")
                    continue

                handler = ClientHandlerThread(client_sock, addr, self._print_queue, self)
                # Connect signals BEFORE start so no events are lost
                handler.srv_log.connect(self._log_model.add_entry, Qt.QueuedConnection)
                handler.finished.connect(lambda h=handler: self._cleanup_handler(h))
                handler.start()
                self._handlers.append(handler)
                self.srv_log.emit(now(), addr[0], "已连接")
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
        self.srv_log.emit(now(), "系统", "服务已停止")

    def _cleanup_handler(self, handler: ClientHandlerThread):
        if handler in self._handlers:
            self._handlers.remove(handler)
        handler.deleteLater()
