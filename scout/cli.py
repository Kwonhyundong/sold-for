"""매물 시장 정찰기.

사용법:
  python3 -m scout.cli collect     # 수집해서 DB에 저장
  python3 -m scout.cli report      # 저장된 데이터로 리포트
"""
import sys

from . import analyze, fetch, parse, store

SOURCES = {
    # 부르는 값(현재 매물)
    "microns": ("https://www.microns.io/", parse.parse_microns),
    # 실제 체결가(판매 완료) — 호가보다 훨씬 값진 데이터
    "microns_sold": ("https://www.microns.io/sell-your-startup", parse.parse_microns),
}


def collect() -> None:
    conn = store.connect()
    total = 0
    for name, (url, parser) in SOURCES.items():
        print(f"[{name}] 수집 중 … {url}")
        try:
            page = fetch.get(url)
        except RuntimeError as e:
            print(f"[{name}] 실패: {e}")
            continue
        records, warnings = parser(page)
        for w in warnings:
            print(f"  ! {w}")
        seen: set[int] = set()
        for rec in records:
            rec["source"] = name
            seen.add(store.upsert(conn, rec))
        gone = store.mark_absent(conn, name, seen)
        conn.commit()
        total += len(records)
        print(f"[{name}] 매물 {len(records)}건 저장, 목록에서 사라진 것 {gone}건")
    conn.close()
    print(f"\n합계 {total}건. DB: {store.DB_PATH}")


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
    elif cmd == "report":
        report()
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
