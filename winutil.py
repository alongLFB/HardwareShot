# -*- coding: utf-8 -*-
"""Windows 相关的小工具:DPI、剪贴板图片、打开资源管理器、设置读写。"""
import ctypes
import getpass
import io
import json
import os
import subprocess
from ctypes import wintypes


def enable_dpi():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def virtual_screen_origin():
    u = ctypes.windll.user32
    return u.GetSystemMetrics(76), u.GetSystemMetrics(77)  # SM_XVIRTUALSCREEN / SM_YVIRTUALSCREEN


def copy_image_to_clipboard(img):
    """把 PIL 图片以 DIB 格式放进剪贴板,可直接在微信/QQ/钉钉里 Ctrl+V。"""
    buf = io.BytesIO()
    img.convert('RGB').save(buf, 'BMP')
    data = buf.getvalue()[14:]  # 去掉 BITMAPFILEHEADER
    k, u = ctypes.windll.kernel32, ctypes.windll.user32
    k.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    k.GlobalAlloc.restype = ctypes.c_void_p
    k.GlobalLock.argtypes = [ctypes.c_void_p]
    k.GlobalLock.restype = ctypes.c_void_p
    k.GlobalUnlock.argtypes = [ctypes.c_void_p]
    u.OpenClipboard.argtypes = [wintypes.HWND]
    u.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
    u.SetClipboardData.restype = ctypes.c_void_p
    h = k.GlobalAlloc(0x0002, len(data))  # GMEM_MOVEABLE
    p = k.GlobalLock(h)
    ctypes.memmove(p, data, len(data))
    k.GlobalUnlock(h)
    ok = False
    for _ in range(10):  # 剪贴板可能被占用,重试
        if u.OpenClipboard(None):
            ok = True
            break
        ctypes.windll.kernel32.Sleep(50)
    if not ok:
        raise RuntimeError('无法打开剪贴板')
    try:
        u.EmptyClipboard()
        u.SetClipboardData(8, h)  # CF_DIB
    finally:
        u.CloseClipboard()


def reveal_in_explorer(path):
    if os.path.isfile(path):
        subprocess.Popen(['explorer', '/select,', os.path.normpath(path)])
    else:
        os.startfile(path)


def settings_path():
    d = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'HardwareShot')
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, 'settings.json')


def default_save_dir():
    pics = os.path.join(os.path.expanduser('~'), 'Pictures')
    base = pics if os.path.isdir(pics) else os.path.expanduser('~')
    return os.path.join(base, '硬件配置')


def default_nickname():
    """获取 Windows 当前系统用户名作为默认昵称"""
    try:
        name = getpass.getuser()
    except Exception:
        name = os.environ.get('USERNAME') or os.environ.get('USER') or ''
    return (name or '').strip()


def load_settings():
    def_nick = default_nickname()
    s = {'save_dir': default_save_dir(), 'nickname': def_nick, 'theme': '科技蓝', 'detail': True, 'auto_copy': True}
    try:
        with open(settings_path(), encoding='utf-8') as f:
            data = json.load(f)
            s.update(data)
            if not (s.get('nickname') or '').strip():
                s['nickname'] = def_nick
    except Exception:
        pass
    return s


def save_settings(s):
    try:
        with open(settings_path(), 'w', encoding='utf-8') as f:
            json.dump(s, f, ensure_ascii=False, indent=1)
    except Exception:
        pass
