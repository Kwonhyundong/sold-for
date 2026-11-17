"""거래 하나하나에 자기 페이지를 준다.

지금은 198건이 한 페이지에 들어 있어서 검색엔진에는 페이지 하나다.
쪼개면 198개가 되고, 데이터가 늘면 페이지도 저절로 는다.

구글의 대량 생성 규제는 '내용 없이 양만 늘린 것'을 잡는다. 그래서 각
페이지에는 템플릿을 걷어내도 남는 것이 있어야 한다 — 이 거래의 숫자,
비슷한 거래들과의 비교, 같은 구간의 분포. 전부 데이터에서 계산된다.
"""
import html
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SITE = "https://kwonhyundong.github.io/sold-for"
OUT = Path(__file__).resolve().parent.parent / "site"

BANDS = [
    ("under-10k", 0, 10_000, "under $10,000"),
    ("10k-100k", 10_000, 100_000, "$10,000 to $100,000"),
    ("100k-1m", 100_000, 1_000_000, "$100,000 to $1 million"),
    ("over-1m", 1_000_000, float("inf"), "over $1 million"),
]


@dataclass
class Deal:
    slug: str
    title: str
    price: int
    revenue: int | None
    category: str | None
    sold_on: str | None
    source_url: str
    source_name: str

    @property
    def multiple(self) -> float | None:
        if not self.revenue:
            return None
        return round(self.price / self.revenue, 1)

    @property
    def band(self) -> tuple[str, str]:
        for key, lo, hi, label in BANDS:
            if lo <= self.price < hi:
                return key, label
        return BANDS[-1][0], BANDS[-1][3]


def _slug(text: str, used: set[str]) -> str:
    base = re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", (text or "").lower())).strip("-")
    base = base[:70] or "deal"
    slug, n = base, 2
    while slug in used:
        slug = f"{base}-{n}"
        n += 1
    used.add(slug)
    return slug


def _cat_slug(category: str | None) -> str | None:
    if not category:
        return None
    s = re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", category.lower())).strip("-")
    return s or None


def total_records(conn) -> int:
    """데이터베이스 전체 건수. 개별 페이지 수(184)와 다르다 —
    커뮤니티 공개 발언은 제목과 금액뿐이라 페이지를 만들지 않는다."""
    a = conn.execute(
        "SELECT COUNT(*) c FROM listings WHERE exit_price IS NOT NULL").fetchone()["c"]
    b = conn.execute(
        "SELECT COUNT(*) c FROM claims WHERE status='approved' AND price IS NOT NULL"
    ).fetchone()["c"]
    return a + b


def load(conn) -> list[Deal]:
    used: set[str] = set()
    out: list[Deal] = []
    for r in conn.execute(
        """SELECT title, category, exit_price, revenue_amount, revenue_period,
                  sold_on, url, source
           FROM listings WHERE exit_price IS NOT NULL ORDER BY exit_price DESC"""
    ):
        rev = r["revenue_amount"]
        if rev is not None and r["revenue_period"] == "monthly":
            rev *= 12
        out.append(Deal(
            slug=_slug(r["title"], used),
            title=r["title"],
            price=r["exit_price"],
            revenue=rev,
            category=r["category"],
            sold_on=r["sold_on"],
            source_url=r["url"] or SITE,
            source_name="Flippa" if r["source"] == "flippa" else "Microns",
        ))
    return out


def _money(n: int | None) -> str:
    return f"${n:,}" if n else "not disclosed"


def _esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def _context(deal: Deal, deals: list[Deal]) -> tuple[str, list[Deal]]:
    """이 거래가 전체에서 어디쯤인지, 그리고 비슷한 거래들.

    이 문단이 페이지마다 다르기 때문에 템플릿만 남는 페이지가 되지 않는다.
    """
    band_key, band_label = deal.band
    peers = [d for d in deals if d.band[0] == band_key and d.slug != deal.slug]
    cheaper = sum(1 for d in deals if d.price < deal.price)
    pct = round(100 * cheaper / max(1, len(deals) - 1))

    bits = [
        f"This sale is larger than {pct}% of the {len(deals)} marketplace deals on record."
    ]
    if deal.multiple:
        band_mults = [d.multiple for d in peers if d.multiple]
        bits.append(
            f"At {_money(deal.price)} on {_money(deal.revenue)} of annual revenue, "
            f"it cleared at {deal.multiple}× revenue."
        )
        if band_mults:
            med = sorted(band_mults)[len(band_mults) // 2]
            verdict = ("above" if deal.multiple > med * 1.3
                       else "below" if deal.multiple < med * 0.7 else "close to")
            bits.append(
                f"The median multiple for deals {band_label} is {med}×, "
                f"so this one is {verdict} the typical price for its size."
            )
    else:
        bits.append(
            f"Revenue was not disclosed, so no multiple can be calculated — "
            f"which is true of {sum(1 for d in deals if not d.revenue)} deals in the set."
        )

    nearest = sorted(peers, key=lambda d: abs(d.price - deal.price))[:6]
    return " ".join(bits), nearest


def _page(title: str, desc: str, canonical: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<meta name="description" content="{_esc(desc)}">
<link rel="canonical" href="{_esc(canonical)}">
<style>
  :root {{ --bg:#fbfaf8; --fg:#1a1a18; --muted:#6c6a66; --line:#e4e1db;
          --accent:#1d5c48; --card:#fff; }}
  @media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
    --bg:#14141a; --fg:#eceaf0; --muted:#9b98a6; --line:#2c2c36;
    --accent:#6fd8ac; --card:#1c1c24; }} }}
  :root[data-theme="dark"] {{ --bg:#14141a; --fg:#eceaf0; --muted:#9b98a6;
    --line:#2c2c36; --accent:#6fd8ac; --card:#1c1c24; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--fg);
    font:16px/1.65 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; }}
  .wrap {{ max-width:720px; margin:0 auto; padding:40px 16px 72px; }}
  nav {{ font-size:14px; color:var(--muted); margin:0 0 24px; }}
  nav a {{ color:var(--muted); }}
  h1 {{ font-size:clamp(24px,4.5vw,34px); line-height:1.2; margin:0 0 10px;
    letter-spacing:-.02em; }}
  .figure {{ font-size:40px; font-weight:700; letter-spacing:-.02em; margin:18px 0 2px; }}
  .figure small {{ display:block; font-size:14px; font-weight:400; color:var(--muted); }}
  .facts {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr));
    gap:10px; margin:22px 0; }}
  .fact {{ background:var(--card); border:1px solid var(--line); border-radius:10px;
    padding:12px 14px; }}
  .fact b {{ display:block; font-size:19px; }}
  .fact span {{ color:var(--muted); font-size:13px; }}
  h2 {{ font-size:17px; margin:30px 0 8px; }}
  table {{ width:100%; border-collapse:collapse; font-size:15px; }}
  th,td {{ text-align:left; padding:9px 8px; border-bottom:1px solid var(--line); }}
  th {{ font-size:12px; text-transform:uppercase; letter-spacing:.07em; color:var(--muted); }}
  td.n {{ text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }}
  a {{ color:var(--accent); }}
  .src {{ font-size:14px; color:var(--muted); margin-top:20px; }}
  footer {{ margin-top:40px; padding-top:18px; border-top:1px solid var(--line);
    font-size:14px; color:var(--muted); }}
</style>
</head>
<body><div class="wrap">{body}</div></body>
</html>
"""


def _nav(extra: str = "") -> str:
    return (f'<nav><a href="{SITE}/">All closed deals</a> · '
            f'<a href="{SITE}/worth/">What is mine worth?</a>{extra}</nav>')


def build_deal_pages(deals: list[Deal], out: Path, total: int) -> list[str]:
    urls = []
    for deal in deals:
        ctx, nearest = _context(deal, deals)
        band_key, band_label = deal.band
        cat = _cat_slug(deal.category)

        facts = [("Sold for", _money(deal.price))]
        if deal.revenue:
            facts.append(("Annual revenue", _money(deal.revenue)))
            facts.append(("Multiple", f"{deal.multiple}×"))
        if deal.category:
            facts.append(("Type", deal.category))
        if deal.sold_on:
            facts.append(("Closed", deal.sold_on[:7]))

        rows = "".join(
            f'<tr><td class="n">{_money(d.price)}</td>'
            f'<td class="n">{(str(d.multiple) + "×") if d.multiple else "—"}</td>'
            f'<td><a href="{SITE}/deals/{_esc(d.slug)}/">{_esc(d.title[:52])}</a></td></tr>'
            for d in nearest)

        body = f"""{_nav()}
<h1>{_esc(deal.title)}</h1>
<div class="figure">{_money(deal.price)}<small>what it actually sold for</small></div>
<div class="facts">{"".join(
    f'<div class="fact"><b>{_esc(v)}</b><span>{_esc(k)}</span></div>' for k, v in facts)}</div>
<p>{_esc(ctx)}</p>
<h2>Closed deals of a similar size</h2>
<table><thead><tr><th>Price</th><th class="n">×rev</th><th>Deal</th></tr></thead>
<tbody>{rows or '<tr><td colspan="3">No comparable deals on record yet.</td></tr>'}</tbody></table>
<p class="src">Source: <a href="{_esc(deal.source_url)}" rel="nofollow noopener"
   target="_blank">{_esc(deal.source_name)}</a>. This is a closed price, not an asking price.</p>
<footer>Part of <a href="{SITE}/">a database of {total} software business sale prices</a>,
collected daily. See all deals <a href="{SITE}/price/{band_key}/">{_esc(band_label)}</a>{
f' or all <a href="{SITE}/category/{cat}/">{_esc(deal.category)}</a> deals' if cat else ''}.</footer>"""

        desc = (f"{deal.title} sold for {_money(deal.price)}"
                + (f" at {deal.multiple}× annual revenue" if deal.multiple else "")
                + ". A closed price, with comparable deals of similar size.")
        url = f"{SITE}/deals/{deal.slug}/"
        d = out / "deals" / deal.slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(
            _page(f"{deal.title} — sold for {_money(deal.price)}", desc, url, body),
            encoding="utf-8")
        urls.append(url)
    return urls


def _group_page(deals: list[Deal], total: int, *, heading: str,
                desc: str, url: str, path: Path, lede: str) -> None:
    prices = sorted(d.price for d in deals)
    mults = sorted(d.multiple for d in deals if d.multiple)
    med_p = prices[len(prices) // 2] if prices else None
    med_m = mults[len(mults) // 2] if mults else None

    facts = [("Deals", str(len(deals)))]
    if med_p:
        facts.append(("Median price", _money(med_p)))
    if med_m:
        facts.append(("Median multiple", f"{med_m}×"))
    if prices:
        facts.append(("Range", f"{_money(prices[0])} – {_money(prices[-1])}"))

    rows = "".join(
        f'<tr><td class="n">{_money(d.price)}</td>'
        f'<td class="n">{_money(d.revenue) if d.revenue else "—"}</td>'
        f'<td class="n">{(str(d.multiple) + "×") if d.multiple else "—"}</td>'
        f'<td><a href="{SITE}/deals/{_esc(d.slug)}/">{_esc(d.title[:48])}</a></td></tr>'
        for d in sorted(deals, key=lambda x: -x.price))

    body = f"""{_nav()}
<h1>{_esc(heading)}</h1>
<p>{_esc(lede)}</p>
<div class="facts">{"".join(
    f'<div class="fact"><b>{_esc(v)}</b><span>{_esc(k)}</span></div>' for k, v in facts)}</div>
<table><thead><tr><th>Sold for</th><th class="n">Revenue</th><th class="n">×rev</th>
<th>Deal</th></tr></thead><tbody>{rows}</tbody></table>
<footer>Part of <a href="{SITE}/">a database of {total} software business
sale prices</a>, collected daily from closed deals.</footer>"""

    path.mkdir(parents=True, exist_ok=True)
    (path / "index.html").write_text(_page(heading, desc, url, body), encoding="utf-8")


def build(conn, out: Path = OUT) -> dict:
    deals = load(conn)
    total = total_records(conn)
    urls = [f"{SITE}/", f"{SITE}/worth/"]
    urls += build_deal_pages(deals, out, total)

    # 금액대별
    for key, lo, hi, label in BANDS:
        group = [d for d in deals if lo <= d.price < hi]
        if not group:
            continue
        url = f"{SITE}/price/{key}/"
        _group_page(
            group, total,
            heading=f"Software businesses that sold for {label}",
            desc=(f"{len(group)} closed deals {label}: what each one actually sold for, "
                  f"with revenue and multiple where disclosed."),
            lede=(f"Every closed deal on record {label}. These are prices buyers paid, "
                  f"not prices sellers asked."),
            url=url, path=out / "price" / key)
        urls.append(url)

    # 업종별
    cats: dict[str, list[Deal]] = {}
    for d in deals:
        c = _cat_slug(d.category)
        if c:
            cats.setdefault(c, []).append(d)
    for c, group in cats.items():
        if len(group) < 3:          # 2건짜리 페이지는 읽을 게 없다
            continue
        name = group[0].category
        url = f"{SITE}/category/{c}/"
        _group_page(
            group, total,
            heading=f"What {name} businesses sold for",
            desc=(f"{len(group)} closed {name} deals with the price each one sold for, "
                  f"plus revenue and multiple where disclosed."),
            lede=(f"Closed deals in the {name} category. Prices buyers paid, "
                  f"not prices sellers asked."),
            url=url, path=out / "category" / c)
        urls.append(url)

    now = datetime.now(timezone.utc).date().isoformat()
    (out / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc><lastmod>{now}</lastmod></url>\n" for u in urls)
        + "</urlset>\n", encoding="utf-8")
    (out / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n", encoding="utf-8")

    return {"deals": len(deals), "total": total, "bands": len(BANDS),
            "categories": len(cats), "urls": len(urls)}
