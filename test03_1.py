import os
import numpy as np
import pandas as pd
from datetime import datetime

# === 常量定义 ===
TX_NUM = 7
# folder = r"F:\2_python\test1024Gout\pythonProject1\.venv\data\10241747"
input_folder = r'F:\2_python\test1024Gout\pythonProject1\.venv\11061130_write7_85'  # 文件夹路径

NUM_DOPPLER_BINS = 128  # 多普勒 bin 数量
RIVER_RADAR_HOR_THETA = np.deg2rad(0)  # 雷达水平角度 (弧度)
MAX_VALUE_THRESLOD = 3
MAX_VALUE_THRESLOD_PARAM = 0.2
MAX_LEFT_RIGHT_INTERVAL = 1

ALL_AVER = 1

if ALL_AVER != 1:
    AVER_LEFT = 3
    AVER_RIGHT = 10

doppler_flag = bytes.fromhex("05 00 00 00 24 00 00 00")
systemIfo_len = 0x24
height_flag = bytes.fromhex("15 00 00 00 28 00 00 00")
area_len = 0x28

start_flag = bytes.fromhex("19 00 00 00 00 80 00 00")
payload_len = 0x8000  # 51200 bytes
range_flag = bytes.fromhex("11 00 00 00 00 02 00 00")
range_angle_len = 0x200

# ======================================================
# 多峰值检测函数
# ======================================================
def multi_peak_search(x, threshold_ratio=MAX_VALUE_THRESLOD_PARAM):
    num_points = len(x)
    mask = num_points - 1
    max_idx = np.argmax(x)
    max_val = x[max_idx]
    if max_val < MAX_VALUE_THRESLOD:
        return [(0, max_val)]
    local_vals, local_idx = [], []
    for offset in range(-MAX_LEFT_RIGHT_INTERVAL, MAX_LEFT_RIGHT_INTERVAL + 1):
        idx = (max_idx + offset + num_points) & mask
        local_vals.append(x[idx])
        local_idx.append(idx)
    sorted_peaks = sorted(zip(local_idx, local_vals), key=lambda kv: kv[1], reverse=True)
    peaks = [(i, v) for i, v in sorted_peaks if v >= threshold_ratio * max_val and v > MAX_VALUE_THRESLOD]
    return peaks

# ======================================================
# 处理单个文件
# ======================================================
def process_file(fpath):
    fname = os.path.basename(fpath)
    with open(fpath, "rb") as f:
        data = f.read()

    i = data.find(start_flag)
    if i < 0:
        print(f"{fname}: 没有帧头")
        return None

    arr = np.frombuffer(data[i + len(start_flag): i + len(start_flag) + payload_len], dtype="<f4")
    if arr.size % NUM_DOPPLER_BINS != 0:
        print(f"{fname}: payload 长度异常")
        return None

    groups = arr.reshape(-1, NUM_DOPPLER_BINS)
    groups = np.fft.fftshift(groups, axes=1)

    d_idx = data.find(doppler_flag)
    if d_idx >= 0:
        arr_d = np.frombuffer(data[d_idx + len(doppler_flag): d_idx + len(doppler_flag) + systemIfo_len], dtype="<f4")
        radar_dopplerRes_file = arr_d[1] / TX_NUM if len(arr_d) >= 4 else 0.368753016
    else:
        radar_dopplerRes_file = 0.368753016

    rows2, weighted_idx, velocities = [], [], []

    for row in groups:
        peaks = multi_peak_search(row)
        row_out = [len(peaks)]
        for idx, val in peaks:
            row_out.extend([idx, val])
        rows2.append(row_out)

        if peaks:
            idxs = np.array([p[0] for p in peaks])
            vals = np.array([p[1] for p in peaks])
            w_idx = np.dot(idxs, vals) / vals.sum() if vals.sum() > 0 else 0.0
        else:
            w_idx = 0.0
        weighted_idx.append(w_idx)
        vel = (w_idx - NUM_DOPPLER_BINS / 2) * radar_dopplerRes_file
        velocities.append(vel)

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
    h_idx = data.find(height_flag)
    radar_height = river_area = None
    if h_idx >= 0:
        arrh = np.frombuffer(data[h_idx + len(height_flag): h_idx + len(height_flag) + area_len], dtype="<f4")
        if len(arrh) >= 5:
            radar_height = arrh[2]
            river_height = arrh[3]
            river_area = arrh[4]
            df5["radarToRiverHeight"] = radar_height
            df5["RiverHeight"] = river_height
            df5["riverArea"] = river_area
    df5["radar_dopplerRes"] = radar_dopplerRes_file

    real_vel = []
    if radar_height is not None and len(df5) > 0:
        for i in range(len(df5)):
            r, ang_rad = df5.loc[i, "range"], df5.loc[i, "angle_rad"]
            radar_vel = velocities[i] if i < len(velocities) else 0.0
            if r > radar_height:
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
    files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f)) and f.endswith(".bin")]
    if not files:
        print("文件夹为空")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # === Step1-6 Excel ===
    with pd.ExcelWriter(os.path.join(folder, f"{timestamp}_{MAX_VALUE_THRESLOD_PARAM}_{MAX_LEFT_RIGHT_INTERVAL}_excel_1.xlsx"), engine="openpyxl") as writer1, \
         pd.ExcelWriter(os.path.join(folder, f"{timestamp}_{MAX_VALUE_THRESLOD_PARAM}_{MAX_LEFT_RIGHT_INTERVAL}_excel_2.xlsx"), engine="openpyxl") as writer2, \
         pd.ExcelWriter(os.path.join(folder, f"{timestamp}_{MAX_VALUE_THRESLOD_PARAM}_{MAX_LEFT_RIGHT_INTERVAL}_excel_5_17.xlsx"), engine="openpyxl") as writer5:

        all_weighted_idx, all_velocities, all_river_velocities = [], [], []
        all_ranges, all_areas, valid_files = [], [], []

        for f in files:
            fpath = os.path.join(folder, f)
            result = process_file(fpath)
            if result is None:
                continue
            groups, rows2, weighted_idx, velocities, df5, real_vel = result
            sheet_name = f[:31]

            pd.DataFrame(groups).to_excel(writer1, sheet_name=sheet_name, index=False, header=False)
            pd.DataFrame(rows2).to_excel(writer2, sheet_name=sheet_name, index=False, header=False)
            df5.to_excel(writer5, sheet_name=sheet_name, index=False)

            # 收集数据
            all_weighted_idx.append(weighted_idx)
            all_velocities.append(velocities)
            all_river_velocities.append(real_vel)
            all_ranges.append(df5["range"].tolist() if "range" in df5 else [])
            all_areas.append(df5["riverArea"].iloc[0] if "riverArea" in df5 else None)
            valid_files.append(f)

    # === Step7: excel_7_all 汇总河流速度 ===
    def to_excel7_style(data_list, folder, timestamp, name):
        max_len = max(len(v) for v in data_list)
        padded = [v + [None]*(max_len - len(v)) for v in data_list]
        df = pd.DataFrame(padded, index=valid_files)
        path = os.path.join(folder, f"{timestamp}_{MAX_VALUE_THRESLOD_PARAM}_{MAX_LEFT_RIGHT_INTERVAL}{name}.xlsx")
        df.to_excel(path)
        print(f"{name} 已生成: {path}")
        return df

    df3 = to_excel7_style(all_weighted_idx, folder, timestamp, "_excel_3_weighted_idx")
    df4 = to_excel7_style(all_velocities, folder, timestamp, "_excel_4_radarVelocity")
    df6 = to_excel7_style(all_river_velocities, folder, timestamp, "_excel_6_riverVelocity")
    df7 = to_excel7_style(all_river_velocities, folder, timestamp, "_excel_7_all")

    # === Step8: 负值置零 + 平均流速 + 流量 ===
    df8 = df7.copy()
    avg_velocities, flows, areas = [], [], []
    for vel_row, rng_row, area in zip(all_river_velocities, all_ranges, all_areas):
        vlist = [v for v in vel_row] if vel_row else []
        rlist = rng_row if rng_row else []
        if len(vlist) != len(rlist):
            avg_v = 0
        else:
            avg_v = np.mean(vlist) if ALL_AVER else np.mean([v for v, r in zip(vlist, rlist) if AVER_LEFT <= r <= AVER_RIGHT])
        avg_velocities.append(avg_v)
        areas.append(area if area is not None else 0)
        flows.append(avg_v * (area if area is not None else 0))

    df8["riverVelocity_avg"] = avg_velocities
    df8["riverArea"] = areas
    df8["riverFlow"] = flows
    path8 = os.path.join(folder, f"{timestamp}_{MAX_VALUE_THRESLOD_PARAM}_{MAX_LEFT_RIGHT_INTERVAL}_excel_8.xlsx")
    df8.to_excel(path8)
    print(f"excel_8 已生成: {path8}")

# ======================================================
# 主入口
# ======================================================
if __name__ == "__main__":
    process_folder(input_folder)
