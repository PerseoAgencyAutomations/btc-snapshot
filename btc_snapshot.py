"""Retrato do BTC: ciclo, on-chain, sentimento e rendimento.

Roda sem chave. Fontes públicas:
  Coin Metrics community API  -> preço, MVRV (preço realizado = preço / MVRV), endereços ativos
  alternative.me              -> Fear & Greed
  mempool.space               -> hashrate e próximo ajuste de dificuldade
  DefiLlama yields            -> rendimento de lending de BTC em DeFi
  BCB SGS                     -> Selic meta (432) e dólar PTAX (1)

Uso:
  python3 btc_snapshot.py                     # leitura no terminal
  python3 btc_snapshot.py --html site/index.html   # também gera o dashboard
"""
import argparse
import datetime as dt
import html
import json
import os
import statistics as st
import urllib.request

UA = {"User-Agent": "Mozilla/5.0"}
HALVING_BLOCK = 1_050_000
CLASSE = {"Extreme Fear": "medo extremo", "Fear": "medo", "Neutral": "neutro",
          "Greed": "ganância", "Extreme Greed": "ganância extrema"}


def data_br(iso):
    """2026-11-22 vira 22/11/2026."""
    return "/".join(reversed(str(iso)[:10].split("-")))


def br(v, casas=0):
    """Número no formato brasileiro: 58.851 e 2,40."""
    s = f"{v:,.{casas}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def get(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


# ---------- coleta: cada função devolve um dict, sem imprimir ----------

def ciclo():
    url = ("https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc"
           "&metrics=PriceUSD,CapMVRVCur,AdrActCnt&frequency=1d&start_time=2010-07-18&page_size=10000")
    d = [r for r in get(url, 120)["data"] if r.get("PriceUSD") and r.get("CapMVRVCur")]
    P = [float(r["PriceUSD"]) for r in d]
    M = [float(r["CapMVRVCur"]) for r in d]
    T = [r["time"][:10] for r in d]
    p, mvrv = P[-1], M[-1]
    ath = max(P)
    i_ath = P.index(ath)
    # série semanal (do fim pra trás, a cada 7 dias) pra média de 200 semanas e pro gráfico
    idx = list(range(len(P) - 1, -1, -7))[::-1]
    wk_p = [P[i] for i in idx]
    wk_t = [T[i] for i in idx]
    wk_real = [P[i] / M[i] for i in idx]
    wk_ma = [st.mean(wk_p[j - 199:j + 1]) if j >= 199 else None for j in range(len(wk_p))]
    corte = max(0, len(idx) - 52 * 5)  # últimos 5 anos no gráfico
    return {
        "data": T[-1], "preco": p, "ath": ath, "ath_data": T[i_ath],
        "queda": p / ath - 1,
        "dias_ath": (dt.date.fromisoformat(T[-1]) - dt.date.fromisoformat(T[i_ath])).days,
        "mvrv": mvrv, "realized": p / mvrv, "w200": wk_ma[-1], "mayer": p / st.mean(P[-200:]),
        "retornos": {k: p / P[-1 - k] - 1 for k in (7, 30, 365)},
        "serie": {"datas": wk_t[corte:], "preco": wk_p[corte:],
                  "realized": wk_real[corte:], "ma200w": wk_ma[corte:]},
    }


def sentimento_rede():
    f = get("https://api.alternative.me/fng/?limit=30")["data"]
    h = get("https://mempool.space/api/v1/mining/hashrate/1y")["hashrates"]
    da = get("https://mempool.space/api/v1/difficulty-adjustment")
    altura = da["nextRetargetHeight"] - da["remainingBlocks"]
    return {
        "fng": [{"data": dt.datetime.fromtimestamp(int(x["timestamp"]), dt.timezone.utc).strftime("%Y-%m-%d"),
                 "valor": int(x["value"]), "classe": x["value_classification"]} for x in f][::-1],
        "hash": [{"data": dt.datetime.fromtimestamp(x["timestamp"], dt.timezone.utc).strftime("%Y-%m-%d"),
                  "ehs": x["avgHashrate"] / 1e18} for x in h],
        "altura": altura,
        "dias_halving": (HALVING_BLOCK - altura) * 10 / 60 / 24,
    }


def rendimento_defi():
    pools = get("https://yields.llama.fi/pools", 120)["data"]
    alvo = [x for x in pools if (x["symbol"] or "").upper() in ("WBTC", "CBBTC", "LBTC", "TBTC", "BTCB")
            and (x["tvlUsd"] or 0) > 100e6]
    alvo.sort(key=lambda x: -x["tvlUsd"])
    return [{"projeto": x["project"], "rede": x["chain"], "token": x["symbol"],
             "tvl": x["tvlUsd"], "apy": x["apy"] or 0} for x in alvo[:10]]


def brasil():
    selic = get("https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/1?formato=json")[0]
    usd = get("https://api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados/ultimos/1?formato=json")[0]
    return {"selic": float(selic["valor"]), "ptax": float(usd["valor"]), "ptax_data": usd["data"]}


ETAPAS = {"ciclo": ciclo, "rede": sentimento_rede, "defi": rendimento_defi, "brasil": brasil}


def coletar():
    """Roda cada fonte isolada: uma fora do ar não derruba o resto."""
    dados, erros = {}, {}
    for nome, fn in ETAPAS.items():
        try:
            dados[nome] = fn()
        except Exception as e:
            erros[nome] = f"{type(e).__name__}: {e}"
    return dados, erros


# ---------- saída no terminal ----------

def imprimir(dados, erros):
    if c := dados.get("ciclo"):
        print(f"[Coin Metrics, fecho {c['data']}]")
        print(f"  preço US$ {c['preco']:,.0f} | ATH US$ {c['ath']:,.0f} em {c['ath_data']} | queda {c['queda']:.1%} | {c['dias_ath']} dias desde o ATH")
        print(f"  MVRV {c['mvrv']:.2f} | preço realizado US$ {c['realized']:,.0f} | distância {c['preco'] / c['realized'] - 1:+.1%}")
        print(f"  média 200 semanas US$ {c['w200']:,.0f} ({c['preco'] / c['w200'] - 1:+.1%}) | Mayer (200d) {c['mayer']:.2f}")
        for k, v in c["retornos"].items():
            print(f"  retorno {k}d {v:+.1%}")
    if r := dados.get("rede"):
        f = r["fng"]
        print(f"[alternative.me] Fear & Greed hoje {f[-1]['valor']} ({CLASSE.get(f[-1]['classe'], f[-1]['classe'])}), 7d: {[x['valor'] for x in f[-7:]]}")
        h = [x["ehs"] for x in r["hash"]]
        print(f"[mempool.space] hashrate {h[-1]:,.0f} EH/s | 1 ano atrás {h[0]:,.0f} | pico 1a {max(h):,.0f}")
        print(f"  bloco ~{r['altura']:,} | próximo halving (bloco {HALVING_BLOCK:,}) em ~{r['dias_halving']:,.0f} dias")
    if d := dados.get("defi"):
        print("[DefiLlama] maiores pools de BTC (TVL > US$ 100 mi)")
        for x in d:
            print(f"  {x['projeto']:<16} {x['rede']:<9} {x['token']:<6} TVL US$ {x['tvl'] / 1e6:,.0f} mi | APY {x['apy']:.2f}%")
    if b := dados.get("brasil"):
        print(f"[BCB] Selic meta {b['selic']}% | dólar PTAX R$ {b['ptax']} ({b['ptax_data']})")
    for nome, e in erros.items():
        print(f"[{nome}] falhou: {e}")


# ---------- dashboard HTML (SVG gerado aqui, sem biblioteca) ----------

def svg_linhas(datas, series, w=760, h=280, log=False, fmt=lambda v: f"{v:,.0f}"):
    """series: lista de (rótulo, valores, classe_css). Valores None são pulados."""
    import math
    pad_l, pad_r, pad_t, pad_b = 64, 12, 12, 28
    tr = (lambda v: math.log10(v)) if log else (lambda v: v)
    todos = [tr(v) for _, vals, _ in series for v in vals if v]
    lo, hi = min(todos), max(todos)
    margem = (hi - lo) * 0.05 or 1
    lo, hi = lo - margem, hi + margem
    n = len(datas)
    x = lambda i: pad_l + (w - pad_l - pad_r) * i / max(1, n - 1)
    y = lambda v: pad_t + (h - pad_t - pad_b) * (1 - (tr(v) - lo) / (hi - lo))
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" preserveAspectRatio="none">']
    for k in range(5):  # grade horizontal
        val = lo + (hi - lo) * k / 4
        real = 10 ** val if log else val
        yy = pad_t + (h - pad_t - pad_b) * (1 - k / 4)
        out.append(f'<line class="grid" x1="{pad_l}" x2="{w - pad_r}" y1="{yy:.1f}" y2="{yy:.1f}"/>'
                   f'<text class="axis" x="{pad_l - 8}" y="{yy + 4:.1f}" text-anchor="end">{fmt(real)}</text>')
    anos_vistos = set()
    for i, d in enumerate(datas):  # rótulo por ano
        if d[:4] not in anos_vistos and d[5:7] == "01":
            anos_vistos.add(d[:4])
            out.append(f'<text class="axis" x="{x(i):.1f}" y="{h - 8}" text-anchor="middle">{d[:4]}</text>')
    for _, vals, cls in series:
        pts, seg = [], []
        for i, v in enumerate(vals):
            if v:
                seg.append(f"{x(i):.1f},{y(v):.1f}")
            elif seg:
                pts.append(seg)
                seg = []
        if seg:
            pts.append(seg)
        for s in pts:
            out.append(f'<polyline class="{cls}" points="{" ".join(s)}"/>')
    out.append("</svg>")
    return "".join(out)


def legenda(series):
    return '<div class="legend">' + "".join(
        f'<span><i class="sw {cls}"></i>{html.escape(r)}</span>' for r, _, cls in series) + "</div>"


def kpi(rotulo, valor, nota="", extra=""):
    return (f'<div class="kpi"><div class="k-label">{rotulo}</div><div class="k-value {extra}">{valor}</div>'
            f'<div class="k-note">{nota}</div></div>')


def gerar_html(dados, erros):
    e = html.escape
    agora = dt.datetime.now(dt.timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    blocos = []

    if c := dados.get("ciclo"):
        sinal = lambda v: f'<span class="{"up" if v >= 0 else "down"}">{f"{v:+.1%}".replace(".", ",")}</span>'
        blocos.append('<section class="kpis">' + "".join([
            kpi("Preço", f"US$ {br(c['preco'])}", f"fechamento de {data_br(c['data'])}"),
            kpi("Desde o topo", sinal(c["queda"]), f"topo de US$ {br(c['ath'])} em {data_br(c['ath_data'])}, há {c['dias_ath']} dias"),
            kpi("MVRV", br(c['mvrv'], 2), f"preço realizado US$ {br(c['realized'])}"),
            kpi("Múltiplo de Mayer", br(c['mayer'], 2), "preço / média de 200 dias"),
            kpi("Retornos", " ".join(sinal(v) for v in c["retornos"].values()), "7d · 30d · 365d", "small"),
        ]) + "</section>")
        s = c["serie"]
        series = [("Preço", s["preco"], "l-price"), ("Média de 200 semanas", s["ma200w"], "l-ma"),
                  ("Preço realizado", s["realized"], "l-real")]
        blocos.append('<section class="card"><h2>Ciclo: preço contra o preço realizado e a média de 200 semanas</h2>'
                      f'<p class="sub">Em dólar, semanal, últimos 5 anos, escala log. Fonte: Coin Metrics.</p>{legenda(series)}'
                      f'{svg_linhas(s["datas"], series, log=True, fmt=lambda v: f"{br(v / 1000)} mil")}</section>')

    if r := dados.get("rede"):
        f = r["fng"]
        hoje = f[-1]
        barras = "".join(
            f'<div class="bar" title="{x["data"]}: {x["valor"]}" style="height:{x["valor"]}%"></div>' for x in f)
        hs = r["hash"]
        bruto = [x["ehs"] for x in hs]
        media7 = [st.mean(bruto[max(0, i - 6):i + 1]) for i in range(len(bruto))]  # diário é ruído puro
        hseries = [("Hashrate (EH/s)", media7, "l-price")]
        blocos.append('<section class="duo">'
                      f'<div class="card"><h2>Medo e ganância</h2><p class="sub">Últimos 30 dias. Fonte: alternative.me.</p>'
                      f'<div class="fng"><div class="k-value">{hoje["valor"]}</div><div class="k-note">{e(CLASSE.get(hoje["classe"], hoje["classe"]))}</div></div>'
                      f'<div class="bars">{barras}</div></div>'
                      f'<div class="card"><h2>Rede</h2><p class="sub">Hashrate, média de 7 dias, 1 ano. Fonte: mempool.space.</p>'
                      f'{svg_linhas([x["data"] for x in hs], hseries, w=420, h=180)}'
                      f'<p class="foot">Bloco ~{br(r["altura"])} · próximo halving (bloco {br(HALVING_BLOCK)}) em ~{br(r["dias_halving"])} dias</p></div>'
                      '</section>')

    if d := dados.get("defi"):
        linhas = "".join(f'<tr><td>{e(x["projeto"])}</td><td>{e(x["rede"])}</td><td>{e(x["token"])}</td>'
                         f'<td class="num">US$ {br(x["tvl"] / 1e6)} mi</td><td class="num">{br(x["apy"], 2)}%</td></tr>' for x in d)
        blocos.append('<section class="card"><h2>DeFi: maiores pools de empréstimo em BTC</h2>'
                      '<p class="sub">TVL acima de US$ 100 milhões. Fonte: DefiLlama.</p><div class="scroll"><table>'
                      '<thead><tr><th>Protocolo</th><th>Rede</th><th>Token</th><th class="num">TVL</th><th class="num">APY</th></tr></thead>'
                      f'<tbody>{linhas}</tbody></table></div></section>')

    if b := dados.get("brasil"):
        blocos.append('<section class="kpis">' + kpi("Selic (meta)", f"{br(b['selic'], 2)}%", "Banco Central, SGS 432")
                      + kpi("Dólar (PTAX)", f"R$ {br(b['ptax'], 4)}", f"{e(b['ptax_data'])}, SGS 1") + "</section>")

    for nome, err in erros.items():
        blocos.append(f'<section class="card err"><h2>{e(nome)}: fonte fora do ar</h2><p class="sub">{e(err)}</p></section>')

    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BTC Snapshot</title>
<style>
:root{{--bg:#f6f6f4;--card:#fff;--ink:#16181d;--mute:#6b7079;--line:#e3e3df;--price:#16181d;--ma:#c2410c;--real:#2563eb;--up:#15803d;--down:#b91c1c}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0f1115;--card:#171a20;--ink:#e8e9ec;--mute:#8b909a;--line:#262a33;--price:#e8e9ec;--ma:#fb923c;--real:#60a5fa;--up:#4ade80;--down:#f87171}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}}
main{{max-width:1080px;margin:0 auto;padding:32px 16px 48px}}
header h1{{margin:0;font-size:26px;letter-spacing:-.01em}}header p{{margin:4px 0 24px;color:var(--mute)}}
h2{{font-size:15px;margin:0}}.sub{{margin:2px 0 12px;color:var(--mute);font-size:13px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px;margin-bottom:16px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:16px}}
.kpi{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}}
.k-label{{font-size:12px;color:var(--mute)}}.k-value{{font-size:24px;font-weight:600;font-variant-numeric:tabular-nums;margin:2px 0}}
.k-value.small{{font-size:17px;padding-top:5px}}.k-note{{font-size:12px;color:var(--mute)}}.up{{color:var(--up)}}.down{{color:var(--down)}}
.duo{{display:grid;grid-template-columns:1fr 1.4fr;gap:16px}}.duo .card{{margin-bottom:16px}}
@media (max-width:720px){{.duo{{grid-template-columns:1fr}}}}
svg{{width:100%;height:auto;display:block}}polyline{{fill:none;stroke-width:1.6;stroke-linejoin:round}}
.l-price{{stroke:var(--price)}}.l-ma{{stroke:var(--ma)}}.l-real{{stroke:var(--real)}}
.grid{{stroke:var(--line);stroke-width:1}}.axis{{fill:var(--mute);font-size:11px}}
.legend{{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;color:var(--mute);margin-bottom:6px}}
.sw{{display:inline-block;width:14px;height:2px;vertical-align:middle;margin-right:6px}}
.sw.l-price{{background:var(--price)}}.sw.l-ma{{background:var(--ma)}}.sw.l-real{{background:var(--real)}}
.bars{{display:flex;align-items:flex-end;gap:2px;height:90px;margin-top:12px;border-bottom:1px solid var(--line)}}
.bar{{flex:1;background:var(--mute);opacity:.55;border-radius:2px 2px 0 0}}.bar:last-child{{opacity:1;background:var(--ink)}}
.foot{{margin:10px 0 0;font-size:13px;color:var(--mute)}}
.scroll{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;font-size:14px}}
th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);white-space:nowrap}}th{{font-size:12px;color:var(--mute);font-weight:500}}
.num{{text-align:right;font-variant-numeric:tabular-nums}}.err h2{{color:var(--down)}}
footer{{color:var(--mute);font-size:12px;margin-top:8px}}
</style></head><body><main>
<header><h1>BTC Snapshot</h1><p>Ciclo, on-chain, sentimento e rendimento, de APIs públicas. Atualizado em {agora}.</p></header>
{"".join(blocos)}
<footer>Gerado pelo btc_snapshot.py, só com a biblioteca padrão do Python, e atualizado todo dia pelo GitHub Actions. É leitura de dados, não recomendação de investimento.</footer>
</main></body></html>"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--html", metavar="ARQUIVO", help="também grava o dashboard HTML nesse caminho")
    a = ap.parse_args()
    dados, erros = coletar()
    imprimir(dados, erros)
    if a.html:
        os.makedirs(os.path.dirname(a.html) or ".", exist_ok=True)
        with open(a.html, "w", encoding="utf-8") as fh:
            fh.write(gerar_html(dados, erros))
        print(f"dashboard: {a.html}")
