import asyncio
import json
import os
import re
from datetime import date
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import Stealth

OUTPUT_FILE = "./tmp/plus_bonus.json"
PLUS_BASE = "https://www.plus.nl"
PLUS_URL = f"{PLUS_BASE}/aanbiedingen"

# Regex to extract price from deal string like "2 VOOR 6.00" or "50 % KORTING"
_PRICE_RE = re.compile(r'[\d]+[.,]?\d*')


def _clean_text(raw: str) -> str:
    """Strip whitespace and normalise internal spaces."""
    return re.sub(r'\s+', ' ', raw).strip()


async def scrape_plus_bonus() -> list[dict]:
    results = []
    seen_hrefs: set[str] = set()

    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="nl-NL",
        )
        page = await context.new_page()

        print("🚀 Navigating to Plus aanbiedingen page...", flush=True)
        try:
            await page.goto(PLUS_URL, wait_until="load", timeout=30_000)
            print(f"✅ Page loaded: {await page.title()} | {page.url}", flush=True)

            # -- Cookie consent --------------------------------------------------
            # Plus uses a custom cookie modal (not OneTrust).
            for selector in [
                "button.btn-cookies-accept",
                "button.gtm-cookies-accept-all-btn",
                "button[class*='accept']",
                "button#onetrust-accept-btn-handler",
            ]:
                try:
                    btn = page.locator(selector)
                    await btn.wait_for(state="visible", timeout=3_000)
                    await btn.click()
                    print("✅ Cookies accepted.", flush=True)
                    break
                except PlaywrightTimeoutError:
                    continue
            else:
                print("ℹ️  No cookie banner found, continuing...", flush=True)

            # -- Scroll to trigger lazy-loaded sections --------------------------
            print("⏳ Scrolling to load all offer cards...", flush=True)
            await page.wait_for_timeout(3_000)

            # Plus uses infinite scroll; keep pressing End until no new cards appear.
            card_selector = "a[href*='/aanbiedingen/']"
            prev_count = 0
            for _ in range(10):
                await page.keyboard.press("End")
                await page.wait_for_timeout(1_500)
                current_count = await page.locator(card_selector).count()
                if current_count == prev_count:
                    break          # no new cards loaded
                prev_count = current_count

            await page.wait_for_selector(card_selector, timeout=20_000)
            cards = await page.locator(card_selector).all()
            print(f"📦 Found {len(cards)} offer cards — extracting details...", flush=True)

            for i, card in enumerate(cards):
                try:
                    # -- Deduplicate by href ------------------------------------
                    href = await card.get_attribute("href", timeout=3_000)
                    if not href or href in seen_hrefs:
                        continue
                    seen_hrefs.add(href)
                    url = f"{PLUS_BASE}{href}" if href.startswith("/") else href

                    # -- Product name ------------------------------------------
                    # Prefer aria-label on the card anchor (most reliable).
                    aria = await card.get_attribute("aria-label", timeout=2_000)
                    if aria:
                        name = _clean_text(aria)
                    else:
                        # Fallback: second visible text span (first is often the deal label)
                        spans = await card.locator("span").all()
                        name_raw = ""
                        for span in spans[1:3]:
                            txt = _clean_text(await span.inner_text(timeout=1_500))
                            if txt:
                                name_raw = txt
                                break
                        name = name_raw

                    # -- Deal label --------------------------------------------
                    # The first span inside the card is the promo badge
                    # e.g. "2 VOOR 6.00", "50 % KORTING", "1+1 GRATIS"
                    deal: str | None = None
                    first_span = card.locator("span").first
                    span_count = await card.locator("span").count()
                    if span_count > 0:
                        raw_deal = _clean_text(await first_span.inner_text(timeout=2_000))
                        deal = raw_deal if raw_deal else None

                    # -- Price -------------------------------------------------
                    # Only grab the FIRST price element to avoid concatenating
                    # current + original prices into garbage like "3. 74 7.493.74"
                    price: str | None = None
                    price_loc = card.locator(
                        "[class*='price'], [class*='Price'], [data-testid*='price']"
                    ).first
                    price_count = await card.locator(
                        "[class*='price'], [class*='Price'], [data-testid*='price']"
                    ).count()
                    if price_count > 0:
                        t = _clean_text(await price_loc.inner_text(timeout=1_500))
                        price = t if t else None

                    # -- Product image -----------------------------------------
                    img_el = card.locator("img").first
                    img_count = await card.locator("img").count()
                    image = (
                        await img_el.get_attribute("src", timeout=2_000)
                        if img_count > 0 else None
                    )

                    if not name:
                        continue

                    results.append({
                        "store": "Plus",
                        "name": name,
                        "deal": deal,
                        "price": price,
                        "url": url,
                        "image": image,
                        "scraped_date": date.today().isoformat(),
                    })

                    if (i + 1) % 20 == 0:
                        print(f"   ... processed {i + 1}/{len(cards)}", flush=True)

                except PlaywrightTimeoutError:
                    continue
                except Exception as e:
                    print(f"   ⚠️  Card {i} error: {e}", flush=True)
                    continue

        except PlaywrightTimeoutError as e:
            print(f"⏱️  Timeout: {e}", flush=True)
        except Exception as e:
            print(f"❌ Error: {e}", flush=True)
        finally:
            await browser.close()

    return results


if __name__ == "__main__":
    data = asyncio.run(scrape_plus_bonus())

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Done! {len(data)} items saved to {OUTPUT_FILE}", flush=True)
    print("\nSample (first 5):", flush=True)
    for item in data[:5]:
        deal_str = item["deal"] or "?"
        print(f"  🔥 {item['name']} — {deal_str}", flush=True)
