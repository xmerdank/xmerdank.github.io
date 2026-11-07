#!/usr/bin/env python3
"""
Сборка профиля маршрутизации для Throne (Windows, sing-box) из тех же списков,
что используют Shadowrocket и Loon.

Использование:
    python tools/build_throne.py

Результат: xRocket/Throne.json — удалённый профиль Throne
(в Throne: Маршрутизация → добавить Remote профиль → https://xmerdank.github.io/xRocket/Throne.json).

Порядок правил повторяет xRules.conf: реклама → ИИ → VPN → Apple → Spotify → Туркменистан → напрямую,
всё остальное — через VPN (default_outbound = proxy).
Встроенные наборы geosite-*/geoip-* Throne скачивает сам (MetaCubeX/meta-rules-dat).
Правила, которых нет в sing-box (IP-ASN, URL-REGEX), пропускаются: туркменские сети
покрыты диапазонами IP и набором geoip-tm.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULES = ROOT / "xRocket" / "rules"
OUT = ROOT / "xRocket" / "Throne.json"

FIELD = {
    "DOMAIN-SUFFIX": "domain_suffix",
    "DOMAIN": "domain",
    "DOMAIN-KEYWORD": "domain_keyword",
    "IP-CIDR": "ip_cidr",
    "IP-CIDR6": "ip_cidr",
}
SKIPPED_TYPES = {"IP-ASN", "URL-REGEX", "USER-AGENT", "GEOIP"}


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
        rule("DNS", action="hijack-dns", protocol="dns"),
        # QUIC (HTTP/3) — браузеры перейдут на TCP; через VPN так стабильнее
        rule("QUIC → блок", action="reject", network="udp", port=[443]),
        rule("Реклама → блок", action="reject",
             rule_set=["geosite-category-ads-all"], **read_list("reject2.list")),
        rule("ChatGPT → VPN", "proxy", rule_set=["geosite-openai"], **read_list("ai/chatgpt.list")),
        rule("Claude → напрямую (отключить = через VPN)", "direct",
             rule_set=["geosite-anthropic"], **read_list("ai/claude.list")),
        rule("Gemini → напрямую (отключить = через VPN)", "direct",
             rule_set=["geosite-google-gemini"], **read_list("ai/gemini.list")),
        rule("ИИ прочие → VPN", "proxy", **read_list("ai/other.list")),
        rule("VPN", "proxy",
             rule_set=["geosite-telegram", "geosite-whatsapp", "geosite-instagram", "geosite-facebook",
                       "geosite-youtube", "geosite-twitter", "geosite-tiktok", "geosite-github", "geosite-vk"],
             **read_list("proxy.list")),
        rule("Apple → напрямую (отключить = через VPN)", "direct", **read_list("apple.list")),
        rule("Spotify → VPN", "proxy", rule_set=["geosite-spotify"], **read_list("spotify.list")),
        rule("Туркменистан → напрямую", "direct", rule_set=["geoip-tm"], **read_list("tmdirect.list")),
        rule("Напрямую", "direct",
             rule_set=["geosite-google", "geosite-yandex", "geosite-mailru", "geosite-microsoft", "geosite-ozon"],
             **read_list("direct.list")),
    ]
    profile = {
        "kind": "throne-route-profile",
        "v": 1,
        "name": "xmn",
        "default_outbound": "proxy",
        "rules": rules,
    }
    OUT.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Готово: {OUT.relative_to(ROOT)} — правил: {len(rules)}")


if __name__ == "__main__":
    main()
