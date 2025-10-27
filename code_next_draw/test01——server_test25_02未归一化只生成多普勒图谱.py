import math
import os
import numpy as np
import matplotlib.pyplot as plt

start_flag = bytes.fromhex("19 00 00 00 00 C8 00 00")
payload_len = 0xC800

NUM_CHIRPS = 128
NUM_GROUPS_OF_ONE_FIG = 20
NUM_COLS = 5 #一行5张图片
NUM_ROWS = NUM_GROUPS_OF_ONE_FIG // NUM_COLS

folder = r"F:\2_python\test1024Gout\pythonProject1\.venv\data\test10241747"

NORMAL_PER_GROUP=1#是否对每个组的多普勒信号进行归一化，1为是，0为否。

if NORMAL_PER_GROUP:
    put_folder = "pictures_normal"
else:
    put_folder = "pictures_no_normal"


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
            if NORMAL_PER_GROUP:
                #归一化：将信号值映射到 0~1 之间，使得不同组的信号能有比较大的差异。
                y = (y - np.min(y)) / (np.max(y) - np.min(y) + 1e-8)
            ax.plot(y)#绘制曲线；
            ax.set_title(f"Group {g_idx:03d}", fontsize=9)#给子图加标题，例如 “Group 012”；
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
        fpath = os.path.join(folder_path, fname)
        if os.path.isfile(fpath):
            parse_and_plot_bin(fpath, global_out_dir)


if __name__ == "__main__":
    parse_folder(folder)
