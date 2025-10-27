import os
import struct
import pandas as pd
from tkinter import Tk, filedialog

def parse_bin_file(file_path):
    with open(file_path, "rb") as f:
        data = f.read()

    # 帧头模式
    pattern = bytes.fromhex("15 00 00 00 28 00 00 00")
    idx = data.find(pattern)
    if idx == -1:
        return None  # 没找到帧头

    # 从帧头后面取出 36 个字节 (9 组 * 4字节)
    segment = data[idx:idx + 36]
    if len(segment) < 36:
        return None

    # 按照小端解析：前两个 uint32 只是帧头，可以跳过或保留
    values = []
    for i in range(0, 36, 4):
        group = segment[i:i + 4]
        if i in (0, 4):  # 帧头两个数
            val = struct.unpack("<I", group)[0]
        elif i in (8, 12):  # 点个数 / 个数 uint32
            val = struct.unpack("<I", group)[0]
        else:  # 其他 float
            val = struct.unpack("<f", group)[0]
        values.append(val)

    result = {
        "文件名": os.path.basename(file_path),
        "点个数": values[2],
        "个数": values[3],
        "定点雷达到水面高度": values[4],
        "水面高度": values[5],
        "截面积": values[6],
        "平均流速": values[7],
        "流量": values[8],
    }
    return result

def main():
    # 选择文件夹
    root = Tk()
    root.withdraw()
    folder = filedialog.askdirectory(title="请选择包含 .bin 文件的文件夹")
    if not folder:
        print("❌ 未选择文件夹")
        return

    results = []
    for file in os.listdir(folder):
        if file.lower().endswith(".bin"):
            file_path = os.path.join(folder, file)
            parsed = parse_bin_file(file_path)
            if parsed:
                results.append(parsed)

    # 保存到 Excel
    if results:
        df = pd.DataFrame(results)
        out_file = os.path.join(folder, "parsed_21_data.xlsx")
        df.to_excel(out_file, index=False)
        print(f"✅ 已保存结果到 {out_file}")
    else:
        print("⚠️ 没有解析出任何数据")

if __name__ == "__main__":
    main()
