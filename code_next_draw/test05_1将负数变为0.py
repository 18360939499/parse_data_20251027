import pandas as pd

# ======== 读取 Excel ========
input_file = r"F:\2_python\test1024Gout\pythonProject1\.venv\code_main\data\11201539_write10_45_max2_3\20251121_085754_0.2_1_excel_7_all.xlsx"
df = pd.read_excel(input_file)

# ======== 将数值列中小于0的值置为0 ========
# 假设第一列是文件名，从第二列开始处理
df.iloc[:, 1:] = df.iloc[:, 1:].clip(lower=0)

# ======== 保存为新的 Excel ========
output_file = r"F:\2_python\test1024Gout\pythonProject1\.venv\code_main\data\11201539_write10_45_max2_3\20251121_085754_0.2_1_excel_7_all_nonnegative.xlsx"
df.to_excel(output_file, index=False)

print(f"处理完成，负数已置为0，新文件保存为：{output_file}")
