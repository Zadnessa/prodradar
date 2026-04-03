"""Браузерный этап для получения динамических данных до запуска парсеров."""

import asyncio
import logging
import re
import time

from playwright.async_api import async_playwright

import config


async def fetch_browser_secrets():
    """Собирает buildId/cookies с защищённых сайтов одним браузерным запуском."""
    started_at = time.time()
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
            user_agent=config.REQUEST_HEADERS["User-Agent"],
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
                    await asyncio.sleep(5)
                    html = await page.content()
                    match = re.search(r'"buildId"\s*:\s*"([^"]+)"', html)
                    build_id = match.group(1) if match else None
                    results[task["key"]] = build_id
                    logging.info("%s: %s", task["key"], build_id or "не найден")
                elif task["extract"] == "cookies":
                    cookies = await page.context.cookies()
                    results[task["key"]] = cookies
                    cookie_names = [str(cookie.get("name") or "") for cookie in cookies if cookie.get("name")]
                    logging.info(
                        "%s: получено %s cookies [%s]",
                        task["key"],
                        len(cookies),
                        ", ".join(cookie_names),
                    )
            except Exception as exc:
                results[task["key"]] = None
                logging.warning("Браузерное задание %s не удалось: %s", task["key"], exc)

            if idx < len(tasks) - 1:
                await asyncio.sleep(2)

        await browser.close()
        elapsed = time.time() - started_at
        logging.info("Браузерный этап завершён за %.1f сек", elapsed)

    return results
