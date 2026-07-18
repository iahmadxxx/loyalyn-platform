"""Browser/mobile smoke test for the Loyalyn V6 single-brand studio.

Run this against a deployed QA URL because some build environments block
Chromium access to localhost/private networks.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from playwright.async_api import async_playwright

WEB = os.getenv("LOYALYN_WEB_URL", "http://127.0.0.1:3000").rstrip("/")
EMAIL = os.getenv("LOYALYN_MANAGER_EMAIL") or os.getenv("LOYALYN_OWNER_EMAIL")
PASSWORD = os.getenv("LOYALYN_MANAGER_PASSWORD") or os.getenv("LOYALYN_OWNER_PASSWORD")
OUT = Path(os.getenv("LOYALYN_QA_SCREENSHOTS", "/tmp/loyalyn-v6-ui"))
OUT.mkdir(parents=True, exist_ok=True)
TABS = ["استوديو البطاقات", "العملاء", "السكان السريع", "سجل العمليات", "الإعدادات"]


async def login(page) -> None:
    await page.goto(f"{WEB}/login", wait_until="domcontentloaded")
    await page.fill("input[type=email]", EMAIL or "")
    await page.fill("input[type=password]", PASSWORD or "")
    await page.click('button:has-text("دخول")')
    await page.wait_for_url("**/admin", timeout=25_000)
    await page.wait_for_selector(".v6-shell", timeout=25_000)


async def open_menu(page) -> None:
    if not await page.locator(".v6-sidebar").evaluate("e => e.classList.contains('open')"):
        await page.click('button[aria-label="فتح القائمة"]')
        await page.wait_for_selector(".v6-sidebar.open")


async def validate_page(page, label: str, index: int) -> None:
    await open_menu(page)
    item = page.locator(".v6-sidebar nav button", has_text=label).first
    if await item.count() != 1:
        raise AssertionError(f"missing V6 tab: {label}")
    await item.click()
    await page.wait_for_timeout(450)
    text = await page.locator("body").inner_text()
    if "Application error" in text or "client-side exception" in text:
        raise AssertionError(f"client crash on {label}")
    await page.screenshot(path=str(OUT / f"mobile-{index}-{label}.png"), full_page=True)


async def main() -> None:
    if not EMAIL or not PASSWORD:
        raise SystemExit("Set LOYALYN_MANAGER_EMAIL/LOYALYN_MANAGER_PASSWORD for a dedicated QA account.")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            executable_path=os.getenv("CHROMIUM_PATH", "/usr/bin/chromium"),
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(viewport={"width": 390, "height": 844}, locale="ar-QA")
        page = await context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await login(page)
        for index, label in enumerate(TABS):
            await validate_page(page, label, index)
        overflow = await page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth + 2")
        if overflow:
            raise AssertionError("horizontal overflow on V6 mobile interface")
        small_inputs = await page.locator("input:visible, select:visible, textarea:visible").evaluate_all(
            "els => els.map(e => parseFloat(getComputedStyle(e).fontSize)).filter(x => x < 15.9)"
        )
        if small_inputs:
            raise AssertionError(f"mobile form font below 16px: {small_inputs[:8]}")
        if errors:
            raise AssertionError(f"browser errors: {errors[:5]}")
        await browser.close()
    print(json.dumps({"ok": True, "tabs": TABS, "overflow": False, "screenshots": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
