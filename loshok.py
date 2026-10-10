#!/usr/bin/env python3

import requests
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from rich.console import Console
from rich.table import Table
from rich.live import Live

console = Console()

# =========================
# НАСТРОЙКИ
# =========================

TARGET = "https://YOUR-DOMAIN.com/"

SOURCES = [
    "https://raw.githubusercontent.com/Moleway/Free-Proxy-List/main/http.txt",
    "https://raw.githubusercontent.com/Moleway/Free-Proxy-List/main/https.txt",
]

CHECK_TIMEOUT = 5
REQUEST_TIMEOUT = 10

# Максимум запросов через один прокси
REQUESTS_PER_PROXY = 1

# Пауза между циклами проверки списка
UPDATE_INTERVAL = 300

# Сколько прокси проверять одновременно
CHECK_WORKERS = 30

# Сколько прокси одновременно использовать для теста
TEST_WORKERS = 5

OUTPUT = "working_proxies.txt"

lock = threading.Lock()


# =========================
# ЗАГРУЗКА ПРОКСИ
# =========================

def download_proxies():

    proxies = set()

    for source in SOURCES:

        try:
            r = requests.get(source, timeout=15)
            r.raise_for_status()

            for line in r.text.splitlines():

                line = line.strip()

                if line and ":" in line:
                    proxies.add(line)

        except Exception as e:
            console.print(f"[red]Источник недоступен:[/red] {e}")

    return list(proxies)


# =========================
# ПРОВЕРКА ПРОКСИ
# =========================

def check_proxy(proxy):

    try:

        proxy_config = {
            "http": f"http://{proxy}",
            "https": f"http://{proxy}"
        }

        start = time.perf_counter()

        r = requests.get(
            "https://example.com",
            proxies=proxy_config,
            timeout=CHECK_TIMEOUT
        )

        latency = time.perf_counter() - start

        if r.status_code == 200:
            return proxy, latency

    except Exception:
        pass

    return None


def check_all(proxies):

    working = []

    console.print(
        f"\n[yellow]Проверяю {len(proxies)} прокси...[/yellow]"
    )

    with ThreadPoolExecutor(max_workers=CHECK_WORKERS) as executor:

        futures = [
            executor.submit(check_proxy, proxy)
            for proxy in proxies
        ]

        for future in as_completed(futures):

            result = future.result()

            if result:
                working.append(result)

    return sorted(working, key=lambda x: x[1])


# =========================
# СОХРАНЕНИЕ
# =========================

def save_proxies(proxies):

    with open(OUTPUT, "w") as f:

        for proxy, latency in proxies:
            f.write(proxy + "\n")


# =========================
# ТЕСТ САЙТА
# =========================

def test_proxy(proxy):

    result = {
        "proxy": proxy,
        "status": None,
        "latency": None,
        "error": False
    }

    try:

        proxy_config = {
            "http": f"http://{proxy}",
            "https": f"http://{proxy}"
        }

        start = time.perf_counter()

        r = requests.get(
            TARGET,
            proxies=proxy_config,
            timeout=REQUEST_TIMEOUT
        )

        result["status"] = r.status_code
        result["latency"] = (
            time.perf_counter() - start
        ) * 1000

    except Exception:

        result["error"] = True

    return result


# =========================
# ТЕСТ ВСЕХ ПРОКСИ
# =========================

def run_test(proxies):

    console.print(
        f"\n[cyan]Тестирую сайт через {len(proxies)} IP...[/cyan]\n"
    )

    results = []

    with ThreadPoolExecutor(max_workers=TEST_WORKERS) as executor:

        futures = []

        for proxy, _ in proxies:

            for _ in range(REQUESTS_PER_PROXY):

                futures.append(
                    executor.submit(test_proxy, proxy)
                )

        for future in as_completed(futures):

            result = future.result()

            results.append(result)

            proxy = result["proxy"]

            if result["error"]:

                console.print(
                    f"[red]ERROR[/red] {proxy}"
                )

            else:

                console.print(
                    f"[green]{result['status']}[/green] "
                    f"{proxy} "
                    f"{result['latency']:.0f} ms"
                )

    return results


# =========================
# СТАТИСТИКА
# =========================

def show_stats(results):

    codes = Counter()

    errors = 0
    latencies = []

    for result in results:

        if result["error"]:

            errors += 1
            continue

        codes[result["status"]] += 1

        if result["latency"] is not None:
            latencies.append(result["latency"])

    table = Table(title="RESULTS")

    table.add_column("Показатель")
    table.add_column("Значение")

    table.add_row(
        "Всего запросов",
        str(len(results))
    )

    table.add_row(
        "Ошибки соединения",
        str(errors)
    )

    for code, count in sorted(codes.items()):

        table.add_row(
            f"HTTP {code}",
            str(count)
        )

    if latencies:

        avg = sum(latencies) / len(latencies)

        table.add_row(
            "Средняя задержка",
            f"{avg:.0f} ms"
        )

    console.print()
    console.print(table)


# =========================
# MAIN
# =========================

def main():

    console.print(
        "\n[bold cyan]PROXY WEB TESTER[/bold cyan]"
    )

    console.print(
        f"Target: [yellow]{TARGET}[/yellow]"
    )

    while True:

        console.print(
            "\n[bold]Обновляю список прокси...[/bold]"
        )

        proxies = download_proxies()

        console.print(
            f"Получено: [cyan]{len(proxies)}[/cyan]"
        )

        working = check_all(proxies)

        console.print(
            f"[green]Рабочих: {len(working)}[/green]"
        )

        save_proxies(working)

        if working:

            results = run_test(working)

            show_stats(results)

        else:

            console.print(
                "[red]Рабочих прокси нет.[/red]"
            )

        console.print(
            f"\n[yellow]Следующее обновление через "
            f"{UPDATE_INTERVAL // 60} минут.[/yellow]"
        )

        time.sleep(UPDATE_INTERVAL)


if __name__ == "__main__":

    try:
        main()

    except KeyboardInterrupt:

        console.print(
            "\n[yellow]Остановлено.[/yellow]"
        )
      
