# -*- coding: utf-8 -*-
"""硬件信息采集:通过 PowerShell(CIM/WMI) + Win32 API 收集,不依赖第三方库,也不读取序列号/MAC/IP 等隐私信息。"""
import base64
import ctypes
import datetime
import json
import math
import re
import subprocess
from ctypes import wintypes

SCHEMA = 1

PS_SCRIPT = r'''
$ErrorActionPreference='SilentlyContinue'
[Console]::OutputEncoding=[Text.Encoding]::UTF8
function Dec($b){ if($b -eq $null){return ''}; (-join ($b | Where-Object {$_ -ne 0} | ForEach-Object {[char]$_})).Trim() }
$o=[ordered]@{}
$o.cs=Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer,Model,SystemFamily,TotalPhysicalMemory
$o.enc=@(Get-CimInstance Win32_SystemEnclosure | ForEach-Object { $_.ChassisTypes })
$o.os=Get-CimInstance Win32_OperatingSystem | Select-Object Caption,OSArchitecture,BuildNumber
$o.dv=(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').DisplayVersion
$o.cpu=@(Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed,L3CacheSize)
$o.mem=@(Get-CimInstance Win32_PhysicalMemory | Select-Object Manufacturer,PartNumber,Capacity,Speed,ConfiguredClockSpeed,SMBIOSMemoryType)
$o.memslots=(Get-CimInstance Win32_PhysicalMemoryArray | Measure-Object MemoryDevices -Sum).Sum
$o.gpu=@(Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM,DriverVersion,PNPDeviceID)
$g=@()
Get-ChildItem 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}' | ForEach-Object {
  $p=Get-ItemProperty $_.PSPath
  if($p.DriverDesc){
    $m=$p.'HardwareInformation.qwMemorySize'
    if($m -is [byte[]]){ $b=New-Object byte[] 8; [Array]::Copy($m,$b,[Math]::Min(8,$m.Length)); $m=[BitConverter]::ToUInt64($b,0) }
    $g += [pscustomobject]@{Desc=[string]$p.DriverDesc;Mem=[string]$m}
  }
}
$o.gpureg=@($g)
$o.board=Get-CimInstance Win32_BaseBoard | Select-Object Manufacturer,Product
$o.bios=Get-CimInstance Win32_BIOS | Select-Object Manufacturer,SMBIOSBIOSVersion,@{n='Date';e={ if($_.ReleaseDate){$_.ReleaseDate.ToString('yyyy-MM-dd')} }}
$o.chipset=@(Get-CimInstance Win32_PnPEntity -Filter "Name LIKE '%LPC%' OR Name LIKE '%eSPI%'" | Select-Object -ExpandProperty Name)
$o.mid=@(Get-CimInstance -Namespace root\wmi -ClassName WmiMonitorID | ForEach-Object { [pscustomobject]@{Inst=$_.InstanceName;Mfg=(Dec $_.ManufacturerName);Name=(Dec $_.UserFriendlyName);Code=(Dec $_.ProductCodeID)} })
$o.msz=@(Get-CimInstance -Namespace root\wmi -ClassName WmiMonitorBasicDisplayParams | ForEach-Object { [pscustomobject]@{Inst=$_.InstanceName;H=$_.MaxHorizontalImageSize;V=$_.MaxVerticalImageSize} })
$sysn=$null
try{ $sysn=(Get-Partition -DriveLetter C | Get-Disk).Number }catch{}
$o.sysdisk=$sysn
$o.pd=@(Get-PhysicalDisk | Select-Object FriendlyName,Size,@{n='MediaType';e={[string]$_.MediaType}},@{n='BusType';e={[string]$_.BusType}},@{n='Id';e={[string]$_.DeviceId}})
$o.dd=@(Get-CimInstance Win32_DiskDrive | Select-Object Model,Size,InterfaceType,MediaType,Index)
$o.net=@(Get-NetAdapter -Physical | Select-Object Name,InterfaceDescription,LinkSpeed,@{n='Status';e={[string]$_.Status}})
$o.snd=@(Get-CimInstance Win32_SoundDevice | Select-Object Name,Manufacturer)
$o | ConvertTo-Json -Depth 5 -Compress
'''


def run_ps(script, timeout=90):
    enc = base64.b64encode(script.encode('utf-16le')).decode()
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0
    p = subprocess.run(
        ['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', enc],
        capture_output=True, timeout=timeout, startupinfo=si, creationflags=0x08000000)
    out = p.stdout.decode('utf-8', 'replace').lstrip('\ufeff').strip()
    i = out.find('{')
    if i < 0:
        raise RuntimeError('PowerShell 没有返回数据: ' + p.stderr.decode('utf-8', 'replace')[:300])
    return json.loads(out[i:])


# ---------------------------------------------------------------- 工具函数
def _list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _first(v):
    v = _list(v)
    return v[0] if v else {}


def _s(v):
    return '' if v is None else str(v).strip()


def _int(v, d=0):
    try:
        return int(float(v))
    except Exception:
        return d


JUNK = re.compile(r'(system (product|manufacturer|version)|to be filled|default string|o\.?e\.?m\.?|not applicable|none|unknown|^$)', re.I)


def is_junk(s):
    return bool(JUNK.search(_s(s)))


def clean(s):
    s = _s(s)
    s = re.sub(r'\((R|TM|r|tm)\)', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


def localize_prefix(name, table):
    low = name.lower()
    for k, v in table:
        if low.startswith(k):
            return v + name[len(k):]
    return name


VENDOR = [
    ('asustek', '华硕'), ('asus', '华硕'), ('micro-star', '微星'), ('msi', '微星'), ('gigabyte', '技嘉'),
    ('lenovo', '联想'), ('dell', '戴尔'), ('hewlett', '惠普'), ('hp', '惠普'), ('acer', '宏碁'),
    ('huawei', '华为'), ('xiaomi', '小米'), ('asrock', '华擎'), ('colorful', '七彩虹'), ('samsung', '三星'),
    ('apple', '苹果'), ('microsoft', '微软'), ('tongfang', '同方'), ('thunderobot', '雷神'), ('machenike', '机械师'),
    ('hasee', '神舟'), ('mechrevo', '机械革命'), ('honor', '荣耀'), ('razer', '雷蛇'), ('biostar', '映泰'),
    ('maxsun', '铭瑄'), ('onda', '昂达'), ('soyo', '梅捷'), ('intel', '英特尔'), ('supermicro', '超微'),
]


def cn_vendor(s):
    s = clean(s)
    low = s.lower()
    for k, v in VENDOR:
        if low.startswith(k):
            return v
    s = re.sub(r'\b(inc|co|corp|corporation|ltd|computer|technology)\b\.?,?', '', s, flags=re.I).strip(' ,.')
    return s


DISK_BRAND = [('samsung', '三星'), ('western digital', '西部数据'), ('wdc', '西部数据'), ('kingston', '金士顿'),
              ('crucial', '英睿达'), ('seagate', '希捷'), ('toshiba', '东芝'), ('intel', '英特尔'),
              ('sk hynix', 'SK海力士'), ('hynix', 'SK海力士'), ('netac', '朗科'), ('adata', '威刚'),
              ('kioxia', '铠侠'), ('micron', '美光'), ('sandisk', '闪迪'), ('lexar', '雷克沙'),
              ('colorful', '七彩虹'), ('lenovo', '联想'), ('hp ', '惠普 '), ('zhitai', '致态'), ('ymtc', '长江存储'),
              ('galax', '影驰'), ('gigabyte', '技嘉'), ('asus', '华硕'), ('teamgroup', '十铨'), ('team ', '十铨 '),
              ('sabrent', 'Sabrent'), ('corsair', '海盗船'), ('acer', '宏碁')]

COMMON_BRAND = [('intel', '英特尔'), ('realtek', '瑞昱'), ('qualcomm', '高通'), ('mediatek', '联发科'),
                ('broadcom', '博通'), ('nvidia', 'NVIDIA'), ('advanced micro devices', 'AMD'), ('killer', 'Killer')]

MEM_BRAND_HEX = {'80AD': 'SK海力士', '802C': '美光', 'CE00': '三星', '029E': '海盗船', '04CD': '芝奇',
                 '9801': '金士顿', '859B': '英睿达', '014F': '光威(Transcend)', '0198': '金士顿'}
MEM_PART_PREFIX = [('CMK', '海盗船'), ('CMT', '海盗船'), ('CMH', '海盗船'), ('CMW', '海盗船'), ('CMD', '海盗船'),
                   ('CMN', '海盗船'), ('KF', '金士顿'), ('KHX', '金士顿'), ('HX', '金士顿'), ('F5-', '芝奇'),
                   ('F4-', '芝奇'), ('CT', '英睿达'), ('BL', '英睿达'), ('M378', '三星'), ('M471', '三星'),
                   ('M323', '三星'), ('M425', '三星'), ('HMA', 'SK海力士'), ('HMC', 'SK海力士'), ('HMCG', 'SK海力士'),
                   ('TF', '十铨'), ('TED', '十铨'), ('TL', '十铨'), ('GW', '光威'), ('ADATA', '威刚'), ('AX', '威刚')]
MEM_NAME = [('corsair', '海盗船'), ('kingston', '金士顿'), ('g.skill', '芝奇'), ('gskill', '芝奇'),
            ('crucial', '英睿达'), ('micron', '美光'), ('samsung', '三星'), ('hynix', 'SK海力士'),
            ('team', '十铨'), ('adata', '威刚'), ('patriot', '博帝'), ('lexar', '雷克沙'), ('gloway', '光威'),
            ('apacer', '宇瞻'), ('colorful', '七彩虹'), ('netac', '朗科'), ('galax', '影驰'),
            ('asgard', '阿斯加特'), ('kllisre', '科力'), ('v-color', 'V-Color')]
MEM_TYPE = {20: 'DDR', 21: 'DDR2', 24: 'DDR3', 26: 'DDR4', 27: 'LPDDR', 28: 'LPDDR2', 29: 'LPDDR3',
            30: 'LPDDR4', 34: 'DDR5', 35: 'LPDDR5'}
GPU_AIB = {'1458': '技嘉', '1043': '华硕', '1462': '微星', '3842': 'EVGA', '19DA': '索泰', '1569': 'Palit',
           '10B0': 'Gainward', '196E': 'PNY', '1682': 'XFX', '174B': '蓝宝石', '1DA2': '蓝宝石',
           '148C': '迪兰', '1849': '华擎', '7377': '七彩虹', '1B4C': '影驰', '107D': '丽台',
           '1025': '宏碁', '17AA': '联想', '103C': '惠普', '1028': '戴尔', '10DE': '公版'}
MON_VENDOR = {'SAM': '三星', 'DEL': '戴尔', 'AOC': 'AOC', 'GSM': 'LG', 'LEN': '联想', 'ACI': '华硕', 'AUS': '华硕',
              'HWP': '惠普', 'HPN': '惠普', 'BNQ': '明基', 'PHL': '飞利浦', 'ACR': '宏碁', 'MSI': '微星',
              'GBT': '技嘉', 'VSC': '优派', 'SNY': '索尼', 'SHP': '夏普', 'CMN': '奇美', 'BOE': '京东方',
              'LGD': 'LG Display', 'AUO': '友达', 'HKC': 'HKC', 'XMI': '小米', 'HUA': '华为', 'HSD': 'HannStar',
              'IVO': '龙腾', 'CSO': '华星光电', 'SDC': '三星', 'NEC': 'NEC', 'EIZ': 'EIZO', 'KOS': '科思', 'TCL': 'TCL',
              'KTC': 'KTC', 'MAG': 'MAG', 'RTK': '瑞昱', 'SKY': '创维', 'PNP': ''}


def fmt_disk(b):
    g = b / 1e9
    if g >= 990:
        s = f'{g / 1000:.2f}'.rstrip('0').rstrip('.')
        return f'{s} TB'
    return f'{round(g)} GB'


def fmt_gib(b):
    return f'{round(b / 2 ** 30)} GB'


def fmt_uptime(sec):
    sec = int(sec)
    d, r = divmod(sec, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    return f'{d}天{h}小时{m}分钟{s}秒'


# ---------------------------------------------------------------- 显示器 (Win32)
class DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('DeviceName', ctypes.c_wchar * 32), ('DeviceString', ctypes.c_wchar * 128),
                ('StateFlags', wintypes.DWORD), ('DeviceID', ctypes.c_wchar * 128), ('DeviceKey', ctypes.c_wchar * 128)]


class DEVMODEW(ctypes.Structure):
    _fields_ = [('dmDeviceName', ctypes.c_wchar * 32), ('dmSpecVersion', wintypes.WORD),
                ('dmDriverVersion', wintypes.WORD), ('dmSize', wintypes.WORD), ('dmDriverExtra', wintypes.WORD),
                ('dmFields', wintypes.DWORD), ('dmPositionX', wintypes.LONG), ('dmPositionY', wintypes.LONG),
                ('dmDisplayOrientation', wintypes.DWORD), ('dmDisplayFixedOutput', wintypes.DWORD),
                ('dmColor', ctypes.c_short), ('dmDuplex', ctypes.c_short), ('dmYResolution', ctypes.c_short),
                ('dmTTOption', ctypes.c_short), ('dmCollate', ctypes.c_short), ('dmFormName', ctypes.c_wchar * 32),
                ('dmLogPixels', wintypes.WORD), ('dmBitsPerPel', wintypes.DWORD), ('dmPelsWidth', wintypes.DWORD),
                ('dmPelsHeight', wintypes.DWORD), ('dmDisplayFlags', wintypes.DWORD),
                ('dmDisplayFrequency', wintypes.DWORD), ('dmICMMethod', wintypes.DWORD),
                ('dmICMIntent', wintypes.DWORD), ('dmMediaType', wintypes.DWORD), ('dmDitherType', wintypes.DWORD),
                ('dmReserved1', wintypes.DWORD), ('dmReserved2', wintypes.DWORD), ('dmPanningWidth', wintypes.DWORD),
                ('dmPanningHeight', wintypes.DWORD)]


def enum_displays():
    """返回当前已连接显示器:[{code,w,h,hz,primary}]"""
    res = []
    u = ctypes.windll.user32
    i = 0
    while True:
        dd = DISPLAY_DEVICEW()
        dd.cb = ctypes.sizeof(dd)
        if not u.EnumDisplayDevicesW(None, i, ctypes.byref(dd), 0):
            break
        i += 1
        if not (dd.StateFlags & 1):
            continue
        dm = DEVMODEW()
        dm.dmSize = ctypes.sizeof(dm)
        w = h = hz = 0
        if u.EnumDisplaySettingsW(dd.DeviceName, -1, ctypes.byref(dm)):
            w, h, hz = dm.dmPelsWidth, dm.dmPelsHeight, dm.dmDisplayFrequency
        mon = DISPLAY_DEVICEW()
        mon.cb = ctypes.sizeof(mon)
        code = ''
        if u.EnumDisplayDevicesW(dd.DeviceName, 0, ctypes.byref(mon), 0):
            parts = mon.DeviceID.split('\\')
            if len(parts) > 1:
                code = parts[1].upper()
        res.append({'code': code, 'w': w, 'h': h, 'hz': hz, 'primary': bool(dd.StateFlags & 4)})
    return res


# ---------------------------------------------------------------- 各类硬件格式化
def build_header(raw):
    cs = _first(raw.get('cs'))
    board = _first(raw.get('board'))
    enc = [_int(x) for x in _list(raw.get('enc'))]
    laptop = {8, 9, 10, 11, 12, 14, 18, 21, 30, 31, 32}
    desktop = {3, 4, 5, 6, 7, 15, 16, 24, 35, 36}
    aio = {13}
    kind = '电脑'
    for t in enc:
        if t in laptop:
            kind = '笔记本电脑'
            break
        if t in aio:
            kind = '一体机'
            break
        if t in desktop:
            kind = '台式电脑'
            break
    brand_src = cs.get('Manufacturer') if not is_junk(cs.get('Manufacturer')) else board.get('Manufacturer')
    brand = cn_vendor(brand_src)
    fam, model = _s(cs.get('SystemFamily')), _s(cs.get('Model'))
    name = ''
    if brand.startswith('联想') or kind == '笔记本电脑':
        name = fam if not is_junk(fam) else (model if not is_junk(model) else '')
    else:
        name = model if not is_junk(model) else ''
    name = clean(name)
    if name.lower().startswith(brand.lower()) and brand:
        name = name[len(brand):].strip()
    parts = [p for p in (brand, name, kind) if p]
    model_str = ' '.join(parts)

    osr = _first(raw.get('os'))
    cap = clean(osr.get('Caption')).replace('Microsoft ', '')
    for en, cn in [('Pro for Workstations', '专业工作站版'), ('Pro Education', '专业教育版'), ('Pro', '专业版'),
                   ('Home', '家庭版'), ('Enterprise', '企业版'), ('Education', '教育版'), ('Ultimate', '旗舰版'),
                   ('Professional', '专业版')]:
        if re.search(r'\b' + en + r'\b', cap):
            cap = re.sub(r'\b' + en + r'\b', cn, cap)
            break
    arch = '64位' if '64' in _s(osr.get('OSArchitecture')) else '32位'
    os_str = f'{cap} {arch}'.strip()
    dv = _s(raw.get('dv'))
    detail = []
    if dv:
        detail.append(f'版本 {dv}')
    if osr.get('BuildNumber'):
        detail.append(f'内部版本 {osr.get("BuildNumber")}')
    try:
        up = ctypes.windll.kernel32.GetTickCount64
        up.restype = ctypes.c_ulonglong
        uptime = fmt_uptime(up() / 1000)
    except Exception:
        uptime = ''
    return {'model': model_str, 'os': os_str, 'os_detail': ' · '.join(detail), 'uptime': uptime}


def build_cpu(raw, metrics):
    cpus = _list(raw.get('cpu'))
    rows = []
    cores = threads = 0
    for c in cpus:
        name = clean(c.get('Name'))
        name = re.sub(r'\s*@.*$', '', name)
        name = re.sub(r'\bCPU\b', '', name)
        name = re.sub(r'\b\d+-Core Processor\b', '', name)
        name = re.sub(r'\bProcessor\b', '', name)
        name = re.sub(r'\s+', ' ', name).strip()
        n, t = _int(c.get('NumberOfCores')), _int(c.get('NumberOfLogicalProcessors'))
        cores += n
        threads += t
        d = [f'{n}核心 {t}线程']
        if _int(c.get('MaxClockSpeed')):
            d.append(f'基准频率 {_int(c.get("MaxClockSpeed")) / 1000:.2f} GHz')
        if _int(c.get('L3CacheSize')):
            d.append(f'三级缓存 {math.ceil(_int(c.get("L3CacheSize")) / 1024)} MB')
        rows.append({'t': name, 'd': ' · '.join(d)})
    metrics['cpu_cores'] = cores
    metrics['cpu_threads'] = threads
    return rows


def mem_brand(m):
    man = _s(m.get('Manufacturer'))
    part = _s(m.get('PartNumber'))
    hexs = man.upper()
    if hexs in MEM_BRAND_HEX:
        return MEM_BRAND_HEX[hexs]
    low = man.lower()
    for k, v in MEM_NAME:
        if low.startswith(k) or k in low:
            return v
    up = part.upper()
    for k, v in sorted(MEM_PART_PREFIX, key=lambda x: -len(x[0])):
        if up.startswith(k):
            return v
    if is_junk(man) or re.fullmatch(r'[0-9A-Fa-f]{4}', man):
        return ''
    return man


def build_mem(raw, metrics):
    mods = _list(raw.get('mem'))
    total = sum(_int(m.get('Capacity')) for m in mods)
    if not total:
        total = _int(_first(raw.get('cs')).get('TotalPhysicalMemory'))
    groups = {}
    parts = []
    speeds = []
    for m in mods:
        speed = _int(m.get('ConfiguredClockSpeed')) or _int(m.get('Speed'))
        typ = MEM_TYPE.get(_int(m.get('SMBIOSMemoryType')), '')
        if not typ:
            typ = 'DDR5' if speed >= 4000 else ('DDR4' if speed >= 1800 else '')
        key = (mem_brand(m), typ, speed, _int(m.get('Capacity')))
        groups[key] = groups.get(key, 0) + 1
        speeds.append(speed)
        if _s(m.get('PartNumber')):
            parts.append(_s(m.get('PartNumber')))
    desc = []
    for (brand, typ, speed, cap), n in groups.items():
        seg = ' '.join(x for x in (brand, typ, f'{speed}MHz' if speed else '') if x)
        desc.append(f'{seg} {round(cap / 2 ** 30)}GB x {n}'.strip())
    t = f'{fmt_gib(total)}' + (f' ({"; ".join(desc)})' if desc else '')
    d = []
    slots = _int(raw.get('memslots'))
    if mods and slots:
        d.append(f'已用 {len(mods)}/{slots} 个插槽')
    if parts:
        d.append('型号 ' + ' / '.join(dict.fromkeys(parts)))
    metrics['ram_gb'] = round(total / 2 ** 30)
    metrics['ram_speed'] = max(speeds) if speeds else 0
    return [{'t': t, 'd': ' · '.join(d)}] if total else []


def build_gpu(raw, metrics):
    gpus = _list(raw.get('gpu'))
    reg = {_s(r.get('Desc')): _int(r.get('Mem')) for r in _list(raw.get('gpureg'))}
    bad = re.compile(r'(basic display|remote|virtual|parsec|meta |citrix|idd|displaylink|spacedesk)', re.I)
    good = [g for g in gpus if not bad.search(_s(g.get('Name')))] or gpus
    rows = []
    vmax = 0
    for g in good:
        name = clean(g.get('Name'))
        vram = reg.get(_s(g.get('Name')), 0) or _int(g.get('AdapterRAM'))
        pnp = _s(g.get('PNPDeviceID')).upper()
        ven = re.search(r'VEN_([0-9A-F]{4})', pnp)
        sub = re.search(r'SUBSYS_[0-9A-F]{4}([0-9A-F]{4})', pnp)
        extra = []
        if vram >= 2 ** 30:
            extra.append(fmt_gib(vram))
            vmax = max(vmax, round(vram / 2 ** 30))
        if ven and ven.group(1) in ('10DE', '1002') and sub and vram >= 2 ** 30:
            extra.append(GPU_AIB.get(sub.group(1), '') or '')
        extra = [e for e in extra if e]
        t = name + (f' ({" / ".join(extra)})' if extra else '')
        drv = _s(g.get('DriverVersion'))
        if drv and 'nvidia' in name.lower():
            digits = drv.replace('.', '')[-5:]
            if len(digits) == 5:
                drv = f'{digits[:3]}.{digits[3:]}'
        rows.append({'t': t, 'd': f'驱动版本 {drv}' if drv else ''})
    metrics['vram_gb'] = vmax
    return rows


def build_board(raw):
    b = _first(raw.get('board'))
    bios = _first(raw.get('bios'))
    man = cn_vendor(b.get('Manufacturer')) if not is_junk(b.get('Manufacturer')) else ''
    prod = clean(b.get('Product')) if not is_junk(b.get('Product')) else ''
    chip = [clean(c) for c in _list(raw.get('chipset'))]
    chip_s = ''
    if chip:
        c = chip[0]
        m = re.search(r'([A-Z]\d{2,3}[A-Z]?|X\d{3}[A-Z]?|B\d{3}[A-Z]?|H\d{2,3}|Z\d{2,3})', c)
        chip_s = c if not m else c
        chip_s = re.sub(r'\bIntel\b', '英特尔', chip_s)
    t = ' '.join(x for x in (man, prod) if x)
    if chip_s:
        t += f' ({chip_s})'
    d = []
    if bios:
        bv = clean(bios.get('SMBIOSBIOSVersion'))
        if bv:
            d.append(f'BIOS {bv}' + (f' ({bios.get("Date")})' if bios.get('Date') else ''))
    return [{'t': t, 'd': ' · '.join(d)}] if t else []


def build_monitors(raw):
    ids = _list(raw.get('mid'))
    szs = {_s(s.get('Inst')): s for s in _list(raw.get('msz'))}
    disp = enum_displays()
    by_code = {}
    for m in ids:
        code = _s(m.get('Inst')).split('\\')[1].upper() if '\\' in _s(m.get('Inst')) else ''
        by_code.setdefault(code, []).append(m)
    rows = []
    for dsp in disp:
        info = None
        lst = by_code.get(dsp['code'])
        if lst:
            info = lst.pop(0)
        brand = ''
        name = ''
        inch = ''
        if info:
            mfg = _s(info.get('Mfg')).upper()
            brand = MON_VENDOR.get(mfg, mfg)
            name = _s(info.get('Name')) or _s(info.get('Code')) or dsp['code']
            sz = szs.get(_s(info.get('Inst')), {})
            h, v = _int(sz.get('H')), _int(sz.get('V'))
            if h and v:
                inch = f' ({math.hypot(h, v) / 2.54:.1f} 英寸)'
        else:
            name = dsp['code'] or '显示器'
        if brand and name.lower().startswith(brand.lower()):
            name = name[len(brand):].strip()
        t = ' '.join(x for x in (brand, name) if x) + inch
        d = ''
        if dsp['w']:
            d = f'{dsp["w"]}×{dsp["h"]}' + (f' @ {dsp["hz"]}Hz' if dsp['hz'] > 1 else '')
            if dsp['primary'] and len(disp) > 1:
                d += ' · 主显示器'
        rows.append({'t': t, 'd': d})
    return rows


def build_disks(raw, metrics):
    sysn = raw.get('sysdisk')
    rows = []
    total_g = 0
    pds = _list(raw.get('pd'))
    pds = [p for p in pds if _s(p.get('BusType')).upper() not in ('USB', '7', 'SD', '12', 'MMC', '13')]
    if pds:
        for p in pds:
            name = localize_prefix(clean(p.get('FriendlyName')), DISK_BRAND)
            size = _int(p.get('Size'))
            mt, bus = _s(p.get('MediaType')).upper(), _s(p.get('BusType'))
            kind = {'SSD': '固态硬盘', 'HDD': '机械硬盘'}.get(mt, '')
            if not kind:
                kind = '固态硬盘' if re.search(r'ssd|nvme', name, re.I) or bus.lower() == 'nvme' else '硬盘'
            t = f'{name} ({fmt_disk(size)} / {kind})'
            d = []
            if bus and bus.lower() not in ('unknown', '0'):
                d.append({'17': 'NVMe'}.get(bus, bus))
            if sysn is not None and _s(p.get('Id')) == str(sysn):
                d.append('系统盘')
            rows.append({'t': t, 'd': ' · '.join(d), '_sys': 1 if (sysn is not None and _s(p.get('Id')) == str(sysn)) else 0})
            total_g += size / 1e9
    else:
        for p in _list(raw.get('dd')):
            if 'usb' in _s(p.get('InterfaceType')).lower():
                continue
            name = localize_prefix(clean(p.get('Model')), DISK_BRAND)
            size = _int(p.get('Size'))
            kind = '固态硬盘' if re.search(r'ssd|nvme', name, re.I) else '硬盘'
            rows.append({'t': f'{name} ({fmt_disk(size)} / {kind})', 'd': '', '_sys': 0})
            total_g += size / 1e9
    rows.sort(key=lambda r: -r.pop('_sys', 0))
    metrics['disk_gb'] = round(total_g)
    return rows


def build_net(raw):
    bad = re.compile(r'(bluetooth|virtual|vmware|hyper-v|tap-|wan miniport|npcap|vethernet|loopback|wintun|tailscale|zerotier)', re.I)
    rows = []
    for n in _list(raw.get('net')):
        desc = clean(n.get('InterfaceDescription'))
        if not desc or bad.search(desc):
            continue
        name = localize_prefix(desc, COMMON_BRAND)
        up = _s(n.get('Status')).lower() == 'up'
        d = ('已连接' + (f' · {n.get("LinkSpeed")}' if n.get('LinkSpeed') else '')) if up else '未连接'
        rows.append({'t': name, 'd': d})
    return rows


def build_sound(raw):
    bad = re.compile(r'(virtual|steam|oculus|vb-audio|remote|voicemeeter|cable|nahimic|sonar)', re.I)
    rows, seen = [], set()
    for s in _list(raw.get('snd')):
        name = clean(s.get('Name'))
        if not name or bad.search(name) or name in seen:
            continue
        seen.add(name)
        rows.append({'t': localize_prefix(name, COMMON_BRAND), 'd': ''})
    return rows


def collect(nickname=''):
    raw = run_ps(PS_SCRIPT)
    metrics = {}
    items = [
        ('cpu', '处理器', build_cpu(raw, metrics)),
        ('mem', '内存', build_mem(raw, metrics)),
        ('gpu', '显卡', build_gpu(raw, metrics)),
        ('board', '主板', build_board(raw)),
        ('monitor', '显示器', build_monitors(raw)),
        ('disk', '硬盘', build_disks(raw, metrics)),
        ('net', '网卡', build_net(raw)),
        ('sound', '声卡', build_sound(raw)),
    ]
    return {
        'app': 'HardwareShot', 'schema': SCHEMA, 'nickname': nickname,
        'scan_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
        'header': build_header(raw),
        'items': [{'key': k, 'label': l, 'rows': r} for k, l, r in items if r],
        'metrics': metrics,
    }
