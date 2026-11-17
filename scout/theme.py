"""뽀송(pposongi) 앱 테마를 웹으로 옮긴 것.

색을 임의로 고르지 않는다. 아래 값은 전부
Kwonhyundong/pposongi · lib/theme/app_theme.dart 에서 그대로 가져왔다.
값을 바꿔야 하면 그 파일을 먼저 바꾸고 여기에 반영한다.

텍스트 가이드도 같은 리포의 lib/widgets/bilingual.dart 를 따른다:
한글 본문 아래 영문 서브라벨, Outfit 10.5px w300~400, 자간 0.55,
불투명도 0.30~0.32.
"""

# ── 브랜드 (라이트/다크 공통) ─────────────────────────────────
PRIMARY = "#FF6B8A"
PRIMARY_SOFT = "#FFD6E0"
MINT = "#4ECBA4"
MINT_SOFT = "#B8F0DC"
LAVENDER = "#9B8CE8"
LAVENDER_SOFT = "#DDD5FF"
PEACH = "#FF9A6C"
PEACH_SOFT = "#FFDDCC"
SUNNY = "#FFBF3C"
SKY_BLUE = "#5BAAEF"

# ── 라이트 ────────────────────────────────────────────────────
CREAM = "#FAF9FF"
TEXT_DARK = "#18181C"
TEXT_SOFT = "#8A8A9E"
CARD_LIGHT = "#FFFFFF"
CONTAINER_LIGHT = "#F5F4FF"
BORDER_LIGHT = "#ECECF4"

# ── 다크 ──────────────────────────────────────────────────────
DARK_BG = "#0E0E12"
DARK_SURFACE = "#16161C"
DARK_CARD = "#1E1E28"
DARK_BORDER = "#2A2A38"
DARK_TEXT = "#F0F0F8"
DARK_TEXT_SOFT = "#7A7A9A"

# 모서리 — app_theme.dart 의 카드 20 / 버튼 16 / 인풋 14
RADIUS_CARD = "20px"
RADIUS_BUTTON = "16px"
RADIUS_INPUT = "14px"

FONTS_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link href="https://fonts.googleapis.com/css2?'
    "family=Noto+Sans+KR:wght@400;500;700;800;900&"
    "family=Outfit:wght@300;400;500;600&"
    "family=JetBrains+Mono:wght@700;800&"
    "family=Space+Grotesk:wght@700&"
    'display=swap" rel="stylesheet">'
)

# 상태색은 브랜드 팔레트 안에서 고른다. 새 색을 만들지 않는다.
STATUS_OK = MINT          # 정상
STATUS_WARN = SUNNY       # 주의
STATUS_BAD = PRIMARY      # 문제 (브랜드 핑크가 경고 역할을 겸한다)

CSS_VARS = f"""
  :root {{
    color-scheme: light;
    --brand:{PRIMARY}; --brand-soft:{PRIMARY_SOFT};
    --mint:{MINT}; --lavender:{LAVENDER}; --peach:{PEACH}; --sunny:{SUNNY};
    --sky:{SKY_BLUE};
    --bg:{CREAM}; --card:{CARD_LIGHT}; --container:{CONTAINER_LIGHT};
    --fg:{TEXT_DARK}; --soft:{TEXT_SOFT}; --border:{BORDER_LIGHT};
    --shadow:0 4px 16px rgba(0,0,0,.055);
    --r-card:{RADIUS_CARD}; --r-btn:{RADIUS_BUTTON}; --r-input:{RADIUS_INPUT};
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      color-scheme: dark;
      --bg:{DARK_BG}; --card:{DARK_CARD}; --container:{DARK_SURFACE};
      --fg:{DARK_TEXT}; --soft:{DARK_TEXT_SOFT}; --border:{DARK_BORDER};
      --shadow:0 4px 24px rgba(0,0,0,.35);
    }}
  }}
  :root[data-theme="dark"] {{
    color-scheme: dark;
    --bg:{DARK_BG}; --card:{DARK_CARD}; --container:{DARK_SURFACE};
    --fg:{DARK_TEXT}; --soft:{DARK_TEXT_SOFT}; --border:{DARK_BORDER};
    --shadow:0 4px 24px rgba(0,0,0,.35);
  }}
"""

CSS_BASE = """
  * { box-sizing:border-box; }
  body {
    margin:0; background:var(--bg); color:var(--fg);
    font-family:'Noto Sans KR',ui-sans-serif,system-ui,-apple-system,sans-serif;
    font-size:15px; line-height:1.6; font-weight:400;
    -webkit-font-smoothing:antialiased;
  }
  /* 한글 본문 + 영문 서브라벨 — bilingual.dart 의 BL 위젯 */
  .bl    { display:flex; flex-direction:column; gap:2px; }
  .bl-ko { font-family:'Noto Sans KR'; }
  .bl-en { font-family:'Outfit'; font-size:10.5px; font-weight:400;
           letter-spacing:.55px; line-height:1.3; color:var(--fg); opacity:.32; }
  /* 같은 줄에 나란히 — BLRow */
  .blrow    { display:flex; align-items:baseline; gap:8px; flex-wrap:wrap; }
  .blrow-en { font-family:'Outfit'; font-size:11px; font-weight:300;
              letter-spacing:.5px; color:var(--fg); opacity:.30; }

  h1 { font-family:'Noto Sans KR'; font-weight:900; font-size:26px;
       margin:0; line-height:1.15; }
  h2 { font-family:'Noto Sans KR'; font-weight:800; font-size:19px;
       margin:0; line-height:1.2; }
  .num { font-family:'JetBrains Mono'; font-weight:800; letter-spacing:-1px;
         font-variant-numeric:tabular-nums; }
  .en-display { font-family:'Space Grotesk'; font-weight:700; letter-spacing:-.4px; }
  .label { font-family:'Outfit'; font-weight:500; font-size:13px; letter-spacing:.3px; }

  .card { background:var(--card); border:1px solid var(--border);
          border-radius:var(--r-card); box-shadow:var(--shadow); }
"""
