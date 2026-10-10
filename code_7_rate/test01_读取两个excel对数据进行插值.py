"""
读取两个Excel文件，根据参比测流的中间时刻对雷达流速进行线性插值，
最后生成一个只包含以下5列的Excel：

开始时间、结束时间、匹配时间、雷达流速、参比流速

运行前安装：
    pip install pandas numpy openpyxl
"""

from pathlib import Path

import numpy as np
import pandas as pd


# 两个原始Excel与本程序放在同一个文件夹中
DATA_FOLDER = Path(".")

RADAR_FILE = DATA_FOLDER / "Datasheet/02侧扫雷达水面平均流速汇总.xlsx"
REFERENCE_FILE = DATA_FOLDER / "Datasheet/01水文局参比断面平均流速汇总.xlsx"

# 最终生成的Excel文件名
OUTPUT_FILE = DATA_FOLDER / "Datasheet/03插值后的两个流速.xlsx"


def main():
    # 1. 读取侧扫雷达流速
    radar_df = pd.read_excel(
        RADAR_FILE,
        sheet_name="侧扫雷达流速汇总",
    )

    # 2. 读取水文局参比流速
    reference_df = pd.read_excel(
        REFERENCE_FILE,
        sheet_name="参比流速汇总",
    )

    # 3. 修改列名，方便后面处理
    radar_df = radar_df.rename(
        columns={
            "施测时间": "雷达时间",
            "侧扫雷达水面平均流速(m/s)": "雷达流速",
        }
    )

    reference_df = reference_df.rename(
        columns={
            "施测时间": "开始时间",
            "结束时分": "结束时间",
            "断面平均流速": "参比流速",
        }
    )

    # 4. 将时间列转换为时间格式
    radar_df["雷达时间"] = pd.to_datetime(
        radar_df["雷达时间"], errors="coerce"
    )
    reference_df["开始时间"] = pd.to_datetime(
        reference_df["开始时间"], errors="coerce"
    )
    reference_df["结束时间"] = pd.to_datetime(
        reference_df["结束时间"], errors="coerce"
    )

    # 5. 将流速列转换为数值格式
    radar_df["雷达流速"] = pd.to_numeric(
        radar_df["雷达流速"],errors="coerce"
    )
    reference_df["参比流速"] = pd.to_numeric(
        reference_df["参比流速"], errors="coerce"
    )

    # 6. 删除缺少时间或流速的数据
    radar_df = radar_df.dropna(subset=["雷达时间", "雷达流速"])
    reference_df = reference_df.dropna(
        subset=["开始时间", "结束时间", "参比流速"]
    )

    # 7. 按时间从早到晚排序
    radar_df = radar_df.sort_values("雷达时间").reset_index(drop=True)
    reference_df = reference_df.sort_values("开始时间").reset_index(drop=True)

    # 8. 匹配时间取参比测流开始时间和结束时间的中间时刻
    reference_df["匹配时间"] = (
        reference_df["开始时间"]
        + (reference_df["结束时间"] - reference_df["开始时间"]) / 2
    )

    # 9. 将时间转换为秒时间戳，便于使用numpy进行线性插值
    radar_seconds = (
        radar_df["雷达时间"].astype("int64") / 1_000_000_000
    ).to_numpy()
    match_seconds = (
        reference_df["匹配时间"].astype("int64") / 1_000_000_000
    ).to_numpy()

    # 10. 根据匹配时间，对雷达流速进行线性插值
    reference_df["雷达流速"] = np.interp(
        match_seconds,
        radar_seconds,
        radar_df["雷达流速"].to_numpy(),
    ).round(4)

    # 11. 只保留需要的5列
    result_df = reference_df[
        ["开始时间", "结束时间", "匹配时间", "雷达流速", "参比流速"]
    ]

    # 12. 生成Excel文件
    result_df.to_excel(
        OUTPUT_FILE,
        sheet_name="插值流速",
        index=False,
    )

    print(f"处理完成，共生成 {len(result_df)} 组数据")
    print(f"结果文件：{OUTPUT_FILE.resolve()}")


if __name__ == "__main__":
    main()
