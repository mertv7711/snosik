import asyncio
import aiohttp
import requests
import csv
import ipaddress
import time
from urllib.parse import urlparse

RAW_URL = (
    "https://raw.githubusercontent.com/"
    "6yyn/free-proxy-list/blob/main/proxies.txt"
)


def get_test_url():
    url = input("Введи HTTPS-ссылку на свой сайт: ").strip()
    parsed = urlparse(url)

    if parsed.scheme != "https" or not parsed.hostname:
        raise SystemExit(
            "Ошибка: укажи корректный URL, начинающийся с https://"
        )

    return url


def load_proxies():
    response = requests.get(RAW_URL, timeout=15)
    response.raise_for_status()

    proxies = []

    for line in response.text.splitlines():
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        try:
            ip, port = line.rsplit(":", 1)
            ipaddress.ip_address(ip)
            port = int(port)

            if not 1 <= port <= 65535:
                continue

            proxies.append(f"http://{ip}:{port}")

        except ValueError:
            print(f"Пропуск некорректной строки: {line}")

    return list(dict.fromkeys(proxies))


async def check_proxy(proxy, test_url):
    timeout = aiohttp.ClientTimeout(total=10)
    started = time.perf_counter()

    try:
        async with aiohttp.ClientSession(
            timeout=timeout
        ) as session:
            async with session.get(
                test_url,
                proxy=proxy,
            ) as response:
                await response.read()

                return {
                    "proxy": proxy,
                    "status": response.status,
                    "latency_ms": round(
                        (time.perf_counter() - started) * 1000, 2
                    ),
                    "error": "",
                }

    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
        return {
            "proxy": proxy,
            "status": 0,
            "latency_ms": round(
                (time.perf_counter() - started) * 1000, 2
            ),
            "error": type(exc).__name__,
        }


async def main():
    test_url = get_test_url()

    print("\nЗагружаю список прокси из GitHub...")

    try:
        proxies = load_proxies()
    except requests.RequestException as exc:
        raise SystemExit(f"Не удалось загрузить список: {exc}")

    if not proxies:
        raise SystemExit("В файле не найдено корректных прокси.")

    print(f"Найдено прокси: {len(proxies)}")
    print(f"Тестовый URL: {test_url}\n")

    results = []

    # Последовательная проверка всех прокси.
    for index, proxy in enumerate(proxies, start=1):
        result = await check_proxy(proxy, test_url)
        results.append(result)

        print(
            f"[{index}/{len(proxies)}] "
            f"status={result['status']} "
            f"latency={result['latency_ms']} ms "
            f"proxy={proxy}"
        )

        await asyncio.sleep(0.5)

    with open(
        "proxy_report.csv",
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "proxy",
                "status",
                "latency_ms",
                "error",
            ],
        )
        writer.writeheader()
        writer.writerows(results)

    working = sum(
        200 <= result["status"] < 400
        for result in results
    )

    print("\n=== Итоги ===")
    print(f"Всего прокси: {len(results)}")
    print(f"Успешные HTTP-ответы: {working}")
    print(f"Остальные ответы или ошибки: {len(results) - working}")
    print("Отчёт сохранён в proxy_report.csv")


if __name__ == "__main__":
    asyncio.run(main())
