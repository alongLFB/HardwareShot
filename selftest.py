# -*- coding: utf-8 -*-
"""一次性测试:扫描 -> 渲染本机长图 + 构造一份"好友"数据生成对比图。"""
import copy
import json
import os
import sys

import collector
import renderer

out = sys.argv[1] if len(sys.argv) > 1 else 'out'
os.makedirs(out, exist_ok=True)
me = collector.collect('阿龙')
fr = copy.deepcopy(me)
fr['nickname'] = '小王'
fr['header']['model'] = '联想 QiTianM4500-N070 台式电脑'
fr['items'][0]['rows'] = [{'t': '英特尔 Celeron(赛扬) G1840 @ 2.80GHz 双核', 'd': '2核心 2线程'}]
fr['items'][1]['rows'] = [{'t': '8 GB (金士顿 DDR3 1600MHz 4GB x 2)', 'd': ''}]
fr['items'][2]['rows'] = [{'t': 'Intel(R) HD Graphics (1GB / 联想)', 'd': ''}]
fr['metrics'].update(cpu_cores=2, cpu_threads=2, ram_gb=8, ram_speed=1600, vram_gb=0, disk_gb=320)
for th in renderer.THEMES:
    renderer.render_report(me, th, True).save(os.path.join(out, f'report_{th}.png'))
renderer.render_compare(me, fr, '科技蓝', True).save(os.path.join(out, 'compare.png'))
json.dump(me, open(os.path.join(out, 'me.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('ok')
