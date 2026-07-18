"""Browser/mobile smoke test for a running Loyalyn instance.

Requires Playwright + Chromium and dedicated QA accounts. It does not create or
modify production records; it signs in, opens allowed screens and validates the
responsive shell and employee privacy flow.

Example:
    LOYALYN_WEB_URL=http://127.0.0.1:3000 \
    LOYALYN_OWNER_EMAIL=owner@example.com \
    LOYALYN_OWNER_PASSWORD=OwnerPass123! \
    LOYALYN_EMPLOYEE_EMAIL=hadi@example.com \
    LOYALYN_EMPLOYEE_PASSWORD=HadiPass123! \
    python scripts/qa_mobile_ui.py
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from playwright.async_api import async_playwright

WEB = os.getenv("LOYALYN_WEB_URL", "http://127.0.0.1:3000").rstrip("/")
OWNER_EMAIL = os.getenv("LOYALYN_OWNER_EMAIL")
OWNER_PASSWORD = os.getenv("LOYALYN_OWNER_PASSWORD")
EMPLOYEE_EMAIL = os.getenv("LOYALYN_EMPLOYEE_EMAIL")
EMPLOYEE_PASSWORD = os.getenv("LOYALYN_EMPLOYEE_PASSWORD")
OUT = Path(os.getenv("LOYALYN_QA_SCREENSHOTS", "/tmp/loyalyn-v41-ui"))
OUT.mkdir(parents=True, exist_ok=True)
OWNER_TABS = [
    "نظرة عامة", "البراندات", "الفروع", "العملاء", "الموظفون", "بطاقات الأختام",
    "السكان السريع", "محرك الولاء", "استوديو البطاقة", "الإشعارات والحملات",
    "سجل التدقيق", "شهادة Apple المركزية",
]


async def login(page, email: str, password: str) -> None:
    await page.goto(f"{WEB}/login", wait_until="domcontentloaded")
    await page.fill("input[type=email]", email)
    await page.fill("input[type=password]", password)
    await page.click('button:has-text("دخول")')
    await page.wait_for_url("**/admin", timeout=20_000)
    await page.wait_for_selector(".topbar", timeout=20_000)


async def open_mobile_nav(page) -> None:
    opened = await page.locator(".sidebar").evaluate("e => e.classList.contains('open')")
    if not opened:
        await page.click(".mobile-menu-btn")
        await page.wait_for_selector(".sidebar.open")


async def check_owner(browser) -> dict:
    context = await browser.new_context(viewport={"width": 390, "height": 844}, locale="ar-QA")
    page = await context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    await login(page, OWNER_EMAIL or "", OWNER_PASSWORD or "")
    for index, label in enumerate(OWNER_TABS):
        await open_mobile_nav(page)
        nav = page.locator(".sidebar .nav-btn", has_text=label).first
        if await nav.count() != 1:
            raise AssertionError(f"missing owner tab: {label}")
        await nav.click()
        await page.wait_for_timeout(550)
        text = await page.locator("body").inner_text()
        if "Application error" in text or "client-side exception" in text:
            raise AssertionError(f"client crash on {label}")
        if index in {0, 5, 6, 8}:
            await page.screenshot(path=str(OUT / f"mobile-{index}.png"), full_page=True)
    overflow = await page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth + 2")
    if overflow:
        raise AssertionError("horizontal overflow on mobile")
    undersized = await page.locator("button:visible").evaluate_all(
        "els => els.map(e => ({text:(e.innerText||e.getAttribute('aria-label')||'').trim(), h:e.getBoundingClientRect().height}))"
        ".filter(x => x.h > 0 && x.h < 39)"
    )
    if undersized:
        raise AssertionError(f"undersized visible mobile buttons: {undersized[:8]}")
    small_fonts = await page.locator("input:visible, select:visible, textarea:visible").evaluate_all(
        "els => els.map(e => parseFloat(getComputedStyle(e).fontSize)).filter(x => x < 15.9)"
    )
    if small_fonts:
        raise AssertionError(f"mobile form font below 16px: {small_fonts[:8]}")
    await context.close()
    return {"tabs": len(OWNER_TABS), "overflow": False, "errors": errors}


async def check_employee(browser) -> dict | None:
    if not EMPLOYEE_EMAIL or not EMPLOYEE_PASSWORD:
        return None
    context = await browser.new_context(viewport={"width": 390, "height": 844}, locale="ar-QA")
    page = await context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    await login(page, EMPLOYEE_EMAIL, EMPLOYEE_PASSWORD)
    await open_mobile_nav(page)
    labels = await page.locator(".sidebar .nav-btn:not(.danger) span").all_inner_texts()
    if labels != ["نظرة عامة", "العملاء", "السكان السريع"]:
        raise AssertionError(f"unexpected default employee navigation: {labels}")
    await page.locator(".sidebar .nav-btn", has_text="العملاء").click()
    await page.wait_for_timeout(550)
    text = await page.locator("body").inner_text()
    if "اكتب حرفين على الأقل" not in text or "Application error" in text:
        raise AssertionError("employee customer-search screen is not safe")
    await open_mobile_nav(page)
    await page.locator(".sidebar .nav-btn", has_text="السكان السريع").click()
    await page.wait_for_timeout(550)
    text = await page.locator("body").inner_text()
    if "Application error" in text:
        raise AssertionError("employee scan screen crashed")
    overflow = await page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth + 2")
    if overflow:
        raise AssertionError("employee mobile screen overflows horizontally")
    await page.screenshot(path=str(OUT / "mobile-employee-scan.png"), full_page=True)
    await context.close()
    return {"tabs": labels, "overflow": False, "errors": errors}


async def main() -> None:
    if not OWNER_EMAIL or not OWNER_PASSWORD:
        raise SystemExit("Set LOYALYN_OWNER_EMAIL and LOYALYN_OWNER_PASSWORD for the dedicated QA account.")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            executable_path=os.getenv("CHROMIUM_PATH", "/usr/bin/chromium"),
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        owner = await check_owner(browser)
        employee = await check_employee(browser)
        await browser.close()
    print(json.dumps({"ok": True, "owner": owner, "employee": employee, "screenshots": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
