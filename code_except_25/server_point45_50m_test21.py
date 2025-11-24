import os
import struct
import pandas as pd
import chardet

start_flag = bytes.fromhex("15 00 00 00 28 00 00 00")

input_folder = r'F:\2_python\test1024Gout\pythonProject1\.venv\11181631'  # 文件夹路径

def detect_encoding(file_path):
    with open(file_path, 'rb') as f:
        raw_data = f.read(10000)
    result = chardet.detect(raw_data)
    encoding = result['encoding']
    confidence = result['confidence']
    print(f"自动检测编码: {encoding} (置信度: {confidence:.2f})")
    return encoding


def parse_binary_file(file_path, start_flag):
    # 自动获取数据长度
    data_length = struct.unpack('<I', start_flag[4:8])[0]

    with open(file_path, "rb") as f:
        content = f.read()

        # 尝试把原始文件内容看成 ascii hex 文本再转字节
        # try:
        #     hex_string = content.decode('ascii').replace(" ", "").strip()
        #     content = bytes.fromhex(hex_string)
        # except:
        #     pass  # 如果不是ascii表示的hex，就保持原始content

    floats_all = []
    start = 0

    while True:
        start_index = content.find(start_flag, start)
        if start_index == -1:
            break

        data_start = start_index + len(start_flag)
        data_end = data_start + data_length
        if data_end > len(content):
            print(f"{os.path.basename(file_path)} 剩余内容不足一帧，跳过")
            break

        data_bytes = content[data_start:data_end]
        if 0:
            floats = [struct.unpack('<f', data_bytes[i:i + 4])[0] for i in range(0, len(data_bytes), 4)]
        else:
            # === 1. 前两个 uint32 ===
            uint_part = [struct.unpack('<I', data_bytes[i:i + 4])[0] for i in range(0, 8, 4)]
            # === 2. 剩下部分是 float32 ===
            float_part = [struct.unpack('<f', data_bytes[i:i + 4])[0] for i in range(8, len(data_bytes), 4)]
            # === 3. 合并两个uint + float部分 ===
            floats = uint_part + float_part

        floats_all.append(floats)

        # 继续搜索下一个
        start = data_end

    return floats_all


def parse_folder(input_folder):
    # 起始标志

    all_data = []
    for file_name in os.listdir(input_folder):
        file_path = os.path.join(input_folder, file_name)
        if not os.path.isfile(file_path):
            continue

        floats_all = parse_binary_file(file_path, start_flag)

        for floats in floats_all:
            # 每行前面加文件名
            all_data.append([file_name] + floats)

    if all_data:
        df = pd.DataFrame(all_data)
        df.to_excel(os.path.join(input_folder, "server_parsed_21_all.xlsx"),
                    index=False, header=False)
        print(f"已解析 {len(all_data)} 行，保存到：{os.path.join(input_folder, 'server_parsed_21_all.xlsx')}")
    else:
        print("未解析到任何数据帧")


# 使用示例
parse_folder(input_folder)
