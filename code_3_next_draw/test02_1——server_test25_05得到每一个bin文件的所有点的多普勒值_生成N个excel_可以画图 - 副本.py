import os
import numpy as np
import pandas as pd
import struct

from tkinter import Tk
from tkinter.filedialog import askdirectory

# start_flag = bytes.fromhex("19 00 00 00 00 C8 00 00")
# payload_len = 0xC800
# start_flag = bytes.fromhex("19 00 00 00 00 60 00 00")
# payload_len = 0x6000

start_flag = bytes.fromhex("19 00 00 00")
# start_flag = bytes.fromhex("19 00 00 00 00 80 00 00")
# payload_len = 0x8000

NUM_CHIRPS = 128

DO_FFT_SHIFT=1

if DO_FFT_SHIFT:
    put_folder = "excel_output_fft"
else:
    put_folder = "excel_output_no_fft"


# ===============================
# 选择文件夹（新增）
# ===============================
def choose_folder():
    Tk().withdraw()  # 隐藏Tk窗口
    folder = askdirectory(title="请选择要解析的文件夹")
    if not folder:
        raise ValueError("未选择文件夹")
    print(f"已选择文件夹：{folder}")
    return folder


def parse_bin_to_excel(bin_path, global_out_dir):
    """
    从二进制文件中解析数据帧，并保存到 Excel
    每帧: 51200 字节 → 12800 float32 → 100 x 128, 做 fftshift
    """
    # === 常量 ===

    # === 输出文件路径 ===
    base = os.path.basename(bin_path)
    name_no_ext = os.path.splitext(base)[0]
    out_path = os.path.join(global_out_dir, f"{name_no_ext}.xlsx")

    with open(bin_path, "rb") as f:
        data = f.read()
#添加如下两句_start
        # hex_string = data.decode('ascii').replace(" ", "").strip()
        # data = bytes.fromhex(hex_string)
# 添加如下两句_end

    # === 查找所有帧头 ===
    frames = []
    idx = 0
    while True:
        i = data.find(start_flag, idx)
        if i < 0:
            break

        payload_len = struct.unpack('<I', data[i + 4:i + 8])[0]

        payload_start = i + len(start_flag)+4
        payload_end = payload_start + payload_len
        if payload_end > len(data):
            print(f"{bin_path}: 末尾数据不足一帧，丢弃。")
            break

        payload = data[payload_start:payload_end]
        arr = np.frombuffer(payload, dtype="<f4")  # 小端 float32

        num_floats_of_one_frame = payload_len // 4  # 12800
        num_dopplerbins_of_one_group = NUM_CHIRPS  # 通过查看内存排列方式，先doppler,后aoa,再range，一组里面128个doppler

        if arr.size == num_floats_of_one_frame:
            groups = arr.reshape(-1, num_dopplerbins_of_one_group)# 自动计算组数,一组就是128个doppler，共有aoa*range组doppler
            if DO_FFT_SHIFT:# 对每组doppler做 fftshift
                groups = np.fft.fftshift(groups, axes=1)
                # axes = 0：在第0个维度（行方向）上移动；维度 0（axis=0）：不同的组（不同 range/aoa）
                # axes = 1：在第1个维度（列方向）上移动；维度 1（axis=1）：每组内的 Doppler bins（0~127）

            frames.append(groups)

        idx = payload_end  # 继续往后找下一帧

    if not frames:
        print(f"{bin_path}: 没有有效帧，跳过。")
        return

    # === 保存到 Excel ===
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        for fi, frame in enumerate(frames, 1):
            df = pd.DataFrame(frame)
            sheet_name = f"Frame_{fi}"
            df.to_excel(writer, sheet_name=sheet_name, index=False, header=False)

    print(f"{bin_path}: 已保存到 {out_path}")


def parse_folder(folder_path):
    """
    遍历文件夹，批量解析所有文件
    """
    global_out_dir = os.path.join(folder_path, put_folder)
    os.makedirs(global_out_dir, exist_ok=True)

    for fname in os.listdir(folder_path):
        if fname.lower().endswith(".bin"):
            fpath = os.path.join(folder_path, fname)
            if os.path.isfile(fpath):
                try:
                    parse_bin_to_excel(fpath, global_out_dir)
                except Exception as e:
                    print(f"{fpath}: 处理失败，原因：{e}")


if __name__ == "__main__":
    input_folder = choose_folder()

    parse_folder(input_folder)
