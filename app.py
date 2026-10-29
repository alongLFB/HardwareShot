# -*- coding: utf-8 -*-
"""硬件配置助手 - 主界面 + 区域截图"""
import datetime
import json
import os
import queue
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from PIL import Image, ImageGrab, ImageTk

import collector
import market
import renderer
import winutil

APP_NAME = '硬件配置助手'
SIDE_BG = '#0A56D8'
SIDE_HOVER = '#2C74F0'
GREEN = '#16C47F'
GREEN_HOVER = '#2FD893'
FONT = 'Microsoft YaHei UI'


class FlatButton(tk.Label):
    def __init__(self, master, text, command, bg=SIDE_BG, hover=SIDE_HOVER, font=None, **kw):
        super().__init__(master, text=text, bg=bg, fg='white', font=font, cursor='hand2', anchor='w', **kw)
        self._bg, self._hover, self._cmd = bg, hover, command
        self.bind('<Enter>', lambda e: self.config(bg=self._hover))
        self.bind('<Leave>', lambda e: self.config(bg=self._bg))
        self.bind('<Button-1>', lambda e: self._cmd())


class RegionSelector:
    """全屏半透明遮罩,拖动选择区域;Esc / 右键取消。"""

    def __init__(self, root, full, origin, callback):
        self.full, self.cb, self.done = full, callback, False
        W, H = full.size
        self.top = tk.Toplevel(root)
        self.top.overrideredirect(True)
        self.top.attributes('-topmost', True)
        self.top.geometry(f'{W}x{H}+{origin[0]}+{origin[1]}')
        self.c = tk.Canvas(self.top, width=W, height=H, highlightthickness=0, cursor='crosshair', bd=0)
        self.c.pack()
        self.photo = ImageTk.PhotoImage(full)
        self.c.create_image(0, 0, image=self.photo, anchor='nw')
        self.shade = [self.c.create_rectangle(0, 0, 0, 0, fill='black', stipple='gray50', width=0) for _ in range(4)]
        self.box = self.c.create_rectangle(0, 0, 0, 0, outline='#16C47F', width=2)
        self.label = self.c.create_text(0, 0, text='', fill='white', anchor='sw', font=(FONT, 11, 'bold'))
        self.labelbg = self.c.create_rectangle(0, 0, 0, 0, fill='#16C47F', width=0)
        self.c.tag_raise(self.label)
        self.hint = self.c.create_text(W // 2 + 0, 40, text='拖动鼠标选择截图区域    Esc / 右键 取消', fill='white',
                                       font=(FONT, 14, 'bold'))
        hb = self.c.bbox(self.hint)
        self.hintbg = self.c.create_rectangle(hb[0] - 16, hb[1] - 8, hb[2] + 16, hb[3] + 8, fill='#0A56D8', width=0)
        self.c.tag_lower(self.hintbg, self.hint)
        self._shade(0, 0, W, H)
        self.p0 = None
        self.c.bind('<ButtonPress-1>', self.press)
        self.c.bind('<B1-Motion>', self.drag)
        self.c.bind('<ButtonRelease-1>', self.release)
        self.c.bind('<Button-3>', lambda e: self.finish(None))
        self.top.bind('<Escape>', lambda e: self.finish(None))
        self.top.focus_force()
        self.c.focus_set()

    def _shade(self, x0, y0, x1, y1):
        W, H = self.full.size
        rects = [(0, 0, W, y0), (0, y1, W, H), (0, y0, x0, y1), (x1, y0, W, y1)]
        for item, r in zip(self.shade, rects):
            self.c.coords(item, *r)

    def press(self, e):
        self.p0 = (e.x, e.y)
        self.c.itemconfig(self.hint, state='hidden')
        self.c.itemconfig(self.hintbg, state='hidden')

    def drag(self, e):
        if not self.p0:
            return
        W, H = self.full.size
        x0, y0 = self.p0
        x1, y1 = max(0, min(W, e.x)), max(0, min(H, e.y))
        a, b, c, d = min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)
        self._shade(a, b, c, d)
        self.c.coords(self.box, a, b, c, d)
        self.c.itemconfig(self.label, text=f' {c - a} × {d - b} ')
        ly = b - 4 if b > 28 else d + 26
        self.c.coords(self.label, a, ly)
        bb = self.c.bbox(self.label)
        self.c.coords(self.labelbg, *bb)
        self.c.tag_raise(self.labelbg)
        self.c.tag_raise(self.label)

    def release(self, e):
        if not self.p0:
            return
        W, H = self.full.size
        x0, y0 = self.p0
        x1, y1 = max(0, min(W, e.x)), max(0, min(H, e.y))
        a, b, c, d = min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)
        if c - a < 6 or d - b < 6:
            self.p0 = None
            self._shade(0, 0, W, H)
            self.c.coords(self.box, 0, 0, 0, 0)
            return
        self.finish(self.full.crop((a, b, c, d)))

    def finish(self, img):
        if self.done:
            return
        self.done = True
        self.top.destroy()
        self.cb(img)


class ToastNotification:
    """悬浮通知条: 在右侧内容区顶部居中弹出精致提示, 包含操作状态、辅助说明、快捷操作按钮与自动倒计时消失。"""

    def __init__(self, parent, px_fn):
        self.parent = parent
        self.px = px_fn
        self.frame = None
        self._timer = None

    def show(self, title, message='', path=None, is_error=False, duration=3500):
        if self._timer:
            self.parent.after_cancel(self._timer)
            self._timer = None
        if self.frame:
            try:
                self.frame.destroy()
            except Exception:
                pass
            self.frame = None

        px = self.px
        f = lambda sz, b=False: (FONT, sz, 'bold') if b else (FONT, sz)
        bar_col = '#EF4444' if is_error else '#16C47F'
        icon = '✕  ' if is_error else '✔  '

        self.frame = tk.Frame(self.parent, bg='#181F2C', bd=0, highlightthickness=1,
                              highlightbackground='#3B82F6' if not is_error else '#EF4444')
        self.frame.place(relx=0.5, y=px(18), anchor='n')

        tk.Frame(self.frame, bg=bar_col, width=px(5)).pack(side='left', fill='y')

        content = tk.Frame(self.frame, bg='#181F2C', padx=px(14), pady=px(8))
        content.pack(side='left', fill='both', expand=True)

        row1 = tk.Frame(content, bg='#181F2C')
        row1.pack(fill='x')

        tk.Label(row1, text=icon + title, bg='#181F2C', fg='white', font=f(11, True)).pack(side='left')

        btns = tk.Frame(row1, bg='#181F2C')
        btns.pack(side='right', padx=(px(16), 0))

        if path and os.path.exists(path):
            def open_item():
                try:
                    os.startfile(path)
                except Exception:
                    pass

            def reveal_item():
                try:
                    winutil.reveal_in_explorer(path)
                except Exception:
                    pass

            b_rev = tk.Label(btns, text='打开文件夹', bg='#233044', fg='#93C5FD', font=f(9),
                             cursor='hand2', padx=px(8), pady=px(2))
            b_rev.pack(side='left', padx=(0, px(6)))
            b_rev.bind('<Enter>', lambda e, w=b_rev: w.config(bg='#334460'))
            b_rev.bind('<Leave>', lambda e, w=b_rev: w.config(bg='#233044'))
            b_rev.bind('<Button-1>', lambda e: reveal_item())

            if os.path.isfile(path) and path.lower().endswith(('.png', '.jpg')):
                b_op = tk.Label(btns, text='查看图片', bg='#233044', fg='#93C5FD', font=f(9),
                                cursor='hand2', padx=px(8), pady=px(2))
                b_op.pack(side='left', padx=(0, px(6)))
                b_op.bind('<Enter>', lambda e, w=b_op: w.config(bg='#334460'))
                b_op.bind('<Leave>', lambda e, w=b_op: w.config(bg='#233044'))
                b_op.bind('<Button-1>', lambda e: open_item())

        b_close = tk.Label(btns, text='✕', bg='#181F2C', fg='#64748B', font=f(10), cursor='hand2', padx=px(4))
        b_close.pack(side='left')
        b_close.bind('<Enter>', lambda e, w=b_close: w.config(fg='white'))
        b_close.bind('<Leave>', lambda e, w=b_close: w.config(fg='#64748B'))
        b_close.bind('<Button-1>', lambda e: self.hide())

        if message:
            tk.Label(content, text=message, bg='#181F2C', fg='#94A3B8', font=f(9), anchor='w').pack(fill='x', pady=(px(3), 0))

        self.frame.lift()

        if duration > 0:
            self._timer = self.parent.after(duration, self.hide)

    def hide(self):
        if self._timer:
            self.parent.after_cancel(self._timer)
            self._timer = None
        if self.frame:
            try:
                self.frame.destroy()
            except Exception:
                pass
            self.frame = None


class App:
    def __init__(self):
        winutil.enable_dpi()
        self.root = tk.Tk()
        self.k = self.root.winfo_fpixels('1i') / 96.0
        self.s = winutil.load_settings()
        self.report = None       # 本机扫描结果
        self.friend = None       # 好友配置
        self.mode = 'local'      # local / compare
        self.cur_img = None
        self.last_saved = None
        self.q = queue.Queue()
        self.scanning = False
        self._resize_job = None
        self._photo = None

        self.root.title(APP_NAME)
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f'{min(self.px(1180), sw - 60)}x{min(self.px(780), sh - 90)}+30+20')
        self.root.minsize(self.px(900), min(self.px(600), sh - 90))
        self._build_ui()
        self._bind_keys()
        self.root.protocol('WM_DELETE_WINDOW', self.on_close)
        self.root.after(200, self.start_scan)

    def px(self, n):
        return int(n * self.k)

    # ------------------------------------------------------------ UI
    def _build_ui(self):
        px = self.px
        f = lambda sz, b=False: (FONT, sz, 'bold') if b else (FONT, sz)
        side = tk.Frame(self.root, bg=SIDE_BG, width=px(236))
        side.pack(side='left', fill='y')
        side.pack_propagate(False)
        tk.Label(side, text=APP_NAME, bg=SIDE_BG, fg='white', font=f(17, True)).pack(anchor='w', padx=px(20), pady=(px(18), 0))
        tk.Label(side, text='扫描 · 估值 · 天梯 · 对比', bg=SIDE_BG, fg='#A9C8FF', font=f(9)).pack(anchor='w', padx=px(20), pady=(px(2), px(10)))

        def btn(text, cmd, primary=False):
            b = FlatButton(side, text, cmd, GREEN if primary else SIDE_BG, GREEN_HOVER if primary else SIDE_HOVER,
                           font=f(10, primary), padx=px(16), pady=px(4))
            b.pack(fill='x', padx=px(10) if primary else 0, pady=(px(1), px(1)))
            return b

        self.btn_scan = btn('重新扫描   F5', self.start_scan)
        btn('保存当前长图   F2', self.save_image, True)
        btn('复制长图到剪贴板   F3', self.copy_image)
        btn('区域截图   F4', self.region_shot)
        tk.Frame(side, bg='#2C74F0', height=1).pack(fill='x', padx=px(16), pady=px(5))
        btn('联网精准估值 (AI/报价库)', self.start_online_price)
        btn('手动改价 / AI接口设置', self.open_price_editor)
        btn('CPU 性能天梯榜', lambda: self.show_ladder('cpu'))
        btn('显卡 (GPU) 性能天梯榜', lambda: self.show_ladder('gpu'))
        tk.Frame(side, bg='#2C74F0', height=1).pack(fill='x', padx=px(16), pady=px(5))
        btn('导出配置文件 (.json)', self.export_json)
        btn('导入好友配置 → 对比', self.import_friend)
        btn('返回本机配置', self.back_local)
        tk.Frame(side, bg='#2C74F0', height=1).pack(fill='x', padx=px(16), pady=px(5))

        box = tk.Frame(side, bg=SIDE_BG)
        box.pack(fill='x', padx=px(16))
        tk.Label(box, text='昵称(显示在图上)', bg=SIDE_BG, fg='#A9C8FF', font=f(9)).pack(anchor='w')
        self.nick_var = tk.StringVar(value=self.s.get('nickname') or winutil.default_nickname())
        e = tk.Entry(box, textvariable=self.nick_var, font=f(10), relief='flat', bd=0)
        e.pack(fill='x', ipady=px(3), pady=(px(2), px(6)))

        self._nick_timer = None

        def _on_nick_edit(ev=None):
            if self._nick_timer:
                self.root.after_cancel(self._nick_timer)
            self._nick_timer = self.root.after(400, self.on_option_change)

        e.bind('<KeyRelease>', _on_nick_edit)
        e.bind('<Return>', lambda ev: self.on_option_change())
        e.bind('<FocusOut>', lambda ev: self.on_option_change())
        tk.Label(box, text='长图主题', bg=SIDE_BG, fg='#A9C8FF', font=f(9)).pack(anchor='w')
        self.theme_var = tk.StringVar(value=self.s.get('theme', '科技蓝'))
        cb = ttk.Combobox(box, textvariable=self.theme_var, values=list(renderer.THEMES), state='readonly', font=f(10))
        cb.pack(fill='x', pady=(px(2), px(4)))
        cb.bind('<<ComboboxSelected>>', lambda ev: self.on_option_change())
        self.price_var = tk.BooleanVar(value=self.s.get('show_price', True))
        self.detail_var = tk.BooleanVar(value=self.s.get('detail', True))
        self.copy_var = tk.BooleanVar(value=self.s.get('auto_copy', True))
        for text, var in (
            ('显示市场价格估值(二手/全新)', self.price_var),
            ('显示详细信息(频率/驱动等)', self.detail_var),
            ('保存时同时复制到剪贴板', self.copy_var),
        ):
            tk.Checkbutton(box, text=text, variable=var, command=self.on_option_change, bg=SIDE_BG, fg='white',
                           activebackground=SIDE_BG, activeforeground='white', selectcolor='#083E9E',
                           font=f(9), anchor='w', bd=0, highlightthickness=0).pack(fill='x', anchor='w')

        tk.Label(box, text='保存目录', bg=SIDE_BG, fg='#A9C8FF', font=f(9)).pack(anchor='w', pady=(px(10), 0))
        self.dir_label = tk.Label(box, text='', bg=SIDE_BG, fg='white', font=f(9), wraplength=px(200), justify='left', anchor='w')
        self.dir_label.pack(fill='x')
        row = tk.Frame(box, bg=SIDE_BG)
        row.pack(fill='x', pady=(px(4), 0))
        FlatButton(row, '更改目录', self.choose_dir, font=f(9), padx=px(8), pady=px(4)).pack(side='left')
        FlatButton(row, '打开目录', self.open_dir, font=f(9), padx=px(8), pady=px(4)).pack(side='left', padx=px(6))
        self._refresh_dir_label()

        right = tk.Frame(self.root, bg='#E9EEF7')
        right.pack(side='left', fill='both', expand=True)
        self.right = right
        self.toast = ToastNotification(self.right, self.px)

        bar = tk.Frame(right, bg='white', height=px(34))
        bar.pack(side='bottom', fill='x')
        bar.pack_propagate(False)
        self.status = tk.Label(bar, text='', bg='white', fg='#445', font=f(9), anchor='w')
        self.status.pack(side='left', padx=px(12))
        self.link = tk.Label(bar, text='在文件夹中显示', bg='white', fg='#0A56D8', font=(FONT, 9, 'underline'), cursor='hand2')
        self.link.bind('<Button-1>', lambda e: self.last_saved and winutil.reveal_in_explorer(self.last_saved))
        self.link.bind('<Enter>', lambda e: self.link.config(fg='#2C74F0'))
        self.link.bind('<Leave>', lambda e: self.link.config(fg='#0A56D8'))
        sb = ttk.Scrollbar(right, orient='vertical')
        sb.pack(side='right', fill='y')
        self.canvas = tk.Canvas(right, bg='#E9EEF7', highlightthickness=0, yscrollcommand=sb.set,
                                yscrollincrement=px(24))
        self.canvas.pack(side='left', fill='both', expand=True)
        sb.config(command=self.canvas.yview)
        self.canvas.bind('<Configure>', self._on_resize)
        self.root.bind_all('<MouseWheel>', lambda e: self.canvas.yview_scroll(int(-e.delta / 120) * 3, 'units'))

    def _bind_keys(self):
        self.root.bind('<F5>', lambda e: self.start_scan())
        self.root.bind('<F2>', lambda e: self.save_image())
        self.root.bind('<F3>', lambda e: self.copy_image())
        self.root.bind('<F4>', lambda e: self.region_shot())

    # ------------------------------------------------------------ 状态/设置
    def set_status(self, text, path=None):
        self.status.config(text=text)
        self.last_saved = path
        if path:
            self.link.pack(side='right', padx=self.px(12))
        else:
            self.link.pack_forget()

    def _refresh_dir_label(self):
        self.dir_label.config(text=self.s['save_dir'])

    def on_option_change(self):
        self.s['nickname'] = self.nick_var.get().strip()
        self.s['theme'] = self.theme_var.get()
        self.s['show_price'] = self.price_var.get()
        self.s['detail'] = self.detail_var.get()
        self.s['auto_copy'] = self.copy_var.get()
        winutil.save_settings(self.s)
        if self.report:
            self.report['nickname'] = self.s['nickname']
        self.refresh_view()

    def choose_dir(self):
        d = filedialog.askdirectory(initialdir=self.s['save_dir'] if os.path.isdir(self.s['save_dir']) else None,
                                    title='选择保存目录', parent=self.root)
        if d:
            self.s['save_dir'] = os.path.normpath(d)
            winutil.save_settings(self.s)
            self._refresh_dir_label()
            self.toast.show('保存目录已更新', self.s['save_dir'], duration=2600)

    def open_dir(self):
        os.makedirs(self.s['save_dir'], exist_ok=True)
        os.startfile(self.s['save_dir'])

    def on_close(self):
        self.on_option_change()
        if hasattr(self, 'toast'):
            self.toast.hide()
        self.root.destroy()

    # ------------------------------------------------------------ 扫描
    def start_scan(self):
        if self.scanning:
            return
        self.scanning = True
        self.mode = 'local'
        self.set_status('正在扫描硬件并评估市场价值…')
        self._show_message('正在扫描硬件信息并计算市场估值,请稍候…')

        def work():
            try:
                self.q.put(('ok', collector.collect(self.nick_var.get().strip())))
            except Exception as ex:
                self.q.put(('err', str(ex)))

        threading.Thread(target=work, daemon=True).start()
        self.root.after(100, self._poll)

    def _poll(self):
        try:
            kind, data = self.q.get_nowait()
        except queue.Empty:
            self.root.after(100, self._poll)
            return
        self.scanning = False
        if kind == 'ok':
            self.report = data
            val = data.get('valuation', {})
            u_p, n_p = val.get('total_used', 0), val.get('total_new', 0)
            p_str = f'  ·  二手残值 ≈ ¥{u_p:,} / 全新参考 ≈ ¥{n_p:,}' if u_p else ''
            self.set_status(f'扫描完成 · {data["scan_time"]}{p_str}')
            self.refresh_view()
            m = data.get('header', {}).get('model', '')
            msg = (f'已识别: {m}' if m else '整机扫描完成') + p_str
            self.toast.show('硬件扫描与估值完成', msg, duration=3500)
        else:
            self._show_message('扫描失败:' + data)
            self.set_status('扫描失败')
            self.toast.show('扫描失败', data, is_error=True)

    # ------------------------------------------------------------ 预览
    def _show_message(self, text):
        self.canvas.delete('all')
        self.cur_img = None
        w = max(self.canvas.winfo_width(), 10)
        self.canvas.create_text(w // 2, self.px(160), text=text, fill='#556', font=(FONT, 14))

    def refresh_view(self):
        th = self.theme_var.get()
        det = self.detail_var.get()
        sp = self.price_var.get()
        if self.mode == 'compare' and self.friend and self.report:
            self.cur_img = renderer.render_compare(self.report, self.friend, th, det, sp)
        elif self.mode == 'cpu_ladder':
            self.cur_img = renderer.render_ladder('cpu', self.report, self.friend, th, sp)
        elif self.mode == 'gpu_ladder':
            self.cur_img = renderer.render_ladder('gpu', self.report, self.friend, th, sp)
        elif self.report:
            self.cur_img = renderer.render_report(self.report, th, det, sp)
        else:
            return
        self._draw()

    def show_ladder(self, kind='cpu'):
        self.mode = 'cpu_ladder' if kind == 'cpu' else 'gpu_ladder'
        self.refresh_view()
        self.canvas.yview_moveto(0)
        name = 'CPU 性能天梯榜' if kind == 'cpu' else '显卡 (GPU) 性能天梯榜'
        self.set_status(f'当前视图: {name} (已自动标出本机硬件排位) · 按 F2 保存 / F3 复制')
        self.toast.show(f'已切换至{name}', '高亮框即为本机当前硬件所在排位，可按 F2 保存或 F3 复制长图', duration=2800)

    def _on_resize(self, e):
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(120, self._draw)

    def _draw(self):
        self._resize_job = None
        if self.cur_img is None:
            return
        cw = self.canvas.winfo_width()
        if cw < 50:
            return
        margin = self.px(16)
        tw_ = min(cw - margin * 2, self.cur_img.width)
        th_ = int(self.cur_img.height * tw_ / self.cur_img.width)
        shown = self.cur_img.resize((tw_, th_), Image.LANCZOS)
        self._photo = ImageTk.PhotoImage(shown)
        self.canvas.delete('all')
        self.canvas.create_image(cw // 2, margin, image=self._photo, anchor='n')
        self.canvas.config(scrollregion=(0, 0, cw, th_ + margin * 2))
        if hasattr(self, 'toast') and self.toast.frame:
            self.toast.frame.lift()

    # ------------------------------------------------------------ 保存 / 复制
    def _name(self, prefix, ext):
        nick = re.sub(r'[\\/:*?"<>|]', '', self.nick_var.get().strip())
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'{prefix}{"_" + nick if nick else ""}_{ts}.{ext}'

    def save_image(self):
        self.on_option_change()
        if self.cur_img is None:
            self.toast.show('还没有可保存的内容', '请先等待硬件扫描完成', is_error=True)
            return self.set_status('还没有可保存的内容,请先扫描')
        os.makedirs(self.s['save_dir'], exist_ok=True)
        prefix_map = {'compare': '硬件对比', 'cpu_ladder': 'CPU天梯榜', 'gpu_ladder': '显卡天梯榜'}
        prefix = prefix_map.get(self.mode, '硬件配置')
        path = os.path.join(self.s['save_dir'], self._name(prefix, 'png'))
        self.cur_img.save(path, 'PNG')
        copy_ok = False
        if self.copy_var.get():
            copy_msg = self._try_copy(self.cur_img)
            copy_ok = '已复制' in copy_msg
        else:
            copy_msg = ''
        self.set_status(f'已保存:{path}{copy_msg}', path)
        msg = '长图已保存，并已自动复制到剪贴板 (可直接在微信/QQ等 Ctrl+V 发送)' if copy_ok else '长图已成功保存至本地文件夹'
        self.toast.show('长图保存成功', msg, path=path)

    def _try_copy(self, img):
        try:
            winutil.copy_image_to_clipboard(img)
            return '  (已复制到剪贴板,可直接 Ctrl+V 发送)'
        except Exception as ex:
            return f'  (复制剪贴板失败:{ex})'

    def copy_image(self):
        self.on_option_change()
        if self.cur_img is None:
            self.toast.show('还没有可复制的内容', '请先等待硬件扫描完成', is_error=True)
            return self.set_status('还没有可复制的内容,请先扫描')
        msg = self._try_copy(self.cur_img)
        self.set_status('长图' + msg.strip())
        if '已复制' in msg:
            self.toast.show('长图已复制到剪贴板', '可直接在微信、QQ、钉钉等聊天窗口粘贴 (Ctrl + V) 发送')
        else:
            self.toast.show('复制失败', msg.strip(), is_error=True)

    # ------------------------------------------------------------ 区域截图
    def region_shot(self):
        self.root.withdraw()
        self.root.after(350, self._grab)

    def _grab(self):
        try:
            full = ImageGrab.grab(all_screens=True)
        except Exception as ex:
            self.root.deiconify()
            return messagebox.showerror(APP_NAME, f'截屏失败:{ex}')
        RegionSelector(self.root, full, winutil.virtual_screen_origin(), self._on_region)

    def _on_region(self, img):
        self.root.deiconify()
        self.root.lift()
        if img is None:
            self.toast.show('已取消截图', '未截取任何屏幕区域', duration=2000)
            return self.set_status('已取消截图')
        os.makedirs(self.s['save_dir'], exist_ok=True)
        path = os.path.join(self.s['save_dir'], self._name('截图', 'png'))
        img.save(path, 'PNG')
        copy_ok = False
        if self.copy_var.get():
            copy_msg = self._try_copy(img)
            copy_ok = '已复制' in copy_msg
        else:
            copy_msg = ''
        self.set_status(f'截图已保存:{path}{copy_msg}', path)
        msg = '截图已保存，并已复制到系统剪贴板 (可直接 Ctrl+V 发送)' if copy_ok else '截图已成功保存至本地文件夹'
        self.toast.show('区域截图保存成功', msg, path=path)

    # ------------------------------------------------------------ 导出 / 对比
    def export_json(self):
        if not self.report:
            self.toast.show('尚未检测到硬件信息', '请先等待硬件扫描完成', is_error=True)
            return self.set_status('请先扫描')
        self.on_option_change()
        os.makedirs(self.s['save_dir'], exist_ok=True)
        path = os.path.join(self.s['save_dir'], self._name('硬件配置', 'json'))
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.report, f, ensure_ascii=False, indent=1)
        self.set_status(f'配置文件已导出,发给好友即可对比:{path}', path)
        self.toast.show('配置文件导出成功', '已生成轻量 .json 配置文件，发送给好友导入即可进行双机对比', path=path)

    def import_friend(self):
        if not self.report:
            self.toast.show('尚未检测到本机配置', '请先等待本机硬件扫描完成', is_error=True)
            return self.set_status('请先扫描本机硬件')
        p = filedialog.askopenfilename(title='选择好友的配置文件 (.json)', parent=self.root,
                                       initialdir=self.s['save_dir'] if os.path.isdir(self.s['save_dir']) else None,
                                       filetypes=[('硬件配置文件', '*.json'), ('所有文件', '*.*')])
        if not p:
            return
        try:
            with open(p, encoding='utf-8') as f:
                data = json.load(f)
            assert data.get('app') == 'HardwareShot' and isinstance(data.get('items'), list)
        except Exception:
            self.toast.show('无效的配置文件', '请选择好友使用本工具导出的 .json 配置文件', is_error=True)
            return messagebox.showerror(APP_NAME, '这不是有效的配置文件,请选择好友用本工具导出的 .json 文件。')
        if not (data.get('nickname') or '').strip():
            n = simpledialog.askstring(APP_NAME, '给好友起个名字(显示在对比图上):', initialvalue='好友', parent=self.root)
            data['nickname'] = (n or '好友').strip()
        self.friend = data
        self.mode = 'compare'
        self.refresh_view()
        self.canvas.yview_moveto(0)
        self.set_status('对比图已生成,按 F2 保存 / F3 复制;点「返回本机配置」回到单机视图')
        fnick = self.friend.get('nickname') or '好友'
        self.toast.show('好友配置导入成功', f'已生成与「{fnick}」的双机对比图，按 F2 保存 / F3 复制')

    def back_local(self):
        self.mode = 'local'
        self.refresh_view()
        self.canvas.yview_moveto(0)
        self.set_status('已返回本机配置')
        self.toast.show('已返回本机配置', '当前展示本机硬件配置与估值预览', duration=2000)

    # ------------------------------------------------------------ 联网精准估值 & 手动改价弹窗
    def start_online_price(self, force_channel=None):
        if not self.report:
            self.toast.show('请先扫描硬件', '等待本机硬件扫描完成后再进行联网估值', is_error=True)
            return
        if getattr(self, '_pricing', False):
            return
        self._pricing = True
        has_key = bool((self.s.get('ai_api_key') or '').strip())
        use_ai = (force_channel == 'ai') or (force_channel is None and has_key)
        ch_desc = f'AI 大模型 ({self.s.get("ai_model", "qwen-plus")})' if use_ai else '公开硬件报价库 (免Key通道)'
        self.set_status(f'正在通过「{ch_desc}」联网校准价格…')
        self.toast.show('正在联网精准估值…', f'当前通道: {ch_desc}，请稍候 2~6 秒', duration=6000)

        pq = queue.Queue()

        def work():
            try:
                cb = lambda msg: pq.put(('prog', msg))
                if use_ai:
                    cnt, src = market.lookup_via_ai(self.report, self.s, cb)
                else:
                    cnt, src = market.lookup_via_web(self.report, cb)
                pq.put(('done', (cnt, src)))
            except Exception as ex:
                pq.put(('err', str(ex)))

        threading.Thread(target=work, daemon=True).start()

        def poll_p():
            try:
                while True:
                    k, v = pq.get_nowait()
                    if k == 'prog':
                        self.set_status(v)
                    elif k == 'done':
                        self._pricing = False
                        cnt, src = v
                        self.refresh_view()
                        val = self.report.get('valuation', {})
                        u_p, n_p = val.get('total_used', 0), val.get('total_new', 0)
                        self.set_status(f'联网估值完成 ({src}) · 二手残值 ≈ ¥{u_p:,} / 全新参考 ≈ ¥{n_p:,}')
                        self.toast.show('联网精准估值完成',
                                        f'已通过「{src}」校准 {cnt} 项硬件 · 二手总计 ≈ ¥{u_p:,} | 全新总计 ≈ ¥{n_p:,}',
                                        duration=4200)
                        return
                    elif k == 'err':
                        self._pricing = False
                        self.set_status('联网估值失败: ' + v)
                        self.toast.show('联网估值失败', v, is_error=True, duration=4500)
                        return
            except queue.Empty:
                pass
            self.root.after(100, poll_p)

        self.root.after(100, poll_p)

    def open_price_editor(self):
        if not self.report:
            self.toast.show('请先等待硬件扫描完成', '扫描完成后即可手动微调各项硬件价格或配置 AI 接口', is_error=True)
            return
        market.enrich(self.report)
        px = self.px
        f = lambda sz, b=False: (FONT, sz, 'bold') if b else (FONT, sz)

        win = tk.Toplevel(self.root)
        win.title('手动调整硬件估价 & 联网估值设置')
        win.configure(bg='#F1F5F9')
        win.geometry(f'{px(760)}x{px(640)}')
        win.transient(self.root)
        win.grab_set()

        # --- 1. 顶部 AI 大模型联网询价配置卡片
        ai_card = tk.Frame(win, bg='white', padx=px(16), pady=px(12), highlightthickness=1, highlightbackground='#CBD5E1')
        ai_card.pack(fill='x', padx=px(16), pady=(px(14), px(8)))

        hdr_row = tk.Frame(ai_card, bg='white')
        hdr_row.pack(fill='x', pady=(0, px(8)))
        tk.Label(hdr_row, text='🌐 联网精准估值通道设置', bg='white', fg='#0F172A', font=f(11, True)).pack(side='left')
        tk.Label(hdr_row, text='(不填 Key 默认走免Key公开报价网；填 Key 可用 AI 大模型识别特种硬件溢价)',
                 bg='white', fg='#64748B', font=f(9)).pack(side='left', padx=px(8))

        r1 = tk.Frame(ai_card, bg='white')
        r1.pack(fill='x', pady=px(3))
        tk.Label(r1, text='AI 服务商:', bg='white', fg='#334155', font=f(9), width=10, anchor='w').pack(side='left')
        prov_var = tk.StringVar(value=self.s.get('ai_provider', '通义千问 (百炼·支持联网)'))
        cb_prov = ttk.Combobox(r1, textvariable=prov_var, values=list(market.AI_PROVIDERS.keys()), state='readonly', font=f(9), width=24)
        cb_prov.pack(side='left', padx=(0, px(12)))

        tk.Label(r1, text='模型名称:', bg='white', fg='#334155', font=f(9)).pack(side='left')
        model_var = tk.StringVar(value=self.s.get('ai_model', 'qwen-plus'))
        tk.Entry(r1, textvariable=model_var, font=f(9), width=20, relief='solid', bd=1).pack(side='left', padx=px(6))

        r2 = tk.Frame(ai_card, bg='white')
        r2.pack(fill='x', pady=px(3))
        tk.Label(r2, text='接口地址:', bg='white', fg='#334155', font=f(9), width=10, anchor='w').pack(side='left')
        base_var = tk.StringVar(value=self.s.get('ai_api_base', 'https://dashscope.aliyuncs.com/compatible-mode/v1'))
        tk.Entry(r2, textvariable=base_var, font=f(9), relief='solid', bd=1).pack(side='left', fill='x', expand=True, padx=(0, px(6)))

        r3 = tk.Frame(ai_card, bg='white')
        r3.pack(fill='x', pady=px(3))
        tk.Label(r3, text='API Key:', bg='white', fg='#334155', font=f(9), width=10, anchor='w').pack(side='left')
        key_var = tk.StringVar(value=self.s.get('ai_api_key', ''))
        tk.Entry(r3, textvariable=key_var, font=f(9), show='*', relief='solid', bd=1).pack(side='left', fill='x', expand=True, padx=(0, px(8)))

        def on_prov_select(ev=None):
            p_info = market.AI_PROVIDERS.get(prov_var.get())
            if p_info and p_info[0]:
                base_var.set(p_info[0])
                model_var.set(p_info[1])

        cb_prov.bind('<<ComboboxSelected>>', on_prov_select)

        def save_ai_cfg():
            self.s['ai_provider'] = prov_var.get()
            self.s['ai_api_base'] = base_var.get().strip()
            self.s['ai_api_key'] = key_var.get().strip()
            self.s['ai_model'] = model_var.get().strip()
            winutil.save_settings(self.s)

        def run_ai_now():
            save_ai_cfg()
            if not self.s.get('ai_api_key'):
                return messagebox.showwarning('提示', '请先填入有效的 API Key（如阿里云百炼、DeepSeek、Kimi 等），或点击右侧「免Key公开报价校准」。', parent=win)
            win.destroy()
            self.start_online_price(force_channel='ai')

        def run_web_now():
            save_ai_cfg()
            win.destroy()
            self.start_online_price(force_channel='web')

        FlatButton(r3, '🤖 用 AI 联网重估', run_ai_now, bg='#0A56D8', hover='#2C74F0', font=f(9, True), padx=px(10), pady=px(3)).pack(side='left', padx=px(3))
        FlatButton(r3, '🌐 免Key公开报价校准', run_web_now, bg='#0D9488', hover='#14B8A6', font=f(9, True), padx=px(10), pady=px(3)).pack(side='left')

        # --- 2. 中部: 单项硬件价格手动微调列表
        list_card = tk.Frame(win, bg='white', padx=px(16), pady=px(12), highlightthickness=1, highlightbackground='#CBD5E1')
        list_card.pack(fill='both', expand=True, padx=px(16), pady=px(6))

        tk.Label(list_card, text='✏️ 单项硬件价格微调 (直接修改数字并保存，即可永久记住并更新长图)',
                 bg='white', fg='#0F172A', font=f(11, True)).pack(anchor='w', pady=(0, px(8)))

        th_row = tk.Frame(list_card, bg='#E2E8F0', pady=px(5))
        th_row.pack(fill='x')
        tk.Label(th_row, text='类别', bg='#E2E8F0', fg='#334155', font=f(9, True), width=10, anchor='w', padx=px(8)).pack(side='left')
        tk.Label(th_row, text='硬件型号名称', bg='#E2E8F0', fg='#334155', font=f(9, True), anchor='w').pack(side='left', fill='x', expand=True)
        tk.Label(th_row, text='二手残值 (¥)', bg='#E2E8F0', fg='#334155', font=f(9, True), width=12).pack(side='left')
        tk.Label(th_row, text='全新参考 (¥)', bg='#E2E8F0', fg='#334155', font=f(9, True), width=12).pack(side='left')
        tk.Label(th_row, text='当前来源', bg='#E2E8F0', fg='#334155', font=f(9, True), width=12).pack(side='left')

        c_frame = tk.Frame(list_card, bg='white')
        c_frame.pack(fill='both', expand=True)
        cv = tk.Canvas(c_frame, bg='white', highlightthickness=0)
        vsb = ttk.Scrollbar(c_frame, orient='vertical', command=cv.yview)
        vsb.pack(side='right', fill='y')
        cv.pack(side='left', fill='both', expand=True)
        cv.configure(yscrollcommand=vsb.set)
        inner = tk.Frame(cv, bg='white')
        inner_id = cv.create_window((0, 0), window=inner, anchor='nw')
        inner.bind('<Configure>', lambda e: cv.configure(scrollregion=cv.bbox('all')))
        cv.bind('<Configure>', lambda e: cv.itemconfig(inner_id, width=e.width))

        entries = []
        for it in self.report.get('items', []):
            k = it.get('key')
            for r in it.get('rows', []):
                ev = r.get('_eval') or {}
                if k == 'sound' or ev.get('note') == 'CPU内置核显':
                    continue
                entries.append((k, it.get('label', k), r.get('t', ''), ev.get('used', 0), ev.get('new', 0), ev.get('source', '内置估算')))

        val = self.report.get('valuation', {})
        ex_lbl = val.get('extra_label', '机箱/电源/散热器基础估算')
        pcache = winutil.load_price_cache()
        ex_ck = market.cache_key('extra', ex_lbl)
        ex_src = pcache.get(ex_ck, {}).get('source', '内置估算')
        entries.append(('extra', '机电散/附加', ex_lbl, val.get('extra_used', 0), val.get('extra_new', 0), ex_src))

        row_vars = []
        for idx_r, (k, lab, title_str, u_val, n_val, src_str) in enumerate(entries):
            bg_c = '#F8FAFC' if idx_r % 2 == 1 else 'white'
            rf = tk.Frame(inner, bg=bg_c, pady=px(5))
            rf.pack(fill='x')
            tk.Label(rf, text=lab, bg=bg_c, fg='#0A56D8', font=f(9, True), width=10, anchor='w', padx=px(8)).pack(side='left')
            tk.Label(rf, text=title_str, bg=bg_c, fg='#1E293B', font=f(9), anchor='w').pack(side='left', fill='x', expand=True)
            uv = tk.StringVar(value=str(u_val))
            nv = tk.StringVar(value=str(n_val))
            tk.Entry(rf, textvariable=uv, font=f(9), width=10, justify='center', relief='solid', bd=1).pack(side='left', padx=px(6))
            tk.Entry(rf, textvariable=nv, font=f(9), width=10, justify='center', relief='solid', bd=1).pack(side='left', padx=px(6))
            tk.Label(rf, text=src_str, bg=bg_c, fg='#16A34A' if src_str != '内置估算' else '#64748B', font=f(8), width=12).pack(side='left')
            row_vars.append((k, title_str, u_val, n_val, uv, nv))

        # --- 3. 底部操作按钮
        bot = tk.Frame(win, bg='#F1F5F9', padx=px(16), pady=px(10))
        bot.pack(fill='x')

        def save_all():
            save_ai_cfg()
            pc = winutil.load_price_cache()
            now_s = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
            changed = 0
            for k, t_s, old_u, old_n, uv, nv in row_vars:
                try:
                    new_u = max(0, int(float(uv.get().strip() or 0)))
                    new_n = max(0, int(float(nv.get().strip() or 0)))
                except Exception:
                    continue
                ck = market.cache_key(k, t_s)
                if new_u != old_u or new_n != old_n:
                    pc[ck] = {'used': new_u, 'new': new_n, 'source': '手动校准', 'ts': now_s}
                    changed += 1
            winutil.save_price_cache(pc)
            market.enrich(self.report)
            self.refresh_view()
            v_now = self.report.get('valuation', {})
            u_p, n_p = v_now.get('total_used', 0), v_now.get('total_new', 0)
            self.set_status(f'已更新估值 · 二手残值 ≈ ¥{u_p:,} / 全新参考 ≈ ¥{n_p:,}')
            win.destroy()
            self.toast.show('价格设置已保存', f'当前整机二手估值 ≈ ¥{u_p:,} | 全新参考 ≈ ¥{n_p:,}', duration=3000)

        def reset_cache():
            if not messagebox.askyesno('恢复默认估值', '确定要清空所有联网校准和手动修改的价格，恢复为内置离线基准估值吗？', parent=win):
                return
            winutil.save_price_cache({})
            market.enrich(self.report)
            self.refresh_view()
            v_now = self.report.get('valuation', {})
            u_p, n_p = v_now.get('total_used', 0), v_now.get('total_new', 0)
            self.set_status(f'已恢复默认离线估值 · 二手残值 ≈ ¥{u_p:,} / 全新参考 ≈ ¥{n_p:,}')
            win.destroy()
            self.toast.show('已恢复默认离线估值', f'当前整机二手估值 ≈ ¥{u_p:,} | 全新参考 ≈ ¥{n_p:,}', duration=2800)

        FlatButton(bot, '✔ 保存修改并刷新长图', save_all, bg=GREEN, hover=GREEN_HOVER, font=f(10, True), padx=px(18), pady=px(6)).pack(side='right')
        FlatButton(bot, '取消', win.destroy, bg='#64748B', hover='#475569', font=f(10), padx=px(14), pady=px(6)).pack(side='right', padx=px(10))
        FlatButton(bot, '↺ 恢复默认离线估值', reset_cache, bg='#EF4444', hover='#DC2626', font=f(9), padx=px(12), pady=px(6)).pack(side='left')

    def run(self):
        self.root.mainloop()
