# -*- coding: utf-8 -*-
"""小鹿lulu形象：按考试类型匹配形象 + 留白安全区随机落位（底层规则，默认启用）。

三条硬规则
1. 每张海报都必须带一只小鹿lulu；形象从 POSE_LIB 里按考试类型挑，位置/大小随机，
   保证同批海报不重样、画面更活泼。
2. 落点用「除背景外所有图层的占用图」求交，**零重叠**才算合法 ——
   因此绝不会遮挡标题 / 内容卡 / 价格 / 二维码。
3. 小鹿图层插在「背景三件套」之上、其余内容之下，图层名固定 `小鹿lulu形象`
   （保证 PSD 里背景仍垫底）。

用法：
    import xiaolu
    layers = poster.build(cfg, with_qr=True)
    layers, info = xiaolu.add(layers, exam_type="备考", seed=12345)
"""
import os
import random
import numpy as np
from PIL import Image, PngImagePlugin

PngImagePlugin.MAX_TEXT_MEMORY = 2 ** 31 - 1

ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "xiaolu")
LAYER_NAME = "小鹿lulu形象"

# ---------------------------------------------------------------- 形象库
# types：备考 / 公安军警 / 基层乡村 / 面试 / 金融国企 / 活动福利 / 通用
POSE_LIB = [
    dict(id=1,  file="lulu01.png", scene="坐在书堆上读书",      types=["备考"]),
    dict(id=2,  file="lulu02.png", scene="戴圆眼镜抱书（学霸）", types=["备考", "金融国企"]),
    dict(id=3,  file="lulu03.png", scene="枕头上睡觉",          types=["长线陪伴"]),
    dict(id=4,  file="lulu04.png", scene="坐姿微笑",            types=["通用", "面试"]),
    dict(id=5,  file="lulu05.png", scene="坐姿挥手打招呼",      types=["通用", "备考", "公安军警", "基层乡村", "面试", "金融国企"]),
    dict(id=11, file="lulu11.png", scene="吃西瓜",              types=["活动福利"]),
    dict(id=12, file="lulu12.png", scene="披风欢呼跃起",        types=["备考", "通用"]),
    dict(id=13, file="lulu13.png", scene="书桌前写字看书",      types=["备考"]),
    dict(id=14, file="lulu14.png", scene="斗篷星星冲刺",        types=["备考"]),
    dict(id=15, file="lulu15.png", scene="草帽抱麦穗",          types=["基层乡村"]),
    dict(id=21, file="lulu21.png", scene="举奖杯欢呼",          types=["备考", "公安军警", "基层乡村", "金融国企"]),
    dict(id=22, file="lulu22.png", scene="军装敬礼",            types=["公安军警"]),
    dict(id=23, file="lulu23.png", scene="奔跑欢笑（红领巾）",  types=["面试", "通用"]),
    dict(id=24, file="lulu24.png", scene="拿文件夹微笑",        types=["金融国企", "面试", "备考"]),
]

# ---------------------------------------------------------------- 落点区
# 2000×2000 版式实测留白带。左侧正文从 x≥200 起排，右侧地域线稿止于 x≈1775。
# 侧腰区的 y 下限定在 900：标题带（y≈420–800）一律不放，避免小鹿紧贴主标题显拥挤。
# 每项：(名称, 包围盒, 最小高, 最大高, x 贴边, y 贴边)；lo/hi/mid = 靠左|靠右|居中。
REGIONS = [
    ("左下角",   (6, 1395, 236, 1992), 240, 430, "lo",  "hi"),
    ("右下角",   (1736, 1395, 1992, 1992), 240, 430, "hi", "hi"),
    ("左侧中部", (6, 900, 202, 1395), 250, 350, "lo",  "mid"),
    ("右侧中部", (1806, 900, 1992, 1395), 250, 350, "hi", "mid"),
    ("顶部横带", (900, 4, 1712, 246), 190, 246, "mid", "lo"),
]
CORNER_RATIO = 0.65          # 65% 概率优先用底角（视觉最佳），其余优先用左右侧腰


def poses_for(exam_type):
    return [p for p in POSE_LIB if exam_type in p["types"]]


def pick_pose(exam_type, rng, exclude=()):
    pool = poses_for(exam_type) or poses_for("通用")
    cands = [p for p in pool if p["id"] not in exclude] or pool
    return cands[rng.randrange(len(cands))]


def load_art(pose, target_h, asset_dir=None):
    path = os.path.join(asset_dir or ASSET_DIR, pose["file"])
    im = Image.open(path).convert("RGBA")
    bb = im.getbbox()
    if bb:
        im = im.crop(bb)
    w0, h0 = im.size
    h = int(target_h)
    return im.resize((max(1, int(round(w0 * h / h0))), h), Image.LANCZOS)


def occ_of(layers, size):
    """除「背景*」外所有图层的占用图。"""
    occ = np.zeros((size, size), bool)
    for n, im in layers:
        if n.startswith("背景"):
            continue
        occ |= (np.asarray(im)[..., 3] > 8)
    return occ


def _foot(art):
    foot = np.asarray(art)[..., 3] > 8
    ys, xs = np.where(foot)
    return foot[ys.min():ys.max() + 1, xs.min():xs.max() + 1], ys.min(), xs.min()


def hits_in(occ, art, box, size, step=10):
    """返回 box 内所有零重叠落点 [(x0, y0)]。"""
    w, h = art.size
    x_lo, y_lo, x_hi, y_hi = box
    x_hi, y_hi = min(x_hi, size - w), min(y_hi, size - h)
    if x_hi < x_lo or y_hi < y_lo:
        return []
    fsub, fy0, fx0 = _foot(art)
    fy1, fx1 = fy0 + fsub.shape[0], fx0 + fsub.shape[1]
    out = []
    for y0 in range(max(0, y_lo), y_hi + 1, step):
        for x0 in range(max(0, x_lo), x_hi + 1, step):
            if np.any(occ[y0 + fy0:y0 + fy1, x0 + fx0:x0 + fx1] & fsub):
                continue
            out.append((x0, y0))
    return out


def _regions_for(size):
    if size == 2000:
        return REGIONS
    k = size / 2000.0
    return [(n, tuple(int(round(v * k)) for v in box), int(h1 * k), int(h2 * k), xp, yp)
            for n, box, h1, h2, xp, yp in REGIONS]


def solve(occ, pose, rng, size=2000, asset_dir=None, debug=False, prefer=None):
    """在留白区随机落位，返回 (x, y, art) 或 None。

    prefer="left"/"right" 时把该侧的角/腰排在前面（同批多张图可左右交替，避免全挤一侧）；
    该侧实在没有零重叠落点时自动回落到另一侧，不会硬塞。
    """
    regions = _regions_for(size)
    corners, sides = regions[:2], regions[2:4]
    rng.shuffle(corners)
    rng.shuffle(sides)
    if prefer in ("left", "right"):
        want_lo = (prefer == "left")
        key = lambda r: 0 if (r[4] == "lo") == want_lo else 1
        corners.sort(key=key)
        sides.sort(key=key)
    order = (corners + sides) if rng.random() < CORNER_RATIO else (sides + corners)
    order.append(regions[4])                     # 顶部横带仅作兜底

    for name, box, h_lo, h_hi, xp, yp in order:
        hmax = None
        for h in range(h_hi, h_lo - 1, -10):
            art = load_art(pose, h, asset_dir)
            if hits_in(occ, art, box, size):
                hmax = h
                break
        if hmax is None:
            continue
        h = rng.randint(max(h_lo, int(hmax * 0.82)), hmax)
        art = load_art(pose, h, asset_dir)
        hits = hits_in(occ, art, box, size)
        w = art.size[0]
        x_lo, y_lo, x_hi, y_hi = box
        tx = {"lo": x_lo, "hi": x_hi - w, "mid": (x_lo + x_hi - w) // 2}[xp]
        ty = {"lo": y_lo, "hi": y_hi - h, "mid": (y_lo + y_hi - h) // 2}[yp]
        hits.sort(key=lambda p: abs(p[0] - tx) + abs(p[1] - ty))
        pool = hits[:max(1, len(hits) // 4)]     # 最贴合贴边意图的前 25% 里随机
        x, y = pool[rng.randrange(len(pool))]
        if debug:
            print(f"    小鹿落点区={name} 高度={h} pos=({x},{y}) size={w}x{h}")
        return x, y, art
    return None


def insert_index(layers):
    """小鹿插在背景层之上、其余内容之下。"""
    idx = 0
    for i, (n, _) in enumerate(layers):
        if n.startswith("背景"):
            idx = i + 1
    return idx


def add(layers, exam_type="备考", seed=None, size=2000, asset_dir=None,
        extra_occ=None, exclude=(), debug=False, prefer=None):
    """在图层栈（自下而上）中插入小鹿图层。

    返回 (新图层列表, info)。找不到落点时原样返回 layers 并 info=None。
    extra_occ：另一版式（如有码/无码）的占用图，传入后落点对两版同时安全。
    prefer：left/right，偏好落在画面左侧或右侧（同批交替用，避免全挤一侧）。
    """
    rng = random.Random(seed)
    if not os.path.isdir(asset_dir or ASSET_DIR):
        return layers, None
    pose = pick_pose(exam_type, rng, exclude=exclude)
    occ = occ_of(layers, size)
    if extra_occ is not None:
        occ = occ | extra_occ
    sol = solve(occ, pose, rng, size=size, asset_dir=asset_dir, debug=debug, prefer=prefer)
    if sol is None:
        return layers, None
    x, y, art = sol
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(art, (x, y))
    new = list(layers)
    new.insert(insert_index(layers), (LAYER_NAME, canvas))
    return new, dict(pose=pose, x=x, y=y, w=art.size[0], h=art.size[1])