import socket
import json
import threading
import time
from typing import Optional


class FeedbackReceiver:
    """
    异步接收 search_controller 通过 UDP 回传的决策 label。
    由刺激主循环按 tag 周期 pop 一次最新值，触发反馈边框。
    """
    def __init__(self, ip: str = '0.0.0.0', port: int = 5006, timeout: float = 1.5):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.ip, self.port))
        self.sock.settimeout(0.05)

        self._latest_label: Optional[int] = None
        self._last_recv_time: float = 0.0
        self._lock = threading.Lock()

        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._thread.start()
        print(f"[FeedbackReceiver] Listening on {self.ip}:{self.port}")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        self.sock.close()

    def _recv_loop(self):
        while self._running:
            try:
                data, _ = self.sock.recvfrom(1024)
                msg = json.loads(data.decode('utf-8'))
                label = msg.get('label')
                if isinstance(label, int):
                    with self._lock:
                        self._latest_label = label
                        self._last_recv_time = time.time()
            except socket.timeout:
                continue
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            except OSError:
                if not self._running:
                    break

    def pop_latest_label(self) -> Optional[int]:
        """取走最新 label 并清空。超时则返回 None。"""
        with self._lock:
            if self._latest_label is None:
                return None
            if time.time() - self._last_recv_time > self.timeout:
                self._latest_label = None
                return None
            label = self._latest_label
            self._latest_label = None
            return label
