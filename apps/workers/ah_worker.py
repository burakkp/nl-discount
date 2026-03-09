import asyncio
import json
import os
import re
from datetime import date
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import Stealth

OUTPUT_FILE = "./tmp/ah_bonus.json"
AH_BASE = "https://www.ah.nl"


def parse_aria_label(aria_label: str) -> dict:
    """
    Parse the aria-label string into structured fields.

    AH aria-label format (comma-separated):
      "Klikbaar:<name>, <deal>, [Bijv. <example>], [van <orig_price>], [voor <price>]"

    Examples:
      "Klikbaar:AH Courgette, 2 voor 1.39"
      "Klikbaar:Stim-u-dent Tandenstokers, 2+2 gratis, Bijv. 4 x 100 stuks, van 12.36, voor 6.18"
    """
    clean = aria_label.replace("Klikbaar:", "").strip()
    parts = [p.strip() for p in clean.split(",")]

    result = {
        "name": parts[0] if len(parts) > 0 else None,
        "deal": parts[1] if len(parts) > 1 else None,
        "example": None,
        "original_price": None,
        "discount_price": None,
    }

    for part in parts[2:]:
        p = part.strip()
        if p.lower().startswith("bijv."):
            result["example"] = p[5:].strip()
        elif p.lower().startswith("van "):
            result["original_price"] = p[4:].strip()
        elif p.lower().startswith("voor "):
            result["discount_price"] = p[5:].strip()

    return result


async def scrape_ah_bonus() -> list[dict]:
    results = []

    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="nl-NL",
        )
        page = await context.new_page()

        print("🚀 Navigating to Albert Heijn Bonus page...", flush=True)
        try:
            await page.goto(f"{AH_BASE}/bonus", wait_until="load", timeout=30_000)
            print(f"✅ Page loaded: {await page.title()}", flush=True)

            # Handle cookie consent (OneTrust)
            try:
                cookie_button = page.locator("button#onetrust-accept-btn-handler")
                await cookie_button.wait_for(state="visible", timeout=5_000)
                await cookie_button.click()
                print("✅ Cookies accepted.", flush=True)
            except PlaywrightTimeoutError:
                print("ℹ️  No cookie banner, continuing...", flush=True)

            # Scroll to trigger lazy-loaded cards
            print("⏳ Scrolling to load all bonus products...", flush=True)
            await page.wait_for_timeout(3_000)
            for i in range(5):
                await page.keyboard.press("End")
                await page.wait_for_timeout(1_500)

            card_selector = 'a[class*="promotion-card_root"]'
            await page.wait_for_selector(card_selector, timeout=20_000)

            cards = await page.locator(card_selector).all()
            print(f"📦 Found {len(cards)} bonus items — extracting details...", flush=True)

            for i, card in enumerate(cards):
                try:
                    aria_label = await card.get_attribute("aria-label", timeout=3_000)
                    href = await card.get_attribute("href", timeout=3_000)

                    if not aria_label:
                        continue

                    parsed = parse_aria_label(aria_label)
                    parsed["url"] = f"{AH_BASE}{href}" if href else None
                    parsed["store"] = "Albert Heijn"
                    parsed["scraped_date"] = date.today().isoformat()

                    results.append(parsed)

                    if (i + 1) % 20 == 0:
                        print(f"   ... processed {i + 1}/{len(cards)}", flush=True)

                except PlaywrightTimeoutError:
                    continue

        except PlaywrightTimeoutError as e:
            print(f"⏱️  Timeout: {e}", flush=True)
        except Exception as e:
            print(f"❌ Error: {e}", flush=True)
        finally:
            await browser.close()

    return results


if __name__ == "__main__":
    data = asyncio.run(scrape_ah_bonus())

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Done! {len(data)} items saved to {OUTPUT_FILE}", flush=True)
    print("\nSample (first 5):", flush=True)
    for item in data[:5]:
        deal_str = item["deal"] or "?"
        price_str = f"  (was {item['original_price']}, now {item['discount_price']})" if item["discount_price"] else ""
        print(f"  🔥 {item['name']} — {deal_str}{price_str}", flush=True)