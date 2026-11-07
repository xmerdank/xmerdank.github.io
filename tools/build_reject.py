#!/usr/bin/env python3
"""
Сборка рекламных списков из hosts-файла StevenBlack.

Использование:
    python tools/build_reject.py                 # скачать свежий StevenBlack (fakenews + gambling)
    python tools/build_reject.py hosts.txt       # взять локальный hosts-файл
    python tools/build_reject.py xRocket/rules/reject.list   # пересобрать из старого списка

Результат (в xRocket/rules/):
    reject.list  — RULE-SET (DOMAIN-SUFFIX,домен) — для Loon и как запасной вариант
    reject.txt   — DOMAIN-SET (.домен)            — для Shadowrocket, легче и быстрее

Логика блокировки та же, что и раньше: каждый домен блокируется вместе со всеми
поддоменами. Убираются только записи, которые и так покрыты родительским доменом
(например, ads.example.com при наличии example.com), мусор из шапки hosts-файла
и домены, которые конфликтуют с proxy/direct списками.
"""
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_URL = "https://raw.githubusercontent.com/StevenBlack/hosts/master/alternates/fakenews-gambling/hosts"
ROOT = Path(__file__).resolve().parent.parent
RULES = ROOT / "xRocket" / "rules"

# Домены из этих списков не должны блокироваться (иначе REJECT, стоящий выше, их перекроет)
PROTECTED_LISTS = ["proxy.list", "direct.list", "tmdirect.list", "apple.list",
                   "ai/chatgpt.list", "ai/claude.list", "ai/gemini.list", "ai/other.list"]

# Служебные имена из шапки hosts-файла
JUNK = {
    "localhost", "localhost.localdomain", "local", "broadcasthost",
    "ip6-localhost", "ip6-loopback", "ip6-localnet", "ip6-mcastprefix",
    "ip6-allnodes", "ip6-allrouters", "ip6-allhosts", "0.0.0.0",
}

MIN_DOMAINS = 20000  # меньше — значит, скачалось что-то не то

DOMAIN_RE =re.compile(r"^(?=.{1,253}$)(?!-)[a-z0-9_-]+(\.[a-z0-9_-]+)+$")
IP_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def read_source(arg: str | None) -> str:
    if arg is None or arg.startswith(("http://", "https://")):
        url = arg or DEFAULT_URL
        print(f"Скачиваю {url}")
        with urllib.request.urlopen(url, timeout=60) as r:
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
    src = sys.argv[1] if len(sys.argv) > 1 else None
    domains = parse(read_source(src))
    result, removed = reduce(domains, protected_domains())
    # Защита: если источник вернул пустой/битый файл, старые списки не трогаем
    if len(result) < MIN_DOMAINS:
        sys.exit(f"Ошибка: получено всего {len(result)} доменов (минимум {MIN_DOMAINS}). Файлы не изменены.")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    header = [
        "# Реклама, трекеры, вредоносные сайты, fake news, азартные игры",
        "# Источник: StevenBlack/hosts (fakenews-gambling) — https://github.com/StevenBlack/hosts",
        f"# Собрано: {stamp} скриптом tools/build_reject.py",
        f"# Доменов: {len(result)} (каждый блокируется вместе с поддоменами)",
        "",
    ]
    # newline="\n" — одинаковые концы строк (LF) и на Windows, и на GitHub
    (RULES / "reject.list").write_text(
        "\n".join(header + [f"DOMAIN-SUFFIX,{d}" for d in result]) + "\n", encoding="utf-8", newline="\n")
    (RULES / "reject.txt").write_text(
        "\n".join(header + [f".{d}" for d in result]) + "\n", encoding="utf-8", newline="\n")
    print(f"Исходных доменов: {len(domains)}")
    print(f"Итого: {len(result)} (убрано поддоменов-дублей: {len(domains) - len(result) - len(removed)})")
    if removed:
        print("Исключены, т.к. конфликтуют с proxy/direct:", ", ".join(removed))


if __name__ == "__main__":
    main()
