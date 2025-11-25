import os

from tkinter import Tk
from tkinter.filedialog import askopenfilename

def choose_bin_file():
    """弹窗选择 .bin 文件"""
    Tk().withdraw()
    file_path = askopenfilename(
        title="请选择雷达原始 bin 文件",
        filetypes=[("BIN 文件", "*.bin"), ("所有文件", "*.*")]
    )
    return file_path

def split_bin_file(input_path, output_dir, frame_header_hex="0201040306050807"):
    # 转成字节串
    frame_header = bytes.fromhex(frame_header_hex)

    with open(input_path, "rb") as f:
        data = f.read()
        # hex_string = data.decode('ascii').replace(" ", "").strip()
        # data = bytes.fromhex(hex_string)

    # 查找所有帧头的位置
    positions = []
    pos = data.find(frame_header)
    while pos != -1:
        positions.append(pos)
        pos = data.find(frame_header, pos + 1)

    if not positions:
        print("❌ 没找到帧头")
        return

    print(f"找到 {len(positions)} 个帧头")

    # 依次切分帧数据
    os.makedirs(output_dir, exist_ok=True)
    for i in range(len(positions)):
        start = positions[i]
        end = positions[i + 1] if i + 1 < len(positions) else len(data)
        frame = data[start:end]

        out_path = os.path.join(output_dir, f"frame_{i+1:04d}.bin")
        with open(out_path, "wb") as f:
            f.write(frame)

        print(f"✅ 保存 {out_path}, 大小 {len(frame)} bytes")


if __name__ == "__main__":
    # 1️⃣ 选择输入文件
    input_file = choose_bin_file()
    if not input_file:
        print("❌ 未选择文件，程序退出")
        exit()

    # 2️⃣ 自动生成输出目录：同目录 + 文件名（无后缀）
    base_dir = os.path.dirname(input_file)
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    output_dir = os.path.join(base_dir, base_name)

    print(f"✔ 输入文件：{input_file}")
    print(f"✔ 输出文件夹：{output_dir}")

    split_bin_file(input_file, output_dir)