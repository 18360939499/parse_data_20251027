import os
import struct
import pandas as pd
import chardet

from tkinter import Tk
from tkinter.filedialog import askdirectory



start_flag = bytes.fromhex("05 00 00 00")
flagLength=0xCA8

produce_file_name = "server_parsed_05_all.xlsx"  # 保存的文件名

# ===============================
# 选择文件夹（新增）
# ===============================
def choose_folder():
    Tk().withdraw()  # 隐藏Tk窗口
    folder = askdirectory(title="请选择要解析的文件夹")
    if not folder:
        raise ValueError("未选择文件夹")
    print(f"已选择文件夹：{folder}")
    return folder

def detect_encoding(file_path):
    with open(file_path, 'rb') as f:
        raw_data = f.read(10000)
    result = chardet.detect(raw_data)
    encoding = result['encoding']
    confidence = result['confidence']
    print(f"自动检测编码: {encoding} (置信度: {confidence:.2f})")
    return encoding


def parse_binary_file(file_path, start_flag):

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

        data_length = struct.unpack('<I', content[start_index + 4:start_index + 8])[0]

        # ==============================
        # ✅ 关键判断点
        # ==============================
        if data_length != flagLength:
            # 不是合法帧，继续找下一个 start_flag
            start = start_index + 1
            continue

        data_start = start_index + len(start_flag) + 4
        data_end = data_start + data_length
        if data_end > len(content):
            print(f"{os.path.basename(file_path)} 剩余内容不足一帧，跳过")
            break

        data_bytes = content[data_start:data_end]
        if 0:
            floats = [struct.unpack('<f', data_bytes[i:i + 4])[0] for i in range(0, len(data_bytes), 4)]
        else:
            # === 1.  uint32 ===
            data_part1=[]
            for i in range(36, (36+6*4*100), 4):
                value = struct.unpack('<f', data_bytes[i:i + 4])[0]
                data_part1.append(value)

            data_part2 = []
            for i in range((36+6*4*100), len(data_bytes)-4, 8):
                value = struct.unpack('<Q', data_bytes[i:i + 8])[0]
                data_part2.append(value)

            data_part3 = []
            for i in range((36 + 6 * 4 * 100 +1*8*100), len(data_bytes) , 4):
                value = struct.unpack('<I', data_bytes[i:i + 4])[0]
                data_part3.append(value)

            # === 3. 合并两个uint32 + float部分 ===
            floats = data_part1 + data_part2 + data_part3

        floats_all.append(floats)

        # 继续搜索下一个
        start = data_end

    return floats_all


def parse_folder(input_folder):
    # 起始标志

    all_data = []
    for file_name in os.listdir(input_folder):
        if file_name.lower().endswith(".bin"):
            file_path = os.path.join(input_folder, file_name)
            if not os.path.isfile(file_path):
                continue

            floats_all = parse_binary_file(file_path, start_flag)

            for floats in floats_all:
                # 每行前面加文件名
                all_data.append([file_name] + floats)

    # header_columns = [
    #     "文件名",
    #     "mpu_tempC",
    #     "mpu_accelX",
    #     "mpu_accelY",
    #     "mpu_accelZ",
    #     "mpu_gyroX",
    #     "mpu_gyroY",
    #     "mpu_gyroZ",
    #     "mpu_isValid"
    # ]
    # # 校验列数是否匹配（非常推荐）
    # if len(header_columns) != len(all_data[0]):
    #     raise ValueError(
    #         f"列名数量({len(header_columns)}) 与数据列数({len(all_data[0])}) 不一致"
    #     )

    if all_data:
        # df = pd.DataFrame(all_data, columns=header_columns)
        df = pd.DataFrame(all_data)

        df.to_excel(os.path.join(input_folder, produce_file_name),
                    index=False, header=True)
        print(f"已解析 {len(all_data)} 行，保存到：{os.path.join(input_folder, 'server_parsed_05_all.xlsx')}")
    else:
        print("未解析到任何数据帧")


# 使用示例
input_folder = choose_folder()

parse_folder(input_folder)
