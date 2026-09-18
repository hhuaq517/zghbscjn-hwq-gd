# -*- coding: utf-8 -*-
"""
中公教育 方形推广海报生成器（纯代码，不调用 Photoshop）

用法：
    python3 poster.py                  # 生成 2 张 JPG
    python3 poster.py --psd            # 额外生成分层 PSD
    python3 poster.py --config c.json  # 用 JSON 覆盖 CONFIG

依赖：pillow>=10, numpy, pytoshop, psd-tools, six
    python3 -m venv .venv && .venv/bin/pip install pillow numpy pytoshop psd-tools six
"""
import os, sys, math, json, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# 脚本所在目录 —— 所有默认路径都相对它解析，换台电脑即可直接跑
_HERE = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# CONFIG —— 每个新任务只改这里
# ============================================================
CONFIG = {
    # 输出目录：默认 <脚本目录>/out，可用环境变量 ZG_OUT_DIR 覆盖
    "out_dir": os.environ.get("ZG_OUT_DIR", os.path.join(_HERE, "out")),
    "base_name": "海珠事编笔试冲刺卷课件包",
    "size": 2000,

    # 顶部
    # logo：默认 <脚本目录>/assets/logo.png，可用环境变量 ZG_LOGO 覆盖
    "logo_path": os.environ.get("ZG_LOGO", os.path.join(_HERE, "assets", "logo.png")),
    "project_tag": "事业单位",          # 项目类型：事业单位 / 教师招聘 / 省考 / 医疗 ...
    "notice": "2026年广州市海珠区事业单位公开招聘高校毕业生公告",  # 公告名词

    # 主标题（无 kicker，直接大标题）
    "title_main": "海珠事编",
    "title_sub": [["笔试", "w"], ["冲刺卷", "r"]],   # w=白 r=标红
    "title_main_size": 238,
    "title_sub_size": 198,
    "title_width": 1600,                              # 标题两端对齐到内容框宽度（字距自动放宽）

    # 标签组
    "subtitle": "全真模拟 · 三套",
    "badge": "电子课件",

    # 课件卡片：rows = [全称, 后缀说明]
    "content_title": "课件内容",
    "content_meta": "共 6 份电子文档",
    "content_rows": [
        ["2026海珠区事业单位招聘高校毕业生冲刺卷（一）", "· 参考答案及解析"],
        ["2026海珠区事业单位招聘高校毕业生冲刺卷（二）", "· 参考答案及解析"],
        ["2026海珠区事业单位招聘高校毕业生冲刺卷（三）", "· 参考答案及解析"],
    ],
    "content_note": "全部为电子版课件 · 每套均配参考答案及详细解析",

    # 价格
    "price_group": "2人拼团",
    "price_value": "5.99",
    "price_single": "单独购买 15.99 元",
    "only_price": "5.99",
    "only_sub": "限时优惠 · 电子课件",

    # 底部
    "claim": "购买后在中公教育 App 可下载电子文档",
    "footer": "2026广州市海珠区事业单位“高珠识粤”笔试冲刺卷三套（电子课件）",

    # 地域元素
    "motif": "canton_tower",   # canton_tower | waves | grid

    # 配色（活力撞色，可整套替换）
    "palette": {
        "bg_top": (18, 32, 96),
        "bg_bot": (34, 74, 178),
        "white":  (255, 255, 255),
        "light":  (198, 214, 255),
        "mute":   (156, 174, 226),
        "track":  (128, 148, 206),
        "ink":    (26, 36, 92),
        "red":    (250, 108, 74),
        "yellow": (255, 205, 61),
        "cyan":   (61, 214, 232),
    },
}

# ============================================================
# 字体白名单（仅可用这些，且必须已安装）
# ============================================================
FONT_DIR = os.environ.get("ZG_FONT_DIR") or os.path.expanduser("~/Library/Fonts")
FONT_WHITELIST = {
    "方正兰亭特黑": "FZLTTHJW.TTF",
    "方正兰亭粗黑": "FZLTCHJW.TTF",
    "方正兰亭黑":  "FZLTHJW.TTF",
    "方正粗谭黑":  "FZCTHJW.TTF",
    "方正汉真广标": "FZHZGBJW.TTF",
    "方正特雅宋":  "FZTYSJW.ttf",
    "方正清刻本悦宋": "FZQKBYSJW.TTF",
    "方正书宋":    "方正书宋简体.ttf",
    "方正仿宋":    "方正仿宋简体.TTF",
    "方正楷体":    "方正楷体简体.ttf",
    "方正黑体":    "方正黑体简体.TTF",
    "站酷高端黑":  "站酷高端黑修订版1.13.ttf",
    "站酷酷黑":    "站酷酷黑.ttf",
    "庞门正道标题体": "庞门正道标题体2.0增强版.ttf",
    "锐字真言体":  "锐字真言体免费商用.ttf",
}
FT_TITLE = FONT_WHITELIST["方正兰亭粗黑"]
FT_HEAVY = FONT_WHITELIST["方正兰亭粗黑"]
FT_BOLD  = FONT_WHITELIST["方正兰亭粗黑"]
FT_REG   = FONT_WHITELIST["方正兰亭黑"]

# 违规广告词黑名单（命中即需替换）
BANNED_WORDS = ["资料", "真题", "押题", "上岸", "保过", "包过", "协议班", "绝密",
                "内部", "命题", "命中", "预测", "必过", "保分", "官方指定", "第一",
                "最好", "最佳", "最强", "100%", "百分百", "泄题", "原题", "保过班"]

# 配色（运行时由 CONFIG["palette"] 覆盖）
PAL = dict(CONFIG["palette"])
S = 2000


def C(k):
    return PAL[k]


def F(name, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


def new_canvas():
    return Image.new("RGBA", (S, S), (0, 0, 0, 0))


def vgrad(c1, c2):
    ramp = np.linspace(0, 1, S).reshape(S, 1, 1)
    a = (np.array(c1, float).reshape(1, 1, 3) * (1 - ramp) +
         np.array(c2, float).reshape(1, 1, 3) * ramp).astype(np.uint8)
    return Image.fromarray(np.repeat(a, S, axis=1), "RGB").convert("RGBA")


def glow(cx, cy, r, color, strength):
    yy, xx = np.mgrid[0:S, 0:S]
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / r
    m = np.clip(1 - d, 0, 1) ** 2 * strength
    layer = np.zeros((S, S, 4), np.uint8)
    for i in range(3):
        layer[..., i] = color[i]
    layer[..., 3] = (m * 255).astype(np.uint8)
    return Image.fromarray(layer, "RGBA")


def text_img(text, font, fill, sw=0, sfill=None):
    d = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    b = d.textbbox((0, 0), text, font=font, stroke_width=sw)
    pad = 6
    out = Image.new("RGBA", (b[2] - b[0] + pad * 2 + sw * 2,
                             b[3] - b[1] + pad * 2 + sw * 2), (0, 0, 0, 0))
    ImageDraw.Draw(out).text((pad - b[0], pad - b[1]), text, font=font, fill=fill,
                             stroke_width=sw, stroke_fill=sfill)
    return out


def put(layer, im, cx, cy):
    layer.alpha_composite(im, (int(cx - im.size[0] / 2), int(cy - im.size[1] / 2)))


def tracked_segs(layer, segs, font, cx, cy, track):
    """segs: [(text, fill, stroke_fill)] 带字距，整行居中，返回总宽"""
    chars = [(ch, fill, sf) for (t, fill, sf) in segs for ch in t]
    ws = [font.getlength(ch) for ch, _, _ in chars]
    total = sum(ws) + track * (len(chars) - 1)
    x = cx - total / 2
    for (ch, fill, sf), w in zip(chars, ws):
        im = text_img(ch, font, fill, 3, sf)
        layer.alpha_composite(im, (int(x), int(cy - im.size[1] / 2)))
        x += w + track
    return total


def fit_track(text, font, target):
    """按目标宽度反算字距，使该行两端对齐到 target 宽度"""
    ws = [font.getlength(ch) for ch in text]
    if len(ws) < 2:
        return 0
    return (target - sum(ws)) / (len(ws) - 1)


# ---------------- 背景与地域元素（全原创矢量绘制） ----------------
def L_bg():
    bg = vgrad(C("bg_top"), C("bg_bot"))
    bg.alpha_composite(glow(400, 360, 1150, C("cyan"), 0.24))
    bg.alpha_composite(glow(1760, 1720, 1300, C("red"), 0.16))
    bg.alpha_composite(glow(1500, 700, 800, (90, 140, 255), 0.20))
    return bg


def L_motif(motif):
    l = new_canvas()
    dr = ImageDraw.Draw(l)
    line_c = C("cyan")
    if motif == "canton_tower":
        cx, top, bot = 1660, 300, 1580
        wmin, tw, ka, kb = 30, 0.60, 2.15, 1.55

        def half(t):
            return (1.95 * wmin * math.cosh(ka * (tw - t)) if t <= tw
                    else 1.55 * wmin * math.cosh(kb * (t - tw)))
        n = 90
        left, right = [], []
        for i in range(n + 1):
            t = i / n
            y = top + (bot - top) * t
            w = half(t)
            left.append((cx - w, y)); right.append((cx + w, y))
        dr.line(left, fill=line_c + (95,), width=3)
        dr.line(right, fill=line_c + (95,), width=3)
        for i in range(0, n, 5):
            t = i / n
            y = top + (bot - top) * t
            w = half(t)
            dr.line([(cx - w, y), (cx + w, y)], fill=line_c + (48,), width=2)
        dr.line([(cx, top), (cx, 158)], fill=line_c + (95,), width=4)
        for t in (0.30, 0.45, 0.62, 0.80):
            y = top + (bot - top) * t
            w = half(t)
            dr.line([(cx - w - 5, y), (cx + w + 5, y)], fill=C("yellow") + (80,), width=5)
    elif motif == "grid":
        for i in range(6):
            x = 180 + i * 300
            dr.line([(x, 300), (x, 1500)], fill=line_c + (44,), width=3)
        for j in range(6):
            y = 340 + j * 220
            dr.line([(180, y), (1820, y)], fill=line_c + (44,), width=3)
    return l


def L_water():
    l = new_canvas()
    dr = ImageDraw.Draw(l)
    for y0, amp, per, ph, wd, al in [(1560, 30, 1500, 0.4, 3, 52), (1652, 44, 1150, 1.3, 3, 58),
                                     (1748, 26, 900, 2.4, 2, 44), (1852, 46, 1300, 0.9, 4, 62)]:
        pts = [(S * i / 400, y0 + amp * math.sin(2 * math.pi * (S * i / 400) / per + ph))
               for i in range(401)]
        dr.line(pts, fill=C("cyan") + (al,), width=wd, joint="curve")
    return l


# ---------------- 顶部 ----------------
def L_logo(cfg):
    l = new_canvas()
    logo = Image.open(cfg["logo_path"]).convert("RGBA")
    h = 118
    logo = logo.resize((int(logo.width * h / logo.height), h), Image.LANCZOS)
    px, py, padx, pady = 96, 74, 30, 20
    pw, ph = logo.width + padx * 2, logo.height + pady * 2
    chip = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    ImageDraw.Draw(chip).rounded_rectangle([0, 0, pw - 1, ph - 1], radius=16, fill=C("white"))
    l.alpha_composite(chip, (px, py))
    l.alpha_composite(logo, (px + padx, py + pady))
    return l


def L_project(cfg):
    l = new_canvas()
    f = F(FT_BOLD, 44)
    tag = cfg["project_tag"]
    w, h = int(f.getlength(tag)) + 92, 78
    box = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(box)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=h // 2, fill=C("red"))
    d.ellipse([26, h // 2 - 7, 40, h // 2 + 7], fill=C("yellow"))
    d.text((62, h // 2), tag, font=f, fill=C("white"), anchor="lm")
    l.alpha_composite(box, (S - w - 96, 90))
    return l


def L_rule():
    l = new_canvas()
    ImageDraw.Draw(l).line([(96, 250), (S - 96, 250)], fill=C("white") + (58,), width=2)
    return l


def L_notice(cfg):
    l = new_canvas()
    put(l, text_img(cfg["notice"], F(FT_REG, 42), C("light")), S / 2, 296)
    return l


# ---------------- 主标题（无 kicker，字距放宽） ----------------
def L_title(cfg):
    l = new_canvas()
    cx = S / 2
    target = cfg.get("title_width", 1600)
    f1 = F(FT_TITLE, cfg.get("title_main_size", 238))
    tracked_segs(l, [(cfg["title_main"], C("white"), (30, 60, 150))], f1, cx, 486,
                 fit_track(cfg["title_main"], f1, target))
    f2 = F(FT_TITLE, cfg.get("title_sub_size", 198))
    segs = [(t, C("red") if k == "r" else C("white"),
             (150, 52, 24) if k == "r" else (30, 60, 150))
            for t, k in cfg["title_sub"]]
    sub_text = "".join(t for t, _ in cfg["title_sub"])
    tracked_segs(l, segs, f2, cx, 730, fit_track(sub_text, f2, target))
    return l


def _sub_positions(cfg):
    fs, ft = F(FT_HEAVY, 64), F(FT_BOLD, 46)
    ws = int(fs.getlength(cfg["subtitle"])) + 118
    wt = int(ft.getlength(cfg["badge"])) + 60
    gap = 44
    sx = int(S / 2 - (ws + gap + wt) / 2)
    return sx, ws, sx + ws + gap, wt


def L_subtitle2(cfg):
    l = new_canvas()
    fs = F(FT_HEAVY, 64)
    sx, ws, _, _ = _sub_positions(cfg)
    box = Image.new("RGBA", (ws, 102), (0, 0, 0, 0))
    d = ImageDraw.Draw(box)
    d.rounded_rectangle([0, 0, ws - 1, 101], radius=18, fill=C("yellow"))
    d.text((ws / 2, 51), cfg["subtitle"], font=fs, fill=C("ink"), anchor="mm")
    l.alpha_composite(box, (sx, 878))
    return l


def L_badge(cfg):
    l = new_canvas()
    ft = F(FT_BOLD, 46)
    _, _, tx, wt = _sub_positions(cfg)
    box = Image.new("RGBA", (wt, 82), (0, 0, 0, 0))
    d = ImageDraw.Draw(box)
    d.rounded_rectangle([2, 2, wt - 3, 79], radius=14, outline=C("cyan"), width=4)
    d.text((wt / 2, 41), cfg["badge"], font=ft, fill=C("cyan"), anchor="mm")
    l.alpha_composite(box, (tx, 888))
    return l


# ---------------- 课件卡片（放大撑满） ----------------
def L_content(cfg):
    l = new_canvas()
    rows = cfg["content_rows"]
    x0, y0, x1, y1 = 200, 990, 1800, 1490
    box = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
    d = ImageDraw.Draw(box)
    d.rounded_rectangle([0, 0, x1 - x0 - 1, y1 - y0 - 1], radius=26, fill=C("white"))
    d.rounded_rectangle([2, 2, x1 - x0 - 3, y1 - y0 - 3], radius=24, outline=C("yellow"), width=5)
    d.text((48, 44), cfg["content_title"], font=F(FT_HEAVY, 58), fill=C("red"), anchor="lt")
    d.text((x1 - x0 - 48, 76), cfg["content_meta"], font=F(FT_REG, 40), fill=C("mute"), anchor="rm")
    d.line([(48, 142), (x1 - x0 - 48, 142)], fill=(224, 230, 240), width=2)

    inner_r = x1 - x0 - 48       # 卡片内容右边界
    text_x = 112                 # 名称起始
    size = 48                    # 自适应缩小，保证名称+后缀撑满且不溢出
    while size > 34:
        f = F(FT_BOLD, size)
        wsum = max((f.getlength(r[0]) + (f.getlength(r[1]) if len(r) > 1 else 0) for r in rows
                    if isinstance(r, (list, tuple))), default=0)
        if text_x + wsum + 70 <= inner_r:
            break
        size -= 1
    fn = F(FT_BOLD, size)
    for i, row in enumerate(rows):
        name, suffix = (row if isinstance(row, (list, tuple)) else (row, ""))
        cy = 216 + i * 90
        d.rounded_rectangle([48, cy - 16, 84, cy + 16], radius=10, fill=C("red"))
        d.line([(58, cy), (68, cy + 9), (78, cy - 10)], fill=C("white"), width=6)
        d.text((text_x, cy), name, font=fn, fill=C("ink"), anchor="lm")
        if suffix:
            d.text((inner_r, cy), suffix, font=fn, fill=C("mute"), anchor="rm")
    d.text((48, 452), cfg["content_note"], font=F(FT_REG, 38), fill=C("mute"), anchor="lm")
    l.alpha_composite(box, (x0, y0))
    return l


# ---------------- 价格区 ----------------
def dash_rect(d, box, radius, color, width, dash, gap):
    x0, y0, x1, y1 = box
    for a, b in [((x0 + radius, y0), (x1 - radius, y0)), ((x0 + radius, y1), (x1 - radius, y1)),
                 ((x0, y0 + radius), (x0, y1 - radius)), ((x1, y0 + radius), (x1, y1 - radius))]:
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
        t = 0
        while t < length:
            e = min(t + dash, length)
            d.line([(a[0] + ux * t, a[1] + uy * t), (a[0] + ux * e, a[1] + uy * e)],
                   fill=color, width=width)
            t = e + gap
    for cxx, cyy, s in [(x0 + radius, y0 + radius, 90), (x1 - radius, y0 + radius, 0),
                        (x0 + radius, y1 - radius, 180), (x1 - radius, y1 - radius, 270)]:
        d.arc([cxx - radius, cyy - radius, cxx + radius, cyy + radius], s, s + 90,
              fill=color, width=width)


def big_price(layer, value, unit_size, num_size, cx, cy):
    fn = text_img(value, F(FT_TITLE, num_size), C("red"))
    fu = text_img("元", F(FT_TITLE, unit_size), C("yellow"))
    total = fn.size[0] + 14 + fu.size[0]
    x = cx - total / 2
    layer.alpha_composite(fn, (int(x), int(cy - fn.size[1] / 2)))
    layer.alpha_composite(fu, (int(x + fn.size[0] + 14), int(cy - fu.size[1] / 2)))


def L_price(cfg, with_qr):
    l = new_canvas()
    if with_qr:
        x = 300
        lb = text_img(cfg["price_group"], F(FT_HEAVY, 60), C("light"))
        l.alpha_composite(lb, (x, int(1568 - lb.size[1] / 2)))
        num = text_img(cfg["price_value"], F(FT_TITLE, 176), C("red"))
        unit = text_img("元", F(FT_TITLE, 92), C("yellow"))
        cy = 1690
        l.alpha_composite(num, (x, int(cy - num.size[1] / 2)))
        l.alpha_composite(unit, (x + num.size[0] + 14, int(cy - unit.size[1] / 2)))
        if cfg["price_single"]:
            add = text_img(cfg["price_single"], F(FT_BOLD, 44), C("mute"))
            l.alpha_composite(add, (x, int(1802 - add.size[1] / 2)))
            ImageDraw.Draw(l).line([(x, 1802), (x + add.size[0], 1802)],
                                   fill=C("mute") + (170,), width=3)
        qx, qy, qs = 1448, 1524, 268
        qb = Image.new("RGBA", (qs, qs), (0, 0, 0, 0))
        dq = ImageDraw.Draw(qb)
        dq.rounded_rectangle([0, 0, qs - 1, qs - 1], radius=20, fill=C("white"))
        dash_rect(dq, (7, 7, qs - 8, qs - 8), 16, C("mute"), 4, 16, 12)
        l.alpha_composite(qb, (qx, qy))
        put(l, text_img("码上获取", F(FT_HEAVY, 48), C("yellow")), qx + qs / 2, 1838)
    else:
        put(l, text_img("仅售", F(FT_HEAVY, 72), C("white")), 690, 1660)
        big_price(l, cfg["only_price"], 112, 218, 1180, 1660)
        if cfg["only_sub"]:
            put(l, text_img(cfg["only_sub"], F(FT_BOLD, 46), C("light")), S / 2, 1798)
    return l


def L_claim(cfg):
    l = new_canvas()
    put(l, text_img(cfg["claim"], F(FT_BOLD, 44), C("light")), S / 2, 1906)
    return l


def L_footer(cfg):
    l = new_canvas()
    put(l, text_img(cfg["footer"], F(FT_REG, 32), C("track")), S / 2, 1956)
    return l


def check_copy(cfg):
    texts = []
    def walk(v):
        if isinstance(v, str):
            texts.append(v)
        elif isinstance(v, (list, tuple)):
            for x in v:
                walk(x)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
    walk(cfg)
    hits = {}
    for w in BANNED_WORDS:
        for t in texts:
            if w in t:
                hits.setdefault(w, []).append(t)
    return hits


def build(cfg, with_qr):
    return [
        ("背景-渐变", L_bg()),
        ("背景-地域元素", L_motif(cfg["motif"])),
        ("背景-水纹", L_water()),
        ("顶部细线", L_rule()),
        ("中公教育logo", L_logo(cfg)),
        ("项目标签", L_project(cfg)),
        ("公告名词", L_notice(cfg)),
        ("主标题", L_title(cfg)),
        ("电子课件标签", L_badge(cfg)),
        ("副标题", L_subtitle2(cfg)),
        ("课件内容卡片", L_content(cfg)),
        ("价格区", L_price(cfg, with_qr)),
        ("领取说明", L_claim(cfg)),
        ("底部课件全称", L_footer(cfg)),
    ]


def flatten(layers):
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    for _, im in layers:
        out.alpha_composite(im)
    return out


def save_psd(layers, path):
    from pytoshop.user import nested_layers as nl
    from pytoshop import enums, image_data
    psd_layers = []
    for name, im in layers:
        a = np.array(im.convert("RGBA"))
        psd_layers.append(nl.Image(name=name, visible=True, opacity=255, group_id=0,
                                   blend_mode=enums.BlendMode.normal, top=0, left=0,
                                   channels={0: a[..., 0], 1: a[..., 1], 2: a[..., 2], -1: a[..., 3]}))
    psd = nl.nested_layers_to_psd(psd_layers, color_mode=enums.ColorMode.rgb,
                                  size=(S, S), compression=enums.Compression.zip)
    arr = np.array(flatten(layers).convert("RGB"))
    psd.image_data = image_data.ImageData(
        channels=np.stack([arr[..., 0], arr[..., 1], arr[..., 2]]),
        compression=enums.Compression.zip)
    with open(path, "wb") as f:
        psd.write(f)


def main():
    global S, PAL
    cfg = dict(CONFIG)
    args = sys.argv[1:]
    if "--config" in args:
        with open(args[args.index("--config") + 1], encoding="utf-8") as fh:
            cfg.update(json.load(fh))
    PAL.update(cfg.get("palette", {}))
    S = cfg.get("size", 2000)
    os.makedirs(cfg["out_dir"], exist_ok=True)

    hits = check_copy({k: v for k, v in cfg.items() if k != "palette"})
    if hits:
        print("!! 违规广告词命中：")
        for k, v in hits.items():
            print("   ", k, "->", v)
    else:
        print("OK 文案自检通过（无违规词，无“资料”）")

    for with_qr, suffix in [(True, "有二维码"), (False, "无二维码")]:
        layers = build(cfg, with_qr)
        flat = flatten(layers).convert("RGB")
        p = os.path.join(cfg["out_dir"], f"{cfg['base_name']}_{suffix}.jpg")
        flat.save(p, quality=95, subsampling=0)
        flat.resize((1000, 1000), Image.LANCZOS).save(
            os.path.join(tempfile.gettempdir(), f"zg_preview_{suffix}.jpg"), quality=88)
        print("JPG", p)
        if "--psd" in args and with_qr:
            psd = os.path.join(cfg["out_dir"], f"{cfg['base_name']}.psd")
            save_psd(layers, psd)
            print("PSD", psd)


if __name__ == "__main__":
    main()
