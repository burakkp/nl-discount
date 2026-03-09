import asyncio
import json
import os
from datetime import date
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import Stealth

OUTPUT_FILE = "./tmp/aldi_bonus.json"
ALDI_BASE = "https://www.aldi.nl"
ALDI_URL = f"{ALDI_BASE}/aanbiedingen.html"


async def scrape_aldi_bonus() -> list[dict]:
    results = []

    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="nl-NL",
        )
        page = await context.new_page()

        print("🚀 Navigating to Aldi aanbiedingen page...", flush=True)
        try:
            await page.goto(ALDI_URL, wait_until="load", timeout=30_000)
            print(f"✅ Page loaded: {await page.title()}", flush=True)

            # Handle cookie consent
            for selector in [
                "button#onetrust-accept-btn-handler",
                "button[class*='accept']",
                ".accept-cookies",
            ]:
                try:
                    btn = page.locator(selector)
                    await btn.wait_for(state="visible", timeout=2_000)
                    await btn.click()
                    print("✅ Cookies accepted.", flush=True)
                    break
                except PlaywrightTimeoutError:
                    continue
            else:
                print("ℹ️  No cookie banner, continuing...", flush=True)

            # Scroll to trigger lazy-loaded tiles
            print("⏳ Scrolling to load all product tiles...", flush=True)
            await page.wait_for_timeout(3_000)
            for _ in range(5):
                await page.keyboard.press("End")
                await page.wait_for_timeout(1_500)

            # Use div.product-tile as root (193 items) so the action link and image
            # are within scope — the data-testid content div is a child of this element.
            card_selector = 'div.product-tile'
            await page.wait_for_selector(card_selector, timeout=20_000)

            cards = await page.locator(card_selector).all()
            print(f"📦 Found {len(cards)} product tiles — extracting details...", flush=True)

            for i, card in enumerate(cards):
                try:
                    # Brand name — data-testid suffix: brand-name
                    brand_els = await card.locator('[data-testid$="brand-name"]').all()
                    brand = (await brand_els[0].inner_text(timeout=2_000)).strip() if brand_els else None

                    # Product name — data-testid suffix: product-name
                    name_els = await card.locator('[data-testid$="product-name"]').all()
                    if not name_els:
                        continue
                    name = (await name_els[0].inner_text(timeout=2_000)).strip()

                    # Current (sale) price — data-testid suffix: tag-current-price-amount
                    price_els = await card.locator('[data-testid$="tag-current-price-amount"]').all()
                    price = (await price_els[0].inner_text(timeout=2_000)).strip() if price_els else None

                    # Promo label — e.g. "1+1 GRATIS", "2e HALVE PRIJS"
                    promo_els = await card.locator('[data-testid$="tag-promo-label"]').all()
                    promo = (await promo_els[0].inner_text(timeout=2_000)).strip() if promo_els else None

                    # Product URL — a.product-tile__action
                    link_els = await card.locator("a.product-tile__action").all()
                    href = await link_els[0].get_attribute("href", timeout=2_000) if link_els else None
                    url = f"{ALDI_BASE}{href}" if href and href.startswith("/") else href

                    # Product image
                    img_els = await card.locator("img").all()
                    image = await img_els[0].get_attribute("src", timeout=2_000) if img_els else None

                    # Build deal string: use promo label if present, otherwise just price
                    deal = promo if promo else price

                    # Full product name combining brand + name
                    full_name = f"{brand} {name}".strip() if brand else name

                    results.append({
                        "store": "Aldi",
                        "name": full_name,
                        "brand": brand,
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
    data = asyncio.run(scrape_aldi_bonus())

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Done! {len(data)} items saved to {OUTPUT_FILE}", flush=True)
    print("\nSample (first 5):", flush=True)
    for item in data[:5]:
        print(f"  🔥 {item['name']} — {item['deal']}", flush=True)
