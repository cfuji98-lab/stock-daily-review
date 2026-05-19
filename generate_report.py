#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股每日复盘报告生成器
自动采集数据→分析→生成HTML→推送到GitHub Pages
"""

import json, os, time, subprocess, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from datetime import datetime, timedelta
from urllib.request import Request, urlopen

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(REPO_DIR, 'docs')
os.makedirs(OUTPUT_DIR, exist_ok=True)

def fetch_json(url):
    """通用API请求"""
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        resp = urlopen(req, timeout=15)
        return json.loads(resp.read().decode('utf-8', errors='ignore'))
    except Exception as e:
        return {"error": str(e)}

def get_market_index():
    """获取主要指数行情"""
    codes = {
        "上证指数": "1.000001",
        "深证成指": "0.399001",
        "创业板指": "0.399006",
        "科创50": "1.000688"
    }
    result = {}
    for name, code in codes.items():
        url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={code}&fields=f43,f44,f45,f46,f47,f48,f50,f57,f58,f170,f171"
        data = fetch_json(url)
        d = data.get('data', {})
        if d and d.get('f43'):
            price = d.get('f43', 0) / 100
            change = d.get('f170', 0) / 100 if d.get('f170') else 0
            change_pct = d.get('f169', 0) if d.get('f169') else 0
            if isinstance(change_pct, (int, float)):
                pass
            elif d.get('f170'):
                change_pct = d['f170'] / 100
            open_p = d.get('f44', 0) / 100 if d.get('f44') else 0
            high = d.get('f45', 0) / 100 if d.get('f45') else 0
            low = d.get('f46', 0) / 100 if d.get('f46') else 0
            volume = d.get('f47', 0) or 0
            amount = d.get('f48', 0) or 0
            result[name] = {
                "price": round(price, 2), "change": round(change, 2),
                "change_pct": round(change_pct, 2),
                "open": round(open_p, 2), "high": round(high, 2), "low": round(low, 2),
                "volume": f"{volume/10000:.0f}万手" if volume else "—",
                "amount": f"{amount/100000000:.0f}亿" if amount else "—"
            }
        time.sleep(0.5)
    return result

def get_limit_up_down():
    """获取涨停/跌停数据"""
    url = "https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=30&po=1&np=1&fields=f12,f14,f2,f3,f62,f184,f66&fid=f3&fs=m:90+t:2+f:!50"
    data = fetch_json(url)
    up_list = []
    down_list = []
    items = data.get('data', {}).get('diff', [])
    for item in items or []:
        chg_pct = item.get('f3', 0)
        if chg_pct >= 9.8:
            up_list.append(f"{item.get('f14','')}({chg_pct:+.1f}%)")
        elif chg_pct <= -9.8:
            down_list.append(f"{item.get('f14','')}({chg_pct:+.1f}%)")
    return up_list[:10], down_list[:10]

def get_hot_sectors():
    """热门板块"""
    url = "https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=10&po=1&np=1&fields=f12,f14,f3,f4,f62,f184,f66&fid=f3&fs=m:90+t:3+f:!50"
    data = fetch_json(url)
    sectors = []
    items = data.get('data', {}).get('diff', [])
    for item in items or []:
        sectors.append({
            "name": item.get('f14', ''),
            "chg": f"{item.get('f3', 0):+.1f}%"
        })
    return sectors

def get_market_breadth():
    """涨跌家数"""
    url = "https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=5000&po=1&np=1&fields=f12,f3&fid=f3&fs=m:90+t:2"
    data = fetch_json(url)
    total = 0; up = 0; down = 0; flat = 0
    items = data.get('data', {}).get('diff', [])
    for item in items or []:
        total += 1
        chg = item.get('f3', 0)
        if chg > 0: up += 1
        elif chg < 0: down += 1
        else: flat += 1
    return {"total": total, "up": up, "down": down, "flat": flat}

def get_news():
    """财经新闻"""
    url = "https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&fields=f12,f14,f2,f3,f4&secids=1.000001&np=1"
    # 用财联社快讯
    url2 = "https://www.cls.cn/api/telegraph"
    return []

def get_stock_picks():
    """AI选股推荐"""
    # 基于当前市场状态给出推荐逻辑
    return [
        {"name": "注意：以下不构成投资建议", "reason": "市场有风险，投资需谨慎"},
        {"name": "建议关注方向", "reason": "跟随当日热门板块及资金流向"}
    ]

def generate_html(indexes, limit_up, limit_down, sectors, breadth, news, picks):
    """生成漂亮的HTML报告"""
    now = datetime.now()
    date_str = now.strftime('%Y-%m-%d')
    weekday_cn = ['一','二','三','四','五','六','日'][now.weekday()]
    
    # 判断行情
    sh = indexes.get('上证指数', {})
    market_status = "📈" if sh.get('change', 0) > 0 else "📉" if sh.get('change', 0) < 0 else "➖"
    change_str = f"{sh.get('change', 0):+.2f}" if sh.get('change') else "—"
    pct_str = f"{sh.get('change_pct', 0):+.2f}%" if sh.get('change_pct') else "—"
    
    # 涨跌家数判断
    breadth_str = ""
    if breadth:
        ratio = breadth.get('up', 0) / max(breadth.get('total', 1), 1) * 100
        breadth_str = f"上涨{breadth.get('up',0)}家 / 下跌{breadth.get('down',0)}家 / 平盘{breadth.get('flat',0)}家"
        if ratio > 60: breadth_str += " 🟢 市场情绪积极"
        elif ratio < 40: breadth_str += " 🔴 市场情绪低迷"
        else: breadth_str += " 🟡 市场情绪中性"
    
    # 涨停跌停
    zt_str = "、".join(limit_up[:5]) if limit_up else "暂无"
    dt_str = "、".join(limit_down[:5]) if limit_down else "暂无"
    
    # 热门板块
    sector_str = ""
    for s in sectors[:5]:
        arrow = "📈" if '+' in s.get('chg','') else "📉"
        sector_str += f"<span class='tag'>{arrow} {s['name']} {s['chg']}</span>\n"
    
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>A股每日复盘 {date_str}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#0a0e17;color:#e0e0e0;padding:20px}}
.container{{max-width:800px;margin:0 auto}}
.header{{text-align:center;padding:30px 0 20px;border-bottom:1px solid rgba(255,255,255,.08);margin-bottom:24px}}
.header h1{{font-size:28px;background:linear-gradient(135deg,#f59e0b,#ef4444);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.header .date{{color:rgba(255,255,255,.4);font-size:14px;margin-top:6px}}
.card{{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);border-radius:16px;padding:20px;margin-bottom:16px}}
.card h2{{font-size:18px;margin-bottom:14px;display:flex;align-items:center;gap:8px}}
.index-grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.index-item{{background:rgba(255,255,255,.03);border-radius:10px;padding:14px}}
.index-item .name{{font-size:13px;color:rgba(255,255,255,.5);margin-bottom:4px}}
.index-item .price{{font-size:22px;font-weight:700}}
.index-item .change{{font-size:14px;margin-top:2px}}
.up{{color:#ef4444}}
.down{{color:#22c55e}}
.flat{{color:rgba(255,255,255,.3)}}
.tag{{display:inline-block;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);border-radius:6px;padding:4px 10px;font-size:12px;margin:3px}}
.breadth{{font-size:14px;line-height:1.8}}
.zt{{color:#ef4444;font-weight:600}}
.dt{{color:#22c55e;font-weight:600}}
.qrcode-section{{text-align:center;border-top:1px solid rgba(255,255,255,.08);margin-top:24px;padding-top:20px}}
.qrcode-section p{{font-size:13px;color:rgba(255,255,255,.4);margin-bottom:10px}}
.qrcode-section img{{width:180px;height:180px;border-radius:12px}}
.footer{{text-align:center;font-size:12px;color:rgba(255,255,255,.2);padding:20px}}
</style>
</head>
<body>
<div class="container">
<div class="header">
<h1>{market_status} A股每日复盘</h1>
<div class="date">{date_str} 星期{weekday_cn} · AI自动生成</div>
</div>

<div class="card">
<h2>📊 主要指数</h2>
<div class="index-grid">
'''
    for name, data in indexes.items():
        cls = "up" if data.get('change', 0) > 0 else "down" if data.get('change', 0) < 0 else "flat"
        chg = f"{data.get('change', 0):+.2f}" if data.get('change') else "—"
        pct = f"{data.get('change_pct', 0):+.2f}%" if data.get('change_pct') else "—"
        price = f"{data.get('price', 0):.2f}" if data.get('price') else "—"
        html += f'''
<div class="index-item">
<div class="name">{name}</div>
<div class="price">{price}</div>
<div class="change {cls}">{chg} ({pct})</div>
</div>'''
    
    html += '''
</div>
</div>

<div class="card">
<h2>📈 涨跌分布</h2>
<div class="breadth">''' + breadth_str + '''</div>
</div>

<div class="card">
<h2>🔥 涨停/跌停</h2>
<p>涨停：<span class="zt">''' + zt_str + '''</span></p>
<p style="margin-top:6px">跌停：<span class="dt">''' + dt_str + '''</span></p>
</div>

<div class="card">
<h2>📌 热门板块</h2>
<div>''' + sector_str + '''</div>
</div>

<div class="card">
<h2>💰 今日成交</h2>
<p>''' + f"沪市{sh.get('amount','—')}" + '''</p>
<p style="font-size:13px;color:rgba(255,255,255,.4);margin-top:6px">数据来源：东方财富 · 仅供参考</p>
</div>

<div class="qrcode-section">
<p>如果对你有帮助，欢迎打赏支持持续更新 ☕</p>
<img src="assets/qrcode.png" alt="收款码">
</div>

<div class="footer">
AI自动生成 · 每日收盘后更新 · 不构成投资建议
</div>
</div>
</body>
</html>'''
    return html

def main():
    print("=== A股每日复盘报告生成 ===")
    
    print("1/5 获取指数行情...")
    indexes = get_market_index()
    print(f"   获取到 {len(indexes)} 个指数")
    
    print("2/5 获取涨跌停数据...")
    limit_up, limit_down = get_limit_up_down()
    print(f"   涨停 {len(limit_up)} 跌停 {len(limit_down)}")
    
    print("3/5 获取热门板块...")
    sectors = get_hot_sectors()
    print(f"   获取到 {len(sectors)} 个板块")
    
    print("4/5 获取涨跌分布...")
    breadth = get_market_breadth()
    print(f"   上涨{breadth.get('up',0)} 下跌{breadth.get('down',0)}")
    
    print("5/5 生成HTML...")
    html = generate_html(indexes, limit_up, limit_down, sectors, breadth, [], [])
    
    outpath = os.path.join(OUTPUT_DIR, 'index.html')
    with open(outpath, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ 报告已生成: {outpath}")
    
    # 复制收款码到docs
    import shutil
    qr_src = os.path.join(REPO_DIR, 'assets', 'qrcode.png')
    qr_dst = os.path.join(OUTPUT_DIR, 'assets', 'qrcode.png')
    os.makedirs(os.path.dirname(qr_dst), exist_ok=True)
    if os.path.exists(qr_src):
        shutil.copy2(qr_src, qr_dst)
    
    # 推送到GitHub
    os.chdir(REPO_DIR)
    subprocess.run(['git', 'add', '.'], capture_output=True)
    subprocess.run(['git', 'commit', '-m', f'每日复盘 {datetime.now().strftime("%Y-%m-%d")}'], capture_output=True)
    result = subprocess.run(['git', 'push'], capture_output=True, text=True)
    print(f"✅ 已推送到GitHub")
    print(f"   https://cfuji98-lab.github.io/stock-daily-review/")

if __name__ == '__main__':
    main()
