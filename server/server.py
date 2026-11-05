#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HardwareShot 云端配置天梯榜 & 在线 PK 平台后端服务 (零第三方依赖: Python3 标准库 + SQLite3)。"""
import datetime
import hashlib
import json
import os
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


def _extract_summary(rep):
    nick = (rep.get('nickname') or '').strip() or '神秘玩家'
    hd = rep.get('header') or {}
    val = rep.get('valuation') or {}
    metrics = rep.get('metrics') or {}
    model = (hd.get('model') or '').strip() or '台式电脑'

    cpu_name, gpu_name, ram_desc = '-', '-', '-'
    for it in rep.get('items', []):
        k = it.get('key')
        rows = it.get('rows') or []
        if not rows:
            continue
        if k == 'cpu':
            cpu_name = rows[0].get('t', '-')
        elif k == 'gpu':
            gpu_name = rows[0].get('t', '-')
        elif k in ('mem', 'ram'):
            ram_desc = it.get('summary') or rows[0].get('t', '-')

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
    rep['valuation'] = val

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
            val = rep.get('valuation') or {}
            # 补齐趣味称号与质价比
            if not val.get('fun_tag'):
                s_tmp = _extract_summary(rep)
                val = rep.get('valuation') or {}
            d['fun_tag'] = val.get('fun_tag') or '🎯 实力战将'
            d['fun_desc'] = val.get('fun_desc') or ''
            d['value_ratio'] = val.get('value_ratio') or round((d['total_score'] * 100.0) / max(d['total_used'], 1000), 1)
        except Exception:
            d['report'] = {}
            d['fun_tag'] = '🎯 实力战将'
            d['fun_desc'] = ''
            d['value_ratio'] = round((d['total_score'] * 100.0) / max(d['total_used'], 1000), 1)
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

    def _handle_get(self, head_only=False):
        parsed = urllib.parse.urlparse(self.path)
        p = urllib.parse.unquote(parsed.path)
        if p == '/api/configs':
            return self._send_json({'ok': True, 'items': list_configs()})
        if p.startswith('/api/config/'):
            cid = p.split('/api/config/', 1)[1].strip('/')
            for item in list_configs():
                if item['id'] == cid:
                    return self._send_json({'ok': True, 'item': item, 'report': item.get('report')})
            return self._send_json({'ok': False, 'error': '未找到该配置记录'}, 404)
        if p in ('/download/硬件配置助手.zip', '/download/HardwareShot.zip', '/硬件配置助手.zip'):
            zp = os.path.join(HERE, '硬件配置助手.zip')
            return self._send_file(zp, 'application/zip', '硬件配置助手.zip', head_only=head_only)
        if p in ('/', '/index.html'):
            return self._send_file(os.path.join(HERE, 'index.html'), 'text/html; charset=utf-8', head_only=head_only)
        self.send_error(404, 'Not Found')

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/api/upload':
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

