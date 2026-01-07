import os
import re

from tkinter import Tk
from tkinter.filedialog import askopenfilename

def choose_sql_file():
    """弹窗选择 .sql 文件"""
    Tk().withdraw()
    file_path = askopenfilename(
        title="请选择雷达原始 sql 文件",
        filetypes=[("SQL 文件", "*.sql"), ("所有文件", "*.*")]
    )
    return file_path

def sql_to_bin(sql_file):
    # 生成输出目录
    base_name = os.path.splitext(sql_file)[0]
    output_dir = f"{base_name}_output"
    os.makedirs(output_dir, exist_ok=True)

    # 读取sql文件
    with open(sql_file, "r", encoding="utf-8") as f:
        content = f.read()

    # 匹配INSERT语句
    pattern = re.compile(
        r"INSERT INTO `test0104`.*?\((\d+),\s*0x([0-9a-fA-F]+),",
        re.DOTALL
    )

    matches = pattern.findall(content)

    for id_val, hex_str in matches:
        file_path = os.path.join(output_dir, f"{id_val}.bin")
        with open(file_path, "wb") as f:
            f.write(bytes.fromhex(hex_str))
        print(f"生成文件: {file_path}")

if __name__ == "__main__":
    # 1️⃣ 选择输入文件
    input_file = choose_sql_file()
    if not input_file:
        print("❌ 未选择文件，程序退出")
        exit()

    sql_to_bin(input_file)
