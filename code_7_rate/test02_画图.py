import math
import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = ['SimHei']   # 中文显示
plt.rcParams['axes.unicode_minus'] = False

# ==========================================================
# 数据：Stage 1（中高流速组，17个点）
# ==========================================================
vr_1 = [
    0.0043
    , -0.0068
    , 0.2067
    , 0.2529
    , 0.0037
    , 0.072
    , 0.0234
    , 0.0125
    , 0.3437
    , 0.0103
    , 0.2263
    , 0.0858
    , -0.0029
    , 0.1822
    , 0.4467
    , 0.6298
    , 0.565
    , 0.481
    , 0.5761
    , 0.5996
    , 0.79
    , 0.7948
    , 0.8326
    , 0.9739
    , 1.0329
    , 1.1154
    , 0.8725
    , 1.2214
    , 0.9425
    , 1.1853
]
vbar_1 = [
    0.047
    , 0.039
    , 0.2206
    , 0.2801
    , 0.051
    , 0.1103
    , 0.07
    , 0.057
    , 0.3542
    , 0.05
    , 0.2394
    , 0.1298
    , 0.041
    , 0.22
    , 0.4188
    , 0.638
    , 0.6295
    , 0.52
    , 0.56
    , 0.6393
    , 0.8271
    , 0.828
    , 0.8262
    , 0.9264
    , 1.0469
    , 1.1263
    , 0.827
    , 1.1784
    , 0.9781
    , 1.098

]

# ==========================================================
# 数据：Stage 2（低流速组，14个点）
# ==========================================================
vr_2 = [

]
vbar_2 = [

]

# 合并全部数据用于拟合
vr_all   = vr_1 + vr_2
vbar_all = vbar_1 + vbar_2
n = len(vr_all)

# ==========================================================
# 最小二乘拟合（保留你原来的手写计算逻辑）
# ==========================================================
sum_x  = sum(vr_all)
sum_y  = sum(vbar_all)
sum_x2 = sum(x * x for x in vr_all)
sum_xy = sum(x * y for x, y in zip(vr_all, vbar_all))
denom  = n * sum_x2 - sum_x * sum_x

if 1:
    a = (n * sum_xy - sum_x * sum_y) / denom
    # a=round(a,4)
    b = (sum_x2 * sum_y - sum_x * sum_xy) / denom
    # b=round(b,4)
else:
    a=0.945132
    b=0.045723


# 误差指标
sse    = sum((y - (a * x + b)) ** 2 for x, y in zip(vr_all, vbar_all))
rmse   = math.sqrt(sse / n)
mae    = sum(abs(y - (a * x + b)) for x, y in zip(vr_all, vbar_all)) / n
mean_y = sum_y / n
sst    = sum((y - mean_y) ** 2 for y in vbar_all)
r2     = 1 - sse / sst
r      = math.sqrt(r2)   # 两变量同为正方向，相关系数取正

print(f"Vbar = {a:.6f}*Vr + {b:.6f}   R²={r2:.3f}  RMSE={rmse:.4f}  MAE={mae:.4f}")

# ==========================================================
# 绘图
# ==========================================================
fig, ax = fig, ax = plt.subplots(figsize=(10, 6.5))


if 0:
    # ---- 1:1 参考线 ----
    lims = [-0.1, 0.95]
    ax.plot(lims, lims, 'k:', lw=1, label='1:1 line', zorder=1)

# ---- 两阶段散点 ----
ax.scatter(vr_1, vbar_1, c='tab:blue', marker='o', s=45,
           edgecolors='k', linewidths=0.5, label=f'有效数据点(n={len(vbar_1)})', zorder=3)
# ax.scatter(vr_2, vbar_2, c='tab:orange', marker='^', s=55,
#            edgecolors='k', linewidths=0.5, label='7月23日至8月5日样本(n=14)', zorder=3)



max_value = max(max(vr_all), max(vbar_all))
upper_limit = math.ceil(max_value * 10) / 10 + 0.1





# ---- 合并拟合直线 ----
import numpy as np
# xx = np.linspace(-0.1, 0.9, 100)
# xx = np.linspace(-0.1, 1.3, 100)
xx = np.linspace(-0.1, upper_limit, 100)

# ax.plot(xx, a * xx + b, color='teal', lw=2,
#         label=f'统一关系: Vbar={a:.3f}Vr+{b:.3f}', zorder=2)

ax.plot(xx, a * xx + b, color='teal', lw=2,
        label=rf'率定关系: $V^-={a:.4f}V_r+{b:.4f}$', zorder=2)


# ---- 低流速低分辨率阴影区 |Vr| < 0.06 ----
ax.axvspan(-0.06, 0.06, color='gray', alpha=0.15, zorder=0)
# if 0:
#     ax.text(0, -0.055, '|Vr| < 0.06 m/s: nominal low-resolution zone',
#             ha='center', fontsize=8, color='dimgray')
# else:
#     # ---- 定量应用建议：在阴影边界画一条竖线并标注 ----
#     ax.axvline(0.06, label='应用建议: 仅当 |Vr| ≥ 0.06 m/s 时使用拟合式')


if 0:
    # ---- 统计信息框 ----
    stats = (f'N={n}  r={r:.3f}  R²={r2:.3f}\n'
             f'RMSE={rmse:.4f} m/s  MAE={mae:.4f} m/s')
    ax.text(0.98, 0.97, stats, transform=ax.transAxes,
            ha='right', va='top', fontsize=10,
            bbox=dict(boxstyle='round', fc='white', ec='gray'))

# ---- 坐标轴 ----
ax.set_xlabel('侧扫雷达水面平均流速 Vr (m/s)', fontsize=11)
ax.set_ylabel(r'断面平均流速 $V^{-}$(m/s)', fontsize=11)
ax.set_title('泗洪（金锁）水文站侧扫雷达水面平均流速与断面平均流速关系',fontsize=13)
# ax.set_xlim(-0.1, 0.95)
# ax.set_ylim(-0.1, 0.9)
# ax.set_xlim(-0.1, 1.3)
# ax.set_ylim(-0.1, 1.3)
ax.set_xlim(-0.1, upper_limit)
ax.set_ylim(-0.1, upper_limit)
ax.legend(loc='upper left', fontsize=9, framealpha=0.9)
ax.grid(True, ls='--', alpha=0.3)

if 0:
    # ==========================================================
    # 插图：Stage 2 低流速放大
    # ==========================================================
    ax_in = ax.inset_axes([0.58, 0.05, 0.38, 0.35])   # [x, y, w, h] 比例

    ax_in.axvspan(-0.06, 0.06, color='gray', alpha=0.15)
    ax_in.scatter(vr_2, vbar_2, c='tab:orange', marker='^', s=40,
                  edgecolors='k', linewidths=0.5, zorder=3)
    ax_in.plot(xx, a * xx + b, color='tab:red', lw=1.8,
               label=f'Vbar={a:.3f}Vr+{b:.3f}')
    ax_in.axhline(0, color='k', lw=0.8)
    ax_in.axvline(0, color='k', lw=0.8)

    ax_in.set_xlim(-0.03, 0.20)
    ax_in.set_ylim(-0.06, 0.24)
    ax_in.set_title('Stage 2 low-flow detail', fontsize=9)
    ax_in.tick_params(labelsize=7)
    ax_in.legend(fontsize=7, loc='lower right')
    ax_in.grid(True, ls='--', alpha=0.3)

    # 用指示线把插图对应区域和主图阴影区连接起来
    ax.indicate_inset_zoom(ax_in, edgecolor='gray', alpha=0.7)

plt.tight_layout()
plt.savefig('jinsuo_calibration.png', dpi=200, bbox_inches='tight')
plt.show()
