import serial
import struct
import time
import argparse
import logging
import os

from datetime import datetime


# ============================================================
# 用户配置
# ============================================================

PORT_NUMBER = "COM9"
BAUD_RATE = 115200

# 一个完整测试周期：3分钟
CYCLE_SECONDS = 180

# 等待启动回复超时
START_REPLY_TIMEOUT = 10

# 等待雷达通知可以读取数据
READ_NOTIFY_TIMEOUT = 120

# 等待读取数据回复
READ_REPLY_TIMEOUT = 10


# ============================================================
# 协议定义
# ============================================================

FRAME_HEAD = b"\xAA\xAA"
FRAME_TAIL = b"\x55\x55"

# 命令
CMD_START = 0x1A
CMD_READ = 0x1B

# 类型
TYPE_CALL = 0x01       # 调用
TYPE_REPLY = 0x02      # 回复
TYPE_NOTIFY = 0x03     # 通知
TYPE_ACK = 0x04        # 确认

# 状态
STATUS_OK = 0x00

# 防止错误报文中的dataLength导致程序申请异常数据
MAX_APP_DATA_LEN = 1024 * 1024


# ============================================================
# 日志
# ============================================================

def setup_logger():

    # --------------------------------------------------------
    # 创建日志目录
    # --------------------------------------------------------

    log_dir = "logs"

    os.makedirs(
        log_dir,
        exist_ok=True
    )

    # --------------------------------------------------------
    # 每次程序启动创建一个新的日志文件
    # --------------------------------------------------------

    log_filename = os.path.join(
        log_dir,
        datetime.now().strftime(
            "rtu_serial_%Y%m%d_%H%M%S.log"
        )
    )

    # --------------------------------------------------------
    # 创建Logger
    # --------------------------------------------------------

    logger = logging.getLogger(
        "RTU_SERIAL"
    )

    logger.setLevel(
        logging.INFO
    )

    # 防止程序重复初始化时增加多个handler
    logger.handlers.clear()

    # --------------------------------------------------------
    # 文件Handler
    # --------------------------------------------------------

    file_handler = logging.FileHandler(
        log_filename,
        mode="a",
        encoding="utf-8"
    )

    # --------------------------------------------------------
    # 控制台Handler
    # --------------------------------------------------------

    console_handler = logging.StreamHandler()

    # --------------------------------------------------------
    # 时间精确到毫秒
    # --------------------------------------------------------

    formatter = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler.setFormatter(
        formatter
    )

    console_handler.setFormatter(
        formatter
    )

    logger.addHandler(
        file_handler
    )

    logger.addHandler(
        console_handler
    )

    logger.info(
        "=" * 100
    )

    logger.info(
        "[SYSTEM] RTU串口自动测试程序启动"
    )

    logger.info(
        f"[SYSTEM] 日志文件: "
        f"{os.path.abspath(log_filename)}"
    )

    logger.info(
        "=" * 100
    )

    return logger


logger = setup_logger()


# ============================================================
# CRC16-MODBUS
#
# CRC计算范围：
#
# frameSeq
# cmd
# type
# status
# dataLength
# appData
#
# 不包括：
# AA AA
# CRC本身
# 55 55
#
# CRC16-MODBUS：
# polynomial = 0xA001
# initial    = 0xFFFF
#
# CRC低字节先发送
# ============================================================

def crc16_modbus(data: bytes) -> int:

    crc = 0xFFFF

    for byte in data:

        crc ^= byte

        for _ in range(8):

            if crc & 0x0001:

                crc = (
                    (crc >> 1)
                    ^ 0xA001
                )

            else:

                crc >>= 1

    return crc & 0xFFFF


# ============================================================
# 构造协议帧
# ============================================================

def build_frame(
        frame_seq: int,
        cmd: int,
        frame_type: int,
        status: int = STATUS_OK,
        app_data: bytes = b""
):

    data_length = len(
        app_data
    )

    # --------------------------------------------------------
    # 协议Body
    #
    # < 表示小端
    #
    # I : uint32 frameSeq
    # B : uint8  cmd
    # B : uint8  type
    # B : uint8  status
    # I : uint32 dataLength
    # --------------------------------------------------------

    body = struct.pack(
        "<IBBBI",
        frame_seq,
        cmd,
        frame_type,
        status,
        data_length
    )

    body += app_data

    # --------------------------------------------------------
    # CRC
    # --------------------------------------------------------

    crc = crc16_modbus(
        body
    )

    # --------------------------------------------------------
    # 完整帧
    # --------------------------------------------------------

    frame = (
        FRAME_HEAD
        + body
        + struct.pack(
            "<H",
            crc
        )
        + FRAME_TAIL
    )

    return frame


# ============================================================
# 将bytes转成十六进制字符串
# ============================================================

def bytes_to_hex(
        data: bytes
) -> str:

    return " ".join(
        f"{b:02X}"
        for b in data
    )


# ============================================================
# 打印TX/RX，同时写入日志
# ============================================================

def log_hex(
        direction: str,
        data: bytes
):

    logger.info(
        f"[{direction}] "
        f"{bytes_to_hex(data)}"
    )


# ============================================================
# 解析完整协议帧
# ============================================================

def parse_frame(
        frame: bytes
):

    # --------------------------------------------------------
    # 最小长度：
    #
    # AA AA          2
    # frameSeq       4
    # cmd            1
    # type           1
    # status         1
    # dataLength     4
    # CRC            2
    # 55 55          2
    #
    # 总计17字节
    # --------------------------------------------------------

    if len(frame) < 17:

        raise ValueError(
            f"帧长度过短: {len(frame)}"
        )

    # --------------------------------------------------------
    # 帧头
    # --------------------------------------------------------

    if frame[0:2] != FRAME_HEAD:

        raise ValueError(
            "帧头错误"
        )

    # --------------------------------------------------------
    # 帧尾
    # --------------------------------------------------------

    if frame[-2:] != FRAME_TAIL:

        raise ValueError(
            "帧尾错误"
        )

    # --------------------------------------------------------
    # 固定协议字段
    #
    # frame[2:13]
    # 共11字节
    # --------------------------------------------------------

    (
        frame_seq,
        cmd,
        frame_type,
        status,
        data_length

    ) = struct.unpack(
        "<IBBBI",
        frame[2:13]
    )

    # --------------------------------------------------------
    # 检查dataLength
    # --------------------------------------------------------

    if data_length > MAX_APP_DATA_LEN:

        raise ValueError(
            f"dataLength异常: {data_length}"
        )

    # --------------------------------------------------------
    # 完整帧理论长度
    # --------------------------------------------------------

    expected_length = (
        17
        + data_length
    )

    if len(frame) != expected_length:

        raise ValueError(
            f"帧长度错误，"
            f"实际={len(frame)}，"
            f"理论={expected_length}"
        )

    # --------------------------------------------------------
    # appData
    # --------------------------------------------------------

    app_data = frame[
        13:
        13 + data_length
    ]

    # --------------------------------------------------------
    # 接收到的CRC
    # --------------------------------------------------------

    recv_crc = struct.unpack(
        "<H",
        frame[
            13 + data_length:
            15 + data_length
        ]
    )[0]

    # --------------------------------------------------------
    # 本地重新计算CRC
    # --------------------------------------------------------

    calc_crc = crc16_modbus(
        frame[
            2:
            13 + data_length
        ]
    )

    if recv_crc != calc_crc:

        raise ValueError(
            f"CRC错误，"
            f"接收=0x{recv_crc:04X}，"
            f"计算=0x{calc_crc:04X}"
        )

    return {

        "frameSeq": frame_seq,

        "cmd": cmd,

        "type": frame_type,

        "status": status,

        "dataLength": data_length,

        "appData": app_data,

        "crc": recv_crc
    }


# ============================================================
# TLV解析
#
# TLV格式：
#
# tag     uint32
# length  uint32
# value   length字节
#
# 当前协议示例中：
# length == 4
# value按float32解析
# ============================================================

def parse_tlv(
        app_data: bytes
):

    offset = 0

    tlv_list = []

    while offset < len(
            app_data
    ):

        # ----------------------------------------------------
        # TLV头至少8字节
        # ----------------------------------------------------

        if (
            offset + 8
            > len(app_data)
        ):

            raise ValueError(
                "TLV头长度不足"
            )

        tag, length = struct.unpack(
            "<II",
            app_data[
                offset:
                offset + 8
            ]
        )

        offset += 8

        # ----------------------------------------------------
        # 检查Value长度
        # ----------------------------------------------------

        if (
            offset + length
            > len(app_data)
        ):

            raise ValueError(
                f"TLV数据越界，"
                f"Tag=0x{tag:08X}，"
                f"Length={length}"
            )

        value = app_data[
            offset:
            offset + length
        ]

        offset += length

        item = {

            "tag": tag,

            "length": length,

            "raw": value
        }

        # ----------------------------------------------------
        # 当前协议4字节按float32解释
        # ----------------------------------------------------

        if length == 4:

            item["float"] = struct.unpack(
                "<f",
                value
            )[0]

        tlv_list.append(
            item
        )

    return tlv_list


# ============================================================
# RTU串口测试类
# ============================================================

class RtuTester:

    def __init__(
            self,
            port,
            baudrate,
            cycle_seconds=180
    ):

        # ----------------------------------------------------
        # 打开串口
        # ----------------------------------------------------

        self.ser = serial.Serial(

            port=port,

            baudrate=baudrate,

            bytesize=serial.EIGHTBITS,

            parity=serial.PARITY_NONE,

            stopbits=serial.STOPBITS_ONE,

            timeout=0.2
        )

        self.cycle_seconds = (
            cycle_seconds
        )

        # ----------------------------------------------------
        # 接收缓存
        # ----------------------------------------------------

        self.rx_buffer = (
            bytearray()
        )

        # ----------------------------------------------------
        # frameSeq
        #
        # 一个完整周期使用一个frameSeq
        #
        # 下一周期+1
        # ----------------------------------------------------

        self.frame_seq = 0

    # ========================================================
    # 获取新的周期frameSeq
    # ========================================================

    def next_seq(
            self
    ):

        seq = (
            self.frame_seq
        )

        self.frame_seq = (
            self.frame_seq + 1
        ) & 0xFFFFFFFF

        return seq

    # ========================================================
    # 清空串口接收缓存
    # ========================================================

    def clear_serial_buffer(
            self
    ):

        self.rx_buffer.clear()

        self.ser.reset_input_buffer()

    # ========================================================
    # 发送完整协议帧
    # ========================================================

    def send_frame(
            self,
            frame: bytes
    ):

        # ----------------------------------------------------
        # 先打印发送时间和数据
        # ----------------------------------------------------

        log_hex(
            "TX",
            frame
        )

        # ----------------------------------------------------
        # 串口发送
        # ----------------------------------------------------

        self.ser.write(
            frame
        )

        self.ser.flush()

    # ========================================================
    # 接收一个完整协议帧
    # ========================================================

    def read_frame(
            self,
            timeout=10
    ):

        deadline = (
            time.monotonic()
            + timeout
        )

        while (
            time.monotonic()
            < deadline
        ):

            # ------------------------------------------------
            # 从串口读取当前已有的数据
            # ------------------------------------------------

            waiting = (
                self.ser.in_waiting
            )

            if waiting > 0:

                data = self.ser.read(
                    waiting
                )

            else:

                data = self.ser.read(
                    1
                )

            # ------------------------------------------------
            # 写入缓存
            # ------------------------------------------------

            if data:

                self.rx_buffer.extend(
                    data
                )

            # ------------------------------------------------
            # 查找AA AA帧头
            # ------------------------------------------------

            head_index = (
                self.rx_buffer.find(
                    FRAME_HEAD
                )
            )

            if head_index < 0:

                # 如果最后一个字节为AA，
                # 保留下来，避免AA AA被拆成两次接收

                if self.rx_buffer.endswith(
                        b"\xAA"
                ):

                    self.rx_buffer[:] = (
                        b"\xAA"
                    )

                else:

                    self.rx_buffer.clear()

                continue

            # ------------------------------------------------
            # 删除帧头前面的垃圾数据
            # ------------------------------------------------

            if head_index > 0:

                garbage = bytes(
                    self.rx_buffer[
                        :head_index
                    ]
                )

                logger.warning(
                    f"[RX GARBAGE] "
                    f"{bytes_to_hex(garbage)}"
                )

                del self.rx_buffer[
                    :head_index
                ]

            # ------------------------------------------------
            # 至少收到13字节，
            # 才能解析dataLength
            # ------------------------------------------------

            if len(
                self.rx_buffer
            ) < 13:

                continue

            # ------------------------------------------------
            # 解析dataLength
            #
            # AA AA           0~1
            # frameSeq        2~5
            # cmd             6
            # type            7
            # status          8
            # dataLength      9~12
            # ------------------------------------------------

            data_length = struct.unpack(
                "<I",
                self.rx_buffer[
                    9:13
                ]
            )[0]

            # ------------------------------------------------
            # 防止异常长度
            # ------------------------------------------------

            if (
                data_length
                > MAX_APP_DATA_LEN
            ):

                logger.error(
                    f"[ERROR] "
                    f"dataLength异常: "
                    f"{data_length}"
                )

                # 删除AA AA重新寻找下一帧
                del self.rx_buffer[
                    0:2
                ]

                continue

            # ------------------------------------------------
            # 完整帧长度
            # ------------------------------------------------

            total_length = (
                17
                + data_length
            )

            # ------------------------------------------------
            # 当前数据还没收完整
            # ------------------------------------------------

            if (
                len(self.rx_buffer)
                < total_length
            ):

                continue

            # ------------------------------------------------
            # 提取完整帧
            # ------------------------------------------------

            frame = bytes(
                self.rx_buffer[
                    :total_length
                ]
            )

            # 从buffer移除
            del self.rx_buffer[
                :total_length
            ]

            return frame

        raise TimeoutError(
            f"等待串口完整帧超时，"
            f"timeout={timeout}s"
        )

    # ========================================================
    # 等待指定CMD + TYPE + frameSeq
    # ========================================================

    def wait_frame(
            self,
            cmd,
            frame_type,
            frame_seq,
            timeout=10
    ):

        deadline = (
            time.monotonic()
            + timeout
        )

        while (
            time.monotonic()
            < deadline
        ):

            remaining = (
                deadline
                - time.monotonic()
            )

            # ------------------------------------------------
            # 接收原始帧
            # ------------------------------------------------

            try:

                raw = self.read_frame(
                    timeout=remaining
                )

            except TimeoutError:

                break

            # ------------------------------------------------
            # 打印完整RX数据
            # ------------------------------------------------

            log_hex(
                "RX",
                raw
            )

            # ------------------------------------------------
            # 协议解析和CRC校验
            # ------------------------------------------------

            try:

                info = parse_frame(
                    raw
                )

            except ValueError as e:

                logger.error(
                    f"[PARSE ERROR] "
                    f"{e}"
                )

                continue

            # ------------------------------------------------
            # 打印解析后的协议内容
            # ------------------------------------------------

            logger.info(

                f"[PARSE] "

                f"Seq={info['frameSeq']} "

                f"Cmd=0x{info['cmd']:02X} "

                f"Type=0x{info['type']:02X} "

                f"Status={info['status']} "

                f"Length={info['dataLength']} "

                f"CRC=0x{info['crc']:04X}"
            )

            # ------------------------------------------------
            # CMD检查
            # ------------------------------------------------

            if (
                info["cmd"]
                != cmd
            ):

                logger.warning(

                    f"[IGNORE] "

                    f"CMD不匹配，"

                    f"期望=0x{cmd:02X}，"

                    f"实际=0x{info['cmd']:02X}"
                )

                continue

            # ------------------------------------------------
            # TYPE检查
            # ------------------------------------------------

            if (
                info["type"]
                != frame_type
            ):

                logger.warning(

                    f"[IGNORE] "

                    f"TYPE不匹配，"

                    f"期望=0x{frame_type:02X}，"

                    f"实际=0x{info['type']:02X}"
                )

                continue

            # ------------------------------------------------
            # frameSeq检查
            #
            # 一个周期所有通信必须是同一个seq
            # ------------------------------------------------

            if (
                info["frameSeq"]
                != frame_seq
            ):

                logger.error(

                    f"[SEQ ERROR] "

                    f"frameSeq不匹配，"

                    f"期望={frame_seq}，"

                    f"实际={info['frameSeq']}"
                )

                continue

            return info

        raise TimeoutError(

            f"等待报文超时："

            f"Seq={frame_seq}, "

            f"CMD=0x{cmd:02X}, "

            f"TYPE=0x{frame_type:02X}, "

            f"timeout={timeout}s"
        )

    # ========================================================
    # 执行一个完整周期
    # ========================================================

    def run_one_cycle(
            self
    ):

        # ----------------------------------------------------
        # 一个周期生成一个frameSeq
        # ----------------------------------------------------

        cycle_seq = (
            self.next_seq()
        )

        cycle_start_time = (
            time.monotonic()
        )

        logger.info("")
        logger.info(
            "=" * 100
        )

        logger.info(
            f"[CYCLE START] "
            f"frameSeq={cycle_seq}"
        )

        logger.info(
            "=" * 100
        )

        # ====================================================
        # 1. RTU -> 雷达
        #    START
        # ====================================================

        logger.info(
            "[STEP 1] RTU发送雷达启动命令"
        )

        start_frame = build_frame(

            frame_seq=cycle_seq,

            cmd=CMD_START,

            frame_type=TYPE_CALL,

            status=STATUS_OK
        )

        # ----------------------------------------------------
        # START发送时刻
        # ----------------------------------------------------

        start_send_time = (
            time.monotonic()
        )

        self.send_frame(
            start_frame
        )

        # ====================================================
        # 2. 雷达 -> RTU
        #    START REPLY
        # ====================================================

        logger.info(
            "[STEP 2] 等待雷达启动回复"
        )

        start_reply = self.wait_frame(

            cmd=CMD_START,

            frame_type=TYPE_REPLY,

            frame_seq=cycle_seq,

            timeout=START_REPLY_TIMEOUT
        )

        # ----------------------------------------------------
        # START响应耗时
        # ----------------------------------------------------

        start_cost_ms = (
            time.monotonic()
            - start_send_time
        ) * 1000.0

        logger.info(
            f"[TIME] "
            f"START响应耗时="
            f"{start_cost_ms:.3f} ms"
        )

        # ----------------------------------------------------
        # Status检查
        # ----------------------------------------------------

        if (
            start_reply["status"]
            != STATUS_OK
        ):

            raise RuntimeError(

                f"雷达START回复失败，"

                f"status="
                f"{start_reply['status']}"
            )

        logger.info(

            f"[PASS] "

            f"START回复正确，"

            f"frameSeq={cycle_seq}"
        )

        # ====================================================
        # 3. 雷达 -> RTU
        #    READ NOTIFY
        # ====================================================

        logger.info(
            "[STEP 3] 等待雷达可以读取数据通知"
        )

        notify_wait_time = (
            time.monotonic()
        )

        notify = self.wait_frame(

            cmd=CMD_READ,

            frame_type=TYPE_NOTIFY,

            frame_seq=cycle_seq,

            timeout=READ_NOTIFY_TIMEOUT
        )

        notify_cost = (
            time.monotonic()
            - notify_wait_time
        )

        logger.info(

            f"[TIME] "

            f"等待READ通知耗时="
            f"{notify_cost:.3f} s"
        )

        if (
            notify["status"]
            != STATUS_OK
        ):

            raise RuntimeError(

                f"READ通知状态错误，"

                f"status="
                f"{notify['status']}"
            )

        logger.info(

            f"[PASS] "

            f"收到READ通知，"

            f"frameSeq={cycle_seq}"
        )

        # ====================================================
        # 4. RTU -> 雷达
        #    READ
        #
        # 注意：
        # 不产生新的frameSeq
        # 继续使用cycle_seq
        # ====================================================

        logger.info(
            "[STEP 4] RTU发送读取数据命令"
        )

        read_request = build_frame(

            frame_seq=cycle_seq,

            cmd=CMD_READ,

            frame_type=TYPE_CALL,

            status=STATUS_OK
        )

        read_send_time = (
            time.monotonic()
        )

        self.send_frame(
            read_request
        )

        # ====================================================
        # 5. 雷达 -> RTU
        #    READ REPLY
        # ====================================================

        logger.info(
            "[STEP 5] 等待雷达数据回复"
        )

        read_reply = self.wait_frame(

            cmd=CMD_READ,

            frame_type=TYPE_REPLY,

            frame_seq=cycle_seq,

            timeout=READ_REPLY_TIMEOUT
        )

        # ----------------------------------------------------
        # READ响应耗时
        # ----------------------------------------------------

        read_cost_ms = (
            time.monotonic()
            - read_send_time
        ) * 1000.0

        logger.info(

            f"[TIME] "

            f"READ响应耗时="
            f"{read_cost_ms:.3f} ms"
        )

        if (
            read_reply["status"]
            != STATUS_OK
        ):

            raise RuntimeError(

                f"READ数据回复失败，"

                f"status="
                f"{read_reply['status']}"
            )

        logger.info(

            f"[PASS] "

            f"READ数据回复正确，"

            f"frameSeq={cycle_seq}, "

            f"dataLength="
            f"{read_reply['dataLength']}"
        )

        # ====================================================
        # 6. 解析TLV
        # ====================================================

        logger.info(
            "[STEP 6] 解析雷达测量数据"
        )

        if (
            read_reply["dataLength"]
            > 0
        ):

            tlvs = parse_tlv(
                read_reply[
                    "appData"
                ]
            )

            logger.info(

                f"[DATA] "

                f"TLV数量="
                f"{len(tlvs)}"
            )

            for index, item in enumerate(
                    tlvs,
                    start=1
            ):

                logger.info(

                    f"[TLV {index}] "

                    f"Tag=0x"
                    f"{item['tag']:08X} "

                    f"Length="
                    f"{item['length']} "

                    f"Raw="
                    f"{bytes_to_hex(item['raw'])}"
                )

                if (
                    "float"
                    in item
                ):

                    logger.info(

                        f"[DATA] "

                        f"Tag=0x"
                        f"{item['tag']:08X} "

                        f"Value="
                        f"{item['float']:.6f}"
                    )

        else:

            logger.warning(
                "[DATA] appData为空"
            )

        # ====================================================
        # 7. RTU -> 雷达
        #    ACK
        #
        # 使用同一个cycle_seq
        # ====================================================

        logger.info(
            "[STEP 7] RTU发送数据接收确认ACK"
        )

        ack_frame = build_frame(

            frame_seq=cycle_seq,

            cmd=CMD_READ,

            frame_type=TYPE_ACK,

            status=STATUS_OK
        )

        self.send_frame(
            ack_frame
        )

        logger.info(

            f"[PASS] "

            f"READ ACK发送完成，"

            f"frameSeq={cycle_seq}"
        )

        # ====================================================
        # 本轮耗时
        # ====================================================

        cycle_cost = (
            time.monotonic()
            - cycle_start_time
        )

        logger.info(
            "-" * 100
        )

        logger.info(

            f"[CYCLE PASS] "

            f"frameSeq={cycle_seq}, "

            f"本轮通信耗时="
            f"{cycle_cost:.3f} s"
        )

        logger.info(
            "=" * 100
        )

        return cycle_seq

    # ========================================================
    # 无限循环执行
    # ========================================================

    def run(
            self
    ):

        logger.info(
            f"[SYSTEM] "
            f"串口已打开: "
            f"{self.ser.port}"
        )

        logger.info(
            f"[SYSTEM] "
            f"波特率: "
            f"{self.ser.baudrate}"
        )

        logger.info(
            f"[SYSTEM] "
            f"测试周期: "
            f"{self.cycle_seconds} 秒"
        )

        logger.info(
            "[SYSTEM] "
            "一个通信周期使用一个frameSeq"
        )

        try:

            while True:

                # ------------------------------------------------
                # 记录整个180秒周期起点
                # ------------------------------------------------

                period_start_time = (
                    time.monotonic()
                )

                try:

                    self.run_one_cycle()

                except TimeoutError as e:

                    logger.error(
                        f"[CYCLE FAIL] "
                        f"通信超时: {e}"
                    )

                except ValueError as e:

                    logger.error(
                        f"[CYCLE FAIL] "
                        f"协议解析错误: {e}"
                    )

                except serial.SerialException as e:

                    logger.error(
                        f"[SERIAL ERROR] "
                        f"{e}"
                    )

                except Exception as e:

                    logger.exception(
                        f"[CYCLE FAIL] "
                        f"未知异常: {e}"
                    )

                # ------------------------------------------------
                # 3分钟是从本周期开始时间计算
                #
                # 例如：
                #
                # 11:00:00开始
                # 11:00:50通信完成
                # 再等待130秒
                # 11:03:00开始下一轮
                # ------------------------------------------------

                elapsed = (
                    time.monotonic()
                    - period_start_time
                )

                sleep_time = (
                    self.cycle_seconds
                    - elapsed
                )

                if sleep_time > 0:

                    logger.info(

                        f"[SYSTEM] "

                        f"本周期已运行="
                        f"{elapsed:.3f}s，"

                        f"等待="
                        f"{sleep_time:.3f}s "

                        f"后开始下一周期"
                    )

                    time.sleep(
                        sleep_time
                    )

                else:

                    logger.warning(

                        f"[SYSTEM] "

                        f"本周期执行时间"
                        f"{elapsed:.3f}s "

                        f"已经超过设定周期"
                        f"{self.cycle_seconds}s，"

                        f"立即开始下一周期"
                    )

        except KeyboardInterrupt:

            logger.info(
                "[SYSTEM] 用户手动停止测试"
            )

        finally:

            if self.ser.is_open:

                self.ser.close()

            logger.info(
                "[SYSTEM] 串口已关闭"
            )

            logger.info(
                "[SYSTEM] RTU串口测试程序结束"
            )


# ============================================================
# main
# ============================================================

def main():

    parser = argparse.ArgumentParser(

        description=(
            "侧扫雷达 RTU "
            "串口协议自动测试工具"
        )
    )

    # --------------------------------------------------------
    # 串口
    #
    # 默认COM9
    # 不设置required=True
    # --------------------------------------------------------

    parser.add_argument(

        "--port",

        default=PORT_NUMBER,

        help=(
            f"串口，例如COM3，"
            f"默认{PORT_NUMBER}"
        )
    )

    # --------------------------------------------------------
    # 波特率
    # --------------------------------------------------------

    parser.add_argument(

        "--baud",

        type=int,

        default=BAUD_RATE,

        help=(
            f"波特率，"
            f"默认{BAUD_RATE}"
        )
    )

    # --------------------------------------------------------
    # 周期
    # --------------------------------------------------------

    parser.add_argument(

        "--cycle",

        type=int,

        default=CYCLE_SECONDS,

        help=(
            f"测试周期，单位秒，"
            f"默认{CYCLE_SECONDS}"
        )
    )

    args = (
        parser.parse_args()
    )

    logger.info(
        f"[CONFIG] "
        f"PORT={args.port}"
    )

    logger.info(
        f"[CONFIG] "
        f"BAUD={args.baud}"
    )

    logger.info(
        f"[CONFIG] "
        f"CYCLE={args.cycle}s"
    )

    # --------------------------------------------------------
    # 创建测试对象
    # --------------------------------------------------------

    try:

        tester = RtuTester(

            port=args.port,

            baudrate=args.baud,

            cycle_seconds=args.cycle
        )

    except serial.SerialException as e:

        logger.error(
            f"[FATAL] "
            f"打开串口失败: {e}"
        )

        return

    # --------------------------------------------------------
    # 开始测试
    # --------------------------------------------------------

    tester.run()


# ============================================================
# 程序入口
# ============================================================

if __name__ == "__main__":

    main()