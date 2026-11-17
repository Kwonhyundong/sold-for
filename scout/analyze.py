"""수집한 매물에서 '파는 쪽' 관점의 숫자를 뽑는다.

핵심 질문은 하나: 매출이 거의 없는 제품이 실제로 얼마에 호가되는가.
그게 내가 하나 만들었을 때 기대할 수 있는 가격대다.
"""
from dataclasses import dataclass

NO_REVENUE_CEILING = 600      # 연 $600 미만이면 '사실상 매출 없음'으로 본다
SANE_MULTIPLE_MAX = 5.0       # 연이익 3~5배가 통상 시세


def annualize(amount: int | None, period: str | None) -> int | None:
    if amount is None:
        return None
    if period == "monthly":
        return amount * 12
    # ttm / annual / unknown 은 이미 연 단위로 본다
    return amount


@dataclass
class Row:
    title: str
    category: str | None
    asking: int | None
    annual_revenue: int | None

    @property
    def multiple(self) -> float | None:
        if not self.asking or not self.annual_revenue:
            return None
        return round(self.asking / self.annual_revenue, 1)

    @property
    def bucket(self) -> str:
        if self.annual_revenue is None or self.annual_revenue < NO_REVENUE_CEILING:
            return "매출없음"
        m = self.multiple
        if m is None:
            return "불명"
        return "정상배수" if m <= SANE_MULTIPLE_MAX else "고평가"


def load(conn) -> list[Row]:
    rows = conn.execute(
        """SELECT title, category, asking_price, revenue_amount, revenue_period
           FROM listings"""
    ).fetchall()
    return [
        Row(r["title"], r["category"], r["asking_price"],
            annualize(r["revenue_amount"], r["revenue_period"]))
        for r in rows
    ]


def seller_view(rows: list[Row]) -> dict:
    """매출이 사실상 없는 매물들의 호가 분포 = 내가 만들어 팔 때의 기대 가격."""
    prices = sorted(r.asking for r in rows if r.bucket == "매출없음" and r.asking)
    if not prices:
        return {"n": 0}
    n = len(prices)
    return {
        "n": n,
        "min": prices[0],
        "median": prices[n // 2],
        "max": prices[-1],
        "mean": int(sum(prices) / n),
    }


def report(rows: list[Row]) -> str:
    rows = sorted(rows, key=lambda r: (r.asking or 0))
    lines = ["", "매물 전체", "-" * 92,
             f"{'제목':<44} {'분류':<10} {'호가':>10} {'연매출':>10} {'배수':>7}", "-" * 92]
    for r in rows:
        title = (r.title[:42] + "..") if len(r.title) > 44 else r.title
        lines.append(
            f"{title:<44} {r.bucket:<10} "
            f"{('$' + format(r.asking, ',')) if r.asking else '-':>10} "
            f"{('$' + format(r.annual_revenue, ',')) if r.annual_revenue else '-':>10} "
            f"{(str(r.multiple) + 'x') if r.multiple else '-':>7}"
        )

    sv = seller_view(rows)
    lines += ["", "=" * 92,
              "파는 쪽 관점: '매출 사실상 없음' 매물의 호가 분포",
              "=" * 92]
    if sv["n"] == 0:
        lines.append("  해당 매물 없음")
    else:
        lines += [
            f"  표본        {sv['n']}건",
            f"  최저        ${sv['min']:,}",
            f"  중간값      ${sv['median']:,}",
            f"  평균        ${sv['mean']:,}",
            f"  최고        ${sv['max']:,}",
            "",
            f"  -> 매출 없이 하나 만들어 올리면 기대 호가는 ${sv['min']:,} ~ ${sv['max']:,},",
            f"     중간값 ${sv['median']:,} 근처.",
        ]
    return "\n".join(lines)
