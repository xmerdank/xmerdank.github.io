#!/usr/bin/env python3
"""
Сборка профиля маршрутизации для Throne (Windows, sing-box) из тех же списков,
что используют Shadowrocket и Loon.

Использование:
    python tools/build_throne.py

Результат: xRules/xThrone.json — удалённый профиль Throne
(в Throne: Маршрутизация → добавить Remote профиль → https://xmerdank.github.io/xRules/xThrone.json).

Порядок правил повторяет xRocket.conf: реклама → ИИ → VPN → Apple → Spotify → Туркменистан → напрямую,
всё остальное — через VPN (default_outbound = proxy).
Скачиваемые наборы правил (geosite-*/geoip-*) НЕ используются. Throne качает их через зеркало
jsDelivr (Cloudflare), которое в TM работает плохо, а DNS-правила Throne объединяют наборы из всех
правил: один незагруженный набор ломает DNS для всех доменов из профиля (проверено 2026-11-07 —
не открывалось ничего, что попадало под правила). Всё задаётся доменами и диапазонами из наших списков.
Правила работают по доменам, поэтому профиль сам включает FakeIP (объект "dns", см. PROFILE_DNS):
в режиме TUN Chrome шифрует имя сайта (ECH), и без FakeIP Throne видит только IP — все правила по
доменам молча не срабатывают (проверено по журналу 2026-11-07).
Папка Throne должна лежать по пути из латинских букв: при «Строгой маршрутизации» с путём вроде
X:\\СОФТ\\Throne Windows не узнаёт ThroneCore в исключении брандмауэра и блокирует его собственные
DNS-запросы к роутеру — не работает ничего «напрямую» (найдено 2026-11-10).
Правила, которых нет в sing-box (IP-ASN, URL-REGEX), пропускаются: туркменские сети
покрыты диапазонами IP из tmdirect.list.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULES = ROOT / "xRules" / "rules"
OUT = ROOT / "xRules" / "xThrone.json"

FIELD = {
    "DOMAIN-SUFFIX": "domain_suffix",
    "DOMAIN": "domain",
    "DOMAIN-KEYWORD": "domain_keyword",
    "IP-CIDR": "ip_cidr",
    "IP-CIDR6": "ip_cidr",
}
SKIPPED_TYPES = {"IP-ASN", "URL-REGEX", "USER-AGENT", "GEOIP"}

# Скачиваемые наборы правил запрещены (см. docstring). Добавлять сюда только после проверки в TM.
KNOWN_RULE_SETS: set[str] = set()

# Google идёт напрямую, как в Shadowrocket (правило google в direct.list); заблокированные в TM части
# Google (Диск, Meet, YouTube, вложения Gmail и др.) — в proxy.list, он стоит выше.
# Отдельное правило «Google → VPN» было с 10 по 11.11.2026: Google ломался не из-за блокировок, а из-за
# DNS — см. PROFILE_DNS.

# DNS профиля. Throne применяет его только при первом добавлении профиля (при обновлении — нет),
# поэтому это ещё и памятка, какие настройки DNS должны стоять в Throne.
# FakeIP обязателен: без него в TUN правила по доменам не срабатывают (Chrome шифрует имя сайта, ECH).
# Прямой DNS — явный адрес роутера, НЕ localhost и НЕ dhcp://: с ними sing-box спрашивает в формате
# EDNS, и DNS в TM на часть имён (Google, Anthropic...) отвечает пустотой — сайты не открываются.
# С явным адресом пустых ответов 0 (журнал Throne 2026-11-11). В другой сети поменять на её роутер.
# IPv6 выключен: у провайдера его нет, попытки по IPv6 только множат ошибки.
PROFILE_DNS = {
    "remote_dns": "tls://8.8.8.8",
    "remote_dns_disable_ipv6": True,
    "direct_dns": "192.168.1.1",
    "direct_dns_disable_ipv6": True,
    "dns_final_out": "remote",
    "enable_dns_routing": True,
    "fake_dns": True,
    "fakeip_disable_ipv6": False,
}


def read_domain_set(name: str) -> dict:
    """Читает DOMAIN-SET Shadowrocket (строки вида .example.com) как domain_suffix."""
    domains = []
    for raw in (RULES / name).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        domains.append(line.lstrip(".").lower())
    return {"domain_suffix": domains}


def read_list(*names: str) -> dict:
    """Читает .list файлы Shadowrocket и возвращает поля правила sing-box."""
    fields: dict[str, list[str]] = {}
    for name in names:
        for raw in (RULES / name).read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",")]
            kind = parts[0].upper()
            if kind in SKIPPED_TYPES:
                continue
            if kind not in FIELD or len(parts) < 2:
                print(f"  пропущено ({name}): {line}", file=sys.stderr)
                continue
            value = parts[1].lower() if kind != "IP-CIDR" else parts[1]
            bucket = fields.setdefault(FIELD[kind], [])
            if value not in bucket:
                bucket.append(value)
    return fields


def rule(name: str, outbound: str | None = None, action: str = "route",
         rule_set: list[str] | None = None, **fields) -> dict:
    obj: dict = {"name": name, "type": "custom"}
    for key, values in fields.items():
        if values:
            obj[key] = values
    if rule_set:
        unknown = set(rule_set) - KNOWN_RULE_SETS
        if unknown:
            sys.exit(f"Ошибка: в правиле «{name}» непроверенные наборы {sorted(unknown)} — см. KNOWN_RULE_SETS")
        obj["rule_set"] = rule_set
    obj["action"] = action
    if action == "route":
        obj["outbound"] = outbound
    return obj


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # консоль Windows
        except Exception:
            pass
    rules = [
        rule("Реклама → блок", action="reject", **read_list("reject2.list")),
        # Тот же большой список, что и в Shadowrocket (reject.txt, ~48 тыс. доменов). Отдельным правилом,
        # чтобы его можно было отключить в Throne, если понадобится, не трогая остальную блокировку.
        rule("Реклама (большой список) → блок", action="reject", **read_domain_set("reject.txt")),
        # Только для компьютера: в Shadowrocket и Loon эти списки не подключаются.
        # windows-telemetry.list — свои адреса, windows-telemetry-hagezi.list — список HaGeZi (обновляется сам).
        rule("Телеметрия Windows → блок", action="reject",
             **read_list("windows-telemetry.list", "windows-telemetry-hagezi.list")),
        rule("ChatGPT → VPN", "proxy", **read_list("ai/chatgpt.list")),
        rule("Claude → напрямую (отключить = через VPN)", "direct", **read_list("ai/claude.list")),
        rule("Gemini → напрямую (отключить = через VPN)", "direct", **read_list("ai/gemini.list")),
        rule("ИИ прочие → VPN", "proxy", **read_list("ai/other.list")),
        rule("VPN", "proxy", **read_list("proxy.list")),
        rule("Apple → напрямую (отключить = через VPN)", "direct", **read_list("apple.list")),
        rule("Spotify → VPN", "proxy", **read_list("spotify.list")),
        rule("Туркменистан → напрямую", "direct", **read_list("tmdirect.list")),
        rule("Напрямую", "direct", **read_list("direct.list")),
    ]
    profile = {
        "kind": "throne-route-profile",
        "v": 1,
        "name": "xmn",
        "dns": PROFILE_DNS,
        "default_outbound": "proxy",
        "rules": rules,
    }
    # Без отступов внутри списков файл был бы вдвое больше: каждое правило — одной строкой.
    head = {k: v for k, v in profile.items() if k != "rules"}
    text = json.dumps(head, ensure_ascii=False, indent=2)[:-2] + ',\n  "rules": [\n'
    text += ",\n".join("    " + json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in rules)
    text += "\n  ]\n}\n"
    json.loads(text)  # проверка, что собранный вручную JSON корректен
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"Готово: {OUT.relative_to(ROOT)} — правил: {len(rules)}")


if __name__ == "__main__":
    main()
