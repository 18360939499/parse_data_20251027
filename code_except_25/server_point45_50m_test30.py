import os
import struct
import pandas as pd

start_flag = bytes.fromhex("1E 00 00 00")

input_folder = r'F:\2_python\test1024Gout\pythonProject1\.venv\11061130_write7_85'  # 文件夹路径
produce_file_name = "server_parsed_30_all.xlsx"  # 保存的文件名


def parse_binary_file(file_path):
    """
    解析单个bin文件，返回二维list，每一帧数据为一行
    """
    floats_all = []

    with open(file_path, "rb") as f:
        content = f.read()

    start = 0
    while True:
        start_index = content.find(start_flag, start)
        if start_index == -1:
            break

        data_length = struct.unpack('<I', content[start_index + 4:start_index + 8])[0]
        if data_length < 0xb0:
            start = start_index + 1
            continue

        data_start = start_index + len(start_flag) + 4
        data_end = data_start + data_length
        if data_end > len(content):
            break

        data_bytes = content[data_start:data_end]
        floats = [struct.unpack('<f', data_bytes[i:i + 4])[0]
                  for i in range(0, len(data_bytes), 4)]
        floats_all.append(floats)
        start = data_end

    return floats_all


def parse_folder(folder_path, output_excel_path):
    """
    解析文件夹下所有bin文件，并合并到一个Excel
    每个文件一行，行首是文件名
    """
    all_data = []

    for file in os.listdir(folder_path):
        if file.lower().endswith(".bin"):
            file_path = os.path.join(folder_path, file)
            print(f"正在解析: {file}")
            data = parse_binary_file(file_path)

            # 如果只需要文件对应的一行，可以取第一帧
            if data:
                first_frame = data[0]   # 或者取 data 的平均值
                all_data.append([file] + first_frame)

    # 存Excel
    df = pd.DataFrame(all_data)
    df.to_excel(output_excel_path, index=False, header=False)
    print(f"共解析 {len(all_data)} 个文件，结果已保存到：{output_excel_path}")


# 使用示例
output_excel = os.path.join(input_folder, produce_file_name)
parse_folder(input_folder, output_excel)
