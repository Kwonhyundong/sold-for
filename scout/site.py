"""SQLite 에 모인 데이터를 정적 HTML 한 장으로 굽는다.

프레임워크도 빌드 도구도 쓰지 않는다. 결과물은 파일 하나라
어디에나 무료로 올릴 수 있고, 10년 뒤에도 열린다.

법적 안전장치: 남의 사이트 설명문을 통째로 옮기지 않는다.
싣는 것은 사실(가격·통화·날짜·제목)뿐이고, 모든 행은 원문으로 링크한다.
"""
import html
import json
from datetime import datetime, timezone

from . import seo
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "site"

SCALE_LABEL = {
    "micro": "~$10k",
    "small": "$10k–100k",
    "mid": "$100k–1M",
    "large": "$1M+",
}


def _rows(conn) -> list[dict]:
    out = []
    # 상세 페이지 슬러그를 같은 생성기에서 받아온다 — 양쪽이 어긋나면
    # 링크가 404 가 되므로 슬러그는 한 곳에서만 만든다.
    slugs = {(d.title, d.price): d.slug for d in seo.load(conn)}

    # 마켓플레이스에서 실제로 체결된 거래
    for r in conn.execute(
        """SELECT title, category, exit_price, revenue_amount, source, url, sold_on
           FROM listings WHERE exit_price IS NOT NULL ORDER BY exit_price"""
    ):
        slug = slugs.get((r["title"], r["exit_price"]))
        out.append({
            "title": r["title"],
            "price": r["exit_price"],
            "currency": "USD",
            "revenue": r["revenue_amount"],
            "kind": "marketplace",
            "category": r["category"],
            "url": (f"{seo.SITE}/deals/{slug}/" if slug
                    else (r["url"] or "https://www.microns.io/")),
            "internal": bool(slug),
            "date": r["sold_on"],
        })

    # 사람이 승인한 커뮤니티 공개 발언만 싣는다
    for r in conn.execute(
        """SELECT title, price, currency, scale, url, posted_at, direction
           FROM claims WHERE status='approved' AND price IS NOT NULL
           ORDER BY price"""
    ):
        out.append({
            "title": r["title"],
            "price": r["price"],
            "currency": r["currency"] or "USD",
            "revenue": None,
            "kind": "community",
            "category": r["direction"],
            "url": r["url"],
            "internal": False,
            "date": r["posted_at"],
        })

    return sorted(out, key=lambda x: x["price"])


def _stats(rows: list[dict]) -> dict:
    usd = sorted(r["price"] for r in rows if r["currency"] == "USD")
    by_scale: dict[str, int] = {}
    for r in rows:
        p = r["price"]
        band = ("micro" if p < 10_000 else "small" if p < 100_000
                else "mid" if p < 1_000_000 else "large")
        by_scale[band] = by_scale.get(band, 0) + 1
    return {
        "total": len(rows),
        "median": usd[len(usd) // 2] if usd else None,
        "min": usd[0] if usd else None,
        "max": usd[-1] if usd else None,
        "by_scale": by_scale,
        "with_revenue": sum(1 for r in rows if r["revenue"]),
    }


def _esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def render(conn) -> str:
    rows = _rows(conn)
    st = _stats(rows)
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def money(p, cur="USD"):
        sym = {"USD": "$", "GBP": "£", "EUR": "€", "JPY": "¥"}.get(cur, "")
        return f"{sym}{p:,}"

    cards = "".join(
        f'<div class="stat"><b>{_esc(v)}</b><span>{_esc(SCALE_LABEL.get(k, k))}</span></div>'
        for k, v in sorted(st["by_scale"].items(),
                           key=lambda kv: ["micro", "small", "mid", "large"].index(kv[0])))

    def band_of(p):
        return ("micro" if p < 10_000 else "small" if p < 100_000
                else "mid" if p < 1_000_000 else "large")

    body = "".join(
        f'<tr data-price="{r["price"]}" data-kind="{_esc(r["kind"])}" '
        f'data-band="{band_of(r["price"])}">'
        f'<td class="p">{_esc(money(r["price"], r["currency"]))}</td>'
        f'<td class="t">' + (
            f'<a href="{_esc(r["url"])}">{_esc(r["title"])}</a>' if r.get("internal")
            else f'<a href="{_esc(r["url"])}" target="_blank" rel="noopener nofollow">'
                 f'{_esc(r["title"])}</a>') + '</td>'
        f'<td class="r">{_esc(money(r["revenue"]) if r["revenue"] else "—")}</td>'
        f'<td class="k"><span class="tag {_esc(r["kind"])}">'
        f'{"marketplace" if r["kind"] == "marketplace" else "community"}</span></td>'
        f'<td class="d">{_esc(r["date"] or "—")}</td>'
        f'</tr>'
        for r in rows)

    # 구간·업종 페이지로 가는 내부 링크. 검색엔진이 상세 페이지까지
    # 타고 들어갈 경로이자, 사람이 자기 구간만 보는 입구다.
    bands_html = "".join(
        f'<a class="chip" href="{seo.SITE}/price/{k}/">{_esc(lbl)}</a>'
        for k, _lo, _hi, lbl in seo.BANDS)
    cat_counts: dict[str, tuple[str, int]] = {}
    for d in seo.load(conn):
        c = seo._cat_slug(d.category)
        if not c:
            continue
        name, n = cat_counts.get(c, (d.category, 0))
        cat_counts[c] = (name, n + 1)
    cats_html = "".join(
        f'<a class="chip" href="{seo.SITE}/category/{c}/">{_esc(name)} <b>{n}</b></a>'
        for c, (name, n) in sorted(cat_counts.items(), key=lambda kv: -kv[1][1])
        if n >= 3)

    return TEMPLATE.format(
        bands=bands_html, cats=cats_html,
        updated=updated, total=st["total"],
        median=money(st["median"]) if st["median"] else "—",
        lo=money(st["min"]) if st["min"] else "—",
        hi=money(st["max"]) if st["max"] else "—",
        cards=cards, body=body,
        payload=_esc(json.dumps({"updated": updated, "count": st["total"]})),
    )


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>What Software Businesses Actually Sold For</title>
<meta name="description" content="Real sale prices — from $1,000 weekend projects to $35M exits. Collected from marketplace exits, broker closed deals and founder disclosures. Not asking prices.">
<style>
  :root {{
    --bg:#fbfaf8; --fg:#1a1a18; --muted:#6c6a66; --line:#e4e1db;
    --accent:#1d5c48; --card:#fff;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --bg:#14141a; --fg:#eceaf0; --muted:#9b98a6; --line:#2c2c36;
      --accent:#6fd8ac; --card:#1c1c24;
    }}
  }}
  :root[data-theme="dark"] {{
    --bg:#14141a; --fg:#eceaf0; --muted:#9b98a6; --line:#2c2c36;
    --accent:#6fd8ac; --card:#1c1c24;
  }}
  * {{ box-sizing:border-box; }}
  body {{
    margin:0; background:var(--bg); color:var(--fg);
    font:16px/1.6 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  }}
  .wrap {{ max-width:960px; margin:0 auto; padding:48px 16px 80px; }}
  h1 {{ font-size:clamp(28px,5vw,44px); line-height:1.15; margin:0 0 12px; letter-spacing:-.02em; }}
  .lede {{ color:var(--muted); font-size:18px; max-width:62ch; margin:0 0 8px; }}
  .meta {{ color:var(--muted); font-size:14px; margin:0 0 32px; }}
  .stats {{ display:flex; flex-wrap:wrap; gap:12px; margin:0 0 28px; }}
  .stat {{
    background:var(--card); border:1px solid var(--line); border-radius:10px;
    padding:12px 16px; min-width:104px;
  }}
  .stat b {{ display:block; font-size:22px; }}
  .stat span {{ color:var(--muted); font-size:13px; }}
  .controls {{ display:flex; gap:8px; flex-wrap:wrap; margin:0 0 16px; }}
  button {{
    font:inherit; font-size:14px; padding:7px 14px; cursor:pointer;
    background:var(--card); color:var(--fg);
    border:1px solid var(--line); border-radius:999px;
  }}
  button[aria-pressed="true"] {{ background:var(--accent); color:var(--bg); border-color:var(--accent); }}
  table {{ width:100%; border-collapse:collapse; font-size:15px; }}
  th, td {{ text-align:left; padding:11px 10px; border-bottom:1px solid var(--line); }}
  th {{
    font-size:12px; text-transform:uppercase; letter-spacing:.07em;
    color:var(--muted); font-weight:600;
  }}
  td.p {{ font-variant-numeric:tabular-nums; font-weight:650; white-space:nowrap; }}
  td.r, td.d {{ font-variant-numeric:tabular-nums; color:var(--muted); white-space:nowrap; }}
  td.t a {{ color:var(--fg); text-decoration:none; border-bottom:1px solid var(--line); }}
  td.t a:hover {{ color:var(--accent); border-color:var(--accent); }}
  .tag {{ font-size:12px; padding:2px 9px; border-radius:999px; border:1px solid var(--line); color:var(--muted); }}
  .tag.marketplace {{ border-color:var(--accent); color:var(--accent); }}
  .browse {{ margin-top:38px; }}
  .browse h2 {{ font-size:13px; text-transform:uppercase; letter-spacing:.07em;
    color:var(--muted); margin:20px 0 10px; font-weight:600; }}
  .chip {{ display:inline-block; margin:0 7px 7px 0; padding:6px 13px;
    border:1px solid var(--line); border-radius:999px; background:var(--card);
    color:var(--fg); text-decoration:none; font-size:14px; }}
  .chip:hover {{ border-color:var(--accent); color:var(--accent); }}
  .chip b {{ color:var(--muted); font-weight:500; }}
  .note {{
    margin-top:40px; padding:18px 20px; background:var(--card);
    border:1px solid var(--line); border-radius:10px; font-size:14px; color:var(--muted);
  }}
  .note b {{ color:var(--fg); }}
  @media (max-width:640px) {{
    td.r, th.r, td.d, th.d {{ display:none; }}
    .wrap {{ padding-top:32px; }}
  }}
</style>
</head>
<body>
<div class="wrap">
  <h1>What software businesses actually sold for</h1>
  <p class="lede">From $1,000 weekend projects to $35M exits. Not asking prices &mdash;
     prices someone actually paid.</p>
  <p class="meta"><span id="count">{total}</span> deals &middot; updated {updated} &middot;
     median {median} &middot; range {lo}&ndash;{hi}</p>

  <div class="stats">{cards}</div>

  <div class="controls" data-group="band">
    <button data-band="all" aria-pressed="true">Any size</button>
    <button data-band="micro" aria-pressed="false">Under $10k</button>
    <button data-band="small" aria-pressed="false">$10k&ndash;100k</button>
    <button data-band="mid" aria-pressed="false">$100k&ndash;1M</button>
    <button data-band="large" aria-pressed="false">$1M+</button>
  </div>
  <div class="controls" data-group="kind">
    <button data-filter="all" aria-pressed="true">All sources</button>
    <button data-filter="marketplace" aria-pressed="false">Marketplace &amp; broker</button>
    <button data-filter="community" aria-pressed="false">Founder disclosures</button>
  </div>

  <table>
    <thead><tr>
      <th>Price</th><th>Product</th><th class="r">Revenue</th>
      <th>Source</th><th class="d">Date</th>
    </tr></thead>
    <tbody id="rows">{body}</tbody>
  </table>

  <div class="browse">
    <h2>Browse by deal size</h2>
    {bands}
    <h2>Browse by type</h2>
    {cats}
  </div>

  <div class="note">
    <p><b>Why this exists.</b> Marketplaces publish what sellers <i>ask</i>.
    What a product actually <i>sold</i> for is scattered across sold-listing pages
    and founder posts, and nowhere collected.</p>
    <p><b>How it is built.</b> Marketplace and broker rows are published exit prices.
    Founder-disclosure rows are mined from public posts and then read by a human
    before they appear here &mdash; automated extraction alone got the price wrong often
    enough that it could not be trusted unreviewed. Amounts are kept in the currency
    they were stated in; nothing is converted, because the rate on the day of an old
    deal is unknown. Every row links to its source.</p>
  </div>
</div>
<script>
  const state = {{ band: 'all', kind: 'all' }};
  const rows = [...document.querySelectorAll('#rows tr')];
  const count = document.getElementById('count');

  function apply() {{
    let shown = 0;
    for (const tr of rows) {{
      const ok = (state.band === 'all' || tr.dataset.band === state.band)
              && (state.kind === 'all' || tr.dataset.kind === state.kind);
      tr.style.display = ok ? '' : 'none';
      if (ok) shown++;
    }}
    if (count) count.textContent = shown;
  }}

  for (const group of document.querySelectorAll('.controls')) {{
    const key = group.dataset.group;
    const btns = [...group.querySelectorAll('button')];
    for (const b of btns) {{
      b.addEventListener('click', () => {{
        btns.forEach(x => x.setAttribute('aria-pressed', String(x === b)));
        state[key] = key === 'band' ? b.dataset.band : b.dataset.filter;
        apply();
      }});
    }}
  }}
</script>
</body>
</html>
"""


def build(conn, out_dir: Path = OUT_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "index.html"
    path.write_text(render(conn), encoding="utf-8")
    return path
