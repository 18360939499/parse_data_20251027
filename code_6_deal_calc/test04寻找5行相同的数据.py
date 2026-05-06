import pandas as pd
from tkinter import Tk
from tkinter.filedialog import askopenfilename

# ========================
# 选择文件
# ========================
def choose_excel():
    Tk().withdraw()
    return askopenfilename(
        title="请选择 Excel 文件",
        filetypes=[("Excel 文件", "*.xlsx;*.xls")]
    )

file_path = choose_excel()
if not file_path:
    print("未选择文件")
    exit()

# ========================
# 读取数据
# ========================
df = pd.read_excel(file_path)

# ========================
# 参数
# ========================
WINDOW = 5   # 连续行数
TOL = 1e-6   # 浮点容差（避免精度问题）

# ========================
# 核心逻辑
# ========================
results = []

# 除第一列外参与比较
data_cols = df.columns[1:]

for i in range(len(df) - WINDOW + 1):
    block = df.iloc[i:i+WINDOW]

    # 取第一行作为参考
    ref = block.iloc[0][data_cols]

    # 判断每一行是否与第一行一致
    is_same = block[data_cols].apply(
        lambda row: ((row - ref).abs() < TOL).all(),
        axis=1
    )

    if is_same.all():
        results.append(df.iloc[i, 0])  # 第一列 frame 名

# ========================
# 输出
# ========================
if results:
    print("找到连续相同的起始帧：")
    for r in results:
        print(r)
else:
    print("未找到符合条件的数据")