import socket
import struct
import time
from datetime import datetime
import os

FRAME_HEADER = b'\x02\x01\x04\x03\x06\x05\x08\x07'
HEADER_LEN = 24

FRAME_ID_OFFSET = 8
FRAME_LEN_OFFSET = 20
HEATBEAT_SIZE=0x1C

def try_parse_one_frame(buffer: bytes):
    """
    尝试从 buffer 中解析一帧
    成功返回：(frame_id, frame_len, frame_bytes, remain_buffer)
    失败返回：None, buffer
    """
    if len(buffer) < HEADER_LEN:
        return None, buffer

    start = buffer.find(FRAME_HEADER)
    if start == -1:
        # 找不到帧头，全部丢弃
        return None, b''

    if len(buffer) < start + HEADER_LEN:
        return None, buffer[start:]

    frame_id = struct.unpack_from('<I', buffer, start + FRAME_ID_OFFSET)[0]
    frame_len = struct.unpack_from('<I', buffer, start + FRAME_LEN_OFFSET)[0]

    #防止雷达异常或数据错位导致 frame_len 变成几百 MB
    if frame_len <= 0 or frame_len > MAX_FRAME_LEN:
        # 丢弃这个帧头，继续找下一个
        return None, buffer[start + 1:]

    if len(buffer) < start + frame_len:
        # frame 还没收完整
        return None, buffer[start:]

    frame = buffer[start:start + frame_len]
    remain = buffer[start + frame_len:]
    return (frame_id, frame_len, frame), remain


class FrameMonitor:
    def __init__(self, report_interval, log_dir="logs"):
        self.last_frame_id = None
        self.total_frames = 0
        self.lost_frames = 0
        self.incomplete_frames = 0

        self.heartbeat_cnt = 0
        self.data_frame_cnt = 0

        self.start_time = time.time()
        self.last_report_time = self.start_time
        self.report_interval = report_interval

        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)

        # ✅ 启动时间（精确到秒）
        self.start_dt = datetime.now()
        self.log_date = self.start_dt.strftime("%Y%m%d")

        # ✅ 第一个日志文件：带时分秒
        self.log_file = self._open_start_log_file()

        self._log("INFO", "monitor start")

    def write_final_summary(self, reason="NORMAL_EXIT"):
        end_dt = datetime.now()
        run_time = end_dt.timestamp() - self.start_time

        drop_exist = "YES" if self.lost_frames > 0 else "NO"

        lines = [
            "",
            "================ RUN SUMMARY ================",
            f"exit_reason  : {reason}",
            f"end_time     : {end_dt.strftime('%Y-%m-%d %H:%M:%S')}",
            f"run_time     : {run_time:.1f} s",
            f"total_frames : {self.total_frames}",
            f"data_frames  : {self.data_frame_cnt}",
            f"heartbeat    : {self.heartbeat_cnt}",
            f"lost_frames  : {self.lost_frames}",
            f"incomplete   : {self.incomplete_frames}",
            f"DROP_EXIST   : {drop_exist}",
            "============================================",
            ""
        ]

        for line in lines:
            self.log_file.write(line + "\n")

        self.log_file.flush()


    def _open_start_log_file(self):
        log_path = os.path.join(
            self.log_dir,
            f"frame_monitor_{self.start_dt.strftime('%Y%m%d_%H%M%S')}.log"
        )
        return open(log_path, "a", buffering=1)

    def _open_daily_log_file(self):
        log_path = os.path.join(
            self.log_dir,
            f"frame_monitor_{self.log_date}.log"
        )
        return open(log_path, "a", buffering=1)


    def _open_log_file(self):
        log_path = os.path.join(
            self.log_dir,
            f"frame_monitor_{self.log_date}.log"
        )
        return open(log_path, "a", buffering=1)

    def _rotate_log_if_needed(self):
        today = datetime.now().strftime("%Y%m%d")
        if today != self.log_date:
            self.log_file.close()
            self.log_date = today
            self.log_file = self._open_daily_log_file()
            self._log("INFO", "log rotated (new day)")

    def _now_str(self):
        return datetime.now().strftime("%H:%M:%S")

    def _log(self, tag, msg):
        self._rotate_log_if_needed()  # 👈 关键

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_file.write(f"{ts} | {tag} | {msg}\n")

    def check(self, frame_id, actual_len, declared_len):
        self.total_frames += 1

        # ✅ 心跳 / 数据帧判断
        if declared_len == HEATBEAT_SIZE:
            self.heartbeat_cnt += 1
        else:
            self.data_frame_cnt += 1

        # 1️⃣ 丢帧告警
        if self.last_frame_id is not None:
            expected = (self.last_frame_id + 1) & 0xFFFFFFFF
            if frame_id != expected:
                lost = (frame_id - expected) & 0xFFFFFFFF
                self.lost_frames += lost
                msg = (
                    f"last={hex(self.last_frame_id)} "
                    f"curr={hex(frame_id)} "
                    f"lost={lost}"
                )
                print(f"\n[{self._now_str()}] ❌ 丢帧告警 | {msg}")
                self._log("DROP", msg)

        self.last_frame_id = frame_id

        # 2️⃣ 完整性判断
        if actual_len != declared_len:
            self.incomplete_frames += 1
            msg = (
                f"frame={hex(frame_id)} "
                f"decl={declared_len} "
                f"recv={actual_len}"
            )
            print(f"\n[{self._now_str()}] ❌ 不完整帧 | {msg}")


        # 3️⃣ 定时状态汇总（实时可见）
        now = time.time()
        if now - self.last_report_time >= self.report_interval:
            self.print_status(now)

    def print_status(self, now=None):
        if now is None:
            now = time.time()

        elapsed = now - self.start_time
        msg = (
            f"run={elapsed:.1f}s "
            f"total={self.total_frames} "
            f"data={self.data_frame_cnt} "
            f"hb={self.heartbeat_cnt} "
            f"lost={self.lost_frames} "
            f"incomplete={self.incomplete_frames}"
        )

        print(f"[{datetime.now().strftime('%H:%M:%S')}] [状态] {msg}")
        self._log("STAT", msg)

        self.last_report_time = now

radar_ip_address = "192.168.1.100"
tcp_port_num = 5005
MAX_PACKET_SIZE_BYTES = 160000
MAX_FRAME_LEN = 20 * 1024 * 1024  # 20MB，根据你 11MB 实际情况定

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(10)
sock.connect((radar_ip_address, tcp_port_num))
sock.settimeout(0.2)

print("✔ 已连接雷达")

buffer = b''
# 每 report_interval 秒输出一次状态
monitor = FrameMonitor(report_interval=10)

try:
    while True:
        try:
            data = sock.recv(MAX_PACKET_SIZE_BYTES)
            if not data:
                print("连接断开")
                monitor.write_final_summary(reason="SOCKET_CLOSED")
                break

            buffer += data

            while True:
                result, buffer = try_parse_one_frame(buffer)
                if result is None:
                    break

                frame_id, frame_len, frame = result
                monitor.check(frame_id, len(frame), frame_len)

        except socket.timeout:
            continue

except KeyboardInterrupt:
    print("用户中断")
    monitor.write_final_summary(reason="KEYBOARD_INTERRUPT")

except Exception as e:
    print("程序异常:", e)
    monitor._log("ERROR", f"exception: {repr(e)}")
    monitor.write_final_summary(reason="EXCEPTION")
    raise


finally:
    sock.close()
    monitor.log_file.close()
