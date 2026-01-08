#!/usr/bin/env python3
import pymysql

# ====== 配置 ======
DB_CONFIG = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "AZDazd20230928@",
    "database": "csv",
    "charset": "utf8mb4",
}

KEEP_LATEST = 20     # 保留最新多少条
DELETE_LIMIT = 200   # 每次最多删除多少条
# ==================


def main():
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # 1️⃣ 获取最大 ID
    cursor.execute("SELECT MAX(id) FROM test0104")
    mxid = cursor.fetchone()[0]

    if mxid is None:
        print("表中没有数据")
        return

    threshold_id = mxid - KEEP_LATEST

    if threshold_id <= 0:
        print("数据量不足，无需删除")
        return

    print(f"当前最大 ID: {mxid}")
    print(f"删除阈值 ID < {threshold_id}")

    # 2️⃣ 分批删除（安全排序）
    delete_sql = """
        DELETE FROM test0104
        WHERE id IN (
            SELECT id FROM (
                SELECT id
                FROM test0104
                WHERE id < %s
                ORDER BY id ASC
                LIMIT %s
            ) t
        )
    """

    cursor.execute(delete_sql, (threshold_id, DELETE_LIMIT))
    affected = cursor.rowcount

    conn.commit()

    print(f"本次删除 {affected} 条数据")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
