import pandas as pd
import os
from datetime import datetime
from tkinter import Tk
from tkinter.filedialog import askopenfilename


# ========= 全局参数 =========
WIN = 3                       # 滑动平均窗口
KEEP_FIRST_WIN = False        # 是否保留前 win 行（True/False）

def choose_excel():
    Tk().withdraw()  # 隐藏主窗口
    file_path = askopenfilename(
        title="请选择 Excel 文件",
        filetypes=[("Excel 文件", "*.xlsx;*.xls")]
    )
    return file_path

def process_excel(input_file):
    # 读取 Excel
    df = pd.read_excel(input_file)

    # 计算滑动平均
    df_ma = df.rolling(window=WIN, min_periods=WIN).mean()

    # 是否保留前 win 行
    if not KEEP_FIRST_WIN:
        df_ma = df_ma.iloc[WIN - 1:]   # 去掉前 win 行

    # 生成输出文件名
    base, ext = os.path.splitext(input_file)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"{base}_win{WIN}_{timestamp}{ext}"

    if 0:
        df_ma.to_excel(output_file, index=False)
    else:
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            df_ma.to_excel(writer, index=False, header=False, startrow=1)

    print(f"滑动平均已完成，结果已保存到：\n{output_file}")



# ========== 主入口 ==========
if __name__ == "__main__":
    input_file = choose_excel()    # ← 修改为你的 Excel 文件路径
    process_excel(input_file)
