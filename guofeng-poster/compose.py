#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
guofeng-poster / compose.py
把精确的中文矢量文字叠加到 AI 生成的国风海报底图「左侧 30% 文字栏」。
原因：文生图模型直接出中文必然乱码，所以左侧所有中文一律用 PIL 矢量渲染。

用法：
  python compose.py --image base.png --spec spec.json --out poster.png
  python compose.py --image base.png --spec spec.json --out poster.png --panel-ratio 0.30

spec.json 字段（全部可选，缺省留空字符串）：
  year            年份，如 "2026"
  city_impression 四字城市印象（方形印章，2x2）
  en_city         竖排英文城市名，如 "SUZHOU · CHINA"
  main_title      四字中文主标题（竖排行楷）
  china_city      椭圆印章，如 "中国苏州"
  subtitle        副标题数组（2~3 行）
  intro_cn        中文简介数组（最多 4 行）
  en_location     小号英文，如 "SUZHOU, JIANGSU, CHINA"
  en_intro        英文简介数组（2 行）
  summary_cn      底部中文总结，如 "江南雅韵 · 园林之城"
  summary_en      底部英文总结短句
  icon            线描图标类型：pagoda(塔)/mountain(山水)/bridge(桥)/leaf(花叶)/lantern(灯)
                 默认按城市自动，这里可显式指定
字体：优先使用 Windows 自带中文字体；缺失时回退到微软雅黑。
"""
import argparse
import json
import os
import random

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

FONT_DIR = os.environ.get("GF_POSTER_FONT_DIR", "C:/Windows/Fonts")

# 候选字体（存在即用，缺省回退）
def _f(name, alt=None):
    p = os.path.join(FONT_DIR, name)
    if os.path.exists(p):
        return p
    return os.path.join(FONT_DIR, alt) if alt and os.path.exists(os.path.join(FONT_DIR, alt)) else p

F_PATHS = {
    "yahei":   _f("msyh.ttc"),
    "yahei_b": _f("msyhbd.ttc"),
    "song":    _f("simsun.ttc", "msyh.ttc"),
    "kai":     _f("simkai.ttf", "msyh.ttc"),
    "xingkai": _f("STXINGKA.TTF", "simkai.ttf"),   # 华文行楷（主标题书法感）
    "hei":     _f("simhei.ttf", "msyh.ttc"),
}

# 配色（东方宣纸 + 墨色 + 印泥朱红）
C_PAPER_TOP = (247, 240, 222)   # 暖象牙白（上）
C_PAPER_BOT = (251, 246, 233)   # 浅米白（下）
C_INK       = (28, 40, 33)       # 墨绿近黑（主标题）
C_INK_SOFT  = (45, 62, 52)       # 深绿（年份/副标题）
C_INK_BLUE  = (40, 56, 82)       # 深蓝
C_GREY      = (90, 90, 86)       # 英文灰
C_SEAL      = (168, 46, 38)      # 印泥朱红
C_GOLD      = (180, 150, 96)     # 金线分隔


def load_font(key, size):
    return ImageFont.truetype(F_PATHS[key], size)


def draw_spaced_text(draw, xy, text, font, fill, spacing=4, anchor="la"):
    """手动字距：逐字绘制，返回结束 x。anchor 默认左对齐起点。"""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill, anchor=anchor)
        bbox = draw.textbbox((x, y), ch, font=font, anchor=anchor)
        w = bbox[2] - bbox[0]
        x += w + spacing
    return x


def draw_vertical_cn(draw, x, y_top, text, font, fill, char_gap=6):
    """竖排中文（逐字向下，不旋转）。返回底部 y。"""
    y = y_top
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill, anchor="ma")
        h = draw.textbbox((x, y), ch, font=font, anchor="ma")[3] - draw.textbbox((x, y), ch, font=font, anchor="ma")[1]
        y += h + char_gap
    return y


def draw_vertical_en(draw, img, x, y_top, text, font, fill, char_gap=6):
    """竖排英文：每个字母顺时针旋转 90° 后自上而下堆叠（书脊式）。返回底部 y。"""
    y = y_top
    for ch in text:
        if ch == " ":
            y += font.size // 2
            continue
        tile = Image.new("L", (font.size, font.size), 0)
        d = ImageDraw.Draw(tile)
        d.text((font.size // 2, font.size // 2), ch, font=font, fill=255, anchor="mm")
        tile = tile.rotate(-90, expand=True, resample=Image.BICUBIC)
        w, h = tile.size
        mask = tile
        color_layer = Image.new("RGB", (w, h), fill)
        img.paste(color_layer, (x, y), mask)
        y += h + char_gap
    return y


def draw_seal_square(draw, xy, size, text, fill=C_SEAL):
    """朱红圆角方形印章，4 字 2x2。返回底部 y。"""
    x, y = xy
    # 印泥底
    draw.rounded_rectangle([x, y, x + size, y + size], radius=size * 0.12, fill=fill)
    # 内描边
    draw.rounded_rectangle([x + 4, y + 4, x + size - 4, y + size - 4],
                           radius=size * 0.1, outline=(255, 240, 235), width=2)
    f = load_font("hei", int(size * 0.30))
    chars = list(text[:4])
    while len(chars) < 4:
        chars.append(" ")
    positions = [(x + size/4, y + size/4), (x + 3*size/4, y + size/4),
                 (x + size/4, y + 3*size/4), (x + 3*size/4, y + 3*size/4)]
    for ch, (cx, cy) in zip(chars, positions):
        if ch.strip():
            draw.text((cx, cy), ch, font=f, fill=(255, 244, 240), anchor="mm")
    return y + size


def draw_seal_oval(draw, xy, w, h, text, fill=C_SEAL):
    """朱红椭圆印章，横排文字（如「中国苏州」）。返回底部 y。"""
    x, y = xy
    draw.ellipse([x, y, x + w, y + h], fill=fill)
    draw.ellipse([x + 3, y + 3, x + w - 3, y + h - 3], outline=(255, 240, 235), width=2)
    f = load_font("hei", int(h * 0.42))
    draw.text((x + w/2, y + h/2), text[:6], font=f, fill=(255, 244, 240), anchor="mm")
    return y + h


def draw_line_icon(draw, xy, size, kind="pagoda"):
    """极简线描地标图标（单色细线）。返回底部 y。"""
    x, y = xy
    c = C_INK_SOFT
    w = size
    if kind in ("mountain", "山水"):
        draw.line([(x, y + w*0.7), (x + w*0.35, y + w*0.25), (x + w*0.55, y + w*0.55),
                   (x + w*0.78, y + w*0.2), (x + w, y + w*0.7)], fill=c, width=3)
        draw.line([(x + w*0.1, y + w*0.7), (x + w*0.9, y + w*0.7)], fill=c, width=3)
    elif kind in ("bridge", "桥"):
        draw.arc([x, y + w*0.2, x + w, y + w*0.9], start=180, end=360, fill=c, width=3)
        for i in range(1, 4):
            px = x + w*i/4
            draw.line([(px, y + w*0.55), (px, y + w*0.7)], fill=c, width=3)
        draw.line([(x, y + w*0.7), (x + w, y + w*0.7)], fill=c, width=3)
    elif kind in ("leaf", "花叶"):
        draw.ellipse([x + w*0.2, y, x + w*0.8, y + w*0.7], outline=c, width=3)
        draw.line([(x + w*0.5, y), (x + w*0.5, y + w*0.7)], fill=c, width=3)
        draw.line([(x + w*0.5, y + w*0.7), (x + w*0.5, y + w)], fill=c, width=3)
    elif kind in ("lantern", "灯"):
        draw.ellipse([x + w*0.25, y + w*0.1, x + w*0.75, y + w*0.6], outline=c, width=3)
        draw.line([(x + w*0.5, y), (x + w*0.5, y + w*0.1)], fill=c, width=3)
        draw.line([(x + w*0.5, y + w*0.6), (x + w*0.5, y + w*0.8)], fill=c, width=3)
    else:  # pagoda / 塔（默认）
        # 三层塔
        base_y = y + w
        for i, (ty, tw) in enumerate([(0.0, 1.0), (0.28, 0.78), (0.52, 0.56)]):
            top = y + w*ty
            bw = w*tw
            bx = x + (w - bw)/2
            draw.line([(bx, top + w*0.18), (x + w/2, top), (bx + bw, top + w*0.18)], fill=c, width=3)
            draw.line([(bx, top + w*0.18), (bx + bw, top + w*0.18)], fill=c, width=3)
            draw.line([(bx + bw*0.15, top + w*0.18), (bx + bw*0.15, base_y)], fill=c, width=3)
            draw.line([(bx + bw*0.85, top + w*0.18), (bx + bw*0.85, base_y)], fill=c, width=3)
    return y + w


def build_paper_panel(W, H, panel_w, edge=26, seed=7):
    """生成左侧暖白宣纸面板（RGBA），右缘羽化以自然融入右侧画面。"""
    random.seed(seed)
    # 竖向渐变（1×H 再拉伸，快）
    grad = Image.new("RGB", (1, H))
    gp = grad.load()
    for yy in range(H):
        t = yy / H
        r = int(C_PAPER_TOP[0] + (C_PAPER_BOT[0] - C_PAPER_TOP[0]) * t)
        g = int(C_PAPER_TOP[1] + (C_PAPER_BOT[1] - C_PAPER_TOP[1]) * t)
        b = int(C_PAPER_TOP[2] + (C_PAPER_BOT[2] - C_PAPER_TOP[2]) * t)
        gp[0, yy] = (r, g, b)
    grad = grad.resize((panel_w, H))

    # 细微纸张噪声（小图生成再拉伸，快）。瓦片长宽比要接近面板，避免纵向拉丝。
    nw, nh = 64, 320
    small = Image.new("L", (nw, nh))
    sp = small.load()
    for yy in range(nh):
        for xx in range(nw):
            sp[xx, yy] = random.randint(122, 134)  # 围绕 128 的轻噪声
    grain = small.resize((panel_w, H)).convert("RGB")
    # offset=-128 使噪声围绕 0（-10..+10），再叠加到渐变上
    grad = ImageChops.add(grad, grain, scale=1.0, offset=-128)

    panel = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    panel.paste(grad, (0, 0))
    panel_alpha = Image.new("L", (W, H), 0)
    panel_alpha.paste(Image.new("L", (panel_w, H), 255), (0, 0))
    pa = panel_alpha.load()
    for xx in range(panel_w - edge, panel_w):
        a = int(255 * (panel_w - xx) / edge)
        for yy in range(H):
            pa[xx, yy] = a
    panel.putalpha(panel_alpha)
    return panel


def _text_w(draw, text, font, spacing=0):
    if spacing:
        w = 0
        for ch in text:
            w += draw.textlength(ch, font=font) + spacing
        return w
    return draw.textlength(text, font=font)


def fit_font_size(draw, key, text, max_w, start, min_size=9, spacing=0):
    """返回能放进 max_w 的最大字号（逐级缩小，保证不溢出文字栏）。"""
    size = start
    while size > min_size:
        f = load_font(key, size)
        if _text_w(draw, text, f, spacing) <= max_w:
            return f
        size -= 1
    return load_font(key, min_size)


def wrap_words(draw, text, font, max_w):
    """按词换行。"""
    words = text.split()
    lines, cur = [], ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        if _text_w(draw, trial, font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def wrap_fit_en(draw, text, max_w, start, max_lines=3, min_size=10):
    """英文自动缩字号 + 换行，控制行数 <= max_lines。返回 (font, lines)。"""
    size = start
    while size > min_size:
        f = load_font("yahei", size)
        lines = wrap_words(draw, text, f, max_w)
        if len(lines) <= max_lines:
            return f, lines
        size -= 1
    f = load_font("yahei", min_size)
    return f, wrap_words(draw, text, f, max_w)


def compose(image_path, spec, out_path, panel_ratio=0.30):
    base = Image.open(image_path).convert("RGB")
    W, H = base.size
    panel_w = int(round(W * panel_ratio))

    # 1) 铺左侧宣纸面板（羽化）
    panel = build_paper_panel(W, H, panel_w)
    base.paste(panel, (0, 0), panel)

    # 2) 金线分隔（杂志栏边缘）
    d = ImageDraw.Draw(base)
    d.line([(panel_w - 3, int(H*0.06)), (panel_w - 3, int(H*0.94))],
           fill=C_GOLD, width=2)

    # 文字区边距
    m = int(panel_w * 0.10)
    inner_w = panel_w - 2 * m
    cx = m  # 左对齐基线
    y = int(H * 0.045)

    # —— 年份 ——
    year = (spec.get("year") or "").strip()
    if year:
        f_year = load_font("song", max(20, int(panel_w*0.085)))
        draw_spaced_text(d, (cx, y), year, f_year, C_INK_SOFT, spacing=max(2, int(panel_w*0.02)))
        y += int(panel_w*0.16)

    # —— 方形印章（四字城市印象）——
    imp = (spec.get("city_impression") or "").strip()
    if imp:
        sz = int(panel_w * 0.24)
        y = draw_seal_square(d, (cx, y), sz, imp) + int(panel_w*0.05)

    # —— 竖排英文城市名 + 四字中文主标题（并排）——
    en_city = (spec.get("en_city") or "").strip()
    main_title = (spec.get("main_title") or "").strip()
    en_x = cx + int(panel_w*0.02)
    title_x = cx + int(panel_w*0.30)
    band_top = y + int(panel_w*0.04)
    if en_city:
        f_en = load_font("yahei", max(16, int(panel_w*0.075)))
        draw_vertical_en(d, base, en_x, band_top, en_city, f_en, C_GREY, char_gap=max(3, int(panel_w*0.015)))
    if main_title:
        f_title = load_font("xingkai", max(40, int(panel_w*0.30)))
        bottom = draw_vertical_cn(d, title_x, band_top, main_title[:4], f_title, C_INK, char_gap=int(panel_w*0.02))
        y = max(y, bottom)
    y = band_top + int(panel_w*0.05) + (int(panel_w*0.30)*4 if main_title else int(panel_w*0.4))

    # —— 椭圆印章（中国+城市）——
    china_city = (spec.get("china_city") or "").strip()
    if china_city:
        ew = int(panel_w*0.36)
        eh = int(panel_w*0.13)
        y = draw_seal_oval(d, (cx, y), ew, eh, china_city) + int(panel_w*0.06)

    # —— 副标题（宋体，2~3 行）——
    subs = spec.get("subtitle") or []
    if subs:
        f_sub = fit_font_size(d, "song", max(subs[:3], key=len),
                              inner_w, max(20, int(panel_w*0.095)))
        for line in subs[:3]:
            d.text((cx, y), line, font=f_sub, fill=C_INK_SOFT, anchor="la")
            y += int(panel_w*0.14)
        y += int(panel_w*0.02)

    # —— 中文简介（小宋体，≤4 行）——
    intro = spec.get("intro_cn") or []
    if intro:
        f_intro = fit_font_size(d, "song", max(intro[:4], key=len),
                                inner_w, max(15, int(panel_w*0.07)))
        for line in intro[:4]:
            d.text((cx, y), line, font=f_intro, fill=(60, 60, 56), anchor="la")
            y += int(panel_w*0.105)
        y += int(panel_w*0.03)

    # —— 线描图标 ——
    icon = (spec.get("icon") or "pagoda").strip()
    y = draw_line_icon(d, (cx, y), int(panel_w*0.22), kind=icon) + int(panel_w*0.04)

    # —— 小号英文地点 ——
    en_loc = (spec.get("en_location") or "").strip()
    if en_loc:
        sp = max(1, int(panel_w*0.01))
        f_el = fit_font_size(d, "yahei", en_loc, inner_w, max(13, int(panel_w*0.058)), spacing=sp)
        draw_spaced_text(d, (cx, y), en_loc, f_el, C_GREY, spacing=sp)
        y += int(panel_w*0.10)

    # —— 英文简介（自动换行 + 缩字号，最多 3 行）——
    en_intro = spec.get("en_intro") or []
    if en_intro:
        text = " ".join(en_intro[:2])
        f_ei, lines = wrap_fit_en(d, text, inner_w, max(12, int(panel_w*0.055)), max_lines=3)
        for line in lines:
            d.text((cx, y), line, font=f_ei, fill=(95, 95, 90), anchor="la")
            y += int(f_ei.size * 1.35)

    # —— 底部中英文总结 ——
    y_bottom = H - int(panel_w*0.16)
    sum_cn = (spec.get("summary_cn") or "").strip()
    sum_en = (spec.get("summary_en") or "").strip()
    if sum_cn:
        f_sc = fit_font_size(d, "song", sum_cn, inner_w, max(17, int(panel_w*0.078)))
        d.text((cx, y_bottom), sum_cn, font=f_sc, fill=C_INK, anchor="la")
    if sum_en:
        f_se = fit_font_size(d, "yahei", sum_en, inner_w, max(12, int(panel_w*0.05)))
        d.text((cx, y_bottom + int(panel_w*0.11)), sum_en, font=f_se, fill=C_GREY, anchor="la")

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    base.save(out_path, "PNG")
    print(f"OK saved -> {out_path}  ({W}x{H}, panel={panel_w}px)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--panel-ratio", type=float, default=0.30)
    args = ap.parse_args()
    with open(args.spec, "r", encoding="utf-8") as f:
        spec = json.load(f)
    compose(args.image, spec, args.out, args.panel_ratio)


if __name__ == "__main__":
    main()
