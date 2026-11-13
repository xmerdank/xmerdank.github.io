// Date: 2026.11.13
// Author: xmerdanx
//
// Скрипт расширения FlClash (Android, Windows, macOS, Linux): накладывает наши правила на вашу подписку.
// Серверы берутся из подписки, всё остальное (группы, правила, DNS) задаёт этот скрипт.
// Подключение — в README.md. Ссылка: https://xmerdank.github.io/xRules/xFlClash.js
//
// Правила те же, что в xRocket.conf (Shadowrocket), и в том же порядке. Списки — те же файлы из rules/,
// mihomo понимает их формат. Строки, которых mihomo не знает (URL-REGEX в reject2.list), он пропускает.
// Рекламный список — reject-mihomo.txt: те же домены, что в reject.txt, но в записи «+.домен».

const RULES_URL = "https://xmerdank.github.io/xRules/rules/";

// Переключатели: первый пункт — значение по умолчанию (как в xRocket.conf).
const SWITCHES = [
  // ИИ-сервисы
  ["ChatGPT", "PROXY"],
  ["Claude", "DIRECT"],
  ["Gemini", "DIRECT"],
  ["AI-Other", "PROXY"],
  // Apple в TM не заблокирован; заблокированные части Apple идут через VPN по proxy.list.
  ["Apple", "DIRECT"],
  // Spotify в TM заблокирован (DNS отвечает 127.0.0.1). Если разблокируют — выбрать DIRECT.
  ["Spotify", "PROXY"],
];

// Наборы правил. Скачиваются через VPN: xmerdank.github.io в TM без VPN не открывается.
const RULE_SETS = {
  "reject": ["reject-mihomo.txt", "domain"],
  "reject2": ["reject2.list"],
  "chatgpt": ["ai/chatgpt.list"],
  "claude": ["ai/claude.list"],
  "gemini": ["ai/gemini.list"],
  "ai-other": ["ai/other.list"],
  "proxy": ["proxy.list"],
  "facetime": ["facetime.list"],
  "apple": ["apple.list"],
  "spotify": ["spotify.list"],
  "tmdirect": ["tmdirect.list"],
  "direct": ["direct.list"],
};

const RULES = [
  // Локальная сеть — всегда напрямую
  "IP-CIDR,192.168.0.0/16,DIRECT,no-resolve",
  "IP-CIDR,10.0.0.0/8,DIRECT,no-resolve",
  "IP-CIDR,172.16.0.0/12,DIRECT,no-resolve",
  "IP-CIDR,127.0.0.0/8,DIRECT,no-resolve",
  "IP-CIDR,169.254.0.0/16,DIRECT,no-resolve",
  "IP-CIDR,100.64.0.0/10,DIRECT,no-resolve",

  // QUIC (HTTP/3 по UDP, порт 443) блокируется для всех соединений: приложения переходят на обычный TCP
  // (как block-quic = all в Shadowrocket).
  "AND,((NETWORK,UDP),(DST-PORT,443)),REJECT",

  // Реклама
  "RULE-SET,reject,REJECT",
  "RULE-SET,reject2,REJECT",

  // ИИ-сервисы (стоят выше direct.list, чтобы правила google/microsoft их не перехватывали)
  "RULE-SET,chatgpt,ChatGPT",
  "RULE-SET,claude,Claude",
  "RULE-SET,gemini,Gemini",
  "RULE-SET,ai-other,AI-Other",

  // Маршрутизация
  "RULE-SET,proxy,PROXY",
  "RULE-SET,facetime,DIRECT",
  "RULE-SET,apple,Apple",
  "RULE-SET,spotify,Spotify",
  "RULE-SET,tmdirect,DIRECT",
  "RULE-SET,direct,DIRECT",

  "GEOIP,TM,DIRECT",
  "MATCH,PROXY",
];

// DNS. Публичные DNS (8.8.8.8, 1.1.1.1 — и по порту 53, и DoH) из TM напрямую не отвечают
// (проверено 2026-11-13), поэтому DNS из подписки заменяется на системный (роутер / оператор),
// как dns-server = system в Shadowrocket. Запасной — Google DoH через VPN: mihomo опрашивает оба
// сразу и берёт первый ответ, так что системный (10–30 мс) обычно успевает раньше.
// Режим fake-ip: приложение сразу получает подменный адрес 198.18.x, а для соединений через VPN
// имя сайта передаётся серверу и резолвится там (как force-remote-dns в Shadowrocket).
const DNS = {
  "enable": true,
  "ipv6": false,
  "enhanced-mode": "fake-ip",
  "fake-ip-range": "198.18.0.1/16",
  "fake-ip-filter-mode": "blacklist",
  // Эти имена получают настоящий адрес: локальная сеть, проверка подключения, точное время, STUN.
  "fake-ip-filter": [
    "*.lan", "+.local", "+.home.arpa", "localhost",
    "+.msftconnecttest.com", "+.msftncsi.com",
    "+.pool.ntp.org", "time.*.com", "time.*.gov", "time.*.apple.com", "ntp.*.com",
    "stun.*.*", "stun.*.*.*", "+.stun.playstation.net", "+.xboxlive.com",
  ],
  "use-hosts": true,
  "respect-rules": false,
  // default-nameserver не задаём: он нужен только для имён DNS-серверов, а здесь их нет (8.8.8.8 —
  // это IP), и mihomo требует в нём чистые IP-адреса. Свой адрес TUN mihomo из system:// исключает сам.
  "nameserver": ["system://", "https://8.8.8.8/dns-query#PROXY"],
};

const main = (config) => {
  const proxies = (config.proxies || []).map((p) => p.name);
  const providers = Object.keys(config["proxy-providers"] || {});
  if (proxies.length === 0 && providers.length === 0) {
    throw new Error("В подписке нет серверов");
  }

  // PROXY — сервер, выбранный вручную (как сервер на главном экране Shadowrocket).
  // Группы и правила подписки заменяются нашими.
  const proxyGroup = { "name": "PROXY", "type": "select" };
  if (proxies.length > 0) proxyGroup.proxies = proxies;
  if (providers.length > 0) proxyGroup.use = providers;
  const groups = [proxyGroup];
  for (const [name, first] of SWITCHES) {
    groups.push({
      "name": name,
      "type": "select",
      "proxies": first === "DIRECT" ? ["DIRECT", "PROXY"] : ["PROXY", "DIRECT"],
    });
  }
  config["proxy-groups"] = groups;

  const ruleProviders = {};
  for (const [name, [file, behavior]] of Object.entries(RULE_SETS)) {
    ruleProviders[name] = {
      "type": "http",
      "behavior": behavior || "classical",
      "format": "text",
      "url": RULES_URL + file,
      "interval": 86400,
      "proxy": "PROXY",
    };
  }
  config["rule-providers"] = ruleProviders;
  config["rules"] = RULES.slice();

  config["dns"] = DNS;
  config["mode"] = "rule";
  config["ipv6"] = false;
  return config;
};
