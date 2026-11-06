#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HardwareShot 云端配置天梯榜 & 在线 PK 平台后端服务 (零第三方依赖: Python3 标准库 + SQLite3)。"""
import datetime
import hashlib
import json
import os
import re
import sqlite3
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, 'data')
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, 'pk.db')
DB_LOCK = threading.Lock()
PORT = int(os.environ.get('PORT', '3041'))

ADMIN_KEY_FILE = os.path.join(DATA_DIR, 'admin.key')
ADMIN_KEY = os.environ.get('ADMIN_KEY', '').strip()
if not ADMIN_KEY:
    if os.path.isfile(ADMIN_KEY_FILE):
        try:
            with open(ADMIN_KEY_FILE, 'r', encoding='utf-8') as f:
                ADMIN_KEY = f.read().strip()
        except Exception:
            pass
    if not ADMIN_KEY:
        ADMIN_KEY = 'along888'
        try:
            with open(ADMIN_KEY_FILE, 'w', encoding='utf-8') as f:
                f.write(ADMIN_KEY)
        except Exception:
            pass


def get_admin_key():
    global ADMIN_KEY
    if os.path.isfile(ADMIN_KEY_FILE):
        try:
            with open(ADMIN_KEY_FILE, 'r', encoding='utf-8') as f:
                k = f.read().strip()
                if k:
                    ADMIN_KEY = k
        except Exception:
            pass
    return ADMIN_KEY


def set_admin_key(new_key):
    global ADMIN_KEY
    new_key = (new_key or '').strip()
    if not new_key:
        raise ValueError('密码不能为空')
    ADMIN_KEY = new_key
    with open(ADMIN_KEY_FILE, 'w', encoding='utf-8') as f:
        f.write(new_key)
    return True


def delete_configs(ids):
    if not ids:
        return 0
    with DB_LOCK, sqlite3.connect(DB_PATH) as conn:
        qmarks = ','.join(['?'] * len(ids))
        cur = conn.execute(f'DELETE FROM configs WHERE id IN ({qmarks})', ids)
        conn.commit()
        return cur.rowcount


def init_db():
    with DB_LOCK, sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS configs (
                id TEXT PRIMARY KEY,
                nickname TEXT,
                model TEXT,
                cpu_name TEXT,
                gpu_name TEXT,
                ram_desc TEXT,
                total_score INTEGER DEFAULT 0,
                cpu_score INTEGER DEFAULT 0,
                gpu_score INTEGER DEFAULT 0,
                total_used INTEGER DEFAULT 0,
                total_new INTEGER DEFAULT 0,
                overall_tier TEXT,
                overall_title TEXT,
                beat_pct INTEGER DEFAULT 50,
                scan_time TEXT,
                updated_at TEXT,
                report_json TEXT
            )
        ''')
        conn.commit()


def _compute_fun_tag(rep, total_score, total_used, total_new, cpu_score, gpu_score):
    """根据硬件特征自动计算具有社交传播属性的趣味装机称号与标签。"""
    metrics = rep.get('metrics') or {}
    items = {it.get('key'): it for it in rep.get('items', [])}

    # 显卡占比
    gpu_ratio = (gpu_score / max(total_score, 1)) if total_score > 0 else 0
    gpu_price_ratio = 0
    val = rep.get('valuation') or {}
    gpu_used = val.get('gpu', {}).get('used', 0)
    if total_used > 0 and gpu_used > 0:
        gpu_price_ratio = gpu_used / total_used

    # 硬盘总容量
    disk_gb = metrics.get('disk_total_gb', 0)
    # 屏幕高刷
    hz = metrics.get('monitor_hz', 60)
    cpu_cores = metrics.get('cpu_cores', 4)

    # 判定称号
    if total_used >= 25000 or total_new >= 35000:
        return '👑 钞能力霸皇', '全服身价天花板，顶级硬件拉满，毫无妥协的赛博富豪'
    if gpu_price_ratio >= 0.58 or (gpu_score >= 28000 and cpu_score < 18000):
        return '🎮 卡比人贵', '显卡身价撑起大半壁江山，纯粹为了极致画质与游戏而生'
    if gpu_score >= 26000 and cpu_cores <= 8 and cpu_score < 16000:
        return '🏇 吕布骑驴', '旗舰卡皇配入门搭子，显卡在大喊“CPU你带得动我吗”'
    if total_used <= 6000 and total_score >= 18000:
        return '🛠️ 垃圾佬狂喜', '极致质价比刀锋战士，花最少的银子榨干每一丝极限战力'
    if disk_gb >= 4000:
        return '💾 固态仓鼠党', f'总固态储备超 {round(disk_gb/1024, 1)} TB，数字生命安乐窝，存满也不慌'
    if hz >= 240:
        return '⚡ 极致高刷狂', f'{hz}Hz 视网膜极速电竞屏，物理外挂，眨眼即被锁定'
    if cpu_score >= 32000 and gpu_score >= 32000:
        return '💥 双T0核弹井', 'CPU与GPU双双登顶第一梯队，4K全光追渲染毫无波澜'
    if total_score >= 28000:
        return '⚔️ 4K旗舰战神', '全画质通杀级主机，大型生产力与3A大作得力助手'
    if total_score >= 20000:
        return '🎯 甜点电竞主力', '主流网游与2K电竞黄金黄金水桶机，均衡耐打'
    return '🌱 实用主义先锋', '高性价比日常战斗伙伴，满足学习、办公与轻度娱乐'


def _is_igpu(row):
    """判断某一行显卡是否为 CPU 内置核显。"""
    ev = row.get('_eval') or {}
    if ev.get('note') == 'CPU内置核显':
        return True
    t = (row.get('t') or '').lower()
    s = (row.get('s') or '').lower()
    igpu_keywords = [
        'intel(r) uhd', 'intel uhd', 'intel(r) iris', 'intel iris', 'intel(r) hd', 'intel hd graphics',
        'amd radeon(tm) graphics', 'amd radeon graphics', 'radeon(tm) graphics', 'radeon graphics', 'vega 7', 'vega 8'
    ]
    for kw in igpu_keywords:
        if kw in t or kw in s:
            return True
    return False


def _pick_primary_gpu(gpu_rows):
    """
    智能挑选主力显卡:
    当存在多张显卡(如独显+核显)时，优先挑选性能/显存/估值最高的独立显卡出战；
    绝不用核显冒充主力独显，同时输出多显卡副标。
    """
    if not gpu_rows:
        return {'primary_name': '-', 'sub_desc': '', 'row': {}, 'is_multi': False}

    discrete_gpus = []
    igpus = []

    for r in gpu_rows:
        if _is_igpu(r):
            igpus.append(r)
        else:
            discrete_gpus.append(r)

    # 排序权重: 性能跑分 score > 二手估值 used > 显存
    def gpu_rank_score(r):
        ev = r.get('_eval') or {}
        return (ev.get('score', 0) * 100) + ev.get('used', 0)

    if discrete_gpus:
        discrete_gpus.sort(key=gpu_rank_score, reverse=True)
        primary = discrete_gpus[0]
    else:
        igpus.sort(key=gpu_rank_score, reverse=True)
        primary = igpus[0]

    is_multi = len(gpu_rows) > 1
    sub_desc = ''
    if is_multi:
        if discrete_gpus and igpus:
            sub_desc = f'双显卡配置 (主力独显 + 辅助核显: {igpus[0].get("t", "").split("(")[0].strip()})'
        elif len(discrete_gpus) > 1:
            sub_desc = f'多独显系统 (共 {len(discrete_gpus)} 张独立显卡)'
        else:
            sub_desc = f'多显卡架构 (共 {len(gpu_rows)} 张显示适配器)'

    return {
        'primary_name': primary.get('t', '-'),
        'sub_desc': sub_desc,
        'row': primary,
        'is_multi': is_multi,
        'all_rows': gpu_rows
    }


def _aggregate_disks(disk_rows, metrics):
    """
    智能聚合多硬盘:
    当存在多块固态/机械硬盘时，累加总存储容量，以旗舰主盘/系统盘为主标，
    并输出多盘规格清单。
    """
    if not disk_rows:
        return {'primary_name': '-', 'total_gb': 0, 'summary_label': '-', 'disks': []}

    disks_info = []
    calc_total_gb = 0

    for idx, r in enumerate(disk_rows, 1):
        t = r.get('t', '')
        s = r.get('s', '')
        # 尝试提取容量数字
        cap_gb = 0
        m_cap = re.search(r'(\d+(?:\.\d+)?)\s*([tg]b)', f'{t} {s}', re.I)
        if m_cap:
            val_num = float(m_cap.group(1))
            unit = m_cap.group(2).lower()
            if unit == 'tb':
                cap_gb = int(val_num * 1000)
            else:
                cap_gb = int(val_num)
        calc_total_gb += cap_gb

        disks_info.append({
            'index': idx,
            'name': t,
            'desc': s,
            'cap_gb': cap_gb,
            'eval': r.get('_eval', {})
        })

    metric_total = metrics.get('disk_total_gb', 0)
    final_total_gb = max(calc_total_gb, metric_total)

    # 格式化总容量 (如 6000 GB -> 6.0 TB)
    if final_total_gb >= 1000:
        total_str = f'{round(final_total_gb / 1000.0, 1)} TB'
    else:
        total_str = f'{final_total_gb} GB'

    # 挑选主力主盘 (估值最高或包含系统标识)
    def disk_rank(d):
        ev = d['eval']
        return ev.get('used', 0) * 100 + d['cap_gb']

    sorted_disks = sorted(disks_info, key=disk_rank, reverse=True)
    primary = sorted_disks[0] if sorted_disks else {'name': '-'}

    ssd_count = sum(1 for d in disks_info if any(k in f"{d['name']} {d['desc']}".lower() for k in ['ssd', 'nvme', '固态']))
    type_label = f'{len(disks_info)} 块 SSD 固态' if ssd_count == len(disks_info) else f'{len(disks_info)} 块硬盘'

    summary_label = f'总存储 {total_str} (共 {type_label})' if len(disks_info) > 1 else primary['name']

    return {
        'primary_name': primary['name'],
        'total_gb': final_total_gb,
        'total_str': total_str,
        'summary_label': summary_label,
        'disks': disks_info
    }


def _extract_summary(rep):
    nick = (rep.get('nickname') or '').strip() or '神秘玩家'
    hd = rep.get('header') or {}
    val = rep.get('valuation') or {}
    metrics = rep.get('metrics') or {}
    model = (hd.get('model') or '').strip() or '台式电脑'

    cpu_name, ram_desc = '-', '-'
    gpu_rows = []
    disk_rows = []

    for it in rep.get('items', []):
        k = it.get('key')
        rows = it.get('rows') or []
        if not rows:
            continue
        if k == 'cpu':
            cpu_name = rows[0].get('t', '-')
        elif k == 'gpu':
            gpu_rows = rows
        elif k in ('mem', 'ram'):
            ram_desc = it.get('summary') or rows[0].get('t', '-')
        elif k == 'disk':
            disk_rows = rows

    # 智能挑选主力显卡 (排除核显作为首选)
    gpu_picked = _pick_primary_gpu(gpu_rows)
    gpu_name = gpu_picked['primary_name']

    # 智能聚合多硬盘
    disk_picked = _aggregate_disks(disk_rows, metrics)
    metrics['disk_total_gb'] = disk_picked['total_gb']

    total_score = int(val.get('total_score') or (metrics.get('cpu_score', 0) * 0.42 + metrics.get('gpu_score', 0) * 0.58) or 0)
    cpu_score = int(val.get('cpu', {}).get('score') or metrics.get('cpu_score') or 0)
    gpu_score = int(val.get('gpu', {}).get('score') or metrics.get('gpu_score') or 0)
    total_used = int(val.get('total_used') or metrics.get('used_price') or 0)
    total_new = int(val.get('total_new') or metrics.get('new_price') or 0)
    overall_tier = val.get('overall_tier') or 'T2'
    overall_title = val.get('overall_title') or 'T2 · 主流畅玩甜点主机'
    beat_pct = int(val.get('beat_pct') or 60)
    scan_time = rep.get('scan_time') or datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

    # 计算质价比指数 (战力 / 二手价格 * 100)
    value_ratio = round((total_score * 100.0) / max(total_used, 1000), 1) if total_used > 0 else 0
    fun_tag, fun_desc = _compute_fun_tag(rep, total_score, total_used, total_new, cpu_score, gpu_score)

    # 存入 rep 自身，方便前端详情直接获取
    val['fun_tag'] = fun_tag
    val['fun_desc'] = fun_desc
    val['value_ratio'] = value_ratio
    val['gpu_picked'] = gpu_picked
    val['disk_picked'] = disk_picked
    rep['valuation'] = val
    rep['metrics'] = metrics

    # 以 昵称 + CPU + 显卡 生成稳定的 8 位短 ID
    seed = f'{nick.lower()}::{cpu_name.lower()}::{gpu_name.lower()}'
    short_id = hashlib.sha1(seed.encode('utf-8')).hexdigest()[:8]

    return {
        'id': short_id,
        'nickname': nick[:32],
        'model': model[:64],
        'cpu_name': cpu_name[:80],
        'gpu_name': gpu_name[:80],
        'ram_desc': ram_desc[:80],
        'total_score': total_score,
        'cpu_score': cpu_score,
        'gpu_score': gpu_score,
        'total_used': total_used,
        'total_new': total_new,
        'overall_tier': overall_tier,
        'overall_title': overall_title,
        'beat_pct': beat_pct,
        'value_ratio': value_ratio,
        'fun_tag': fun_tag,
        'fun_desc': fun_desc,
        'gpu_picked': gpu_picked,
        'disk_picked': disk_picked,
        'scan_time': scan_time,
        'updated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }


def save_config(rep):
    if not isinstance(rep, dict) or rep.get('app') != 'HardwareShot' or not isinstance(rep.get('items'), list):
        raise ValueError('无效的配置文件格式 (需要由「硬件配置助手」生成)')
    s = _extract_summary(rep)
    rep['nickname'] = s['nickname']
    raw_json = json.dumps(rep, ensure_ascii=False)
    with DB_LOCK, sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            INSERT INTO configs (
                id, nickname, model, cpu_name, gpu_name, ram_desc,
                total_score, cpu_score, gpu_score, total_used, total_new,
                overall_tier, overall_title, beat_pct, scan_time, updated_at, report_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                nickname=excluded.nickname,
                model=excluded.model,
                cpu_name=excluded.cpu_name,
                gpu_name=excluded.gpu_name,
                ram_desc=excluded.ram_desc,
                total_score=excluded.total_score,
                cpu_score=excluded.cpu_score,
                gpu_score=excluded.gpu_score,
                total_used=excluded.total_used,
                total_new=excluded.total_new,
                overall_tier=excluded.overall_tier,
                overall_title=excluded.overall_title,
                beat_pct=excluded.beat_pct,
                scan_time=excluded.scan_time,
                updated_at=excluded.updated_at,
                report_json=excluded.report_json
        ''', (
            s['id'], s['nickname'], s['model'], s['cpu_name'], s['gpu_name'], s['ram_desc'],
            s['total_score'], s['cpu_score'], s['gpu_score'], s['total_used'], s['total_new'],
            s['overall_tier'], s['overall_title'], s['beat_pct'], s['scan_time'], s['updated_at'], raw_json
        ))
        conn.commit()
        rows = conn.execute('SELECT id FROM configs ORDER BY total_score DESC, total_used DESC').fetchall()
        ids = [r[0] for r in rows]
        rank = (ids.index(s['id']) + 1) if s['id'] in ids else 1
        total = len(ids)
    return s, rank, total


def list_configs():
    with DB_LOCK, sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute('''
            SELECT id, nickname, model, cpu_name, gpu_name, ram_desc,
                   total_score, cpu_score, gpu_score, total_used, total_new,
                   overall_tier, overall_title, beat_pct, scan_time, updated_at, report_json
            FROM configs
            ORDER BY total_score DESC, total_used DESC
            LIMIT 200
        ''').fetchall()
    out = []
    for idx, r in enumerate(rows, 1):
        d = dict(r)
        d['rank'] = idx
        raw = d.pop('report_json', '{}')
        try:
            rep = json.loads(raw)
            d['report'] = rep
            # 实时智能提取主力独显、多硬盘聚合及趣味称号
            s_dyn = _extract_summary(rep)
            d['gpu_name'] = s_dyn['gpu_name']  # 修正老数据存成核显的问题
            d['fun_tag'] = s_dyn['fun_tag']
            d['fun_desc'] = s_dyn['fun_desc']
            d['value_ratio'] = s_dyn['value_ratio']
            d['gpu_picked'] = s_dyn['gpu_picked']
            d['disk_picked'] = s_dyn['disk_picked']
        except Exception:
            d['report'] = {}
            d['fun_tag'] = '🎯 实力战将'
            d['fun_desc'] = ''
            d['value_ratio'] = round((d['total_score'] * 100.0) / max(d['total_used'], 1000), 1)
            d['gpu_picked'] = {'primary_name': d.get('gpu_name', '-'), 'sub_desc': '', 'is_multi': False}
            d['disk_picked'] = {'primary_name': '-', 'total_gb': 0, 'summary_label': '-', 'disks': []}
        out.append(d)
    return out


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path, content_type, download_name=None, head_only=False):
        if not os.path.isfile(path):
            self.send_error(404, 'Not Found')
            return
        size = os.path.getsize(path)
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(size))
        if download_name:
            enc_name = urllib.parse.quote(download_name)
            self.send_header('Content-Disposition', f"attachment; filename=\"HardwareShot.zip\"; filename*=UTF-8''{enc_name}")
        self.end_headers()
        if not head_only:
            with open(path, 'rb') as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)

    def do_OPTIONS(self):
        self._send_json({'ok': True})

    def do_HEAD(self):
        self._handle_get(head_only=True)

    def do_GET(self):
        self._handle_get(head_only=False)

    def _verify_admin(self, body=None):
        auth_key = self.headers.get('X-Admin-Key')
        if not auth_key and isinstance(body, dict):
            auth_key = body.get('admin_key') or body.get('key')
        expected = get_admin_key()
        return bool(auth_key and auth_key == expected)

    def _handle_get(self, head_only=False):
        parsed = urllib.parse.urlparse(self.path)
        p = urllib.parse.unquote(parsed.path)
        if p == '/api/configs':
            return self._send_json({'ok': True, 'items': list_configs()})
        if p == '/api/admin/configs':
            if not self._verify_admin():
                return self._send_json({'ok': False, 'error': '未授权或管理密钥错误'}, 403)
            return self._send_json({'ok': True, 'items': list_configs(), 'db_size': os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0})
        if p == '/api/admin/export':
            if not self._verify_admin():
                return self._send_json({'ok': False, 'error': '未授权或管理密钥错误'}, 403)
            return self._send_json({'ok': True, 'exported_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'items': list_configs()})
        if p.startswith('/api/config/'):
            cid = p.split('/api/config/', 1)[1].strip('/')
            for item in list_configs():
                if item['id'] == cid:
                    return self._send_json({'ok': True, 'item': item, 'report': item.get('report')})
            return self._send_json({'ok': False, 'error': '未找到该配置记录'}, 404)
        if p in ('/download/硬件配置助手.zip', '/download/HardwareShot.zip', '/硬件配置助手.zip'):
            zp = os.path.join(HERE, '硬件配置助手.zip')
            return self._send_file(zp, 'application/zip', '硬件配置助手.zip', head_only=head_only)
        if p in ('/admin', '/admin.html'):
            return self._send_file(os.path.join(HERE, 'admin.html'), 'text/html; charset=utf-8', head_only=head_only)
        if p in ('/', '/index.html'):
            return self._send_file(os.path.join(HERE, 'index.html'), 'text/html; charset=utf-8', head_only=head_only)
        self.send_error(404, 'Not Found')

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        p = parsed.path

        # 管理员接口
        if p.startswith('/api/admin/'):
            try:
                length = int(self.headers.get('Content-Length', '0'))
                raw = self.rfile.read(length).decode('utf-8', 'replace') if length > 0 else '{}'
                data = json.loads(raw) if raw.strip() else {}
            except Exception as ex:
                return self._send_json({'ok': False, 'error': f'请求体解析失败: {ex}'}, 400)

            if p == '/api/admin/auth':
                key = (data.get('key') or data.get('admin_key') or '').strip()
                if key and key == get_admin_key():
                    return self._send_json({'ok': True, 'msg': '认证成功'})
                return self._send_json({'ok': False, 'error': '管理密钥错误'}, 403)

            if not self._verify_admin(data):
                return self._send_json({'ok': False, 'error': '未授权或管理密钥错误'}, 403)

            if p == '/api/admin/delete':
                ids = data.get('ids', [])
                if isinstance(ids, str):
                    ids = [ids]
                deleted = delete_configs(ids)
                return self._send_json({'ok': True, 'deleted': deleted, 'msg': f'成功删除 {deleted} 条记录'})

            if p == '/api/admin/clear-all':
                with DB_LOCK, sqlite3.connect(DB_PATH) as conn:
                    cur = conn.execute('DELETE FROM configs')
                    conn.commit()
                    deleted = cur.rowcount
                return self._send_json({'ok': True, 'deleted': deleted, 'msg': f'全服数据已清空，共删除 {deleted} 条记录'})

            if p == '/api/admin/change-key':
                new_key = data.get('new_key', '').strip()
                if not new_key:
                    return self._send_json({'ok': False, 'error': '新密码不能为空'}, 400)
                set_admin_key(new_key)
                return self._send_json({'ok': True, 'msg': '管理密钥已更新成功'})

            return self.send_error(404, 'Not Found')

        if p == '/api/upload':
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length <= 0 or length > 2 * 1024 * 1024:
                    return self._send_json({'ok': False, 'error': '请求体积异常'}, 400)
                raw = self.rfile.read(length).decode('utf-8', 'replace')
                rep = json.loads(raw)
                summary, rank, total = save_config(rep)
                host = self.headers.get('Host') or 'pc.alonglfb.com'
                proto = self.headers.get('X-Forwarded-Proto') or 'https'
                base_url = f'{proto}://{host}'
                return self._send_json({
                    'ok': True,
                    'id': summary['id'],
                    'rank': rank,
                    'total': total,
                    'summary': summary,
                    'url': f'{base_url}/?id={summary["id"]}',
                    'pk_url': f'{base_url}/?pk={summary["id"]}',
                })
            except Exception as ex:
                return self._send_json({'ok': False, 'error': str(ex)}, 400)
        self.send_error(404, 'Not Found')


if __name__ == '__main__':
    init_db()
    print(f'HardwareShot PK Server listening on http://127.0.0.1:{PORT}')
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()

