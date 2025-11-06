import os
import numpy as np
import matplotlib.pyplot as plt

# ================================================================
# 🧩 一、参数配置区
# ================================================================
start_flag = bytes.fromhex("20 00 00 00 00 00 70 00")  # 帧起始标志
payload_len = 0x700000  # 每帧长度（字节）—— 必须与C端一致

NUM_RANGE = 64          # Range维度数量（range0 ~ range3）
NUM_ANT = 112          # 虚拟天线数
NUM_DOPPLER = 128      # Doppler维度数量（每个天线有128个点）

input_folder = r'F:\2_python\test1024Gout\pythonProject1\.venv\11061130_write7_85'  # 文件夹路径
output_folder = os.path.join(input_folder, "plots")
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
# 🎨 三、绘图函数 —— Doppler曲线 + 峰值 + 跨天线相位变化
# ================================================================
def plot_frame(frame, frame_id):
    num_figs = NUM_ANT // groups_per_fig

    for range_idx in range(NUM_RANGE):  # 对每个range层生成图
        # ===============================
        # (1) Doppler曲线 + 峰值标注
        # ===============================
        for fig_idx in range(num_figs):
            fig, axes = plt.subplots(n_rows, n_cols,
                                     figsize=(16, 10),
                                     sharex=True, sharey=False)
            fig.suptitle(
                f"Frame {frame_id} | Range {range_idx} | Antennas {fig_idx*groups_per_fig}-{fig_idx*groups_per_fig+groups_per_fig-1}",
                fontsize=14, fontweight="bold"
            )

            axes = axes.flatten()

            for j in range(groups_per_fig):
                ant_idx = fig_idx * groups_per_fig + j
                doppler = frame[range_idx, ant_idx]
                doppler_shifted = np.fft.fftshift(doppler)
                mag = np.abs(doppler_shifted)

                # === 找峰值 ===
                peak_idx = np.argmax(mag)
                peak_val = mag[peak_idx]

                ax = axes[j]
                ax.plot(mag, color="blue")
                ax.plot(peak_idx, peak_val, "ro")
                ax.text(peak_idx, peak_val, f"({peak_idx},{peak_val:.2f})",
                        color="red", fontsize=7, ha="left", va="bottom")
                ax.set_title(f"Antenna {ant_idx}", fontsize=9)
                ax.grid(True)

                if j >= groups_per_fig - n_cols:
                    ax.set_xlabel("Doppler Index")
                if j % n_cols == 0:
                    ax.set_ylabel("Amplitude")

            for k in range(groups_per_fig, len(axes)):
                fig.delaxes(axes[k])

            plt.tight_layout(rect=[0, 0, 1, 0.95])
            save_path = os.path.join(
                output_folder,
                f"Frame{frame_id}_Range{range_idx}_Ant_{fig_idx*groups_per_fig}_{fig_idx*groups_per_fig+groups_per_fig-1}_amp.png"
            )
            plt.savefig(save_path, dpi=150)
            plt.close()
            print(f"✅ 已保存振幅图: {save_path}")

        # ===============================
        # (2) 跨天线相位变化图
        # ===============================
        phases = []
        for ant_idx in range(NUM_ANT):
            doppler = np.fft.fftshift(frame[range_idx, ant_idx])
            mag = np.abs(doppler)
            peak_idx = np.argmax(mag)
            phase = np.angle(doppler[peak_idx])  # 取峰值处的相位
            phases.append(phase)

        plt.figure(figsize=(10, 5))
        plt.plot(phases, 'o-', color='orange', lw=2)
        plt.title(f"Frame {frame_id} | Range {range_idx} | Phase across antennas")
        plt.xlabel("Antenna index")
        plt.ylabel("Phase (rad)")
        plt.grid(True)
        plt.tight_layout()

        save_phase_path = os.path.join(
            output_folder, f"Frame{frame_id}_Range{range_idx}_PhaseAcrossAnt.png")
        plt.savefig(save_phase_path, dpi=150)
        plt.close()
        print(f"✅ 已保存相位变化图: {save_phase_path}")


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
            plot_frame(frame, fi)


# ================================================================
# 🏁 五、执行入口
# ================================================================
if __name__ == "__main__":
    parse_folder()
