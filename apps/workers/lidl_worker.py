import asyncio
import json
import os
from datetime import date
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import Stealth

OUTPUT_FILE = "./tmp/lidl_bonus.json"
LIDL_BASE = "https://www.lidl.nl"
LIDL_URL = f"{LIDL_BASE}/c/aanbiedingen/a10008785"


async def scrape_lidl_bonus() -> list[dict]:
    results = []

    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="nl-NL",
        )
        page = await context.new_page()

        print("🚀 Navigating to Lidl aanbiedingen page...", flush=True)
        try:
            await page.goto(LIDL_URL, wait_until="load", timeout=30_000)
            print(f"✅ Page loaded: {await page.title()} | {page.url}", flush=True)

            # Handle cookie consent
            for selector in [
                "button#onetrust-accept-btn-handler",
                "button.cookie-alert-extended-button",
                "[data-tracking-label='accept-all']",
            ]:
                try:
                    btn = page.locator(selector)
                    await btn.wait_for(state="visible", timeout=3_000)
                    await btn.click()
                    print(f"✅ Cookies accepted.", flush=True)
                    break
                except PlaywrightTimeoutError:
                    continue
            else:
                print("ℹ️  No cookie banner, continuing...", flush=True)

            # Scroll to trigger lazy-loaded tiles
            print("⏳ Scrolling to load all offer tiles...", flush=True)
            await page.wait_for_timeout(3_000)
            for _ in range(5):
                await page.keyboard.press("End")
                await page.wait_for_timeout(1_500)

            # Card selector confirmed from DOM probe: div.odsc-tile (28 cards)
            card_selector = "div.odsc-tile"
            await page.wait_for_selector(card_selector, timeout=20_000)

            cards = await page.locator(card_selector).all()
            print(f"📦 Found {len(cards)} offer tiles — extracting details...", flush=True)

            for i, card in enumerate(cards):
                try:
                    # Product name — from the visible link text or title div
                    name_el = card.locator("div.product-grid-box__title").first
                    name_count = await card.locator("div.product-grid-box__title").count()
                    if name_count > 0:
                        name = (await name_el.inner_text(timeout=3_000)).strip()
                    else:
                        # Fallback: visible text of the anchor link
                        link_text = await card.locator("a.odsc-tile__link").first.inner_text(timeout=3_000)
                        name = link_text.strip()

                    # Deal/description — the subtitle below the title
                    desc_el = card.locator("div.product-grid-box__desc").first
                    desc_count = await card.locator("div.product-grid-box__desc").count()
                    deal_desc = (await desc_el.inner_text(timeout=2_000)).strip() if desc_count > 0 else None

                    # Price — the main price value
                    price_el = card.locator("div.ods-price__value").first
                    price_count = await card.locator("div.ods-price__value").count()
                    price = (await price_el.inner_text(timeout=2_000)).strip() if price_count > 0 else None

                    # Price footer — often shows "per stuk", "per kg", promotion badge
                    footer_el = card.locator("div.ods-price__footer").first
                    footer_count = await card.locator("div.ods-price__footer").count()
                    price_footer = (await footer_el.inner_text(timeout=2_000)).strip() if footer_count > 0 else None

                    # Product URL
                    href = await card.locator("a.odsc-tile__link").first.get_attribute("href", timeout=2_000)
                    url = f"{LIDL_BASE}{href}" if href and href.startswith("/") else href

                    # Product image
                    img_el = card.locator("img").first
                    img_count = await card.locator("img").count()
                    image = await img_el.get_attribute("src", timeout=2_000) if img_count > 0 else None

                    # Combine price + footer as the deal string
                    deal_parts = [p for p in [price, price_footer] if p]
                    deal = " — ".join(deal_parts) if deal_parts else deal_desc

                    results.append({
                        "store": "Lidl",
                        "name": name,
                        "deal": deal,
                        "description": deal_desc,
                        "price": price,
                        "url": url,
                        "image": image,
                        "scraped_date": date.today().isoformat(),
                    })

                    if (i + 1) % 10 == 0:
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
    data = asyncio.run(scrape_lidl_bonus())

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Done! {len(data)} items saved to {OUTPUT_FILE}", flush=True)
    print("\nSample (first 5):", flush=True)
    for item in data[:5]:
        print(f"  🔥 {item['name']} — {item['deal']}", flush=True)
