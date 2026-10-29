# -*- coding: utf-8 -*-
"""硬件市场估值(二手残值 + 全新参考价)与 CPU/显卡天梯榜数据库及智能匹配引擎。"""
import re

# ---------------------------------------------------------------- 段位定义
TIERS = {
    'T0': ('T0 殿堂旗舰', (255, 72, 110)),
    'T1': ('T1 高端发烧', (245, 158, 11)),
    'T2': ('T2 主流甜点', (16, 185, 129)),
    'T3': ('T3 入门实用', (59, 130, 246)),
    'T4': ('T4 经典亮机', (148, 163, 184)),
}

# ---------------------------------------------------------------- CPU 天梯榜与价格库
# 字段: (匹配关键字正则/词组, 标准展示名, 天梯跑分, 二手价¥, 全新价¥, 段位, 是否展示在标准天梯图)
CPU_DATA = [
    # --- T0 殿堂旗舰 ---
    (r'9950x3d', 'AMD R9 9950X3D', 48500, 4599, 5299, 'T0', True),
    (r'9950x\b', 'AMD R9 9950X', 45000, 3699, 4399, 'T0', True),
    (r'9800x3d', 'AMD R7 9800X3D', 42000, 3299, 3799, 'T0', True),
    (r'7950x3d', 'AMD R9 7950X3D', 41500, 3199, 3899, 'T0', True),
    (r'14900ks', 'Intel i9-14900KS', 43000, 3399, 4599, 'T0', False),
    (r'14900k[f]?\b', 'Intel i9-14900K/KF', 41200, 2599, 3399, 'T0', True),
    (r'ultra\s*9\s*285k', 'Intel Ultra 9 285K', 42800, 3599, 4399, 'T0', True),
    (r'13900ks', 'Intel i9-13900KS', 40200, 2499, 3299, 'T0', False),
    (r'13900k[f]?\b', 'Intel i9-13900K/KF', 39200, 2199, 2899, 'T0', True),
    (r'7950x\b', 'AMD R9 7950X', 39500, 2650, 3299, 'T0', True),
    (r'9900x\b', 'AMD R9 9900X', 36800, 2399, 2999, 'T0', True),

    # --- T1 高端发烧 ---
    (r'7800x3d', 'AMD R7 7800X3D', 35500, 2350, 2799, 'T1', True),
    (r'ultra\s*7\s*265k[f]?', 'Intel Ultra 7 265K/KF', 35200, 2199, 2699, 'T1', True),
    (r'14700k[f]?\b', 'Intel i7-14700K/KF', 34800, 1899, 2499, 'T1', True),
    (r'7900x3d', 'AMD R9 7900X3D', 34000, 2299, 2799, 'T1', False),
    (r'7900x\b', 'AMD R9 7900X', 33200, 1999, 2499, 'T1', True),
    (r'13700k[f]?\b', 'Intel i7-13700K/KF', 31500, 1599, 2199, 'T1', True),
    (r'9700x\b', 'AMD R7 9700X', 30800, 1699, 2099, 'T1', True),
    (r'14900[f]?\b', 'Intel i9-14900/F', 32500, 2199, 2899, 'T1', False),
    (r'13900[f]?\b', 'Intel i9-13900/F', 31000, 1899, 2499, 'T1', False),
    (r'14900hx', 'Intel i9-14900HX (移动版)', 31200, 2200, 2900, 'T1', False),
    (r'13900hx', 'Intel i9-13900HX (移动版)', 29500, 1900, 2500, 'T1', False),
    (r'7945hx', 'AMD R9 7945HX (移动版)', 32800, 2300, 2900, 'T1', False),
    (r'12900k[sf]?\b', 'Intel i9-12900K/KF', 28200, 1450, 1999, 'T1', True),
    (r'14700[f]?\b', 'Intel i7-14700/F', 29200, 1650, 2199, 'T1', False),
    (r'14600k[f]?\b', 'Intel i5-14600K/KF', 27600, 1250, 1599, 'T1', True),
    (r'ultra\s*5\s*245k[f]?', 'Intel Ultra 5 245K/KF', 28000, 1499, 1899, 'T1', False),
    (r'7700x\b', 'AMD R7 7700X', 26800, 1399, 1799, 'T1', True),
    (r'9600x\b', 'AMD R5 9600X', 25800, 1199, 1499, 'T1', True),
    (r'13600k[f]?\b', 'Intel i5-13600K/KF', 26200, 1099, 1450, 'T1', True),

    # --- T2 主流甜点 ---
    (r'7700\b', 'AMD R7 7700', 25200, 1199, 1499, 'T2', False),
    (r'5800x3d', 'AMD R7 5800X3D', 24800, 1399, 1799, 'T2', True),
    (r'5950x\b', 'AMD R9 5950X', 26500, 1599, 2199, 'T2', False),
    (r'5900x\b', 'AMD R9 5900X', 23800, 1150, 1599, 'T2', False),
    (r'13700[f]?\b', 'Intel i7-13700/F', 25500, 1399, 1899, 'T2', False),
    (r'12700k[f]?\b', 'Intel i7-12700K/KF', 23500, 1050, 1450, 'T2', True),
    (r'5700x3d', 'AMD R7 5700X3D', 22800, 999, 1299, 'T2', True),
    (r'7600x\b', 'AMD R5 7600X', 22400, 950, 1199, 'T2', True),
    (r'7600\b', 'AMD R5 7600', 21500, 880, 1099, 'T2', False),
    (r'7500f\b', 'AMD R5 7500F', 21000, 799, 999, 'T2', True),
    (r'14490f\b', 'Intel i5-14490F', 20800, 850, 1099, 'T2', False),
    (r'14400[f]?\b', 'Intel i5-14400/F', 19800, 780, 999, 'T2', True),
    (r'13490f\b', 'Intel i5-13490F', 19500, 750, 969, 'T2', False),
    (r'13400[f]?\b', 'Intel i5-13400/F', 18800, 699, 899, 'T2', True),
    (r'12600k[f]?\b', 'Intel i5-12600K/KF', 20500, 799, 1050, 'T2', True),
    (r'12700[f]?\b', 'Intel i7-12700/F', 21200, 920, 1299, 'T2', False),
    (r'5800x\b', 'AMD R7 5800X', 19200, 720, 999, 'T2', False),
    (r'5700x\b', 'AMD R7 5700X', 18500, 650, 899, 'T2', True),
    (r'11900k[f]?\b', 'Intel i9-11900K/KF', 18200, 850, 1199, 'T2', False),
    (r'10900k[f]?\b', 'Intel i9-10900K/KF', 17500, 799, 1099, 'T2', False),
    (r'13700h\b|13620h\b|14650hx\b|13650hx\b', 'Intel i7 13/14代标压移动版', 21500, 1200, 1600, 'T2', False),
    (r'7840h[s]?\b|8845h[s]?\b|7735h[s]?\b', 'AMD R7 7840H/8845HS (移动版)', 21000, 1150, 1500, 'T2', False),

    # --- T3 入门实用 ---
    (r'12490f\b', 'Intel i5-12490F', 16800, 550, 699, 'T3', False),
    (r'12400[f]?\b', 'Intel i5-12400/F', 16200, 499, 649, 'T3', True),
    (r'5600x\b', 'AMD R5 5600X', 16000, 520, 699, 'T3', False),
    (r'5600[g]?\b', 'AMD R5 5600/5600G', 15500, 460, 599, 'T3', True),
    (r'5500\b', 'AMD R5 5500', 13500, 350, 469, 'T3', False),
    (r'11700[kf]?\b', 'Intel i7-11700/K', 15800, 650, 899, 'T3', False),
    (r'10700[kf]?\b', 'Intel i7-10700/K', 14200, 550, 750, 'T3', True),
    (r'11400[f]?\b', 'Intel i5-11400/F', 13200, 360, 499, 'T3', False),
    (r'10400[f]?\b', 'Intel i5-10400/F', 11500, 299, 429, 'T3', True),
    (r'13100[f]?\b|14100[f]?\b', 'Intel i3-13100/14100F', 12500, 380, 529, 'T3', False),
    (r'12100[f]?\b', 'Intel i3-12100/F', 11800, 299, 429, 'T3', True),
    (r'3700x\b|3800x\b', 'AMD R7 3700X', 13800, 380, 520, 'T3', False),
    (r'3600[x]?\b', 'AMD R5 3600/X', 11600, 240, 350, 'T3', True),
    (r'9900k[f]?\b', 'Intel i9-9900K/KF', 13600, 680, 899, 'T3', False),
    (r'9700[kf]?\b', 'Intel i7-9700/K', 11200, 450, 620, 'T3', False),
    (r'8700[k]?\b', 'Intel i7-8700/K', 10500, 360, 499, 'T3', True),

    # --- T4 经典亮机 ---
    (r'9400[f]?\b', 'Intel i5-9400F', 8200, 190, 280, 'T4', True),
    (r'8400\b|8500\b', 'Intel i5-8400/8500', 7800, 170, 250, 'T4', False),
    (r'2600[x]?\b|2700[x]?\b', 'AMD R5 2600 / R7 2700', 8500, 150, 230, 'T4', True),
    (r'7700[k]?\b', 'Intel i7-7700/K', 6800, 260, 360, 'T4', True),
    (r'6700[k]?\b', 'Intel i7-6700/K', 6000, 190, 280, 'T4', False),
    (r'10100[f]?\b|10105[f]?\b', 'Intel i3-10100/F', 7600, 170, 260, 'T4', False),
    (r'9100[f]?\b|8100\b', 'Intel i3-8100/9100F', 5500, 90, 150, 'T4', False),
    (r'7500\b|6500\b', 'Intel i5-6500/7500', 4600, 80, 130, 'T4', True),
    (r'4790[k]?\b|4770[k]?\b', 'Intel i7-4790K', 4500, 130, 200, 'T4', False),
    (r'4590\b|4460\b|3470\b', 'Intel i5 四代/三代', 3200, 45, 80, 'T4', False),
    (r'e5[\s\-]*26[0-9]{2}', 'Intel Xeon E5 系列', 9500, 65, 130, 'T4', True),
]

# ---------------------------------------------------------------- 显卡 (GPU) 天梯榜与价格库
GPU_DATA = [
    # --- T0 殿堂旗舰 ---
    (r'5090\s*d?\b', 'NVIDIA RTX 5090 / 5090D', 42000, 16500, 18999, 'T0', True),
    (r'4090\s*d\b', 'NVIDIA RTX 4090 D', 33500, 11800, 13999, 'T0', False),
    (r'4090\b', 'NVIDIA RTX 4090', 35000, 13200, 15999, 'T0', True),
    (r'5080\b', 'NVIDIA RTX 5080', 31000, 7999, 8999, 'T0', True),
    (r'4080\s*super', 'NVIDIA RTX 4080 Super', 27800, 6699, 7799, 'T0', True),
    (r'7900\s*xtx', 'AMD RX 7900 XTX', 27200, 5699, 6799, 'T0', True),
    (r'4080\b', 'NVIDIA RTX 4080', 26800, 6199, 7299, 'T0', True),

    # --- T1 高端发烧 ---
    (r'5070\s*ti', 'NVIDIA RTX 5070 Ti', 25500, 5899, 6699, 'T1', True),
    (r'4070\s*ti\s*super', 'NVIDIA RTX 4070 Ti Super', 24000, 5299, 6199, 'T1', True),
    (r'7900\s*xt\b', 'AMD RX 7900 XT', 23500, 4399, 5199, 'T1', True),
    (r'9070\s*xt\b', 'AMD RX 9070 XT', 23800, 4499, 4999, 'T1', True),
    (r'4070\s*ti\b', 'NVIDIA RTX 4070 Ti', 22200, 4599, 5499, 'T1', True),
    (r'3090\s*ti\b', 'NVIDIA RTX 3090 Ti', 21500, 4899, 6299, 'T1', False),
    (r'5070\b', 'NVIDIA RTX 5070', 21200, 4299, 4799, 'T1', True),
    (r'4070\s*super', 'NVIDIA RTX 4070 Super', 20600, 3999, 4699, 'T1', True),
    (r'7900\s*gre', 'AMD RX 7900 GRE', 19800, 3499, 4099, 'T1', True),
    (r'3090\b', 'NVIDIA RTX 3090', 19600, 4299, 5599, 'T1', True),
    (r'3080\s*ti\b', 'NVIDIA RTX 3080 Ti', 19000, 3199, 4299, 'T1', False),
    (r'6950\s*xt', 'AMD RX 6950 XT', 19200, 3099, 3899, 'T1', False),
    (r'4070\b', 'NVIDIA RTX 4070', 17800, 3499, 4099, 'T1', True),
    (r'7800\s*xt', 'AMD RX 7800 XT', 18200, 3099, 3699, 'T1', True),
    (r'6900\s*xt', 'AMD RX 6900 XT', 17600, 2699, 3499, 'T1', False),
    (r'3080\b', 'NVIDIA RTX 3080', 17200, 2499, 3399, 'T1', True),

    # --- T2 主流甜点 ---
    (r'6800\s*xt', 'AMD RX 6800 XT', 16200, 2299, 2999, 'T2', True),
    (r'7700\s*xt', 'AMD RX 7700 XT', 15500, 2499, 2999, 'T2', False),
    (r'4060\s*ti', 'NVIDIA RTX 4060 Ti', 14200, 2499, 2999, 'T2', True),
    (r'3070\s*ti', 'NVIDIA RTX 3070 Ti', 14500, 1999, 2699, 'T2', True),
    (r'6800\b', 'AMD RX 6800', 14000, 1950, 2599, 'T2', False),
    (r'3070\b', 'NVIDIA RTX 3070', 13400, 1699, 2299, 'T2', True),
    (r'6750\s*gre', 'AMD RX 6750 GRE', 12400, 1699, 2099, 'T2', True),
    (r'6750\s*xt|6700\s*xt', 'AMD RX 6700 XT / 6750 XT', 12200, 1599, 2099, 'T2', False),
    (r'3060\s*ti', 'NVIDIA RTX 3060 Ti', 11800, 1499, 1999, 'T2', True),
    (r'4060\b', 'NVIDIA RTX 4060', 11200, 1899, 2299, 'T2', True),
    (r'2080\s*ti', 'NVIDIA RTX 2080 Ti', 12600, 1599, 2199, 'T2', False),
    (r'7600\s*xt|7600\b', 'AMD RX 7600 / XT', 10600, 1599, 1999, 'T2', True),
    (r'b580\b', 'Intel Arc B580', 10800, 1699, 1999, 'T2', False),

    # --- T3 入门实用 ---
    (r'2080\s*super|2080\b', 'NVIDIA RTX 2080 / Super', 10200, 1150, 1599, 'T3', False),
    (r'6650\s*xt|6600\s*xt', 'AMD RX 6650 XT / 6600 XT', 9600, 1199, 1549, 'T3', True),
    (r'3060\b', 'NVIDIA RTX 3060', 8900, 1199, 1599, 'T3', True),
    (r'2070\s*super|2070\b', 'NVIDIA RTX 2070 / Super', 8800, 980, 1350, 'T3', False),
    (r'a770\b|a750\b', 'Intel Arc A750 / A770', 8600, 1050, 1499, 'T3', False),
    (r'6600\b', 'AMD RX 6600', 8100, 950, 1299, 'T3', True),
    (r'2060\s*super|2060\b', 'NVIDIA RTX 2060 / Super', 7600, 799, 1099, 'T3', True),
    (r'1080\s*ti', 'NVIDIA GTX 1080 Ti', 8400, 850, 1199, 'T3', False),
    (r'3050\b', 'NVIDIA RTX 3050', 6400, 850, 1199, 'T3', True),
    (r'1660\s*super|1660\s*ti|1660\b', 'NVIDIA GTX 1660 Super/Ti', 6200, 580, 799, 'T3', True),
    (r'1080\b|1070\s*ti|1070\b', 'NVIDIA GTX 1070 / 1080', 6300, 550, 780, 'T3', False),
    (r'5700\s*xt|5600\s*xt', 'AMD RX 5600 XT / 5700 XT', 7200, 650, 899, 'T3', False),

    # --- T4 经典亮机 ---
    (r'1650\s*super|1650\b', 'NVIDIA GTX 1650 / Super', 4500, 399, 599, 'T4', True),
    (r'6500\s*xt|6400\b', 'AMD RX 6500 XT / 6400', 4600, 450, 649, 'T4', False),
    (r'1060\b', 'NVIDIA GTX 1060', 4300, 350, 499, 'T4', True),
    (r'580\b|590\b|480\b|470\b', 'AMD RX 580 / 590', 4100, 260, 399, 'T4', True),
    (r'1050\s*ti|1050\b', 'NVIDIA GTX 1050 / Ti', 2700, 220, 340, 'T4', True),
    (r'970\b|960\b', 'NVIDIA GTX 960 / 970', 2800, 160, 260, 'T4', False),
    (r'750\s*ti|750\b|730\b|1030\b', 'NVIDIA GT 1030 / GTX 750 Ti', 1600, 110, 199, 'T4', True),
]


def _score_to_tier(score, is_gpu=False):
    if is_gpu:
        if score >= 26000:
            return 'T0'
        if score >= 17000:
            return 'T1'
        if score >= 10500:
            return 'T2'
        if score >= 5500:
            return 'T3'
        return 'T4'
    else:
        if score >= 36000:
            return 'T0'
        if score >= 25500:
            return 'T1'
        if score >= 17000:
            return 'T2'
        if score >= 10000:
            return 'T3'
        return 'T4'


def _score_to_pct(score, max_s):
    return max(5, min(99, round(100 * (score / max_s) ** 0.62)))


def _neighbors(score, ladder):
    """在天梯榜中找相邻型号描述"""
    st = sorted(ladder, key=lambda x: x['score'], reverse=True)
    higher, lower = None, None
    for item in st:
        if abs(item['score'] - score) < 350:
            return f'性能与「{item["name"]}」同级'
        if item['score'] > score:
            higher = item['name']
        elif item['score'] < score and lower is None:
            lower = item['name']
            break
    if higher and lower:
        return f'位于 {lower} 与 {higher} 之间'
    if higher:
        return f'紧随 {higher} 之后'
    if lower:
        return f'领先于 {lower}'
    return ''


def get_ladder(kind='cpu'):
    src = CPU_DATA if kind == 'cpu' else GPU_DATA
    out = []
    for pat, name, score, used, new, tier, show in src:
        if show:
            out.append({'name': name, 'score': score, 'used': used, 'new': new, 'tier': tier, 'pat': pat, 'tags': []})
    out.sort(key=lambda x: x['score'], reverse=True)
    return out


def _pick_hw(rep, kind='cpu'):
    """从 report 中提取主 CPU 或主显卡(得分最高的一张)的评估信息。"""
    if not rep or not isinstance(rep.get('items'), list):
        return None
    enrich(rep)
    best_row, best_ev = None, None
    for it in rep.get('items', []):
        if it.get('key') == kind:
            for r in it.get('rows', []):
                ev = r.get('_eval') or {}
                if best_ev is None or ev.get('score', 0) > best_ev.get('score', -1):
                    best_row, best_ev = r, ev
    if not best_row or not best_ev:
        return None
    raw_t = re.sub(r'\s*\(.*?\)', '', best_row.get('t', '')).strip()
    return {'raw': raw_t, 'ev': best_ev}


def build_ladder_view(kind='cpu', rep=None, friend=None):
    """构建带本机/好友硬件高亮标记的天梯榜列表,按分数降序排列并标注排名。"""
    ladder = get_ladder(kind)
    na = ((rep or {}).get('nickname') or '').strip() or '本机'
    nb = ((friend or {}).get('nickname') or '').strip() or '好友'

    for role, r_data, label in (('local', rep, f'本机 · {na}'), ('friend', friend, f'好友 · {nb}')):
        hw = _pick_hw(r_data, kind)
        if not hw:
            continue
        ev = hw['ev']
        raw_low = hw['raw'].lower()
        hit = None
        for item in ladder:
            if item['name'] == ev.get('std_name') or (item.get('pat') and re.search(item['pat'], raw_low)):
                hit = item
                break
        if hit:
            hit['tags'].append((role, label, hw['raw']))
        else:
            ladder.append({
                'name': ev.get('std_name') or hw['raw'],
                'score': ev.get('score', 5000),
                'used': ev.get('used', 0),
                'new': ev.get('new', 0),
                'tier': ev.get('tier', 'T4'),
                'pat': '',
                'tags': [(role, label, hw['raw'])],
            })

    ladder.sort(key=lambda x: x['score'], reverse=True)
    for idx, item in enumerate(ladder, 1):
        item['rank'] = idx
    return ladder


# ---------------------------------------------------------------- 各类硬件单项估值与匹配
def eval_cpu(title, detail, metrics):
    low = (title or '').lower()
    is_mobile = bool(re.search(r'(\d{3,5}(hx|hs|h|u|p|g\d|y)\b|laptop|mobile)', low))
    matched = None
    for pat, std_name, score, used, new, tier, _ in CPU_DATA:
        if re.search(pat, low):
            matched = (std_name, score, used, new, tier)
            break

    if matched:
        std_name, score, used, new, tier = matched
        if is_mobile and '移动版' not in std_name:
            score = round(score * 0.85)
            used = round(used * 0.78 / 10) * 10
            new = round(new * 0.82 / 10) * 10
            tier = _score_to_tier(score, False)
    else:
        # 启发式兜底: 根据核心数 + 线程数 + 代数估算
        cores = metrics.get('cpu_cores') or 6
        threads = metrics.get('cpu_threads') or 12
        m_core = re.search(r'(\d+)核心\s*(\d+)线程', detail or '')
        if m_core:
            cores, threads = int(m_core.group(1)), int(m_core.group(2))
        gen_factor = 1.0
        if re.search(r'(14\d{3}|13\d{3}|9\d{3}x|7\d{3}x|ultra)', low):
            gen_factor = 1.35
        elif re.search(r'(12\d{3}|11\d{3}|5\d{3}x?)', low):
            gen_factor = 1.1
        elif re.search(r'(10\d{3}|9\d{3}|8\d{3}|3\d{3}x?)', low):
            gen_factor = 0.85
        else:
            gen_factor = 0.65
        score = round((cores * 1450 + threads * 420) * gen_factor)
        score = max(2800, min(42000, score))
        tier = _score_to_tier(score, False)
        used = max(60, round(score * 0.062 / 10) * 10)
        new = max(120, round(used * 1.32 / 10) * 10)
        std_name = re.sub(r'\s*\(.*?\)', '', title).strip()

    pct = _score_to_pct(score, 48500)
    nb = _neighbors(score, get_ladder('cpu'))
    return {
        'used': used, 'new': new, 'score': score, 'tier': tier,
        'tier_label': TIERS[tier][0], 'pct': pct, 'std_name': std_name,
        'rank_desc': f'CPU 天梯跑分 {score:,} · 超越 {pct}% 处理器' + (f' · {nb}' if nb else ''),
        'note': '板载折算' if is_mobile else '',
    }


def eval_gpu(title, detail, metrics):
    low = (title or '').lower()
    # 识别核显
    igpu = re.search(r'(uhd graphics|iris xe|hd graphics|radeon\(tm\) graphics|radeon graphics|amd radeon\(tm\)|vega \d|780m|760m|680m|660m|890m|arc graphics)', low)
    if igpu and not re.search(r'(rtx|rx\s*\d{3,4}|gtx\s*\d{3,4}|arc\s*[ab]\d{3})', low):
        score = 3800 if re.search(r'(780m|890m|iris xe|arc)', low) else 1500
        return {
            'used': 0, 'new': 0, 'score': score, 'tier': 'T4',
            'tier_label': '核芯显卡', 'pct': _score_to_pct(score, 42000),
            'std_name': title.split('(')[0].strip(),
            'rank_desc': f'处理器内置核显 (天梯跑分 {score:,}) · 价值已计入处理器',
            'note': 'CPU内置核显',
        }

    is_laptop = bool(re.search(r'(laptop|mobile|max-q|\b\d{3,4}m\b)', low))
    matched = None
    for pat, std_name, score, used, new, tier, _ in GPU_DATA:
        if re.search(pat, low):
            matched = (std_name, score, used, new, tier)
            break

    if matched:
        std_name, score, used, new, tier = matched
        if is_laptop:
            score = round(score * 0.76)
            used = round(used * 0.72 / 10) * 10
            new = round(new * 0.78 / 10) * 10
            tier = _score_to_tier(score, True)
            std_name = std_name + ' (Laptop)'
    else:
        vram = metrics.get('vram_gb') or 4
        m_v = re.search(r'(\d+)\s*gb', low)
        if m_v:
            vram = int(m_v.group(1))
        score = max(2000, min(32000, vram * 1450))
        tier = _score_to_tier(score, True)
        used = max(150, round(score * 0.16 / 10) * 10)
        new = max(260, round(used * 1.3 / 10) * 10)
        std_name = title.split('(')[0].strip()

    # 一线旗舰 AIB 品牌小幅溢价
    if any(b in title for b in ('华硕', '微星', '技嘉', '七彩虹')) and used >= 1500 and not is_laptop:
        used = round(used * 1.04 / 10) * 10
        new = round(new * 1.04 / 10) * 10

    pct = _score_to_pct(score, 42000)
    nb = _neighbors(score, get_ladder('gpu'))
    return {
        'used': used, 'new': new, 'score': score, 'tier': tier,
        'tier_label': TIERS[tier][0], 'pct': pct, 'std_name': std_name,
        'rank_desc': f'显卡天梯跑分 {score:,} · 超越 {pct}% 显卡' + (f' · {nb}' if nb else ''),
        'note': '笔记本独显折算' if is_laptop else '',
    }


def eval_mem(title, detail, metrics):
    gb = metrics.get('ram_gb') or 16
    m = re.match(r'\s*(\d+)\s*GB', title or '', re.I)
    if m:
        gb = int(m.group(1))
    speed = metrics.get('ram_speed') or 3200
    is_ddr5 = 'DDR5' in (title or '').upper() or speed >= 4400
    is_ddr3 = 'DDR3' in (title or '').upper() or (0 < speed <= 1866)
    if is_ddr5:
        u_per_g, n_per_g = (19, 26) if speed >= 6000 else (16, 22)
    elif is_ddr3:
        u_per_g, n_per_g = (4.5, 8)
    else:
        u_per_g, n_per_g = (11.5, 16.5) if speed >= 3600 else (9.5, 14)

    premium = 1.12 if any(b in (title or '') for b in ('芝奇', '海盗船', '金士顿', '阿斯加特', '宏碁')) else 1.0
    used = max(40, round(gb * u_per_g * premium / 10) * 10)
    new = max(70, round(gb * n_per_g * premium / 10) * 10)
    tier = 'T0' if gb >= 64 else ('T1' if (gb >= 32 and is_ddr5) else ('T2' if gb >= 32 or (gb >= 16 and is_ddr5) else ('T3' if gb >= 16 else 'T4')))
    return {'used': used, 'new': new, 'tier': tier, 'tier_label': TIERS[tier][0]}


def eval_board(title, detail, is_laptop=False):
    if is_laptop:
        return {'used': 450, 'new': 750, 'note': '笔记本主板'}
    up = (title or '').upper()
    if re.search(r'\b(Z890|Z790|X870E?|X670E?)\b', up):
        used, new, tier = 1450, 2199, 'T0'
    elif re.search(r'\b(Z690|Z590|X570|B850|B650E)\b', up):
        used, new, tier = 899, 1399, 'T1'
    elif re.search(r'\b(B760|B660|B650|B550|Z490|Z390)\b', up):
        used, new, tier = 580, 899, 'T2'
    elif re.search(r'\b(B560|B460|B450|B360|B365|H610|A620|A520)\b', up):
        used, new, tier = 320, 499, 'T3'
    elif re.search(r'\b(H510|H410|H310|H110|B250|B150|B85|H81|X99|X79|A320)\b', up):
        used, new, tier = 160, 280, 'T4'
    else:
        used, new, tier = 450, 699, 'T2'

    if any(b in (title or '') for b in ('华硕', '微星', '技嘉')):
        used = round(used * 1.12 / 10) * 10
        new = round(new * 1.15 / 10) * 10
    return {'used': used, 'new': new, 'tier': tier, 'tier_label': TIERS[tier][0]}


def eval_disk(title, detail):
    s = (title or '') + ' ' + (detail or '')
    gb = 512
    m_tb = re.search(r'([\d.]+)\s*TB', s, re.I)
    m_gb = re.search(r'(\d+)\s*GB', s, re.I)
    if m_tb:
        gb = float(m_tb.group(1)) * 1000
    elif m_gb:
        gb = float(m_gb.group(1))

    is_nvme = 'NVME' in s.upper() or '固态' in s
    is_hdd = '机械' in s or 'HDD' in s.upper()
    if is_hdd:
        used = max(40, round((gb / 1000) * 130 / 10) * 10)
        new = max(90, round((gb / 1000) * 240 / 10) * 10)
    elif is_nvme:
        used = max(70, round((gb / 1000) * 310 / 10) * 10)
        new = max(120, round((gb / 1000) * 430 / 10) * 10)
    else:
        used = max(55, round((gb / 1000) * 240 / 10) * 10)
        new = max(99, round((gb / 1000) * 340 / 10) * 10)

    if any(b in (title or '') for b in ('三星', '致态', 'SK海力士', '西部数据')):
        used = round(used * 1.12 / 10) * 10
        new = round(new * 1.15 / 10) * 10
    return {'used': used, 'new': new}


def eval_monitor(title, detail, is_laptop=False):
    s = (title or '') + ' ' + (detail or '')
    m_in = re.search(r'([\d.]+)\s*英寸', s)
    inch = float(m_in.group(1)) if m_in else (15.6 if is_laptop else 24.0)
    if is_laptop and inch <= 18.5:
        return {'used': 0, 'new': 0, 'note': '笔记本内置屏幕'}

    m_res = re.search(r'(\d{3,4})×(\d{3,4})', s)
    w, h = (int(m_res.group(1)), int(m_res.group(2))) if m_res else (1920, 1080)
    m_hz = re.search(r'@\s*(\d+)\s*Hz', s, re.I)
    hz = int(m_hz.group(1)) if m_hz else 60

    if w >= 3400 or h >= 2000:  # 4K / 准4K带鱼
        used, new = (1350, 1999) if hz >= 120 else (799, 1299)
    elif w >= 2500 or h >= 1400:  # 2K
        used, new = (999, 1499) if hz >= 200 else ((650, 999) if hz >= 120 else (450, 699))
    else:  # 1080P
        used, new = (480, 749) if hz >= 144 else (260, 429)

    if inch >= 31:
        used, new = round(used * 1.2 / 10) * 10, round(new * 1.2 / 10) * 10
    return {'used': used, 'new': new}


# ---------------------------------------------------------------- 整机评估入口
def enrich(rep):
    """对采集到的 report 进行全量市场价格估算与天梯性能评级,原地写入并返回 rep。"""
    if not rep or not isinstance(rep.get('items'), list):
        return rep
    hd = rep.get('header', {})
    metrics = rep.setdefault('metrics', {})
    is_laptop = '笔记本' in (hd.get('model') or '')

    total_used = 0
    total_new = 0
    cat_totals = {'gpu': [0, 0], 'cpu': [0, 0], 'mem_disk': [0, 0], 'board_case': [0, 0], 'periph': [0, 0]}

    best_cpu = {'score': 0, 'tier': 'T3', 'name': '-', 'pct': 50, 'used': 0, 'new': 0}
    best_gpu = {'score': 0, 'tier': 'T4', 'name': '-', 'pct': 20, 'used': 0, 'new': 0}

    for item in rep['items']:
        k = item.get('key')
        item_used, item_new = 0, 0
        for row in item.get('rows', []):
            t, d = row.get('t', ''), row.get('d', '')
            if k == 'cpu':
                ev = eval_cpu(t, d, metrics)
                if ev['score'] >= best_cpu['score']:
                    best_cpu = {'score': ev['score'], 'tier': ev['tier'], 'name': ev['std_name'],
                                'pct': ev['pct'], 'used': ev['used'], 'new': ev['new']}
                cat_totals['cpu'][0] += ev['used']
                cat_totals['cpu'][1] += ev['new']
            elif k == 'gpu':
                ev = eval_gpu(t, d, metrics)
                if ev['score'] >= best_gpu['score']:
                    best_gpu = {'score': ev['score'], 'tier': ev['tier'], 'name': ev['std_name'],
                                'pct': ev['pct'], 'used': ev['used'], 'new': ev['new']}
                cat_totals['gpu'][0] += ev['used']
                cat_totals['gpu'][1] += ev['new']
            elif k == 'mem':
                ev = eval_mem(t, d, metrics)
                cat_totals['mem_disk'][0] += ev['used']
                cat_totals['mem_disk'][1] += ev['new']
            elif k == 'board':
                ev = eval_board(t, d, is_laptop)
                cat_totals['board_case'][0] += ev['used']
                cat_totals['board_case'][1] += ev['new']
            elif k == 'disk':
                ev = eval_disk(t, d)
                cat_totals['mem_disk'][0] += ev['used']
                cat_totals['mem_disk'][1] += ev['new']
            elif k == 'monitor':
                ev = eval_monitor(t, d, is_laptop)
                cat_totals['periph'][0] += ev['used']
                cat_totals['periph'][1] += ev['new']
            elif k == 'net':
                ev = {'used': 60, 'new': 110} if 'wi-fi' in t.lower() or 'wireless' in t.lower() else {'used': 0, 'new': 0, 'note': '主板集成'}
                cat_totals['periph'][0] += ev['used']
                cat_totals['periph'][1] += ev['new']
            elif k == 'sound':
                ev = {'used': 0, 'new': 0, 'note': '主板/显卡内置'}
            else:
                ev = {'used': 0, 'new': 0}

            row['_eval'] = ev
            item_used += ev.get('used', 0)
            item_new += ev.get('new', 0)

        item['_used'] = item_used
        item['_new'] = item_new
        total_used += item_used
        total_new += item_new

    # 机电散 / 笔记本模具折算
    core_used = cat_totals['cpu'][0] + cat_totals['gpu'][0]
    if is_laptop:
        extra_used, extra_new = 450, 750
        extra_label = '笔记本模具/屏幕/电池折算'
    else:
        if core_used >= 8000:
            extra_used, extra_new = 750, 1299
        elif core_used >= 3500:
            extra_used, extra_new = 420, 750
        elif core_used >= 1500:
            extra_used, extra_new = 240, 420
        else:
            extra_used, extra_new = 120, 220
        extra_label = '机箱/电源/散热器基础估算'

    cat_totals['board_case'][0] += extra_used
    cat_totals['board_case'][1] += extra_new
    total_used += extra_used
    total_new += extra_new

    # 综合性能分與整机段位
    total_score = round(best_cpu['score'] * 0.42 + best_gpu['score'] * 0.58)
    beat_pct = max(8, min(99, round(100 * (total_score / 41000) ** 0.58)))
    if total_score >= 28000:
        ov_tier, ov_title = 'T0', 'T0 · 4K 殿堂级发烧战神'
    elif total_score >= 19500:
        ov_tier, ov_title = 'T1', 'T1 · 2K/4K 高端电竞主机'
    elif total_score >= 12000:
        ov_tier, ov_title = 'T2', 'T2 · 主流畅玩甜点主机'
    elif total_score >= 6500:
        ov_tier, ov_title = 'T3', 'T3 · 实用网游与生产力主机'
    else:
        ov_tier, ov_title = 'T4', 'T4 · 经典办公亮机配置'

    # 同步到 metrics 方便双机对比使用
    metrics['cpu_score'] = best_cpu['score']
    metrics['gpu_score'] = best_gpu['score']
    metrics['used_price'] = total_used
    metrics['new_price'] = total_new

    rep['valuation'] = {
        'total_used': total_used,
        'total_new': total_new,
        'extra_used': extra_used,
        'extra_new': extra_new,
        'extra_label': extra_label,
        'cpu': best_cpu,
        'gpu': best_gpu,
        'total_score': total_score,
        'overall_tier': ov_tier,
        'overall_title': ov_title,
        'beat_pct': beat_pct,
        'breakdown': [
            ('显卡', cat_totals['gpu'][0], cat_totals['gpu'][1], (255, 92, 124)),
            ('处理器', cat_totals['cpu'][0], cat_totals['cpu'][1], (56, 189, 248)),
            ('内存与硬盘', cat_totals['mem_disk'][0], cat_totals['mem_disk'][1], (52, 211, 153)),
            ('主板与机电', cat_totals['board_case'][0], cat_totals['board_case'][1], (251, 191, 36)),
            ('显示器与外设', cat_totals['periph'][0], cat_totals['periph'][1], (167, 139, 250)),
        ],
    }
    return rep
