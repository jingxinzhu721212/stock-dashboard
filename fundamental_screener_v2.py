import os
import yfinance as yf
import pandas as pd
from datetime import datetime, timezone

DEFAULT_WATCHLIST = [
    "AAPL", "GOOGL", "MSFT", "META", "AMZN",
    "UNH",  "JNJ",   "ABT",
    "KO",   "PG",    "WMT",
    "VZ",   "T",
    "JPM",  "BRK-B",
]

CYCLICAL_SECTORS = {
    "Energy", "Materials", "Industrials",
    "Consumer Cyclical", "Real Estate"
}

def get_watchlist():
    env = os.environ.get("CUSTOM_TICKERS", "").strip()
    if env:
        return [t.strip().upper() for t in env.split(",") if t.strip()]
    return DEFAULT_WATCHLIST

def fetch_fundamentals(ticker):
    try:
        stock = yf.Ticker(ticker)
        info  = stock.info
        fcf = None
        cashflow = stock.cashflow
        if not cashflow.empty:
            try:
                operating = cashflow.loc["Operating Cash Flow"].iloc[0]
                capex     = cashflow.loc["Capital Expenditure"].iloc[0]
                fcf = operating + capex
            except KeyError:
                pass
        return {
            "ticker":          ticker,
            "name":            info.get("shortName", ticker),
            "sector":          info.get("sector", "N/A"),
            "industry":        info.get("industry", "N/A"),
            "price":           info.get("currentPrice"),
            "pe":              info.get("trailingPE"),
            "forward_pe":      info.get("forwardPE"),
            "pb":              info.get("priceToBook"),
            "roe":             info.get("returnOnEquity"),
            "gross_margin":    info.get("grossMargins"),
            "profit_margin":   info.get("profitMargins"),
            "debt_equity":     info.get("debtToEquity"),
            "revenue_growth":  info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "dividend_yield":  info.get("dividendYield"),
            "payout_ratio":    info.get("payoutRatio"),
            "beta":            info.get("beta"),
            "fcf":             fcf,
            "market_cap":      info.get("marketCap"),
        }
    except Exception as e:
        print(f"  ⚠️  {ticker} 获取失败: {e}")
        return {"ticker": ticker, "name": ticker, "sector": "N/A", "industry": "N/A"}

def classify_stock(data):
    types = []
    pe             = data.get("pe")
    pb             = data.get("pb")
    roe            = data.get("roe")
    gross_margin   = data.get("gross_margin")
    profit_margin  = data.get("profit_margin")
    revenue_growth = data.get("revenue_growth")
    earnings_growth= data.get("earnings_growth")
    dividend_yield = data.get("dividend_yield")
    payout_ratio   = data.get("payout_ratio")
    debt_equity    = data.get("debt_equity")
    beta           = data.get("beta")
    fcf            = data.get("fcf")
    sector         = data.get("sector", "")

    growth_score = 0
    if revenue_growth  and revenue_growth  > 0.15: growth_score += 1
    if earnings_growth and earnings_growth > 0.15: growth_score += 1
    if pe              and pe < 60:                growth_score += 1
    if growth_score >= 2:
        types.append("🚀 成长股")

    value_score = 0
    if pe  and pe  < 15:  value_score += 2
    elif pe and pe < 20:  value_score += 1
    if pb  and pb  < 1.5: value_score += 2
    elif pb and pb < 3.0: value_score += 1
    if profit_margin and profit_margin > 0.05: value_score += 1
    if value_score >= 3:
        types.append("💰 价值股")

    moat_score = 0
    if roe          and roe          > 0.20: moat_score += 2
    elif roe        and roe          > 0.15: moat_score += 1
    if gross_margin and gross_margin > 0.50: moat_score += 2
    elif gross_margin and gross_margin > 0.35: moat_score += 1
    if profit_margin and profit_margin > 0.15: moat_score += 1
    if moat_score >= 3:
        types.append("🏰 护城河股")

    if dividend_yield and dividend_yield > 0.02:
        if (payout_ratio is None or payout_ratio < 0.8) and (fcf is not None and fcf > 0):
            types.append("🏦 股息股")

    if sector in CYCLICAL_SECTORS:
        types.append("🔄 周期股")

    if sector in {"Consumer Defensive", "Healthcare", "Utilities"}:
        if beta is None or beta < 0.8:
            types.append("🛡️ 防御股")

    danger_score = 0
    if debt_equity    and debt_equity    > 200:   danger_score += 2
    if fcf            and fcf            < 0:     danger_score += 2
    if revenue_growth and revenue_growth < -0.05: danger_score += 1
    if profit_margin  and profit_margin  < 0:     danger_score += 2
    if danger_score >= 3:
        types.append("⚠️ 困境股")

    if not types:
        types.append("📊 均衡型")
    return types

def score_valuation(pe, pb):
    score = 0
    if pe is not None:
        if   pe < 12:  score += 20
        elif pe < 20:  score += 15
        elif pe < 30:  score += 8
        elif pe < 40:  score += 3
    if pb is not None:
        if   pb < 1.5: score += 10
        elif pb < 3.0: score += 7
        elif pb < 5.0: score += 3
    return score

def score_profitability(roe, gross_margin, revenue_growth):
    score = 0
    if roe is not None:
        if   roe > 0.25: score += 15
        elif roe > 0.15: score += 12
        elif roe > 0.10: score += 7
        elif roe > 0.05: score += 3
    if gross_margin is not None:
        if   gross_margin > 0.50: score += 10
        elif gross_margin > 0.30: score += 7
        elif gross_margin > 0.15: score += 3
    if revenue_growth is not None:
        if   revenue_growth > 0.15: score += 5
        elif revenue_growth > 0.05: score += 3
        elif revenue_growth > 0:    score += 1
    return score

def score_cashflow(fcf, market_cap):
    if fcf is None or market_cap is None or market_cap == 0:
        return 0
    score = 0
    if fcf > 0:
        score += 15
        fcf_yield = fcf / market_cap
        if   fcf_yield > 0.06: score += 10
        elif fcf_yield > 0.03: score += 6
        elif fcf_yield > 0.01: score += 2
    return score

def score_safety(debt_equity):
    if debt_equity is None:
        return 7
    de = debt_equity / 100
    if   de < 0.3: return 15
    elif de < 0.7: return 10
    elif de < 1.2: return 5
    elif de < 2.0: return 2
    else:          return 0

def calculate_score(data):
    v_score  = score_valuation(data.get("pe"), data.get("pb"))
    p_score  = score_profitability(data.get("roe"), data.get("gross_margin"), data.get("revenue_growth"))
    cf_score = score_cashflow(data.get("fcf"), data.get("market_cap"))
    s_score  = score_safety(data.get("debt_equity"))
    total    = v_score + p_score + cf_score + s_score
    types    = classify_stock(data)
    return {
        **data,
        "stock_types_str":     " | ".join(types),
        "score_valuation":     round(v_score,  1),
        "score_profitability": round(p_score,  1),
        "score_cashflow":      round(cf_score, 1),
        "score_safety":        round(s_score,  1),
        "total_score":         round(total,    1),
    }

def grade(score):
    if   score >= 80: return "⭐⭐⭐ 强烈关注"
    elif score >= 65: return "⭐⭐  值得关注"
    elif score >= 50: return "⭐   一般"
    elif score >= 35: return "     偏弱"
    else:             return "❌   回避"

def run_screener(tickers):
    print(f"\n{'='*60}")
    print(f"  基本面筛选器 v2.1 | 共 {len(tickers)} 只股票")
    print(f"{'='*60}\n")
    results = []
    for i, ticker in enumerate(tickers, 1):
        print(f"  [{i:02d}/{len(tickers)}] 获取 {ticker} ...")
        data   = fetch_fundamentals(ticker)
        scored = calculate_score(data)
        results.append(scored)
    df = pd.DataFrame(results)
    df = df.sort_values("total_score", ascending=False).reset_index(drop=True)
    return df

def save_results(df):
    os.makedirs("results", exist_ok=True)
    now       = datetime.now(timezone.utc)
    datestamp = now.strftime("%Y-%m-%d")
    cols = ["ticker","name","sector","industry","stock_types_str",
            "price","total_score","score_valuation","score_profitability",
            "score_cashflow","score_safety","pe","forward_pe","pb","roe",
            "gross_margin","profit_margin","debt_equity","revenue_growth",
            "dividend_yield","beta","market_cap"]
    cols = [c for c in cols if c in df.columns]
    df[cols].to_csv(f"results/screening_{datestamp}.csv", index=False)
    df[cols].to_csv("results/latest.csv", index=False)
    with open("results/latest.md", "w", encoding="utf-8") as f:
        f.write(f"# 📊 基本面筛选结果\n\n更新时间：{now.strftime('%Y-%m-%d %H:%M UTC')}\n\n")
        f.write("| # | 代码 | 名称 | 总分 | 类型 | 评级 |\n|---|------|------|------|------|------|\n")
        for i, row in df.iterrows():
            f.write(f"| {i+1} | {row['ticker']} | {str(row.get('name',''))[:20]} | {row.get('total_score',0):.1f} | {row.get('stock_types_str','N/A')} | {grade(row.get('total_score',0))} |\n")
    print(f"  💾 结果已保存到 results/\n")

if __name__ == "__main__":
    df = run_screener(get_watchlist())
    save_results(df)
