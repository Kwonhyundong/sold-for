"""매물 시장 정찰기.

사용법:
  python3 -m scout.cli collect     # 마켓플레이스 매물 수집
  python3 -m scout.cli mine        # 커뮤니티에서 판매 발언 채굴
  python3 -m scout.cli approve-explicit  # 제목에 금액이 명시된 건은 규칙 통과
  python3 -m scout.cli review      # 나머지는 사람이 승인/거절
  python3 -m scout.cli site        # 정적 사이트 생성 → site/index.html
  python3 -m scout.cli report      # 저장된 데이터로 리포트
"""
import sys

from . import analyze, fetch, hn, parse, site, store

# 한 마켓플레이스가 여러 페이지에 걸쳐 있어도 source 는 하나로 둔다.
# 나누면 같은 매물이 두 행으로 들어온다 (UNIQUE 가 source 를 포함하므로).
SOURCES = {
    "microns": (
        [
            "https://www.microns.io/",                   # 부르는 값(현재 매물)
            "https://www.microns.io/sell-your-startup",  # 실제 체결가(판매 완료)
        ],
        parse.parse_microns,
    ),
}


def collect() -> None:
    conn = store.connect()
    total = 0
    for name, (urls, parser) in SOURCES.items():
        seen: set[int] = set()
        records: list[dict] = []
        for url in urls:
            print(f"[{name}] 수집 중 … {url}")
            try:
                page = fetch.get(url)
            except RuntimeError as e:
                print(f"[{name}] 실패: {e}")
                continue
            page_records, warnings = parser(page)
            for w in warnings:
                print(f"  ! {w}")
            records.extend(page_records)
        for rec in records:
            rec["source"] = name
            seen.add(store.upsert(conn, rec))
        gone = store.mark_absent(conn, name, seen)
        conn.commit()
        total += len(records)
        print(f"[{name}] 매물 {len(records)}건 저장, 목록에서 사라진 것 {gone}건")
    conn.close()
    print(f"\n합계 {total}건. DB: {store.DB_PATH}")


def mine() -> None:
    """커뮤니티 글에서 '얼마에 팔았다' 발언을 캐내 검토 대기열에 넣는다."""
    conn = store.connect()
    print("Hacker News 채굴 중 …")
    records = hn.mine()
    added = sum(1 for r in records if store.upsert_claim(conn, r))
    conn.commit()
    pending = conn.execute(
        "SELECT COUNT(*) c FROM claims WHERE status='pending'").fetchone()["c"]
    conn.close()
    print(f"후보 {len(records)}건 발견, 새로 추가 {added}건. 검토 대기 {pending}건.")
    if pending:
        print("검토:  python3 -m scout.cli review")


def review() -> None:
    """사람의 승인 게이트. 기계가 고르고 사람이 판정한다."""
    conn = store.connect()
    rows = conn.execute(
        """SELECT id, title, price, direction, url, points, posted_at
           FROM claims WHERE status='pending' ORDER BY price""").fetchall()
    if not rows:
        print("검토할 항목 없음.")
        conn.close()
        return
    print(f"검토 대기 {len(rows)}건.  y=승인  n=거절  s=건너뜀  q=종료\n")
    for r in rows:
        print("-" * 78)
        print(f"  {r['title']}")
        print(f"  ${r['price']:,}  ·  {r['direction']}  ·  {r['points'] or 0}pt  ·  {r['posted_at'] or '?'}")
        print(f"  {r['url']}")
        try:
            ans = input("  > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n중단.")
            break
        if ans == "q":
            break
        if ans in ("y", "n"):
            conn.execute("UPDATE claims SET status=? WHERE id=?",
                         ("approved" if ans == "y" else "rejected", r["id"]))
            conn.commit()
    left = conn.execute("SELECT COUNT(*) c FROM claims WHERE status='pending'").fetchone()["c"]
    ok = conn.execute("SELECT COUNT(*) c FROM claims WHERE status='approved'").fetchone()["c"]
    conn.close()
    print(f"\n승인 {ok}건, 남은 대기 {left}건.")


def approve_explicit() -> None:
    """제목이 금액을 직접 말하는 건은 규칙으로 통과시킨다.

    "I sold my side project for $30k" 같은 제목은 해석의 여지가 없다.
    판단이 필요한 건 금액이 빠진 글이고, 그건 사람에게 남긴다.
    통과 사유를 note 에 남겨 나중에 되짚을 수 있게 한다.
    """
    conn = store.connect()
    rows = conn.execute(
        """SELECT id, title, price FROM claims
           WHERE status='pending' AND price IS NOT NULL""").fetchall()
    n = 0
    for r in rows:
        got = hn.extract(r["title"])
        # 추출기를 다시 돌려 같은 금액이 나올 때만 인정한다
        if got and got.get("price") == r["price"]:
            conn.execute(
                "UPDATE claims SET status='approved', note=? WHERE id=?",
                ("제목이 금액을 명시함", r["id"]))
            n += 1
    conn.commit()
    left = conn.execute(
        "SELECT COUNT(*) c FROM claims WHERE status='pending'").fetchone()["c"]
    conn.close()
    print(f"규칙 통과 {n}건. 사람이 볼 것 {left}건 남음.")
    if left:
        print("  python3 -m scout.cli review")


def build_site() -> None:
    conn = store.connect()
    path = site.build(conn)
    conn.close()
    print(f"사이트 생성: {path}")


def report() -> None:
    conn = store.connect()
    rows = analyze.load(conn)
    if not rows:
        print("데이터 없음. 먼저 'collect' 를 돌리세요.")
        return
    print(analyze.report(rows))
    conn.close()


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    if cmd == "collect":
        collect()
    elif cmd == "mine":
        mine()
    elif cmd == "review":
        review()
    elif cmd == "approve-explicit":
        approve_explicit()
    elif cmd == "site":
        build_site()
    elif cmd == "report":
        report()
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
