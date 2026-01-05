import os
import pandas as pd

from tkinter import Tk
from tkinter.filedialog import askopenfilename

# ======== 选择 Excel 文件 ========
def choose_excel():
    Tk().withdraw()  # 隐藏主窗口
    file_path = askopenfilename(
        title="请选择 Excel 文件",
        filetypes=[("Excel 文件", "*.xlsx;*.xls")]
    )
    return file_path

if __name__ == "__main__":
    # 让用户选择 Excel 文件
    input_file = choose_excel()
    if not input_file:
        print("❌ 未选择文件，程序退出")
        exit()

    df = pd.read_excel(input_file)

    # ======== 将数值列中小于0的值置为0 ========
    # 假设第一列是文件名，从第二列开始处理
    df.iloc[:, 1:] = df.iloc[:, 1:].clip(lower=0)

    # ======== 保存为新的 Excel ========
    # ======== 自动生成输出文件名 ========
    dirname, basename = os.path.split(input_file)
    name, ext = os.path.splitext(basename)

    # 输出文件名：原文件名 + "_nonnegative.xlsx"
    output_file = os.path.join(dirname, f"{name}_nonnegative{ext}")

    # 保存
    df.to_excel(output_file, index=False)

    print(f"处理完成，负数已置为0，新文件保存为：{output_file}")
