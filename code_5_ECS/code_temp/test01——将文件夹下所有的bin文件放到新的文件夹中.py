import os
import shutil
from tkinter import Tk
from tkinter.filedialog import askdirectory


NORMAL_PER_GROUP=1

def choose_src_folder():
    """弹出窗口选择源文件夹"""
    Tk().withdraw()  # 隐藏主窗口
    folder = askdirectory(title="请选择源文件夹")
    return folder


def collect_images(src_root, dst_folder, exts=None):
    """
    从 src_root 的所有子文件夹中收集图片，放到 dst_folder 中

    :param src_root: 根目录
    :param dst_folder: 目标文件夹
    :param exts: 图片扩展名集合，默认常见图片格式
    """
    if exts is None:
        exts = {".bin"}

    # 创建目标文件夹
    os.makedirs(dst_folder, exist_ok=True)

    count = 0
    dst_abs = os.path.abspath(dst_folder)

    for root, dirs, files in os.walk(src_root):
        # 🚫 跳过目标目录 itself
        if os.path.abspath(root) == dst_abs:
            continue

        for file in files:
            if os.path.splitext(file)[1].lower() in exts:
                src_path = os.path.join(root, file)
                dst_path = os.path.join(dst_folder, file)

                # if 0:
                #     # 避免文件名冲突
                #     if os.path.exists(dst_path):
                #         name, ext = os.path.splitext(file)
                #         i = 1
                #         while os.path.exists(dst_path):
                #             dst_path = os.path.join(dst_folder, f"{name}_{i}{ext}")
                #             i += 1

                # 🔁 同名文件直接覆盖
                shutil.copy2(src_path, dst_path)
                count += 1

    print(f"✅ 共复制 {count} 张图片到: {dst_folder}")


if __name__ == "__main__":
    src_root= choose_src_folder()
    if not src_root:
        print("❌ 未选择文件夹，程序退出")
        exit()

    #（2）自动创建目标目录 = 源目录 + "\all"
    dst_folder = os.path.join(src_root, "all2")

    collect_images(src_root, dst_folder)
