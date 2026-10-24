"""太阳花 3D 打印原型：生成两种型号的打印件 STL、装配检查报告和效果图场景。单位 mm，1:1。

    python3 -m venv .cad && .cad/bin/pip install manifold3d                      # 只有重新生成时需要
    .cad/bin/python docs/hardware/print/model.py docs/hardware/print             # 写 stl/ 和 check.md
    .cad/bin/python docs/hardware/print/model.py docs/hardware/print --scene DIR # 另写效果图场景（render.swift 读）

世界坐标：Z 向上，原点在桌面、偏航轴上，正面朝 -Y。花头在自己的局部坐标里建模：脸朝 +Z，
花瓣环前表面 z = 0；装配时绕 X 转 70°（脸朝前并上仰 20°），再平移到脸心高 182。
尺寸取自 ../README.md 与 ../draw.py；外购件里没核实的尺寸都集中在 BUY，改那里再重跑。
"""
import json
import math
import pathlib
import sys

import numpy as np
from manifold3d import CrossSection, FillRule, Manifold, OpType

TILT, FACE_Z = 20, 182          # 花头上仰角、脸心高
POT_BOT, POT_TOP, WALL = 11, 75, 2.4  # 花盆壳体底 / 口沿高度（底板 3 + 脚 8 在下面）、壁厚
DECK_Z = 69                     # 土面格栅底面高度（格栅厚 3，顶面比口沿低 3）
PLATE_Z0, PLATE_Z1 = -9, -4     # 花头前框在局部 z 上的范围（前面贴花瓣环背面）
LED_R, PIN_R = 39, 36           # 灯珠圆、定位销圆
C0 = (0.0, -10.0, -20.0)        # 颈座轴线经过的点（花头局部坐标）
FIT = 0.2                       # 插配单边间隙
BUY = {  # 外购件尺寸：来源见 ../README.md「尺寸来源」，标 * 的是占位、要按实物核对
    "stem": (12.0, 8.0),        # 花茎铝管外径 / 内径
    "bearing": (12.0, 21.0, 5.0),  # 6801ZZ
    "gc9a01": (37.5, 3.0),      # 1.28″ 模块外径、* 厚度
    "st7701s": (58.18, 60.71, 20.0, 3.0),  # 2.1″ 外形宽、高、* 排线引出处宽、* 厚度
    "lens": (56.0, 1.0),        # * 屏显版透明面罩：亚克力圆片
    "led": (10.0, 2.5),         # * WS2812B 单颗圆形小板
    "switch": (6.0, 3.5, 3.5),  # * 6×6 轻触开关：边长、本体高、按柱直径
    "speaker": (40.0, 15.0),    # Ø40 扬声器、* 高度
}
VARIANTS = {
    "standard": {"name": "标准版", "face_r": 28.0, "body_r": 27.0, "window_r": 16.5, "lens": False, "depth": 20},
    "screen": {"name": "屏显版", "face_r": 31.0, "body_r": 30.0, "window_r": 27.0, "lens": True, "depth": 28},
}


def cyl(r, h, z0=0.0, seg=96, r2=None):
    return Manifold.cylinder(h, r, r if r2 is None else r2, seg).translate((0, 0, z0))


def ring(r_out, r_in, h, z0=0.0, seg=96):
    return cyl(r_out, h, z0, seg) - cyl(r_in, h + 2, z0 - 1, seg)


def union(parts):
    return Manifold.batch_boolean(list(parts), OpType.Add)


def polar(r, deg):
    return r * math.sin(math.radians(deg)), r * math.cos(math.radians(deg))  # 0° 朝 +Y，顺时针


def at(m, r, deg, z=0.0):
    x, y = polar(r, deg)
    return m.translate((x, y, z))


def poly(pts):
    return CrossSection([list(pts)], FillRule.NonZero)  # 轮廓顺逆时针都算实体


def ellipse(cx, cy, rx, ry, deg, n=40):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    pts = [(rx * math.cos(2 * math.pi * i / n), ry * math.sin(2 * math.pi * i / n)) for i in range(n)]
    return [(cx + x * c - y * s, cy + x * s + y * c) for x, y in pts]


def rounded_slot(w, h, length):
    """横截面 w×h（h 方向两端半圆）、沿 Y 方向长 length 的长条孔。"""
    body = Manifold.cube((w - h, length, h), center=True)
    end = Manifold.cylinder(length, h / 2, h / 2, 24, True).rotate((90, 0, 0))
    return union([body, end.translate(((w - h) / 2, 0, 0)), end.translate((-(w - h) / 2, 0, 0))])


def hex_holes(r_hole, pitch, r_min, r_max, h, z0):
    holes = []
    for j in range(-40, 41):
        y = j * pitch * math.sqrt(3) / 2
        for i in range(-40, 41):
            x = i * pitch + (pitch / 2 if j % 2 else 0)
            if r_min <= math.hypot(x, y) <= r_max:
                holes.append(cyl(r_hole, h, z0, 16).translate((x, y, 0)))
    return union(holes)


# ---------- 花盆底座 ----------

def bezier(p0, p1, p2, p3, n):
    out = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * t * (1 - t) ** 2, 3 * t * t * (1 - t), t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return out


def pot_outline():
    """外轮廓（r, z），自口沿向下：口沿 Ø90、腰 Ø100、底 Ø68，与 draw.py 的 pot_path 同一条贝塞尔。"""
    return bezier((45, POT_TOP), (53.5, POT_TOP - 11.4), (53.5, POT_BOT + 22), (34, POT_BOT), 40)


def pot_inline(outer):
    inner = []
    for i, (r, z) in enumerate(outer):
        (r0, z0), (r1, z1) = outer[max(i - 1, 0)], outer[min(i + 1, len(outer) - 1)]
        tr, tz = r1 - r0, z1 - z0
        n = math.hypot(tr, tz)
        inner.append((r + tz / n * WALL, z - tr / n * WALL))  # 沿法线往里收一个壁厚
    inner[0] = (inner[0][0], POT_TOP)
    inner[-1] = (inner[-1][0], POT_BOT)
    return inner


def inner_r(z):
    pts = sorted(pot_inline(pot_outline()), key=lambda p: p[1])
    return float(np.interp(z, [p[1] for p in pts], [p[0] for p in pts]))


def pot_shell():
    outer = pot_outline()
    inner = pot_inline(outer)
    body = poly([(0, POT_BOT)] + outer[::-1] + [(0, POT_TOP)])
    shell = poly(outer + inner[::-1])
    ledge = poly([(39.0, DECK_Z), (60, DECK_Z), (60, DECK_Z - 21)]) ^ body  # 45° 倒角托住格栅，免支撑
    m = (shell + ledge).revolve(128)
    bosses = union(at(cyl(3.8, 10, POT_BOT, 32), 28.5, 45 + 90 * k) for k in range(4))
    pilots = union(at(cyl(1.1, 9, POT_BOT - 1, 16), 28.5, 45 + 90 * k) for k in range(4))
    usb = rounded_slot(9.4, 3.8, 20).translate((0, 40, POT_BOT + 6))  # 背面 USB-C
    return (m + (bosses ^ body.revolve(128))) - pilots - usb


def base_plate():
    plate = cyl(34, 3, 8, 128)
    feet = union(at(cyl(5, 8.2, -0.2 + 0.2, 48), 24, 90 * k) for k in range(4))
    screws = union(at(cyl(1.4, 4, 7.5, 16) + cyl(2.8, 1.4, 8, 32, 1.4), 28.5, 45 + 90 * k) for k in range(4))
    sound = hex_holes(1.25, 4.5, 0, 16, 5, 7)
    return plate + feet - screws - sound


def deck():
    plate = cyl(42.3, 3, DECK_Z, 160)
    boss = cyl(13.5, 4.5, DECK_Z - 4, 96)
    _, od, w = BUY["bearing"]
    pocket = cyl(od / 2 + 0.05, w + 0.15, DECK_Z - 4.1, 96)  # 轴承压入，外圈顶在 2 mm 的唇上
    lip_hole = cyl(8, 10, DECK_Z, 64)  # 只压外圈，不碰内圈
    grid = hex_holes(1.1, 4.2, 15.5, 38.5, 5, DECK_Z - 1)
    mics = union(at(cyl(1.5, 5, DECK_Z - 1, 20), 22, 45 + 90 * k) for k in range(4))  # 麦孔：对角 44
    return plate + boss - pocket - lip_hole - grid - mics


def stem_collar():
    return ring(7.2, BUY["stem"][0] / 2 + 0.1, 2.5, 0, 64)


# ---------- 叶片 ----------
LEAF_L, LEAF_W, LEAF_T, LEAF_UP, LEAF_Z, LEAF_X0, TAB = 54, 24, 2.4, 25, 103, 12.6, 5.5
PAD_X = 0.62 * LEAF_L


def leaf_outline(n=48):
    top = []
    for i in range(n + 1):
        t = i / n
        w = LEAF_W / 2 * math.sin(math.pi * (0.08 + 0.92 * t) ** 0.8)
        top.append((t * LEAF_L, w))
    return top + [(x, -y) for x, y in reversed(top[1:-1])]


def leaf_up():
    """叶片局部坐标里的「世界竖直向上」：叶片绕 Y 转了 -LEAF_UP。"""
    a = math.radians(LEAF_UP)
    return np.array([math.sin(a), 0, math.cos(a)])


def leaf(with_button):
    t = LEAF_T / 2
    m = poly(leaf_outline()).extrude(LEAF_T).translate((0, 0, -t))
    m += Manifold.cube((TAB + 0.5, 10, LEAF_T)).translate((-TAB, -5, -t))
    m -= Manifold.cube((0.8 * LEAF_L - 4, 1.2, 1)).translate((4, -0.6, t - 0.6))  # 叶脉
    if with_button:
        u = leaf_up()
        top = np.array([PAD_X, 0, t + 6.5])
        pad = cyl(6.5, 14, t - 0.5, 48).translate((PAD_X, 0, 0)).trim_by_plane(tuple(-u), float(-u @ top))
        s, body, _ = BUY["switch"]
        pocket = Manifold.cube((s + 0.3, s + 0.3, body + 0.5 + 3), center=True).translate((0, 0, 1.5 - (body + 0.5) / 2))
        wire = Manifold.cylinder(20, 1.0, 1.0, 16).translate((0, 0, -20 + 0.1))
        tilt = lambda x: x.rotate((0, LEAF_UP, 0)).translate(tuple(top))  # noqa: E731  竖直于世界
        m = m + pad - tilt(pocket) - tilt(wire)
        m -= Manifold.cube((PAD_X + TAB - 4, 2, 1.0)).translate((-TAB, -1, -t - 0.01))  # 背面走线槽
    return m


def leaf_pose(m, side):
    m = m.rotate((0, -LEAF_UP, 0)).translate((LEAF_X0, 0, LEAF_Z))
    return m if side > 0 else m.rotate((0, 0, 180))


def leaf_collar():
    c = ring(12, BUY["stem"][0] / 2 + 0.15, 14, LEAF_Z - 7, 64)
    slot = Manifold.cube((TAB + 0.5 + 2 * FIT, 10 + 2 * FIT, LEAF_T + 2 * FIT)).translate(
        (-TAB - FIT, -5 - FIT, -LEAF_T / 2 - FIT))
    return c - leaf_pose(slot, 1) - leaf_pose(slot, -1)


def ladybug():
    shell = Manifold.sphere(1, 48).scale((7, 5.5, 4.5)).trim_by_plane((0, 0, 1), 0)
    head = Manifold.sphere(1, 32).scale((2.6, 3.2, 2.6)).translate((-6.5, 0, 0)).trim_by_plane((0, 0, 1), 0)
    stem_hole = cyl(BUY["switch"][2] / 2 + 0.1, 2.0, -0.01, 24)
    return shell + head - stem_hole


def button_top_world():
    """瓢虫键开关口在世界坐标里的位置（右叶）。"""
    p = Manifold.cube((0.01, 0.01, 0.01), center=True).translate((PAD_X, 0, LEAF_T / 2 + 6.5))
    b = leaf_pose(p, 1).bounding_box()
    return np.array([(b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2])


# ---------- 花头（局部坐标） ----------

def petal_cs(rad, rx, ry, offset):
    return CrossSection([ellipse(*polar(rad, offset + 22.5 * i), rx, ry, -(offset + 22.5 * i))
                         for i in range(16)])


def petal_ring(v):
    base = CrossSection.circle(38, 128)
    front = petal_cs(37.5, 8, 13, 0)
    back = petal_cs(39.5, 7.5, 13.5, 11.25)
    m = (base + front + back).offset(0.4, circular_segments=16).extrude(2).translate((0, 0, -4))  # 背层包住前层并外扩 0.4，正面朝上打印无悬空，两层轮廓也不重合
    m += (base + front).extrude(2, scale_top=(0.985, 0.985)).translate((0, 0, -2))
    m -= cyl(v["body_r"] + FIT, 10, -5, 128)
    m -= union(at(cyl(0.975, 3, -4.01, 16), PIN_R, 101.25 + 120 * k) for k in range(3))
    return m


def cover(v):
    r, b, w = v["face_r"], v["body_r"], v["window_r"]
    m = cyl(b, 4, -4, 128) + cyl(r, 0.7, 0, 128) + cyl(r, 0.5, 0.7, 128, r - 0.5)
    m -= cyl(w, 10, -5, 128)
    if v["lens"]:
        m -= cyl(BUY["lens"][0] / 2 + 0.25, 1.0, 0.21, 128)  # 面罩沉台
    else:
        m -= cyl(w, 2.21, -1.0, 128, w + 2.21)  # 窗口 45° 倒角，屏不显得深
    return m


def panel_cs(v, grow=0.0):
    if not v["lens"]:
        return CrossSection.circle(BUY["gc9a01"][0] / 2 + grow, 128)
    wd, ht, tab, _ = BUY["st7701s"]
    c = CrossSection.circle(wd / 2 + grow, 128)
    return c + CrossSection.square((tab + 2 * grow, ht - wd / 2 + grow)).translate((-tab / 2 - grow, -(ht - wd / 2) - grow))


def head_front(v):
    thick = BUY["st7701s"][3] if v["lens"] else BUY["gc9a01"][1]
    m = cyl(47, PLATE_Z1 - PLATE_Z0, PLATE_Z0, 160)
    m -= panel_cs(v, 0.25).extrude(thick + 0.1).translate((0, 0, PLATE_Z1 - thick))
    m -= panel_cs(v, -2).extrude(10).translate((0, 0, PLATE_Z0 - 1))  # 留 2 mm 窄沿托住屏背
    if v["lens"]:
        m -= Manifold.cube((20, 14, 10)).translate((-10, -33, PLATE_Z0 - 1))  # 屏排线过孔
    m -= union(at(cyl(BUY["led"][0] / 2 + 0.2, 2.6, -6.5, 32), LED_R, 22.5 * i) for i in range(16))
    m -= union(at(cyl(1.5, 4, PLATE_Z0 - 1, 16), LED_R, 22.5 * i) for i in range(16))
    m -= union(at(cyl(0.975, 3.01, -7, 16), PIN_R, 101.25 + 120 * k) for k in range(3))
    m -= ring(46.25, 44.95, 1.5, PLATE_Z0 - 0.01, 160)  # 后壳唇口槽
    return m


def head_back_profile(v):
    d = v["depth"]
    zb = PLATE_Z0 - d
    rb = 47 - (d - 4)
    return [(0, PLATE_Z0), (47, PLATE_Z0), (47, PLATE_Z0 - 4), (rb, zb), (0, zb)], zb


def socket_axis():
    a = math.radians(TILT)
    return np.array(C0), np.array([0, -math.cos(a), -math.sin(a)])


def head_back(v):
    pts, zb = head_back_profile(v)
    outer = poly(pts)
    both = poly([(-r, z) for r, z in reversed(pts)] + pts)  # 镜像成整截面再内缩，轴线上不留实心
    inner = (both.offset(-2, circular_segments=48) ^ CrossSection.square((60, 100)).translate((0, -80))) + \
        CrossSection.square((45, 5)).translate((0, PLATE_Z0 - 3))  # 口沿敞开
    lip = CrossSection.square((0.8, 1.3)).translate((45.2, PLATE_Z0))
    m = (outer - inner + lip).revolve(160)
    c0, d = socket_axis()
    s_q = 0.0
    while True:  # 沿轴线走到壳外
        p = c0 + d * s_q
        if p[2] < zb or math.hypot(p[0], p[1]) > np.interp(p[2], [zb, PLATE_Z0 - 4], [pts[3][0], 47]):
            break
        s_q += 0.25
    s_end = s_q + 6
    along = lambda r, s0, s1, seg=48: Manifold.cylinder(s1 - s0, r, r, seg).translate((0, 0, s0)).rotate(  # noqa: E731
        (90 + TILT, 0, 0)).translate(tuple(c0))
    boss = along(9, 0, s_end)
    slab = boss.project().extrude(0.01).translate((0, 0, zb))
    boss = Manifold.batch_hull([boss, slab]).trim_by_plane((0, 0, 1), zb)
    m += boss
    m -= along(BUY["stem"][0] / 2 + 0.15, s_end - 16, s_end + 30)  # 穿透颈座下的楔形
    m -= along(3.5, -3, s_end - 15)
    return m, s_end - 16


def head_world(m):
    c0, _ = socket_axis()
    r = Manifold.cube((0.01, 0.01, 0.01), center=True).translate(tuple(c0)).rotate((90 - TILT, 0, 0)).bounding_box()
    return m.rotate((90 - TILT, 0, 0)).translate((0, -(r[1] + r[4]) / 2, FACE_Z))


def local_to_world(p):
    b = head_world(Manifold.cube((0.01, 0.01, 0.01), center=True).translate(tuple(p))).bounding_box()
    return np.array([(b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2])


# ---------- 外购件代理（装配检查与效果图用，不打印） ----------

def buy_parts(v, stem_top):
    od, idd = BUY["stem"]
    bi, bo, bw = BUY["bearing"]
    thick = BUY["st7701s"][3] if v["lens"] else BUY["gc9a01"][1]
    parts = {
        "花茎铝管": ring(od / 2, idd / 2, stem_top - 48, 48, 64),
        "6801 轴承": ring(bo / 2, bi / 2, bw, DECK_Z - 4, 64),
        "扬声器": cyl(BUY["speaker"][0] / 2, BUY["speaker"][1], 11.01, 64),
        "圆屏": head_world(panel_cs(v).extrude(thick).translate((0, 0, PLATE_Z1 - thick))),
        "灯珠 ×16": head_world(union(at(cyl(BUY["led"][0] / 2, BUY["led"][1], PLATE_Z1 - BUY["led"][1], 24), LED_R,
                                        22.5 * i) for i in range(16))),
    }
    s, body, stem = BUY["switch"]
    top = button_top_world()
    sw = Manifold.cube((s, s, body), center=True).translate((0, 0, -0.5 - body / 2)) + cyl(stem / 2, 1.0, -0.5, 24)
    parts["轻触开关"] = sw.translate(tuple(top))
    if v["lens"]:
        parts["亚克力面罩"] = head_world(cyl(BUY["lens"][0] / 2, BUY["lens"][1], 0.21, 128))
    return parts


# ---------- 装配 ----------

def assemble(v):
    """返回 {零件名: (打印件 Manifold, 世界坐标 Manifold, 打印姿态说明, 数量, STL 子目录)}，以及外购件代理。"""
    back, bore_s = head_back(v)
    c0, d = socket_axis()
    stem_top = local_to_world(c0 + d * bore_s)[2]
    flip = lambda m: m.rotate((180, 0, 0))  # noqa: E731
    top = button_top_world()
    var = "standard" if not v["lens"] else "screen"
    parts = {
        "pot_shell": (pot_shell(), None, "口沿朝上", 1, "common"),
        "base_plate": (flip(base_plate()), base_plate(), "脚朝上", 1, "common"),
        "deck": (flip(deck()), deck(), "土面朝下", 1, "common"),
        "stem_collar": (stem_collar(), [stem_collar().translate((0, 0, DECK_Z - 4 - 2.5)),
                                        stem_collar().translate((0, 0, DECK_Z + 1))], "平放", 2, "common"),
        "leaf_collar": (leaf_collar(), None, "竖放", 1, "common"),
        "leaf_left": (leaf(False), leaf_pose(leaf(False), -1), "平放", 1, "common"),
        "leaf_right": (leaf(True), leaf_pose(leaf(True), 1), "平放，键座朝上", 1, "common"),
        "ladybug": (ladybug(), ladybug().translate(tuple(top + [0, 0, 0.3])), "平底朝下", 1, "common"),
        "petal_ring": (petal_ring(v), head_world(petal_ring(v)), "背面朝下", 1, var),
        "cover": (flip(cover(v)), head_world(cover(v)), "正面朝下", 1, var),
        "head_front": (flip(head_front(v)), head_world(head_front(v)), "正面朝下", 1, var),
        "head_back": (back, head_world(back), "背面朝下，颈座孔斜着，不加支撑", 1, var),
    }
    out = {}
    for k, (pm, wm, pose, n, sub) in parts.items():
        out[k] = (pm, pm if wm is None else wm, pose, n, sub)
    return out, buy_parts(v, stem_top), stem_top


def on_bed(m):
    b = m.bounding_box()
    return m.translate((-(b[0] + b[3]) / 2, -(b[1] + b[4]) / 2, -b[2]))


def overhang_area(m, limit=45):
    me = m.to_mesh()
    v, t = me.vert_properties[:, :3], me.tri_verts
    a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    n = np.cross(b - a, c - a)
    area = np.linalg.norm(n, axis=1) / 2
    nz = n[:, 2] / np.maximum(np.linalg.norm(n, axis=1), 1e-12)
    low = np.minimum(np.minimum(a[:, 2], b[:, 2]), c[:, 2])
    down = (nz < -math.cos(math.radians(90 - limit))) & (low > 0.3)
    flat = down & (nz < -0.996)  # 朝下的水平面：小孔、小槽顶上的桥接
    return float(area[down & ~flat].sum()), float(area[flat].sum())


def write_stl(path, m):
    me = m.simplify(0.001).to_mesh()  # 先并掉 float32 下会重合的短边，免得出退化三角形
    v = me.vert_properties[:, :3].astype(np.float32)
    t = me.tri_verts
    a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    n = np.cross(b - a, c - a)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    rec = np.zeros(len(t), dtype=[("n", "<f4", 3), ("v", "<f4", 9), ("attr", "<u2")])
    rec["n"], rec["v"] = n, np.hstack([a, b, c])
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"Sunflower prototype - docs/hardware/print/model.py".ljust(80, b" "))
        f.write(np.uint32(len(t)).tobytes())
        f.write(rec.tobytes())


def interference(solids):
    names = list(solids)
    hits = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            vol = (solids[a] ^ solids[b]).volume()
            if vol > 0.5:
                hits.append((a, b, vol))
    return hits


def main(out, scene=None):
    out = pathlib.Path(out)
    report = ["# 打印件自检（model.py 生成，勿手改）", ""]
    written = set()
    for key, v in VARIANTS.items():
        parts, buys, stem_top = assemble(v)
        report += [f"## {v['name']}", "", "| 文件 | 数量 | 打印姿态 | 外形 X×Y×Z mm | 实体体积 cm³ | 连通体 | 悬空斜面 >45° mm² | 水平桥接 mm² |",
                   "|---|---|---|---|---|---|---|---|"]
        solids = {}
        for name, (pm, wm, pose, n, sub) in parts.items():
            bed = on_bed(pm)
            path = out / "stl" / sub / f"{name}.stl"
            if path not in written:
                write_stl(path, bed)
                written.add(path)
            b = bed.bounding_box()
            slope, flat = overhang_area(bed)
            report.append(f"| `stl/{sub}/{name}.stl` | {n} | {pose} | {b[3] - b[0]:.0f}×{b[4] - b[1]:.0f}×{b[5]:.0f} | "
                          f"{bed.volume() / 1000:.1f} | {len(bed.decompose())} | {slope:.0f} | {flat:.0f} |")
            for j, w in enumerate(wm if isinstance(wm, list) else [wm]):
                solids[name if j == 0 else f"{name}#{j + 1}"] = w
        solids.update(buys)
        hits = interference(solids)
        top = max(s.bounding_box()[5] for s in solids.values())
        report += ["", f"- 花茎铝管长度：{stem_top - 48:.0f} mm（底端 z = 48 留给电机联轴，见待核实）",
                   f"- 整机高度：{top:.0f} mm",
                   "- 装配干涉（任意两件重叠体积 > 0.5 mm³）：" + ("无" if not hits else "；".join(
                       f"{a} × {b} {vol:.1f} mm³" for a, b, vol in hits)), ""]
        if scene:
            write_scene(pathlib.Path(scene) / key, parts, buys, v)
            write_scene(pathlib.Path(scene) / f"{key}-exploded", parts, buys, v, explode=True)
    (out / "check.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))


# ---------- 效果图场景 ----------
COLORS = {"pot_shell": "#F7F3EA", "base_plate": "#EDE6D8", "deck": "#5D4E44", "stem_collar": "#8BC34A",
          "leaf_collar": "#7CB342", "leaf_left": "#8BC34A", "leaf_right": "#8BC34A", "ladybug": "#D7362F",
          "petal_ring": "#FFCF3F", "cover": "#F6A33A", "head_front": "#F2C230", "head_back": "#E9B92A",
          "花茎铝管": "#7CB342", "亚克力面罩": "#FFFFFF"}


def face_deco(v):
    """效果图里屏幕显示的内容（只用于渲染）。"""
    z = PLATE_Z1 + 0.02
    if not v["lens"]:
        r = BUY["gc9a01"][0] / 2
        return [("#F6A33A", cyl(r - 1.3, 0.1, z, 96)),
                ("#2B2B2B", union([Manifold.sphere(1, 24).scale((1.4, 2.0, 0.4)).translate((x, 3, z + 0.1))
                                   for x in (-5, 5)])),
                ("#F28B82", union([Manifold.sphere(1, 24).scale((2.6, 1.6, 0.3)).translate((x, -2.8, z + 0.1))
                                   for x in (-9, 9)])),
                ("#2B2B2B", (ring(3.2, 2.5, 0.25, z + 0.05, 48) ^ Manifold.cube((8, 4, 2)).translate((-4, -6, z))))]
    r = BUY["st7701s"][0] / 2
    arc = ring(26.5, 25, 0.2, z + 0.1, 128) - Manifold.cube((30, 30, 2)).translate((-30, 0, z))
    return [("#1F2A44", cyl(r - 0.5, 0.1, z, 128)), ("#F5A623", arc),
            ("#FFFFFF", union([cyl(1.4, 0.2, z + 0.1, 24).translate((x, 12, 0)) for x in (-4, 4)])),
            ("#FFFFFF", Manifold.cube((20, 3.6, 0.2)).translate((-10, 0, z + 0.1))),
            ("#B8C2D6", Manifold.cube((16, 1.8, 0.2)).translate((-8, -6, z + 0.1)))]


def write_bin(path, m):
    """效果图网格：顶点数、三角形数、坐标、法线（锐边 > 40° 处拆开）、索引，全部小端。"""
    me = m.calculate_normals(0, 40).to_mesh(0)
    vp = me.vert_properties.astype("<f4")
    with open(path, "wb") as f:
        f.write(np.array([len(vp), len(me.tri_verts)], "<u4").tobytes())
        f.write(np.ascontiguousarray(vp[:, :3]).tobytes())
        f.write(np.ascontiguousarray(vp[:, 3:6]).tobytes())
        f.write(me.tri_verts.astype("<u4").tobytes())


EXPLODE = {"base_plate": (0, 0, -32), "deck": (0, 0, 24), "stem_collar": (0, 0, 24), "6801 轴承": (0, 0, 12),
           "花茎铝管": (0, 0, 24), "leaf_collar": (0, 0, 40), "leaf_left": (-30, 0, 40), "leaf_right": (30, 0, 40),
           "ladybug": (30, 0, 58), "瓢虫斑点": (30, 0, 58)}
HEAD_EXPLODE = {"cover": 48, "亚克力面罩": 66, "petal_ring": 22, "屏幕": -4, "圆屏": -4, "head_front": -30,
                "head_back": -66}


def explode_offset(name):
    if name in HEAD_EXPLODE:
        a = math.radians(TILT)
        k = HEAD_EXPLODE[name]
        return (0, -math.cos(a) * k, 80 + math.sin(a) * k)
    return EXPLODE.get(name, (0, 0, 0))


def write_scene(d, parts, buys, v, explode=False):
    d.mkdir(parents=True, exist_ok=True)
    items = []

    def add(name, m, color, opacity=1.0, rough=0.55):
        f = d / f"{len(items):02d}.bin"
        write_bin(f, m.translate(explode_offset(name)) if explode else m)
        items.append({"file": f.name, "name": name, "color": color, "opacity": opacity, "roughness": rough})

    for name, (_, wm, _, _, _) in parts.items():
        for w in (wm if isinstance(wm, list) else [wm]):
            add(name, w, COLORS[name], 1.0, 0.45 if name == "petal_ring" else 0.6)
    add("花茎铝管", buys["花茎铝管"], COLORS["花茎铝管"], 1.0, 0.4)
    if explode:
        add("圆屏", buys["圆屏"], "#2B2B2B", 1.0, 0.3)
        add("6801 轴承", buys["6801 轴承"], "#B0B4BA", 1.0, 0.25)
    for color, m in face_deco(v):
        add("屏幕", head_world(m), color, 1.0, 0.3)
    spots = union([Manifold.sphere(1, 16).scale((1.2, 1.2, 0.5)).translate((x, y, z)) for x, y, z in
                   [(1.5, 2.6, 3.6), (1.5, -2.6, 3.6), (-2.5, 0, 4.0), (4.5, 0, 2.2)]])
    add("瓢虫斑点", spots.translate(tuple(button_top_world() + [0, 0, 0.3])), "#1E1E1E")
    if v["lens"] and explode:  # 装配图里面罩是透明的，不画，免得挡住屏
        add("亚克力面罩", buys["亚克力面罩"], "#DDEBF5", 1.0, 0.1)
    (d / "scene.json").write_text(json.dumps({"title": v["name"], "items": items}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    args = sys.argv[1:]
    main(args[0], args[args.index("--scene") + 1] if "--scene" in args else None)
