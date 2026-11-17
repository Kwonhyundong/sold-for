"""추출기 회귀 테스트.

여기 적힌 사례들은 전부 실제 Hacker News 제목이다.
처음 두 개는 실제로 버그를 잡아낸 것이라 특히 지우면 안 된다:
  - "$0 revenue ... for $4.5k" 는 앞의 $0 을 판매가로 집던 버그
  - "was acquired" 는 글쓴이가 산 쪽이라고 거꾸로 판정하던 버그
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scout.hn import extract  # noqa: E402

CASES = [
    # (제목, 기대값)
    ("I sold my $0 revenue SaaS side project for $4.5k", (4500, "USD", "sold")),
    ("I just acquired my first SaaS company for $14,000", (14000, "USD", "acquired")),
    ("My bootstrapped SaaS was acquired for $800k", (800000, "USD", "sold")),
    ("How I sold my app for +$100k via email (and why I regret it)", (100000, "USD", "sold")),
    ("I sold my $12k ARR SaaS for $30k", (30000, "USD", "sold")),
    ("Show HN: My weekend project just sold for $1,200", (1200, "USD", "sold")),
    # 달러가 아닌 통화 — 환산하지 않고 원 통화를 보존한다
    ("I sold my startup for \u00a3100k", (100000, "GBP", "sold")),
    ("Why I sold my startup for \u20ac45,000", (45000, "EUR", "sold")),
    # 금액이 본문에만 있는 글 — 버리지 않고 사람이 채우도록 남긴다
    ("Sold My Side Project", (None, None, "sold")),
    ("Thank HN: My bootstrapped startup got acquired today", (None, None, "sold")),
    # 대기업 M&A — 전부 걸러져야 한다
    ("Citrix acquired and merged with Tibco for $16.5B", None),
    ("Electronic Arts to be acquired for $52B in largest private equity buyout", None),
    ("Zendesk to be acquired by investor group for $10.2bn", None),
    ("Solo founder's Base44 acquired by Wix for $80M", None),
    # 거래 얘기가 아닌 것
    ("Show HN: I built a CLI for managing dotfiles", None),
    ("Ask HN: How do you price your SaaS?", None),
]


def main() -> int:
    failed = 0
    for title, want in CASES:
        r = extract(title)
        got = None if r is None else (r["price"], r["currency"], r["direction"])
        if got != want:
            failed += 1
            print(f"FAIL  {title}\n      기대 {want}, 실제 {got}")
    total = len(CASES)
    print(f"\n{total - failed}/{total} 통과" + ("" if failed else " ✓"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
