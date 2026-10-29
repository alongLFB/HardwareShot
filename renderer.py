# -*- coding: utf-8 -*-
"""用 Pillow 把硬件配置渲染成长图(本机报告 / 双机对比图 / CPU与显卡天梯榜)。采用"显示列表"方式:先排版得到总高度,再一次性绘制。"""
import os
import re

from PIL import Image, ImageDraw, ImageFont

import market

SC = 2  # 输出放大倍数(逻辑宽 860px -> 实际 1720px,清晰度更好)

THEMES = {
    '科技蓝': dict(bg=(8, 62, 168), card=(13, 84, 212), card_border=(30, 102, 235),
                 text=(255, 255, 255), sub=(184, 212, 255), accent=(124, 214, 255),
                 divider=(44, 112, 232), hdr1=(0, 98, 255), hdr2=(0, 190, 255),
                 hdr_sub=(214, 234, 255), diff=(31, 108, 224), good=(34, 197, 94),
                 bar_bg=(8, 62, 168), chip=(22, 96, 228), ca=(103, 232, 249), cb=(251, 146, 60),
                 ca_pill_fg=(0, 84, 214), ca_pill_bg=(255, 255, 255),
                 cb_pill_fg=(255, 255, 255), cb_pill_bg=(249, 115, 22),
                 price_fg=(254, 240, 138), price_bg=(9, 52, 145)),

    '赛博朋克': dict(bg=(14, 15, 25), card=(23, 24, 39), card_border=(64, 52, 92),
                 text=(245, 248, 255), sub=(145, 148, 180), accent=(0, 240, 255),
                 divider=(44, 42, 70), hdr1=(225, 0, 105), hdr2=(0, 210, 255),
                 hdr_sub=(242, 228, 255), diff=(52, 25, 70), good=(0, 230, 150),
                 bar_bg=(16, 17, 30), chip=(40, 34, 68), ca=(0, 240, 255), cb=(255, 36, 125),
                 ca_pill_fg=(14, 15, 25), ca_pill_bg=(0, 240, 255),
                 cb_pill_fg=(255, 255, 255), cb_pill_bg=(255, 36, 125),
                 price_fg=(253, 224, 71), price_bg=(36, 30, 62)),

    'ROG电竞': dict(bg=(16, 17, 21), card=(26, 27, 34), card_border=(62, 28, 36),
                 text=(248, 249, 250), sub=(148, 152, 164), accent=(255, 38, 66),
                 divider=(46, 48, 60), hdr1=(195, 14, 42), hdr2=(48, 12, 22),
                 hdr_sub=(255, 204, 212), diff=(58, 18, 26), good=(34, 197, 94),
                 bar_bg=(16, 17, 22), chip=(46, 22, 30), ca=(255, 42, 72), cb=(245, 158, 11),
                 ca_pill_fg=(255, 255, 255), ca_pill_bg=(220, 20, 50),
                 cb_pill_fg=(16, 17, 21), cb_pill_bg=(245, 158, 11),
                 price_fg=(253, 224, 71), price_bg=(44, 22, 28)),

    '极客绿': dict(bg=(11, 15, 13), card=(18, 25, 21), card_border=(32, 54, 42),
                text=(240, 252, 245), sub=(128, 156, 140), accent=(0, 230, 118),
                divider=(30, 44, 36), hdr1=(8, 72, 44), hdr2=(0, 185, 95),
                hdr_sub=(196, 248, 220), diff=(24, 52, 36), good=(0, 230, 118),
                bar_bg=(13, 18, 15), chip=(24, 42, 32), ca=(0, 230, 118), cb=(56, 189, 248),
                ca_pill_fg=(11, 15, 13), ca_pill_bg=(0, 230, 118),
                cb_pill_fg=(11, 15, 13), cb_pill_bg=(56, 189, 248),
                price_fg=(253, 224, 71), price_bg=(22, 38, 30)),

    '黑金奢华': dict(bg=(18, 17, 16), card=(28, 26, 24), card_border=(62, 52, 40),
                 text=(250, 246, 238), sub=(162, 150, 135), accent=(234, 179, 8),
                 divider=(48, 44, 38), hdr1=(142, 96, 26), hdr2=(224, 168, 38),
                 hdr_sub=(255, 238, 204), diff=(48, 38, 22), good=(52, 211, 153),
                 bar_bg=(16, 15, 14), chip=(46, 38, 28), ca=(234, 179, 8), cb=(203, 213, 225),
                 ca_pill_fg=(18, 17, 16), ca_pill_bg=(234, 179, 8),
                 cb_pill_fg=(18, 17, 16), cb_pill_bg=(203, 213, 225),
                 price_fg=(253, 224, 71), price_bg=(44, 36, 24)),

    '深色': dict(bg=(15, 18, 28), card=(26, 31, 46), card_border=(42, 49, 70),
               text=(235, 240, 250), sub=(140, 152, 175), accent=(96, 165, 250),
               divider=(44, 51, 72), hdr1=(37, 99, 235), hdr2=(124, 58, 237),
               hdr_sub=(210, 225, 255), diff=(48, 38, 20), good=(34, 197, 94),
               bar_bg=(15, 18, 28), chip=(38, 45, 66), ca=(96, 165, 250), cb=(251, 146, 60),
               ca_pill_fg=(15, 18, 28), ca_pill_bg=(96, 165, 250),
               cb_pill_fg=(255, 255, 255), cb_pill_bg=(251, 146, 60),
               price_fg=(253, 224, 71), price_bg=(34, 41, 62)),

    '冰川极光': dict(bg=(238, 245, 252), card=(255, 255, 255), card_border=(216, 228, 242),
                 text=(16, 28, 46), sub=(96, 114, 140), accent=(14, 138, 232),
                 divider=(226, 236, 248), hdr1=(2, 132, 199), hdr2=(56, 189, 248),
                 hdr_sub=(224, 246, 255), diff=(232, 244, 255), good=(16, 185, 129),
                 bar_bg=(228, 238, 248), chip=(235, 244, 252), ca=(14, 138, 232), cb=(244, 63, 94),
                 ca_pill_fg=(255, 255, 255), ca_pill_bg=(14, 138, 232),
                 cb_pill_fg=(255, 255, 255), cb_pill_bg=(244, 63, 94),
                 price_fg=(180, 83, 9), price_bg=(254, 243, 199)),

    '浅色': dict(bg=(240, 244, 250), card=(255, 255, 255), card_border=(226, 232, 240),
               text=(24, 32, 48), sub=(108, 119, 140), accent=(22, 119, 255),
               divider=(230, 234, 242), hdr1=(22, 119, 255), hdr2=(0, 195, 255),
               hdr_sub=(225, 242, 255), diff=(254, 243, 199), good=(22, 163, 74),
               bar_bg=(236, 240, 247), chip=(238, 242, 249), ca=(37, 99, 235), cb=(234, 88, 12),
               ca_pill_fg=(255, 255, 255), ca_pill_bg=(37, 99, 235),
               cb_pill_fg=(255, 255, 255), cb_pill_bg=(234, 88, 12),
               price_fg=(180, 83, 9), price_bg=(254, 243, 199)),
}
WHITE = (255, 255, 255)

# ---------------------------------------------------------------- 字体
_FONT_DIR = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
_REG = ['msyh.ttc', 'msyh.ttf', 'simhei.ttf', 'simsun.ttc', 'segoeui.ttf']
_BOLD = ['msyhbd.ttc', 'msyhbd.ttf', 'simhei.ttf', 'msyh.ttc']
_fcache = {}


def font(size, bold=False):
    key = (round(size * SC), bold)
    if key not in _fcache:
        f = None
        for name in (_BOLD if bold else _REG):
            p = os.path.join(_FONT_DIR, name)
            if os.path.exists(p):
                try:
                    f = ImageFont.truetype(p, key[0])
                    break
                except Exception:
                    pass
        _fcache[key] = f or ImageFont.load_default()
    return _fcache[key]


_meas = ImageDraw.Draw(Image.new('RGB', (4, 4)))


def tw(text, size, bold=False):
    return _meas.textlength(text, font=font(size, bold)) / SC


_TOK = re.compile(r"[A-Za-z0-9_.\-/()@%+:,'\"&#×¥|,]+|\s+|.")


def wrap(text, size, maxw, bold=False):
    text = (text or '').strip()
    if not text:
        return ['']
    lines, line = [], ''
    for tok in _TOK.findall(text):
        if tw(line + tok, size, bold) <= maxw:
            line += tok
            continue
        if line.strip():
            lines.append(line.rstrip())
        line = '' if tok.isspace() else tok
        while tw(line, size, bold) > maxw and len(line) > 1:
            cut = len(line) - 1
            while cut > 1 and tw(line[:cut], size, bold) > maxw:
                cut -= 1
            lines.append(line[:cut])
            line = line[cut:]
    if line.strip():
        lines.append(line)
    return lines or ['']


# ---------------------------------------------------------------- 显示列表
class DL:
    def __init__(self):
        self.ops = []

    def add(self, *op):
        self.ops.append(op)
        return len(self.ops) - 1

    def text(self, x, y, t, size, color, bold=False, anchor='la'):
        self.add('text', x, y, t, size, color, bold, anchor)

    def rrect(self, x0, y0, x1, y1, r, fill, outline=None, ow=1):
        return self.add('rrect', x0, y0, x1, y1, r, fill, outline, ow)

    def pill(self, x, y, t, size, fg, bg, bold=True, padx=9, h=None):
        w = tw(t, size, bold) + padx * 2
        h = h or size + 9
        self.rrect(x, y, x + w, y + h, h / 2, bg)
        self.text(x + padx, y + (h - size * 1.35) / 2 + 0.5, t, size, fg, bold)
        return w

    def pill_right(self, xr, y, t, size, fg, bg, bold=True, padx=9, h=None):
        """从右边界 xr 向左绘制胶囊,返回胶囊宽度"""
        w = tw(t, size, bold) + padx * 2
        h = h or size + 9
        x = xr - w
        self.rrect(x, y, xr, y + h, h / 2, bg)
        self.text(x + padx, y + (h - size * 1.35) / 2 + 0.5, t, size, fg, bold)
        return w


def execute(dl, W, H, bg):
    img = Image.new('RGB', (int(W * SC), int(H * SC)), bg)
    d = ImageDraw.Draw(img)
    for op in dl.ops:
        k = op[0]
        if k == 'rrect':
            _, x0, y0, x1, y1, r, fill, outline, ow = op
            d.rounded_rectangle([x0 * SC, y0 * SC, x1 * SC, y1 * SC], radius=r * SC, fill=fill,
                                outline=outline, width=int(ow * SC) if outline else 0)
        elif k == 'text':
            _, x, y, t, size, color, bold, anchor = op
            d.text((x * SC, y * SC), t, font=font(size, bold), fill=color, anchor=anchor)
        elif k == 'line':
            _, x0, y0, x1, y1, color, w = op
            d.line([x0 * SC, y0 * SC, x1 * SC, y1 * SC], fill=color, width=max(1, int(w * SC)))
        elif k == 'ellipse':
            _, x0, y0, x1, y1, fill = op
            d.ellipse([x0 * SC, y0 * SC, x1 * SC, y1 * SC], fill=fill)
        elif k == 'grad':
            _, x0, y0, x1, y1, c1, c2 = op
            X0, X1, Y0, Y1 = int(x0 * SC), int(x1 * SC), int(y0 * SC), int(y1 * SC)
            n = max(1, X1 - X0 - 1)
            for i in range(X1 - X0):
                t = i / n
                c = tuple(int(c1[j] + (c2[j] - c1[j]) * t) for j in range(3))
                d.line([X0 + i, Y0, X0 + i, Y1], fill=c)
    return img


# ---------------------------------------------------------------- 公共部件
def _header(dl, W, th, title, subtitle_fn, h=150):
    dl.add('grad', 0, 0, W, h, th['hdr1'], th['hdr2'])
    dl.text(28, 26, 'HARDWARE REPORT & MARKET VALUATION', 12, th.get('hdr_sub', (214, 234, 255)), True)
    dl.text(28, 48, title, 30, WHITE, True)
    subtitle_fn(dl, 28, 100)
    mx, my = W - 28 - 96, 36
    icon_col = th.get('hdr_icon', WHITE)
    dl.rrect(mx, my, mx + 96, my + 62, 9, None, icon_col, 3)
    for i, bh in enumerate((20, 34, 26, 40)):
        x = mx + 16 + i * 18
        dl.rrect(x, my + 50 - bh, x + 10, my + 50, 3, icon_col)
    dl.add('line', mx + 48, my + 62, mx + 48, my + 76, icon_col, 3)
    dl.add('line', mx + 28, my + 78, mx + 68, my + 78, icon_col, 3)


def _footer(dl, W, y, th, text):
    dl.text(W / 2, y, text, 13, th['sub'], False, 'ma')
    return y + 22 + 22


def _norm(s):
    return re.sub(r'\s+', '', (s or '').lower())


# ---------------------------------------------------------------- 本机报告
def render_report(rep, theme='科技蓝', detail=True, show_price=True):
    market.enrich(rep)
    th = THEMES.get(theme, THEMES['科技蓝'])
    W, PAD = 880, 28
    dl = DL()
    nick = (rep.get('nickname') or '').strip()
    hd = rep.get('header', {})
    val = rep.get('valuation', {})
    title = f'{nick} 的电脑配置' if nick else '电脑硬件配置'

    def sub(dl_, x, y):
        dl_.text(x, y, f'{hd.get("model", "")}   ·   扫描于 {rep.get("scan_time", "")}', 15, th.get('hdr_sub', (232, 244, 255)))

    _header(dl, W, th, title, sub)
    y = 150 + 20

    # --- 1. 三张概览卡片
    gap = 14
    cw = (W - 2 * PAD - 2 * gap) / 3
    cards = [('型号信息', hd.get('model', '-'), ''),
             ('系统信息', hd.get('os', '-'), hd.get('os_detail', '') if detail else ''),
             ('运行时间', hd.get('uptime', '-'), '')]
    prepared = []
    for lab, v_str, det in cards:
        vl = wrap(v_str, 16, cw - 32, True)
        dlines = wrap(det, 12, cw - 32) if det else []
        prepared.append((lab, vl, dlines))
    ch = 18 + 22 + max(len(v) * 24 + (len(dd) * 18 + 4 if dd else 0) for _, v, dd in prepared) + 14
    border = th.get('card_border')
    for i, (lab, vl, dlines) in enumerate(prepared):
        x = PAD + i * (cw + gap)
        dl.rrect(x, y, x + cw, y + ch, 12, th['card'], outline=border)
        dl.add('ellipse', x + 16, y + 22, x + 24, y + 30, th['accent'])
        dl.text(x + 32, y + 15, lab, 14, th['sub'])
        yy = y + 44
        for ln in vl:
            dl.text(x + 16, yy, ln, 16, th['text'], True)
            yy += 24
        for ln in dlines:
            dl.text(x + 16, yy + 2, ln, 12, th['sub'])
            yy += 18
    y += ch + 16

    # --- 2. 市场价值评估 & 性能段位大卡片
    if val:
        top = y
        v_idx = dl.rrect(PAD, top, W - PAD, top + 10, 12, th['card'], outline=border)
        sec_title = '市场价值评估 & 性能段位' if show_price else '整机性能段位评估'
        dl.text(PAD + 22, top + 18, sec_title, 18, th['text'], True)

        # 右侧段位与击败比例胶囊
        xr = W - PAD - 22
        w_beat = dl.pill_right(xr, top + 16, f'击败全国 {val.get("beat_pct", 80)}% 电脑', 12, WHITE, th['good'], True, 11, 24)
        ov_t = val.get('overall_tier', 'T2')
        ov_col = market.TIERS.get(ov_t, ('', (59, 130, 246)))[1]
        dl.pill_right(xr - w_beat - 8, top + 16, val.get('overall_title', '主流主机'), 12, WHITE, ov_col, True, 11, 24)

        y = top + 56
        bx0 = PAD + 22
        bw = (W - 2 * (PAD + 22) - 2 * 12) / 3
        bh = 76
        cpu_info = val.get('cpu', {})
        gpu_info = val.get('gpu', {})
        if show_price:
            boxes = [
                ('二手市场残值 (闲鱼参考)', f'¥ {val.get("total_used", 0):,}',
                 f'含{val.get("extra_label", "机电散")} ≈ ¥{val.get("extra_used", 0)}', th.get('price_fg', (254, 240, 138))),
                ('全新装机参考 (电商新件)', f'¥ {val.get("total_new", 0):,}',
                 f'含{val.get("extra_label", "机电散")} ≈ ¥{val.get("extra_new", 0)}', th['accent']),
                ('整机天梯综合跑分', f'{val.get("total_score", 0):,} 分',
                 f'CPU {cpu_info.get("score", 0):,} · 显卡 {gpu_info.get("score", 0):,}', th['good']),
            ]
        else:
            boxes = [
                ('整机天梯综合跑分', f'{val.get("total_score", 0):,} 分', val.get('overall_title', ''), th['good']),
                ('处理器 (CPU) 天梯分', f'{cpu_info.get("score", 0):,} 分',
                 f'{cpu_info.get("name", "-")} · 超越 {cpu_info.get("pct", 50)}%', th['accent']),
                ('显卡 (GPU) 天梯分', f'{gpu_info.get("score", 0):,} 分',
                 f'{gpu_info.get("name", "-")} · 超越 {gpu_info.get("pct", 50)}%', th['ca']),
            ]

        for i, (blab, bval, bsub, bcol) in enumerate(boxes):
            bx = bx0 + i * (bw + 12)
            dl.rrect(bx, y, bx + bw, y + bh, 10, th['chip'], outline=th['divider'])
            dl.text(bx + 14, y + 10, blab, 12, th['sub'])
            dl.text(bx + 14, y + 29, bval, 21, bcol, True)
            dl.text(bx + 14, y + 56, bsub, 11, th['sub'])
        y += bh + 14

        # 预算/价值分布比例条
        if show_price and val.get('total_used', 0) > 0:
            tot_u = val['total_used']
            bar_w = W - 2 * (PAD + 22)
            dl.rrect(bx0, y, bx0 + bar_w, y + 12, 6, th['bar_bg'])
            cur_x = bx0
            bdown = [b for b in val.get('breakdown', []) if b[1] > 0]
            for idx_b, (bname, bu, bn, bcol) in enumerate(bdown):
                seg_w = bar_w * (bu / tot_u)
                if idx_b == len(bdown) - 1:
                    seg_w = bx0 + bar_w - cur_x
                if seg_w >= 4:
                    dl.rrect(cur_x, y, cur_x + seg_w, y + 12, 4 if idx_b in (0, len(bdown) - 1) else 1, bcol)
                cur_x += seg_w
            y += 20
            lx = bx0
            for bname, bu, bn, bcol in bdown:
                pct_b = round(bu * 100 / tot_u)
                dl.add('ellipse', lx, y + 4, lx + 8, y + 12, bcol)
                txt = f'{bname} ¥{bu:,} ({pct_b}%)'
                dl.text(lx + 13, y, txt, 12, th['sub'])
                lx += tw(txt, 12) + 28
            y += 22
        else:
            y += 4

        dl.ops[v_idx] = ('rrect', PAD, top, W - PAD, y, 12, th['card'], border, 1)
        y += 16

    # --- 3. 详细信息卡片 (含单项双价格与 CPU/GPU 天梯进度条)
    top = y
    bg_idx = dl.rrect(PAD, top, W - PAD, top + 10, 12, th['card'], outline=border)
    dl.text(PAD + 22, top + 18, '硬件明细 & 单项估值' if show_price else '详细信息', 18, th['text'], True)
    if show_price:
        srcs = val.get('sources') or []
        src_txt = f'来源: {" / ".join(srcs)}  ·  ' if srcs else ''
        dl.text(W - PAD - 22, top + 22, f'{src_txt}口径: 闲鱼二手均价 / 全新参考价', 12, th['sub'], False, 'ra')
    y = top + 58
    x0 = PAD + 22
    vx = x0 + 98
    xr = W - PAD - 22
    items = rep.get('items', [])
    for n, it in enumerate(items):
        dl.text(x0, y, it['label'], 16, th['accent'], True)
        if show_price and len(it.get('rows', [])) > 1 and it.get('_used', 0) > 0:
            dl.text(x0, y + 24, f'小计 ¥{it["_used"]:,}', 11, th.get('price_fg', th['sub']))
        yy = y
        for row in it['rows']:
            ev = row.get('_eval') or {}
            # 先绘制右侧价格胶囊与段位徽章,并算出标题可用宽度
            badge_w = 0
            if show_price:
                if ev.get('used', 0) > 0:
                    ptxt = f'二手 ≈ ¥{ev["used"]:,}   |   全新 ≈ ¥{ev["new"]:,}'
                    pw = dl.pill_right(xr, yy, ptxt, 11, th.get('price_fg', (254, 240, 138)),
                                       th.get('price_bg', th['chip']), True, 10, 22)
                    badge_w += pw + 8
                elif ev.get('note'):
                    pw = dl.pill_right(xr, yy, ev['note'], 11, th['sub'], th['chip'], False, 9, 21)
                    badge_w += pw + 8
            if ev.get('tier') and it['key'] in ('cpu', 'gpu'):
                t_code = ev['tier']
                t_label, t_col = market.TIERS.get(t_code, (t_code, th['accent']))
                tw_p = dl.pill_right(xr - badge_w, yy, ev.get('tier_label', t_label), 11, WHITE, t_col, True, 9, 22)
                badge_w += tw_p + 8

            row_maxw = max(220, (xr - vx) - badge_w - 6)
            for ln in wrap(row['t'], 16, row_maxw, True):
                dl.text(vx, yy, ln, 16, th['text'], True)
                yy += 24
            if detail and row.get('d'):
                for ln in wrap(row['d'], 13, xr - vx):
                    dl.text(vx, yy, ln, 13, th['sub'])
                    yy += 19
            # CPU / GPU 内嵌天梯定位条
            if it['key'] in ('cpu', 'gpu') and ev.get('rank_desc'):
                yy += 3
                bar_l = 120
                pct = max(6, min(100, ev.get('pct', 50)))
                t_col = market.TIERS.get(ev.get('tier', 'T2'), ('', th['accent']))[1]
                dl.rrect(vx, yy + 4, vx + bar_l, yy + 13, 4, th['bar_bg'])
                dl.rrect(vx, yy + 4, vx + bar_l * pct / 100.0, yy + 13, 4, t_col)
                dl.text(vx + bar_l + 10, yy, ev['rank_desc'], 12, th['accent'])
                yy += 20
            yy += 6
        y = max(yy - 6, y + 26)
        if n < len(items) - 1:
            y += 10
            dl.add('line', x0, y, xr, y, th['divider'], 1)
            y += 14
    y += 22
    dl.ops[bg_idx] = ('rrect', PAD, top, W - PAD, y, 12, th['card'], border, 1)
    y = _footer(dl, W, y + 20, th, f'由「硬件配置助手」生成  ·  价格与天梯数据仅供参考  ·  {rep.get("scan_time", "")}')
    return execute(dl, W, y, th['bg'])


# ---------------------------------------------------------------- 对比图
def _get_compare_metrics(show_price=True):
    base = [
        ('cpu_score', 'CPU 天梯性能分', '分'),
        ('gpu_score', '显卡天梯性能分', '分'),
    ]
    if show_price:
        base += [
            ('used_price', '整机二手残值', '元'),
            ('new_price', '整机全新参考价', '元'),
        ]
    base += [
        ('cpu_cores', 'CPU 核心数', '核'),
        ('cpu_threads', 'CPU 线程数', '线程'),
        ('ram_gb', '内存容量', 'GB'),
        ('ram_speed', '内存频率', 'MHz'),
        ('vram_gb', '显存容量', 'GB'),
        ('disk_gb', '硬盘总容量', 'GB'),
    ]
    return base


def _fmt_metric(key, v, unit):
    if key in ('used_price', 'new_price'):
        return f'¥ {v:,}'
    if key in ('cpu_score', 'gpu_score'):
        return f'{v:,} {unit}'
    if key == 'disk_gb' and v >= 990:
        return f'{v / 1000:.2f}'.rstrip('0').rstrip('.') + ' TB'
    return f'{v} {unit}'


def render_compare(a, b, theme='科技蓝', detail=True, show_price=True):
    market.enrich(a)
    market.enrich(b)
    th = THEMES.get(theme, THEMES['科技蓝'])
    W, PAD = 1020, 28
    na = (a.get('nickname') or '').strip() or '我'
    nb = (b.get('nickname') or '').strip() or '好友'
    dl = DL()

    def sub(dl_, x, y):
        wa = dl_.pill(x, y - 4, na, 15, th.get('ca_pill_fg', (0, 84, 214)), th.get('ca_pill_bg', WHITE), True, 14, 28)
        dl_.text(x + wa + 14, y - 1, 'VS', 15, WHITE, True)
        dl_.pill(x + wa + 14 + tw('VS', 15, True) + 14, y - 4, nb, 15,
                 th.get('cb_pill_fg', WHITE), th.get('cb_pill_bg', (249, 115, 22)), True, 14, 28)

    _header(dl, W, th, '硬件配置 & 身价对比', sub)
    y = 150 + 20
    border = th.get('card_border')

    # --- 1. 顶部身价与综合段位 PK 卡片
    va, vb = a.get('valuation', {}), b.get('valuation', {})
    if va and vb:
        top = y
        pk_h = 108 if show_price else 86
        dl.rrect(PAD, top, W - PAD, top + pk_h, 12, th['card'], outline=border)
        col_w = (W - 2 * PAD - 120) / 2
        lx = PAD + 22
        rx = W - PAD - 22

        # 左方 (本机 na)
        dl.text(lx, top + 16, f'{na} · {va.get("overall_title", "")}', 15, th['ca'], True)
        dl.text(lx, top + 42, f'综合性能 {va.get("total_score", 0):,} 分 (击败 {va.get("beat_pct", 50)}%)', 14, th['text'], True)
        if show_price:
            dl.text(lx, top + 68, f'二手残值 ≈ ¥{va.get("total_used", 0):,}   |   全新参考 ≈ ¥{va.get("total_new", 0):,}',
                    13, th.get('price_fg', th['accent']), True)

        # 右方 (好友 nb)
        dl.text(rx, top + 16, f'{nb} · {vb.get("overall_title", "")}', 15, th['cb'], True, 'ra')
        dl.text(rx, top + 42, f'综合性能 {vb.get("total_score", 0):,} 分 (击败 {vb.get("beat_pct", 50)}%)', 14, th['text'], True, 'ra')
        if show_price:
            dl.text(rx, top + 68, f'二手残值 ≈ ¥{vb.get("total_used", 0):,}   |   全新参考 ≈ ¥{vb.get("total_new", 0):,}',
                    13, th.get('price_fg', th['accent']), True, 'ra')

        # 中间 PK 徽章
        dl.pill(W / 2 - 26, top + (pk_h - 32) / 2, 'PK', 16, WHITE, th['accent'], True, 14, 32)
        y += pk_h + 16

    # --- 2. 关键指标条形图
    ma, mb = a.get('metrics', {}), b.get('metrics', {})
    m_defs = _get_compare_metrics(show_price)
    rows = [(k, l, u, ma.get(k, 0), mb.get(k, 0)) for k, l, u in m_defs if ma.get(k, 0) or mb.get(k, 0)]
    if rows:
        top = y
        idx = dl.rrect(PAD, top, W - PAD, top + 10, 12, th['card'], outline=border)
        dl.text(PAD + 22, top + 18, '关键性能与身价对比', 18, th['text'], True)
        y = top + 60
        x0 = PAD + 22
        bx = x0 + 132
        bwmax = W - PAD - 22 - bx - 165
        for k, l, u, v1, v2 in rows:
            mx = max(v1, v2) or 1
            dl.text(x0, y + 14, l, 15, th['text'], True)
            for j, (v, col) in enumerate(((v1, th['ca']), (v2, th['cb']))):
                by = y + j * 26
                dl.rrect(bx, by + 4, bx + bwmax, by + 20, 8, th['bar_bg'])
                w = max(10, bwmax * v / mx) if v else 0
                if w:
                    dl.rrect(bx, by + 4, bx + w, by + 20, 8, col)
                label = _fmt_metric(k, v, u) if v else '-'
                dl.text(bx + bwmax + 14, by + 2, label, 14, th['text'])
                if v and v > (v2 if j == 0 else v1):
                    tx = bx + bwmax + 14 + tw(label, 14) + 8
                    tag_t = '更贵' if k in ('used_price', 'new_price') else '更高'
                    dl.pill(tx, by + 3, tag_t, 11, WHITE, th['good'], True, 7, 17)
            y += 64
        y += 6
        dl.ops[idx] = ('rrect', PAD, top, W - PAD, y, 12, th['card'], border, 1)
        y += 16

    # --- 3. 详细配置对比
    keys = []
    la = {i['key']: i for i in a.get('items', [])}
    lb = {i['key']: i for i in b.get('items', [])}
    for i in a.get('items', []) + b.get('items', []):
        if i['key'] not in keys:
            keys.append(i['key'])
    diffs = 0
    top = y
    idx = dl.rrect(PAD, top, W - PAD, top + 10, 12, th['card'], outline=border)
    dl.text(PAD + 22, top + 18, '详细配置与单项估值对比', 18, th['text'], True)
    sum_idx = dl.add('text', 0, 0, '', 14, th['sub'], False, 'ra')
    x0 = PAD + 22
    ca = x0 + 100
    colw = (W - PAD - 22 - ca - 20) / 2
    cb = ca + colw + 20
    y = top + 62
    dl.text(ca, y, na, 15, th['ca'], True)
    dl.text(cb, y, nb, 15, th['cb'], True)
    y += 30
    dl.add('line', x0, y, W - PAD - 22, y, th['divider'], 1)
    y += 14
    pcol = th.get('price_fg', th['accent'])
    for key in keys:
        ia, ib = la.get(key), lb.get(key)
        label = (ia or ib)['label']
        ra = ia['rows'] if ia else []
        rb = ib['rows'] if ib else []
        same = [_norm(r['t']) for r in ra] == [_norm(r['t']) for r in rb]
        if not same:
            diffs += 1
        n = max(len(ra), len(rb), 1)
        layout = []
        total = 0
        for i in range(n):
            def cell(rs, i=i):
                if i >= len(rs):
                    return [('—', 16, th['sub'])] if i == 0 else []
                r = rs[i]
                ev = r.get('_eval') or {}
                out = [(ln, 16, th['text']) for ln in wrap(r['t'], 16, colw)]
                if detail and r.get('d'):
                    out += [(ln, 13, th['sub']) for ln in wrap(r['d'], 13, colw)]
                if show_price:
                    t_badge = f'[{ev["tier_label"]}]  ' if ev.get('tier_label') and key in ('cpu', 'gpu') else ''
                    if ev.get('used', 0) > 0:
                        out.append((f'{t_badge}二手 ≈ ¥{ev["used"]:,}  |  全新 ≈ ¥{ev["new"]:,}', 12, pcol))
                    elif ev.get('note'):
                        out.append((f'{t_badge}{ev["note"]}', 12, th['sub']))
                elif ev.get('tier_label') and key in ('cpu', 'gpu'):
                    out.append((f'[{ev["tier_label"]}] 跑分 {ev.get("score", 0):,}', 12, pcol))
                return out
            ca_l, cb_l = cell(ra), cell(rb)
            hh = lambda c: sum(24 if s == 16 else 19 for _, s, _c in c)
            rh = max(hh(ca_l), hh(cb_l), 24) + 6
            layout.append((ca_l, cb_l, rh))
            total += rh
        total = max(total - 6, 50)
        if not same:
            dl.rrect(PAD + 10, y - 8, W - PAD - 10, y + total + 8, 8, th['diff'])
        dl.text(x0, y, label, 16, th['accent'], True)
        dl.pill(x0, y + 28, '相同' if same else '不同', 11, WHITE, th['good'] if same else (245, 158, 11), True, 8, 18)
        yy = y
        for ca_l, cb_l, rh in layout:
            for col, cl in ((ca, ca_l), (cb, cb_l)):
                cy = yy
                for t, s, c in cl:
                    dl.text(col, cy, t, s, c, s == 16)
                    cy += 24 if s == 16 else 19
            yy += rh
        y += total + 18
    y += 6
    dl.ops[idx] = ('rrect', PAD, top, W - PAD, y, 12, th['card'], border, 1)
    dl.ops[sum_idx] = ('text', W - PAD - 22, top + 22, f'共 {len(keys)} 类硬件,{diffs} 类不同', 14, th['sub'], False, 'ra')
    y = _footer(dl, W, y + 20, th, f'由「硬件配置助手」生成  ·  价格与天梯数据仅供参考  ·  {a.get("scan_time", "")}')
    return execute(dl, W, y, th['bg'])


# ---------------------------------------------------------------- CPU / 显卡天梯榜
def render_ladder(kind='cpu', rep=None, friend=None, theme='科技蓝', show_price=True):
    """渲染独立的高清 CPU 或显卡天梯榜,并高亮标出本机与好友当前硬件所在排位。"""
    th = THEMES.get(theme, THEMES['科技蓝'])
    W, PAD = 920, 28
    dl = DL()
    is_gpu = (kind == 'gpu')
    title = '显卡 (GPU) 性能天梯榜 & 市场行情' if is_gpu else '处理器 (CPU) 性能天梯榜 & 市场行情'
    ladder = market.build_ladder_view(kind, rep, friend)
    max_score = max((x['score'] for x in ladder), default=40000)

    # 找出本机与好友上榜项
    my_hits = [x for x in ladder if any(t[0] == 'local' for t in x.get('tags', []))]
    fr_hits = [x for x in ladder if any(t[0] == 'friend' for t in x.get('tags', []))]

    def sub(dl_, x, y):
        if my_hits:
            m = my_hits[0]
            dl_.text(x, y, f'★ 本机定位: 第 {m["rank"]} 名 · {m["name"]} ({m["score"]:,} 分 / {market.TIERS[m["tier"]][0]})',
                     15, th.get('hdr_sub', WHITE), True)
        else:
            dl_.text(x, y, '主流桌面与移动硬件综合性能排行 · 闲鱼二手残值与全新参考价一览', 15, th.get('hdr_sub', WHITE))

    _header(dl, W, th, title, sub)
    y = 150 + 20
    border = th.get('card_border')

    # --- 1. 顶部本机 / 好友定位摘要卡片
    if my_hits or fr_hits:
        top = y
        cards_to_show = []
        if my_hits:
            m = my_hits[0]
            raw_lbl = next((t[2] for t in m['tags'] if t[0] == 'local'), m['name'])
            cards_to_show.append(('本机当前硬件排位', m, raw_lbl, th['ca']))
        if fr_hits:
            f_item = fr_hits[0]
            raw_lbl = next((t[2] for t in f_item['tags'] if t[0] == 'friend'), f_item['name'])
            cards_to_show.append(('好友硬件排位', f_item, raw_lbl, th['cb']))

        cw = (W - 2 * PAD - (14 if len(cards_to_show) > 1 else 0)) / len(cards_to_show)
        ch = 104
        for idx_c, (clab, item_c, raw_lbl, col_c) in enumerate(cards_to_show):
            cx = PAD + idx_c * (cw + 14)
            dl.rrect(cx, top, cx + cw, top + ch, 12, th['card'], outline=col_c, ow=2)
            t_label, t_col = market.TIERS.get(item_c['tier'], ('', col_c))
            rk_txt = f'天梯第 #{item_c["rank"]} 名'
            w_rk = dl.pill(cx + 16, top + 14, rk_txt, 12, WHITE, col_c, True, 10, 22)
            dl.pill(cx + 16 + w_rk + 8, top + 14, t_label, 12, WHITE, t_col, True, 10, 22)
            dl.text(cx + cw - 16, top + 16, clab, 12, th['sub'], False, 'ra')
            dl.text(cx + 16, top + 45, raw_lbl, 16, th['text'], True)
            dl.text(cx + 16, top + 74, f'天梯跑分: {item_c["score"]:,} 分', 13, col_c, True)
            if show_price and item_c.get('used', 0) > 0:
                dl.text(cx + cw - 16, top + 74, f'二手 ≈ ¥{item_c["used"]:,}  |  全新 ≈ ¥{item_c["new"]:,}',
                        13, th.get('price_fg', th['accent']), True, 'ra')
        y += ch + 16

    # --- 2. 按 T0 ~ T4 分段绘制天梯榜
    for tier_code in ('T0', 'T1', 'T2', 'T3', 'T4'):
        group = [x for x in ladder if x['tier'] == tier_code]
        if not group:
            continue
        t_title, t_col = market.TIERS[tier_code]
        top = y
        card_idx = dl.rrect(PAD, top, W - PAD, top + 10, 12, th['card'], outline=border)
        dl.pill(PAD + 20, top + 16, t_title, 14, WHITE, t_col, True, 14, 28)
        desc_map = {
            'T0': '4K 极高画质 / 专业重度生产力殿堂级硬件',
            'T1': '2K/4K 高刷电竞 / 高端主力发烧级硬件',
            'T2': '1080P/2K 畅玩 3A 与主流电竞高性价比甜点',
            'T3': '主流网游畅玩 / 日常设计办公实用级硬件',
            'T4': '轻度办公 / 影音娱乐 / 经典老款亮机硬件',
        }
        dl.text(PAD + 150, top + 21, desc_map.get(tier_code, ''), 13, th['sub'])
        if show_price:
            dl.text(W - PAD - 22, top + 21, '二手残值  /  全新参考', 12, th['sub'], False, 'ra')

        y = top + 56
        x_rank = PAD + 22
        x_name = PAD + 68
        x_bar = PAD + 285
        xr = W - PAD - 22
        bar_max_w = (xr - x_bar - 215) if show_price else (xr - x_bar - 90)

        for item in group:
            tags = item.get('tags', [])
            is_local = any(t[0] == 'local' for t in tags)
            is_friend = any(t[0] == 'friend' for t in tags)
            row_h = 56 if tags else 36

            if tags:
                hl_col = th['ca'] if is_local else th['cb']
                dl.rrect(PAD + 12, y - 4, W - PAD - 12, y + row_h - 6, 8, th['diff'], outline=hl_col, ow=2)

            # 排名
            rk_col = t_col if item['rank'] <= 3 else (th['ca'] if is_local else th['sub'])
            dl.text(x_rank, y + 4, f'#{item["rank"]}', 14, rk_col, True)

            # 型号名称
            dl.text(x_name, y + 4, item['name'], 15, th['text'], True if tags else False)

            # 性能长条 + 分数
            bw = max(12, bar_max_w * (item['score'] / max_score))
            bar_col = th['ca'] if is_local else (th['cb'] if is_friend else t_col)
            dl.rrect(x_bar, y + 7, x_bar + bar_max_w, y + 21, 7, th['bar_bg'])
            dl.rrect(x_bar, y + 7, x_bar + bw, y + 21, 7, bar_col)
            dl.text(x_bar + bw + 8, y + 4, f'{item["score"]:,}', 13, th['text'], True)

            # 价格
            if show_price:
                if item.get('used', 0) > 0:
                    ptxt = f'¥{item["used"]:,}  /  ¥{item["new"]:,}'
                    dl.text(xr, y + 4, ptxt, 13, th.get('price_fg', th['accent']), True, 'ra')
                else:
                    dl.text(xr, y + 4, '内置/核显', 12, th['sub'], False, 'ra')

            # 本机/好友高亮标签行
            if tags:
                tx = x_name
                for role, r_lbl, raw_name in tags:
                    p_bg = th['ca_pill_bg'] if role == 'local' else th['cb_pill_bg']
                    p_fg = th['ca_pill_fg'] if role == 'local' else th['cb_pill_fg']
                    w_tag = dl.pill(tx, y + 27, f'★ {r_lbl}: {raw_name}', 11, p_fg, p_bg, True, 9, 20)
                    tx += w_tag + 10

            y += row_h

        y += 8
        dl.ops[card_idx] = ('rrect', PAD, top, W - PAD, y, 12, th['card'], border, 1)
        y += 16

    scan_t = (rep or {}).get('scan_time') or ''
    y = _footer(dl, W, y + 10, th, f'由「硬件配置助手」生成  ·  天梯跑分与二手/全新行情仅供参考  {("·  " + scan_t) if scan_t else ""}')
    return execute(dl, W, y, th['bg'])
