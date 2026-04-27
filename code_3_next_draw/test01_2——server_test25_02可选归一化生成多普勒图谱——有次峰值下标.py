import math
import os
import numpy as np
import matplotlib.pyplot as plt
import struct

from tkinter import Tk
from tkinter.filedialog import askdirectory

# === 全局参数 ===
start_flag = bytes.fromhex("19 00 00 00 ")
# start_flag = bytes.fromhex("19 00 00 00 00 60 00 00")
# payload_len = 0x6000

NUM_CHIRPS = 256
NUM_GROUPS_OF_ONE_FIG = 20
NUM_COLS = 5  # 一行5张图片
NUM_ROWS = NUM_GROUPS_OF_ONE_FIG // NUM_COLS

SECOND_PEAK_RATIO = 0.2  # 次峰阈值比例（主峰值的20%）
NORMAL_PER_GROUP = 0  # 是否对每个组的多普勒信号进行归一化，1为是，0为否
LOG_OR_ABS = 0 #如果是1则是看强度数据，如果是0则看最高峰的绝对值

if NORMAL_PER_GROUP == 1:
    normal_str = "normal"
else:
    normal_str = "no_normal"

if LOG_OR_ABS == 1:
    mode_str = "log"
else:
    mode_str = "abs"

put_folder = "pictures_" + normal_str + "_" + mode_str



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


def parse_and_plot_bin(bin_path, global_out_dir):

    base = os.path.basename(bin_path)
    name_no_ext = os.path.splitext(base)[0]
    out_dir = os.path.join(global_out_dir, f"{name_no_ext}")
    os.makedirs(out_dir, exist_ok=True)

    with open(bin_path, "rb") as f:
        data = f.read()

    start_idx = data.find(start_flag)
    if start_idx < 0:
        print(f"{bin_path}: 没有找到帧头，跳过。")
        return

    payload_len = struct.unpack('<I', data[start_idx + 4:start_idx + 8])[0]

    payload_start = start_idx + len(start_flag)+4
    payload_end = payload_start + payload_len
    if payload_end > len(data):
        print(f"{bin_path}: 数据不足 51200 字节，跳过。")
        return

    num_floats_of_one_frame = payload_len // 4

    payload = data[payload_start:payload_end]
    arr = np.frombuffer(payload, dtype="<f4")
    if arr.size != num_floats_of_one_frame:
        print(f"{bin_path}: 解析数量异常 {arr.size}，跳过。")
        return

    # === 分组与频移 ===
    num_dopplerbins_of_one_group = NUM_CHIRPS
    groups = arr.reshape(-1, num_dopplerbins_of_one_group)
    shifted = np.fft.fftshift(groups, axes=1)

    num_groups_of_one_frame = groups.shape[0]
    num_groups_of_one_fig = NUM_GROUPS_OF_ONE_FIG
    num_figs_of_one_frame = math.ceil(num_groups_of_one_frame / num_groups_of_one_fig)

    for fig_id in range(num_figs_of_one_frame):
        start_g = fig_id * num_groups_of_one_fig
        end_g = min(start_g + num_groups_of_one_fig, num_groups_of_one_frame)

        fig, axes = plt.subplots(NUM_ROWS, NUM_COLS, figsize=(16, 12))
        axes = axes.ravel()

        for k, g_idx in enumerate(range(start_g, end_g)):
            ax = axes[k]
            y = shifted[g_idx]
            if LOG_OR_ABS:
                y = 20 * np.log10(np.abs(y))

            # if NORMAL_PER_GROUP:
            #     y = (y - np.min(y)) / (np.max(y) - np.min(y) + 1e-8)

            ax.plot(y, label="Signal")

            # === 主峰 ===
            main_peak_idx = np.argmax(y)
            main_peak_val = y[main_peak_idx]
            ax.plot(main_peak_idx, main_peak_val, "ro", markersize=6, label="Main Peak")
            ax.text(main_peak_idx, main_peak_val,
                    f"({main_peak_idx},{main_peak_val:.2f})",
                    color="red", fontsize=8, ha="left", va="bottom")

            # === 次峰（大于主峰值20%的最大峰）===
            threshold = main_peak_val * SECOND_PEAK_RATIO
            # 排除主峰本身
            candidate_indices = np.where((y < main_peak_val) & (y > threshold))[0]
            if len(candidate_indices) > 0:
                second_peak_idx = candidate_indices[np.argmax(y[candidate_indices])]
                second_peak_val = y[second_peak_idx]
                # 画蓝点标记次峰
                ax.plot(second_peak_idx, second_peak_val, "bo", markersize=5, label="2nd Peak")
                ax.text(second_peak_idx, second_peak_val,
                        f"({second_peak_idx},{second_peak_val:.2f})",
                        color="blue", fontsize=8, ha="left", va="bottom")

            ax.set_title(f"Group {g_idx:03d}", fontsize=9)
            ax.set_xlabel("Index")
            ax.set_ylabel("Value")

        for k in range(end_g - start_g, len(axes)):
            axes[k].axis("off")

        fig.tight_layout()
        out_path = os.path.join(out_dir, f"{name_no_ext}_part{fig_id + 1}.png")
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
        print(f"已保存：{out_path}")

    print(f"{bin_path}: 完成。")


def parse_folder(folder_path):
    global_out_dir = os.path.join(folder_path, put_folder)
    os.makedirs(global_out_dir, exist_ok=True)

    for fname in os.listdir(folder_path):
        if fname.lower().endswith(".bin"):
            fpath = os.path.join(folder_path, fname)
            if os.path.isfile(fpath):
                parse_and_plot_bin(fpath, global_out_dir)


if __name__ == "__main__":
    input_folder = choose_folder()

    parse_folder(input_folder)
