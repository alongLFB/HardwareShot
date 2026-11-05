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
        elif k == 'mem':
            ram_desc = rows[0].get('t', '-')

    total_score = int(val.get('total_score') or (metrics.get('cpu_score', 0) * 0.42 + metrics.get('gpu_score', 0) * 0.58) or 0)
    cpu_score = int(val.get('cpu', {}).get('score') or metrics.get('cpu_score') or 0)
    gpu_score = int(val.get('gpu', {}).get('score') or metrics.get('gpu_score') or 0)
    total_used = int(val.get('total_used') or metrics.get('used_price') or 0)
    total_new = int(val.get('total_new') or metrics.get('new_price') or 0)
    overall_tier = val.get('overall_tier') or 'T2'
    overall_title = val.get('overall_title') or 'T2 · 主流畅玩甜点主机'
    beat_pct = int(val.get('beat_pct') or 60)
    scan_time = rep.get('scan_time') or datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

    # 以 昵称 + CPU + 显卡 生成稳定的 8 位短 ID, 同一玩家更新配置时自动覆盖旧记录不刷屏
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
        try:
            d['report'] = json.loads(d.pop('report_json'))
        except Exception:
            d['report'] = {}
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

