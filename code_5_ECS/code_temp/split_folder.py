import os
import shutil
from tkinter import Tk
from tkinter.filedialog import askdirectory


def choose_folder():
    Tk().withdraw()  # 不显示主窗口
    folder = askdirectory(title="请选择包含 bin 文件的文件夹")
    if not folder:
        raise ValueError("未选择任何文件夹")
    print(f"已选择文件夹：{folder}")
    return folder


def split_bin_files(src_dir, files_per_folder=500, move_files=False):
    # 1. 找到所有 bin 文件
    bin_files = sorted([
        f for f in os.listdir(src_dir)
        if f.lower().endswith(".bin")
    ])

    if not bin_files:
        print("未找到任何 .bin 文件")
        return

    print(f"共找到 {len(bin_files)} 个 bin 文件")

    # 2. 分组
    for i in range(0, len(bin_files), files_per_folder):
        group = bin_files[i:i + files_per_folder]
        group_idx = i // files_per_folder + 1

        # 新文件夹名
        new_dir = os.path.join(
            src_dir,
            f"bin_group_{group_idx:03d}"
        )
        os.makedirs(new_dir, exist_ok=True)

        # 3. 复制 / 移动文件
        for fname in group:
            src_path = os.path.join(src_dir, fname)
            dst_path = os.path.join(new_dir, fname)

            if move_files:
                shutil.move(src_path, dst_path)
            else:
                shutil.copy2(src_path, dst_path)

        print(f"已处理：{new_dir}（{len(group)} 个文件）")


if __name__ == "__main__":
    folder = choose_folder()
    split_bin_files(
        folder,
        files_per_folder=500,
        move_files=False  # True = 移动，False = 复制
    )
