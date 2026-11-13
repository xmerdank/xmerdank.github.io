#!/usr/bin/env python3
"""
Сборка рекламных списков из нескольких источников (см. SOURCES) в один список без дублей.

Использование:
    python tools/build_reject.py                 # скачать свежие источники (StevenBlack + HaGeZi Light)
    python tools/build_reject.py hosts.txt       # взять один локальный файл вместо источников
    python tools/build_reject.py xRules/rules/reject.list   # пересобрать из старого списка

Результат (в xRules/rules/):
    reject.list  — RULE-SET (DOMAIN-SUFFIX,домен) — для Loon и как запасной вариант
    reject.txt   — DOMAIN-SET (.домен)            — для Shadowrocket, легче и быстрее
    reject-mihomo.txt — набор доменов mihomo (+.домен) — для FlClash (xFlClash.js). В mihomo запись
                   «.домен» блокирует только поддомены, а «+.домен» — и сам домен, как в Shadowrocket.
    windows-telemetry-hagezi.list — телеметрия Microsoft, только для профиля Throne (см. TELEMETRY_SOURCE);
                   собирается только при запуске без аргумента

Логика блокировки та же, что и раньше: каждый домен блокируется вместе со всеми
поддоменами. Убираются только записи, которые и так покрыты родительским доменом
(например, ads.example.com при наличии example.com), мусор из шапки hosts-файла
и домены, которые конфликтуют с proxy/direct списками.

Если список заблокировал что-то нужное — добавить адрес в xRules/rules/reject-allow.list
и пересобрать (вкладка Actions → "Обновление списков блокировки" → Run workflow).

Почему именно эти два источника (замер 2026-11-11 по журналам Shadowrocket, 37,5 тыс. соединений):
StevenBlack блокировал 13,2% соединений, HaGeZi Light — 14,9%, а вместе — 21,1%: они почти не
пересекаются (StevenBlack сильнее в рекламных сетях приложений, HaGeZi — в трекерах и телеметрии
TikTok, Trendyol, Яндекса, Apple). Ложных срабатываний в журналах не нашлось.
Не взяты: HaGeZi Pro (вдвое больше доменов ради +1%), OISD и AdGuard DNS (поверх этой пары
добавляют меньше 0,5%), 1Hosts и GoodbyeAds (блокируют нужное: вход TikTok, Firebase, картинки AliExpress).
"""
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# (название, адрес). Подходят hosts-файлы ("0.0.0.0 домен") и простые списки доменов по одному в строке.
SOURCES = [
    ("StevenBlack/hosts (fakenews-gambling)",
     "https://raw.githubusercontent.com/StevenBlack/hosts/master/alternates/fakenews-gambling/hosts"),
    ("HaGeZi Multi Light",
     "https://raw.githubusercontent.com/hagezi/dns-blocklists/main/wildcard/light-onlydomains.txt"),
]
ROOT = Path(__file__).resolve().parent.parent
RULES = ROOT / "xRules" / "rules"

# Телеметрия Windows, Office, Edge, Bing, Xbox — список встроенных трекеров Microsoft от HaGeZi (~365 адресов).
# Идёт отдельным файлом и подключается только в Throne (правило «Телеметрия Windows → блок»):
# на айфоне он не нужен. Свои адреса — в windows-telemetry.list, тот файл скрипт не трогает.
TELEMETRY_SOURCE = ("HaGeZi Native Tracker — Microsoft (Windows/Office)",
                    "https://raw.githubusercontent.com/hagezi/dns-blocklists/main/wildcard/native.winoffice-onlydomains.txt")
TELEMETRY_FILE = "windows-telemetry-hagezi.list"
MIN_TELEMETRY = 200  # меньше — значит, скачалось что-то не то

# Домены из этих списков не должны блокироваться (иначе REJECT, стоящий выше, их перекроет)
# reject-allow.list — ручные исключения: адреса, которые источники блокируют зря.
PROTECTED_LISTS = ["proxy.list", "direct.list", "tmdirect.list", "apple.list", "spotify.list", "facetime.list",
                   "ai/chatgpt.list", "ai/claude.list", "ai/gemini.list", "ai/other.list", "reject-allow.list"]

# Служебные имена из шапки hosts-файла
JUNK = {
    "localhost", "localhost.localdomain", "local", "broadcasthost",
    "ip6-localhost", "ip6-loopback", "ip6-localnet", "ip6-mcastprefix",
    "ip6-allnodes", "ip6-allrouters", "ip6-allhosts", "0.0.0.0",
}

MIN_DOMAINS = 20000  # меньше (в любом из источников или в итоге) — значит, скачалось что-то не то

DOMAIN_RE =re.compile(r"^(?=.{1,253}$)(?!-)[a-z0-9_-]+(\.[a-z0-9_-]+)+$")
IP_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def read_source(arg: str) -> str:
    if arg.startswith(("http://", "https://")):
        print(f"Скачиваю {arg}")
        with urllib.request.urlopen(arg, timeout=120) as r:
            return r.read().decode("utf-8", "replace")
    return Path(arg).read_text(encoding="utf-8", errors="replace")


def parse(text: str) -> set[str]:
    domains = set()
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("DOMAIN-SUFFIX,") or line.startswith("DOMAIN,"):
            host = line.split(",", 2)[1]
        else:
            parts = line.split()
            # hosts-формат: "0.0.0.0 домен"
            host = parts[1] if len(parts) >= 2 else parts[0]
        host = host.strip().strip(".").lower()
        if host in JUNK or IP_RE.match(host) or not DOMAIN_RE.match(host):
            continue
        domains.add(host)
    return domains


def protected_domains() -> set[str]:
    out = set()
    for name in PROTECTED_LISTS:
        path = RULES / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2 and parts[0] in ("DOMAIN-SUFFIX", "DOMAIN"):
                out.add(parts[1].lower())
    return out


def parents(domain: str):
    labels = domain.split(".")
    for i in range(1, len(labels) - 1):
        yield ".".join(labels[i:])


def reduce(domains: set[str], protected: set[str]) -> tuple[list[str], list[str]]:
    # Не блокируем защищённый домен и его родителей (родитель-суффикс заблокировал бы и его)
    blocked_by_reject = {d for d in domains if d in protected
                         or any(d in set(parents(p)) for p in protected)}
    kept = domains - blocked_by_reject
    # Убираем поддомены, которые уже покрыты родителем
    result = sorted(d for d in kept if not any(p in kept for p in parents(d)))
    return result, sorted(blocked_by_reject)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # консоль Windows
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sources = [(sys.argv[1], sys.argv[1])] if len(sys.argv) > 1 else SOURCES
    domains: set[str] = set()
    for title, src in sources:
        part = parse(read_source(src))
        # Защита: если хоть один источник не скачался или пришёл битым, старые списки не трогаем —
        # иначе список молча сжался бы до одного источника.
        if len(part) < MIN_DOMAINS:
            sys.exit(f"Ошибка: «{title}» — всего {len(part)} доменов (минимум {MIN_DOMAINS}). Файлы не изменены.")
        print(f"  {title}: {len(part)} доменов, новых: {len(part - domains)}")
        domains |= part
    result, removed = reduce(domains, protected_domains())
    if len(result) < MIN_DOMAINS:
        sys.exit(f"Ошибка: получено всего {len(result)} доменов (минимум {MIN_DOMAINS}). Файлы не изменены.")
    # Телеметрия скачивается до записи файлов: если она не скачалась, не меняется ничего.
    telemetry = telemetry_removed = None
    if len(sys.argv) == 1:
        title, url = TELEMETRY_SOURCE
        part = parse(read_source(url))
        if len(part) < MIN_TELEMETRY:
            sys.exit(f"Ошибка: «{title}» — всего {len(part)} доменов (минимум {MIN_TELEMETRY}). Файлы не изменены.")
        telemetry, telemetry_removed = reduce(part, protected_domains())
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    header = [
        "# Реклама, трекеры, вредоносные сайты, fake news, азартные игры",
        "# Источники: " + "; ".join(title for title, _ in sources),
        f"# Собрано: {stamp} скриптом tools/build_reject.py",
        f"# Доменов: {len(result)} (каждый блокируется вместе с поддоменами)",
        "",
    ]
    # newline="\n" — одинаковые концы строк (LF) и на Windows, и на GitHub
    (RULES / "reject.list").write_text(
        "\n".join(header + [f"DOMAIN-SUFFIX,{d}" for d in result]) + "\n", encoding="utf-8", newline="\n")
    (RULES / "reject.txt").write_text(
        "\n".join(header + [f".{d}" for d in result]) + "\n", encoding="utf-8", newline="\n")
    (RULES / "reject-mihomo.txt").write_text(
        "\n".join(header + [f"+.{d}" for d in result]) + "\n", encoding="utf-8", newline="\n")
    print(f"Исходных доменов: {len(domains)}")
    print(f"Итого: {len(result)} (убрано поддоменов-дублей: {len(domains) - len(result) - len(removed)})")
    if removed:
        print("Исключены, т.к. конфликтуют с proxy/direct или стоят в reject-allow.list:", ", ".join(removed))
    if telemetry is not None:
        t_header = [
            "# Телеметрия Microsoft: Windows, Office, Edge, Bing, Xbox. Используется только в профиле Throne.",
            f"# Источник: {TELEMETRY_SOURCE[0]} — https://github.com/hagezi/dns-blocklists",
            "# Файл собирается автоматически, руками не править: свои адреса — в windows-telemetry.list,",
            "# исключения — в reject-allow.list.",
            f"# Собрано: {stamp} скриптом tools/build_reject.py",
            f"# Доменов: {len(telemetry)} (каждый блокируется вместе с поддоменами)",
            "",
        ]
        (RULES / TELEMETRY_FILE).write_text(
            "\n".join(t_header + [f"DOMAIN-SUFFIX,{d}" for d in telemetry]) + "\n", encoding="utf-8", newline="\n")
        print(f"Телеметрия Microsoft: {len(telemetry)} доменов")
        if telemetry_removed:
            print("  исключены (proxy/direct/reject-allow):", ", ".join(telemetry_removed))


if __name__ == "__main__":
    main()
