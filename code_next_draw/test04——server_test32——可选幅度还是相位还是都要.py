import os
import numpy as np
import matplotlib.pyplot as plt

#画出来的是 每个天线的多普勒幅度谱图（Amplitude Spectrum）

# ================================================================
# 🧩 一、参数配置区
# ================================================================

# 在这里选模式
plot_mode = "amp"   # 可选 "amp", "phase", "both"

start_flag = bytes.fromhex("20 00 00 00 00 00 70 00")  # 帧起始标志
payload_len = 0x700000  # 每帧长度（字节）—— 必须与C端一致

NUM_RANGE = 64          # Range维度数量（range0 ~ range3）
NUM_ANT = 112          # 虚拟天线数
NUM_DOPPLER = 128      # Doppler维度数量（每个天线有128个点）

input_folder = r'F:\2_python\test1024Gout\pythonProject1\.venv\11061130_write7_85'  # 文件夹路径
output_folder = os.path.join(input_folder, "plots_with_peaks_test")
os.makedirs(output_folder, exist_ok=True)

# 每张图画20个天线的子图（4行5列）
groups_per_fig = 20
n_rows, n_cols = 4, 5





# ================================================================
# 🧠 二、帧提取函数 —— 从bin文件中提取所有帧
# ================================================================
def extract_frames(path):
    with open(path, "rb") as f:
        data = f.read()

    frames = []
    idx = 0

    while True:
        i = data.find(start_flag, idx)
        if i < 0:
            break

        payload_start = i + len(start_flag)
        payload_end = payload_start + payload_len
        if payload_end > len(data):
            break

        payload = data[payload_start:payload_end]
        arr = np.frombuffer(payload, dtype="<f4")
        complex_arr = arr[0::2] + 1j * arr[1::2]

        try:
            frame = complex_arr.reshape(NUM_RANGE, NUM_ANT, NUM_DOPPLER)
            frames.append(frame)
        except:
            print("⚠ reshape 错误，丢弃该帧")

        idx = payload_end
    return frames

# ================================================================
# 🎨 三、绘图函数 —— 可选幅度 / 相位 / 双显示
# ================================================================
def plot_frame(frame, frame_id, mode="both"):
    """
    mode 可选：
        "amp"   —— 只画幅度谱
        "phase" —— 只画相位谱
        "both"  —— 幅度+相位（默认）
    """
    num_figs = NUM_ANT // groups_per_fig

    for range_idx in range(NUM_RANGE):  # 自动绘制4个range层
        for fig_idx in range(num_figs):
            fig, axes = plt.subplots(n_rows, n_cols,
                                     figsize=(16, 10),
                                     sharex=True,
                                     sharey=False)
            fig.suptitle(
                f"Frame {frame_id} | Range {range_idx} | Antennas {fig_idx*groups_per_fig}-{fig_idx*groups_per_fig+groups_per_fig-1} | Mode={mode}",
                fontsize=14, fontweight="bold"
            )

            axes = axes.flatten()

            for j in range(groups_per_fig):
                ant_idx = fig_idx * groups_per_fig + j
                doppler = frame[range_idx, ant_idx]
                doppler_shifted = np.fft.fftshift(doppler)

                # === 幅度 & 相位 ===
                mag = np.abs(doppler_shifted)
                phase = np.angle(doppler_shifted)

                ax = axes[j]

                # === 绘图模式选择 ===
                if mode in ("amp", "both"):
                    peak_idx = np.argmax(mag)
                    peak_val = mag[peak_idx]
                    ax.plot(mag, color="blue", label="Amplitude")
                    ax.plot(peak_idx, peak_val, "ro")
                    ax.text(peak_idx, peak_val, f"({peak_idx}, {peak_val:.2f})",
                            color="red", fontsize=7, ha="left", va="bottom")

                if mode in ("phase", "both"):
                    if mode == "both":
                        ax2 = ax.twinx()
                        ax2.plot(phase, color="orange", alpha=0.5, label="Phase")
                        ax2.set_ylabel("Phase (rad)", color="orange", fontsize=8)
                    else:
                        ax.plot(phase, color="orange", label="Phase")
                        ax.set_ylabel("Phase (rad)")

                ax.set_title(f"Antenna {ant_idx}", fontsize=9)
                ax.grid(True)

                if j >= groups_per_fig - n_cols:
                    ax.set_xlabel("Doppler Index")
                if mode != "phase" and j % n_cols == 0:
                    ax.set_ylabel("Amplitude")

            # 删除多余子图
            for k in range(groups_per_fig, len(axes)):
                fig.delaxes(axes[k])

            plt.tight_layout(rect=[0, 0, 1, 0.95])
            save_path = os.path.join(
                output_folder,
                f"Frame{frame_id}_Range{range_idx}_Ant_{fig_idx*groups_per_fig}_{fig_idx*groups_per_fig+groups_per_fig-1}_{mode}.png"
            )
            plt.savefig(save_path, dpi=150)
            plt.close()
            print(f"✅ 已保存: {save_path}")


# ================================================================
# 🚀 四、主函数 —— 扫描文件夹并处理所有bin文件
# ================================================================
def parse_folder():
    for fname in os.listdir(input_folder):
        fpath = os.path.join(input_folder, fname)
        if not os.path.isfile(fpath):
            continue

        frames = extract_frames(fpath)
        print(f"{fname}: 找到 {len(frames)} 帧")

        for fi, frame in enumerate(frames, start=1):
            plot_frame(frame, fi,mode=plot_mode)

# ================================================================
# 🏁 五、执行入口
# ================================================================
if __name__ == "__main__":
    parse_folder()
