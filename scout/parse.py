"""마켓플레이스별 리스팅 파서.

사이트 HTML이 바뀌면 여기만 고친다.
파서는 예외로 죽지 않고, 자기가 읽은 값이 그 카드 안에 실제로 있는지 스스로 검증한다.
"""
import html
import re

MONEY = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)\s*([kKmM])?")


def _money(text: str) -> int | None:
    """'$55,891' -> 55891,  '$1.2k' -> 1200.  못 읽으면 None."""
    m = MONEY.search(text or "")
    if not m:
        return None
    try:
        val = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    suffix = (m.group(2) or "").lower()
    if suffix == "k":
        val *= 1_000
    elif suffix == "m":
        val *= 1_000_000
    return int(round(val))


def _text(fragment: str) -> str:
    t = re.sub(r"<[^>]+>", " ", fragment or "")
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


def _period(label: str) -> str:
    low = (label or "").lower()
    if "ttm" in low:
        return "ttm"
    if "annual" in low or "year" in low or "arr" in low:
        return "annual"
    if "month" in low or "mrr" in low:
        return "monthly"
    return "unknown"


# 값/라벨 쌍: <h5 class="h5-heading">$X</h5><div class="body-text xs opacity-30">LABEL</div>
_PAIR = re.compile(
    r'<h5[^>]*class="h5-heading"[^>]*>(.*?)</h5>\s*'
    r'<div[^>]*class="[^"]*body-text xs opacity-30[^"]*"[^>]*>(.*?)</div>',
    re.S,
)


def parse_microns(page: str) -> tuple[list[dict], list[str]]:
    """Microns.io 리스팅 파싱. (매물목록, 경고목록) 을 돌려준다.

    카드 종류가 두 가지라 공통 지점인 listing-card-headings 로 자른다.
    각 조각은 다음 카드의 headings 직전에서 끝나므로 값이 옆 카드로 새지 않는다.
    """
    out: list[dict] = []
    warnings: list[str] = []

    chunks = page.split('class="listing-card-headings"')[1:]
    for idx, chunk in enumerate(chunks):
        try:
            title_m = re.search(r"<h5[^>]*>(.*?)</h5>", chunk, re.S)
            if not title_m:
                continue
            title = _text(title_m.group(1))
            if not title:
                continue

            desc_m = re.search(
                r'<div[^>]*class="[^"]*body-text s-light opacity-70[^"]*"[^>]*>(.*?)</div>',
                chunk, re.S)
            # 카테고리 태그는 카드 종류에 따라 headings 앞/뒤 모두 올 수 있다
            tag_m = re.search(r'class="tag-mc".*?<div>([^<]{2,40})</div>', chunk, re.S)
            slug_m = re.search(r'href="/startup-listings/([^"]+)"', chunk)

            pairs = _PAIR.findall(chunk)
            asking = revenue = None
            period = "unknown"
            n_asking = n_revenue = 0
            for value_frag, label_frag in pairs:
                amount = _money(_text(value_frag))
                label = _text(label_frag).lower()
                if amount is None:
                    continue
                if "asking" in label or "price" in label:
                    if n_asking == 0:
                        asking = amount
                    n_asking += 1
                elif "revenue" in label or "profit" in label:
                    if n_revenue == 0:
                        revenue, period = amount, _period(label)
                    n_revenue += 1

            if asking is None and revenue is None:
                continue

            # 자기 검증: 카드 하나에 호가/매출이 각각 두 번 이상 나오면 경계가 샌 것이다
            if n_asking > 1 or n_revenue > 1:
                warnings.append(
                    f"[{title[:40]}] 한 카드에서 호가 {n_asking}개 / 매출 {n_revenue}개 발견 — 경계 의심")

            out.append({
                "source": "microns",
                "external_key": slug_m.group(1) if slug_m
                                else re.sub(r"\W+", "-", title.lower())[:80],
                "title": title,
                "category": _text(tag_m.group(1)) if tag_m else None,
                "description": _text(desc_m.group(1)) if desc_m else None,
                "asking_price": asking,
                "revenue_amount": revenue,
                "revenue_period": period,
            })
        except Exception as e:  # 한 카드가 깨져도 나머지는 살린다
            warnings.append(f"카드 {idx} 파싱 실패: {e}")
            continue
    return out, warnings
