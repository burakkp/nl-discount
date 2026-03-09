import asyncio
import json
import os
from datetime import date
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import Stealth

OUTPUT_FILE = "./tmp/jumbo_bonus.json"
JUMBO_BASE = "https://www.jumbo.com"
JUMBO_URL = f"{JUMBO_BASE}/aanbiedingen"


async def scrape_jumbo_bonus() -> list[dict]:
    results = []

    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="nl-NL",
        )
        page = await context.new_page()

        print("🚀 Navigating to Jumbo aanbiedingen page...", flush=True)
        try:
            await page.goto(JUMBO_URL, wait_until="load", timeout=30_000)
            print(f"✅ Page loaded: {await page.title()} | {page.url}", flush=True)

            # Handle cookie consent — Jumbo uses OneTrust
            try:
                cookie_btn = page.locator("button#onetrust-accept-btn-handler")
                await cookie_btn.wait_for(state="visible", timeout=5_000)
                await cookie_btn.click()
                print("✅ Cookies accepted.", flush=True)
            except PlaywrightTimeoutError:
                # Try Jumbo's own cookie button as fallback
                try:
                    cookie_btn = page.locator("button[data-testid='accept-cookies']")
                    await cookie_btn.wait_for(state="visible", timeout=3_000)
                    await cookie_btn.click()
                    print("✅ Cookies accepted (fallback).", flush=True)
                except PlaywrightTimeoutError:
                    print("ℹ️  No cookie banner, continuing...", flush=True)

            # Scroll to trigger lazy-loaded promotion cards
            print("⏳ Scrolling to load all promotion cards...", flush=True)
            await page.wait_for_timeout(3_000)
            for _ in range(5):
                await page.keyboard.press("End")
                await page.wait_for_timeout(1_500)

            # Main card selector confirmed from live page: data-testid="promotion-card"
            card_selector = '[data-testid="promotion-card"]'
            await page.wait_for_selector(card_selector, timeout=20_000)

            cards = await page.locator(card_selector).all()
            print(f"📦 Found {len(cards)} promotion cards — extracting details...", flush=True)

            for i, card in enumerate(cards):
                try:
                    # Product name: first jum-heading inside the card
                    name_el = card.locator('[data-testid="jum-heading"]').first
                    name = (await name_el.inner_text(timeout=3_000)).strip()

                    # Deal label: jum-tag holds "1+1 gratis", "2e halve prijs", etc.
                    # There may be multiple tags; grab them all and join
                    tags = card.locator('[data-testid="jum-tag"]')
                    tag_count = await tags.count()
                    deal_parts = []
                    for t in range(tag_count):
                        text = (await tags.nth(t).inner_text(timeout=2_000)).strip()
                        # Normalize multi-line tags (e.g. "Combikorting\n2 voor 4,50")
                        text = " | ".join(line.strip() for line in text.splitlines() if line.strip())
                        if text:
                            deal_parts.append(text)
                    deal = " | ".join(deal_parts) if deal_parts else None

                    # Product link: jum-router-link inside card
                    link_el = card.locator('[data-testid="jum-router-link"]').first
                    href = await link_el.get_attribute("href", timeout=2_000)
                    url = f"{JUMBO_BASE}{href}" if href and href.startswith("/") else href

                    # Product image
                    img_el = card.locator('[data-testid="jum-card-image"] img').first
                    img_count = await card.locator('[data-testid="jum-card-image"] img').count()
                    img_src = await img_el.get_attribute("src", timeout=2_000) if img_count > 0 else None

                    results.append({
                        "store": "Jumbo",
                        "name": name,
                        "deal": deal,
                        "url": url,
                        "image": img_src,
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
    data = asyncio.run(scrape_jumbo_bonus())

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Done! {len(data)} items saved to {OUTPUT_FILE}", flush=True)
    print("\nSample (first 5):", flush=True)
    for item in data[:5]:
        print(f"  🔥 {item['name']} — {item['deal']}", flush=True)
