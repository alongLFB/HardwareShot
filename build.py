# -*- coding: utf-8 -*-
"""一键打包:生成图标 -> PyInstaller 单文件 exe -> 生成发布目录和 zip。用法: python build.py"""
import os
import shutil
import subprocess
import sys
import zipfile

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = '硬件配置助手'
os.chdir(HERE)


def make_icon(path):
    S = 512
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    grad = Image.new('RGB', (S, S))
    gd = ImageDraw.Draw(grad)
    for i in range(S):
        t = i / S
        gd.line([(0, i), (S, i)], fill=(int(0 + 10 * t), int(120 - 30 * t), int(255 - 40 * t)))
    mask = Image.new('L', (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([16, 16, S - 16, S - 16], radius=110, fill=255)
    img.paste(grad, (0, 0), mask)
    w = (255, 255, 255, 255)
    d.rounded_rectangle([96, 120, 416, 330], radius=26, outline=w, width=22)
    for i, h in enumerate((60, 100, 78, 120)):
        x = 140 + i * 62
        d.rounded_rectangle([x, 290 - h, x + 34, 290], radius=8, fill=w)
    d.rectangle([242, 352, 270, 392], fill=w)
    d.rounded_rectangle([172, 388, 340, 414], radius=13, fill=w)
    img.save(path, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])


def main():
    ico = os.path.join(HERE, 'app.ico')
    make_icon(ico)
    ver_file = os.path.join(HERE, 'version_info.txt')
    for d in ('build', 'dist'):
        shutil.rmtree(os.path.join(HERE, d), ignore_errors=True)
    cmd = [
        sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--windowed',
        '--name', NAME, '--icon', ico,
        '--version-file', ver_file,
        '--exclude-module', 'numpy', '--exclude-module', 'matplotlib',
        'main.py'
    ]
    subprocess.check_call(cmd)
    pkg = os.path.join(HERE, 'dist', NAME)
    os.makedirs(pkg, exist_ok=True)
    shutil.move(os.path.join(HERE, 'dist', NAME + '.exe'), os.path.join(pkg, NAME + '.exe'))
    shutil.copy(os.path.join(HERE, 'README.txt'), os.path.join(pkg, '使用说明.txt'))

    bat_path = os.path.join(pkg, '一键解除拦截运行.bat')
    bat_content = (
        "@echo off\r\n"
        "chcp 65001 >nul\r\n"
        "title 硬件配置助手 - 解除 Windows 拦截保护\r\n"
        "cd /d \"%~dp0\"\r\n"
        "echo ========================================================\r\n"
        "echo   硬件配置助手 - 一键解除 Windows 智能拦截保护\r\n"
        "echo ========================================================\r\n"
        "echo.\r\n"
        "echo 正在解除下载锁定保护 (Unblock-File)... \r\n"
        "powershell -NoProfile -Command \"Unblock-File -Path '.\\硬件配置助手.exe' -ErrorAction SilentlyContinue\"\r\n"
        "echo 解除完成！正在为您启动硬件配置助手...\r\n"
        "echo.\r\n"
        "start \"\" \"硬件配置助手.exe\"\r\n"
    )
    with open(bat_path, 'w', encoding='utf-8') as f:
        f.write(bat_content)

    zp = os.path.join(HERE, 'dist', NAME + '.zip')
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in os.listdir(pkg):
            z.write(os.path.join(pkg, f), f'{NAME}/{f}')
    print('\n发布目录:', pkg)
    print('压缩包  :', zp)


if __name__ == '__main__':
    main()
