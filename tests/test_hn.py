"""추출기 회귀 테스트.

여기 적힌 제목은 전부 실제 Hacker News 글이다.
앞의 두 사례는 실제로 버그를 잡아낸 것이라 지우면 안 된다:
  - "$0 revenue ... for $4.5k" 는 앞의 $0 을 판매가로 집던 버그
  - "was acquired" 는 글쓴이가 산 쪽이라고 거꾸로 판정하던 버그
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scout.hn import extract  # noqa: E402

# (제목, 금액, 통화, 방향, 규모, 대기업여부)
CASES = [
    ("I sold my $0 revenue SaaS side project for $4.5k",
     4500, "USD", "sold", "micro", False),
    ("My bootstrapped SaaS was acquired for $800k",
     800_000, "USD", "sold", "mid", False),
    ("I just acquired my first SaaS company for $14,000",
     14_000, "USD", "acquired", "small", False),
    ("How I sold my app for +$100k via email (and why I regret it)",
     100_000, "USD", "sold", "mid", False),
    ("I sold my $12k ARR SaaS for $30k",
     30_000, "USD", "sold", "small", False),
    ("Show HN: My weekend project just sold for $1,200",
     1_200, "USD", "sold", "micro", False),
    # 달러가 아닌 통화 — 환산하지 않고 원 통화를 보존한다
    ("I sold my startup for £100k", 100_000, "GBP", "sold", "mid", False),
    ("Why I sold my startup for €45,000", 45_000, "EUR", "sold", "small", False),
    # 대형 거래도 버리지 않고 분류해 남긴다
    ("Citrix acquired and merged with Tibco for $16.5B",
     16_500_000_000, "USD", "sold", "large", False),
    ("Electronic Arts to be acquired for $52B in largest private equity buyout",
     52_000_000_000, "USD", "sold", "large", True),
    ("Solo founder's Base44 acquired by Wix for $80M",
     80_000_000, "USD", "sold", "large", False),
    # 금액이 본문에만 있는 글 — 사람이 채우도록 남긴다
    ("Sold My Side Project", None, None, "sold", None, False),
    ("Thank HN: My bootstrapped startup got acquired today",
     None, None, "sold", None, False),
]

# 거래 기록이 아니므로 아무것도 나오면 안 되는 것
NON_CASES = [
    "Show HN: I built a CLI for managing dotfiles",
    "Ask HN: How do you price your SaaS?",
]


def main() -> int:
    failed = 0
    for title, price, cur, direction, scale, corp in CASES:
        r = extract(title)
        want = (price, cur, direction, scale, corp)
        got = None if r is None else (r["price"], r["currency"], r["direction"],
                                      r["scale"], r["corporate"])
        if got != want:
            failed += 1
            print(f"FAIL  {title}\n      기대 {want}\n      실제 {got}")
    for title in NON_CASES:
        if extract(title) is not None:
            failed += 1
            print(f"FAIL  {title}\n      거래 기록이 아닌데 추출됨: {extract(title)}")

    total = len(CASES) + len(NON_CASES)
    print(f"\n{total - failed}/{total} 통과" + ("" if failed else " ✓"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
