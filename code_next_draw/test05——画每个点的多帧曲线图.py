import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import math

# ======== 读取 Excel ========
input_file = r"F:\2_python\test1024Gout\pythonProject1\.venv\code_main\data\11201539_write10_45_max2_3\20251121_085754_0.2_1_excel_7_all_nonnegative.xlsx"
df = pd.read_excel(input_file)

data = df.iloc[:, 1:]     # 从第1列开始为数值列
num_frames = df.shape[0]
num_cols = data.shape[1]

# ======== 分页参数 ========
cols_per_page = 16
rows = 4
cols = 4
num_pages = math.ceil(num_cols / cols_per_page)

# 计算所有列的 y 值范围
y_min = data.min().min()
y_max = data.max().max()

for page in range(num_pages):
    fig = plt.figure(figsize=(10, 10))

    start_col = page * cols_per_page
    end_col = min(start_col + cols_per_page, num_cols)

    for i, col_idx in enumerate(range(start_col, end_col)):
        ax = fig.add_subplot(rows, cols, i + 1)
        y = data.iloc[:, col_idx]
        ax.plot(range(num_frames), y)
        ax.set_title(f"Column {col_idx}", fontsize=10)

        # 固定纵坐标
        ax.set_ylim(y_min, y_max)

        # 设置纵坐标刻度间隔为 0.5
        ax.yaxis.set_major_locator(ticker.MultipleLocator(0.5))

    fig.subplots_adjust(
        left=0.05, right=0.95,
        top=0.92, bottom=0.05,
        wspace=0.3, hspace=0.4
    )

    fig.suptitle(f"Columns {start_col} - {end_col - 1}", fontsize=12)
    plt.show()
