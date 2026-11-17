dev.to 게시글
https://dev.to/new

제목 아래 내용을 그대로 붙여넣으면 됩니다. dev.to 는 마크다운을 지원하므로
이 파일의 ** 기호가 그대로 굵게 표시됩니다 (레딧과 다릅니다).

태그 4개: datascience, webdev, startup, showdev

이 글이 중요한 이유: 레딧·HN 은 하루 반짝이고 끝나지만, 글은 검색에 남아
몇 달·몇 년 동안 사람을 데려옵니다.

════════════════════════════════════════════════════════════════
TITLE
════════════════════════════════════════════════════════════════

I collected 198 real software business sale prices. Small products sell at 8x revenue; big ones at 0.9x.

════════════════════════════════════════════════════════════════
BODY  (아래 ─── 줄 다음부터 끝까지)
════════════════════════════════════════════════════════════════
────────────────────────────────────────────────────────────────

Every marketplace shows you what sellers **ask**. Almost nobody publishes what
buyers actually **paid**.

That gap matters. Asking prices are aspirational — I found live listings at
28x and 31x annual revenue, which implies a payback period longer than most
marriages. Closed prices are the only honest signal, and they are scattered
across sold-listing pages, broker archives and the occasional founder post.

So I collected them: **[198 closed deals](https://kwonhyundong.github.io/sold-for/)**,
from $1,000 weekend projects to a $2B acquisition.

Here is what the data says.

## 1. Small products clear at high multiples. Big ones don't.

This was the opposite of what I expected.

| Deal size | Deals | Median × annual revenue |
|---|---|---|
| Under $10k | 11 | **8.0×** |
| $100k – $1M | 159 | **0.9×** |
| $1M+ | 24 | **1.65×** |

A tiny product clears at many times what it earns. A real business clears at
roughly one year of revenue.

The reason appears to be a floor. Prices do not go meaningfully below ~$1,000
no matter how little a product earns, so when revenue is near zero the
multiple explodes. It is not that small products are valuable; it is that
there is a minimum price for a working, transferable thing.

## 2. Products earning almost nothing still sell

Seven products in the dataset earned under **$600/year** and sold anyway:

```
$1,000   $1,000   $1,000   $1,050   $2,000   $5,000   $5,000
```

Median $1,050.

If you have something small you stopped maintaining, that is roughly what it
is worth to someone who wants a running start. Not life-changing. Also not
zero, which is what most abandoned side projects currently return.

## 3. Web products clear far better than mobile apps

This one has a clear mechanism.

| Product | Annual revenue | Sold for | Multiple |
|---|---|---|---|
| Photo cleaner (iOS) | $1,384 | $1,000 | 0.7× |
| Old photo restore (iOS) | $1,900 | $2,000 | 1.1× |
| Energy drink scanner (iOS) | $487 | $1,050 | 2.2× |
| Local business outreach (web) | $250 | $2,000 | **8.0×** |
| Language learning (web) | $200 | $5,000 | **25×** |

The iOS apps earned more and sold for less. A buyer taking over a web app
changes a DNS record and a Stripe key. A buyer taking over an iOS app
inherits an App Store account transfer, a review process, and a platform that
can reject the next build.

If you are building something to sell, this is the single most actionable row
in the dataset: **build on the web**.

## How the data was collected

Only closed deals. Asking prices are excluded deliberately — including those
28x listings would corrupt every median above.

Three sources:

- Marketplace exit prices, where a marketplace publishes what a listing
  actually sold for
- Broker closed-deal records
- Founder disclosures in public posts, mined by regex and then **read
  individually before being accepted**

That last step matters more than it sounds. Automated extraction got things
wrong in ways that would have quietly poisoned the dataset:

- `"I sold my $0 revenue SaaS side project for $4.5k"` was first recorded as a
  **$0 sale**, because the first dollar amount in the title was the revenue
  figure, not the price.
- `"My bootstrapped SaaS was acquired for $800k"` was recorded as the author
  **buying**. Passive voice means the author sold.

Of 27 mined candidates, 2 survived review with a price attached. Most founders
simply never say what they sold for, which is exactly why marketplace and
broker records carry the volume.

I also tried mining Hacker News **comments**, on the theory that prices get
disclosed there more often than in titles. 307 comments produced 4 that passed
a product-context filter, and all four were false positives — a PDP-11 sold
for $25, a concert ticket, a gold bar, some Amazon stock. Comments carry
prices without carrying context. That path was abandoned.

## What this cannot tell you

- The **under-$10k band has only 10 deals with revenue attached**. Treat the
  8× as a hint, not a number.
- Broker deals skew the dataset toward $100k+.
- Comparables mix SaaS, content sites, apps and ecommerce, which sell at very
  different multiples of the same revenue. Margin matters more than revenue
  and is almost never published.

That last limitation is why the
[valuation page](https://kwonhyundong.github.io/sold-for/worth/) shows you the
actual comparable deals rather than just returning a number. A formula picks a
band and can be quietly wrong about which one — mine was, on its first
version, reporting a range drawn from the "under $10k" band for a business
with $55,891 of revenue. Comparables cannot fail that way, and you can check
the comparison yourself.

## It is free and it updates itself

No signup, no ads, no tracking, nothing to buy. A scheduled job re-collects
the sources daily, re-runs the extraction tests, and republishes.

If you have sold something and are willing to say what it went for, or you
know a closed-deal source I have missed, I would like to add it.

**[See the data →](https://kwonhyundong.github.io/sold-for/)**
