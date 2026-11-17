"""SQLite 저장소 — 매물 데이터를 쌓아두고 시간에 따른 변화를 본다."""
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "listings.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT    NOT NULL,   -- microns | sideprojectors | ...
    external_key    TEXT    NOT NULL,   -- 사이트 내 식별자(없으면 제목 슬러그)
    title           TEXT    NOT NULL,
    category        TEXT,
    description     TEXT,
    asking_price    INTEGER,            -- USD (부르는 값)
    exit_price      INTEGER,            -- USD (실제 체결가. 팔린 매물만)
    revenue_amount  INTEGER,            -- USD
    revenue_period  TEXT,               -- ttm | annual | monthly | unknown
    first_seen      TEXT    NOT NULL,
    last_seen       TEXT    NOT NULL,
    raw             TEXT,
    UNIQUE(source, external_key)
);

CREATE TABLE IF NOT EXISTS snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id  INTEGER NOT NULL REFERENCES listings(id),
    seen_at     TEXT    NOT NULL,
    asking_price INTEGER,
    revenue_amount INTEGER,
    present     INTEGER NOT NULL DEFAULT 1   -- 0 이면 그날 목록에서 사라짐(= 팔렸을 가능성)
);

CREATE INDEX IF NOT EXISTS idx_snap_listing ON snapshots(listing_id, seen_at);

-- 커뮤니티에 공개된 "얼마에 팔았다" 발언.
-- 마켓플레이스 매물(listings)과 성격이 달라 테이블을 나눈다:
-- 이쪽은 사람이 한 주장이라 사람의 승인을 거쳐야 공개할 수 있다.
CREATE TABLE IF NOT EXISTS claims (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source       TEXT    NOT NULL,          -- hn | reddit | ...
    external_key TEXT    NOT NULL,          -- 원글 id
    url          TEXT    NOT NULL,          -- 출처 링크 (반드시 보존)
    title        TEXT    NOT NULL,
    price        INTEGER,                   -- 추출값 (환산하지 않음)
    currency     TEXT,                      -- USD | GBP | EUR | ... (원 통화 그대로)
    direction    TEXT,                      -- sold | acquired | unknown
    points       INTEGER,
    posted_at    TEXT,
    status       TEXT    NOT NULL DEFAULT 'pending',  -- pending | approved | rejected
    note         TEXT,
    found_at     TEXT    NOT NULL,
    UNIQUE(source, external_key)
);

CREATE INDEX IF NOT EXISTS idx_claims_status ON claims(status, price);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def upsert(conn: sqlite3.Connection, rec: dict) -> int:
    """매물 1건 저장. 이미 있으면 last_seen 갱신하고 스냅샷을 하나 더 쌓는다."""
    ts = now()
    cur = conn.execute(
        "SELECT id FROM listings WHERE source=? AND external_key=?",
        (rec["source"], rec["external_key"]),
    )
    row = cur.fetchone()
    if row:
        listing_id = row["id"]
        conn.execute(
            """UPDATE listings SET title=?, category=?, description=?,
               asking_price=COALESCE(?, asking_price),
               exit_price=COALESCE(?, exit_price),
               revenue_amount=?, revenue_period=?, last_seen=?, raw=?
               WHERE id=?""",
            (rec["title"], rec.get("category"), rec.get("description"),
             rec.get("asking_price"), rec.get("exit_price"), rec.get("revenue_amount"),
             rec.get("revenue_period", "unknown"), ts, rec.get("raw"), listing_id),
        )
    else:
        cur = conn.execute(
            """INSERT INTO listings
               (source, external_key, title, category, description,
                asking_price, exit_price, revenue_amount, revenue_period, first_seen, last_seen, raw)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (rec["source"], rec["external_key"], rec["title"], rec.get("category"),
             rec.get("description"), rec.get("asking_price"), rec.get("exit_price"),
             rec.get("revenue_amount"),
             rec.get("revenue_period", "unknown"), ts, ts, rec.get("raw")),
        )
        listing_id = cur.lastrowid

    conn.execute(
        "INSERT INTO snapshots (listing_id, seen_at, asking_price, revenue_amount, present) VALUES (?,?,?,?,1)",
        (listing_id, ts, rec.get("asking_price"), rec.get("revenue_amount")),
    )
    return listing_id


def mark_absent(conn: sqlite3.Connection, source: str, seen_ids: set[int]) -> int:
    """이번 수집에서 안 보인 매물에 present=0 스냅샷을 남긴다 (사라짐 = 팔렸을 가능성)."""
    ts = now()
    rows = conn.execute("SELECT id FROM listings WHERE source=?", (source,)).fetchall()
    missing = [r["id"] for r in rows if r["id"] not in seen_ids]
    for lid in missing:
        conn.execute(
            "INSERT INTO snapshots (listing_id, seen_at, asking_price, revenue_amount, present) VALUES (?,?,NULL,NULL,0)",
            (lid, ts),
        )
    return len(missing)


def upsert_claim(conn: sqlite3.Connection, rec: dict) -> bool:
    """판매 주장 1건 저장. 이미 있으면 건드리지 않는다 —
    사람이 이미 승인/거절한 판정을 재수집이 덮어쓰면 안 되기 때문이다."""
    cur = conn.execute(
        "SELECT 1 FROM claims WHERE source=? AND external_key=?",
        (rec["source"], rec["external_key"]),
    )
    if cur.fetchone():
        return False
    conn.execute(
        """INSERT INTO claims
           (source, external_key, url, title, price, currency, direction, points, posted_at, found_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (rec["source"], rec["external_key"], rec["url"], rec["title"], rec.get("price"),
         rec.get("currency"), rec.get("direction"), rec.get("points"), rec.get("posted_at"), now()),
    )
    return True
