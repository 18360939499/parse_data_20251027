import math
import os
import numpy as np
import matplotlib.pyplot as plt

from tkinter import Tk
from tkinter.filedialog import askdirectory


# start_flag = bytes.fromhex("19 00 00 00 00 80 00 00")
# payload_len = 0x8000

# start_flag = bytes.fromhex("19 00 00 00 00 60 00 00")
# payload_len = 0x6000
start_flag = bytes.fromhex("19 00 00 00 00 4A 00 00")
payload_len = 0x4A00

NUM_CHIRPS = 128
NUM_GROUPS_OF_ONE_FIG = 20
NUM_COLS = 5 #一行5张图片
NUM_ROWS = NUM_GROUPS_OF_ONE_FIG // NUM_COLS

NORMAL_PER_GROUP=1#是否对每个组的多普勒信号进行归一化，1为是，0为否。

if NORMAL_PER_GROUP:
    put_folder = "pictures_normal_onlyzhufeng"
else:
    put_folder = "pictures_no_normal_onlyzhufeng"


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
    # === 常量 ===
    num_floats_of_one_frame = payload_len // 4

    # === 输出目录 ===
    base = os.path.basename(bin_path)
    name_no_ext = os.path.splitext(base)[0]
    out_dir = os.path.join(global_out_dir, f"{name_no_ext}")
    os.makedirs(out_dir, exist_ok=True)

    # === 读取文件 ===
    with open(bin_path, "rb") as f:
        data = f.read()

    # === 查找帧头 ===
    i = data.find(start_flag)
    if i < 0:
        print(f"{bin_path}: 没有找到帧头，跳过。")
        return

    payload_start = i + len(start_flag)
    payload_end = payload_start + payload_len
    if payload_end > len(data):
        print(f"{bin_path}: 数据不足 51200 字节，跳过。")
        return

    payload = data[payload_start:payload_end]
    arr = np.frombuffer(payload, dtype="<f4")  # 小端 float32
    if arr.size != num_floats_of_one_frame:
        print(f"{bin_path}: 解析数量异常 {arr.size}，跳过。")
        return

    # === 分组 & fftshift ===
    num_dopplerbins_of_one_group = NUM_CHIRPS  # 通过查看内存排列方式，先doppler,后aoa,再range，一组里面128个doppler
    groups = arr.reshape(-1, num_dopplerbins_of_one_group)  # 自动计算组数,一组就是128个doppler，共有aoa*range组doppler
    shifted = np.fft.fftshift(groups, axes=1)
    # axes = 0：在第0个维度（行方向）上移动；维度 0（axis=0）：不同的组（不同 range/aoa）
    # axes = 1：在第1个维度（列方向）上移动；维度 1（axis=1）：每组内的 Doppler bins（0~127）

    # === 绘图 ===
    num_groups_of_one_frame = groups.shape[0] #一帧里面的doppler组数——数据决定的
    num_groups_of_one_fig = NUM_GROUPS_OF_ONE_FIG  # 一张图里面有多少组doppler——自己决定的设置一张图里面有多少组doppler
    num_figs_of_one_frame = math.ceil(num_groups_of_one_frame / num_groups_of_one_fig) #共有多少张图

    for fig_id in range(num_figs_of_one_frame):
        # === 计算当前图要画的组范围 ===
        start_g = fig_id * num_groups_of_one_fig#一张图的开始组索引
        #确保最后一张图不超出总组数。#一张图的结束组索引
        end_g = min(start_g + num_groups_of_one_fig, num_groups_of_one_frame)

        # ===创建一个 NUM_ROWS × NUM_COLS 的子图网格；每个子图 (axes) 对应一个组；
        # figsize=(16, 12) 设置整张图的大小；axes.ravel() 把二维子图数组拉平成一维，方便用索引访问。
        fig, axes = plt.subplots(NUM_ROWS, NUM_COLS, figsize=(16, 12))
        axes = axes.ravel()

        # ===内层循环：绘制每个组的曲线 ===
        for k, g_idx in enumerate(range(start_g, end_g)):#遍历当前图要画的开始和结束组索引
            ax = axes[k]#选中第 k 个子图
            y = shifted[g_idx]#取该组的多普勒信号；
            # y = 20 * np.log10(np.abs(y) + 1e-8)

            # if NORMAL_PER_GROUP:
            #     #归一化：将信号值映射到 0~1 之间，使得不同组的信号能有比较大的差异。
            #     y = (y - np.min(y)) / (np.max(y) - np.min(y) + 1e-8)

            ax.plot(y, label="Signal")  # 绘制曲线

            # === 找出主峰（最高点）===
            main_peak_idx = np.argmax(y)
            main_peak_val = y[main_peak_idx]

            # 标出主峰点
            ax.plot(main_peak_idx, main_peak_val, "ro", markersize=6, label="Main Peak")

            # 在图上标注主峰坐标（Index, Value）
            ax.text(main_peak_idx, main_peak_val,
                    f"({main_peak_idx},{main_peak_val:.2f})",
                    color="red", fontsize=8, ha="left", va="bottom")

            ax.set_title(f"Group {g_idx:03d}", fontsize=9)
            ax.set_xlabel("Index")
            ax.set_ylabel("Value")

        # 当前图可能没用满所有子图格子；
        # 这一段代码把空白的子图坐标轴隐藏掉，让图片更整洁
        for k in range(end_g - start_g, len(axes)):
            axes[k].axis("off")

        # === 布局与保存图片    ===
        fig.tight_layout()
        out_path = os.path.join(out_dir, f"{name_no_ext}_part{fig_id + 1}.png")
        fig.savefig(out_path, dpi=150)#fig.savefig()：保存图像；dpi=150：设置分辨率为 150 像素/英寸；
        plt.close(fig)#关闭当前图，释放内存。
        print(f"已保存：{out_path}")

    print(f"{bin_path}: 完成。")


def parse_folder(folder_path):
    global_out_dir = os.path.join(folder_path,put_folder)
    os.makedirs(global_out_dir, exist_ok=True)

    for fname in os.listdir(folder_path):
        if fname.lower().endswith(".bin"):
            fpath = os.path.join(folder_path, fname)
            if os.path.isfile(fpath):
                parse_and_plot_bin(fpath, global_out_dir)


if __name__ == "__main__":
    input_folder = choose_folder()

    parse_folder(input_folder)
