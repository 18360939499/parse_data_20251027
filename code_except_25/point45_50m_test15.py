import os
import struct
import pandas as pd
import chardet
from openpyxl import load_workbook

from tkinter import Tk
from tkinter.filedialog import askopenfilename


# 起始标志与长度
# start_flag = bytes.fromhex("0F 00 00 00 80 01 00 00")
start_flag = bytes.fromhex("0F 00 00 00 E8 01 00 00")


def choose_file():
    Tk().withdraw()  # 不显示主窗口
    filename = askopenfilename(
        title="请选择输入的 .bin 文件",
        filetypes=[("BIN files", "*.bin"), ("All files", "*.*")]
    )
    if not filename:
        raise ValueError("未选择任何文件")
    print(f"已选择文件：{filename}")
    return filename

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
        f"parsed_15_{base_name}.xlsx"
    )


    # 自动获取数据长度
    data_length = struct.unpack('<I', start_flag[4:8])[0]

    with open(file_path, "rb") as f:
        content = f.read()

        # 尝试把原始文件内容看成 ascii hex 文本再转字节
        # try:
        #     hex_string = content.decode('ascii').replace(" ", "").strip()
        #     content = bytes.fromhex(hex_string)
        # except:
        #     pass  # 如果不是ascii表示的hex，就跳过，保持原始content

    # 查找起始标志
    start_index = content.find(start_flag)

    if start_index == -1:
        print("未找到起始标志")
        return None

    data_start = start_index + len(start_flag)
    data_end = data_start + data_length
    data_bytes = content[data_start:data_end]

    if len(data_bytes) != data_length:
        print("数据长度不足")
        return None

    # 每4字节解析为float（小端）
    floats = [struct.unpack('<f', data_bytes[i:i + 4])[0] for i in range(0, len(data_bytes), 4)]

    # 按 2 个一组整理成 DataFrame
    xy_pairs = list(zip(floats[::2], floats[1::2]))
    df = pd.DataFrame(xy_pairs, columns=["x", "y"])

    # 保存到 Excel
    df.to_excel(output_excel_path, index=False)
    print(f"已保存到 Excel 文件: {output_excel_path}")
    return df

# 使用示例
input_path = choose_file()

parse_binary_file(input_path)
