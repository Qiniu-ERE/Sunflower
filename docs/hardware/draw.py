"""生成太阳花实体设备的三张设计图：形象图 / 结构图 / 解构图（SVG）。比例：1 mm = 2 px。

    python3 docs/hardware/draw.py docs/hardware

PNG 由浏览器打开 SVG 截图得到（宽 1800）。
"""
import math
import pathlib
import sys

W, H = 1800, 1200
FONT = "PingFang SC, Hiragino Sans GB, Noto Sans CJK SC, Microsoft YaHei, sans-serif"
INK, SUB, LINE = "#3B3227", "#7A6E5D", "#B9AE9A"
YEL, YEL2, YELS = "#FFD54F", "#F2C230", "#D9A400"
ORA, ORAS = "#F6A33A", "#D9801A"
GRN, GRNS = "#8BC34A", "#5B8F2A"
POT, POTS = "#FFFDF7", "#CFC6B4"
SOIL = "#5D4E44"
out = []


def a(s):
    out.append(s)


def text(x, y, s, size=15.0, fill=INK, anchor="start", weight=400, extra=""):
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    a(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
      f'font-weight="{weight}" {extra}>{s}</text>')


def badge(x, y, n, r=11):
    a(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{INK}"/>')
    text(x, y + 4.5, n, 12.5, "#fff", "middle", 700)


def callout(n, lx, ly, px, py, label, side):
    """side='L'：标签在左，文字右对齐；'R'：标签在右。"""
    a(f'<polyline points="{lx + (14 if side == "L" else -14)},{ly} {px},{py}" fill="none" '
      f'stroke="{INK}" stroke-width="1"/>')
    a(f'<circle cx="{px}" cy="{py}" r="2.6" fill="{INK}"/>')
    badge(lx, ly, n)
    if side == "L":
        text(lx - 17, ly + 5, label, 14, INK, "end")
    else:
        text(lx + 17, ly + 5, label, 14, INK, "start")


def dim_v(x, y1, y2, label, side=1):
    a(f'<g stroke="{SUB}" stroke-width="1"><line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" '
      f'marker-start="url(#arr)" marker-end="url(#arr)"/></g>')
    ym = (y1 + y2) / 2
    w = len(label) * 9 + 12
    a(f'<rect x="{x - 10}" y="{ym - w / 2}" width="20" height="{w}" fill="#FBF8F0"/>')
    text(x, ym + 5, label, 13.5, SUB, "middle", 400, f'transform="rotate(-90 {x} {ym})"')


def dim_h(y, x1, x2, label):
    a(f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{SUB}" stroke-width="1" '
      f'marker-start="url(#arr)" marker-end="url(#arr)"/>')
    w = len(label) * 8 + 12
    a(f'<rect x="{(x1 + x2) / 2 - w / 2}" y="{y - 10}" width="{w}" height="18" fill="#FBF8F0"/>')
    text((x1 + x2) / 2, y + 5, label, 13.5, SUB, "middle")


def panel_title(x, y, t, sub=""):
    text(x, y, t, 19, INK, "start", 700)
    if sub:
        text(x, y + 22, sub, 13, SUB)


def petals(cx, cy):
    for layer, (rad, rx, ry, fill, off) in enumerate([(76, 15, 27, YEL2, 11.25), (73, 16, 26, YEL, 0)]):
        for i in range(16):
            ang = i * 22.5 + off
            px = cx + rad * math.sin(math.radians(ang))
            py = cy - rad * math.cos(math.radians(ang))
            a(f'<ellipse cx="{px:.1f}" cy="{py:.1f}" rx="{rx}" ry="{ry}" fill="{fill}" stroke="{YELS}" '
              f'stroke-width="1.2" transform="rotate({ang:.2f} {px:.1f} {py:.1f})"/>')
            if layer == 1:
                hx = cx + (rad + 8) * math.sin(math.radians(ang - 4))
                hy = cy - (rad + 8) * math.cos(math.radians(ang - 4))
                a(f'<ellipse cx="{hx:.1f}" cy="{hy:.1f}" rx="4" ry="8" fill="#FFF3C4" opacity=".7" '
                  f'transform="rotate({ang:.2f} {hx:.1f} {hy:.1f})"/>')


def ladybug(x, y, s=1.0):
    a(f'<g transform="translate({x},{y}) scale({s})">'
      f'<circle cx="-11" cy="2" r="5" fill="#2B2B2B"/>'
      f'<ellipse cx="0" cy="0" rx="12" ry="9" fill="#D7362F" stroke="#9E1F1A" stroke-width="1"/>'
      f'<line x1="-3" y1="-8.5" x2="-1" y2="8.5" stroke="#5A1410" stroke-width="1"/>'
      f'<circle cx="4" cy="-3" r="2" fill="#2B2B2B"/><circle cx="6" cy="4" r="1.8" fill="#2B2B2B"/>'
      f'<circle cx="-6" cy="3" r="1.8" fill="#2B2B2B"/>'
      f'<ellipse cx="3" cy="-5" rx="4" ry="2" fill="#fff" opacity=".45"/></g>')


def pot_path(cx, top=492, base=632):
    return (f"M{cx - 90},{top} C{cx - 108},{top + 25} {cx - 112},{base - 40} {cx - 68},{base} "
            f"L{cx + 68},{base} C{cx + 112},{base - 40} {cx + 108},{top + 25} {cx + 90},{top} Z")


def rot(px, py, cx, cy, deg):
    r = math.radians(deg)
    dx, dy = px - cx, py - cy
    return cx + dx * math.cos(r) - dy * math.sin(r), cy + dx * math.sin(r) + dy * math.cos(r)


def structure():
    out.clear()
    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
      f'font-family="{FONT}">')
    a('<defs>'
      f'<marker id="arr" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
      f'<path d="M0,1 L9,5 L0,9 z" fill="{SUB}"/></marker>'
      f'<marker id="arrI" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
      f'<path d="M0,1 L9,5 L0,9 z" fill="{INK}"/></marker>'
      f'<marker id="arrO" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
      f'<path d="M0,1 L9,5 L0,9 z" fill="{ORAS}"/></marker>'
      '<pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
      f'<rect width="6" height="6" fill="{POT}"/><line x1="0" y1="0" x2="0" y2="6" stroke="{POTS}" stroke-width="1.6"/></pattern>'
      '<pattern id="hatchD" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
      '<rect width="5" height="5" fill="#8A8F96"/><line x1="0" y1="0" x2="0" y2="5" stroke="#5E636A" stroke-width="1.5"/></pattern>'
      '<pattern id="grille" width="7" height="7" patternUnits="userSpaceOnUse">'
      f'<rect width="7" height="7" fill="{SOIL}"/><circle cx="3.5" cy="3.5" r="1.4" fill="#2E2621"/></pattern>'
      '<radialGradient id="face" cx="45%" cy="40%" r="65%"><stop offset="0" stop-color="#FFC56B"/>'
      '<stop offset="1" stop-color="#F29A2E"/></radialGradient>'
      '<linearGradient id="potg" x1="0" x2="1"><stop offset="0" stop-color="#F1EBDD"/><stop offset=".35" stop-color="#FFFFFF"/>'
      '<stop offset="1" stop-color="#E9E2D2"/></linearGradient>'
      '</defs>')
    a(f'<rect width="{W}" height="{H}" fill="#FBF8F0"/>')
    text(40, 52, "太阳花 Sunflower · 实体设备结构设计图", 30, INK, "start", 800)
    text(40, 82, "桌面语音编程伙伴：听声转向（4 麦阵列定位 + 单轴偏航）· 表情屏 · 花瓣状态灯 · 瓢虫说话键 —— 单位 mm，三视图 1 mm = 2 px", 15, SUB)
    text(1760, 52, "v0.1 概念结构", 15, SUB, "end", 600)
    text(1760, 76, "2026-10-23", 13, SUB, "end")
    a(f'<line x1="40" y1="100" x2="1760" y2="100" stroke="{LINE}"/>')

    # ---------------------------------------------------------------- A 正视图
    panel_title(40, 132, "A　正视图 · 外观")
    cx, cy = 300, 276
    a(f'<ellipse cx="{cx}" cy="644" rx="130" ry="10" fill="#E8E0CF"/>')
    a(f'<line x1="110" y1="640" x2="490" y2="640" stroke="{LINE}" stroke-width="1.5"/>')
    # 茎 + 叶
    a(f'<path d="M{cx - 11},492 C{cx - 10},430 {cx - 9},390 {cx - 8},350 L{cx + 8},350 C{cx + 9},390 {cx + 10},430 {cx + 11},492 Z" '
      f'fill="{GRN}" stroke="{GRNS}" stroke-width="1.4"/>')
    a(f'<path d="M{cx},476 C{cx - 30},446 {cx - 78},420 {cx - 112},426 C{cx - 86},454 {cx - 42},474 {cx},482 Z" '
      f'fill="{GRN}" stroke="{GRNS}" stroke-width="1.4"/>')
    a(f'<path d="M{cx - 6},474 C{cx - 40},452 {cx - 75},436 {cx - 100},430" fill="none" stroke="{GRNS}" stroke-width="1.2"/>')
    a(f'<path d="M{cx},468 C{cx + 32},440 {cx + 84},418 {cx + 116},422 C{cx + 94},450 {cx + 46},468 {cx},476 Z" '
      f'fill="{GRN}" stroke="{GRNS}" stroke-width="1.4"/>')
    a(f'<path d="M{cx + 6},466 C{cx + 42},446 {cx + 80},430 {cx + 104},426" fill="none" stroke="{GRNS}" stroke-width="1.2"/>')
    ladybug(cx + 82, 424)
    # 花盆
    a(f'<path d="{pot_path(cx)}" fill="url(#potg)" stroke="{POTS}" stroke-width="1.6"/>')
    a(f'<rect x="{cx - 50}" y="632" width="22" height="8" rx="3" fill="#B7B0A3"/>'
      f'<rect x="{cx + 28}" y="632" width="22" height="8" rx="3" fill="#B7B0A3"/>')
    a(f'<ellipse cx="{cx}" cy="492" rx="90" ry="12" fill="#F4EFE4" stroke="{POTS}" stroke-width="1.4"/>')
    a(f'<ellipse cx="{cx}" cy="494" rx="78" ry="8.5" fill="url(#grille)"/>')
    a(f'<rect x="{cx - 11}" y="480" width="22" height="14" fill="{GRN}"/>')
    # 偏航箭头
    a(f'<path d="M{cx - 30},396 A30 8 0 1 0 {cx + 30},396" fill="none" stroke="{ORAS}" stroke-width="2.2" '
      f'marker-end="url(#arrO)"/>')
    text(cx - 38, 392, "偏航 ±170°", 13, ORAS, "end", 700)
    # 花头
    petals(cx, cy)
    a(f'<circle cx="{cx}" cy="{cy}" r="56" fill="url(#face)" stroke="{ORAS}" stroke-width="1.5"/>')
    a(f'<circle cx="{cx}" cy="{cy}" r="33" fill="none" stroke="#E2882A" stroke-width="1.2" stroke-dasharray="3 3"/>')
    a(f'<circle cx="{cx - 14}" cy="{cy - 8}" r="5" fill="#6D2C1F"/><circle cx="{cx + 14}" cy="{cy - 8}" r="5" fill="#6D2C1F"/>'
      f'<circle cx="{cx - 12.5}" cy="{cy - 9.5}" r="1.5" fill="#fff"/><circle cx="{cx + 15.5}" cy="{cy - 9.5}" r="1.5" fill="#fff"/>')
    a(f'<path d="M{cx - 10},{cy + 8} Q{cx},{cy + 17} {cx + 10},{cy + 8}" fill="none" stroke="#6D2C1F" stroke-width="3" stroke-linecap="round"/>')
    a(f'<ellipse cx="{cx - 33}" cy="{cy + 14}" rx="10" ry="6.5" fill="#F0627E" opacity=".42"/>'
      f'<ellipse cx="{cx + 33}" cy="{cy + 14}" rx="10" ry="6.5" fill="#F0627E" opacity=".42"/>')
    # 尺寸
    a(f'<line x1="62" y1="171" x2="{cx}" y2="171" stroke="{LINE}" stroke-dasharray="2 3"/>')
    dim_v(70, 171, 640, "总高 ≈ 235")
    dim_h(150, cx - 105, cx + 105, "花头 Ø105")
    dim_h(668, cx - 100, cx + 100, "花盆 Ø100")
    a(f'<line x1="130" y1="492" x2="{cx - 92}" y2="492" stroke="{LINE}" stroke-dasharray="2 3"/>')
    dim_v(140, 492, 640, "75", -1)
    a(f'<line x1="96" y1="{cy}" x2="{cx - 106}" y2="{cy}" stroke="{LINE}" stroke-dasharray="2 3"/>')
    dim_v(104, cy, 640, "脸心 182", -1)
    # 正视图标注
    callout("1", 450, 214, cx + 48, cy - 30, "脸盖 Ø56", "R")
    callout("2", 450, 250, cx + 26, cy + 18, "圆屏 Ø32.4", "R")
    callout("7", 450, 392, cx + 86, 418, "说话键", "R")
    callout("8", 450, 520, cx + 52, 496, "声学格栅", "R")

    # ---------------------------------------------------------------- B 剖视图
    panel_title(560, 132, "B　A-A 侧剖视", "左 = 正面（朝向用户）")
    X = 880
    a(f'<ellipse cx="{X}" cy="644" rx="130" ry="10" fill="#E8E0CF"/>')
    a(f'<line x1="690" y1="640" x2="1070" y2="640" stroke="{LINE}" stroke-width="1.5"/>')
    # 偏航轴
    a(f'<line x1="{X}" y1="150" x2="{X}" y2="664" stroke="{ORAS}" stroke-width="1.2" stroke-dasharray="14 4 2 4"/>')
    text(X + 6, 162, "偏航轴", 13, ORAS, "start", 700)
    # 花盆壳（剖面线）+ 内腔
    a(f'<path d="{pot_path(X)}" fill="url(#hatch)" stroke="{POTS}" stroke-width="1.6"/>')
    a(f'<path d="M{X - 85},496 C{X - 101},520 {X - 105},{592} {X - 64},{624} L{X + 64},{624} '
      f'C{X + 105},592 {X + 101},520 {X + 85},496 Z" fill="#F3EEE3"/>')
    a(f'<rect x="{X - 50}" y="632" width="22" height="8" rx="3" fill="#B7B0A3"/>'
      f'<rect x="{X + 28}" y="632" width="22" height="8" rx="3" fill="#B7B0A3"/>')
    # 底部出声口
    a(f'<rect x="{X - 22}" y="624" width="44" height="8" fill="#F3EEE3"/>')
    for dx in (-16, -6, 4, 14):
        a(f'<path d="M{X + dx},634 l{dx * 0.6:.1f},10" stroke="{SUB}" stroke-width="1.2" marker-end="url(#arr)"/>')
    # 格栅盖 + 轴承
    a(f'<rect x="{X - 78}" y="494" width="156" height="7" fill="url(#grille)" stroke="#3A302A" stroke-width=".8"/>')
    a(f'<g stroke="#4A4F57" stroke-width="1"><rect x="{X - 19}" y="490" width="10" height="14" fill="#C9CDD3"/>'
      f'<rect x="{X + 9}" y="490" width="10" height="14" fill="#C9CDD3"/>'
      f'<path d="M{X - 19},490 l10,14 M{X - 9},490 l-10,14 M{X + 9},490 l10,14 M{X + 19},490 l-10,14"/></g>')
    # 麦克风环板
    a(f'<rect x="{X - 73}" y="512" width="59" height="6" fill="#2E7D4F" stroke="#1D5234"/>'
      f'<rect x="{X + 14}" y="512" width="59" height="6" fill="#2E7D4F" stroke="#1D5234"/>')
    for mx in (X - 62, X + 62):
        a(f'<rect x="{mx - 4}" y="507" width="8" height="5" fill="#222"/>')
        a(f'<line x1="{mx}" y1="507" x2="{mx}" y2="501" stroke="#222" stroke-width="1" stroke-dasharray="1.5 1.5"/>')
    a(f'<rect x="{X + 30}" y="518" width="16" height="4" fill="#333"/>')
    # 线缆盘绕
    a(f'<path d="M{X + 12},528 C{X + 30},522 {X + 52},524 {X + 50},532 C{X + 48},540 {X + 22},538 {X + 26},531 '
      f'C{X + 30},524 {X + 62},526 {X + 60},536 C{X + 58},546 {X + 34},544 {X + 40},538 C{X + 46},532 {X + 64},540 {X + 62},586" '
      f'fill="none" stroke="{ORA}" stroke-width="2"/>')
    # 挡销
    a(f'<rect x="{X - 32}" y="530" width="6" height="12" fill="#C62828"/>')
    # 电机 + 联轴法兰 + 编码器
    a(f'<rect x="{X - 18}" y="538" width="36" height="7" fill="#9AA0A8" stroke="#555"/>')
    a(f'<rect x="{X - 34}" y="545" width="68" height="28" rx="3" fill="#5F6670" stroke="#363B42"/>'
      f'<line x1="{X - 34}" y1="556" x2="{X + 34}" y2="556" stroke="#9AA0A8"/>'
      f'<rect x="{X - 4}" y="573" width="8" height="4" fill="#B0463A"/>'
      f'<rect x="{X - 20}" y="578" width="40" height="4" fill="#2E7D4F"/>')
    # 主板
    a(f'<rect x="{X - 66}" y="588" width="132" height="6" fill="#2E7D4F" stroke="#1D5234"/>')
    for bx, bw in ((-58, 18), (-34, 14), (20, 22), (46, 12)):
        a(f'<rect x="{X + bx}" y="583" width="{bw}" height="5" fill="#333"/>')
    # 配重 + 扬声器
    a(f'<rect x="{X - 64}" y="610" width="22" height="14" fill="url(#hatchD)"/><rect x="{X + 42}" y="610" width="22" height="14" fill="url(#hatchD)"/>')
    a(f'<path d="M{X - 36},600 L{X + 36},600 L{X + 22},624 L{X - 22},624 Z" fill="#444A52" stroke="#2A2E33"/>'
      f'<rect x="{X - 12}" y="598" width="24" height="6" fill="#2A2E33"/>')
    # USB-C
    a(f'<rect x="{X + 92}" y="600" width="12" height="9" rx="2" fill="#777"/>')
    # 茎（含线缆内腔）
    a(f'<rect x="{X - 12}" y="350" width="24" height="188" fill="{GRN}" stroke="{GRNS}" stroke-width="1.2"/>'
      f'<line x1="{X - 8}" y1="352" x2="{X - 8}" y2="536" stroke="{GRNS}" stroke-width=".8" stroke-dasharray="3 2"/>'
      f'<line x1="{X + 8}" y1="352" x2="{X + 8}" y2="536" stroke="{GRNS}" stroke-width=".8" stroke-dasharray="3 2"/>')
    a(f'<path d="M{X + 2},356 L{X + 2},526 Q{X + 2},530 {X + 12},528" fill="none" stroke="{ORA}" stroke-width="2"/>')
    # 叶（垂直纸面，虚线）
    a(f'<ellipse cx="{X}" cy="458" rx="40" ry="9" fill="none" stroke="{GRNS}" stroke-width="1.2" stroke-dasharray="4 3"/>')
    # 花头（绕中心仰 20°）
    C = (880, 276)
    a(f'<g transform="rotate(20 {C[0]} {C[1]})">')
    for y0, y1 in ((171, 224), (328, 381)):
        a(f'<rect x="858" y="{y0}" width="44" height="{y1 - y0}" rx="20" fill="{YEL}" fill-opacity=".85" stroke="{YELS}"/>')
    a(f'<rect x="864" y="214" width="44" height="124" rx="10" fill="url(#hatch)" stroke="{POTS}" stroke-width="1.4"/>'
      f'<rect x="868" y="222" width="34" height="108" rx="6" fill="#F3EEE3"/>')
    a(f'<path d="M852,220 h8 v23 h-8 z M852,309 h8 v23 h-8 z" fill="{ORA}" stroke="{ORAS}"/>'
      f'<rect x="852" y="243" width="3" height="66" fill="#CFE8FF" opacity=".8"/>')
    a(f'<rect x="858" y="238" width="8" height="76" fill="#1F2A44" stroke="#111"/>'
      f'<rect x="866" y="250" width="5" height="52" fill="#2E7D4F"/>')
    for ly in (196, 356):
        a(f'<rect x="866" y="{ly - 4}" width="8" height="8" fill="#FFB300" stroke="#C77800"/>'
          f'<rect x="874" y="{ly - 6}" width="3" height="12" fill="#2E7D4F"/>')
    a(f'<path d="M871,276 C882,290 888,320 888,338" fill="none" stroke="{ORA}" stroke-width="2"/>')
    a('</g>')
    # 颈座
    nx, ny = rot(888, 338, C[0], C[1], 20)
    a(f'<path d="M{X - 12},350 L{X + 12},350 L{nx + 8:.1f},{ny - 2:.1f} L{nx - 12:.1f},{ny - 10:.1f} Z" fill="#B9BFC7" stroke="#6E747C"/>')
    # 仰角标注
    fx, fy = rot(852, 276, C[0], C[1], 20)
    ex, ey = fx - 120 * math.cos(math.radians(20)), fy - 120 * math.sin(math.radians(20))
    a(f'<line x1="{fx:.1f}" y1="{fy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="{ORAS}" stroke-width="1.3" marker-end="url(#arrO)"/>')
    a(f'<line x1="{fx:.1f}" y1="{fy:.1f}" x2="{fx - 125:.1f}" y2="{fy:.1f}" stroke="{ORAS}" stroke-width="1" stroke-dasharray="4 3"/>')
    a(f'<path d="M{fx - 90:.1f},{fy:.1f} A90 90 0 0 1 {fx - 90 * math.cos(math.radians(20)):.1f},{fy - 90 * math.sin(math.radians(20)):.1f}" '
      f'fill="none" stroke="{ORAS}"/>')
    text(fx - 98, fy - 12, "仰 20°", 13.5, ORAS, "end", 700)

    # 剖视标注
    def P(px, py):
        return rot(px, py, C[0], C[1], 20)


    L, R = 690, 1010
    p1 = P(853, 228); p2 = P(862, 300); p3 = P(870, 356); p4 = P(905, 300)
    callout("1", L, 330, int(p1[0]), int(p1[1]), "脸盖", "L")
    callout("2", L, 362, int(p2[0]), int(p2[1]), "圆屏", "L")
    callout("3", R, 200, int(P(870, 196)[0]), int(P(870, 196)[1]), "花瓣灯环", "R")
    callout("4", R, 300, int(p4[0]), int(p4[1]), "头壳", "R")
    callout("5", L, 410, X - 12, 410, "花茎管（内走线）", "L")
    callout("6", L, 448, X - 38, 456, "叶片 ×2", "L")
    callout("8", L, 486, X - 70, 497, "声学格栅", "L")
    callout("9", R, 470, X + 16, 494, "轴承", "R")
    callout("10", L, 520, X - 62, 510, "4 麦环形阵列板", "L")
    callout("11", R, 512, X + 56, 534, "线缆盘绕 + 挡销", "R")
    callout("12", L, 556, X - 34, 560, "云台无刷电机", "L")
    callout("13", R, 556, X + 20, 580, "磁编码器", "R")
    callout("14", L, 592, X - 66, 591, "主板", "L")
    callout("15", L, 626, X - 30, 612, "扬声器（朝下）", "L")
    callout("16", R, 600, X + 56, 616, "配重", "R")
    callout("17", R, 640, X + 104, 604, "USB-C", "R")

    # ---------------------------------------------------------------- C 俯视 · 声源定位
    panel_title(1150, 132, "C　俯视 · 听声转向", "下 = 正前 0°；声源在 θ 时花头转到 θ")
    O = (1300, 318)
    a(f'<circle cx="{O[0]}" cy="{O[1]}" r="100" fill="url(#potg)" stroke="{POTS}" stroke-width="1.6"/>')
    a(f'<circle cx="{O[0]}" cy="{O[1]}" r="78" fill="url(#grille)"/>')
    a(f'<circle cx="{O[0]}" cy="{O[1]}" r="73" fill="none" stroke="#9FD3B1" stroke-width="1.2" stroke-dasharray="4 3"/>')
    a(f'<rect x="{O[0] - 44}" y="{O[1] - 44}" width="88" height="88" fill="none" stroke="#9FD3B1" stroke-width="1" stroke-dasharray="2 3"/>')
    th = 35
    # 花头俯视：虚线 = 0°，实线 = 转到 θ
    for deg, dash, op in ((0, 'stroke-dasharray="4 3"', ".35"), (th, "", "1")):
        a(f'<g transform="rotate({deg} {O[0]} {O[1]})" opacity="{op}">'
          f'<rect x="{O[0] - 105}" y="{O[1] - 28}" width="210" height="56" rx="24" fill="{YEL}" fill-opacity=".4" stroke="{YELS}" {dash}/>'
          f'<rect x="{O[0] - 56}" y="{O[1] + 18}" width="112" height="10" rx="4" fill="{ORA}" stroke="{ORAS}" {dash}/>'
          f'<circle cx="{O[0]}" cy="{O[1]}" r="12" fill="{GRN}" stroke="{GRNS}"/></g>')
    for i, ang in enumerate((225, 315, 45, 135)):
        mx = O[0] + 62 * math.cos(math.radians(ang)); my = O[1] + 62 * math.sin(math.radians(ang))
        a(f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="6" fill="#222" stroke="#9FD3B1" stroke-width="1.5"/>')
        lx = O[0] + 118 * math.cos(math.radians(ang)); ly = O[1] + 118 * math.sin(math.radians(ang))
        a(f'<line x1="{mx:.1f}" y1="{my:.1f}" x2="{lx:.1f}" y2="{ly:.1f}" stroke="#2E7D4F" stroke-width="1"/>')
        text(lx + (4 if math.cos(math.radians(ang)) > 0 else -4), ly + (14 if math.sin(math.radians(ang)) > 0 else -4),
             f"M{i + 1}", 13, "#2E7D4F", "start" if math.cos(math.radians(ang)) > 0 else "end", 700)
    text(O[0], O[1] - 52, "d = 44", 12, "#CDEBD7", "middle")
    # 0° 轴、声源
    a(f'<line x1="{O[0]}" y1="{O[1]}" x2="{O[0]}" y2="{O[1] + 190}" stroke="{SUB}" stroke-dasharray="5 4"/>')
    text(O[0] + 6, O[1] + 186, "0°", 13, SUB)
    sx = O[0] - 175 * math.sin(math.radians(th)); sy = O[1] + 175 * math.cos(math.radians(th))
    a(f'<line x1="{O[0]}" y1="{O[1]}" x2="{sx:.1f}" y2="{sy:.1f}" stroke="{ORAS}" stroke-width="1.4" stroke-dasharray="5 3"/>')
    for rr in (26, 40, 54):
        a(f'<path d="M{sx + rr * math.sin(math.radians(th + 40)):.1f},{sy - rr * math.cos(math.radians(th + 40)):.1f} '
          f'A{rr} {rr} 0 0 0 {sx + rr * math.sin(math.radians(th - 40)):.1f},{sy - rr * math.cos(math.radians(th - 40)):.1f}" '
          f'fill="none" stroke="{ORAS}" stroke-width="1.4" opacity=".75"/>')
    a(f'<circle cx="{sx:.1f}" cy="{sy + 4:.1f}" r="13" fill="#E7DCC6" stroke="{SUB}"/>'
      f'<circle cx="{sx:.1f}" cy="{sy + 4:.1f}" r="5" fill="{SUB}"/>')
    text(sx - 18, sy + 9, "说话人", 13, INK, "end", 700)
    a(f'<path d="M{O[0]},{O[1] + 120} A120 120 0 0 1 {O[0] - 120 * math.sin(math.radians(th)):.1f},{O[1] + 120 * math.cos(math.radians(th)):.1f}" '
      f'fill="none" stroke="{ORAS}" stroke-width="1.6" marker-end="url(#arrO)"/>')
    text(O[0] - 30, O[1] + 140, "θ", 17, ORAS, "middle", 800)
    # 挡销 ±170°
    for s in (-1, 1):
        bx = O[0] + s * 100 * math.sin(math.radians(10)); by = O[1] - 100 * math.cos(math.radians(10))
        a(f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="4" fill="#C62828"/>')
    text(O[0], O[1] - 110, "挡销：±170°（背后 20° 盲区）", 12.5, "#C62828", "middle", 600)

    # 定位/转向要点
    tx0 = 1470
    text(tx0, 186, "定位与转向规则", 16, INK, "start", 700)
    rules = [
        ("每 100 ms 读阵列 DOA θ 与语音能量", ""),
        ("语音段起始 300 ms 取 θ 中位数", "能量 / 置信度不够就不转"),
        ("|θ − φ| ≤ 10° 不动（死区防抖）", ""),
        ("S 曲线转到 θ：180° ≤ 0.8 s", "φ 由编码器给出"),
        ("转动中、TTS 播报中冻结 DOA", "防止自身噪声/回声误导"),
        ("θ 落在背后盲区 → 停在最近挡销", ""),
        ("最大时差 Δt = d / c ≈ 128 μs", "d < λ/2 → 无混叠上限 3.9 kHz"),
    ]
    yy = 214
    for i, (r1, r2) in enumerate(rules):
        badge(tx0 + 9, yy - 5, str(i + 1), 9)
        text(tx0 + 24, yy, r1, 13.5)
        if r2:
            yy += 19
            text(tx0 + 24, yy, r2, 12.5, SUB)
        yy += 27

    # ---------------------------------------------------------------- D 控制回路 + 系统链路
    panel_title(1150, 560, "D　转向闭环与系统链路")
    def box(x, y, w, h, t1, t2="", fill="#FFFFFF", stroke=LINE):
        a(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="1.3"/>')
        text(x + w / 2, y + (h / 2 + 5 if not t2 else h / 2 - 3), t1, 13.5, INK, "middle", 700)
        if t2:
            text(x + w / 2, y + h / 2 + 15, t2, 11.5, SUB, "middle")


    def arrow(x1, y1, x2, y2, label="", color=INK, dy=-6):
        a(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.4" marker-end="url(#arrI)"/>')
        if label:
            text((x1 + x2) / 2, (y1 + y2) / 2 + dy, label, 11.5, SUB, "middle")


    by = 590
    bw, bh, gap = 108, 48, 20
    xs = [1150 + i * (bw + gap) for i in range(5)]
    names = [("⑩ 4 麦阵列", "XVF3800 DSP"), ("DOA θ + VAD", "AEC / 降噪"), ("⑭ ESP32-S3", "死区 / 冻结"),
             ("FOC 驱动", "DRV8313"), ("⑫ 电机 → 花头", "")]
    for i, (n1, n2) in enumerate(names):
        box(xs[i], by, bw, bh, n1, n2, "#FFF8E5" if i in (2,) else "#FFFFFF")
        if i:
            arrow(xs[i - 1] + bw, by + bh / 2, xs[i] - 2, by + bh / 2)
    a(f'<path d="M{xs[4] + bw / 2},{by + bh} L{xs[4] + bw / 2},{by + bh + 26} L{xs[2] + bw / 2},{by + bh + 26} L{xs[2] + bw / 2},{by + bh + 3}" '
      f'fill="none" stroke="{INK}" stroke-width="1.4" marker-end="url(#arrI)"/>')
    text((xs[2] + xs[4]) / 2 + bw / 2, by + bh + 20, "⑬ 编码器回读角度 φ（绝对值，上电免归零）", 11.5, SUB, "middle")

    ly = 700
    box(1150, ly, 150, 56, "太阳花设备", "ESP32-S3 · 端侧 MCP", "#FFF8E5")
    box(1420, ly, 150, 56, "语音服务", "灵矽 ASR · LLM · TTS")
    box(1150, ly + 100, 150, 56, "主机 :8787", "Codex 执行 · 提交")
    box(1420, ly + 100, 150, 56, "任意浏览器", "进展上屏（SSE）")
    a(f'<line x1="1300" y1="{ly + 22}" x2="1418" y2="{ly + 22}" stroke="{INK}" stroke-width="1.4" marker-end="url(#arrI)"/>'
      f'<line x1="1420" y1="{ly + 36}" x2="1302" y2="{ly + 36}" stroke="{INK}" stroke-width="1.4" marker-end="url(#arrI)"/>')
    text(1360, ly + 16, "WebSocket", 11.5, SUB, "middle")
    text(1360, ly + 52, "语音 / 播报", 11.5, SUB, "middle")
    arrow(1225, ly + 56, 1225, ly + 98, "", INK)
    text(1232, ly + 82, "self.code.* → 局域网 HTTP", 11.5, SUB)
    arrow(1300, ly + 128, 1418, ly + 128, "SSE", INK)
    a(f'<rect x="1600" y="{ly}" width="160" height="156" rx="8" fill="#FFF3E0" stroke="{ORA}" stroke-dasharray="4 3"/>')
    for i, s in enumerate(["转向是本地反射：", "不经云端、不占工具", "调用 30 s 时限；", "本仓现有主机/面板", "代码不改，设备只", "替换 Mac 上的软设备"]):
        text(1612, ly + 24 + i * 22, s, 12.5, INK)

    # ---------------------------------------------------------------- E 状态表
    panel_title(1150, 900, "E　状态 → 表情 / 灯 / 动作", "对应主机 state 事件")
    cols = [1150, 1250, 1400, 1560]
    hdr = ["状态", "② 圆屏表情", "③ 花瓣灯", "动作"]
    rows = [("待机", "微笑、慢眨眼", "暖白呼吸 10%", "朝向上一位说话人"),
            ("聆听", "眼睛睁大", "黄色常亮", "按 θ 转向"),
            ("执行中", "思考眼 + 进度点", "顺时针流水", "保持不动"),
            ("完成", "眯眼笑 + 腮红", "绿色闪 2 次", "播报结果、点头"),
            ("出错", "皱眉", "橙红常亮", "播报下一步建议")]
    y0 = 942
    a(f'<rect x="1150" y="{y0}" width="610" height="26" fill="#EFE7D6"/>')
    for c, h in zip(cols, hdr):
        text(c + 8, y0 + 18, h, 13, INK, "start", 700)
    for i, r in enumerate(rows):
        yy = y0 + 26 + i * 30
        if i % 2:
            a(f'<rect x="1150" y="{yy}" width="610" height="30" fill="#F6F0E4"/>')
        for c, v in zip(cols, r):
            text(c + 8, yy + 20, v, 13, INK, "start", 700 if c == cols[0] else 400)
    text(1150, y0 + 26 + 5 * 30 + 22, "「点头」= 偏航 ±8° 往复一次（单轴实现，无需俯仰电机）", 12.5, SUB)

    # ---------------------------------------------------------------- 零件表 + 关键数字
    panel_title(40, 720, "零件表（标准版）", "屏显版只换花头（⑲–㉒），见解构图；外购件尺寸取自供应商页面，以实物 / 规格书为准")
    bom = [
        ("1", "脸盖", "橙色 PC，圆窗 Ø33，腮红移印"),
        ("2", "圆屏", "1.28″ GC9A01 240×240，可视 Ø32.4 / 外形 Ø37.5"),
        ("3", "花瓣灯环", "16 × WS2812B-2020，半透黄 PC 花瓣导光"),
        ("4", "头壳", "ABS，与颈座固定 20° 仰角"),
        ("5", "花茎管", "Ø12 / Ø8 铝管，内走 10 芯 AWG30（屏 SPI + 灯 + 按键）"),
        ("6", "叶片 ×2", "随花头一起转"),
        ("7", "瓢虫说话键", "轻触开关、竖直按压（不产生偏航力矩）"),
        ("8", "声学格栅（土面）", "Ø78 冲孔盖，麦克风与出线孔"),
        ("9", "轴承", "6800 深沟球 10×19×5，承受花头弯矩"),
        ("10", "4 麦环形阵列板", "麦间距 44 mm，中心过轴孔；XVF3800：DOA / AEC / 降噪"),
        ("11", "线缆盘绕 + 挡销", "±170° 限位，不用滑环"),
        ("12", "云台无刷电机", "2804 级，FOC 低噪声，避免步进噪声进麦"),
        ("13", "磁编码器", "AS5600 + 径向磁铁，绝对角度"),
        ("14", "主板", "ESP32-S3-N16R8 + MAX98357A 功放 + DRV8313 FOC 驱动"),
        ("15", "扬声器", "Ø40 4 Ω 3 W，朝下出声，脚垫留 8 mm 出声缝"),
        ("16", "配重 + 防滑垫", "钢环约 150 g，硅胶脚垫"),
        ("17", "USB-C 供电", "PD 取 12 V 给电机；DC-DC 降 5 V / 3.3 V"),
        ("18", "花盆壳体", "ABS 哑光白，Ø100 × 75，底部 4 颗螺丝开盖检修"),
    ]
    colx = [40, 590]
    for i, (n, name, spec) in enumerate(bom):
        cx0 = colx[0] if i < 9 else colx[1]
        yy = 770 + (i if i < 9 else i - 9) * 30
        badge(cx0 + 11, yy - 5, n, 10.5)
        text(cx0 + 28, yy, name, 13.5, INK, "start", 700)
        text(cx0 + 150, yy, spec, 13, SUB)

    ky = 1050
    a(f'<rect x="40" y="{ky - 12}" width="1090" height="96" rx="8" fill="#FFFFFF" stroke="{LINE}"/>')
    text(56, ky + 12, "关键数字（估算）", 14.5, INK, "start", 700)
    keys = [
        "仰角 20°：用户眼高 400、距离 600、脸心 182 → atan(218/600) ≈ 20°",
        "重心：花头+茎 ≈150 g @182，底座 ≈450 g @30 → 重心高 ≈ 68",
        "抗倾倒：底座半宽 50 → 倾覆角 atan(50/68) ≈ 36°",
        "最大时差 Δt ≈ 128 μs；16 kHz 采样 = 62.5 μs/点，需亚样本插值",
    ]
    for i, k in enumerate(keys):
        text(56 + (i % 2) * 545, ky + 40 + (i // 2) * 24, "· " + k, 12.8, INK)

    a('</svg>')
    return "\n".join(out)


# ============================================================ 共用部件（canonical 坐标：花头中心 (300,276)，1 mm = 2 px）
DEFS = ('<defs>'
        f'<marker id="arr" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M0,1 L9,5 L0,9 z" fill="{SUB}"/></marker>'
        f'<marker id="arrI" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
        f'<path d="M0,1 L9,5 L0,9 z" fill="{INK}"/></marker>'
        '<pattern id="grille" width="7" height="7" patternUnits="userSpaceOnUse">'
        f'<rect width="7" height="7" fill="{SOIL}"/><circle cx="3.5" cy="3.5" r="1.4" fill="#2E2621"/></pattern>'
        '<radialGradient id="face" cx="45%" cy="40%" r="65%"><stop offset="0" stop-color="#FFC56B"/>'
        '<stop offset="1" stop-color="#F29A2E"/></radialGradient>'
        '<linearGradient id="potg" x1="0" x2="1"><stop offset="0" stop-color="#F1EBDD"/><stop offset=".35" stop-color="#FFFFFF"/>'
        '<stop offset="1" stop-color="#E9E2D2"/></linearGradient>'
        '<linearGradient id="boxg" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#FFFFFF"/>'
        '<stop offset="1" stop-color="#ECE5D6"/></linearGradient>'
        '<linearGradient id="bg" x1="0" x2="1" y1="0" y2="1"><stop offset="0" stop-color="#FFF9EC"/>'
        '<stop offset="1" stop-color="#FBEFD5"/></linearGradient>'
        + "".join(f'<radialGradient id="glow{k}"><stop offset=".45" stop-color="{c}" stop-opacity=".55"/>'
                  f'<stop offset="1" stop-color="{c}" stop-opacity="0"/></radialGradient>'
                  for k, c in (("W", "#FFF4D6"), ("Y", "#FFD23F"), ("B", "#FFB300"), ("G", "#7BD389"), ("R", "#FF6B4A")))
        + '</defs>')

STATES = [("待机", "smile", "W", "暖白呼吸"), ("聆听", "listen", "Y", "黄色常亮"), ("执行中", "think", "B", "琥珀流水"),
          ("完成", "done", "G", "绿色闪烁"), ("出错", "error", "R", "橙红常亮")]


def face(cx, cy, expr="smile"):
    eye = "#6D2C1F"
    a(f'<circle cx="{cx}" cy="{cy}" r="56" fill="url(#face)" stroke="{ORAS}" stroke-width="1.5"/>')
    blush = {"done": .7, "error": .2}.get(expr, .42)
    a(f'<ellipse cx="{cx - 33}" cy="{cy + 14}" rx="10" ry="6.5" fill="#F0627E" opacity="{blush}"/>'
      f'<ellipse cx="{cx + 33}" cy="{cy + 14}" rx="10" ry="6.5" fill="#F0627E" opacity="{blush}"/>')
    if expr == "listen":
        for dx in (-14, 14):
            a(f'<circle cx="{cx + dx}" cy="{cy - 9}" r="7.5" fill="{eye}"/><circle cx="{cx + dx + 2.5}" cy="{cy - 12}" r="2.6" fill="#fff"/>')
        a(f'<ellipse cx="{cx}" cy="{cy + 13}" rx="5" ry="6" fill="{eye}"/>')
    elif expr == "think":
        for dx in (-14, 14):
            a(f'<circle cx="{cx + dx + 3}" cy="{cy - 12}" r="5" fill="{eye}"/><circle cx="{cx + dx + 4.5}" cy="{cy - 13.5}" r="1.5" fill="#fff"/>')
        a(f'<path d="M{cx - 7},{cy + 10} L{cx + 7},{cy + 10}" stroke="{eye}" stroke-width="3" stroke-linecap="round"/>')
        for i, op in enumerate((1, .6, .3)):
            a(f'<circle cx="{cx - 10 + i * 10}" cy="{cy + 24}" r="2.8" fill="{eye}" opacity="{op}"/>')
    elif expr == "done":
        for dx in (-14, 14):
            a(f'<path d="M{cx + dx - 6},{cy - 6} Q{cx + dx},{cy - 15} {cx + dx + 6},{cy - 6}" fill="none" stroke="{eye}" stroke-width="3" stroke-linecap="round"/>')
        a(f'<path d="M{cx - 13},{cy + 6} Q{cx},{cy + 22} {cx + 13},{cy + 6} Z" fill="{eye}"/>')
    elif expr == "error":
        for dx, s in ((-14, 1), (14, -1)):
            a(f'<circle cx="{cx + dx}" cy="{cy - 6}" r="4.5" fill="{eye}"/>'
              f'<path d="M{cx + dx - 7 * s},{cy - 20} L{cx + dx + 6 * s},{cy - 15}" stroke="{eye}" stroke-width="2.6" stroke-linecap="round"/>')
        a(f'<path d="M{cx - 10},{cy + 15} Q{cx},{cy + 7} {cx + 10},{cy + 15}" fill="none" stroke="{eye}" stroke-width="3" stroke-linecap="round"/>')
    else:
        for dx in (-14, 14):
            a(f'<circle cx="{cx + dx}" cy="{cy - 8}" r="5" fill="{eye}"/><circle cx="{cx + dx + 1.5}" cy="{cy - 9.5}" r="1.5" fill="#fff"/>')
        a(f'<path d="M{cx - 10},{cy + 8} Q{cx},{cy + 17} {cx + 10},{cy + 8}" fill="none" stroke="{eye}" stroke-width="3" stroke-linecap="round"/>')


def head(cx=300, cy=276, expr="smile", glow=None):
    if glow:
        a(f'<circle cx="{cx}" cy="{cy}" r="150" fill="url(#glow{glow})"/>')
    petals(cx, cy)
    face(cx, cy, expr)


def stem_leaves(cx=300, soil=492):
    a(f'<path d="M{cx - 11},{soil} C{cx - 10},430 {cx - 9},390 {cx - 8},350 L{cx + 8},350 C{cx + 9},390 {cx + 10},430 {cx + 11},{soil} Z" '
      f'fill="{GRN}" stroke="{GRNS}" stroke-width="1.4"/>')
    a(f'<path d="M{cx},476 C{cx - 30},446 {cx - 78},420 {cx - 112},426 C{cx - 86},454 {cx - 42},474 {cx},482 Z" '
      f'fill="{GRN}" stroke="{GRNS}" stroke-width="1.4"/>'
      f'<path d="M{cx - 6},474 C{cx - 40},452 {cx - 75},436 {cx - 100},430" fill="none" stroke="{GRNS}" stroke-width="1.2"/>')
    a(f'<path d="M{cx},468 C{cx + 32},440 {cx + 84},418 {cx + 116},422 C{cx + 94},450 {cx + 46},468 {cx},476 Z" '
      f'fill="{GRN}" stroke="{GRNS}" stroke-width="1.4"/>'
      f'<path d="M{cx + 6},466 C{cx + 42},446 {cx + 80},430 {cx + 104},426" fill="none" stroke="{GRNS}" stroke-width="1.2"/>')
    ladybug(cx + 82, 424)


def pot(cx=300):
    a(f'<path d="{pot_path(cx)}" fill="url(#potg)" stroke="{POTS}" stroke-width="1.6"/>')
    a(f'<rect x="{cx - 50}" y="632" width="22" height="8" rx="3" fill="#B7B0A3"/>'
      f'<rect x="{cx + 28}" y="632" width="22" height="8" rx="3" fill="#B7B0A3"/>')
    a(f'<ellipse cx="{cx}" cy="492" rx="90" ry="12" fill="#F4EFE4" stroke="{POTS}" stroke-width="1.4"/>')
    a(f'<ellipse cx="{cx}" cy="494" rx="78" ry="8.5" fill="url(#grille)"/>')


def screen_face(cx, cy, mode):
    """屏显版花芯：2.1″ 480×480 圆屏（可视 Ø53），平时显示表情，执行 / 完成 / 出错 / 听写时回显数据。"""
    if mode in ("smile", "listen", "think", "done", "error"):
        face(cx, cy, mode)
        a(f'<circle cx="{cx}" cy="{cy}" r="62" fill="none" stroke="{ORAS}" stroke-width="3"/>')
        return
    a(f'<circle cx="{cx}" cy="{cy}" r="62" fill="{ORA}" stroke="{ORAS}" stroke-width="2"/>')
    a(f'<circle cx="{cx}" cy="{cy}" r="53" fill="#1E2433"/>')
    ring = {"run": ("#FFB300", .68), "ok": ("#5CC879", 1.0), "fail": ("#FF6B4A", 1.0), "asr": ("#FFD23F", .25)}[mode]
    r = 48
    a(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#33405A" stroke-width="5"/>')
    if ring[1] >= 1:
        a(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{ring[0]}" stroke-width="5"/>')
    else:
        e = math.radians(360 * ring[1] - 90)
        a(f'<path d="M{cx},{cy - r} A{r} {r} 0 {1 if ring[1] > .5 else 0} 1 {cx + r * math.cos(e):.1f},{cy + r * math.sin(e):.1f}" '
          f'fill="none" stroke="{ring[0]}" stroke-width="5" stroke-linecap="round"/>')
    for dx in (-9, 9):  # 保留一对小眼睛，数据态也认得出是它
        a(f'<circle cx="{cx + dx}" cy="{cy - 26}" r="3" fill="#FFE3B3"/>')
    big, small = {"run": ("跑测试", "第 3 步 · 01:12"), "ok": ("✓ 6 通过", "voice: 3f2a1c9"),
                  "fail": ("✗ 2 失败", "说「修好它」"), "asr": ("加删除命令", "你说的话")}[mode]
    text(cx, cy + 6, big, 17, "#FFF6E0", "middle", 800)
    text(cx, cy + 25, small, 10.5, "#B9C3D6", "middle", 500)


def device(variant, cx=300, expr="smile", glow=None, mode=None):
    """整机正视（canonical 坐标，地面 y=640）。两种型号同一个花盆底座，屏显版只换花芯。"""
    stem_leaves(cx)
    pot(cx)
    if glow:
        a(f'<circle cx="{cx}" cy="276" r="150" fill="url(#glow{glow})"/>')
    petals(cx, 276)
    if variant == "std":
        face(cx, 276, expr)
    else:
        screen_face(cx, 276, mode or expr)


def disc(cx, cy, rx, ry, h, top, side, stroke="#555", hole=None, hole_fill="#FBF8F0"):
    a(f'<path d="M{cx - rx},{cy} L{cx - rx},{cy + h} A{rx} {ry} 0 0 0 {cx + rx},{cy + h} L{cx + rx},{cy} Z" '
      f'fill="{side}" stroke="{stroke}" stroke-width="1"/>')
    a(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{top}" stroke="{stroke}" stroke-width="1"/>')
    if hole:
        a(f'<ellipse cx="{cx}" cy="{cy}" rx="{hole}" ry="{hole * ry / rx:.1f}" fill="{hole_fill}" stroke="{stroke}" stroke-width=".8"/>')


def frame(title, subtitle, w=W, h=H):
    out.clear()
    a(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{w}" height="{h}" '
      f'viewBox="0 0 {w} {h}" font-family="{FONT}">')
    a(DEFS)
    a(f'<rect width="{w}" height="{h}" fill="url(#bg)"/>')
    text(40, 56, title, 32, INK, "start", 800)
    text(40, 88, subtitle, 15.5, SUB)
    text(w - 40, 56, "概念设计 v0.1", 15, SUB, "end", 600)
    text(w - 40, 80, "2026-10-23", 13, SUB, "end")
    a(f'<line x1="40" y1="106" x2="{w - 40}" y2="106" stroke="{LINE}"/>')


# ============================================================ 形象图
def hero():
    frame("太阳花 Sunflower · 桌面语音编程伙伴",
          "对着太阳花说一句话，Codex 就开始写代码；花面转向说话人，进展实时上屏，完成后语音播报 —— 两种型号同一个底座，屏显版只把花芯换成圆屏",
          h=1000)
    a('<rect x="40" y="846" width="900" height="6" rx="3" fill="#EADFC8"/>')
    for x, variant, kw in ((240, "std", {"expr": "listen", "glow": "Y"}), (690, "pro", {"mode": "run", "glow": "B"})):
        a(f'<g transform="translate({x},{840 - 490 * 1.1:.1f}) scale(1.1) translate(-300,-150)">')
        a('<ellipse cx="300" cy="645" rx="140" ry="11" fill="#E6D9BE"/>')
        device(variant, **kw)
        a('</g>')
    for x, name, sub in ((240, "标准版", "1.28″ 花芯只显示表情 · 进展投到任意浏览器 / 大屏"),
                         (690, "屏显版", "2.1″ 圆屏花芯 · 平时是脸，执行和完成时回显进展")):
        a(f'<rect x="{x - 105}" y="868" width="210" height="34" rx="17" fill="{INK}"/>')
        text(x, 891, name, 17, "#FFF8E5", "middle", 700)
        text(x, 928, sub, 14, SUB, "middle")
    x0 = 1010
    cards = [("听声转向", ["土面下 4 麦克风阵列定位说话人", "花面 0.8 s 内转过去，范围 ±170°"]),
             ("表情 + 花瓣灯", ["花瓣里藏 16 颗灯，脸上有五种表情", "Codex 在听、在做、做完、出错，一眼可知"]),
             ("瓢虫说话键", ["按一下开始说，再按一下结束", "不靠唤醒词，嘈杂工位也不误触发"]),
             ("花芯回显（屏显版）", ["屏幕跟着花面转，始终朝向你", "只放一眼能看完的：步骤、进度、结果"])]
    for i, (t, lines) in enumerate(cards):
        cx0, cy0 = x0 + (i % 2) * 380, 136 + (i // 2) * 140
        a(f'<rect x="{cx0}" y="{cy0}" width="360" height="122" rx="14" fill="#FFFFFF" stroke="#EADFC8"/>')
        a(f'<rect x="{cx0}" y="{cy0}" width="6" height="122" rx="3" fill="{ORA}"/>')
        text(cx0 + 22, cy0 + 36, t, 20, INK, "start", 800)
        for j, l in enumerate(lines):
            text(cx0 + 22, cy0 + 68 + j * 26, l, 14.5, SUB)
    text(x0, 452, "屏显版花芯：一次任务里的画面", 18, INK, "start", 800)
    seq = [("smile", "平时：花芯", "待机就是一张脸"), ("asr", "听写回显", "确认听对了再派"),
           ("run", "执行中", "进度环 + 当前步骤"), ("ok", "完成", "结果 + 提交号，5 s 后回到花芯")]
    for i, (mode, name, sub) in enumerate(seq):
        sx = x0 + 80 + i * 186
        a(f'<g transform="translate({sx},552) scale(.62) translate(-300,-276)">')
        petals(300, 276)
        screen_face(300, 276, mode)
        a('</g>')
        if i:
            a(f'<path d="M{sx - 118},552 l20,0" stroke="{SUB}" stroke-width="1.6" marker-end="url(#arrI)"/>')
        text(sx, 640, name, 15, INK, "middle", 700)
        text(sx, 660, sub, 12.5, SUB, "middle")
    text(x0, 712, "五种状态：表情 × 花瓣灯（两种型号相同）", 18, INK, "start", 800)
    for i, (name, expr, glow, light) in enumerate(STATES):
        sx = x0 + 70 + i * 150
        a(f'<g transform="translate({sx},800) scale(.44) translate(-300,-276)">')
        head(300, 276, expr, glow)
        a('</g>')
        text(sx, 878, name, 15, INK, "middle", 700)
        text(sx, 898, light, 12.5, SUB, "middle")
    text(x0, 948, "语音识别与合成由灵矽提供；编程交给 Codex（可切换渠道）；主机与面板代码两种型号通用。", 13.5, SUB)
    text(x0, 970, "外购件：GC9A01 1.28″ / ST7701S 2.1″ 圆屏 · XVF3800 4 麦阵列 · 2804 云台无刷电机 · ESP32-S3", 13, SUB)
    a('</svg>')
    return "\n".join(out)


# ============================================================ 解构图（爆炸图）
def exploded():
    frame("太阳花 Sunflower · 解构图",
          "左：标准版整机沿装配轴拆开（编号同结构图零件表）；右：屏显版只换花头 —— 花盆、转向、麦克风两种型号共用",
          h=1320)
    X = 430
    # ---- 花头：沿视线方向拆开（前 → 后）
    text(40, 140, "花头（沿视线方向，前 → 后）", 17, INK, "start", 800)
    a(f'<line x1="60" y1="290" x2="520" y2="290" stroke="{ORAS}" stroke-dasharray="10 4 2 4"/>')
    sx = .36
    parts = [(100, "1", "脸盖"), (175, "2", "圆屏"), (265, "3", "花瓣罩"), (352, "3", "灯环板"), (X, "4", "头壳")]
    for px, n, name in parts:
        a(f'<g transform="translate({px},290) scale({sx},.9) translate(-300,-276)">')
        if name == "脸盖":
            a(f'<circle cx="300" cy="276" r="56" fill="url(#face)" stroke="{ORAS}" stroke-width="3"/>'
              f'<circle cx="300" cy="276" r="33" fill="#FFF3DA" stroke="{ORAS}" stroke-width="3"/>'
              f'<ellipse cx="267" cy="290" rx="10" ry="6.5" fill="#F0627E" opacity=".45"/>'
              f'<ellipse cx="333" cy="290" rx="10" ry="6.5" fill="#F0627E" opacity=".45"/>')
        elif name == "圆屏":
            a(f'<circle cx="300" cy="276" r="37.5" fill="#1F2A44" stroke="#111" stroke-width="3"/>'
              f'<circle cx="300" cy="276" r="32.4" fill="#22335A"/>'
              f'<circle cx="286" cy="268" r="5" fill="#FFE3B3"/><circle cx="314" cy="268" r="5" fill="#FFE3B3"/>'
              f'<path d="M290,284 Q300,293 310,284" fill="none" stroke="#FFE3B3" stroke-width="3" stroke-linecap="round"/>'
              f'<rect x="292" y="312" width="16" height="40" fill="#C98A2B"/>')
        elif name == "花瓣罩":
            petals(300, 276)
            a('<circle cx="300" cy="276" r="54" fill="#FBF3E2" stroke="#D9A400" stroke-width="2"/>')
        elif name == "灯环板":
            a('<circle cx="300" cy="276" r="80" fill="none" stroke="#2E7D4F" stroke-width="16"/>')
            for i in range(16):
                ang = math.radians(i * 22.5)
                a(f'<rect x="{300 + 80 * math.sin(ang) - 5:.1f}" y="{276 - 80 * math.cos(ang) - 5:.1f}" width="10" height="10" fill="#FFC21A" stroke="#B37700"/>')
        else:
            a(f'<circle cx="300" cy="276" r="96" fill="#FFFFFF" stroke="{POTS}" stroke-width="3"/>'
              f'<circle cx="300" cy="276" r="84" fill="#F3EEE3" stroke="{POTS}" stroke-width="2"/>'
              f'<rect x="286" y="364" width="28" height="30" rx="4" fill="#B9BFC7" stroke="#6E747C" stroke-width="2"/>')
        a('</g>')
        badge(px, 160, n, 10.5)
        text(px, 186, name, 13.5, INK, "middle", 700)
    text(X + 40, 392, "颈座：固定 20° 仰角", 12.5, SUB)
    # ---- 花茎与叶
    a(f'<line x1="{X}" y1="368" x2="{X}" y2="1270" stroke="{ORAS}" stroke-dasharray="14 4 2 4"/>')
    a(f'<g transform="translate({X - 300},68)">')
    stem_leaves(300)
    a('</g>')
    # ---- 底座：沿偏航轴自上而下
    y = {}
    y["8"] = 620; disc(X, 620, 78, 22, 6, "url(#grille)", "#3A302A", "#2E2621", hole=10)
    y["9"] = 672; disc(X, 672, 19, 6, 10, "#C9CDD3", "#9AA0A8", "#4A4F57", hole=10)
    y["10"] = 722; disc(X, 722, 73, 20, 5, "#2E7D4F", "#1D5234", "#174429", hole=10)
    for ang in (45, 135, 225, 315):
        mx = X + 52 * math.cos(math.radians(ang)); my = 722 + 52 * 20 / 73 * math.sin(math.radians(ang))
        a(f'<ellipse cx="{mx:.1f}" cy="{my:.1f}" rx="5" ry="2.6" fill="#111"/>')
    a(f'<rect x="{X + 22}" y="714" width="16" height="8" fill="#222" transform="skewX(-30)" transform-origin="{X + 30} 718"/>')
    y["11"] = 778
    for rx, ry in ((32, 9), (25, 7), (18, 5)):
        a(f'<ellipse cx="{X}" cy="778" rx="{rx}" ry="{ry}" fill="none" stroke="{ORA}" stroke-width="2.4"/>')
    a(f'<rect x="{X - 56}" y="768" width="7" height="16" fill="#C62828"/>')
    y["12"] = 832; disc(X, 832, 34, 10, 28, "#7A818A", "#5F6670", "#363B42")
    disc(X, 826, 18, 5, 6, "#B0B6BD", "#9AA0A8", "#555")
    y["13"] = 896; disc(X, 896, 20, 6, 3, "#2E7D4F", "#1D5234", "#174429")
    a(f'<ellipse cx="{X}" cy="890" rx="5" ry="2" fill="#B0463A"/>')
    y["14"] = 944; disc(X, 944, 66, 19, 4, "#2E7D4F", "#1D5234", "#174429")
    for bx, by, bw, bh, c in ((-40, -8, 26, 12, "#C9CDD3"), (-6, -4, 12, 8, "#222"), (14, -10, 16, 9, "#222"), (36, -2, 10, 6, "#222")):
        a(f'<rect x="{X + bx}" y="{944 + by}" width="{bw}" height="{bh}" fill="{c}" stroke="#111" stroke-width=".6"/>')
    y["15"] = 1002; disc(X, 1002, 40, 11, 4, "#444A52", "#2A2E33", "#222")
    a(f'<path d="M{X - 40},1006 L{X - 16},1026 L{X + 16},1026 L{X + 40},1006 Z" fill="#2A2E33"/>')
    y["16"] = 1062; disc(X, 1062, 62, 17, 12, "#8A8F96", "#5E636A", "#4A4F57", hole=44)
    y["18"] = 1170
    a(f'<g transform="translate({X - 300},618)">')
    a(f'<path d="{pot_path(300)}" fill="url(#potg)" stroke="{POTS}" stroke-width="1.6"/>')
    a(f'<ellipse cx="300" cy="492" rx="90" ry="12" fill="#E7E0D2" stroke="{POTS}" stroke-width="1.4"/>'
      f'<ellipse cx="300" cy="494" rx="84" ry="9" fill="#D8D0C0"/>')
    a('<rect x="250" y="632" width="22" height="8" rx="3" fill="#B7B0A3"/><rect x="328" y="632" width="22" height="8" rx="3" fill="#B7B0A3"/>')
    a('<rect x="392" y="580" width="12" height="9" rx="2" fill="#777"/>')
    a('</g>')
    y["17"] = 1202
    labels = [("5", 440, X + 8, 440, "花茎管（内走 10 芯线）"), ("6", 524, X + 70, 524, "叶片 ×2"),
              ("7", 482, X + 92, 488, "瓢虫说话键"),
              ("8", 612, X + 78, 620, "声学格栅 Ø78"), ("9", 664, X + 19, 672, "轴承 6800"),
              ("10", 714, X + 73, 722, "4 麦环形阵列板（XVF3800）"), ("11", 772, X + 32, 778, "线缆盘绕 + 挡销 ±170°"),
              ("12", 836, X + 34, 840, "云台无刷电机 2804"), ("13", 892, X + 20, 896, "磁编码器 AS5600"),
              ("14", 940, X + 66, 944, "主板 ESP32-S3 + 功放 + FOC"), ("15", 1004, X + 40, 1004, "扬声器 Ø40，朝下"),
              ("16", 1062, X + 62, 1066, "配重钢环 ≈150 g"), ("17", 1206, X + 104, 1202, "USB-C 供电"),
              ("18", 1150, X + 96, 1150, "花盆壳体")]
    for n, ly, px, py, lab in labels:
        callout(n, 660, ly, px, py, lab, "R")
    text(60, 600, "底座（沿偏航轴，上 → 下）", 17, INK, "start", 800)
    a(f'<line x1="1000" y1="130" x2="1000" y2="1290" stroke="{LINE}"/>')

    # ---- 右：屏显版花头
    R0 = 1040
    text(R0, 140, "屏显版：只换花头（沿视线方向，前 → 后）", 17, INK, "start", 800)
    a(f'<line x1="{R0 + 20}" y1="290" x2="1740" y2="290" stroke="{ORAS}" stroke-dasharray="10 4 2 4"/>')
    pro = [(1090, "20", "透明面罩"), (1185, "19", "2.1″ 圆屏"), (1300, "3", "花瓣罩"), (1405, "3", "灯环板"),
           (1505, "21", "花头主控"), (1610, "4", "头壳")]
    for px, n, name in pro:
        a(f'<g transform="translate({px},290) scale(.36,.9) translate(-300,-276)">')
        if name == "透明面罩":
            a(f'<circle cx="300" cy="276" r="62" fill="#EAF4FF" fill-opacity=".55" stroke="{ORAS}" stroke-width="6"/>')
        elif name == "2.1″ 圆屏":
            a('<rect x="270" y="210" width="60" height="140" fill="none"/>')
            screen_face(300, 276, "run")
            a('<rect x="290" y="336" width="20" height="44" fill="#C98A2B"/>')
        elif name == "花瓣罩":
            petals(300, 276)
            a('<circle cx="300" cy="276" r="60" fill="#FBF3E2" stroke="#D9A400" stroke-width="2"/>')
        elif name == "灯环板":
            a('<circle cx="300" cy="276" r="80" fill="none" stroke="#2E7D4F" stroke-width="16"/>')
            for k in range(16):
                ang = math.radians(k * 22.5)
                a(f'<rect x="{300 + 80 * math.sin(ang) - 5:.1f}" y="{276 - 80 * math.cos(ang) - 5:.1f}" width="10" height="10" fill="#FFC21A" stroke="#B37700"/>')
        elif name == "花头主控":
            a('<circle cx="300" cy="276" r="58" fill="#2E7D4F" stroke="#174429" stroke-width="3"/>'
              '<rect x="262" y="236" width="76" height="56" rx="4" fill="#C9CDD3" stroke="#555" stroke-width="2"/>'
              '<rect x="278" y="304" width="44" height="18" fill="#222"/>')
        else:
            a(f'<circle cx="300" cy="276" r="96" fill="#FFFFFF" stroke="{POTS}" stroke-width="3"/>'
              f'<circle cx="300" cy="276" r="84" fill="#F3EEE3" stroke="{POTS}" stroke-width="2"/>'
              f'<rect x="286" y="364" width="28" height="30" rx="4" fill="#B9BFC7" stroke="#6E747C" stroke-width="2"/>')
        a('</g>')
        badge(px, 160, n, 10.5)
        text(px, 186, name, 13.5, INK, "middle", 700)
    # 过关节走线对比
    text(R0, 430, "过关节走线：屏显版反而更少", 16, INK, "start", 800)
    for k, (title, wires, note) in enumerate((("标准版 10 芯", ["SPI × 4", "背光", "灯 DIN", "按键 × 2", "电源 × 2"], "底座主控直接驱动 1.28″ 屏（CS 接地）"),
                                              ("屏显版 4 芯 ㉒", ["5 V", "GND", "按键 × 2"], "屏幕数据走花头自己的 Wi-Fi"))):
        y0 = 456 + k * 92
        text(R0, y0 + 20, title, 14, INK, "start", 700)
        for w, lab in enumerate(wires):
            a(f'<rect x="{R0 + 130 + w * 92}" y="{y0 + 4}" width="84" height="24" rx="12" fill="{"#FFF3E0" if k else "#FFFFFF"}" stroke="{ORA if k else LINE}"/>')
            text(R0 + 172 + w * 92, y0 + 21, lab, 12.5, INK, "middle")
        text(R0 + 130, y0 + 50, note, 12.5, SUB)
    # 数据链路
    text(R0, 660, "花芯回显的数据链路", 16, INK, "start", 800)
    chain = [("主机 :8787", "SSE /events"), ("花头 ESP32-S3", "Wi-Fi 直连"), ("RGB 并口", "ST7701S"), ("2.1″ 圆屏", "480 × 480")]
    for k, (t1, t2) in enumerate(chain):
        bx0 = R0 + k * 180
        a(f'<rect x="{bx0}" y="680" width="150" height="54" rx="8" fill="{"#FFF8E5" if k == 1 else "#FFFFFF"}" stroke="{LINE}" stroke-width="1.3"/>')
        text(bx0 + 75, 703, t1, 13.5, INK, "middle", 700)
        text(bx0 + 75, 722, t2, 11.5, SUB, "middle")
        if k:
            a(f'<line x1="{bx0 - 30}" y1="707" x2="{bx0 - 2}" y2="707" stroke="{INK}" stroke-width="1.4" marker-end="url(#arrI)"/>')
    text(R0, 768, "订阅的是面板同一路事件流，只取 state / announce 等少数字段；完整日志仍在浏览器面板里看。", 13, SUB)
    rl = [("19", "2.1″ 480×480 圆形 IPS，ST7701S，RGB 并口（可视 Ø53）"),
          ("20", "透明面罩：PC 镜片 + 橙色边圈，脸盖 Ø56 → Ø62"),
          ("21", "花头主控 ESP32-S3-N8R8：驱动圆屏，Wi-Fi 订阅主机事件"),
          ("22", "过关节 4 芯：5 V、GND、按键 × 2")]
    for k, (n, lab) in enumerate(rl):
        lyy = 812 + k * 26
        badge(R0 + 10, lyy - 5, n, 10)
        text(R0 + 26, lyy, lab, 13.5, INK)
    # ---- 型号对比
    ty = 950
    text(R0, ty, "型号对比", 17, INK, "start", 800)
    rows = [("", "标准版", "屏显版"),
            ("花芯", "1.28″ 240×240，只显示表情", "2.1″ 480×480：平时是脸，执行和完成时回显"),
            ("进展显示", "任意浏览器 / 投大屏", "花芯一眼可看，另外照样可投大屏"),
            ("主控", "底座 ESP32-S3", "底座 ESP32-S3 + 花头 ESP32-S3"),
            ("过关节", "10 芯", "4 芯"),
            ("尺寸 / 供电", "Ø105 × 235 mm · USB-C PD 12 V", "同标准版")]
    for k, r in enumerate(rows):
        yy = ty + 16 + k * 44
        if k == 0:
            a(f'<rect x="{R0}" y="{yy}" width="720" height="40" rx="6" fill="#EFE7D6"/>')
        elif k % 2 == 0:
            a(f'<rect x="{R0}" y="{yy}" width="720" height="40" fill="#F6F0E4"/>')
        for c, v in zip((R0 + 12, R0 + 112, R0 + 352), r):
            text(c, yy + 26, v, 14, INK, "start", 700 if (k == 0 or c == R0 + 12) else 400)
    a('</svg>')
    return "\n".join(out)


if __name__ == "__main__":
    outdir = pathlib.Path(sys.argv[1])
    (outdir / "device-structure.svg").write_text(structure(), encoding="utf-8")
    (outdir / "device-hero.svg").write_text(hero(), encoding="utf-8")
    (outdir / "device-exploded.svg").write_text(exploded(), encoding="utf-8")
