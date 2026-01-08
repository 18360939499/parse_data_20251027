import pymysql
import os

# ====== MySQL 连接信息 ======
conn = pymysql.connect(
    host="127.0.0.1",
    user="root",
    password="AZDazd20230928@",
    database="csv",
    charset="utf8mb4",
    cursorclass=pymysql.cursors.SSCursor  # ⭐ 流式游标
)

cursor = conn.cursor()

# ====== 输出根目录 ======
base_output_dir = "/www/data/export_frames"
os.makedirs(base_output_dir, exist_ok=True)

# ====== 查询 ======
cursor.execute("""
    SELECT id, matrix_original
    FROM test0104
    WHERE id BETWEEN 1253 AND 2117
    ORDER BY id ASC
""")

batch_size = 100          # 每个文件夹 100 个文件
batch_index = 1           # 第几个文件夹
file_count = 0            # 当前文件夹内文件数量

current_batch_dir = None

for row in cursor:
    frame_id = row[0]
    blob = row[1]

    # 如果是新的一批，创建新目录
    if file_count % batch_size == 0:
        batch_name = f"batch_{batch_index:04d}"
        current_batch_dir = os.path.join(base_output_dir, batch_name)
        os.makedirs(current_batch_dir, exist_ok=True)
        batch_index += 1

    out_file = os.path.join(current_batch_dir, f"frame_{frame_id}.bin")
    with open(out_file, "wb") as f:
        f.write(blob)

    file_count += 1
    print(f"已导出 {batch_name}/frame_{frame_id}.bin")

cursor.close()
conn.close()

print("✅ 导出完成")
