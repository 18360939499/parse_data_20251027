import os
import struct
import pandas as pd
import chardet
from openpyxl import load_workbook


input_path = r"F:\2_python\test1024Gout\pythonProject1\.venv\code_main\data\radar_raw_data_11201539_write10_45_max2_3.bin"  # 输入的大文件

# 起始标志与长度
start_flag = bytes.fromhex("0E 00 00 00 00 02 00 00")


def detect_encoding(file_path):
    with open(file_path, 'rb') as f:
        raw_data = f.read(10000)
    result = chardet.detect(raw_data)
    encoding = result['encoding']
    confidence = result['confidence']
    print(f"自动检测编码: {encoding} (置信度: {confidence:.2f})")
    return encoding

def parse_binary_file(file_path):
    # 自动生成输出文件名
    base_name = os.path.splitext(os.path.basename(file_path))[0]  # 不带路径和扩展名
    output_excel_path = os.path.join(
        os.path.dirname(file_path),  # 存到同目录
        f"parsed_14_{base_name}.xlsx"
    )



    # 自动获取数据长度
    data_length = struct.unpack('<I', start_flag[4:8])[0]

    with open(file_path, "rb") as f:
        content = f.read()

        # 尝试把原始文件内容看成 ascii hex 文本再转字节
        try:
            hex_string = content.decode('ascii').replace(" ", "").strip()
            content = bytes.fromhex(hex_string)
        except:
            pass  # 如果不是ascii表示的hex，就跳过，保持原始content

    floats_all = []
    start = 0

    while True:
        start_index = content.find(start_flag, start)
        if start_index == -1:
            break

        data_start = start_index + len(start_flag)
        data_end = data_start + data_length
        if data_end > len(content):
            print("剩余内容不足一帧，跳过")
            break

        data_bytes = content[data_start:data_end]

        floats = [struct.unpack('<f', data_bytes[i:i + 4])[0] for i in range(0, len(data_bytes), 4)]
        floats_all.append(floats)

        # 继续搜索下一个
        start = data_end

    # 写入 Excel
    if floats_all:
        df = pd.DataFrame(floats_all)
        df.to_excel(output_excel_path, index=False, header=False)
        print(f"共解析 {len(floats_all)} 帧，已保存到：{output_excel_path}")
    else:
        print("未解析到任何数据帧")

# 使用示例
parse_binary_file(input_path)
