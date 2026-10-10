import tkinter as tk
from tkinter import filedialog

import pandas as pd


# ==========================================================
# 从弹窗选择一个Excel文件并读取两列流速
# ==========================================================

# 创建并隐藏tkinter主窗口，只显示文件选择弹窗
root = tk.Tk()
root.withdraw()

# 保存到Excel
output_file = r"Datasheet\04逐个样本拟合结果.xlsx"

excel_file = filedialog.askopenfilename(
    title="请选择包含雷达流速和参比流速的Excel文件",
    filetypes=[
        ("Excel文件", "*.xlsx *.xls"),
        ("所有文件", "*.*"),
    ],
)

root.destroy()

# 如果用户没有选择文件，直接结束程序
if not excel_file:
    raise SystemExit("未选择Excel文件，程序已结束。")

# 默认读取Excel中的第一个工作表
data = pd.read_excel(excel_file)

# 清除列名前后可能存在的空格
data.columns = data.columns.astype(str).str.strip()

# 检查Excel中是否存在所需的两列
required_columns = ["雷达流速", "参比流速"]
missing_columns = [
    column for column in required_columns if column not in data.columns
]

if missing_columns:
    raise ValueError(
        "Excel中缺少以下列："
        + "、".join(missing_columns)
        + "。请确认表头名称为‘雷达流速’和‘参比流速’。"
    )

# 将两列转换成数值，不能转换的内容变为空值
data["雷达流速"] = pd.to_numeric(data["雷达流速"], errors="coerce")
data["参比流速"] = pd.to_numeric(data["参比流速"], errors="coerce")

# 只保留雷达流速和参比流速同时有效的数据行
valid_data = data[["雷达流速", "参比流速"]].dropna()

# 雷达流速作为Vr，即拟合中的x
vr = valid_data["雷达流速"].tolist()

# 参比流速作为Vbar，即拟合中的y
vbar = valid_data["参比流速"].tolist()

print("读取文件：", excel_file)
print("有效数据数量：", len(valid_data))

n = len(vr)

# 检查两组数据数量是否相同
if len(vr) != len(vbar):
    raise ValueError("Vr和Vbar的数据数量不一致！")

# ==========================================================
# 第一步：计算最小二乘公式需要的中间量
# ==========================================================

# Σx：所有Vr相加
sum_x = sum(vr)

# Σy：所有Vbar相加
sum_y = sum(vbar)

# Σ(x²)：每个Vr平方后相加
sum_x2 = sum(x * x for x in vr)

# Σ(xy)：每个Vr与对应Vbar相乘后相加
sum_xy = sum(x * y for x, y in zip(vr, vbar))

# 斜率和截距公式的共同分母
denominator = n * sum_x2 - sum_x * sum_x

if denominator == 0:
    raise ValueError("拟合分母为0，无法计算斜率和截距！")

# ==========================================================
# 第二步：计算斜率a
#
#     NΣ(xy) - ΣxΣy
# a = ----------------
#      NΣ(x²) - (Σx)²
# ==========================================================

a = (n * sum_xy - sum_x * sum_y) / denominator
a=round(a,6)
# ==========================================================
# 第三步：计算截距b
#
#     Σ(x²)Σy - ΣxΣ(xy)
# b = -------------------
#       NΣ(x²) - (Σx)²
# ==========================================================

b = (sum_x2 * sum_y - sum_x * sum_xy) / denominator
b=round(b,6)

# ==========================================================
# 第四步：输出中间计算结果
# ==========================================================

print("样本数量 N =", n)
print("Σx          =", format(sum_x, ".12f"))
print("Σy          =", format(sum_y, ".12f"))
print("Σ(x²)       =", format(sum_x2, ".12f"))
print("Σ(xy)       =", format(sum_xy, ".12f"))
print("计算分母    =", format(denominator, ".12f"))

print("\n拟合参数：")
print("斜率 a =", format(a, ".12f"))
print("截距 b =", format(b, ".12f"))

print("\n最终拟合关系：")
print(f"Vbar = {a:.6f} × Vr + {b:.6f}")

if 0:#直接打印
    # ==========================================================
    # 第五步：计算每个样本的拟合值和误差
    # ==========================================================

    print("\n逐个样本计算结果：")
    print("序号      Vr          Vbar        拟合Vbar       误差")

    # 用于累计残差平方和
    sse = 0.0

    for i, (x, y) in enumerate(zip(vr, vbar), start=1):

        # 根据拟合关系计算Vbar
        fitted_vbar = a * x + b

        # 残差 = 实际Vbar - 拟合Vbar
        error = y - fitted_vbar

        # 累加残差平方
        sse += error ** 2

        print(
            f"{i:2d}   "
            f"{x:10.6f}  "
            f"{y:10.6f}  "
            f"{fitted_vbar:10.6f}  "
            f"{error:10.6f}"
        )
else:#excel输出
    import pandas as pd

    # 用于累计残差平方和
    sse = 0.0
    # 用于保存每个样本的计算结果
    result_list = []

    for i, (x, y) in enumerate(zip(vr, vbar), start=1):
        # 根据拟合关系计算Vbar
        fitted_vbar = a * x + b
        fitted_vbar=round(fitted_vbar,6)

        # 残差 = 实际Vbar - 拟合Vbar
        error = y - fitted_vbar

        # 累加残差平方和
        sse += error ** 2

        # 将当前样本结果加入列表
        result_list.append(
            {
                "序号": i,
                "雷达速度Vr": x,
                "参比速度Vbar": y,
                "雷达速度拟合后": fitted_vbar,
                "误差": error,
            }
        )
    # 将列表转换成DataFrame
    result_df = pd.DataFrame(result_list)



    result_df.to_excel(
        output_file,
        sheet_name="拟合结果",
        index=False,
    )

    print(f"\n计算结果已经保存到：{output_file}")

# ==========================================================
# 第六步：计算误差指标
# ==========================================================

# Python自带的math库，不需要额外安装
import math

# 均方根误差
rmse = math.sqrt(sse / n)

# Vbar平均值
mean_y = sum_y / n

# 总离差平方和
sst = sum((y - mean_y) ** 2 for y in vbar)

# 带截距拟合的决定系数
r2 = 1 - sse / sst

print("\n误差统计：")
print("残差平方和 SSE =", format(sse, ".12f"))
print("均方根误差 RMSE =", format(rmse, ".12f"), "m/s")
print("决定系数 R² =", format(r2, ".12f"))
