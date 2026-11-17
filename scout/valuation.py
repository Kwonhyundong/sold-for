"""체결가 데이터에서 '이 가격 적정한가'를 판정할 기준을 뽑는다.

기준은 실제로 팔린 거래에서만 나온다. 호가는 쓰지 않는다 —
호가에는 31배짜리도 섞여 있어서 기준으로 쓰면 기준 자체가 망가진다.

표본이 적은 구간이 있다. 그건 숨기지 않고 그대로 보여준다.
표본 3건짜리 중앙값을 근거처럼 내미는 게 더 나쁘다.
"""
from dataclasses import dataclass, asdict

BANDS = [
    ("micro", 0, 10_000, "Under $10k"),
    ("small", 10_000, 100_000, "$10k – $100k"),
    ("mid", 100_000, 1_000_000, "$100k – $1M"),
    ("large", 1_000_000, float("inf"), "$1M+"),
]

# 표본이 이보다 적으면 '참고용'으로만 표시한다
MIN_CONFIDENT_SAMPLE = 8


@dataclass
class BandStats:
    key: str
    label: str
    n: int                 # 그 구간의 체결 건수
    n_with_revenue: int    # 그중 매출이 함께 공개된 건수
    median_price: int | None
    median_multiple: float | None
    p25_multiple: float | None
    p75_multiple: float | None

    @property
    def confident(self) -> bool:
        return self.n_with_revenue >= MIN_CONFIDENT_SAMPLE


def _pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    i = max(0, min(len(s) - 1, int(round(q * (len(s) - 1)))))
    return round(s[i], 2)


def _deals(conn) -> list[tuple[int, int | None]]:
    """(체결가, 연매출) 목록. 체결된 거래만."""
    out = []
    for r in conn.execute(
        """SELECT exit_price, revenue_amount, revenue_period
           FROM listings WHERE exit_price IS NOT NULL"""
    ):
        rev = r["revenue_amount"]
        if rev is not None and r["revenue_period"] == "monthly":
            rev *= 12
        out.append((r["exit_price"], rev))
    for r in conn.execute(
        """SELECT price FROM claims
           WHERE status='approved' AND price IS NOT NULL"""
    ):
        out.append((r["price"], None))      # 발언에는 매출이 거의 안 붙는다
    return out


def band_stats(conn) -> list[BandStats]:
    deals = _deals(conn)
    out = []
    for key, lo, hi, label in BANDS:
        rows = [(p, rev) for p, rev in deals if lo <= p < hi]
        prices = sorted(p for p, _ in rows)
        mults = [p / rev for p, rev in rows if rev and rev > 0]
        out.append(BandStats(
            key=key, label=label, n=len(rows), n_with_revenue=len(mults),
            median_price=prices[len(prices) // 2] if prices else None,
            median_multiple=_pct(mults, 0.5),
            p25_multiple=_pct(mults, 0.25),
            p75_multiple=_pct(mults, 0.75),
        ))
    return out


def comparables(conn) -> list[dict]:
    """매출이 함께 공개된 체결 거래. 비슷한 매출의 실제 거래를 보여주기 위한 것.

    공식 하나로 값을 내는 대신 실제 사례를 보여준다. 공식은 구간을 잘못
    고르면 조용히 엉뚱한 답을 내놓지만(실제로 매출 $55,891 짜리를
    '$10k 미만' 기준으로 계산하는 일이 있었다), 사례는 틀릴 수가 없다.
    """
    out = []
    for r in conn.execute(
        """SELECT title, exit_price, revenue_amount, revenue_period, sold_on, category
           FROM listings
           WHERE exit_price IS NOT NULL AND revenue_amount IS NOT NULL
             AND revenue_amount > 0"""
    ):
        rev = r["revenue_amount"]
        if r["revenue_period"] == "monthly":
            rev *= 12
        out.append({
            "t": r["title"][:70],
            "p": r["exit_price"],
            "r": rev,
            "d": r["sold_on"],
            "c": r["category"],
        })
    return sorted(out, key=lambda x: x["r"])


def floor_prices(conn) -> list[int]:
    """매출이 거의 없는데도 팔린 거래의 가격. 가격 바닥을 보여준다.

    매출이 NULL 인 건 제외한다. '안 밝혔다'와 '거의 없다'는 다르다 —
    둘을 섞으면 매출 미공개 대형 거래가 바닥값에 끼어든다.
    """
    return sorted(
        r["exit_price"] for r in conn.execute(
            """SELECT exit_price FROM listings
               WHERE exit_price IS NOT NULL
                 AND revenue_amount IS NOT NULL
                 AND revenue_amount < 600"""
        )
    )


def payload(conn) -> dict:
    """정적 페이지에 심을 데이터. 계산은 브라우저에서 한다 — 서버가 필요 없다."""
    stats = [asdict(s) | {"confident": s.confident} for s in band_stats(conn)]
    comps = comparables(conn)
    floors = floor_prices(conn)
    return {
        "bands": stats,
        "comps": comps,
        "floors": floors,
        "total_deals": sum(s["n"] for s in stats),
        "min_sample": MIN_CONFIDENT_SAMPLE,
    }
