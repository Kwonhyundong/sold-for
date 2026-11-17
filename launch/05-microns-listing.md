Microns 매물 등록용
https://www.microns.io/  →  Sell startup  →  계정 만들고 제출

등록비 0원. 팔렸을 때만 10% (첫 $10k 구간 기준).

⚠️ 이 글은 매출이 0이라는 사실을 숨기지 않습니다. 구매자는 Stripe 기록을
요구하고, 없는 걸 있다고 썼다가 들키면 거래가 그 자리에서 끝납니다.
팔리는 것은 매출이 아니라 데이터와 자동화입니다.

════════════════════════════════════════════════════════════════
TITLE
════════════════════════════════════════════════════════════════

Sold For — Database of Real Software Business Sale Prices

════════════════════════════════════════════════════════════════
CATEGORY
════════════════════════════════════════════════════════════════

Micro-SaaS   (없으면 Web app)

════════════════════════════════════════════════════════════════
ONE-LINE DESCRIPTION
════════════════════════════════════════════════════════════════

A searchable database of what software businesses actually sold for — 198 closed deals, collected automatically every day

════════════════════════════════════════════════════════════════
MAIN METRICS  (사실대로)
════════════════════════════════════════════════════════════════

Revenue        $0  (not monetized)
Customers      0
Launched       2026
Asking Price   $3,000

════════════════════════════════════════════════════════════════
OVERVIEW
════════════════════════════════════════════════════════════════

Every marketplace publishes what sellers ask. Almost nobody publishes what
buyers actually paid. That number is scattered across sold-listing pages,
broker archives and the occasional founder post, and no one had collected it.

Sold For does. It holds 198 closed deals, from $1,000 weekend projects to a
$2B acquisition, each linking back to its source, filterable by deal size and
by where the figure came from. A second page takes a revenue figure and shows
the nearest comparable closed deals rather than applying a formula.

I am selling it because I built the collection pipeline and the dataset, and I
am not the right person to monetize it. There is no revenue and no attempt at
revenue — no ads, no paywall, no email capture. The asking price reflects
that. What is finished is the part that takes time.

Honest about the numbers up front: $0 revenue, 0 customers, launched this
month. Traffic so far is whatever a single dev.to article brings. If you are
looking for an income stream on day one, this is not that.

════════════════════════════════════════════════════════════════
WHAT YOU ARE ACTUALLY BUYING
════════════════════════════════════════════════════════════════

• A dataset nobody else has assembled. 198 closed deals with price, revenue
  where disclosed, asset type, date and source link. Public prices are almost
  always asking prices; these are what buyers paid.

• A collection pipeline that runs itself. A scheduled job re-collects every
  source daily, re-runs the extraction tests, rebuilds both pages and
  redeploys. It has been running without intervention since launch.

• Findings the data produced that are not published elsewhere. Products under
  $10k clear at a median 8x annual revenue while $100k–$1M businesses clear at
  0.9x. Web products clear far better than mobile apps at the same revenue.
  Those are the hooks the content writes itself around.

• $0 running cost. Static pages on GitHub Pages, collection on GitHub Actions
  free tier, SQLite committed to the repo. No servers, no database bill, no
  vendor lock-in.

• Clean code with tests. No framework, no build step, Python standard library
  only. One file per source, so adding a source is one file. Regression tests
  cover the extraction logic and run before every collection, so a broken
  parser stops the run rather than silently writing bad rows.

════════════════════════════════════════════════════════════════
OBVIOUS WAYS TO MONETIZE  (none of these are built)
════════════════════════════════════════════════════════════════

• Paid tier for the full dataset export or an API. The free pages stay as the
  funnel.
• Weekly newsletter of newly closed deals. The pipeline already detects them.
• Affiliate or referral revenue from the marketplaces the data links to.
• Sponsorship from brokers and marketplaces, who want to be seen by people
  researching what to sell.
• Programmatic pages per deal size, asset type and multiple, built from data
  that already exists — original data, so it is not thin content.

════════════════════════════════════════════════════════════════
TECH STACK
════════════════════════════════════════════════════════════════

• Collection and site generation: Python 3, standard library only. No
  third-party packages, no paid APIs.
• Storage: SQLite, committed to the repository.
• Pages: static HTML, no framework and no build step. One file each. Dark mode,
  mobile layout, no external scripts.
• Automation: GitHub Actions — daily collection, tests, rebuild, deploy.
• Hosting: GitHub Pages. Free.

════════════════════════════════════════════════════════════════
TIME REQUIRED
════════════════════════════════════════════════════════════════

Zero on a normal day; it collects and republishes on its own.

Realistically, budget an hour every few weeks. Source sites occasionally change
their HTML and a parser needs updating — that is the real maintenance burden
and the main risk, so I am stating it plainly rather than letting you find out.
Each source is isolated in its own file and the tests tell you which one broke.

════════════════════════════════════════════════════════════════
WHAT IS INCLUDED IN THE SALE
════════════════════════════════════════════════════════════════

• The full repository: collection pipeline, parsers, tests, both page
  generators, and the GitHub Actions workflows
• The dataset as it stands, and all its history
• The deployed site, transferred to your own GitHub account or domain
• The published dev.to article that links to it
• 30 days of support for handover and any parser that breaks in that window

No domain is included — the site currently runs on a GitHub Pages subpath. A
buyer should point their own domain at it, which also lifts the directory
submissions that reject subdomains.

════════════════════════════════════════════════════════════════
REASON FOR SELLING
════════════════════════════════════════════════════════════════

I enjoy building collection pipelines and have no interest in running an ads
or subscription business on top of one. Someone who does will get more out of
this than I will.
