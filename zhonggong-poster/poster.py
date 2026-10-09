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
import os, sys, math, json, zlib, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import xiaolu
import styles

# ============================================================
# CONFIG —— 每个新任务只改这里
# ============================================================
HERE = os.path.dirname(os.path.abspath(__file__))   # 技能包根目录（素材均相对此定位）
CONFIG = {
    # 输出目录：默认 <当前工作目录>/海报成品，可用环境变量 ZG_OUT_DIR 覆盖
    "out_dir": os.environ.get("ZG_OUT_DIR", os.path.join(os.getcwd(), "海报成品")),
    "base_name": "海珠事编笔试冲刺卷课件包",
    "size": 2000,

    # 顶部
    # logo：默认 <技能目录>/assets/zhonggong-logo.png，可用环境变量 ZG_LOGO 覆盖
    "logo_path": os.environ.get("ZG_LOGO", os.path.join(HERE, "assets", "zhonggong-logo.png")),
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

    # 小鹿lulu形象（底层规则：默认开启；按考试类型随机匹配形象与留白落点）
    "xiaolu": {
        "enable": True,
        "exam_type": "备考",   # 备考 / 公安军警 / 基层乡村 / 面试 / 金融国企 / 活动福利
        # "seed": 12345,       # 不填则按 base_name 自动定种，保证可复现
    },

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


def fg_on(color):
    """在给定底色上选可读的文字色：亮底（如鎏金）用墨蓝，深底用白。"""
    r, g, b = color[:3]
    return C("ink") if (0.299 * r + 0.587 * g + 0.114 * b) > 170 else C("white")


def accent_deep(color):
    """白底卡片上的强调色：亮色（鎏金）压暗成古铜，保证白底可读。"""
    r, g, b = color[:3]
    if (0.299 * r + 0.587 * g + 0.114 * b) > 170:
        return (int(r * 0.62), int(g * 0.62), int(b * 0.62))
    return color


def card_line():
    """内容卡描边色：配色里给了 cardline 就用它（鎏金套用饱和金更大气）。"""
    return PAL.get("cardline", PAL["yellow"])


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
    bg.alpha_composite(glow(1500, 700, 800, PAL.get("glow3", (90, 140, 255)), 0.20))
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
    elif motif == "huizhou":
        # 惠州 · 合江楼（三层飞檐楼阁）+ 东江拱桥，纯代码原创矢量
        cx, base = 1652, 1580
        tier_w, tier_h = [300, 250, 200], [300, 262, 232]
        y = base
        for i in range(3):
            w, h = tier_w[i], tier_h[i]
            ytop = y - h
            dr.rectangle([cx - w * 0.58, ytop + 26, cx + w * 0.58, y],
                         outline=line_c + (78,), width=3)
            for k in range(1, 4):
                yy = ytop + 26 + (y - ytop - 26) * k / 4
                dr.line([(cx - w * 0.58, yy), (cx + w * 0.58, yy)], fill=line_c + (42,), width=2)
            pts = [(cx - w, ytop + 44), (cx - w * 0.74, ytop + 8), (cx, ytop - 10),
                   (cx + w * 0.74, ytop + 8), (cx + w, ytop + 44)]
            dr.line(pts, fill=line_c + (96,), width=5, joint="curve")
            dr.line([(cx - w, ytop + 44), (cx - w, ytop + 74)], fill=line_c + (62,), width=3)
            dr.line([(cx + w, ytop + 44), (cx + w, ytop + 74)], fill=line_c + (62,), width=3)
            y = ytop
        dr.polygon([(cx - 200, y - 10), (cx, y - 258), (cx + 200, y - 10)],
                   outline=line_c + (96,))
        dr.line([(cx, y - 258), (cx, y - 330)], fill=C("yellow") + (84,), width=6)
        dr.ellipse([cx - 16, y - 366, cx + 16, y - 330], outline=C("yellow") + (90,), width=5)
        dr.arc([120, 1180, 980, 1820], 200, 340, fill=line_c + (46,), width=4)
    elif motif == "zhuhai":
        # 珠海 · 日月贝（珠海大剧院）：一大一小两片扇贝立于海上，纯代码原创矢量。
        # 细扇面从水纹区向上收窄，穿过卡片右缘在标题带留白处收尾，低透明度做纹理。
        def shell(cx, base, r, a0, a1, ribs, edge_al=64):
            # 同心圆弧（贝壳生长纹），圆心=基足点
            for rr, al in ((r, edge_al), (int(r * 0.78), 40), (int(r * 0.56), 34),
                           (int(r * 0.34), 30), (int(r * 0.12), 26)):
                dr.arc([cx - rr, base - rr, cx + rr, base + rr],
                       a0, a1, fill=line_c + (al,), width=3)
            # 基足向外发散的放射肋
            for k in range(1, ribs):
                a = math.radians(a0 + (a1 - a0) * k / ribs)
                dr.line([(cx, base), (cx + r * math.cos(a), base + r * math.sin(a))],
                        fill=C("yellow") + (38,), width=2)
        shell(1608, 1786, 1052, 240, 300, 7)   # 大贝（日贝）
        shell(1858, 1814, 742, 242, 298, 5)    # 小贝（月贝），略前略低
        for k in range(3):                      # 贝下海面微光
            y = 1700 + k * 34
            dr.arc([1080 + k * 90, y - 70, 2000 - k * 30, y + 70],
                   200, 340, fill=line_c + (44 - k * 10,), width=2)
    elif motif == "guokao":
        # 国考·鎏金大气（全原创矢量）：顶部放射光芒 + 中心鎏金光晕 +
        # 右上星轨同心弧 + 左右鎏金光点 + 四角鎏金角标
        gold = C("red")
        ox, oy = S / 2, 150
        for i in range(0, 61, 2):                       # 向下扇面光芒
            a = math.radians(180 * i / 60)
            dr.line([(ox, oy), (ox + math.cos(a) * 1450, oy + math.sin(a) * 1450)],
                    fill=gold + (20,), width=2)
        for r, al in ((430, 36), (520, 26), (610, 18)):  # 中心鎏金光晕
            dr.arc([ox - r, oy - r, ox + r, oy + r], 8, 172, fill=gold + (al,), width=3)
        for r in range(300, 1080, 96):                   # 右上星轨同心弧
            dr.arc([1960 - r, 30 - r, 1960 + r, 30 + r], 116, 300, fill=line_c + (30,), width=2)
        for x, y, r in ((120, 980, 9), (96, 1160, 6), (150, 1330, 7),
                        (1880, 1010, 7), (1912, 1210, 9), (1856, 1380, 6)):
            dr.ellipse([x - r, y - r, x + r, y + r], fill=gold + (70,))
        L, m, t = 132, 44, 5                             # 四角鎏金角标
        for cx_, cy_, sx, sy in ((m, m, 1, 1), (S - m, m, -1, 1),
                                 (m, S - m, 1, -1), (S - m, S - m, -1, -1)):
            dr.line([(cx_, cy_), (cx_ + sx * L, cy_)], fill=gold + (115,), width=t)
            dr.line([(cx_, cy_), (cx_, cy_ + sy * L)], fill=gold + (115,), width=t)
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
    d.ellipse([26, h // 2 - 7, 40, h // 2 + 7], fill=fg_on(C("red")))
    d.text((62, h // 2), tag, font=f, fill=fg_on(C("red")), anchor="lm")
    l.alpha_composite(box, (S - w - 96, 90))
    return l


def L_rule():
    l = new_canvas()
    ImageDraw.Draw(l).line([(96, 250), (S - 96, 250)], fill=C("white") + (58,), width=2)
    return l


def L_notice(cfg):
    """公告名词：可按 title_width 反算字距，使抬头小标题与大标题同宽。"""
    l = new_canvas()
    f = F(FT_REG, cfg.get("notice_size", 42))
    txt = cfg["notice"]
    ws = [f.getlength(ch) for ch in txt]
    track = 0.0
    if cfg.get("notice_fill") and len(ws) > 1:
        track = (cfg.get("title_width", 1600) - sum(ws)) / (len(ws) - 1)
    total = sum(ws) + track * (len(ws) - 1)
    x = S / 2 - total / 2
    cy = cfg.get("notice_y", 296)
    for ch, w in zip(txt, ws):
        im = text_img(ch, f, C("light"))
        l.alpha_composite(im, (int(x), int(cy - im.size[1] / 2)))
        x += w + track
    return l


# ---------------- 主标题（无 kicker，字距放宽） ----------------
def L_title(cfg):
    l = new_canvas()
    cx = S / 2
    target = cfg.get("title_width", 1600)
    sw_white = PAL.get("stroke_w", (30, 60, 150))     # 白字描边（深底衬托）
    sw_accent = PAL.get("stroke_r", (150, 52, 24))    # 强调字描边
    f1 = F(FT_TITLE, cfg.get("title_main_size", 238))
    tracked_segs(l, [(cfg["title_main"], C("white"), sw_white)], f1, cx,
                 cfg.get("title_main_y", 486), fit_track(cfg["title_main"], f1, target))
    f2 = F(FT_TITLE, cfg.get("title_sub_size", 198))
    segs = [(t, C("red") if k == "r" else C("white"),
             sw_accent if k == "r" else sw_white)
            for t, k in cfg["title_sub"]]
    sub_text = "".join(t for t, _ in cfg["title_sub"])
    tracked_segs(l, segs, f2, cx, cfg.get("title_sub_y", 730), fit_track(sub_text, f2, target))
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
    l.alpha_composite(box, (sx, cfg.get("subtitle_y", 878)))
    return l


def L_badge(cfg):
    l = new_canvas()
    ft = F(FT_BOLD, 46)
    _, _, tx, wt = _sub_positions(cfg)
    box = Image.new("RGBA", (wt, 82), (0, 0, 0, 0))
    d = ImageDraw.Draw(box)
    d.rounded_rectangle([2, 2, wt - 3, 79], radius=14, outline=C("cyan"), width=4)
    d.text((wt / 2, 41), cfg["badge"], font=ft, fill=C("cyan"), anchor="mm")
    l.alpha_composite(box, (tx, cfg.get("subtitle_y", 878) + 10))
    return l


# ---------------- 课件卡片（行数自适应，撑满不溢出） ----------------
def L_content(cfg):
    l = new_canvas()
    rows = cfg["content_rows"]
    n = max(1, len(rows))
    bx0, by0, bx1, by1 = cfg.get("content_box", [200, 990, 1800, 1490])
    W, H = bx1 - bx0, by1 - by0
    box = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(box)
    d.rounded_rectangle([0, 0, W - 1, H - 1], radius=26, fill=C("white"))
    d.rounded_rectangle([2, 2, W - 3, H - 3], radius=24, outline=card_line(), width=5)
    d.text((48, 40), cfg["content_title"], font=F(FT_HEAVY, 58), fill=accent_deep(C("red")), anchor="lt")
    d.text((W - 48, 74), cfg["content_meta"], font=F(FT_REG, 40), fill=C("mute"), anchor="rm")
    d.line([(48, 134), (W - 48, 134)], fill=(224, 230, 240), width=2)

    inner_r = W - 48          # 卡片内容右边界
    text_x = 108              # 名称起始
    note_y = H - 42
    top, bottom = 170, note_y - 34
    step = (bottom - top) / n
    # 字号自适应：同时受「行高」与「名称+后缀总宽」约束，保证撑满且不溢出
    size = min(46, int(step * 0.78))
    while size > 22:
        f = F(FT_BOLD, size)
        wsum = max((f.getlength(r[0]) + (f.getlength(r[1]) if len(r) > 1 else 0)
                    for r in rows), default=0)
        if text_x + wsum + 60 <= inner_r:
            break
        size -= 1
    fn = F(FT_BOLD, size)
    for i, row in enumerate(rows):
        name, suffix = (row if isinstance(row, (list, tuple)) else (row, ""))
        cy = top + step * (i + 0.5)
        d.rounded_rectangle([48, cy - 15, 82, cy + 15], radius=9, fill=C("red"))
        d.line([(57, cy), (66, cy + 8), (75, cy - 9)], fill=fg_on(C("red")), width=5)
        d.text((text_x, cy), name, font=fn, fill=C("ink"), anchor="lm")
        if suffix:
            d.text((inner_r, cy), suffix, font=fn, fill=C("mute"), anchor="rm")
    d.text((48, note_y), cfg["content_note"], font=F(FT_REG, 38), fill=C("mute"), anchor="lm")
    l.alpha_composite(box, (bx0, by0))
    return l


# ---------------- 总图：左侧专项标签列 ----------------
def L_tabs(cfg):
    """总图专用：左侧一列专项彩色胶囊（勾选图标 + 专项名）。
    cfg 需给 tabs=[["专项名", (r,g,b)], ...]，可按需给 tabs_box。"""
    l = new_canvas()
    tabs = cfg.get("tabs") or []
    if not tabs:
        return l
    bx0, by0, bx1, by1 = cfg.get("tabs_box", [200, 930, 560, 1552])
    n = len(tabs)
    gap = 16
    h = (by1 - by0 - gap * (n - 1)) / n
    w = bx1 - bx0
    d = ImageDraw.Draw(l)
    for i, t in enumerate(tabs):
        name = t[0] if isinstance(t, (list, tuple)) else t
        col = tuple(t[1]) if isinstance(t, (list, tuple)) and len(t) > 1 else C("red")
        y0 = by0 + i * (h + gap)
        d.rounded_rectangle([bx0, y0, bx1, y0 + h], radius=18, fill=col)
        fg = fg_on(col)
        size = int(min(h * 0.42, (w - 108) / max(1, len(name))))
        cy = y0 + h / 2
        d.rounded_rectangle([bx0 + 26, cy - 17, bx0 + 60, cy + 17], radius=9, fill=fg)
        d.line([(bx0 + 35, cy), (bx0 + 44, cy + 9), (bx0 + 53, cy - 10)], fill=col, width=5)
        d.text((bx0 + 78, cy), name, font=F(FT_HEAVY, size), fill=fg, anchor="lm")
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
    dy = cfg.get("price_dy", 0)
    align = cfg.get("price_align", "left")
    m = cfg.get("price_margin", 300)

    def ax(block_w):
        if align == "left":
            return float(m)
        if align == "right":
            return float(S - m - block_w)
        return (S - block_w) / 2.0

    if with_qr:
        qx, qy, qs = cfg.get("qr_box", [1448, 1524 + dy, 268])
        lb = text_img(cfg["price_group"], F(FT_HEAVY, 60), C("light"))
        num = text_img(cfg["price_value"], F(FT_TITLE, 176), C("red"))
        unit = text_img("元", F(FT_TITLE, 92), C("yellow"))
        x = ax(max(lb.size[0], num.size[0] + 14 + unit.size[0]))
        cy = 1690 + dy
        l.alpha_composite(lb, (int(x), int(1568 + dy - lb.size[1] / 2)))
        l.alpha_composite(num, (int(x), int(cy - num.size[1] / 2)))
        l.alpha_composite(unit, (int(x + num.size[0] + 14), int(cy - unit.size[1] / 2)))
        if cfg["price_single"]:
            add = text_img(cfg["price_single"], F(FT_BOLD, 44), C("mute"))
            l.alpha_composite(add, (int(x), int(1802 + dy - add.size[1] / 2)))
            ImageDraw.Draw(l).line([(int(x), 1802 + dy), (int(x) + add.size[0], 1802 + dy)],
                                   fill=C("mute") + (170,), width=3)
        qb = Image.new("RGBA", (qs, qs), (0, 0, 0, 0))
        dq = ImageDraw.Draw(qb)
        dq.rounded_rectangle([0, 0, qs - 1, qs - 1], radius=20, fill=C("white"))
        dash_rect(dq, (7, 7, qs - 8, qs - 8), 16, C("mute"), 4, 16, 12)
        l.alpha_composite(qb, (qx, qy))
        put(l, text_img("码上获取", F(FT_HEAVY, 48), C("yellow")), qx + qs / 2, qy + qs + 40)
    else:
        lbl = text_img("仅售", F(FT_HEAVY, 72), C("white"))
        num = text_img(cfg["only_price"], F(FT_TITLE, 218), C("red"))
        unit = text_img("元", F(FT_TITLE, 112), C("yellow"))
        x = ax(lbl.size[0] + 34 + num.size[0] + 14 + unit.size[0])
        cy = 1660 + dy
        l.alpha_composite(lbl, (int(x), int(cy - lbl.size[1] / 2)))
        x2 = int(x + lbl.size[0] + 34)
        l.alpha_composite(num, (x2, int(cy - num.size[1] / 2)))
        l.alpha_composite(unit, (x2 + num.size[0] + 14, int(cy - unit.size[1] / 2)))
        if cfg["only_sub"]:
            put(l, text_img(cfg["only_sub"], F(FT_BOLD, 46), C("light")), S / 2, 1798 + dy)
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
    layers = [
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
    if cfg.get("tabs"):
        layers.insert(next(i for i, (n, _) in enumerate(layers)
                           if n == "课件内容卡片"), ("专项标签列", L_tabs(cfg)))
    return layers


def flatten(layers):
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    for _, im in layers:
        out.alpha_composite(im)
    return out


def _packbits_encode(data):
    """纯 Python 的 PackBits(RLE) 编码，逐行调用。"""
    if hasattr(data, "tobytes"):
        data = data.tobytes()
    data = bytes(data)
    out = bytearray()
    n = len(data)
    i = 0
    while i < n:
        run = 1
        while i + run < n and run < 128 and data[i + run] == data[i]:
            run += 1
        if run >= 2:
            out.append((256 - (run - 1)) & 0xFF)
            out.append(data[i])
            i += run
        else:
            j = i
            while j < n and (j - i) < 128:
                if j > i and j + 1 < n and data[j] == data[j + 1]:
                    break
                j += 1
            out.append(j - i - 1)
            out.extend(data[i:j])
            i = j
    return bytes(out)


def _ensure_packbits():
    """
    pytoshop 的 RLE 依赖未编译的 C 扩展 packbits，缺失时会退化成不可用。
    这里用纯 Python 实现兜底：合成图必须用 RLE 压缩，否则 macOS 预览 /
    Photoshop 会判定 PSD 打不开（ZIP 压缩的合成图不被 ImageIO 支持）。
    """
    from pytoshop import codecs
    if getattr(codecs, "packbits", None) is None:
        class _PurePackbits:
            encode = staticmethod(_packbits_encode)
        codecs.packbits = _PurePackbits


def save_psd(layers, path):
    """
    layers: [(名称, RGBA 图)]，顺序为【自下而上】——最底层在最前，背景类图层垫底。
    """
    from pytoshop.user import nested_layers as nl
    from pytoshop import enums, image_data
    _ensure_packbits()
    # 输入约定：自下而上（背景在最前）。稳定排序把「背景*」压到列表最前 = 最底层。
    bottom_to_top = sorted(
        layers, key=lambda it: 0 if it[0].startswith("背景") else 1)
    psd_layers = []
    # ⚠️ pytoshop 的 nested_layers_to_psd 内部已对图层列表做过一次 [::-1]，
    #    所以这里【绝对不能再反转】：按「自下而上」原序传入，写出的 PSD
    #    自上而下顺序才正确（背景落到最底层）。
    #    历史教训：这里多加一次 reversed() 会让整摞图层上下颠倒，背景被顶到最上面。
    for name, im in bottom_to_top:
        a = np.array(im.convert("RGBA"))
        psd_layers.append(nl.Image(name=name, visible=True, opacity=255, group_id=0,
                                   blend_mode=enums.BlendMode.normal, top=0, left=0,
                                   channels={0: a[..., 0], 1: a[..., 1], 2: a[..., 2], -1: a[..., 3]}))
    psd = nl.nested_layers_to_psd(psd_layers, color_mode=enums.ColorMode.rgb,
                                  size=(S, S), compression=enums.Compression.zip)
    arr = np.array(flatten(layers).convert("RGB"))
    psd.image_data = image_data.ImageData(
        channels=np.stack([arr[..., 0], arr[..., 1], arr[..., 2]]),
        compression=enums.Compression.rle)
    with open(path, "wb") as f:
        psd.write(f)


def main():
    global S, PAL
    over = {}
    args = sys.argv[1:]
    if "--config" in args:
        with open(args[args.index("--config") + 1], encoding="utf-8") as fh:
            over = json.load(fh)

    cfg = dict(CONFIG)
    cfg.update(over)
    pal_name = lay_name = None
    rot_state = None
    # 底层规则：每次出图配色与版式都必须换新（见 SKILL.md「配色与版式轮换规则」）
    if not cfg.get("no_rotate"):
        pal_name, lay_name, rot_state = styles.rotate(
            cfg.get("palette_name"), cfg.get("layout_name"), cfg.get("base_name", ""))
        cfg.update(styles.LAYOUTS[lay_name])   # 版式预设生效
        cfg.update(over)                       # 显式配置优先级最高，可覆盖版式预设
        if "palette" not in over:
            cfg["palette"] = styles.PALETTES[pal_name]
        cfg["palette_name"], cfg["layout_name"] = pal_name, lay_name
    if pal_name:
        print(f"配色：{pal_name} ｜ 版式：{lay_name}")

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

    xcfg = cfg.get("xiaolu") or {}
    x_on = xcfg.get("enable", True)
    x_seed = xcfg.get("seed")
    if x_seed is None:
        # 与配色/版式绑定：换了配色或版式，小鹿形象与落点也随之变化，避免每张雷同
        x_seed = zlib.crc32(
            f"{cfg['base_name']}|{cfg.get('palette_name','')}|{cfg.get('layout_name','')}"
            .encode("utf-8"))
    # 两版（有码/无码）一起建，落点取两版占用图并集 → 同一位置对两版都安全
    built = {q: build(cfg, q) for q in (True, False)}
    occ_all = xiaolu.occ_of(built[True], S) | xiaolu.occ_of(built[False], S)

    for with_qr, suffix in [(True, "有二维码"), (False, "无二维码")]:
        layers = built[with_qr]
        if x_on:
            layers, info = xiaolu.add(layers, xcfg.get("exam_type", "备考"),
                                      seed=x_seed, size=S, extra_occ=occ_all)
            if info:
                print(f"小鹿lulu形象：#{info['pose']['id']} {info['pose']['scene']} "
                      f"pos=({info['x']},{info['y']}) {info['w']}x{info['h']}")
            else:
                print("!! 小鹿未找到留白落点，已跳过")
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

    if pal_name:
        styles.commit(pal_name, lay_name, rot_state)


if __name__ == "__main__":
    main()
