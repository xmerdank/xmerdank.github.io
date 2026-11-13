#!/usr/bin/env python3
"""
Проверка: открываются ли из Туркменистана БЕЗ VPN адреса, которые наши правила пускают напрямую.

Запускать на компьютере в TM, когда VPN выключен (Throne остановлен, системный прокси снят):
    python tools/check_direct.py                 # все прямые списки
    python tools/check_direct.py --dns 192.168.1.1 example.com other.org   # плюс свои адреса
    python tools/check_direct.py --rounds 5      # больше попыток на адрес (по умолчанию 3)
    python tools/check_direct.py --only a.com b.com   # только эти адреса (даже если они в proxy.list)
    python tools/check_direct.py --proxy-list    # адреса из proxy.list: не разблокировали ли их

Что проверяется для каждого адреса — так же, как его открывало бы приложение напрямую:
    1. DNS: запрос к DNS роутера (по умолчанию 192.168.1.1). Ответ 127.0.0.1 — так в TM блокируют сайты.
    2. TCP: соединение с полученным адресом на порт 443. Отказ (RST) — блокировка по IP.
    3. TLS: рукопожатие с именем сайта. Обрыв здесь — блокировка по имени сайта (SNI).
    4. HTTP: запрос HEAD /. Любой ответ сервера (даже 404) значит, что адрес работает.

Списки (в порядке правил Shadowrocket): ai/claude.list, ai/gemini.list, facetime.list, apple.list,
tmdirect.list, direct.list. Адреса, которые и так уходят в VPN по proxy.list (он стоит выше), пропускаются.
Правила DOMAIN-KEYWORD (google, microsoft, yandex...) нельзя проверить целиком — вместо них
проверяется набор типичных адресов из KEYWORD_SAMPLES (по журналам Shadowrocket и Throne).

Каждый адрес проверяется несколько раз (--rounds): у Google и Microsoft в TM заблокирована только часть
серверов, а DNS каждый раз выдаёт разные — один и тот же адрес то открывается, то нет. Такие адреса
попадают в отдельный раздел «с перебоями» (найдено 2026-11-12: www.google.com, googleapis.com,
login.microsoftonline.com, teams.microsoft.com и др.).

Результат ничего не меняет в списках — только печатает отчёт. Решение, что переносить в proxy.list,
принимается вручную: одна неудача может быть случайной, стоит перепроверить ещё раз.
"""
import argparse
import random
import socket
import ssl
import struct
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULES = ROOT / "xRules" / "rules"

DIRECT_LISTS = ["ai/claude.list", "ai/gemini.list", "facetime.list", "apple.list", "tmdirect.list", "direct.list"]
PROXY_LIST = "proxy.list"

# Зоны, а не сайты: проверять нечего (example.com.tm — это уже конкретный сайт)
ZONES = {"com.tm", "co.tm", "net.tm", "gov.tm", "edu.tm", "mil.tm"}

# Типичные адреса для правил DOMAIN-KEYWORD — сами ключевые слова проверить нельзя.
KEYWORD_SAMPLES = {
    "google": ["www.google.com", "mail.google.com", "accounts.google.com", "www.googleapis.com",
               "play.googleapis.com", "oauth2.googleapis.com", "fonts.googleapis.com", "apis.google.com",
               "docs.google.com", "translate.google.com", "maps.google.com", "photos.google.com",
               "calendar.google.com", "keep.google.com", "contacts.google.com", "news.google.com",
               "play.google.com", "ogs.google.com", "myaccount.google.com", "clients4.google.com",
               "update.googleapis.com", "dl.google.com", "android.clients.google.com", "mtalk.google.com",
               "lens.google.com", "www.google.tm", "people-pa.googleapis.com", "firebaseinstallations.googleapis.com",
               "googleapis.com", "storage.googleapis.com"],
    "gstatic": ["www.gstatic.com", "fonts.gstatic.com", "ssl.gstatic.com", "encrypted-tbn0.gstatic.com",
                "connectivitycheck.gstatic.com"],
    "gmail": ["gmail.com"],
    "recaptcha": ["www.recaptcha.net"],
    "microsoft": ["www.microsoft.com", "login.microsoftonline.com", "go.microsoft.com",
                  "download.microsoft.com", "update.microsoft.com", "officecdn.microsoft.com",
                  "teams.microsoft.com", "learn.microsoft.com", "displaycatalog.mp.microsoft.com",
                  "settings-win.data.microsoft.com", "officeclient.microsoft.com", "account.microsoft.com"],
    "1drv": ["1drv.ms", "api.onedrive.com"],
    "yandex": ["yandex.ru", "yandex.com", "mail.yandex.ru", "disk.yandex.ru", "music.yandex.ru",
               "translate.yandex.ru", "market.yandex.ru", "api.browser.yandex.ru"],
}

TIMEOUT = 6


def read_rules(name: str):
    """(тип, значение) из .list; IP-правила пропускаются — проверяются только имена."""
    out = []
    for raw in (RULES / name).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2 and parts[0] in ("DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD"):
            out.append((parts[0], parts[1].lower()))
    return out


def in_proxy(host: str, proxy_rules) -> str | None:
    for kind, value in proxy_rules:
        if (kind == "DOMAIN" and host == value) or \
           (kind == "DOMAIN-SUFFIX" and (host == value or host.endswith("." + value))) or \
           (kind == "DOMAIN-KEYWORD" and value in host):
            return f"{kind},{value}"
    return None


# ---------- DNS: простой запрос типа A напрямую к DNS роутера ----------

def _skip_name(data: bytes, pos: int) -> int:
    while True:
        length = data[pos]
        if length == 0:
            return pos + 1
        if length & 0xC0 == 0xC0:
            return pos + 2
        pos += 1 + length


def resolve(host: str, server: str) -> tuple[str, list[str]]:
    """('ok'|'nxdomain'|'empty'|'timeout'|'error', [адреса])"""
    qid = random.randint(0, 0xFFFF)
    query = struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0)
    query += b"".join(bytes([len(p)]) + p.encode("idna") for p in host.split(".")) + b"\x00"
    query += struct.pack(">HH", 1, 1)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(3)
    try:
        for _ in range(2):
            try:
                sock.sendto(query, (server, 53))
                data = sock.recv(4096)
                break
            except socket.timeout:
                continue
        else:
            return "timeout", []
    except OSError as e:
        return f"error {e}", []
    finally:
        sock.close()
    rid, flags, qd, an = struct.unpack(">HHHH", data[:8])
    if rid != qid:
        return "error id", []
    if flags & 0x000F == 3:
        return "nxdomain", []
    pos = 12
    for _ in range(qd):
        pos = _skip_name(data, pos) + 4
    ips = []
    for _ in range(an):
        pos = _skip_name(data, pos)
        rtype, _cls, _ttl, rdlen = struct.unpack(">HHIH", data[pos:pos + 10])
        pos += 10
        if rtype == 1 and rdlen == 4:
            ips.append(socket.inet_ntoa(data[pos:pos + 4]))
        pos += rdlen
    return ("ok" if ips else "empty"), ips


# ---------- TCP + TLS + HTTP ----------

def probe(host: str, ip: str) -> tuple[bool, str, float]:
    t0 = time.monotonic()
    try:
        raw = socket.create_connection((ip, 443), timeout=TIMEOUT)
    except ConnectionRefusedError:
        return False, "TCP: отказ (блок по IP)", time.monotonic() - t0
    except socket.timeout:
        return False, "TCP: тайм-аут", time.monotonic() - t0
    except OSError as e:
        return False, f"TCP: {e.strerror or e}", time.monotonic() - t0
    ctx = ssl.create_default_context()
    note = ""
    try:
        tls = ctx.wrap_socket(raw, server_hostname=host)
    except ssl.SSLCertVerificationError as e:
        raw.close()
        # Имя не совпало — возможна подмена, считаем неудачей. Остальное (неизвестный центр сертификации,
        # как у части серверов Apple со своим корневым сертификатом, или просроченный сертификат) —
        # сервер доступен, проблема не в блокировке: повторяем без проверки.
        if e.verify_code == 62:
            return False, f"TLS: чужой сертификат ({e.verify_message})", time.monotonic() - t0
        note = " (сертификат не проверен)"
        try:
            raw = socket.create_connection((ip, 443), timeout=TIMEOUT)
            loose = ssl.create_default_context()
            loose.check_hostname = False
            loose.verify_mode = ssl.CERT_NONE
            tls = loose.wrap_socket(raw, server_hostname=host)
        except (OSError, ssl.SSLError) as e2:
            return False, f"TLS: {type(e2).__name__}", time.monotonic() - t0
    except (ConnectionResetError, ssl.SSLError, socket.timeout, OSError) as e:
        raw.close()
        kind = "сброс (блок по имени, SNI)" if isinstance(e, ConnectionResetError) else type(e).__name__
        return False, f"TLS: {kind}", time.monotonic() - t0
    try:
        tls.settimeout(TIMEOUT)
        tls.sendall(f"HEAD / HTTP/1.1\r\nHost: {host}\r\nUser-Agent: Mozilla/5.0\r\nConnection: close\r\n\r\n".encode())
        first = tls.recv(256).split(b"\r\n", 1)[0].decode("latin-1", "replace")
    except (OSError, ssl.SSLError) as e:
        return False, f"HTTP: нет ответа ({type(e).__name__})", time.monotonic() - t0
    finally:
        tls.close()
    if not first.startswith("HTTP/"):
        return False, "HTTP: пустой ответ", time.monotonic() - t0
    return True, (first.split(" ", 2)[1] if " " in first else first) + note, time.monotonic() - t0


def check(host: str, dns: str) -> dict:
    status, ips = resolve(host, dns)
    res = {"host": host, "ips": ips}
    if status != "ok":
        res.update(ok=None if status in ("nxdomain", "empty") else False,
                   why={"nxdomain": "DNS: нет такого имени", "empty": "DNS: нет адреса",
                        "timeout": "DNS: не отвечает"}.get(status, status))
        return res
    if all(ip.startswith("127.") or ip == "0.0.0.0" for ip in ips):
        res.update(ok=False, why="DNS: 127.0.0.1 (блок по DNS)")
        return res
    if any(ip.startswith("198.18.") or ip.startswith("198.19.") for ip in ips):
        res.update(ok=None, why="DNS: подменный адрес 198.18.x — VPN/Throne включён, результат неверный")
        return res
    # Пробуем до двух адресов: одна заблокированная подсеть ещё не значит, что не работает весь сайт
    last = None
    for ip in ips[:2]:
        ok, why, dt = probe(host, ip)
        if ok:
            res.update(ok=True, why=f"HTTP {why}", ip=ip, time=dt)
            return res
        last = (why, ip, dt)
    res.update(ok=False, why=last[0], ip=last[1], time=last[2])
    return res


def build_targets(extra: list[str], only: bool = False, proxy_list: bool = False):
    proxy_rules = read_rules(PROXY_LIST)
    targets, skipped = [], []  # (хост, откуда)
    seen = set()

    def add(host, origin, alt=None, force=False):
        if host in seen:
            return
        seen.add(host)
        hit = None if force else in_proxy(host, proxy_rules)
        if hit:
            skipped.append((host, f"через VPN по proxy.list ({hit})"))
        else:
            targets.append((host, origin, alt))

    if proxy_list:
        # Обратная проверка: адреса, которые сейчас идут через VPN, — может, их уже разблокировали
        for kind, value in proxy_rules:
            if kind == "DOMAIN-KEYWORD":
                skipped.append((value, "proxy.list: ключевое слово, не проверяется"))
            else:
                add(value, "proxy.list", None if kind == "DOMAIN" else "www." + value, force=True)
    for name in ([] if only or proxy_list else DIRECT_LISTS):
        for kind, value in read_rules(name):
            if kind == "DOMAIN-KEYWORD":
                for h in KEYWORD_SAMPLES.get(value, []):
                    add(h, f"{name}: ключ {value}")
                if value not in KEYWORD_SAMPLES:
                    skipped.append((value, f"{name}: ключевое слово без примеров"))
            elif value in ZONES:
                skipped.append((value, f"{name}: зона, не сайт"))
            else:
                # для суффикса: сам домен, а если у него нет адреса — www.
                add(value, name, None if kind == "DOMAIN" else "www." + value)
    for h in extra:
        # Адреса из командной строки проверяются всегда, даже если они в proxy.list
        add(h.lower(), "командная строка", force=True)
    return targets, skipped


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Проверка прямых адресов без VPN")
    ap.add_argument("--dns", default="192.168.1.1", help="DNS роутера (по умолчанию 192.168.1.1)")
    ap.add_argument("--rounds", type=int, default=3, help="попыток на адрес (по умолчанию 3)")
    ap.add_argument("--only", action="store_true", help="проверить только адреса из командной строки")
    ap.add_argument("--proxy-list", action="store_true",
                    help="проверить адреса из proxy.list (работают ли они уже напрямую)")
    ap.add_argument("hosts", nargs="*", help="дополнительные адреса для проверки")
    args = ap.parse_args()

    targets, skipped = build_targets(args.hosts, args.only, args.proxy_list)
    print(f"Проверяю {len(targets)} адресов через DNS {args.dns} (VPN должен быть выключен)...\n")

    def run(t):
        host, origin, alt = t
        r = check(host, args.dns)
        if r["ok"] is None and alt and r["why"].startswith("DNS: нет"):
            r2 = check(alt, args.dns)
            if r2["ok"] is not None:
                r, host = r2, alt
        if r["ok"] is None:
            r["origin"] = origin
            return r
        # Повторные попытки: каждая — новый DNS-запрос и первый полученный адрес, как у приложения
        tries = [r]
        for _ in range(args.rounds - 1):
            time.sleep(1)
            tries.append(check(host, args.dns))
        good_tries = [x for x in tries if x["ok"]]
        bad_tries = [x for x in tries if x["ok"] is False]
        best = (good_tries or bad_tries or tries)[0]
        best["origin"] = origin
        best["fails"] = len(bad_tries)
        best["total"] = len(tries)
        if good_tries and bad_tries:
            best["ok"] = "partial"
            best["why"] = f"{len(bad_tries)} из {len(tries)}: {bad_tries[0]['why']}"
            best["bad_ip"] = bad_tries[0].get("ip", "")
        elif bad_tries:
            best["ok"] = False
        return best

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(run, targets))

    if any("198.18" in r["why"] for r in results if r["ok"] is None):
        print("ВНИМАНИЕ: DNS отвечает подменными адресами 198.18.x — включён VPN (Throne/TUN). Выключите и запустите снова.\n")

    bad = [r for r in results if r["ok"] is False]
    partial = [r for r in results if r["ok"] == "partial"]
    unknown = [r for r in results if r["ok"] is None]
    good = [r for r in results if r["ok"] is True]
    print(f"== НЕ работают напрямую ни разу: {len(bad)}")
    for r in sorted(bad, key=lambda r: (r["origin"], r["host"])):
        print(f"  {r['host']:40s} {r['why']:42s} {r.get('ip', ','.join(r['ips'][:2]))}  [{r['origin']}]")
    print(f"\n== С перебоями (часть попыток не открылась — DNS выдал заблокированный сервер): {len(partial)}")
    for r in sorted(partial, key=lambda r: (r["origin"], r["host"])):
        print(f"  {r['host']:40s} {r['why']:42s} {r.get('bad_ip', '')}  [{r['origin']}]")
    print(f"\n== Нет адреса в DNS (не сайт или только поддомены): {len(unknown)}")
    for r in sorted(unknown, key=lambda r: r["host"]):
        print(f"  {r['host']:40s} {r['why']}  [{r['origin']}]")
    print(f"\n== Работают: {len(good)}")
    for r in sorted(good, key=lambda r: (r["origin"], r["host"])):
        print(f"  {r['host']:40s} {r['why']:10s} {r['time']*1000:5.0f} мс  {r['ip']}  [{r['origin']}]")
    if skipped:
        print(f"\n== Пропущено: {len(skipped)}")
        for host, why in skipped:
            print(f"  {host:40s} {why}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
