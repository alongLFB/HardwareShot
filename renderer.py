# -*- coding: utf-8 -*-
"""用 Pillow 把硬件配置渲染成长图(本机报告 / 双机对比图)。采用"显示列表"方式:先排版得到总高度,再一次性绘制。"""
import os
import re

from PIL import Image, ImageDraw, ImageFont

SC = 2  # 输出放大倍数(逻辑宽 860px -> 实际 1720px,清晰度更好)

THEMES = {
    '科技蓝': dict(bg=(8, 62, 168), card=(13, 84, 212), text=(255, 255, 255), sub=(184, 212, 255),
                 accent=(124, 214, 255), divider=(44, 112, 232), hdr1=(0, 98, 255), hdr2=(0, 190, 255),
                 diff=(31, 108, 224), good=(34, 197, 94), bar_bg=(8, 62, 168), chip=(44, 112, 232),
                 ca=(103, 232, 249), cb=(251, 146, 60)),
    '深色': dict(bg=(15, 18, 28), card=(26, 31, 46), text=(235, 240, 250), sub=(140, 152, 175),
               accent=(86, 170, 255), divider=(44, 51, 72), hdr1=(37, 99, 235), hdr2=(124, 58, 237),
               diff=(70, 56, 22), good=(34, 197, 94), bar_bg=(15, 18, 28), chip=(44, 51, 72),
               ca=(96, 165, 250), cb=(251, 146, 60)),
    '浅色': dict(bg=(238, 242, 249), card=(255, 255, 255), text=(24, 32, 48), sub=(108, 119, 140),
               accent=(22, 119, 255), divider=(230, 234, 242), hdr1=(22, 119, 255), hdr2=(0, 200, 255),
               diff=(255, 243, 210), good=(22, 163, 74), bar_bg=(236, 240, 247), chip=(230, 236, 246),
               ca=(59, 130, 246), cb=(249, 115, 22)),
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


_TOK = re.compile(r"[A-Za-z0-9_.\-/()@%+:,'\"&#×]+|\s+|.")


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
        while tw(line, size, bold) > maxw and len(line) > 1:  # 超长单词按字符拆
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
    dl.text(28, 26, 'HARDWARE REPORT', 12, (214, 234, 255), True)
    dl.text(28, 48, title, 30, WHITE, True)
    subtitle_fn(dl, 28, 100)
    # 右侧装饰:显示器图标
    mx, my = W - 28 - 96, 36
    dl.rrect(mx, my, mx + 96, my + 62, 9, None, (255, 255, 255), 3)
    for i, bh in enumerate((20, 34, 26, 40)):
        x = mx + 16 + i * 18
        dl.rrect(x, my + 50 - bh, x + 10, my + 50, 3, (255, 255, 255))
    dl.add('line', mx + 48, my + 62, mx + 48, my + 76, (255, 255, 255), 3)
    dl.add('line', mx + 28, my + 78, mx + 68, my + 78, (255, 255, 255), 3)


def _footer(dl, W, y, th, text):
    dl.text(W / 2, y, text, 13, th['sub'], False, 'ma')
    return y + 22 + 22


def _norm(s):
    return re.sub(r'\s+', '', (s or '').lower())


# ---------------------------------------------------------------- 本机报告
def render_report(rep, theme='科技蓝', detail=True):
    th = THEMES.get(theme, THEMES['科技蓝'])
    W, PAD = 860, 28
    dl = DL()
    nick = (rep.get('nickname') or '').strip()
    hd = rep.get('header', {})
    title = f'{nick} 的电脑配置' if nick else '电脑硬件配置'

    def sub(dl_, x, y):
        dl_.text(x, y, f'{hd.get("model", "")}   ·   扫描于 {rep.get("scan_time", "")}', 15, (232, 244, 255))

    _header(dl, W, th, title, sub)
    y = 150 + 22
    # 三张概览卡片
    gap = 14
    cw = (W - 2 * PAD - 2 * gap) / 3
    cards = [('型号信息', hd.get('model', '-'), ''),
             ('系统信息', hd.get('os', '-'), hd.get('os_detail', '') if detail else ''),
             ('运行时间', hd.get('uptime', '-'), '')]
    prepared = []
    for lab, val, det in cards:
        vl = wrap(val, 17, cw - 32, True)
        dlines = wrap(det, 12, cw - 32) if det else []
        prepared.append((lab, vl, dlines))
    ch = 18 + 22 + max(len(v) * 25 + (len(dd) * 18 + 4 if dd else 0) for _, v, dd in prepared) + 14
    for i, (lab, vl, dlines) in enumerate(prepared):
        x = PAD + i * (cw + gap)
        dl.rrect(x, y, x + cw, y + ch, 12, th['card'])
        dl.add('ellipse', x + 16, y + 22, x + 24, y + 30, th['accent'])
        dl.text(x + 32, y + 15, lab, 14, th['sub'])
        yy = y + 46
        for ln in vl:
            dl.text(x + 16, yy, ln, 17, th['text'], True)
            yy += 25
        for ln in dlines:
            dl.text(x + 16, yy + 2, ln, 12, th['sub'])
            yy += 18
    y += ch + 16

    # 详细信息卡片
    top = y
    bg_idx = dl.rrect(PAD, top, W - PAD, top + 10, 12, th['card'])
    dl.text(PAD + 22, top + 18, '详细信息', 18, th['text'], True)
    y = top + 58
    x0 = PAD + 22
    vx = x0 + 104
    maxw = W - PAD - 22 - vx
    items = rep.get('items', [])
    for n, it in enumerate(items):
        dl.text(x0, y, it['label'], 16, th['accent'], True)
        yy = y
        for row in it['rows']:
            for ln in wrap(row['t'], 17, maxw):
                dl.text(vx, yy, ln, 17, th['text'])
                yy += 25
            if detail and row.get('d'):
                for ln in wrap(row['d'], 13, maxw):
                    dl.text(vx, yy, ln, 13, th['sub'])
                    yy += 19
            yy += 5
        y = max(yy - 5, y + 25)
        if n < len(items) - 1:
            y += 10
            dl.add('line', x0, y, W - PAD - 22, y, th['divider'], 1)
            y += 14
    y += 22
    dl.ops[bg_idx] = ('rrect', PAD, top, W - PAD, y, 12, th['card'], None, 1)
    y = _footer(dl, W, y + 20, th, f'由「硬件配置助手」生成  ·  {rep.get("scan_time", "")}')
    return execute(dl, W, y, th['bg'])


# ---------------------------------------------------------------- 对比图
METRICS = [('cpu_cores', 'CPU 核心数', '核'), ('cpu_threads', 'CPU 线程数', '线程'), ('ram_gb', '内存容量', 'GB'),
           ('ram_speed', '内存频率', 'MHz'), ('vram_gb', '显存容量', 'GB'), ('disk_gb', '硬盘总容量', 'GB')]


def _fmt_metric(key, v, unit):
    if key == 'disk_gb' and v >= 990:
        return f'{v / 1000:.2f}'.rstrip('0').rstrip('.') + ' TB'
    return f'{v} {unit}'


def render_compare(a, b, theme='科技蓝', detail=True):
    th = THEMES.get(theme, THEMES['科技蓝'])
    W, PAD = 1000, 28
    na = (a.get('nickname') or '').strip() or '我'
    nb = (b.get('nickname') or '').strip() or '好友'
    dl = DL()

    def sub(dl_, x, y):
        wa = dl_.pill(x, y - 4, na, 15, (0, 84, 214), WHITE, True, 14, 28)
        dl_.text(x + wa + 14, y - 1, 'VS', 15, WHITE, True)
        dl_.pill(x + wa + 14 + tw('VS', 15, True) + 14, y - 4, nb, 15, WHITE, (249, 115, 22), True, 14, 28)

    _header(dl, W, th, '硬件配置对比', sub)
    y = 150 + 22

    # --- 关键指标条形图
    ma, mb = a.get('metrics', {}), b.get('metrics', {})
    rows = [(k, l, u, ma.get(k, 0), mb.get(k, 0)) for k, l, u in METRICS if ma.get(k, 0) or mb.get(k, 0)]
    if rows:
        top = y
        idx = dl.rrect(PAD, top, W - PAD, top + 10, 12, th['card'])
        dl.text(PAD + 22, top + 18, '关键指标对比', 18, th['text'], True)
        y = top + 60
        x0 = PAD + 22
        bx = x0 + 120
        bwmax = W - PAD - 22 - bx - 150
        for k, l, u, va, vb in rows:
            mx = max(va, vb) or 1
            dl.text(x0, y + 14, l, 15, th['text'], True)
            for j, (v, col) in enumerate(((va, th['ca']), (vb, th['cb']))):
                by = y + j * 26
                dl.rrect(bx, by + 4, bx + bwmax, by + 20, 8, th['bar_bg'])
                w = max(10, bwmax * v / mx) if v else 0
                if w:
                    dl.rrect(bx, by + 4, bx + w, by + 20, 8, col)
                label = _fmt_metric(k, v, u) if v else '-'
                dl.text(bx + bwmax + 14, by + 2, label, 14, th['text'])
                if v and v > (vb if j == 0 else va):
                    tx = bx + bwmax + 14 + tw(label, 14) + 8
                    dl.pill(tx, by + 3, '更高', 11, WHITE, th['good'], True, 7, 17)
            y += 66
        y += 4
        dl.ops[idx] = ('rrect', PAD, top, W - PAD, y, 12, th['card'], None, 1)
        y += 16

    # --- 详细配置对比
    keys = []
    la = {i['key']: i for i in a.get('items', [])}
    lb = {i['key']: i for i in b.get('items', [])}
    for i in a.get('items', []) + b.get('items', []):
        if i['key'] not in keys:
            keys.append(i['key'])
    diffs = 0
    top = y
    idx = dl.rrect(PAD, top, W - PAD, top + 10, 12, th['card'])
    dl.text(PAD + 22, top + 18, '详细配置对比', 18, th['text'], True)
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
                    return [('—', 17, th['sub'])] if i == 0 else []
                out = [(ln, 17, th['text']) for ln in wrap(rs[i]['t'], 17, colw)]
                if detail and rs[i].get('d'):
                    out += [(ln, 13, th['sub']) for ln in wrap(rs[i]['d'], 13, colw)]
                return out
            ca_l, cb_l = cell(ra), cell(rb)
            hh = lambda c: sum(25 if s == 17 else 19 for _, s, _c in c)
            rh = max(hh(ca_l), hh(cb_l), 25) + 5
            layout.append((ca_l, cb_l, rh))
            total += rh
        total = max(total - 5, 50)
        if not same:
            dl.rrect(PAD + 10, y - 8, W - PAD - 10, y + total + 8, 8, th['diff'])
        dl.text(x0, y, label, 16, th['accent'], True)
        dl.pill(x0, y + 28, '相同' if same else '不同', 11, WHITE, th['good'] if same else (245, 158, 11), True, 8, 18)
        yy = y
        for ca_l, cb_l, rh in layout:
            for col, cl in ((ca, ca_l), (cb, cb_l)):
                cy = yy
                for t, s, c in cl:
                    dl.text(col, cy, t, s, c)
                    cy += 25 if s == 17 else 19
            yy += rh
        y += total + 18
    y += 6
    dl.ops[idx] = ('rrect', PAD, top, W - PAD, y, 12, th['card'], None, 1)
    dl.ops[sum_idx] = ('text', W - PAD - 22, top + 22, f'共 {len(keys)} 类硬件,{diffs} 类不同', 14, th['sub'], False, 'ra')
    y = _footer(dl, W, y + 20, th, f'由「硬件配置助手」生成  ·  {a.get("scan_time", "")}')
    return execute(dl, W, y, th['bg'])
