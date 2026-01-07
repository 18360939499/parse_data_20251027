import os

from tkinter import Tk
from tkinter.filedialog import askopenfilename

def choose_sql_file():
    """弹窗选择 .bin 文件"""
    Tk().withdraw()
    file_path = askopenfilename(
        title="请选择雷达原始 sql 文件",
        filetypes=[("sql 文件", "*.sql"), ("所有文件", "*.*")]
    )
    return file_path

def split_file_by_size(
    input_file,
    output_dir,
    chunk_size=100 * 1024  # 100KB
):
    """
    将大文件按固定字节大小拆分
    :param input_file: 原始sql文件路径
    :param output_dir: 拆分后文件保存目录
    :param chunk_size: 每个文件大小（字节）
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    base_name = os.path.splitext(os.path.basename(input_file))[0]

    with open(input_file, 'rb') as f:
        index = 1
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break

            out_file = os.path.join(
                output_dir,
                f"{base_name}_part{index:04d}.sql"
            )

            with open(out_file, 'wb') as out:
                out.write(chunk)

            print(f"生成文件: {out_file} ({len(chunk)} bytes)")
            index += 1




if __name__ == "__main__":
    # input_sql = "v_data202509080942.sql"
    # output_folder = "split_sql"

    # 1️⃣ 选择输入文件
    input_sql = choose_sql_file()
    if not input_sql:
        print("❌ 未选择文件，程序退出")
        exit()

    # 2️⃣ 自动生成输出目录：同目录 + 文件名（无后缀）
    base_dir = os.path.dirname(input_sql)
    base_name = os.path.splitext(os.path.basename(input_sql))[0]
    suffix = "_split"
    output_folder = os.path.join(base_dir, base_name+suffix)

    print(f"✔ 输入文件：{input_sql}")
    print(f"✔ 输出文件夹：{output_folder}")

    split_file_by_size(
        input_file=input_sql,
        output_dir=output_folder,
        chunk_size=5000 * 1024  # 100KB,一个文件100KB
    )
