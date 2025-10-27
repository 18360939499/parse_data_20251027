import os
import numpy as np
import pandas as pd
from datetime import datetime

# === 常量定义 ===
# folder = r"F:\2_python\20251024解析数据\10241358"

folder = r"F:\2_python\test1024Gout\pythonProject1\.venv\10241712"

NUM_DOPPLER_BINS = 128  # 多普勒 bin 数量
RIVER_RADAR_HOR_THETA = np.deg2rad(0)  # 雷达水平角度 (弧度)

MAX_VALUE_THRESLOD = 3
MAX_VALUE_THRESLOD_PARAM = 0.2
MAX_LEFT_RIGHT_INTERVAL = 10

ALL_AVER = 1
if ALL_AVER != 1:
    AVER_LEFT = 3
    AVER_RIGHT = 10

doppler_flag = bytes.fromhex("05 00 00 00 24 00 00 00")
systemIfo_len = 0x24

height_flag = bytes.fromhex("15 00 00 00 28 00 00 00")
area_len = 0x28
if 0:
    start_flag = bytes.fromhex("19 00 00 00 00 46 00 00")
    payload_len = 0x4600  # 51200 bytes

    range_flag = bytes.fromhex("11 00 00 00 18 01 00 00")
    range_angle_len = 0x118
else:
    start_flag = bytes.fromhex("19 00 00 00 00 C8 00 00")
    payload_len = 0xC800  # 51200 bytes

    range_flag = bytes.fromhex("11 00 00 00 20 03 00 00")
    range_angle_len = 0x320


TX_NUM = 1

if 1:

    # ======================================================
    # 多峰值检测函数
    # 输入：一行数据（频谱强度）
    # 输出：符合阈值的峰值 (索引, 强度)
    # ======================================================
    def multi_peak_search(x, threshold_ratio=MAX_VALUE_THRESLOD_PARAM):
        """
        在数据中查找多个显著峰值。
        - threshold_ratio: 阈值比例，用于过滤小峰值
        - 返回值: [(峰值索引, 峰值大小), ...]
        """
        num_points = len(x)
        mask = num_points - 1
        max_idx = np.argmax(x)  # 最大值位置
        max_val = x[max_idx]  # 最大值大小

        # 如果最大值太小，直接返回
        if max_val < MAX_VALUE_THRESLOD:
            return [(0, max_val)]

        # 取最大值附近 ±50 个点
        local_vals, local_idx = [], []
        for offset in range(-MAX_LEFT_RIGHT_INTERVAL, MAX_LEFT_RIGHT_INTERVAL + 1):
            idx = (max_idx + offset + num_points) & mask
            local_vals.append(x[idx])
            local_idx.append(idx)

        # 按值排序，筛选大于阈值的峰
        sorted_peaks = sorted(zip(local_idx, local_vals), key=lambda kv: kv[1], reverse=True)
        peaks = [(i, v) for i, v in sorted_peaks if v >= threshold_ratio * max_val and v > MAX_VALUE_THRESLOD]

        return peaks
else:
    def multi_peak_search(x, threshold_ratio=MAX_VALUE_THRESLOD_PARAM):
        num_points = len(x)
        mask = num_points - 1
        max_idx = np.argmax(x)  # 最大值位置
        max_val = x[max_idx]  # 最大值大小

        # 如果最大值太小，直接返回
        if max_val < MAX_VALUE_THRESLOD:
            return [(64, max_val)]

        threshold = max_val * threshold_ratio
        peaks = []

        # 局部峰值搜索
        for offset in range(-MAX_LEFT_RIGHT_INTERVAL, MAX_LEFT_RIGHT_INTERVAL + 1):
            i = (max_idx + offset + num_points) & mask  # 环绕索引
            iLeft = (i - 1 + num_points) & mask
            iRight = (i + 1) & mask

            # 局部峰值条件
            if x[i] >= x[iLeft] and x[i] >= x[iRight] and x[i] >= threshold and x[i] >= MAX_VALUE_THRESLOD:
                peaks.append((i, x[i]))
            # === 新增逻辑 ===
            # 如果找到了多个峰值，就去掉 index=64 的峰
            if len(peaks) > 1:
                peaks = [(idx, val) for idx, val in peaks if idx != 64]
        return peaks


# ======================================================
# 处理单个文件
# ======================================================
def process_file(fpath):
    """
    输入：单个 bin 文件路径
    输出：6 类数据
      - groups: FFT 后的矩阵
      - rows2: 每行的峰值信息
      - weighted_idx: 加权平均索引
      - velocities: 多普勒速度
      - df5: range / angle / height 信息
      - real_vel: 真实水流速度
    """
    """
    fname = os.path.basename(fpath)
    with open(fpath, "rb") as f:
        data = f.read()

    # ------------------ Step1: 提取 FFT 数据 ------------------

    i = data.find(start_flag)
    if i < 0:
        print(f"{fname}: 没有帧头")
        return None

    arr = np.frombuffer(data[i + len(start_flag): i + len(start_flag) + payload_len], dtype="<f4")

    if arr.size % NUM_DOPPLER_BINS != 0:
        print(f"{fname}: payload 长度异常")
        return None

    groups = arr.reshape(-1,
                         NUM_DOPPLER_BINS)  #把一维数组 arr 重新 reshape 成二维数组，每一行长度是 128。-1 代表 自动计算，由 NumPy 根据数组总长度和其他维度推算出大小。
    groups = np.fft.fftshift(groups, axes=1)  # FFT 中心对齐

    # ------------------ Step2: Doppler 分辨率 ------------------

    d_idx = data.find(doppler_flag)

    if d_idx >= 0:
        arr_d = np.frombuffer(data[d_idx + len(doppler_flag): d_idx + len(doppler_flag) + systemIfo_len], dtype="<f4")
        radar_dopplerRes_file = arr_d[1] / TX_NUM if len(arr_d) >= 4 else 0.368753016
    else:
        radar_dopplerRes_file = 0.368753016

    # ------------------ Step3: 多峰值检测 + 速度 ------------------
    rows2, weighted_idx, velocities = [], [], []

    for row in groups:
        peaks = multi_peak_search(row)
        row_out = [len(peaks)]  # 记录峰值数量
        for idx, val in peaks:
            row_out.extend([idx, val])
        rows2.append(row_out)

        # 加权平均索引
        if peaks:
            idxs = np.array([p[0] for p in peaks])
            vals = np.array([p[1] for p in peaks])
            w_idx = np.dot(idxs, vals) / vals.sum() if vals.sum() > 0 else 0.0  #np.dot(a, b) 是点积运算
        else:
            w_idx = 0.0
        weighted_idx.append(w_idx)

        # 计算多普勒速度
        vel = (w_idx - NUM_DOPPLER_BINS / 2) * radar_dopplerRes_file
        velocities.append(vel)

    # ------------------ Step4: 提取 range/angle ------------------

    r_idx = data.find(range_flag)

    records = []
    if r_idx >= 0:
        arr_rt = np.frombuffer(data[r_idx + len(range_flag): r_idx + len(range_flag) + range_angle_len], dtype="<f4")
        for j in range(0, len(arr_rt), 2):
            if j + 1 >= len(arr_rt):
                break
            r, ang = arr_rt[j], arr_rt[j + 1]
            records.append([r, ang, np.deg2rad(ang)])
    df5 = pd.DataFrame(records, columns=["range", "angle", "angle_rad"])
    print(f"{fname}: arr.size={arr.size}, groups.shape={groups.shape}")

    # ------------------ Step5: 提取高度/面积 ------------------

    h_idx = data.find(height_flag)

    radar_height, river_area = None, None
    if h_idx >= 0:
        arrh = np.frombuffer(data[h_idx + len(height_flag): h_idx + len(height_flag) + area_len], dtype="<f4")
        if len(arrh) >= 5:
            radar_height = arrh[2]  # 雷达到水面的高度
            river_height = arrh[3]  # 河水高度
            river_area = arrh[4]  # 河截面积
            df5["radarToRiverHeight"] = radar_height
            df5["RiverHeight"] = river_height
            df5["riverArea"] = river_area

    df5["radar_dopplerRes"] = radar_dopplerRes_file

    # ------------------ Step6: 计算真实水流速度 ------------------
    real_vel = []
    if radar_height is not None and len(df5) > 0:
        for i in range(len(df5)):
            r, ang_rad = df5.loc[i, "range"], df5.loc[i, "angle_rad"]
            radar_vel = velocities[i] if i < len(velocities) else 0.0
            if r > radar_height:
                if 0:
                    denom = np.sin(RIVER_RADAR_HOR_THETA + ang_rad) * np.sqrt(1 - (radar_height / r) ** 2)
                else:
                    denom = np.cos(RIVER_RADAR_HOR_THETA + ang_rad) * np.sqrt(1 - (radar_height / r) ** 2)
            else:
                denom = 0
            v = radar_vel / denom if denom != 0 else 0.0
            real_vel.append(v)

    return groups, rows2, weighted_idx, velocities, df5, real_vel


# ======================================================
# 处理整个文件夹
# ======================================================
def process_folder(folder):
    """
    遍历文件夹，批量处理 bin 文件
    生成多个 Excel：
      - excel_1: FFT 结果
      - excel_2: 峰值信息
      - excel_3: 加权索引
      - excel_4: 多普勒速度
      - excel_5_17: range/angle/高度/面积
      - excel_6: 水流速度
      - excel_7_all: 汇总所有 riverVelocity
      - excel_8: 负值置零 + 平均流速 + 流量
    """
    files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f)) and f.endswith(".bin")]

    if not files:
        print("文件夹为空")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # === 打开多个 ExcelWriter ===
    with pd.ExcelWriter(os.path.join(folder, f"{timestamp}_excel_1.xlsx"), engine="openpyxl") as writer1, \
            pd.ExcelWriter(os.path.join(folder, f"{timestamp}_excel_2.xlsx"), engine="openpyxl") as writer2, \
            pd.ExcelWriter(os.path.join(folder, f"{timestamp}_excel_3.xlsx"), engine="openpyxl") as writer3, \
            pd.ExcelWriter(os.path.join(folder, f"{timestamp}_excel_4.xlsx"), engine="openpyxl") as writer4, \
            pd.ExcelWriter(os.path.join(folder, f"{timestamp}_excel_5_17.xlsx"), engine="openpyxl") as writer5, \
            pd.ExcelWriter(os.path.join(folder, f"{timestamp}_excel_6.xlsx"), engine="openpyxl") as writer6:

        all_river_velocities, all_ranges, all_areas, valid_files = [], [], [], []

        for f in files:
            fpath = os.path.join(folder, f)
            result = process_file(fpath)
            if result is None:
                continue

            groups, rows2, weighted_idx, velocities, df5, real_vel = result
            sheet_name = f[:31]  # Excel sheet 名最长 31 字符

            # 写入多个 excel 文件
            pd.DataFrame(groups).to_excel(writer1, sheet_name=sheet_name, index=False, header=False)
            pd.DataFrame(rows2).to_excel(writer2, sheet_name=sheet_name, index=False, header=False)
            pd.DataFrame(weighted_idx, columns=["weighted_idx"]).to_excel(writer3, sheet_name=sheet_name, index=False)
            pd.DataFrame(velocities, columns=["radarVelocity"]).to_excel(writer4, sheet_name=sheet_name, index=False)
            df5.to_excel(writer5, sheet_name=sheet_name, index=False)
            pd.DataFrame(real_vel, columns=["riverVelocity"]).to_excel(writer6, sheet_name=sheet_name, index=False)

            # 收集汇总数据
            all_river_velocities.append(real_vel)
            all_ranges.append(df5["range"].tolist() if "range" in df5 else [])
            all_areas.append(df5["riverArea"].iloc[0] if "riverArea" in df5 else None)
            valid_files.append(f)

    # === Step4: 生成 excel_7_all 汇总 ===
    max_len = max(len(v) for v in all_river_velocities)
    padded = [v + [None] * (max_len - len(v)) for v in all_river_velocities]
    df7 = pd.DataFrame(padded, index=valid_files)
    path7 = os.path.join(folder, f"{timestamp}_excel_7_all.xlsx")
    df7.to_excel(path7)

    # === Step5: 负值置零 -> excel_8 ===
    df8 = df7.copy()
    if 0:
        df8 = df8.applymap(lambda x: max(x, 0) if pd.notna(x) else x)  #将负值变为0

    # === Step6: 区间 (5.5m ~ 8m) 平均速度 + 流量 ===
    avg_velocities, flows, areas = [], [], []
    for vel_row, rng_row, area in zip(all_river_velocities, all_ranges, all_areas):
        if 0:
            vlist = [max(v, 0) for v in vel_row] if vel_row else []
        else:
            vlist = [v for v in vel_row] if vel_row else []
            rlist = rng_row if rng_row else []

            if len(vlist) != len(rlist):
                avg_v = 0
            else:
                if ALL_AVER:
                    avg_v = np.mean(vlist)
                else:
                    filt_v = [v for v, r in zip(vlist, rlist) if AVER_LEFT <= r <= AVER_RIGHT]
                    avg_v = np.mean(filt_v) if filt_v else 0

            avg_velocities.append(avg_v)
            areas.append(area if area is not None else 0)
            flows.append(avg_v * (area if area is not None else 0))

    df8["riverVelocity_avg"] = avg_velocities
    df8["riverArea"] = areas
    df8["riverFlow"] = flows

    path8 = os.path.join(folder, f"{timestamp}_excel_8.xlsx")
    df8.to_excel(path8)
    print(f"excel_8 已生成: {path8}")


# ======================================================
# 主入口
# ======================================================
if __name__ == "__main__":
    process_folder(folder)
