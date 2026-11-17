"""수집이 제대로 돌고 있는지 보는 페이지 + 하루치 리포트.

하루 1~2시간 들여다볼 자리다. 봐야 할 것은 둘뿐이다 —
"어제보다 뭐가 늘었나", "죽은 소스가 있나".

디자인은 뽀송(pposongi) 앱 테마를 그대로 쓴다. 색을 새로 고르지 않는다.
scout/theme.py 참고.
"""
import html
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import theme

OUT = Path(__file__).resolve().parent.parent / "site" / "status"

# 매일 도는 수집이므로 이틀 조용하면 이상하다
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
    today = datetime.now(timezone.utc).date()
    yday = today - timedelta(days=1)

    # 소스별 마지막 실행 결과. listings 의 last_seen 만 보면
    # "오늘 돌았는데 차단당했다"와 "오늘 안 돌았다"를 구분할 수 없다.
    last_run = {
        r["source"]: r for r in conn.execute(
            """SELECT source, MAX(finished_at) finished_at, fetched, ok, warnings
               FROM runs GROUP BY source""")
    }

    sources = []
    for r in conn.execute(
        """SELECT source, COUNT(*) n,
                  SUM(CASE WHEN exit_price IS NOT NULL THEN 1 ELSE 0 END) sold,
                  MAX(last_seen) last
           FROM listings GROUP BY source ORDER BY n DESC"""
    ):
        lr = last_run.get(r["source"])
        tried = _hours_since(lr["finished_at"]) if lr else None
        if lr is None:
            state = "unknown"
        elif not lr["ok"]:
            state = "blocked"       # 돌긴 했는데 응답을 못 받음
        elif tried is not None and tried <= STALE_HOURS:
            state = "ok"
        else:
            state = "stale"         # 한동안 안 돌았음
        sources.append({
            "name": r["source"], "n": r["n"], "sold": r["sold"] or 0,
            "age": tried, "state": state,
            "fetched": lr["fetched"] if lr else None,
        })

    def added_on(day) -> int:
        return conn.execute(
            "SELECT COUNT(*) c FROM listings WHERE substr(first_seen,1,10)=?",
            (day.isoformat(),)).fetchone()["c"]

    # 목록에서 사라진 매물 = 팔렸을 가능성
    gone_today = conn.execute(
        """SELECT COUNT(DISTINCT listing_id) c FROM snapshots
           WHERE present=0 AND substr(seen_at,1,10)=?""",
        (today.isoformat(),)).fetchone()["c"]

    new_by_source = {
        r["source"]: r["c"] for r in conn.execute(
            """SELECT source, COUNT(*) c FROM listings
               WHERE substr(first_seen,1,10)=? GROUP BY source""",
            (today.isoformat(),))
    }

    history = [(r["d"], r["n"]) for r in conn.execute(
        """SELECT substr(first_seen,1,10) d, COUNT(*) n
           FROM listings GROUP BY d ORDER BY d""")]
    cum, run = [], 0
    for d, n in history:
        run += n
        cum.append((d, run))

    sold = conn.execute(
        "SELECT COUNT(*) c FROM listings WHERE exit_price IS NOT NULL").fetchone()["c"]
    approved = conn.execute(
        """SELECT COUNT(*) c FROM claims
           WHERE status='approved' AND price IS NOT NULL""").fetchone()["c"]
    pending = conn.execute(
        "SELECT COUNT(*) c FROM claims WHERE status='pending'").fetchone()["c"]
    runs = conn.execute(
        "SELECT COUNT(DISTINCT substr(seen_at,1,13)) n FROM snapshots").fetchone()["n"]

    return {
        "sources": sources, "cumulative": cum, "runs": runs,
        "deals": sold + approved, "sold": sold, "approved": approved,
        "pending": pending,
        "new_today": added_on(today), "new_yday": added_on(yday),
        "gone_today": gone_today, "new_by_source": new_by_source,
    }


def _chart(cum: list[tuple[str, int]]) -> str:
    if len(cum) < MIN_DAYS_FOR_CHART:
        need = MIN_DAYS_FOR_CHART - len(cum)
        return ('<p class="note">추이 그래프는 수집이 '
                f'{MIN_DAYS_FOR_CHART}일 쌓이면 나타납니다. {need}일 더 필요합니다.'
                '<br><span class="bl-en">Trend appears once three days of history exist</span></p>')

    w, h, pad = 660, 210, 36
    xs = [pad + i * (w - 2 * pad) / max(1, len(cum) - 1) for i in range(len(cum))]
    top = max(v for _, v in cum)
    ys = [h - pad - (v / top) * (h - 2 * pad) for _, v in cum]
    line = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}"
                    for i, (x, y) in enumerate(zip(xs, ys)))
    area = f"M{xs[0]:.1f},{h - pad} " + " ".join(
        f"L{x:.1f},{y:.1f}" for x, y in zip(xs, ys)) + f" L{xs[-1]:.1f},{h - pad} Z"
    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="var(--brand)"'
        f' stroke="var(--card)" stroke-width="2.5">'
        f'<title>{_esc(d)} · {v}건</title></circle>'
        for (d, v), x, y in zip(cum, xs, ys))
    labels = "".join(
        f'<text x="{x:.1f}" y="{h - 12}" text-anchor="middle" class="ax">{_esc(d[5:])}</text>'
        for (d, _), x in zip(cum, xs)) if len(cum) <= 14 else ""
    return (f'<svg viewBox="0 0 {w} {h}" role="img" class="chart"'
            f' aria-label="누적 수집 건수 추이">'
            f'<text x="{pad}" y="22" class="ax">{top}</text>'
            f'<path d="{area}" fill="var(--brand)" opacity=".10"/>'
            f'<path d="{line}" fill="none" stroke="var(--brand)" stroke-width="2"'
            f' stroke-linejoin="round" stroke-linecap="round"/>{dots}{labels}</svg>')


def render(conn) -> str:
    d = gather(conn)
    now = datetime.now(timezone.utc)
    kst = now + timedelta(hours=9)

    delta = d["new_today"] - d["new_yday"]
    arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "—")

    tiles = [
        ("기록된 거래", "Deals on record", f"{d['deals']:,}", "brand"),
        ("오늘 새로 들어온 것", "Added today", f"+{d['new_today']:,}", "mint"),
        ("목록에서 사라짐", "Delisted today", f"{d['gone_today']:,}", "lavender"),
        ("검토 대기", "Awaiting review", f"{d['pending']:,}", "peach"),
    ]
    tiles_html = "".join(
        f'<div class="tile {cls}"><b class="num">{_esc(v)}</b>'
        f'<span class="bl-ko">{_esc(ko)}</span>'
        f'<span class="bl-en">{_esc(en)}</span></div>'
        for ko, en, v, cls in tiles)

    LABEL = {
        "ok":      ("●", "정상", "ok"),
        "blocked": ("▲", "응답 없음", "bad"),
        "stale":   ("▲", "오래됨", "bad"),
        "unknown": ("?", "기록 없음", "warn"),
    }
    src_rows = ""
    for s in d["sources"]:
        icon, label, cls = LABEL[s["state"]]
        age = f"{s['age']:.0f}시간 전" if s["age"] is not None else "—"
        plus = d["new_by_source"].get(s["name"], 0)
        src_rows += (
            f'<tr><td class="name">{_esc(s["name"])}</td>'
            f'<td class="n num">{s["n"]:,}</td>'
            f'<td class="n num">{s["sold"]:,}</td>'
            f'<td class="n num">{"+" + str(plus) if plus else "—"}</td>'
            f'<td class="n">{_esc(age)}</td>'
            f'<td><span class="st {cls}">{icon} {label}</span></td></tr>')

    stale = [s for s in d["sources"] if s["state"] in ("blocked", "stale")]
    banner = "" if not stale else (
        f'<div class="alert"><b>▲ {", ".join(x["name"] for x in stale)} '
        f'에서 데이터를 못 받고 있습니다</b>'
        f'<span class="bl-en">Existing rows are kept untouched; nothing was marked delisted</span>'
        f'</div>')

    report = (
        f'오늘 <b class="num">{d["new_today"]}</b>건이 새로 들어왔습니다. '
        f'어제는 {d["new_yday"]}건이었으니 {arrow} '
        f'{abs(delta) if delta else 0}건 차이입니다.'
        if (d["new_today"] or d["new_yday"]) else
        '오늘 새로 들어온 거래가 없습니다. 수집은 돌았지만 소스에 새 매물이 없었다는 뜻입니다.')
    if d["gone_today"]:
        report += (f' 그리고 <b class="num">{d["gone_today"]}</b>건이 목록에서 사라졌습니다 — '
                   f'팔렸을 가능성이 있습니다.')

    return TEMPLATE.format(
        fonts=theme.FONTS_LINK, vars=theme.CSS_VARS, base=theme.CSS_BASE,
        kst=_esc(kst.strftime("%Y년 %m월 %d일 %H:%M")),
        utc=_esc(now.strftime("%Y-%m-%d %H:%M UTC")),
        runs=d["runs"], tiles=tiles_html, rows=src_rows,
        banner=banner, report=report, chart=_chart(d["cumulative"]))


TEMPLATE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>수집 상태 · sold-for</title>
{fonts}
<style>
{vars}
{base}
  .wrap {{ max-width:780px; margin:0 auto; padding:36px 18px 80px; }}
  header {{ margin:0 0 26px; }}
  .stamp {{ font-family:'Outfit'; font-size:12px; color:var(--soft);
            letter-spacing:.3px; margin-top:6px; }}

  .live {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap;
           background:var(--card); border:1px solid var(--border);
           border-radius:var(--r-card); padding:13px 18px; margin:0 0 16px;
           box-shadow:var(--shadow); }}
  .live .bl-ko {{ font-size:14px; font-weight:500; }}
  .live .bl-en {{ margin-left:auto; }}
  .dot {{ width:9px; height:9px; border-radius:50%; background:var(--soft);
          flex:0 0 auto; }}
  .dot.run {{ background:var(--mint); animation:pulse 1.4s ease-in-out infinite; }}
  .dot.idle {{ background:var(--soft); }}
  .dot.fail {{ background:var(--brand); }}
  @keyframes pulse {{ 0%,100% {{ opacity:1; }} 50% {{ opacity:.3; }} }}
  @media (prefers-reduced-motion: reduce) {{ .dot.run {{ animation:none; }} }}
  .report {{ background:var(--container); border:1px solid var(--border);
             border-radius:var(--r-card); padding:18px 20px; margin:0 0 20px;
             font-size:15px; line-height:1.7; }}
  .report b {{ color:var(--brand); font-size:17px; }}

  .alert {{ background:var(--card); border:1.5px solid var(--brand);
            border-radius:var(--r-card); padding:14px 18px; margin:0 0 18px;
            display:flex; flex-direction:column; gap:2px; }}
  .alert b {{ color:var(--brand); font-size:14px; font-weight:700; }}

  .tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(152px,1fr));
            gap:12px; margin:0 0 28px; }}
  .tile {{ background:var(--card); border:1px solid var(--border);
           border-radius:var(--r-card); box-shadow:var(--shadow);
           padding:16px 18px; display:flex; flex-direction:column; gap:2px;
           border-top:3px solid var(--border); }}
  .tile.brand    {{ border-top-color:var(--brand); }}
  .tile.mint     {{ border-top-color:var(--mint); }}
  .tile.lavender {{ border-top-color:var(--lavender); }}
  .tile.peach    {{ border-top-color:var(--peach); }}
  .tile b {{ font-size:30px; line-height:1.1; margin-bottom:4px; }}
  .tile .bl-ko {{ font-size:13px; font-weight:500; }}

  h2 {{ margin:30px 0 12px; }}
  .sec {{ display:flex; align-items:baseline; gap:8px; margin:30px 0 12px; }}
  .sec h2 {{ margin:0; }}

  table {{ width:100%; border-collapse:collapse; font-size:14px;
           background:var(--card); border:1px solid var(--border);
           border-radius:var(--r-card); overflow:hidden; box-shadow:var(--shadow); }}
  th,td {{ text-align:left; padding:12px 14px; border-bottom:1px solid var(--border); }}
  tr:last-child td {{ border-bottom:0; }}
  th {{ font-family:'Outfit'; font-size:11px; text-transform:uppercase;
        letter-spacing:.7px; color:var(--soft); font-weight:500; }}
  td.n, th.n {{ text-align:right; white-space:nowrap; }}
  td.name {{ font-family:'Outfit'; font-weight:500; }}
  .st {{ font-size:12.5px; white-space:nowrap; font-weight:500; }}
  .st.ok   {{ color:var(--mint); }}
  .st.warn {{ color:var(--sunny); }}
  .st.bad  {{ color:var(--brand); }}

  .chart {{ width:100%; height:auto; background:var(--card);
            border:1px solid var(--border); border-radius:var(--r-card);
            box-shadow:var(--shadow); padding:6px; }}
  .ax {{ fill:var(--soft); font-family:'Outfit'; font-size:11px; }}
  .note {{ color:var(--soft); font-size:14px; background:var(--container);
           border:1px solid var(--border); border-radius:var(--r-card);
           padding:16px 18px; }}

  footer {{ margin-top:38px; padding-top:18px; border-top:1px solid var(--border);
            font-size:13px; color:var(--soft); line-height:1.7; }}
  footer a {{ color:var(--brand); text-decoration:none; }}
  footer a:hover {{ text-decoration:underline; }}
  code {{ font-family:'JetBrains Mono'; font-size:12px; background:var(--container);
          padding:2px 6px; border-radius:6px; }}
  @media (max-width:560px) {{
    th.hide, td.hide {{ display:none; }}
    .wrap {{ padding-top:26px; }}
  }}
</style>
</head>
<body><div class="wrap">
  <header>
    <div class="blrow">
      <h1>수집 상태</h1>
      <span class="blrow-en">COLLECTION STATUS</span>
    </div>
    <div class="stamp">{kst} (KST) · {utc} · 실행 {runs}회</div>
  </header>

  <div class="live" id="live">
    <span class="dot" id="live-dot"></span>
    <span class="bl-ko" id="live-text">실행 상태 확인 중…</span>
    <span class="bl-en" id="live-sub">Checking GitHub Actions</span>
  </div>

  {banner}

  <div class="report">{report}</div>

  <div class="tiles">{tiles}</div>

  <div class="sec"><h2>소스별 상태</h2><span class="blrow-en">BY SOURCE</span></div>
  <table>
    <thead><tr>
      <th>소스</th><th class="n">수집</th><th class="n">체결가</th>
      <th class="n">오늘</th><th class="n hide">최종</th><th>상태</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>

  <div class="sec"><h2>누적 수집량</h2><span class="blrow-en">CUMULATIVE</span></div>
  {chart}

  <footer>
    <a href="../">공개 사이트</a> · 매일 03:17 UTC(한국 12:17) 자동 수집<br>
    상태가 <span class="st bad">▲ 오래됨</span> 으로 바뀌면 그 소스의 사이트 구조가
    바뀌었을 가능성이 큽니다. <code>scout/parse.py</code> 에서 해당 파서만 고치면 됩니다.
  </footer>
</div>
<script>
  // 공개 리포지토리라 인증 없이 실행 상태를 읽을 수 있다.
  // 정적 페이지가 "지금 돌고 있나"를 알 수 있는 유일한 방법이다.
  (async () => {{
    const dot  = document.getElementById('live-dot');
    const text = document.getElementById('live-text');
    const sub  = document.getElementById('live-sub');
    const set = (cls, ko, en) => {{
      dot.className = 'dot ' + cls; text.textContent = ko; sub.textContent = en;
    }};
    try {{
      const r = await fetch(
        'https://api.github.com/repos/Kwonhyundong/sold-for/actions/workflows/collect.yml/runs?per_page=1',
        {{ headers: {{ 'Accept': 'application/vnd.github+json' }} }});
      if (!r.ok) throw new Error(r.status);
      const run = (await r.json()).workflow_runs?.[0];
      if (!run) return set('idle', '아직 자동 수집이 돈 적이 없습니다', 'No runs yet');
      if (run.status !== 'completed') {{
        return set('run', '지금 수집 중입니다', 'Collecting now');
      }}
      const mins = Math.round((Date.now() - new Date(run.updated_at)) / 60000);
      const ago  = mins < 60 ? mins + '분 전'
                 : mins < 1440 ? Math.round(mins / 60) + '시간 전'
                 : Math.round(mins / 1440) + '일 전';
      if (run.conclusion === 'success') {{
        set('idle', `마지막 수집 ${{ago}} · 성공`, 'Last run succeeded');
      }} else {{
        set('fail', `마지막 수집 ${{ago}} · 실패 (${{run.conclusion}})`, 'Last run failed');
      }}
    }} catch (e) {{
      set('idle', '실행 상태를 불러오지 못했습니다', 'Could not reach GitHub');
    }}
  }})();
</script>
</body>
</html>
"""


def build(conn, out: Path = OUT) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    p = out / "index.html"
    p.write_text(render(conn), encoding="utf-8")
    return p
