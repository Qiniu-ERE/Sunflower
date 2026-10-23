"""太阳花两种型号的成本、渠道费用、软件费率与 ROI。

    python3 docs/business/cost_model.py           # 打印 README 里的全部表格
    python3 docs/business/cost_model.py --write   # 把表格写回 README.md 的标记区间

只读同目录的 CSV：bom.csv（零件）、rates.csv（汇率 / 渠道 / 软件 / 定价参数）、nre.csv（一次性投入）、
codex_usage.csv（本机实跑的 Codex 用量）、competitors.csv（亚马逊竞品）。改数字只改 CSV，再跑 --write。
"""
import csv
import pathlib
import statistics
import sys

HERE = pathlib.Path(__file__).resolve().parent
VARIANTS = ("标准版", "屏显版")
BEGIN, END = "<!-- cost_model:begin -->", "<!-- cost_model:end -->"


def read(name):
    with open(HERE / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def rates():
    return {r["key"]: float(r["value"]) for r in read("rates.csv")}


def usd(row, col, r):
    v = float(row[col]) * float(row["qty"])
    return v * {"USD": 1.0, "AUD": r["usd_per_aud"], "CNY": 1 / r["cny_per_usd"]}[row["currency"]]


def bom(r):
    """每个型号：{(列, 类别): 金额}，列 = unit_1 / unit_1k，类别 = 报价 / 假设。"""
    out = {v: {} for v in VARIANTS}
    for row in read("bom.csv"):
        for v in VARIANTS:
            if row["variant"] in ("共用", v):
                for col in ("unit_1", "unit_1k"):
                    k = (col, row["kind"])
                    out[v][k] = out[v].get(k, 0.0) + usd(row, col, r)
    return out


def total(b, col):
    return sum(x for (c, _), x in b.items() if c == col)


def codex_task_cost(r):
    """单次任务的 Codex 费用（USD，取本机实测的中位数任务）。"""
    rows = read("codex_usage.csv")
    costs = []
    for u in rows:
        cached, inp, out = int(u["cached_input_tokens"]), int(u["input_tokens"]), int(u["output_tokens"])
        costs.append(((inp - cached) * r["codex_in_per_m"] + cached * r["codex_cached_per_m"]
                      + out * r["codex_out_per_m"]) / 1e6)
    return statistics.median(costs), len(rows)


def voice_month(r):
    """单台每月语音服务费用（USD）：按语音分钟计。"""
    minutes = r["tasks_per_day"] * r["workdays_per_month"] * r["voice_min_per_task"]
    return minutes * r["voice_cny_per_min"] / r["cny_per_usd"], minutes


def unit_economics(r, b):
    out = {}
    voice, _ = voice_month(r)
    for v in VARIANTS:
        price = r[f"price_{'standard' if v == '标准版' else 'screen'}"]
        landed = total(b[v], "unit_1k") * (1 + r["landed_share"])
        fees = {
            "亚马逊佣金": price * r["amazon_referral"],
            "FBA 配送": r["fba_fee"] * (1 + r["fba_surcharge"]),
            "广告": price * r["ads_share"],
            "退货与售后": price * r["returns_share"],
            "随机附赠语音服务": voice * r["bundled_voice_months"],
        }
        contrib = price - landed - sum(fees.values())
        out[v] = {"price": price, "landed": landed, "fees": fees, "contrib": contrib}
    return out


def breakeven_price(r, u):
    """贡献为 0 的售价：按售价提成的费用随价走，其余是固定额。"""
    fixed = u["landed"] + u["fees"]["FBA 配送"] + u["fees"]["随机附赠语音服务"]
    return fixed / (1 - r["amazon_referral"] - r["ads_share"] - r["returns_share"])


def top_parts(r, n):
    rows = [row for row in read("bom.csv") if row["variant"] == "共用"]
    return sorted(rows, key=lambda row: -usd(row, "unit_1k", r))[:n]


def nre():
    rows = read("nre.csv")
    by = {v: 0.0 for v in VARIANTS}
    for row in rows:
        for v in VARIANTS:
            if row["variant"] in ("共用", v):
                by[v] += float(row["usd"])
    return rows, by


def money(x):
    return f"{x:,.2f}" if abs(x) < 1000 else f"{x:,.0f}"


def pct(x):
    return f"{x * 100:.0f}%"


def tables():
    r = rates()
    b = bom(r)
    ue = unit_economics(r, b)
    nre_rows, nre_by = nre()
    voice, _ = voice_month(r)
    be = {v: breakeven_price(r, ue[v]) for v in VARIANTS}
    L = ["### 结论", "",
         f"- 按现有报价（1k 档缺价的零件按小批量价计），两种型号在建议售价 "
         f"{money(ue['标准版']['price'])} / {money(ue['屏显版']['price'])} USD 下单台贡献为 "
         f"{money(ue['标准版']['contrib'])} / {money(ue['屏显版']['contrib'])} USD，"
         f"盈亏平衡售价是 {money(be['标准版'])} / {money(be['屏显版'])} USD。",
         f"- 屏显版售价比标准版高 {money(ue['屏显版']['price'] - ue['标准版']['price'])} USD，"
         f"落地成本只高 {money(ue['屏显版']['landed'] - ue['标准版']['landed'])} USD。",
         "- 降本先看下面最贵的几项：它们大多只有零售价或小批量价，拿到量产报价前，成本是上界。",
         f"- 软件侧每位用户每月语音服务成本 {money(voice)} USD，订阅价 {money(r['subscription_usd'])} USD；"
         "Codex 的费用由用户自己的账号承担，不进设备成本。", ""]

    L += ["### 硬件 BOM（USD / 台）", "",
          "| | 标准版 打样 1 台 | 标准版 量产 1k | 屏显版 打样 1 台 | 屏显版 量产 1k |", "|---|---:|---:|---:|---:|"]
    for kind in ("报价", "假设"):
        cells = [money(b[v].get((c, kind), 0.0)) for v in VARIANTS for c in ("unit_1", "unit_1k")]
        L.append(f"| {kind}件 | " + " | ".join(cells) + " |")
    cells = [f"**{money(total(b[v], c))}**" for v in VARIANTS for c in ("unit_1", "unit_1k")]
    L += ["| 合计 | " + " | ".join(cells) + " |", ""]
    share = {v: b[v].get(("unit_1k", "报价"), 0) / total(b[v], "unit_1k") for v in VARIANTS}
    L += [f"量产 1k 的金额里，有报价的零件占 标准版 {pct(share['标准版'])} / 屏显版 {pct(share['屏显版'])}；"
          "1k 档没查到的零件按更小批量的价格计，所以是上界。", ""]

    L += ["### 单台经济（亚马逊美国站，USD）", "", "| | 标准版 | 屏显版 |", "|---|---:|---:|",
          "| 建议售价 | " + " | ".join(money(ue[v]["price"]) for v in VARIANTS) + " |",
          f"| 落地成本（BOM × {1 + r['landed_share']:.2f}，含头程、关税） | "
          + " | ".join(money(ue[v]["landed"]) for v in VARIANTS) + " |"]
    for k in ue["标准版"]["fees"]:
        L.append(f"| {k} | " + " | ".join(money(ue[v]["fees"][k]) for v in VARIANTS) + " |")
    L += ["| **单台贡献** | " + " | ".join(f"**{money(ue[v]['contrib'])}**" for v in VARIANTS) + " |",
          "| 贡献率 | " + " | ".join(pct(ue[v]["contrib"] / ue[v]["price"]) for v in VARIANTS) + " |",
          "| 盈亏平衡售价 | " + " | ".join(money(breakeven_price(r, ue[v])) for v in VARIANTS) + " |", ""]
    keep = 1 - r["amazon_referral"] - r["ads_share"] - r["returns_share"]
    L += [f"按售价提成的费用合计 {pct(1 - keep)}，所以 BOM 每降 10 USD，盈亏平衡售价降 "
          f"{10 * (1 + r['landed_share']) / keep:.1f} USD。量产 1k 时最贵的五项（两型号共用，USD / 台）：", "",
          "| 零件 | 1k 价 | 说明 |", "|---|---:|---|"]
    for row in top_parts(r, 5):
        L.append(f"| {row['part']} | {money(usd(row, 'unit_1k', r))} | {row['note'] or row['kind']} |")
    L.append("")

    L += ["### 一次性投入（NRE）与 ROI", "", "| 项目 | 适用 | USD | 依据 |", "|---|---|---:|---|"]
    for row in nre_rows:
        L.append(f"| {row['item']} | {row['variant']} | {money(float(row['usd']))} | {row['basis']} |")
    L += ["", "| | 标准版 | 屏显版 |", "|---|---:|---:|",
          "| NRE 合计 | " + " | ".join(money(nre_by[v]) for v in VARIANTS) + " |",
          "| 回本台数（NRE ÷ 单台贡献） | "
          + " | ".join(f"{nre_by[v] / ue[v]['contrib']:,.0f}" if ue[v]["contrib"] > 0 else "不回本"
                      for v in VARIANTS) + " |"]
    for n in (1000, 3000, 10000):
        cells = []
        for v in VARIANTS:
            invest = nre_by[v] + n * ue[v]["landed"]
            cells.append(pct((n * ue[v]["contrib"] - nre_by[v]) / invest))
        L.append(f"| 卖出 {n:,} 台的 ROI（净利 ÷ NRE 与备货） | " + " | ".join(cells) + " |")
    L.append("")

    task, n = codex_task_cost(r)
    voice, minutes = voice_month(r)
    codex_month = task * r["tasks_per_day"] * r["workdays_per_month"]
    L += ["### 软件费用（每位用户每月）", "", "| 项目 | 用量 | USD / 月 | 谁付 |", "|---|---|---:|---|",
          f"| 语音服务 | {minutes:,.0f} 分钟（{r['tasks_per_day']:.0f} 次/天 × {r['workdays_per_month']:.0f} 天 × "
          f"{r['voice_min_per_task']} 分钟/次） | {money(voice)} | 随机附赠 {r['bundled_voice_months']:.0f} 个月，之后订阅 |",
          f"| Codex | 单次任务 {money(task)}（本机实测 {n} 次的中位数）× 同样次数 | {money(codex_month)} | "
          "用户自己的 Codex 账号 / API Key |",
          f"| 订阅价 | | {money(r['subscription_usd'])} | 毛利 {pct(1 - voice / r['subscription_usd'])} |", ""]

    comps = sorted(read("competitors.csv"), key=lambda c: float(c["price_usd"]))
    ours = [{"product": f"**太阳花 {v}**", "price_usd": ue[v]["price"], "group": "本仓", "rating": "", "reviews": "",
             "asin": "", "note": ""} for v in VARIANTS]
    allp = sorted(comps + ours, key=lambda c: float(c["price_usd"]))
    L += ["### 亚马逊竞品价格", "", "| 产品 | 类别 | 售价 USD | 评分（评论数） |", "|---|---|---:|---|"]
    for c in allp:
        rating = f"{c['rating']}（{int(c['reviews']):,}）" if c["rating"] else ""
        name = c["product"] if not c["asin"] else f"[{c['product']}](https://www.amazon.com/dp/{c['asin']})"
        L.append(f"| {name} | {c['group']} | {money(float(c['price_usd']))} | {rating} |")
    return "\n".join(L)


def write_readme(body):
    p = HERE / "README.md"
    text = p.read_text(encoding="utf-8")
    head, rest = text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    p.write_text(f"{head}{BEGIN}\n{body}\n{END}{tail}", encoding="utf-8")


if __name__ == "__main__":
    out = tables()
    if "--write" in sys.argv:
        write_readme(out)
    else:
        print(out)
