import os

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
    input_file = r"F:\2_python\test1024Gout\pythonProject1\.venv\code_main\data\radar_raw_data_11251447.bin"   # 输入的大文件
    output_dir = r"F:\2_python\test1024Gout\pythonProject1\.venv\code_main\data\11241600_test"   # 输出的目录
    split_bin_file(input_file, output_dir)