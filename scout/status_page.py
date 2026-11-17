"""수집이 제대로 돌고 있는지 눈으로 확인하는 페이지.

하루 1~2시간 들여다볼 자리다. 여기서 봐야 할 것은 딱 하나 —
"어제와 달라진 게 있나, 소스 중에 죽은 게 있나".

지금은 수집 이력이 하루치뿐이라 추이 그래프를 그리지 않는다.
점 하나짜리 선 그래프는 그래프가 아니다. 3일치가 쌓이면 자동으로 나타난다.
"""
import html
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "site" / "status"

# 소스가 이 시간 넘게 조용하면 의심한다. 매일 도는 수집이므로 이틀이면 이상하다.
STALE_HOURS = 36
MIN_DAYS_FOR_CHART = 3


def _esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def _hours_since(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        t = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - t).total_seconds() / 3600


def gather(conn) -> dict:
    sources = []
    for r in conn.execute(
        """SELECT source, COUNT(*) n,
                  SUM(CASE WHEN exit_price IS NOT NULL THEN 1 ELSE 0 END) sold,
                  MAX(last_seen) last
           FROM listings GROUP BY source ORDER BY n DESC"""
    ):
        age = _hours_since(r["last"])
        sources.append({
            "name": r["source"], "n": r["n"], "sold": r["sold"] or 0,
            "last": r["last"], "age": age,
            "ok": age is not None and age <= STALE_HOURS,
        })

    claims = {r["status"]: r["n"] for r in conn.execute(
        "SELECT status, COUNT(*) n FROM claims GROUP BY status")}

    history = [(r["d"], r["n"]) for r in conn.execute(
        """SELECT substr(first_seen,1,10) d, COUNT(*) n
           FROM listings GROUP BY d ORDER BY d""")]
    # 누적으로 바꾼다 — 보고 싶은 건 "얼마나 쌓였나"지 "그날 몇 개 들어왔나"가 아니다
    cum, total = [], 0
    for d, n in history:
        total += n
        cum.append((d, total))

    runs = conn.execute(
        "SELECT COUNT(DISTINCT substr(seen_at,1,13)) n FROM snapshots").fetchone()["n"]

    sold = conn.execute(
        "SELECT COUNT(*) c FROM listings WHERE exit_price IS NOT NULL").fetchone()["c"]
    approved = conn.execute(
        """SELECT COUNT(*) c FROM claims
           WHERE status='approved' AND price IS NOT NULL""").fetchone()["c"]

    return {"sources": sources, "claims": claims, "cumulative": cum,
            "runs": runs, "deals": sold + approved,
            "sold": sold, "approved": approved}


def _chart(cum: list[tuple[str, int]]) -> str:
    """누적 수집량 추이. 3일 미만이면 아무것도 그리지 않는다."""
    if len(cum) < MIN_DAYS_FOR_CHART:
        need = MIN_DAYS_FOR_CHART - len(cum)
        return (f'<p class="muted">추이 그래프는 수집이 {MIN_DAYS_FOR_CHART}일 쌓이면 '
                f'나타납니다. {need}일 더 필요합니다.</p>')

    w, h, pad = 640, 200, 34
    xs = [pad + i * (w - 2 * pad) / max(1, len(cum) - 1) for i in range(len(cum))]
    top = max(v for _, v in cum)
    ys = [h - pad - (v / top) * (h - 2 * pad) for _, v in cum]
    line = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}"
                    for i, (x, y) in enumerate(zip(xs, ys)))
    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="var(--series-1)"'
        f' stroke="var(--surface-1)" stroke-width="2"><title>{_esc(d)} · {v}건</title></circle>'
        for (d, v), x, y in zip(cum, xs, ys))
    labels = "".join(
        f'<text x="{x:.1f}" y="{h - 10}" text-anchor="middle" class="ax">{_esc(d[5:])}</text>'
        for (d, _), x in zip(cum, xs)) if len(cum) <= 14 else ""
    return (f'<svg viewBox="0 0 {w} {h}" role="img" class="chart" '
            f'aria-label="누적 수집 건수 추이">'
            f'<text x="{pad}" y="20" class="ax">{top}건</text>'
            f'<path d="{line}" fill="none" stroke="var(--series-1)" stroke-width="2" '
            f'stroke-linejoin="round" stroke-linecap="round"/>{dots}{labels}</svg>')


def render(conn) -> str:
    d = gather(conn)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    tiles = [
        ("기록된 거래", f"{d['deals']:,}"),
        ("마켓플레이스 체결가", f"{d['sold']:,}"),
        ("승인된 공개 발언", f"{d['approved']:,}"),
        ("검토 대기", f"{d['claims'].get('pending', 0):,}"),
    ]
    tiles_html = "".join(
        f'<div class="tile"><b>{_esc(v)}</b><span>{_esc(k)}</span></div>' for k, v in tiles)

    rows = ""
    for s in d["sources"]:
        if s["age"] is None:
            icon, label, cls = "?", "알 수 없음", "warn"
        elif s["ok"]:
            icon, label, cls = "●", "정상", "good"
        else:
            icon, label, cls = "▲", "오래됨", "crit"
        age = f"{s['age']:.0f}시간 전" if s["age"] is not None else "—"
        rows += (f'<tr><td>{_esc(s["name"])}</td>'
                 f'<td class="n">{s["n"]:,}</td>'
                 f'<td class="n">{s["sold"]:,}</td>'
                 f'<td class="n">{_esc(age)}</td>'
                 f'<td><span class="st {cls}">{icon} {label}</span></td></tr>')

    stale = [s for s in d["sources"] if not s["ok"]]
    banner = ("" if not stale else
              f'<div class="alert">▲ 소스 {len(stale)}개가 {STALE_HOURS}시간 넘게 '
              f'갱신되지 않았습니다 — 수집이 멈췄거나 사이트 구조가 바뀌었을 수 있습니다.</div>')

    return TEMPLATE.format(now=_esc(now), tiles=tiles_html, rows=rows,
                           banner=banner, chart=_chart(d["cumulative"]),
                           runs=d["runs"])


TEMPLATE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>수집 상태</title>
<style>
  :root {{
    color-scheme: light;
    --bg:#fbfaf8; --surface-1:#fff; --fg:#1a1a18; --muted:#6c6a66; --line:#e4e1db;
    --series-1:#2a78d6; --good:#0ca30c; --warn:#fab219; --crit:#d03b3b;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:where(:not([data-theme="light"])) {{
      color-scheme: dark;
      --bg:#14141a; --surface-1:#1c1c24; --fg:#eceaf0; --muted:#9b98a6;
      --line:#2c2c36; --series-1:#3987e5;
    }}
  }}
  :root[data-theme="dark"] {{
    color-scheme: dark;
    --bg:#14141a; --surface-1:#1c1c24; --fg:#eceaf0; --muted:#9b98a6;
    --line:#2c2c36; --series-1:#3987e5;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--fg);
    font:16px/1.6 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; }}
  .wrap {{ max-width:760px; margin:0 auto; padding:40px 16px 72px; }}
  h1 {{ font-size:26px; margin:0 0 4px; letter-spacing:-.02em; }}
  .sub {{ color:var(--muted); font-size:14px; margin:0 0 26px; }}
  h2 {{ font-size:14px; text-transform:uppercase; letter-spacing:.07em;
    color:var(--muted); margin:32px 0 10px; font-weight:600; }}
  .tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; }}
  .tile {{ background:var(--surface-1); border:1px solid var(--line);
    border-radius:10px; padding:14px 16px; }}
  .tile b {{ display:block; font-size:26px; font-variant-numeric:tabular-nums;
    letter-spacing:-.02em; }}
  .tile span {{ color:var(--muted); font-size:13px; }}
  table {{ width:100%; border-collapse:collapse; font-size:15px;
    background:var(--surface-1); border:1px solid var(--line); border-radius:10px;
    overflow:hidden; }}
  th,td {{ text-align:left; padding:11px 12px; border-bottom:1px solid var(--line); }}
  tr:last-child td {{ border-bottom:0; }}
  th {{ font-size:12px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); }}
  td.n, th.n {{ text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }}
  .st {{ font-size:13px; white-space:nowrap; }}
  .st.good {{ color:var(--good); }}
  .st.warn {{ color:var(--warn); }}
  .st.crit {{ color:var(--crit); }}
  .alert {{ background:var(--surface-1); border:1px solid var(--crit);
    border-radius:10px; padding:12px 15px; color:var(--crit); font-size:14px;
    margin:0 0 20px; }}
  .chart {{ width:100%; height:auto; background:var(--surface-1);
    border:1px solid var(--line); border-radius:10px; padding:4px; }}
  .ax {{ fill:var(--muted); font-size:11px; }}
  .muted {{ color:var(--muted); font-size:14px; }}
  footer {{ margin-top:36px; padding-top:16px; border-top:1px solid var(--line);
    font-size:14px; color:var(--muted); }}
  a {{ color:var(--series-1); }}
</style>
</head>
<body><div class="wrap">
  <h1>수집 상태</h1>
  <p class="sub">{now} 기준 · 수집 실행 {runs}회</p>

  {banner}

  <div class="tiles">{tiles}</div>

  <h2>소스별 상태</h2>
  <table>
    <thead><tr><th>소스</th><th class="n">수집</th><th class="n">체결가</th>
    <th class="n">최종 갱신</th><th>상태</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>

  <h2>누적 수집량</h2>
  {chart}

  <footer>
    <a href="../">공개 사이트</a> · 매일 03:17 UTC 자동 수집<br>
    상태가 <span class="st crit">▲ 오래됨</span> 으로 바뀌면 그 소스의 사이트 구조가
    바뀌었을 가능성이 큽니다. <code>scout/parse.py</code> 에서 해당 파서만 고치면 됩니다.
  </footer>
</div></body>
</html>
"""


def build(conn, out: Path = OUT) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    p = out / "index.html"
    p.write_text(render(conn), encoding="utf-8")
    return p
