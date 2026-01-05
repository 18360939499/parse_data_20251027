import os

def split_file_by_size(
    input_file,
    output_dir,
    chunk_size=100 * 1024  # 100KB
):
    """
    将大文件按固定字节大小拆分
    :param input_file: 原始sql文件路径
    :param output_dir: 拆分后文件保存目录
    :param chunk_size: 每个文件大小（字节）
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    base_name = os.path.splitext(os.path.basename(input_file))[0]

    with open(input_file, 'rb') as f:
        index = 1
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break

            out_file = os.path.join(
                output_dir,
                f"{base_name}_part{index:04d}.sql"
            )

            with open(out_file, 'wb') as out:
                out.write(chunk)

            print(f"生成文件: {out_file} ({len(chunk)} bytes)")
            index += 1


if __name__ == "__main__":
    input_sql = "v_data202509080942.sql"
    output_folder = "split_sql"

    split_file_by_size(
        input_file=input_sql,
        output_dir=output_folder,
        chunk_size=100 * 1024  # 100KB
    )
