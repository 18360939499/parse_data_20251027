import pymysql
import os

# ====== MySQL 连接信息 ======
conn = pymysql.connect(
    host="127.0.0.1",
    user="root",
    password="AZDazd20230928@",
    database="csv",
    charset="utf8mb4",
    cursorclass=pymysql.cursors.SSCursor  # ⭐ 流式游标（关键）
)

cursor = conn.cursor()

# ====== 输出目录 ======
output_dir = "/www/data/export_frames"
os.makedirs(output_dir, exist_ok=True)

# ====== 查询（按条件） ======
cursor.execute("""
    SELECT id, matrix_original
    FROM test0104
    WHERE id BETWEEN 1253 AND 1263
    ORDER BY id ASC
""")

for row in cursor:
    frame_id = row[0]
    blob = row[1]

    out_file = os.path.join(output_dir, f"frame_{frame_id}.bin")
    with open(out_file, "wb") as f:
        f.write(blob)

    print(f"已导出 frame_{frame_id}.bin")

cursor.close()
conn.close()
