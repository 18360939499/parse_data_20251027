import os
import shutil

src_root = r"F:\2_python\test1024Gout\pythonProject1\.venv\data_1024_1747_1\10241747\pictures_no_normal"  # 源根目录
dst_folder = r"F:\2_python\test1024Gout\pythonProject1\.venv\data_1024_1747_1\10241747\pictures_no_normal\all"  # 收集到的新文件夹

def collect_images(src_root, dst_folder, exts=None):
    """
    从 src_root 的所有子文件夹中收集图片，放到 dst_folder 中

    :param src_root: 根目录
    :param dst_folder: 目标文件夹
    :param exts: 图片扩展名集合，默认常见图片格式
    """
    if exts is None:
        exts = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}

    # 创建目标文件夹
    os.makedirs(dst_folder, exist_ok=True)

    count = 0
    for root, dirs, files in os.walk(src_root):
        for file in files:
            if os.path.splitext(file)[1].lower() in exts:
                src_path = os.path.join(root, file)
                dst_path = os.path.join(dst_folder, file)

                # 避免文件名冲突
                if os.path.exists(dst_path):
                    name, ext = os.path.splitext(file)
                    i = 1
                    while os.path.exists(dst_path):
                        dst_path = os.path.join(dst_folder, f"{name}_{i}{ext}")
                        i += 1

                shutil.copy2(src_path, dst_path)
                count += 1

    print(f"✅ 共复制 {count} 张图片到: {dst_folder}")


if __name__ == "__main__":

    collect_images(src_root, dst_folder)
