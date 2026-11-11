"""水文雷达流速关系率定与精度检验软件 V1.0。

启动桌面界面：python radar_calibration.py
批处理：python radar_calibration.py --input samples.csv --output results
本程序以已经完成同期配对的流速样本为输入。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm, t as student_t

NAME = "水文雷达流速关系率定与精度检验软件"
VERSION = "1.0"
ALIASES = {
    "序号": ["序号", "编号"],
    "雷达流速": ["雷达流速", "雷达速度vr", "雷达水面平均流速", "侧扫雷达水面平均流速（m/s）"],
    "参比流速": ["参比流速", "参比速度vbar", "参比断面平均流速（m/s）"],
    "水位": ["水位", "水位（m）"],
    "参与率定": ["参与率定"],
    "排除原因": ["排除原因"],
}


@dataclass
class Settings:
    """阈值来自所附报告的计算口径，可按审核要求调整。"""
    mode: str = "fit"
    param_a: float = 0.9432
    param_b: float = 0.0442
    sign_alpha: float = 0.25
    runs_alpha: float = 0.05
    deviation_alpha: float = 0.10
    system_limit: float = 0.01
    uncertainty_limit: float = 0.10
    zero_tolerance: float = 1e-12
    station: str = "宿迁某站"

    def validate(self):
        if self.mode not in ("fit", "fixed"):
            raise ValueError("计算模式必须为fit或fixed")
        for key in ("sign_alpha", "runs_alpha", "deviation_alpha"):
            if not 0 < getattr(self, key) < 1:
                raise ValueError(f"{key}必须在0与1之间")
        for key in ("param_a", "param_b", "system_limit", "uncertainty_limit", "zero_tolerance"):
            if not math.isfinite(getattr(self, key)):
                raise ValueError(f"{key}必须为有限数值")
        if min(self.system_limit, self.uncertainty_limit, self.zero_tolerance) < 0:
            raise ValueError("限值和零值容差不能为负数")


def normalize(value):
    return "".join(str(value).split()).lower()


def read_data(path: Path, sheet=0):
    """兼容原始率定输入和原拟合结果表，保留原行及业务列。"""
    if path.suffix.lower() == ".csv":
        try:
            df = pd.read_csv(path, encoding="utf-8-sig")
        except UnicodeDecodeError:
            df = pd.read_csv(path, encoding="gb18030")
    elif path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(path, sheet_name=sheet)
    else:
        raise ValueError("仅支持xlsx、xls或csv文件")
    if df.empty:
        raise ValueError("输入表没有数据")
    rename = {}
    for canonical, aliases in ALIASES.items():
        matches = [c for c in df.columns if normalize(c) in aliases]
        if len(matches) > 1:
            raise ValueError(f"{canonical}存在多个候选列，请保留一列")
        if matches:
            rename[matches[0]] = canonical
    df = df.rename(columns=rename)
    for field in ("雷达流速", "参比流速"):
        if field not in df:
            raise ValueError(f"缺少列：{field}")
        df[field] = pd.to_numeric(df[field], errors="coerce")
    if "序号" not in df:
        df["序号"] = np.arange(1, len(df) + 1)
    if df["序号"].isna().any() or df["序号"].astype(str).duplicated().any():
        raise ValueError("序号必须非空且唯一")
    if "水位" in df:
        df["水位"] = pd.to_numeric(df["水位"], errors="coerce")
    if "参与率定" in df:
        yes = {"1", "1.0", "是", "true", "参与"}
        no = {"0", "0.0", "否", "false", "不参与"}
        values = df["参与率定"].map(normalize)
        if not values.isin(yes | no).all():
            raise ValueError("参与率定列只允许是/否、1/0或true/false")
        df["参与率定"] = values.isin(yes)
    else:
        df["参与率定"] = True
    if "排除原因" not in df:
        df["排除原因"] = ""
    df["排除原因"] = df["排除原因"].fillna("").astype(str)
    if ((~df["参与率定"]) & (df["排除原因"].str.strip() == "")).any():
        raise ValueError("不参与率定的样本必须填写排除原因")
    df["源文件行号"] = np.arange(2, len(df) + 2)
    return df.reset_index(drop=True)


def set_participation(df, indices, include, reason=""):
    """人工排除必须填写依据；恢复参与后清除对应排除标记。"""
    if not include and not reason.strip():
        raise ValueError("请填写排除原因")
    df.loc[indices, "参与率定"] = include
    df.loc[indices, "排除原因"] = "" if include else reason.strip()


def test_item(name, value=None, critical=None, passed=None, note=""):
    return {"检验项目": name, "计算值": value, "控制值": critical,
            "结论": "无法评价" if passed is None else ("通过" if passed else "未通过"),
            "说明": note}


def analyze(data, settings: Settings):
    """统一样本、参数、残差和百分比口径，不在中间步骤舍入。"""
    settings.validate()
    raw = data.copy(deep=True)
    finite = np.isfinite(raw[["雷达流速", "参比流速"]].to_numpy(dtype=float)).all(axis=1)
    raw["数据有效"] = finite
    raw["数据校验说明"] = np.where(finite, "", "流速缺失或不是有限数值")
    selected = raw["参与率定"] & finite
    samples = raw.loc[selected].copy()
    n = len(samples)
    if n <= 2:
        raise ValueError("有效参与样本必须大于2")
    x = samples["雷达流速"].to_numpy(dtype=float)
    y = samples["参比流速"].to_numpy(dtype=float)
    sx, sy, sx2, sxy = map(float, (x.sum(), y.sum(), np.dot(x, x), np.dot(x, y)))
    denominator = n * sx2 - sx * sx
    if settings.mode == "fit":
        # 中心化计算避免大偏置数据的抵消误差。
        xc, yc = x - x.mean(), y - y.mean()
        xx = float(np.dot(xc, xc))
        if xx <= np.finfo(float).eps * max(1.0, float(np.dot(x, x))):
            raise ValueError("雷达流速变化不足，无法唯一确定带截距直线")
        calc_a = float(np.dot(xc, yc) / xx)
        calc_b = float(y.mean() - calc_a * x.mean())
    else:
        calc_a, calc_b = settings.param_a, settings.param_b
    fitted = calc_a * x + calc_b
    residual = y - fitted
    eps = settings.zero_tolerance
    signs = np.where(residual > eps, 1, np.where(residual < -eps, -1, 0))
    samples["拟合流速"] = fitted
    samples["残差"] = residual
    samples["残差符号"] = signs
    relative = np.full(n, np.nan)
    valid_relative = np.abs(fitted) > eps
    relative[valid_relative] = residual[valid_relative] / fitted[valid_relative]
    # logs = np.full(n, np.nan)
    # valid_log = (y > 0) & (fitted > 0)
    # logs[valid_log] = np.log(y[valid_log]) - np.log(fitted[valid_log])
    samples["相对偏离"] = relative
    # samples["对数偏离"] = logs
    samples["相对法说明"] = np.where(valid_relative, "", "拟合值为零或近零，无法相除")
    # samples["对数法说明"] = np.where(valid_log, "", "参比值或拟合值不大于零，无法取对数")
    sse = float(np.dot(residual, residual))
    sst = float(np.dot(y - y.mean(), y - y.mean()))
    r2 = None if sst == 0 else 1 - sse / sst
    r = None if np.std(x) == 0 or np.std(y) == 0 else float(np.corrcoef(x, y)[0, 1])
    summary = {"软件名称": NAME, "版本": VERSION, "计算模式": settings.mode,
               "总样本数": len(raw), "有效参与数": n, "人工不参与数": int((~raw["参与率定"]).sum()),
               "数据无效数": int((~finite).sum()), "calc_a": calc_a, "calc_b": calc_b,
               "Σx": sx, "Σy": sy, "Σx²": sx2, "Σxy": sxy, "分母": denominator,
               "SSE": sse, "RMSE": math.sqrt(sse / n),
               "MAE": float(np.abs(residual).mean()), "r": r, "R²": r2,
               "雷达流速最小值": float(x.min()), "雷达流速最大值": float(x.max()),
               "参比流速最小值": float(y.min()), "参比流速最大值": float(y.max())}
    # 零残差属于线上点，从符号序列排除并报告数量。
    nonzero = signs[signs != 0]
    ns = len(nonzero)
    positive, negative = int((signs > 0).sum()), int((signs < 0).sum())
    sign_critical = float(norm.ppf(1 - settings.sign_alpha / 2))
    u = max(0.0, (abs(min(positive, negative) - ns / 2) - 0.5) / (0.5 * math.sqrt(ns))) if ns else None
    tests = [test_item("符号检验", u, sign_critical, None if u is None else u <= sign_critical,
                       f"正号{positive}，负号{negative}，零残差{n-ns}，符号有效N={ns}")]
    # 水位相同采用原始行号稳定排序，缺失水位时不替换排序变量。
    runs = samples.copy()
    runs["符号变换"] = 0
    runs_critical = float(norm.ppf(1 - settings.runs_alpha))
    if "水位" not in samples or not np.isfinite(samples["水位"].to_numpy(dtype=float)).all():
        tests.append(test_item("适线检验", critical=runs_critical, note="缺少完整水位，不能按水位排序评价"))
    else:
        runs = samples.sort_values(["水位", "源文件行号"], kind="stable").copy()
        sequence = runs.loc[runs["残差符号"] != 0, "残差符号"]
        flips = (sequence != sequence.shift()).astype(int)
        if len(flips):
            flips.iloc[0] = 0
        runs["符号变换"] = 0
        runs.loc[flips.index, "符号变换"] = flips
        k = int(flips.sum())
        m = len(sequence)
        ru = (m - 2 * (k + 1)) / math.sqrt(m - 1) if m > 1 else None
        exempt = m > 1 and k >= (m - 1) / 2
        item = test_item("适线检验", ru, runs_critical,
                         None if ru is None else exempt or ru <= runs_critical,
                         f"水位升序，同水位原行序；N={m}，K={k}" + ("；达到免检条件" if exempt else ""))
        if exempt:
            item["结论"] = "免检"
        tests.append(item)
        summary.update({"适线K": k, "适线N": m})
    # 百分比指标仅在全体参与样本均可计算时给出整体判定。
    if valid_relative.all():
        mean_p = float(relative.mean())
        std_p = float(relative.std(ddof=1))
        se_mean = std_p / math.sqrt(n)
        statistic = abs(mean_p) / se_mean if se_mean > eps else (0.0 if abs(mean_p) <= eps else math.inf)
        critical_t = float(student_t.ppf(1 - settings.deviation_alpha / 2, n - 1))
        uncertainty = 2 * math.sqrt(float(np.dot(relative, relative)) / (n - 2))
        tests += [test_item("偏离数值检验", statistic, critical_t, statistic <= critical_t, f"自由度{n-1}；P=(参比-拟合)/拟合"),
                  test_item("系统误差", mean_p, settings.system_limit, abs(mean_p) <= settings.system_limit, "计算值为小数比例，显示及表格以百分数表示"),
                  test_item("随机不确定度", uncertainty, settings.uncertainty_limit, uncertainty <= settings.uncertainty_limit, "相对法2Se=2√[ΣP²/(N-2)]")]
        summary.update({"平均相对偏离": mean_p, "相对偏离标准差": std_p,
                        "平均偏离标准差": se_mean, "相对法2Se": uncertainty})
    else:
        for title in ("偏离数值检验", "系统误差", "随机不确定度"):
            tests.append(test_item(title, note=f"{int((~valid_relative).sum())}组拟合值为零或近零；整体无法评价"))
    # ln_count = int(valid_log.sum())
    # ln_u = 2 * math.sqrt(float(np.dot(logs[valid_log], logs[valid_log])) / (ln_count - 2)) if ln_count > 2 else None
    # summary.update({"相对法有效数": int(valid_relative.sum()), "对数法有效数": ln_count,
    #                 "对数法2Se": ln_u,
    #                 "对数法范围": "全体参与样本" if ln_count == n else "仅可取对数子集，不能替代全体评价"})

    summary.update({
        "相对法有效数": int(valid_relative.sum())
    })

    complete = all(item["结论"] in ("通过", "免检") for item in tests)
    summary["五项指标结论"] = "全部通过" if complete else "存在未通过或无法评价项目"
    summary["样本数提示"] = "达到报告采用的30组样本数量" if n >= 30 else "少于报告采用的30组样本数量"
    return {"raw": raw, "samples": samples, "runs": runs,
            "summary": summary, "tests": tests, "settings": asdict(settings)}


def make_figure(result):
    """关系线、残差及水位序偏离共用本次计算结果。"""
    from matplotlib.figure import Figure
    from matplotlib import rcParams
    rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "DejaVu Sans"]
    rcParams["axes.unicode_minus"] = False
    figure = Figure(figsize=(11, 7), dpi=110, constrained_layout=True)
    axes = figure.subplots(2, 2)
    df, info = result["samples"], result["summary"]
    x, y = df["雷达流速"], df["参比流速"]
    axes[0, 0].scatter(x, y, s=25, label=f"有效样本 N={len(df)}")
    xx = np.linspace(float(x.min()), float(x.max()), 100)
    axes[0, 0].plot(xx, info["calc_a"] * xx + info["calc_b"], color="teal",
                    label=f"V-={info['calc_a']:.6f}Vr+{info['calc_b']:.6f}")#V̄
    axes[0, 0].set(xlabel="雷达流速 m/s", ylabel="参比流速 m/s", title="流速关系率定")
    axes[0, 0].legend(fontsize=8)
    axes[0, 1].scatter(x, df["残差"], s=25)
    axes[0, 1].axhline(0, color="gray", linestyle="--")
    axes[0, 1].set(xlabel="雷达流速 m/s", ylabel="参比减拟合 m/s", title="残差分布")
    ordered = result["runs"]
    if "水位" in ordered:
        axes[1, 0].plot(ordered["水位"], ordered["相对偏离"] * 100, "o-", markersize=3)
        axes[1, 0].set(xlabel="水位 m", ylabel="相对偏离 %", title="水位序相对偏离")
    else:
        axes[1, 0].text(.5, .5, "未提供水位", ha="center")
    axes[1, 1].axis("off")
    lines = [info["五项指标结论"], f"RMSE={info['RMSE']:.6f} m/s", f"MAE={info['MAE']:.6f} m/s"]
    for item in result["tests"]:
        value = item["计算值"]
        text = "无法计算" if value is None else f"{value:.6f}"
        if item["检验项目"] in ("系统误差", "随机不确定度") and value is not None:
            text = f"{value * 100:.4f}%"
        lines.append(f"{item['检验项目']}：{text}  {item['结论']}")
    axes[1, 1].text(.02, .98, "\n".join(lines), va="top", fontsize=10)
    for axis in axes.flat[:3]:
        axis.grid(alpha=.25)
    return figure


def export_result(result, directory: Path, source: Path | None = None):
    """每次新建时间戳目录，原始输入不被覆盖。"""
    directory.mkdir(parents=True, exist_ok=True)
    folder = directory / datetime.now().strftime("result_%Y%m%d_%H%M%S_%f")
    folder.mkdir()
    workbook = folder / "率定与精度检验结果.xlsx"
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        for key, title in (("raw", "原始数据与校验"), ("samples", "逐样本计算"), ("runs", "水位排序与符号变换")):
            result[key].to_excel(writer, sheet_name=title, index=False)
        pd.DataFrame(result["tests"]).to_excel(writer, sheet_name="五项指标", index=False)
        pd.DataFrame(list(result["summary"].items()), columns=["项目", "数值"]).to_excel(writer, sheet_name="率定汇总", index=False)
        pd.DataFrame(list(result["settings"].items()), columns=["参数", "值"]).to_excel(writer, sheet_name="参数配置", index=False)
        from openpyxl.styles import Font, PatternFill
        for ws in writer.book:
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for cell in ws[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="234E70")
            for column in ws.columns:
                letter = column[0].column_letter
                width = max(len(str(c.value or "")) for c in column)
                ws.column_dimensions[letter].width = min(50, max(14, width * 1.5))
                for cell in column[1:]:
                    if isinstance(cell.value, float):
                        cell.number_format = "0.000000"
                # if str(column[0].value) in ("相对偏离", "对数偏离"):
                #     for cell in column[1:]:
                #         cell.number_format = "0.0000%"
                if str(column[0].value) == "相对偏离":
                    for cell in column[1:]:
                        cell.number_format = "0.0000%"
        ws = writer.book["五项指标"]
        for row in ws.iter_rows(min_row=2):
            if row[0].value in ("系统误差", "随机不确定度"):
                row[1].number_format = row[2].number_format = "0.0000%"
    figure = make_figure(result)
    figure.savefig(folder / "关系线与精度检验.png", dpi=180)
    manifest = {"software": NAME, "version": VERSION, "time": datetime.now().isoformat(),
                "source": str(source) if source else None,
                "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest() if source else None,
                "settings": result["settings"], "summary": result["summary"], "tests": result["tests"]}
    # 非有限统计量写为字符串，保证标准JSON可读。
    def clean(value):
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items()}
        if isinstance(value, list):
            return [clean(v) for v in value]
        if isinstance(value, float) and not math.isfinite(value):
            return str(value)
        return value
    (folder / "计算记录.json").write_text(json.dumps(clean(manifest), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return folder


class Application:
    """桌面工作流：导入、人工复核、率定、检验、图表、导出。"""
    def __init__(self, root):
        import tkinter as tk
        from tkinter import ttk
        self.root, self.tk, self.ttk = root, tk, ttk
        self.data = self.result = self.source = None
        root.title(f"{NAME} V{VERSION}")
        root.geometry("1180x780")
        bar = ttk.Frame(root, padding=10)
        bar.pack(fill="x")
        for title, callback in (("导入数据", self.load), ("排除选中样本", self.exclude),
                                ("恢复选中样本", self.restore), ("计算率定与检验", self.calculate),
                                ("导出成果", self.export)):
            ttk.Button(bar, text=title, command=callback).pack(side="left", padx=4)
        config = ttk.LabelFrame(root, text="率定及精度配置", padding=8)
        config.pack(fill="x", padx=10)
        self.mode = tk.StringVar(value="重新率定")
        ttk.Combobox(config, textvariable=self.mode, values=["重新率定", "固定关系复核"], state="readonly", width=14).grid(row=0, column=0)
        self.variables = {}
        fields = [("param_a", "斜率a", "0.9432"), ("param_b", "截距b", "0.0442"),
                  ("sign_alpha", "符号α", "0.25"), ("runs_alpha", "适线α", "0.05"),
                  ("deviation_alpha", "偏离α", "0.10"), ("system_limit", "系统限值%", "1"),
                  ("uncertainty_limit", "随机限值%", "10")]
        for i, (key, label, default) in enumerate(fields):
            row, col = divmod(i, 4)
            ttk.Label(config, text=label).grid(row=row + 1, column=col * 2, padx=5)
            variable = tk.StringVar(value=default)
            self.variables[key] = variable
            ttk.Entry(config, textvariable=variable, width=11).grid(row=row + 1, column=col * 2 + 1, pady=4)
            variable.trace_add("write", self.invalidate)
        self.mode.trace_add("write", self.invalidate)
        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True, padx=10, pady=8)
        self.table_frame, result_frame, self.figure_frame = (ttk.Frame(notebook) for _ in range(3))
        for frame, title in ((self.table_frame, "数据与样本管理"), (result_frame, "率定与五项指标"), (self.figure_frame, "关系线与残差图")):
            notebook.add(frame, text=title)
        self.tree = ttk.Treeview(self.table_frame, show="headings", selectmode="extended")
        self.tree.pack(fill="both", expand=True, side="left")
        scrollbar = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.text = tk.Text(result_frame, wrap="word", font=("Microsoft YaHei", 11))
        self.text.pack(fill="both", expand=True)
        self.status = tk.StringVar(value="请导入已完成同期配对的Excel或CSV数据")
        ttk.Label(root, textvariable=self.status, padding=8).pack(fill="x")

    def invalidate(self, *_):
        self.result = None
        if hasattr(self, "text"):
            self.text.delete("1.0", "end")
            for child in self.figure_frame.winfo_children():
                child.destroy()
            self.status.set("数据或配置已变更，请重新计算")

    def error(self, exc):
        from tkinter import messagebox
        messagebox.showerror("操作失败", str(exc), parent=self.root)

    def refresh(self):
        columns = ["序号", "雷达流速", "参比流速", "水位", "参与率定", "排除原因"]
        self.tree.delete(*self.tree.get_children())
        self.tree["columns"] = columns
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=280 if col == "排除原因" else 130, anchor="center")
        for index, row in self.data.iterrows():
            values = [row.get(c, "") for c in columns]
            values[4] = "是" if row["参与率定"] else "否"
            self.tree.insert("", "end", iid=str(index), values=values)

    def load(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(parent=self.root, filetypes=[("数据文件", "*.xlsx *.xls *.csv")])
        if not path:
            return
        try:
            source = Path(path)
            data = read_data(source)
            self.source, self.data = source, data
            self.invalidate()
            self.refresh()
            self.status.set(f"已导入{len(data)}组；Excel默认读取第一工作表")
        except Exception as exc:
            self.error(exc)

    def exclude(self):
        from tkinter import simpledialog
        rows = [int(i) for i in self.tree.selection()]
        if not rows:
            return
        reason = simpledialog.askstring("排除依据", "填写现场记录或复核原因", parent=self.root)
        if reason is None:
            return
        try:
            set_participation(self.data, rows, False, reason)
            self.invalidate()
            self.refresh()
        except Exception as exc:
            self.error(exc)

    def restore(self):
        rows = [int(i) for i in self.tree.selection()]
        if rows:
            set_participation(self.data, rows, True)
            self.invalidate()
            self.refresh()

    def calculate(self):
        if self.data is None:
            self.error("请先导入数据")
            return
        try:
            values = {key: float(var.get()) for key, var in self.variables.items()}
            values["system_limit"] /= 100
            values["uncertainty_limit"] /= 100
            settings = Settings(mode="fit" if self.mode.get() == "重新率定" else "fixed", **values)
            self.result = analyze(self.data, settings)
            summary = self.result["summary"]
            lines = [f"{NAME} V{VERSION}", f"有效参与样本 N={summary['有效参与数']}",
                     f"V- = {summary['calc_a']:.6f} × Vr + {summary['calc_b']:.6f}",
                     f"RMSE={summary['RMSE']:.6f}；MAE={summary['MAE']:.6f}",
                     f"r={summary['r']}；R²={summary['R²']}", ""]
            for item in self.result["tests"]:
                value = item["计算值"]
                display = str(value)
                if item["检验项目"] in ("系统误差", "随机不确定度") and value is not None:
                    display = f"{value * 100:.4f}%"
                lines.extend([f"{item['检验项目']}：{display}，{item['结论']}", item["说明"], ""])
            # lines += [summary["五项指标结论"], summary["样本数提示"],
            #           "对数法仅作为对照；综合判定采用全体相对偏离法。"]
            lines += [
                    summary["五项指标结论"],
                    summary["样本数提示"],
                    "随机不确定度采用相对偏离法计算。"]
            self.text.delete("1.0", "end")
            self.text.insert("end", "\n".join(lines))
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
            for child in self.figure_frame.winfo_children():
                child.destroy()
            canvas = FigureCanvasTkAgg(make_figure(self.result), master=self.figure_frame)
            canvas.draw()
            NavigationToolbar2Tk(canvas, self.figure_frame)
            canvas.get_tk_widget().pack(fill="both", expand=True)
            self.status.set(summary["五项指标结论"])
        except Exception as exc:
            self.result = None
            self.error(exc)

    def export(self):
        from tkinter import filedialog, messagebox
        if self.result is None:
            self.error("请先完成本次计算")
            return
        path = filedialog.askdirectory(parent=self.root, title="选择成果保存目录")
        if not path:
            return
        try:
            folder = export_result(self.result, Path(path), self.source)
            messagebox.showinfo("导出完成", str(folder), parent=self.root)
        except Exception as exc:
            self.error(exc)


def main():
    parser = argparse.ArgumentParser(description=f"{NAME} V{VERSION}")
    parser.add_argument("--input", type=Path, help="已有同期配对样本文件")
    parser.add_argument("--output", type=Path, default=Path("results"))
    parser.add_argument("--fixed", nargs=2, type=float, metavar=("A", "B"), help="按固定a、b复核")
    arguments = parser.parse_args()
    if arguments.input:
        try:
            settings = Settings()
            if arguments.fixed:
                settings.mode = "fixed"
                settings.param_a, settings.param_b = arguments.fixed
            data = read_data(arguments.input)
            result = analyze(data, settings)
            print(export_result(result, arguments.output, arguments.input))
            print(result["summary"]["五项指标结论"])
        except Exception as exc:
            parser.exit(1, f"计算失败：{exc}\n")
    else:
        import tkinter as tk
        root = tk.Tk()
        Application(root)
        root.mainloop()


if __name__ == "__main__":
    main()
