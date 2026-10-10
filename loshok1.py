#!/usr/bin/env python3
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from urllib.parse import urlparse
import requests
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
console = Console()
SOURCES = [
    "https://raw.githubusercontent.com/Moleway/Free-Proxy-List/main/http.txt",
    "https://raw.githubusercontent.com/Moleway/Free-Proxy-List/main/https.txt",
]
CHECK_URL = "https://example.com"
OUTPUT = "working_proxies.txt"
CHECK_TIMEOUT = 5
REQUEST_TIMEOUT = 10
MAX_CHECK_WORKERS = 30
lock = threading.Lock()
def ask_settings():
    console.print(Panel(
        "[bold cyan]PROXY WEB TESTER[/bold cyan]\n"
        "Проверка публичных HTTP-прокси",
        border_style="cyan"
    ))
    target = input("URL твоего сайта: ").strip()
    if not target.startswith(("http://", "https://")):
        console.print("[red]Нужен полный URL с http:// или https://[/red]")
        return None
    parsed = urlparse(target)
    if not parsed.hostname:
        console.print("[red]Некорректный URL[/red]")
        return None
    try:
        total = int(input("Количество запросов (1–100, по умолчанию 10): ") or 10)
        workers = int(input("Одновременные запросы (1–5, по умолчанию 2): ") or 2)
        interval = int(input("Интервал обновления, секунд (минимум 60, по умолчанию 300): ") or 300)
        if not 1 <= total <= 100:
            raise ValueError("Количество запросов должно быть от 1 до 100")
        if not 1 <= workers <= 5:
            raise ValueError("Одновременных запросов должно быть от 1 до 5")
        if interval < 60:
            raise ValueError("Интервал должен быть не меньше 60 секунд")
    except ValueError as exc:
        console.print(f"[red]Ошибка настроек: {exc}[/red]")
        return None
    return target, total, workers, interval
def download_proxies():
    proxies = set()
    for source in SOURCES:
        try:
            response = requests.get(source, timeout=15)
            response.raise_for_status()
            for line in response.text.splitlines():
                proxy = line.strip()
                if ":" not in proxy:
                    continue
                host, separator, port = proxy.rpartition(":")
                if separator and host and port.isdigit():
                    if 1 <= int(port) <= 65535:
                        proxies.add(proxy)
        except requests.RequestException as exc:
            console.print(f"[yellow]Источник недоступен: {exc}[/yellow]")
    return sorted(proxies)
def check_proxy(proxy):
    config = {
        "http": f"http://{proxy}",
        "https": f"http://{proxy}",
    }
    try:
        start = time.perf_counter()
        response = requests.get(
            CHECK_URL,
            proxies=config,
            timeout=CHECK_TIMEOUT,
        )
        latency = (time.perf_counter() - start) * 1000
        if response.status_code == 200:
            return proxy, latency
    except requests.RequestException:
        pass
    return None
def check_all(proxies):
    working = []
    console.print(f"\nПроверяю {len(proxies)} прокси...")
    with ThreadPoolExecutor(max_workers=MAX_CHECK_WORKERS) as pool:
        futures = [pool.submit(check_proxy, p) for p in proxies]
        for future in as_completed(futures):
            result = future.result()
            if result:
                working.append(result)
    return sorted(working, key=lambda item: item[1])
def save_proxies(proxies):
    with open(OUTPUT, "w", encoding="utf-8") as file:
        for proxy, _ in proxies:
            file.write(proxy + "\n")
def test_proxy(proxy, target):
    config = {
        "http": f"http://{proxy}",
        "https": f"http://{proxy}",
    }
    try:
        start = time.perf_counter()
        response = requests.get(
            target,
            proxies=config,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": "Authorized-Site-Health-Test/1.0"},
        )
        latency = (time.perf_counter() - start) * 1000
        return {
            "proxy": proxy,
            "status": response.status_code,
            "latency": latency,
            "error": None,
        }
    except requests.RequestException as exc:
        return {
            "proxy": proxy,
            "status": None,
            "latency": None,
            "error": type(exc).__name__,
        }
def run_test(proxies, target, total, workers):
    # Ограничиваем число тестовых запросов.
    selected = proxies[:total]
    console.print(
        f"\n[cyan]Проверка сайта через {len(selected)} прокси[/cyan]"
    )
    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(test_proxy, proxy, target)
            for proxy, _ in selected
        ]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            if result["error"]:
                console.print(
                    f"[yellow]Ошибка соединения: {result['proxy']} "
                    f"({result['error']})[/yellow]"
                )
            else:
                console.print(
                    f"HTTP {result['status']} | "
                    f"{result['latency']:.0f} ms | "
                    f"{result['proxy']}"
                )
    return results
def show_stats(results):
    codes = Counter()
    errors = 0
    latencies = []
    for result in results:
        if result["error"]:
            errors += 1
        else:
            codes[result["status"]] += 1
            latencies.append(result["latency"])
    table = Table(title="Результаты теста")
    table.add_column("Показатель")
    table.add_column("Значение")
    table.add_row("Всего запросов", str(len(results)))
    table.add_row("Ошибки соединения", str(errors))
    for code, count in sorted(codes.items()):
        table.add_row(f"HTTP {code}", str(count))
    if latencies:
        table.add_row(
            "Средняя задержка",
            f"{sum(latencies) / len(latencies):.0f} ms"
        )
    console.print(table)
def main():
    settings = ask_settings()
    if not settings:
        return
    target, total, workers, interval = settings
    console.print(f"\nЦель: {target}")
    console.print("[yellow]Используй только сайт, который вправе тестировать.[/yellow]")
    while True:
        proxies = download_proxies()
        console.print(f"Получено прокси: {len(proxies)}")
        working = check_all(proxies)
        save_proxies(working)
        console.print(f"[green]Рабочих прокси: {len(working)}[/green]")
        console.print(f"Список сохранён в {OUTPUT}")
        if working:
            results = run_test(working, target, total, workers)
            show_stats(results)
        else:
            console.print("[red]Рабочие прокси не найдены.[/red]")
        console.print(f"\nСледующее обновление через {interval} секунд.")
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            console.print("\n[yellow]Остановлено.[/yellow]")
            break
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Завершено пользователем.[/yellow]")
