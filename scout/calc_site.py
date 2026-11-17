"""제품 #2 — '이 가격 적정한가' 계산기.

기준값은 실제 체결가에서만 뽑는다. 계산은 브라우저에서 하므로 서버가 없다.
파일 하나라 어디든 무료로 올라간다.

표본이 얇은 구간은 숨기지 않고 '표본 부족'으로 표시한다.
근거 없는 숫자를 근거처럼 보여주는 게 데이터 사이트가 죽는 가장 빠른 길이다.
"""
import html
import json
from datetime import datetime, timezone
from pathlib import Path

from . import valuation

OUT = Path(__file__).resolve().parent.parent / "site" / "worth" / "index.html"


def _json_for_script(obj) -> str:
    """<script type="application/json"> 안에 안전하게 넣는다.

    HTML 이스케이프를 하면 안 된다 — 그 안에서는 브라우저가 엔티티를
    풀어주지 않아 JSON.parse 가 깨진다(실제로 깨졌다).
    막아야 할 건 스크립트 태그 탈출뿐이다.
    """
    return (json.dumps(obj, ensure_ascii=False)
            .replace("</", "<\\/")
            .replace("<!--", "<\\u0021--"))


def render(conn) -> str:
    data = valuation.payload(conn)
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    rows = ""
    for b in data["bands"]:
        mult = f'{b["median_multiple"]}&times;' if b["median_multiple"] else "&mdash;"
        rng = (f'{b["p25_multiple"]}&ndash;{b["p75_multiple"]}&times;'
               if b["p25_multiple"] and b["p75_multiple"] else "&mdash;")
        price = f'${b["median_price"]:,}' if b["median_price"] else "&mdash;"
        flag = "" if b["confident"] else '<span class="thin">thin sample</span>'
        rows += (f'<tr><td>{html.escape(b["label"])} {flag}</td>'
                 f'<td class="n">{b["n"]}</td><td class="n">{price}</td>'
                 f'<td class="n">{mult}</td><td class="n">{rng}</td></tr>')

    return TEMPLATE.format(
        updated=updated,
        total=data["total_deals"],
        rows=rows,
        payload=_json_for_script(data),
    )


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>What Is My Software Business Worth?</title>
<meta name="description" content="Price your software business against {total} real sale prices — what buyers actually paid, not what sellers asked.">
<style>
  :root {{
    --bg:#fbfaf8; --fg:#1a1a18; --muted:#6c6a66; --line:#e4e1db;
    --accent:#1d5c48; --card:#fff; --warn:#8a5a1c;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --bg:#14141a; --fg:#eceaf0; --muted:#9b98a6; --line:#2c2c36;
      --accent:#6fd8ac; --card:#1c1c24; --warn:#e0b070;
    }}
  }}
  :root[data-theme="dark"] {{
    --bg:#14141a; --fg:#eceaf0; --muted:#9b98a6; --line:#2c2c36;
    --accent:#6fd8ac; --card:#1c1c24; --warn:#e0b070;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--fg);
    font:16px/1.6 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; }}
  .wrap {{ max-width:720px; margin:0 auto; padding:48px 16px 80px; }}
  h1 {{ font-size:clamp(28px,5vw,42px); line-height:1.15; margin:0 0 12px; letter-spacing:-.02em; }}
  .lede {{ color:var(--muted); font-size:18px; margin:0 0 32px; }}
  form {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
    padding:22px; margin:0 0 24px; }}
  label {{ display:block; font-size:14px; font-weight:600; margin:0 0 6px; }}
  .hint {{ font-weight:400; color:var(--muted); }}
  input {{ width:100%; font:inherit; padding:11px 13px; border-radius:8px;
    border:1px solid var(--line); background:var(--bg); color:var(--fg); }}
  input:focus {{ outline:2px solid var(--accent); outline-offset:1px; }}
  .field + .field {{ margin-top:16px; }}
  #out {{ margin-top:20px; padding-top:20px; border-top:1px solid var(--line); display:none; }}
  #out.show {{ display:block; }}
  .big {{ font-size:30px; font-weight:700; letter-spacing:-.02em; }}
  .sub {{ color:var(--muted); font-size:14px; margin-top:6px; }}
  .verdict {{ display:inline-block; margin-top:12px; padding:5px 12px; border-radius:999px;
    font-size:14px; font-weight:600; border:1px solid var(--line); }}
  .fair {{ color:var(--accent); border-color:var(--accent); }}
  .high {{ color:var(--warn); border-color:var(--warn); }}
  .scroller {{ overflow-x:auto; -webkit-overflow-scrolling:touch; }}
  table {{ width:100%; border-collapse:collapse; font-size:15px; margin-top:8px;
    min-width:520px; }}
  th,td {{ text-align:left; padding:10px 8px; border-bottom:1px solid var(--line); }}
  th {{ font-size:12px; text-transform:uppercase; letter-spacing:.07em; color:var(--muted); }}
  td.n, th.n {{ text-align:right; font-variant-numeric:tabular-nums; }}
  .thin {{ font-size:11px; color:var(--warn); border:1px solid var(--warn);
    border-radius:999px; padding:1px 7px; margin-left:6px; white-space:nowrap; }}
  #comps {{ margin-top:18px; }}
  #comps h3 {{ font-size:13px; text-transform:uppercase; letter-spacing:.07em;
    color:var(--muted); margin:0 0 6px; font-weight:600; }}
  #comps table {{ min-width:0; font-size:14px; }}
  #comps td {{ padding:7px 6px; }}
  #comps td.t {{ color:var(--muted); }}
  .note {{ margin-top:32px; padding:18px 20px; background:var(--card);
    border:1px solid var(--line); border-radius:10px; font-size:14px; color:var(--muted); }}
  .note b {{ color:var(--fg); }}
  a {{ color:var(--accent); }}
</style>
</head>
<body>
<div class="wrap">
  <h1>What is my software business worth?</h1>
  <p class="lede">Priced against {total} deals that actually closed &mdash;
     what buyers paid, not what sellers asked.</p>

  <form id="f" autocomplete="off">
    <div class="field">
      <label for="rev">Annual revenue <span class="hint">&mdash; USD, last 12 months</span></label>
      <input id="rev" type="number" min="0" step="1" inputmode="numeric" placeholder="1200">
    </div>
    <div class="field">
      <label for="ask">Asking price <span class="hint">&mdash; optional, to check if it is fair</span></label>
      <input id="ask" type="number" min="0" step="1" inputmode="numeric" placeholder="5000">
    </div>

    <div id="out">
      <div class="big" id="range">&mdash;</div>
      <div class="sub" id="basis"></div>
      <div id="verdict"></div>
      <div id="comps"></div>
    </div>
  </form>

  <h2 style="font-size:19px;margin:28px 0 4px;">What deals actually cleared at</h2>
  <div class="scroller">
    <table>
      <thead><tr>
        <th>Deal size</th><th class="n">Deals</th><th class="n">Median price</th>
        <th class="n">Median &times;revenue</th><th class="n">Typical range</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>

  <div class="note">
    <p><b>Small products sell at high multiples; bigger ones do not.</b>
    Prices have a floor around $1,000 whether a product earns anything or not,
    so a tiny product clears at many times its revenue, while a mid-sized
    business clears near one year of it.</p>
    <p><b>How the estimate is made.</b> No formula. It finds the closed deals
    whose revenue is closest to yours and shows what those actually sold for,
    along with the deals themselves, so you can judge the comparison yourself.
    A formula picks a band and can be quietly wrong about which one; comparables
    cannot be.</p>
    <p><b>What this cannot tell you.</b> Comparable deals mix SaaS, content
    sites, apps and ecommerce, and those sell at different multiples of the same
    revenue. Margin matters more than revenue and is rarely published. That is
    why the deals themselves are listed: judge the comparison, do not just take
    the range.</p>
    <p><b>Where the numbers come from.</b> Only closed deals &mdash; marketplace
    exit prices, broker closed-deal records, and founder disclosures read one by
    one. Asking prices are excluded on purpose: listings at 28&times; and 31&times;
    revenue are common, and including them would corrupt the benchmark.
    Bands marked <span class="thin">thin sample</span> have too few deals with
    revenue attached to be relied on, and are shown rather than hidden.</p>
    <p>Updated {updated}.</p>
  </div>
</div>
<script id="data" type="application/json">{payload}</script>
<script>
  const D = JSON.parse(document.getElementById('data').textContent);
  const rev = document.getElementById('rev');
  const ask = document.getElementById('ask');
  const out = document.getElementById('out');
  const money = n => '$' + Math.round(n).toLocaleString('en-US');

  function pct(sorted, q) {{
    if (!sorted.length) return null;
    const i = Math.max(0, Math.min(sorted.length - 1, Math.round(q * (sorted.length - 1))));
    return sorted[i];
  }}

  // 입력 매출에 가장 가까운 실제 거래들을 고른다.
  // 공식을 쓰지 않는 이유: 구간을 잘못 고르면 조용히 엉뚱한 답을 낸다.
  // 사례는 그럴 수가 없고, 근거를 그대로 보여줄 수 있다.
  function nearest(r, k) {{
    return D.comps
      .map(c => ({{ ...c, gap: Math.abs(Math.log((c.r || 1) / r)) }}))
      .sort((a, b) => a.gap - b.gap)
      .slice(0, k);
  }}

  function estimate() {{
    const r = Number(rev.value);
    const a = Number(ask.value);
    const elRange = document.getElementById('range');
    const elBasis = document.getElementById('basis');
    const elVerdict = document.getElementById('verdict');
    const elComps = document.getElementById('comps');

    // 매출이 거의 없는 경우는 비교가 아니라 '가격 바닥'이 답이다
    if (rev.value !== '' && r >= 0 && r < 600) {{
      const f = D.floors;
      if (!f.length) {{ out.classList.remove('show'); return; }}
      elRange.textContent = money(f[0]) + ' – ' + money(f[f.length - 1]);
      elBasis.textContent =
        f.length + ' products with almost no revenue still sold, at a median of ' +
        money(pct(f, 0.5)) + '. Price has a floor; revenue barely moves it down here.';
      elComps.innerHTML = '';
      elVerdict.innerHTML = a > 0
        ? (a <= f[f.length - 1]
            ? '<span class="verdict fair">Asking ' + money(a) + ' is within what these cleared at</span>'
            : '<span class="verdict high">Asking ' + money(a) +
              ' is above every comparable deal with no revenue</span>')
        : '';
      out.classList.add('show');
      return;
    }}

    if (!r || r <= 0) {{ out.classList.remove('show'); return; }}

    const k = Math.min(12, D.comps.length);
    const near = nearest(r, k);
    if (!near.length) {{ out.classList.remove('show'); return; }}

    const prices = near.map(c => c.p).sort((x, y) => x - y);
    const lo = pct(prices, 0.25), hi = pct(prices, 0.75);
    elRange.textContent = money(lo) + ' – ' + money(hi);

    const revs = near.map(c => c.r).sort((x, y) => x - y);
    elBasis.textContent =
      'Middle half of ' + near.length + ' closed deals with revenue closest to yours (' +
      money(revs[0]) + ' – ' + money(revs[revs.length - 1]) + ').';

    elComps.innerHTML =
      '<h3>The deals this is based on</h3><div class="scroller"><table><tbody>' +
      near.sort((x, y) => x.r - y.r).map(c =>
        '<tr><td class="n">' + money(c.p) + '</td>' +
        '<td class="n">' + money(c.r) + ' rev</td>' +
        '<td class="t">' + c.t.replace(/[<>&]/g, m =>
          ({{'<':'&lt;','>':'&gt;','&':'&amp;'}})[m]) + '</td></tr>'
      ).join('') + '</tbody></table></div>';

    if (!a || a <= 0) {{ elVerdict.innerHTML = ''; }}
    else if (a <= hi) {{
      elVerdict.innerHTML = '<span class="verdict fair">Asking ' + money(a) + ' is within range</span>';
    }} else {{
      const over = (a / hi).toFixed(1);
      elVerdict.innerHTML = '<span class="verdict high">Asking ' + money(a) + ' is ' + over +
        '× the top of this range</span>';
    }}
    out.classList.add('show');
  }}

  rev.addEventListener('input', estimate);
  ask.addEventListener('input', estimate);
</script>
</body>
</html>
"""


def build(conn, out: Path = OUT) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(conn), encoding="utf-8")
    return out
