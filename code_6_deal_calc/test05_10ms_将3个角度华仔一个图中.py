import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from tkinter import Tk
from tkinter.filedialog import askopenfilename


def choose_excel():
    Tk().withdraw()
    return askopenfilename(
        title="请选择 Excel 文件",
        filetypes=[("Excel 文件", "*.xlsx;*.xls")]
    )

# =========================
# 读取Excel文件
# =========================
file_path = choose_excel()
if not file_path:
    print("未选择文件")
    exit()

df = pd.read_excel(file_path)

# =========================
# 参数配置
# =========================
group_size = 100      # 每组100列
num_data = 7          # data1 ~ data6
start_col = 1         # 第1列开始是数据（第0列是帧号）

# 保存每组平均值
mean_results = {}

# 保存每组折线数据
all_data = {}

# =========================
# 提取 data1 ~ data6
# =========================
for i in range(num_data):

    col_start = start_col + i * group_size
    col_end = col_start + group_size

    # 取100列数据
    data_block = df.iloc[:, col_start:col_end]

    # 对所有行求平均
    mean_curve = data_block.mean(axis=0)

    # 保存
    data_name = f"data{i+1}"
    all_data[data_name] = mean_curve.values

    # 所有行整体平均值
    mean_results[data_name] = data_block.values.mean()

# =========================
# 绘制图1：data1~data3
# =========================
plt.figure(figsize=(12,6))

accel_labels = {
    1: "accelX",
    2: "accelY",
    3: "accelZ"
}
for i in range(1, 4):
    plt.plot(all_data[f"data{i}"], label=accel_labels[i])

# for i in range(1, 4):
#     plt.plot(all_data[f"data{i}"], label=f"data{i}")

plt.title("Accelerometer Data")
plt.xlabel("Index")
plt.ylabel("Value")
plt.legend()
plt.grid(True)

# =========================
# 绘制图2：data4~data6
# =========================
plt.figure(figsize=(12,6))

gyro_labels = {
    4: "gyroX",
    5: "gyroY",
    6: "gyroZ"
}
for i in range(4, 7):
    plt.plot(all_data[f"data{i}"], label=gyro_labels[i])
# for i in range(4, 7):
#     plt.plot(all_data[f"data{i}"], label=f"data{i}")

plt.title("Gyroscope Data")
plt.xlabel("Index")
plt.ylabel("Value")
plt.legend()
plt.grid(True)

# =========================
# 输出平均值
# =========================
print("各组平均值：")
for key, value in mean_results.items():
    print(f"{key} 平均值: {value:.6f}")

# =========================
# 显示图像
# =========================
plt.show()