#!/usr/bin/env python3
"""Serenity-A 数据面板后端 — 本地运行，零外部费用"""

import time, random, json, re, urllib.request, urllib.parse, datetime as dt, os, sys

# ── Flask ──
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# ── DeepSeek API（从环境变量读取）──
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

# ── 东财防封：全局节流 + 会话复用（强制不走代理）──
import requests as http_requests
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
EM_SESSION = http_requests.Session()
EM_SESSION.headers.update({"User-Agent": UA})
EM_SESSION.trust_env = False  # 忽略系统代理
EM_MIN_INTERVAL = 2.0
_em_last_call = [0.0]

def em_get(url, params=None, headers=None, timeout=15, **kwargs):
    wait = EM_MIN_INTERVAL - (time.time() - _em_last_call[0])
    if wait > 0: time.sleep(wait + random.uniform(0.1, 0.5))
    try:
        return EM_SESSION.get(url, params=params, headers=headers, timeout=timeout, **kwargs)
    finally:
        _em_last_call[0] = time.time()

DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"

def eastmoney_datacenter(report_name, columns="ALL", filter_str="",
                         page_size=50, sort_columns="", sort_types="-1"):
    params = {"reportName": report_name, "columns": columns,
              "filter": filter_str, "pageNumber": "1", "pageSize": str(page_size),
              "sortColumns": sort_columns, "sortTypes": sort_types,
              "source": "WEB", "client": "WEB"}
    r = em_get(DATACENTER_URL, params=params, timeout=15)
    if r.status_code != 200: return []
    try:
        d = r.json()
        if d.get("result") and d["result"].get("data"):
            return d["result"]["data"]
    except: pass
    return []

# ── 1. 实时行情 ──
def tencent_quote(code):
    """腾讯财经实时行情"""
    prefix = "sh" if code.startswith(("6","9")) else "sz"
    url = f"https://qt.gtimg.cn/q={prefix}{code}"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", UA)
    try:
        resp = urllib.request.urlopen(req, timeout=8)
        data = resp.read().decode("gbk")
        for line in data.strip().split(";"):
            if not line.strip() or "=" not in line or '"' not in line: continue
            vals = line.split('"')[1].split("~")
            if len(vals) < 46: continue
            return {
                "name": vals[1], "code": code,
                "price": float(vals[3]) if vals[3] else 0,
                "last_close": float(vals[4]) if vals[4] else 0,
                "pe_ttm": float(vals[9]) if vals[9] else 0,
                "high": float(vals[33]) if vals[33] else 0,
                "low": float(vals[34]) if vals[34] else 0,
                "open": float(vals[5]) if vals[5] else 0,
                "vol": int(vals[6]) if vals[6] else 0,
                "amount_wan": float(vals[37]) if vals[37] else 0,
                "turnover_pct": float(vals[38]) if vals[38] else 0,
                "mcap_yi": round(float(vals[45])/10000, 2) if vals[45] else 0,
                "fmcap_yi": round(float(vals[44])/10000, 2) if vals[44] else 0,
                "pb": float(vals[46]) if vals[46] else 0,
                "change_pct": float(vals[32]) if vals[32] else 0,
                "change_amt": float(vals[31]) if vals[31] else 0,
                "amplitude": float(vals[43]) if vals[43] else 0,
                "high_52w": float(vals[40]) if vals[40] else 0,
                "low_52w": float(vals[41]) if vals[41] else 0,
            }
    except: return {}

# ── 2. 财务数据（mootdx）──
def get_finance(code):
    """mootdx 财务快照"""
    try:
        from mootdx.quotes import Quotes
        client = Quotes.factory(market='std')
        market = 0 if not code.startswith(("6","9")) else 1
        fin = client.finance(market=market, symbol=code)
        if fin:
            return {
                "eps": fin.get("eps", 0),  # 每股收益
                "bps": fin.get("wz每股净资产", 0),
                "revenue": fin.get("营业收入", 0),  # 万
                "profit": fin.get("净利润", 0),  # 万
                "total_shares": fin.get("总股本", 0),
                "roe": fin.get("roe", 0),
                "gross_margin": fin.get("销售毛利率", 0),
                "net_margin": fin.get("净利润率", 0),
                "total_assets": fin.get("总资产", 0),
                "current_assets": fin.get("流动资产", 0),
                "current_liab": fin.get("流动负债", 0),
                "equity": fin.get("股东权益", 0),
                "goodwill": fin.get("商誉", 0),
            }
    except: pass
    return {}

# ── 3. 概念板块归属 ──
def get_concepts(code):
    mkt = "0" if not code.startswith(("6","9")) else "1"
    url = "https://slist.eastmoney.com/api/list/get"
    params = {"st":1,"sr":-1,"p":1,"ps":50,"filter":f'(Code="{mkt}.{code}")',"client":"web"}
    r = em_get(url, params=params)
    if r.status_code != 200: return []
    try:
        items = r.json().get("data",{}).get("list",[])
        return [{"name":i.get("BoardName",""), "code":i.get("BoardCode","")} for i in items if i.get("BoardName")]
    except: return []

# ── 4. 北向资金 ──
def get_northbound():
    results = {}
    for market in ["hgt","sgt"]:
        url = "https://push2.eastmoney.com/api/qt/kamt.kline/get"
        params = {"fields1":"f1,f2,f3,f4","fields2":"f51,f52,f53",
                  "klt":1,"lmt":120,"market":1 if market=="hgt" else 2}
        r = em_get(url, params=params)
        if r.status_code != 200: continue
        try:
            klines = r.json().get("data",{}).get("klines",[])
            results[market] = []
            for k in klines[-5:]:
                parts = k.split(",")
                results[market].append({"time":parts[0],"net_flow":float(parts[1]) if len(parts)>1 else 0})
        except: continue
    return results

# ── 5. 龙虎榜 ──
def get_lhb():
    today = dt.date.today().strftime("%Y%m%d")
    # try yesterday if today no data
    try:
        data = eastmoney_datacenter("RPT_F10_EFFECTIVE_LHB",filter_str=f"(TRADE_DATE='{today}')",sort_columns="NET_BUY_AMT",sort_types="-1",page_size=20)
        if not data:
            yesterday = (dt.date.today() - dt.timedelta(days=1)).strftime("%Y%m%d")
            data = eastmoney_datacenter("RPT_F10_EFFECTIVE_LHB",filter_str=f"(TRADE_DATE='{yesterday}')",sort_columns="NET_BUY_AMT",sort_types="-1",page_size=20)
    except: return []
    results = []
    for item in data:
        results.append({
            "code":item.get("SCODE",""),"name":item.get("SECUNAME",""),
            "net_buy":item.get("NET_BUY_AMT",0),"buy_amt":item.get("BUY_AMT",0),"sell_amt":item.get("SELL_AMT",0)
        })
    return results

# ── 6. 解禁日历 ──
def get_jiejin(code):
    data = eastmoney_datacenter("RPT_LIFTING_SHARETYPE_LIST",filter_str=f'(SCODE="{code}")',sort_columns="DECLAR_DATE",sort_types="1",page_size=30)
    return [{"date":i.get("DECLAR_DATE",""),"ratio":i.get("REMARK_RATIO",0),"type":i.get("SHARE_TYPE_NAME","")} for i in data]

# ── 7. 融资融券 ──
def get_margin(code):
    data = eastmoney_datacenter("RPTA_F10_MARGIN_TRADING",filter_str=f'(SCODE="{code}")',sort_columns="TRADE_DATE",sort_types="-1",page_size=10)
    return [{"date":i.get("TRADE_DATE",""),"fin_balance":i.get("FUND_BALANCE",0),"fin_buy":i.get("FUND_BUY_AMT",0),"sec_balance":i.get("STOCK_BALANCE",0)} for i in data]

# ── 8. 股东户数 ──
def get_holders(code):
    data = eastmoney_datacenter("RPT_HOLDERNUMLATEST",filter_str=f'(SCODE="{code}")',sort_columns="END_DATE",sort_types="-1",page_size=6)
    return [{"date":i.get("END_DATE",""),"holders":i.get("HOLDER_TOTAL",0),"change_pct":i.get("HOLDER_CHANGE_RATIO",0)} for i in data]

# ── 9. 一致预期 ──
def get_consensus(code):
    url = f"https://basic.10jqka.com.cn/{code}/research.html"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", UA)
    try:
        resp = urllib.request.urlopen(req, timeout=8)
        html = resp.read().decode("gbk", errors="ignore")
        eps = re.findall(r'"eps(\d{4})":\s*([\d.]+)', html)
        rev = re.findall(r'"revenue(\d{4})":\s*([\d.]+)', html)
        return {
            "eps": {y:float(v) for y,v in eps[:3]},
            "revenue": {y:float(v) for y,v in rev[:3]},
        }
    except: return {}

# ── 10. 个股资金流向 ──
def get_moneyflow(code):
    mkt = "0" if not code.startswith(("6","9")) else "1"
    secid = f"{mkt}.{code}"
    url = "https://push2his.eastmoney.com/api/qt/stock/fflow/kline/get"
    params = {"secid":secid,"fields1":"f1,f2,f3,f4","fields2":"f51,f52,f53,f54,f55,f56,f57","klt":1,"lmt":120}
    r = em_get(url, params=params)
    if r.status_code != 200: return []
    try:
        klines = r.json().get("data",{}).get("klines",[])
        results=[]
        for k in klines[-5:]:
            parts=k.split(",")
            if len(parts)>=7:
                results.append({
                    "date":parts[0],"main_net":float(parts[1]),
                    "super_large":float(parts[2]),"large":float(parts[3]),
                    "medium":float(parts[4]),"small":float(parts[5])
                })
        return results
    except: return []

# ═══════════════════════════════════════
#  Serenity-A 卡点评分引擎
# ═══════════════════════════════════════

def score_bottleneck(data):
    """
    根据拉取到的数据，自动判断命中几条卡点判据和红旗
    """
    quote = data.get("quote", {})
    finance = data.get("finance", {})
    concepts = data.get("concepts", [])
    holders = data.get("holders", [])

    mcap_yi = quote.get("mcap_yi", 0)
    pe = quote.get("pe_ttm", 0)
    change_pct = quote.get("change_pct", 0)
    turnover = quote.get("turnover_pct", 0)

    gross_margin = finance.get("gross_margin", 0)
    roe = finance.get("roe", 0)
    profit = finance.get("profit", 0)
    revenue = finance.get("revenue", 0)
    goodwill = finance.get("goodwill", 0)
    equity = finance.get("equity", 0) or 1
    current_assets = finance.get("current_assets", 0)
    current_liab = finance.get("current_liab", 0)

    criteria_hit = []
    redflags_hit = []

    # ── 判据 1: 结构性垄断 — 无法直接判断，需要产业知识 ──

    # 判据 2: 极小市值 vs 巨大TAM
    if mcap_yi > 0 and mcap_yi < 100:
        criteria_hit.append({"id":2, "name":"极小市值 vs 巨大 TAM", "detail":f"市值仅 {mcap_yi}亿，<100亿，有不对称空间", "score":"+1"})

    # 判据 5: 资产负债表能活
    if current_assets > 0 and current_liab > 0:
        ratio = current_assets / current_liab if current_liab else 0
        if ratio > 1.5:
            criteria_hit.append({"id":5, "name":"资产负债表健康", "detail":f"流动比率 {ratio:.1f}，短期无忧", "score":"+1"})

    # 判据 11: 机构认知不足
    if turnover > 0 and turnover < 3:
        criteria_hit.append({"id":11, "name":"机构认知不足", "detail":f"换手率仅 {turnover}%，关注度低", "score":"+1"})

    # 判据 12: 单位经济好
    if gross_margin > 0:
        if gross_margin > 50:
            criteria_hit.append({"id":12, "name":"毛利率优秀", "detail":f"毛利率 {gross_margin:.1f}% > 50%", "score":"+1"})
        elif gross_margin > 30:
            criteria_hit.append({"id":12, "name":"毛利率良好", "detail":f"毛利率 {gross_margin:.1f}%", "score":"+0.5"})

    # 判据 14: 热点概念
    ai_related = ["AI","智能","芯片","半导体","光模块","机器人","算力","数据","光通信"]
    hit_concepts = [c["name"] for c in concepts if any(k in c["name"] for k in ai_related)]
    if hit_concepts:
        criteria_hit.append({"id":14, "name":"AI/科技核心概念", "detail":f"所属概念: {', '.join(hit_concepts[:4])}", "score":"+1"})

    # ── 红旗 4: 零收入纯概念
    if revenue == 0 and profit == 0 and len(concepts) > 0:
        redflags_hit.append({"id":4, "name":"⚠️ 零收入纯概念", "detail":"有概念归属但无营收数据，警惕纯题材炒作", "severity":"hard"})

    # 红旗 7: 大市值无不对称
    if mcap_yi > 500:
        redflags_hit.append({"id":7, "name":"⚠️ 大市值已无不对称", "detail":f"市值 {mcap_yi}亿 > 500亿，框架判断力弱", "severity":"mid"})

    # 红旗 9: 大股东减持 — 无法直接判断，需要公告数据

    # 红旗 10: 巨额解禁
    jiejin = data.get("jiejin", [])
    high_ratio_jj = [j for j in jiejin if j.get("ratio",0) and j["ratio"] > 30]
    if high_ratio_jj:
        redflags_hit.append({"id":10, "name":"⚠️ 巨额解禁临近", "detail":f"解禁比例 {high_ratio_jj[0]['ratio']}%，注意供给冲击", "severity":"high"})

    # 红旗 12: 商誉过高
    if goodwill and equity and goodwill / equity > 0.5:
        redflags_hit.append({"id":12, "name":"⚠️ 商誉过高", "detail":f"商誉/净资产 {goodwill/equity:.1%} > 50%", "severity":"high"})

    # 综合评分
    score = sum(float(c["score"]) for c in criteria_hit)
    has_hard_redflag = any(r["severity"] == "hard" for r in redflags_hit)
    has_high_redflag = any(r["severity"] == "high" for r in redflags_hit)

    if has_hard_redflag:
        verdict = "Sell — 存在硬否决红旗"
    elif score >= 3 and not has_high_redflag:
        verdict = "Buy — 卡点置信度高"
    elif score >= 1.5:
        verdict = "Hold — 需进一步验证"
    else:
        verdict = "Hold — 数据不足以判断"

    return {
        "criteria_hit": criteria_hit,
        "redflags_hit": redflags_hit,
        "total_score": score,
        "verdict": verdict,
        "max_possible": 5,
    }


# ═══════════════════════════════════════
#  DeepSeek 分析
# ═══════════════════════════════════════

SYSTEM_PROMPT = """你是 Serenity-A 分析引擎，使用供应链卡点逆向投资方法论分析 A 股标的。

## 核心方法
从下游需求出发，沿供应链向上逆推，找到"市值最小、却卡住最大瓶颈、市场还没充分定价"的环节。

## 分析要求
1. 结论先行 — 第一句给出 thesis + 方向性判断 + 因由
2. 判断显形 — 点明命中哪几条卡点判据/红旗
3. 风险先写、bull 后写
4. 始终给出"什么会证伪这个 thesis"
5. 中文表达，保留术语（PE/PB/ROE/光模块），去掉英式句法

## 输出结构
### 一句话结论
### 供应链定位
### 卡点判断（命中判据/红旗）
### 估值（bear/base/bull）
### 美股映射（如有）
### 催化剂与证伪门
### 综合判定

注意：不是投资建议，仅分析框架推演。"""

def call_deepseek_analysis(code, name, data_json):
    """调用 DeepSeek API 进行 Serenity-A 框架分析"""
    user_prompt = f"""请用 Serenity-A 框架分析 A 股标的 {code} ({name})。

## 当前数据
{json.dumps(data_json, ensure_ascii=False, indent=2)}

请根据以上数据，输出完整的供应链卡点逆向分析报告。注意：
- 如果数据不足就诚实说
- 给出 bear/base/bull 三档方向
- 不要编造没有的数据
- 所有推断都标出来"""

    try:
        resp = http_requests.post(
            DEEPSEEK_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 4096,
            },
            timeout=120
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        else:
            return f"API 调用失败: HTTP {resp.status_code} - {resp.text[:200]}"
    except Exception as e:
        return f"API 调用异常: {str(e)}"


# ═══════════════════════════════════════
#  Flask Routes
# ═══════════════════════════════════════

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    if os.path.exists(path) and not path.startswith('api/'):
        return send_from_directory('.', path)
    return send_from_directory('.', 'index.html')

@app.route('/api/stock/<code>')
def api_stock(code):
    """获取单只股票的全量数据"""
    code = code.strip().split('.')[0][-6:]  # 归一化
    if not code.isdigit() or len(code) != 6:
        return jsonify({"error": "请输入6位股票代码"})

    quote = tencent_quote(code)
    if not quote:
        return jsonify({"error": f"未找到股票 {code}，请检查代码是否正确"})

    data = {
        "quote": quote,
        "finance": {},
        "concepts": [],
        "holders": [],
        "jiejin": [],
        "margin": [],
        "moneyflow": [],
        "consensus": {},
        "northbound": {},
        "lhb": [],
    }

    # 并行拉取（串行但快速·每个独立容错）
    for _k, _f in [("finance", lambda: get_finance(code) or {}),
                   ("concepts", lambda: get_concepts(code) or []),
                   ("holders", lambda: get_holders(code) or []),
                   ("jiejin", lambda: get_jiejin(code) or []),
                   ("margin", lambda: get_margin(code) or []),
                   ("moneyflow", lambda: get_moneyflow(code) or []),
                   ("consensus", lambda: get_consensus(code) or {}),
                   ("northbound", lambda: get_northbound() or {}),
                   ("lhb", lambda: get_lhb() or [])]:
        try: data[_k] = _f()
        except: data[_k] = {} if isinstance(data.get(_k, {}), dict) else []

    # 卡点评分
    data["score"] = score_bottleneck(data)

    return jsonify(data)

@app.route('/api/analyze/<code>')
def api_analyze(code):
    """获取完整分析报告（含 DeepSeek AI 分析）"""
    code = code.strip().split('.')[0][-6:]
    if not code.isdigit() or len(code) != 6:
        return jsonify({"error": "请输入6位股票代码"})

    # 先拉数据
    quote = tencent_quote(code)
    if not quote:
        return jsonify({"error": f"未找到股票 {code}"})

    name = quote.get("name", code)
    data = {"quote": quote}
    for _k, _f in [("finance", lambda: get_finance(code) or {}),
                   ("concepts", lambda: get_concepts(code) or []),
                   ("holders", lambda: get_holders(code) or []),
                   ("jiejin", lambda: get_jiejin(code) or []),
                   ("margin", lambda: get_margin(code) or []),
                   ("moneyflow", lambda: get_moneyflow(code) or []),
                   ("consensus", lambda: get_consensus(code) or {}),
                   ("northbound", lambda: get_northbound() or {}),
                   ("lhb", lambda: get_lhb() or [])]:
        try: data[_k] = _f()
        except: data[_k] = {} if isinstance(data.get(_k, {}), dict) else []

    data["score"] = score_bottleneck(data)

    # 调用 DeepSeek
    analysis = call_deepseek_analysis(code, name, data)

    return jsonify({
        "code": code,
        "name": name,
        "data": data,
        "analysis": analysis
    })

@app.route('/api/market')
def api_market():
    """获取市场概况和热点"""
    codes = ["000001","399006","000688","399303","300308","300394","300502","688017","002463"]
    results = {}
    for c in codes:
        q = tencent_quote(c)
        if q: results[c] = q
    try:
        lhb = get_lhb()[:10]
    except:
        lhb = []
    return jsonify({"stocks": results, "lhb": lhb})


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8765))
    print(f"🚀 Serenity-A 数据面板启动中...")
    print(f"   访问地址: http://localhost:{port}")
    print(f"   按 Ctrl+C 停止")
    print()
    app.run(host='0.0.0.0', port=port, debug=False)
