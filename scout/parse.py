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


def _slugify(text: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", (text or "").lower())).strip("-")


def _slug_matches(slug: str, title: str) -> bool:
    """링크 슬러그가 정말 이 제목의 것인지 확인한다.

    카드 레이아웃이 한 가지가 아니라서, 조각 안에서 처음 찾은 링크가
    옆 카드 것일 수 있다. 실제로 'Photo Cleaner' 제목에
    'keto-diet-tracking' 링크가 붙는 일이 있었다.
    제목 단어와 슬러그 단어가 전혀 안 겹치면 그 링크는 믿지 않는다.
    """
    want = {w for w in _slugify(title).split("-") if len(w) > 2}
    have = {w for w in (slug or "").split("-") if len(w) > 2}
    if not want:
        return True
    return len(want & have) >= max(1, min(2, len(want) // 3))


def _best_slug(title: str, slugs: list[str]) -> str | None:
    """제목에 가장 잘 맞는 슬러그를 페이지 전체에서 고른다.

    카드 레이아웃이 두 가지라, 어떤 카드는 링크가 제목보다 앞에 온다.
    조각 안에서 링크를 찾으면 옆 카드 것을 집는 일이 생겨서
    (실제로 매물의 3분의 1이 그랬다) 위치 대신 내용으로 짝짓는다.
    Webflow 슬러그는 제목에서 만들어지므로 단어가 겹친다.
    """
    want = {w for w in _slugify(title).split("-") if len(w) > 2}
    if not want:
        return None
    best, best_score = None, 0
    for slug in slugs:
        have = {w for w in slug.split("-") if len(w) > 2}
        score = len(want & have)
        if score > best_score:
            best, best_score = slug, score
    # 제목 단어의 절반 넘게 겹쳐야 같은 매물로 본다
    return best if best_score >= max(1, len(want) // 2) else None


def parse_microns(page: str) -> tuple[list[dict], list[str]]:
    """Microns.io 리스팅 파싱. (매물목록, 경고목록) 을 돌려준다.

    카드 종류가 두 가지라 공통 지점인 listing-card-headings 로 자른다.
    각 조각은 다음 카드의 headings 직전에서 끝나므로 값이 옆 카드로 새지 않는다.
    """
    out: list[dict] = []
    warnings: list[str] = []

    all_slugs = re.findall(r'href="/startup-listings/([^"]+)"', page)
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

            pairs = _PAIR.findall(chunk)
            asking = revenue = exit_price = None
            period = "unknown"
            n_asking = n_revenue = n_exit = 0
            for value_frag, label_frag in pairs:
                amount = _money(_text(value_frag))
                label = _text(label_frag).lower()
                if amount is None:
                    continue
                if "exit" in label:
                    if n_exit == 0:
                        exit_price = amount
                    n_exit += 1
                elif "asking" in label or "price" in label:
                    if n_asking == 0:
                        asking = amount
                    n_asking += 1
                elif "revenue" in label or "profit" in label:
                    if n_revenue == 0:
                        revenue, period = amount, _period(label)
                    n_revenue += 1

            if asking is None and revenue is None and exit_price is None:
                continue

            # 자기 검증: 카드 하나에 호가/매출이 각각 두 번 이상 나오면 경계가 샌 것이다
            if n_asking > 1 or n_revenue > 1 or n_exit > 1:
                warnings.append(
                    f"[{title[:40]}] 한 카드에서 호가 {n_asking} / 매출 {n_revenue} / 체결 {n_exit} 발견 — 경계 의심")

            slug = _best_slug(title, all_slugs)
            if slug is None:
                warnings.append(f"[{title[:44]}] 맞는 링크를 못 찾음 — 목록 페이지로 연결")

            out.append({
                "source": "microns",
                "external_key": slug or _slugify(title)[:80],
                "url": (f"https://www.microns.io/startup-listings/{slug}" if slug
                        else "https://www.microns.io/"),
                "title": title,
                "category": _text(tag_m.group(1)) if tag_m else None,
                "description": _text(desc_m.group(1)) if desc_m else None,
                "asking_price": asking,
                "exit_price": exit_price,
                "revenue_amount": revenue,
                "revenue_period": period,
            })
        except Exception as e:  # 한 카드가 깨져도 나머지는 살린다
            warnings.append(f"카드 {idx} 파싱 실패: {e}")
            continue
    return out, warnings


# --- Flippa 체결 거래 -------------------------------------------------------
# 브로커가 중개한 거래라 금액대가 크다. 소액 구간은 다른 소스가 채운다.
# 카드 한 장에 자산유형 / 체결월 / 제목 / 연매출 / 양쪽 국가 / 체결가가 들어 있다.

_FL_BADGE = re.compile(r'<span class="badge">([^<]+)</span>')
_FL_DATE = re.compile(r'<span class="deal-date">([^<]+)</span>')
_FL_TITLE = re.compile(r'<h2 class="title">(.*?)</h2>', re.S)
_FL_SIZE = re.compile(r'<span class="deal-size">\s*([^<]+?)\s*(?:<br\s*/?>)?\s*</span>', re.S)
_FL_STAT = re.compile(
    r'<div class="stat-item">\s*<label>(.*?)</label>\s*(?:<br\s*/?>)?\s*'
    r'<strong>(.*?)</strong>', re.S)
_FL_CASE = re.compile(r'href="(https://flippa\.com/blog/[^"]+)"')

_MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}


def _fl_date(raw: str) -> str | None:
    """'Apr 2026' -> '2026-04-01'. 날짜를 못 읽으면 None."""
    m = re.match(r"([A-Za-z]{3})[a-z]*\s+(\d{4})", (raw or "").strip())
    if not m or m.group(1).title() not in _MONTHS:
        return None
    return f"{m.group(2)}-{_MONTHS[m.group(1).title()]:02d}-01"


def parse_flippa_closed(page: str) -> tuple[list[dict], list[str]]:
    """Flippa 의 'Closed Deals' 페이지에서 실제 체결 거래를 읽는다."""
    out: list[dict] = []
    warnings: list[str] = []

    chunks = page.split('<div class="listing-card">')[1:]
    for idx, chunk in enumerate(chunks):
        try:
            title_m = _FL_TITLE.search(chunk)
            size_m = _FL_SIZE.search(chunk)
            if not title_m or not size_m:
                continue
            title = _text(title_m.group(1))
            price = _money(_text(size_m.group(1)))
            if not title or not price:
                continue

            badges = [_text(b) for b in _FL_BADGE.findall(chunk)]
            # 첫 배지는 자산 유형, 둘째는 'Sold <날짜>' 이므로 유형만 취한다
            asset_type = badges[0] if badges else None
            if asset_type and asset_type.lower().startswith("sold"):
                asset_type = None

            revenue = None
            period = "unknown"
            for label_frag, value_frag in _FL_STAT.findall(chunk):
                label = _text(label_frag).lower()
                if "revenue" not in label and "profit" not in label:
                    continue
                amount = _money(_text(value_frag))
                if amount is None:
                    continue
                revenue = amount
                period = _period(label)
                break

            date_m = _FL_DATE.search(chunk)
            case_m = _FL_CASE.search(chunk)

            out.append({
                "source": "flippa",
                "external_key": _slugify(title)[:90],
                "title": title,
                "category": asset_type,
                "description": None,          # 남의 설명문은 싣지 않는다
                "url": case_m.group(1) if case_m else "https://flippa.com/lps/closed-deals",
                "asking_price": None,
                "exit_price": price,
                "revenue_amount": revenue,
                "revenue_period": period,
                "sold_on": _fl_date(date_m.group(1)) if date_m else None,
            })
        except Exception as e:
            warnings.append(f"Flippa 카드 {idx} 파싱 실패: {e}")
            continue

    if not out:
        warnings.append("Flippa: 카드를 하나도 못 읽었다 — 페이지 구조가 바뀌었을 수 있다")
    return out, warnings
