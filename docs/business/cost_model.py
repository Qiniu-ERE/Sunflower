"""太阳花两种型号的成本、渠道费用、软件费率与 ROI。

    python3 docs/business/cost_model.py           # 打印 README 里的全部表格
    python3 docs/business/cost_model.py --write   # 写回本目录 README.md 和根 README 的标记区间

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
SUMMARY = ("<!-- cost_summary:begin -->", "<!-- cost_summary:end -->")  # 根 README 的摘要区
COLS = ("unit_1", "unit_1k", "cn_1k")
SCENARIOS = {"unit_1k": "海外报价", "cn_1k": "国内采购"}
FEATURES = ("screen", "turns", "coding_agent", "sdk")
OURS = {"标准版": {"screen": "1.28″ 圆屏（表情）", "turns": "是（4 麦 DOA + 云台电机）", "coding_agent": "是（Codex，可换）",
                "sdk": "本仓 MIT 开源"},
        "屏显版": {"screen": "2.1″ 圆屏（表情 + 进展回显）", "turns": "是（4 麦 DOA + 云台电机）",
                "coding_agent": "是（Codex，可换）", "sdk": "本仓 MIT 开源"}}


def read(name):
    with open(HERE / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def rates():
    return {r["key"]: float(r["value"]) for r in read("rates.csv")}


def usd(row, col, r):
    if col == "cn_1k":  # 国内采购：有国内报价的用国内价（CNY），没有的沿用海外 1k 价
        if not row["cn_1k"]:
            return usd(row, "unit_1k", r)
        return float(row["cn_1k"]) * float(row["qty"]) / r["cny_per_usd"]
    v = float(row[col]) * float(row["qty"])
    return v * {"USD": 1.0, "AUD": r["usd_per_aud"], "CNY": 1 / r["cny_per_usd"]}[row["currency"]]


def bom(r):
    """每个型号：{(列, 类别): 金额}，列 = unit_1 / unit_1k / cn_1k，类别 = 报价 / 假设。"""
    out = {v: {} for v in VARIANTS}
    for row in read("bom.csv"):
        for v in VARIANTS:
            if row["variant"] in ("共用", v):
                for col in COLS:
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


def channels(r, voice):
    """每个渠道：售价参数名、按售价提成的费用（比例）、每台固定费用（USD）。"""
    bundled = voice * r["bundled_voice_months"]
    return {
        "亚马逊": {"price": "price_{}",
                 "share": {"亚马逊佣金": r["amazon_referral"], "广告": r["ads_share"], "退货与售后": r["returns_share"]},
                 "fixed": {"FBA 配送": r["fba_fee"] * (1 + r["fba_surcharge"]), "随机附赠语音服务": bundled}},
        "众筹": {"price": "cf_price_{}",
                "share": {"平台费": r["cf_platform"], "支付处理": r["cf_payment"], "众筹投放": r["cf_ads_share"],
                          "售后备件": r["cf_warranty_share"]},
                "fixed": {"支付单笔费": r["cf_payment_fixed"], "直发支持者运费": r["cf_ship"], "随机附赠语音服务": bundled}},
    }


def unit_economics(r, b, col="unit_1k"):
    """{(型号, 渠道): 单台账}。落地成本两个渠道相同：BOM ×（1 + 头程与关税）；col 选采购场景。"""
    voice, _ = voice_month(r)
    out = {}
    for v in VARIANTS:
        landed = total(b[v], col) * (1 + r["landed_share"])
        for ch, c in channels(r, voice).items():
            price = r[c["price"].format("standard" if v == "标准版" else "screen")]
            fees = {k: price * x for k, x in c["share"].items()} | dict(c["fixed"])
            share, fixed = sum(c["share"].values()), sum(c["fixed"].values())
            out[v, ch] = {"price": price, "landed": landed, "fees": fees, "share": share, "fixed": fixed,
                          "contrib": price - landed - sum(fees.values()),
                          "breakeven": (landed + fixed) / (1 - share)}
    return out


def breakeven_table(r, b):
    sc = {col: unit_economics(r, b, col) for col in SCENARIOS}
    head = " | ".join(f"{name}：落地成本 | {name}：盈亏平衡价" for name in SCENARIOS.values())
    L = [f"| 型号 · 渠道 | 售价 | {head} |", "|---|---:|" + "---:|" * (2 * len(SCENARIOS))]
    for key, u in sc["unit_1k"].items():
        v, ch = key
        label = "建议售价" if ch == "亚马逊" else "早鸟价"
        cells = " | ".join(f"{money(sc[c][key]['landed'])} | **{money(sc[c][key]['breakeven'])}**" for c in SCENARIOS)
        L.append(f"| {v} · {ch}（{label}） | {money(u['price'])} | {cells} |")
    L += ["", f"落地成本 = 量产 1k 的 BOM ×（1 + {pct(r['landed_share'])} 头程与关税）；盈亏平衡价 ="
          "（落地成本 + 每台固定费用）÷（1 − 按售价提成的费用比例）。国内采购只替换查到了国内报价的零件，其余沿用海外报价。"]
    return "\n".join(L)


def precedents():
    return sorted(read("precedents.csv"), key=lambda p: int(p["backers"]))


def backers_line(r, b):
    """按早鸟价收回 NRE 要多少支持者，和 Kickstarter 先例并列。"""
    ue = unit_economics(r, b)
    shells = shell_options(r, ue, *nre())
    cf = {v: ue[v, "众筹"] for v in VARIANTS}

    def need(way):
        ns = [backers(*shells[v, way][:2]) for v in VARIANTS]
        return " / ".join(f"{n:,.0f}" if n else "无法回本" for n in ns)
    return (f"按早鸟价 {money(cf['标准版']['price'])} / {money(cf['屏显版']['price'])} USD，开模方案要 "
            f"{need('开模注塑')} 名支持者才收回 NRE；自己 FDM 打印 + 自己组装要 {need('自己 FDM 打印 + 自己组装')} 名。"
            "Kickstarter 上同类先例的支持者数："
            + "、".join(f"{p['project'].split('（')[0]} {int(p['backers']):,}" for p in precedents()) + "。")


def summary():
    r = rates()
    b = bom(r)
    return breakeven_table(r, b) + "\n\n" + backers_line(r, b)


def price_for(u, nre_usd, n):
    """卖 n 台刚好收回 NRE 的单价。"""
    return (u["landed"] + u["fixed"] + nre_usd / n) / (1 - u["share"])


SHELL_ID, LABOR_ID = "14", "17"  # bom.csv 里外壳塑件、组装人工两行


def shell_options(r, ue, nre_rows, nre_by):
    """外壳三种做法下的众筹单台账：{(型号, 做法): (单台账, NRE)}。开模用 1k 注塑价，外包打印用单台 MJF 价。"""
    rows = {row["id"]: row for row in read("bom.csv")}
    injected, mjf = float(rows[SHELL_ID]["unit_1k"]), float(rows[SHELL_ID]["unit_1"])
    labor = float(rows[LABOR_ID]["unit_1k"])
    ways = {"开模注塑": (0.0, True), "外包 3D 打印（MJF）": (mjf - injected, False),
            "自己 FDM 打印 + 自己组装": (r["fdm_shell_usd"] - injected - labor, False)}
    out = {}
    for v in VARIANTS:
        mold = sum(float(row["usd"]) for row in nre_rows if row["kind"] == "模具" and row["variant"] in ("共用", v))
        for way, (delta, molded) in ways.items():
            u = dict(ue[v, "众筹"])
            u["landed"] += delta * (1 + r["landed_share"])
            u["contrib"] = u["price"] * (1 - u["share"]) - u["landed"] - u["fixed"]
            out[v, way] = (u, nre_by[v] - (0 if molded else mold), delta, mold)
    return out


def backers(u, nre_usd):
    return nre_usd / u["contrib"] if u["contrib"] > 0 else None


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
    chs = list(channels(r, voice))
    keys = [(v, ch) for v in VARIANTS for ch in chs]
    cf = {v: ue[v, "众筹"] for v in VARIANTS}
    cn = unit_economics(r, b, "cn_1k")
    shells = shell_options(r, ue, nre_rows, nre_by)
    precs = precedents()

    L = ["### 结论", "",
         f"- 按现有报价（1k 档缺价的零件按小批量价计），两种型号在亚马逊建议售价 "
         f"{money(ue['标准版', '亚马逊']['price'])} / {money(ue['屏显版', '亚马逊']['price'])} USD 下单台贡献 "
         f"{money(ue['标准版', '亚马逊']['contrib'])} / {money(ue['屏显版', '亚马逊']['contrib'])} USD，"
         f"盈亏平衡售价 {money(ue['标准版', '亚马逊']['breakeven'])} / {money(ue['屏显版', '亚马逊']['breakeven'])} USD。",
         f"- 众筹按筹款额提成的费用合计 {pct(cf['标准版']['share'])}（平台、支付、投放、售后），亚马逊是 "
         f"{pct(ue['标准版', '亚马逊']['share'])}；众筹的盈亏平衡价 {money(cf['标准版']['breakeven'])} / "
         f"{money(cf['屏显版']['breakeven'])} USD，"
         + ("比亚马逊高" if cf["标准版"]["breakeven"] > ue["标准版", "亚马逊"]["breakeven"] else "比亚马逊低")
         + "。众筹的价值在资金流：支持者先付款，NRE 和首批备货不用先垫，也顺带验证需求。",
         "- " + backers_line(r, b),
         "- 早鸟价比亚马逊售价低 " + " / ".join(pct(1 - cf[v]["price"] / ue[v, "亚马逊"]["price"]) for v in VARIANTS)
         + "，先例的早鸟折扣在 " + "–".join(pct(f(1 - float(p["early_bird_usd"]) / float(p["retail_usd"]) for p in precs))
                                     for f in (min, max))
         + "：早鸟价不能低于众筹盈亏平衡价，折扣只能给得比先例小。",
         f"- 屏显版售价比标准版高 {money(ue['屏显版', '亚马逊']['price'] - ue['标准版', '亚马逊']['price'])} USD，"
         f"落地成本只高 {money(ue['屏显版', '亚马逊']['landed'] - ue['标准版', '亚马逊']['landed'])} USD。",
         f"- 把查到国内价的 {sum(1 for row in read('bom.csv') if row['cn_1k'])} 项换成国内价后，亚马逊盈亏平衡价是 {money(cn['标准版', '亚马逊']['breakeven'])} / "
         f"{money(cn['屏显版', '亚马逊']['breakeven'])} USD；没查到国内价的零件仍按海外价计。",
         f"- 软件侧每位用户每月语音服务成本 {money(voice)} USD，订阅价 {money(r['subscription_usd'])} USD；"
         "Codex 的费用由用户自己的账号承担，不进设备成本。", ""]

    L += ["### 成本与盈亏平衡（USD / 台）", "", breakeven_table(r, b), ""]

    L += ["### 硬件 BOM（USD / 台）", "",
          "| | " + " | ".join(f"{v} {n}" for v in VARIANTS for n in ("打样 1 台", "1k 海外报价", "1k 国内采购")) + " |",
          "|---|" + "---:|" * (len(VARIANTS) * len(COLS))]
    for kind in ("报价", "假设"):
        cells = [money(b[v].get((c, kind), 0.0)) for v in VARIANTS for c in COLS]
        L.append(f"| {kind}件 | " + " | ".join(cells) + " |")
    cells = [f"**{money(total(b[v], c))}**" for v in VARIANTS for c in COLS]
    L += ["| 合计 | " + " | ".join(cells) + " |", ""]
    share = {v: b[v].get(("unit_1k", "报价"), 0) / total(b[v], "unit_1k") for v in VARIANTS}
    L += [f"量产 1k 的金额里，有报价的零件占 标准版 {pct(share['标准版'])} / 屏显版 {pct(share['屏显版'])}；"
          "1k 档没查到的零件按更小批量的价格计，所以是上界。量产 1k 时最贵的五项（两型号共用）：", "",
          "| 零件 | 1k 价 | 说明 |", "|---|---:|---|"]
    for row in top_parts(r, 5):
        L.append(f"| {row['part']} | {money(usd(row, 'unit_1k', r))} | {row['note'] or row['kind']} |")
    L += ["", "国内采购场景替换的零件（其余零件国内价没查到，沿用海外报价）：", "",
          "| 零件 | 海外 1k 价 | 国内价 | 国内价 USD | 档位与说明 |", "|---|---:|---:|---:|---|"]
    for row in read("bom.csv"):
        if row["cn_1k"]:
            L.append(f"| {row['part']} ×{row['qty']} | {money(usd(row, 'unit_1k', r))} | "
                     f"[{row['cn_1k']} 元/个]({row['cn_source']}) | {money(usd(row, 'cn_1k', r))} | {row['cn_note']} |")
    L.append("")

    L += ["### 单台账（USD）", "", "| | " + " | ".join(f"{v} · {ch}" for v, ch in keys) + " |",
          "|---|" + "---:|" * len(keys), "| 售价 | " + " | ".join(money(ue[k]["price"]) for k in keys) + " |",
          "| 落地成本 | " + " | ".join(money(ue[k]["landed"]) for k in keys) + " |"]
    names = list(dict.fromkeys(n for k in keys for n in ue[k]["fees"]))
    for name in names:
        L.append(f"| {name} | " + " | ".join(money(ue[k]["fees"][name]) if name in ue[k]["fees"] else "—"
                                             for k in keys) + " |")
    L += ["| **单台贡献** | " + " | ".join(f"**{money(ue[k]['contrib'])}**" for k in keys) + " |",
          "| 贡献率 | " + " | ".join(pct(ue[k]["contrib"] / ue[k]["price"]) for k in keys) + " |", ""]

    L += ["### 一次性投入（NRE）", "", "| 项目 | 适用 | USD | 依据 |", "|---|---|---:|---|"]
    for row in nre_rows:
        L.append(f"| {row['item']} | {row['variant']} | {money(float(row['usd']))} | {row['basis']} |")
    L += ["", f"NRE 合计：标准版 {money(nre_by['标准版'])} USD，屏显版 {money(nre_by['屏显版'])} USD。", ""]

    L += ["### 小批量：外壳做法与众筹回本", "",
          "回本单价 = 卖 n 台刚好收回 NRE 的众筹单价（含全部众筹费用与随机附赠语音服务）。"
          "不开模就省掉模具费，但每台外壳更贵；自己组装省掉组装人工。零件仍按 1k 价计，台数少时实际更贵。", "",
          "| 型号 · 外壳做法 | NRE | 落地成本 | 回本单价 300 台 | 1,000 台 | 3,000 台 | 按早鸟价回本需要的支持者 |",
          "|---|---:|---:|---:|---:|---:|---:|"]
    for (v, way), (u, n_usd, _, _) in shells.items():
        n_back = backers(u, n_usd)
        L.append(f"| {v} · {way} | {money(n_usd)} | {money(u['landed'])} | "
                 + " | ".join(money(price_for(u, n_usd, n)) for n in (300, 1000, 3000))
                 + f" | {f'{n_back:,.0f} 人' if n_back else '早鸟价低于单台成本'} |")
    cross = []
    for v in VARIANTS:
        for way in list(dict.fromkeys(w for _, w in shells))[1:]:
            _, _, delta, mold = shells[v, way]
            n = mold / (delta * (1 + r["landed_share"])) if delta > 0 else None
            cross.append(f"{v} · {way}：{f'{n:,.0f} 台' if n else '任何台数'}")
    L += ["", "不开模比开模便宜的台数上限（模具费 ÷ 每台多出的外壳落地成本）：" + "；".join(cross)
          + "。自己打印的单价只算材料，没算打印机和机时。", ""]

    L += ["### 众筹先例（Kickstarter）", "", "| 项目 | 年份 | 支持者 | 筹款额 | 早鸟价 | 零售价 | 早鸟折扣 | 说明 |",
          "|---|---|---:|---|---:|---:|---:|---|"]
    for p in precs:
        eb, rt = float(p["early_bird_usd"]), float(p["retail_usd"])
        L.append(f"| [{p['project']}]({p['source']}) | {p['year']} | {int(p['backers']):,} | {p['raised']} | "
                 f"{money(eb)} | {money(rt)} | {pct(1 - eb / rt)} | {p['note']} |")
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

    comps = read("competitors.csv")
    ours = [{"product": f"**太阳花 {v}**", "price_usd": ue[v, "亚马逊"]["price"], "group": "本仓", "rating": "",
             "reviews": "", "asin": "", **OURS[v]} for v in VARIANTS]
    allp = sorted(comps + ours, key=lambda c: float(c["price_usd"]))
    L += ["### 亚马逊竞品：价格与功能差异", "",
          "| 产品 | 类别 | 售价 USD | 评分（评论数） | 屏幕 | 听声转向 | 语音驱动 code agent | 开放平台 |",
          "|---|---|---:|---|---|---|---|---|"]
    for c in allp:
        rating = f"{c['rating']}（{int(c['reviews']):,}）" if c["rating"] else ""
        name = c["product"] if not c["asin"] else f"[{c['product']}](https://www.amazon.com/dp/{c['asin']})"
        feats = " | ".join(c.get(k) or "未查到" for k in FEATURES)
        L.append(f"| {name} | {c['group']} | {money(float(c['price_usd']))} | {rating} | {feats} |")
    return "\n".join(L)


def splice(path, markers, body):
    text = path.read_text(encoding="utf-8")
    head, rest = text.split(markers[0], 1)
    _, tail = rest.split(markers[1], 1)
    path.write_text(f"{head}{markers[0]}\n{body}\n{markers[1]}{tail}", encoding="utf-8")


def block(path, markers):
    return path.read_text(encoding="utf-8").split(markers[0], 1)[1].split(markers[1], 1)[0].strip()


if __name__ == "__main__":
    out = tables()
    if "--write" in sys.argv:
        splice(HERE / "README.md", (BEGIN, END), out)
        splice(HERE.parent.parent / "README.md", SUMMARY, summary())
    else:
        print(out)
