"""Hacker News 에서 '내 제품을 얼마에 팔았다' 발언을 캐낸다.

마켓플레이스는 자기가 중개한 거래만 보여준다. 개인 간 거래, 직접 매각,
그리고 "매출 0인데 $4.5k에 팔았다" 같은 기록은 커뮤니티 글에만 남는다.
그게 흩어져 있어서 아무도 안 모았고, 그래서 모을 가치가 있다.

무료 공개 API(hn.algolia.com)만 쓴다. 키도 비용도 없다.
"""
import html
import json
import re
import time
import urllib.parse
from datetime import datetime, timezone

from . import fetch

API = "https://hn.algolia.com/api/v1/search"

# 이 패턴들이 '거래가 일어났다'는 신호다
QUERIES = [
    # 개인·소액 거래 (희소한 구간. 커뮤니티 글에만 남는다)
    "I sold my SaaS",
    "I sold my app",
    "I sold my side project",
    "sold my startup",
    "my side project was acquired",
    "bootstrapped SaaS acquired",
    "I acquired a SaaS",
    "exit price side project",
    "sold my micro SaaS",
    "sold my domain for",
    "sold my newsletter",
    "acquired my company",
    "我的项目卖了",
    # 대형 거래 (뉴스에 많이 남는다. 양으로 데이터베이스를 채운다)
    "acquired for $ million",
    "acquires startup for",
    "acquisition price announced",
    "startup acquired by",
    "exits for million",
]

# 달러만 보면 "£100k 에 팔았다" 같은 기록을 통째로 놓친다.
# 환산은 하지 않는다 — 환율은 거래 시점마다 다르고, 원 통화가 사실이다.
_CUR = {"$": "USD", "£": "GBP", "€": "EUR", "¥": "JPY"}
_MONEY = re.compile(r"([$£€¥])\s?([\d][\d,]*(?:\.\d+)?)\s*([kKmMbB])?")
_SALE_VERB = re.compile(r"\b(sold|selling|sells|acquired|exited?|bought|acquisition)\b", re.I)
# "for $X" / "at $X" 는 거래 금액을 가리키는 가장 강한 신호다.
# 제목에 "$0 revenue" 처럼 다른 금액이 섞여 있어도 이걸로 구분한다.
_FOR_PRICE = re.compile(r"\b(?:for|at)\s+\+?([$£€¥])\s?([\d][\d,]*(?:\.\d+)?)\s*([kKmMbB])?", re.I)
# 수동태(was/got acquired)면 글쓴이가 '판' 쪽이다.
_PASSIVE = re.compile(r"\b(?:was|were|got|been|is|to be)\s+(?:\w+\s+){0,2}?acquired\b", re.I)
_I_BOUGHT = re.compile(r"\b(?:i|we)\s+(?:just\s+)?(?:acquired|bought)\b", re.I)

# 개인이 만든 작은 제품이라는 신호
INDIE_HINTS = re.compile(
    r"\b(my|i|solo|side ?project|indie|bootstrap\w*|micro[- ]?saas|first)\b", re.I)

# 대기업 M&A 신호. 버리지 않고 표시만 한다 —
# 대형 거래도 데이터로서 값지고, 뉴스에 널려 있어 양이 많다.
# 희소한 건 소액 구간이고, 그건 아래 scale 로 구분된다.
CORP_HINTS = re.compile(
    r"\b(private equity|shareholders?|nasdaq|nyse|all[- ]cash deal|"
    r"merger agreement|board of directors|investor group|antitrust)\b", re.I)

# 거래 규모 구간 (USD 기준).
SCALE_BANDS = [
    (10_000, "micro"),        # 주말에 만든 것 ~ 인디 소형. 아무도 안 모으는 구간
    (100_000, "small"),       # 제대로 된 1인 제품
    (1_000_000, "mid"),       # 소규모 사업
]


def scale_of(price: int | None) -> str | None:
    """거래 규모 구간. 통화 환산은 하지 않으므로 USD 가 아니면 대략치다."""
    if price is None:
        return None
    for ceiling, name in SCALE_BANDS:
        if price < ceiling:
            return name
    return "large"


def _amount(num: str, suffix: str | None) -> int | None:
    try:
        val = float(num.replace(",", ""))
    except ValueError:
        return None
    mult = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}.get((suffix or "").lower(), 1)
    return int(round(val * mult))


def _price_from(title: str) -> tuple[int, str] | None:
    """거래 금액과 통화를 고른다.

    'for $X' 를 최우선으로 본다. 제목에 '$0 revenue' 같은 다른 금액이
    섞여 있을 때 그걸 판매가로 착각하지 않기 위해서다.
    """
    m = _FOR_PRICE.search(title)
    if m:
        amt = _amount(m.group(2), m.group(3))
        if amt:                      # 0 은 거래가가 아니다
            return amt, _CUR.get(m.group(1), "USD")
    # 차선: 제목에 나온 0 아닌 금액 중 가장 큰 것
    cands = [(a, _CUR.get(sym, "USD"))
             for sym, n, sfx in _MONEY.findall(title)
             if (a := _amount(n, sfx))]
    return max(cands) if cands else None


def _direction(title: str) -> str:
    """글쓴이가 판 쪽인가 산 쪽인가.

    'My SaaS was acquired' 는 수동태이므로 글쓴이가 판 것이다.
    'I acquired a SaaS' 라야 산 것이다.
    """
    if _I_BOUGHT.search(title):
        return "acquired"
    if _PASSIVE.search(title):
        return "sold"
    return "sold"


def extract(title: str) -> dict | None:
    """제목에서 거래 정보를 뽑는다. 거래 글로 안 보이면 None.

    금액이 제목에 없는 글도 버리지 않고 price=None 으로 돌려준다.
    '내 SaaS를 팔았다'고만 쓰고 금액은 본문에 적는 글이 훨씬 많기 때문이다.
    그런 건 사람이 원글을 열어 금액을 채운다.
    """
    if not _SALE_VERB.search(title):
        return None
    got = _price_from(title)
    if got is None and not INDIE_HINTS.search(title):
        # 금액도 없고 개인 제품 신호도 없으면 거래 기록으로 볼 근거가 없다
        return None
    corporate = bool(CORP_HINTS.search(title))
    if got is None:
        return {"price": None, "currency": None, "scale": None,
                "corporate": corporate, "direction": _direction(title)}
    price, currency = got
    return {"price": price, "currency": currency, "scale": scale_of(price),
            "corporate": corporate, "direction": _direction(title)}


def search(query: str, *, hits: int = 50, since_days: int = 2600,
           min_points: int = 1) -> list[dict]:
    since = int(time.time()) - since_days * 86400
    qs = urllib.parse.urlencode({
        "query": query,
        "tags": "story",
        "hitsPerPage": hits,
        "numericFilters": f"points>{min_points},created_at_i>{since}",
    })
    try:
        payload = json.loads(fetch.get(f"{API}?{qs}"))
    except (RuntimeError, json.JSONDecodeError):
        return []
    return payload.get("hits", [])


def mine() -> list[dict]:
    """모든 검색어를 돌려 후보 발언을 모은다. 중복은 원글 id 로 제거."""
    out: dict[str, dict] = {}
    for q in QUERIES:
        for hit in search(q):
            oid = str(hit.get("objectID") or "")
            if not oid or oid in out:
                continue
            title = html.unescape(hit.get("title") or "").strip()
            got = extract(title)
            if not got:
                continue
            created = hit.get("created_at_i")
            out[oid] = {
                "source": "hn",
                "external_key": oid,
                "url": f"https://news.ycombinator.com/item?id={oid}",
                "title": title,
                "price": got["price"],
                "currency": got["currency"],
                "scale": got["scale"],
                "corporate": got["corporate"],
                "direction": got["direction"],
                "points": hit.get("points"),
                "posted_at": (datetime.fromtimestamp(created, timezone.utc).date().isoformat()
                              if created else None),
            }
    return sorted(out.values(), key=lambda r: (r["price"] is None, r["price"] or 0))
