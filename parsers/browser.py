"""Браузерный этап для получения динамических данных до запуска парсеров."""

import asyncio
import logging
import re

from playwright.async_api import async_playwright


async def fetch_browser_secrets():
    """Собирает buildId/cookies с защищённых сайтов одним браузерным запуском."""
    tasks = [
        {
            "key": "sberhealth_build_id",
            "url": "https://vacancy.sberhealth.ru/vacancies",
            "extract": "html",
        },
        {
            "key": "cian_cookies",
            "url": "https://www.cian.ru/vacancies/",
            "extract": "cookies",
        },
    ]

    results = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="ru-RU",
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = await context.new_page()

        for idx, task in enumerate(tasks):
            try:
                await page.goto(task["url"], timeout=30_000)
                await page.wait_for_load_state("networkidle")

                if task["extract"] == "html":
                    html = await page.content()
                    match = re.search(r'"buildId"\s*:\s*"([^"]+)"', html)
                    results[task["key"]] = match.group(1) if match else None
                elif task["extract"] == "cookies":
                    results[task["key"]] = await page.context.cookies()
            except Exception as exc:
                results[task["key"]] = None
                logging.warning("Браузерное задание %s не удалось: %s", task["key"], exc)

            if idx < len(tasks) - 1:
                await asyncio.sleep(2)

        await browser.close()

    return results
