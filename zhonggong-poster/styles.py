# -*- coding: utf-8 -*-
"""配色库 + 版式库 + 轮换状态（底层规则：每次出图配色与版式都必须换新）。

- PALETTES：8 套完整撞色方案，键与 poster.CONFIG["palette"] 完全一致。
- LAYOUTS：版式预设（几何位置 / 标题字号 / 价格对齐 / 二维码左右）。
- 轮换状态：assets/rotation.json，记录 palette / layout 使用历史；
  新任务从「最近 window 次未用过」的候选中随机取，保证每张都不一样。
"""
import json
import os
import random
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "assets", "rotation.json")

# ---------------------------------------------------------------- 配色库
# 每套：bg_top/bg_bot 渐变底，light/mute/track 三级辅助字色，ink 卡片文字，
#       red 强调色（珊瑚橙系，禁用纯正红），yellow 亮黄，cyan 电光青。
PALETTES = {
    "宝蓝珊瑚": dict(bg_top=(18, 32, 96), bg_bot=(34, 74, 178), white=(255, 255, 255),
                  light=(198, 214, 255), mute=(156, 174, 226), track=(128, 148, 206),
                  ink=(26, 36, 92), red=(250, 108, 74), yellow=(255, 205, 61),
                  cyan=(61, 214, 232)),
    "墨绿柠黄": dict(bg_top=(10, 52, 40), bg_bot=(16, 116, 88), white=(255, 255, 255),
                  light=(206, 236, 222), mute=(140, 190, 172), track=(110, 158, 140),
                  ink=(12, 52, 42), red=(255, 122, 66), yellow=(242, 225, 72),
                  cyan=(79, 224, 190)),
    "绛紫蜜橙": dict(bg_top=(42, 14, 79), bg_bot=(91, 42, 168), white=(255, 255, 255),
                  light=(216, 203, 245), mute=(169, 154, 214), track=(138, 124, 188),
                  ink=(43, 21, 80), red=(255, 138, 61), yellow=(255, 216, 77),
                  cyan=(86, 225, 240)),
    "深海电青": dict(bg_top=(6, 38, 63), bg_bot=(14, 90, 138), white=(255, 255, 255),
                  light=(191, 224, 242), mute=(143, 180, 204), track=(110, 150, 176),
                  ink=(11, 43, 69), red=(255, 107, 74), yellow=(255, 201, 60),
                  cyan=(56, 224, 208)),
    "赤陶沙金": dict(bg_top=(74, 26, 18), bg_bot=(163, 58, 34), white=(255, 255, 255),
                  light=(243, 210, 194), mute=(208, 160, 140), track=(185, 138, 118),
                  ink=(74, 26, 18), red=(255, 176, 58), yellow=(255, 224, 122),
                  cyan=(79, 214, 198)),
    "松石柠檬": dict(bg_top=(8, 52, 60), bg_bot=(15, 122, 120), white=(255, 255, 255),
                  light=(198, 236, 234), mute=(143, 196, 194), track=(111, 168, 166),
                  ink=(10, 50, 56), red=(255, 122, 89), yellow=(255, 228, 92),
                  cyan=(127, 240, 216)),
    "梅子紫玫": dict(bg_top=(58, 16, 64), bg_bot=(122, 32, 120), white=(255, 255, 255),
                  light=(240, 205, 238), mute=(206, 152, 204), track=(176, 124, 174),
                  ink=(60, 18, 66), red=(255, 140, 60), yellow=(255, 222, 96),
                  cyan=(94, 226, 224)),
    "夜棕薄荷": dict(bg_top=(35, 26, 18), bg_bot=(74, 53, 36), white=(255, 255, 255),
                  light=(228, 214, 196), mute=(184, 164, 140), track=(154, 134, 114),
                  ink=(42, 31, 22), red=(255, 159, 69), yellow=(255, 221, 107),
                  cyan=(87, 227, 196)),
    # 庄重国考风：深藏青→靛蓝 + 鎏金强调（标题/价格/勾选为金，青为辅助线）
    "藏青鎏金": dict(bg_top=(7, 16, 42), bg_bot=(24, 56, 132), white=(255, 255, 255),
                  light=(208, 222, 255), mute=(148, 170, 212), track=(116, 140, 188),
                  ink=(16, 26, 62), red=(247, 178, 64), yellow=(255, 219, 120),
                  cyan=(94, 206, 224)),
    # 大红色主题：绛红→正红渐变 + 鎏金强调（红金配，最庄重大气）
    #   red 键放大气主题里的「强调色」=鎏金；cyan 键放香槟金，承担线条/标签/水纹
    #   可选扩展键：cardline 卡片描边 / stroke_w 白字描边 / stroke_r 强调字描边 / glow3 第三层光晕
    "赤金鸿运": dict(bg_top=(104, 10, 26), bg_bot=(200, 24, 46), white=(255, 255, 255),
                  light=(255, 220, 214), mute=(196, 140, 138), track=(190, 124, 122),
                  ink=(74, 10, 22), red=(252, 196, 76), yellow=(255, 228, 150),
                  cyan=(240, 206, 164),
                  cardline=(252, 196, 76), stroke_w=(92, 12, 30),
                  stroke_r=(150, 62, 12), glow3=(255, 152, 96)),
}

# ---------------------------------------------------------------- 版式库
# 每套版式改变：标题字号/宽度、公告与标题的纵向节奏、内容卡几何、价格对齐、二维码左右。
LAYOUTS = {
    "居中宽卡": dict(
        notice_size=42, notice_y=296,
        title_main_size=220, title_sub_size=190,
        title_main_y=446, title_sub_y=690, subtitle_y=818, title_width=1600,
        content_box=[200, 930, 1800, 1552],
        price_align="left", price_margin=200, price_dy=36, qr_box=[1462, 1562, 236]),
    "通栏高卡": dict(
        notice_size=42, notice_y=290,
        title_main_size=226, title_sub_size=196,
        title_main_y=434, title_sub_y=674, subtitle_y=790, title_width=1648,
        content_box=[176, 892, 1824, 1568],
        price_align="left", price_margin=176, price_dy=30, qr_box=[1436, 1592, 212]),
    "窄卡阔景": dict(
        notice_size=40, notice_y=300,
        title_main_size=194, title_sub_size=172,
        title_main_y=452, title_sub_y=700, subtitle_y=828, title_width=1400,
        content_box=[300, 940, 1700, 1552],
        price_align="left", price_margin=300, price_dy=36, qr_box=[1470, 1566, 232]),
    "左码右价": dict(
        notice_size=42, notice_y=300,
        title_main_size=220, title_sub_size=190,
        title_main_y=448, title_sub_y=696, subtitle_y=824, title_width=1600,
        content_box=[200, 938, 1800, 1556],
        price_align="right", price_margin=200, price_dy=32, qr_box=[300, 1560, 236]),
    "居价宽卡": dict(
        notice_size=42, notice_y=294,
        title_main_size=214, title_sub_size=184,
        title_main_y=442, title_sub_y=682, subtitle_y=806, title_width=1560,
        content_box=[220, 916, 1780, 1556],
        price_align="center", price_margin=220, price_dy=34, qr_box=[1454, 1560, 234]),
    # 大气通栏：标题最大、卡片最宽（国考/大型招考类推荐）
    "鎏金通栏": dict(
        notice_size=42, notice_y=284,
        title_main_size=232, title_sub_size=200,
        title_main_y=426, title_sub_y=678, subtitle_y=796, title_width=1648,
        content_box=[176, 900, 1824, 1570],
        price_align="left", price_margin=176, price_dy=30, qr_box=[1436, 1590, 214]),
    # 赤金阔幕：红金大气版 —— 标题字号再放大、标题框=卡片宽度且更贴边、
    #   内容卡更高更阔、价格居中、二维码右下（与「鎏金通栏」明显区分）
    #   ⚠️ price_dy 必须 ≥36：卡片下沿 1572，拼团标签画在 1568+price_dy，
    #      否则「2人拼团」会被卡片压住（2026-10-08 踩坑，勿调小）
    "赤金阔幕": dict(
        notice_size=44, notice_y=280,
        title_main_size=246, title_sub_size=176,
        title_main_y=420, title_sub_y=672, subtitle_y=788, title_width=1696,
        content_box=[152, 884, 1848, 1572],
        price_align="center", price_margin=152, price_dy=36, qr_box=[1548, 1588, 214]),
}


# ---------------------------------------------------------------- 轮换状态
def _load():
    try:
        with open(STATE, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {"palette": [], "layout": []}


def _save(st):
    try:
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        with open(STATE, "w", encoding="utf-8") as fh:
            json.dump(st, fh, ensure_ascii=False, indent=1)
        return True
    except Exception as e:
        print("!! 轮换状态写入失败（下次请手动指定 palette_name/layout_name）:", e)
        return False


def _pick(lib, hist, window, rng):
    recent = set(hist[-window:])
    cands = [k for k in lib if k not in recent] or list(lib)
    return cands[rng.randrange(len(cands))]


def rotate(palette_name=None, layout_name=None, seed_text="", window=4):
    """选出本次配色与版式：优先用显式指定，否则在「最近 window 次未用」里随机。"""
    st = _load()
    rng = random.Random(zlib.crc32(seed_text.encode("utf-8")))
    pal = palette_name if palette_name in PALETTES else _pick(
        PALETTES, st.get("palette", []), window, rng)
    lay = layout_name if layout_name in LAYOUTS else _pick(
        LAYOUTS, st.get("layout", []), window, rng)
    return pal, lay, st


def commit(palette_name, layout_name, st=None):
    st = st or _load()
    st.setdefault("palette", []).append(palette_name)
    st.setdefault("layout", []).append(layout_name)
    st["palette"] = st["palette"][-12:]
    st["layout"] = st["layout"][-12:]
    return _save(st)