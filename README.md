# Shadowrocket Ru-Direct → Anywhere

Репозиторий: [Conv3lsive/anywhere-refilter](https://github.com/Conv3lsive/anywhere-refilter).

Готовый проект для GitHub: исходный `source/Ru-Direct.conf`, Python-генератор,
готовые `.arrs` в `dist/` и ежедневное обновление через GitHub Actions.
Python 3.10+; сторонние библиотеки не нужны. В Action используется Python 3.13.

**Источник истины — приложенный Ru-Direct.conf, сохранённый без изменений.**
Генератор читает порядок правил и URL внешних списков из него. `update-url`
не скачивается автоматически: обновление самого конфига — явное изменение
`source/Ru-Direct.conf`. GEOIP-источники и необязательные Re:filter-источники
вынесены в `sources.json`.

Перенос максимально приближает решения маршрутизатора, однако `.arrs` не
выражает весь язык Shadowrocket. Различия перечислены ниже; проверка на
реальном устройстве остаётся необходимой для DNS и поведения туннеля.

## Структура

```text
anywhere-refilter/
├── source/Ru-Direct.conf           # исходный конфиг целиком
├── sources.json                   # GEOIP RU/KZ, optional Re:filter, размер частей
├── build_rules.py                 # генератор, проверка, объяснение совпадений
├── build_anywhere_refilter.py      # совместимый вход для старой команды запуска
├── tests/test_routing.py           # регрессии приоритетов и публикации
├── .github/workflows/update.yml    # ежедневное обновление и автокоммит
├── .gitignore
├── README.md
└── dist/
    ├── actions/                   # основной вариант: три набора по действиям
    │   ├── proxy-001.arrs
    │   ├── direct-001.arrs
    │   └── reject-001.arrs
    ├── sets/                      # та же политика, разбитая по источникам
    │   ├── 00-local-direct-001.arrs
    │   ├── 05-prematch-proxy-001.arrs
    │   ├── 10-antifilter-proxy-001.arrs
    │   ├── 20-geo-ru-direct-001.arrs
    │   ├── 20-geo-kz-direct-001.arrs
    │   ├── 30-explicit-direct-001.arrs
    │   ├── 40-domain-ips-proxy-001.arrs
    │   ├── 50-geo-detect-direct-001.arrs
    │   └── 60-reject-reject-001.arrs
    ├── optional/                  # расширение политики, по умолчанию не подключать
    │   ├── refilter-domains-001.arrs
    │   └── refilter-ip-001.arrs
    ├── SUBSCRIPTIONS.md           # актуальный каталог файлов и действий
    ├── manifest.json              # числа правил, действия, SHA-256 файлов
    ├── sources.lock.json          # URL и SHA-256 скачанных upstream-списков
    └── report.json                # исходные настройки и отчёт о преобразованиях
```

Номер `001` присутствует всегда. При росте появляется `002`, `003` и т. д.
Каждая часть содержит максимум 90 000 правил; документированный лимит
Anywhere — 100 000. Новые части нужно добавить в подписки вручную по каталогу.
При уменьшении списка удалённые части остаются пустыми файлами: обновление
старой подписки очистит её прежние правила. Их можно удалить из Anywhere.

## Подключение в Anywhere

1. Включить **Rule mode**, выбрать свой VLESS/chain как основной маршрут.
   Это заменяет `FINAL,PROXY`.
2. Для исходной политики отключить дополнительные назначения встроенным
   сервисам и встроенный ADBlock. Country Bypass оставить выключенным:
   RU и KZ уже представлены CIDR-наборами в основной политике. Встроенные
   уровни Anywhere имеют приоритет над пользовательскими наборами.
3. Добавить URL-подписки из `dist/actions/` и явно назначить действия:

   | Файл | Действие |
   |---|---|
   | [proxy-001.arrs](https://raw.githubusercontent.com/Conv3lsive/anywhere-refilter/main/dist/actions/proxy-001.arrs) | **PROXY** |
   | [direct-001.arrs](https://raw.githubusercontent.com/Conv3lsive/anywhere-refilter/main/dist/actions/direct-001.arrs) | **DIRECT** |
   | [reject-001.arrs](https://raw.githubusercontent.com/Conv3lsive/anywhere-refilter/main/dist/actions/reject-001.arrs) | **REJECT** |

4. Проверить назначение **PROXY** вручную: формат файла позволяет задать
   начальный DIRECT/REJECT, но не PROXY. Оставленный **Default** относится к
   другому уровню приоритета и меняет решения на пересечениях.
5. Проверить DNS-настройки по следующему разделу, обновить подписки,
   переподключить туннель и проверить примеры в конце README.

Готовые публичные URL подписок из вашего репозитория, ветка `main`:

```text
https://raw.githubusercontent.com/Conv3lsive/anywhere-refilter/main/dist/actions/proxy-001.arrs
https://raw.githubusercontent.com/Conv3lsive/anywhere-refilter/main/dist/actions/direct-001.arrs
https://raw.githubusercontent.com/Conv3lsive/anywhere-refilter/main/dist/actions/reject-001.arrs
```

Вместо трёх action-наборов можно подключить **все** файлы из `dist/sets/`
с действиями из `SUBSCRIPTIONS.md`: это та же скомпилированная политика.
Их числа и состав могут отличаться от upstream, поскольку решения уже
скорректированы с учётом ранних правил исходника. Не подключать оба варианта
одновременно и не менять отдельным наборам действия, если нужно сохранить
исходную схему. Порядок этих скомпилированных наборов не заменяет порядок
Shadowrocket: необходимые решения уже перенесены в их содержимое.

## DNS и системные настройки

`.arrs` содержит только условия маршрутизации. DNS, перехват запросов,
IPv6, исключения интерфейса и Hosts им не задаются.

В проверенном исходном коде Anywhere раздел **Advanced Settings → DNS**
имеет отдельные резолверы **IP Rules**, **Proxies**, **Subscriptions**,
**ECH** и **Fallback**. Первые четыре предлагают Default / Plain / DoH;
Fallback — Default / Plain. Эквивалента двух DoT-серверов и цепочки
`system → DoT Yandex` в этих настройках нет.

Близкая настройка: для **IP Rules**, **Proxies**, **Subscriptions** и, если
используется ECH, **ECH** выбрать **DoH**, URL
`https://cloudflare-dns.com/dns-query`. Это Cloudflare, но HTTPS вместо
исходного TLS/853. Список из двух независимых DoT-адресов не воспроизводится.
Fallback оставить **Default** для системного поведения. Вариант Plain
`77.88.8.88` обращается к Yandex по незашифрованному DNS и не эквивалентен
исходному `tls://77.88.8.88:853`; автоматически он не включается.

Для работы GEOIP/CIDR по результату разрешения неизвестных доменов
**Prevent DNS Leak должен быть выключен**. Этот выбор нужен для приближения
к исходному GEOIP-роутингу. При включении функция проверки разрешённого IP
отключается; CIDR-наборы остаются полезны для подключения к буквальным IP.
Персональный `no-resolve` только у `domain_ips.list` выразить нельзя:
выключенный Prevent DNS Leak позволяет и этому списку участвовать в fallback.
Назначение DoH не обещает, что все DNS-запросы уйдут через VLESS.

| Исходная настройка | Перенос / ограничение |
|---|---|
| `dns-server = tls://1.0.0.1:853,tls://1.1.1.1:853` | Ручная замена на Cloudflare DoH; протокол и резервирование меняются. |
| `fallback-dns-server = system,tls://77.88.8.88:853` | Default близок к системному fallback; исходная последовательность не выражается. |
| `hijack-dns = :53` | Anywhere сам перехватывает DNS внутри туннеля; аналог настройки не содержится в `.arrs`. |
| `skip-proxy` | Все три private CIDR, `localhost`, `*.local`, `captive.apple.com` → DIRECT. Для имён используется suffix; для `*.local` добавляется и apex `local`. |
| `tun-excluded-routes` | Все исходные диапазоны → DIRECT, с объединением перекрытий. Пакеты всё ещё могут проходить движок туннеля; это не исключение маршрута из TUN. |
| `private-ip-answer = true` | Не управляется файлом правил. DIRECT для private IP не гарантирует такую же обработку ответа DNS. |
| `prefer-ipv6 = false`, `ipv6 = false` | Не управляются `.arrs`. GEOIP-наборы содержат IPv4 и IPv6 из upstream; наличие IPv6-правил само по себе не включает IPv6. Полное отключение IPv6 исходника не гарантируется. |
| `bypass-system = true` | Не выражается; локальные DIRECT-наборы покрывают указанные назначения, не все специальные системные потоки. |
| `udp-policy-not-supported-behaviour = REJECT` | Нет условного REJECT для неподдерживаемого UDP в `.arrs`. Зависит от поддержки UDP выбранным транспортом Anywhere. Глобальная блокировка UDP была бы другой политикой. |
| `always-real-ip = *` | Не воспроизводится: Anywhere использует Fake-IP. Отдельные DIRECT-правила не отключают Fake-IP глобально. |
| `localhost = 127.0.0.1` в `[Host]` | Hosts-подмена не импортируется. Добавлен DIRECT для `localhost` и исходный loopback CIDR; разрешение имени остаётся на устройстве. |
| `yaml = true` | Настройка формата Shadowrocket; для `.arrs` не нужна. |
| `always-reject-url-rewrite = false` | URL Rewrite в исходнике отсутствует; `.arrs` не управляет Rewrite. |
| `update-url` | Сохранён в исходнике, но не используется для автоматической замены источника истины. |

## Совпадения правил и неизбежные различия

| Shadowrocket | Anywhere | Различие |
|---|---|---|
| IPv4 CIDR / одиночный IPv4 | `0, network/prefix` | Одиночные IP получают `/32`; host bits нормализуются. |
| IPv6 CIDR / одиночный IPv6 | `1, network/prefix` | Одиночные IPv6 получают `/128`. |
| `DOMAIN-SUFFIX` | `2, suffix` | IDN переводятся в ASCII/Punycode: `рф` → `xn--p1ai`. Голые TLD `ru`, `su`, `psk` сохраняются. |
| `DOMAIN-KEYWORD` | `3, keyword` | Само условие совпадает, но приоритет относительно suffix отличается. |
| Точный `DOMAIN` / обычная строка DOMAIN-SET | `2, domain` | Включает дочерние домены: `.arrs` не имеет отдельного exact-domain типа. Это консервативное расширение, особенно для antifilter. |
| `.domain`, `*.domain` в списке | `2, domain` | Совпадает также сам `domain`, даже если исходный префикс означал только дочерние имена. |
| `+.domain` в reject.list | `2, domain` | `+.` интерпретируется как намерение «домен и поддомены». Это синтаксис upstream; принятие его Shadowrocket как DOMAIN-SET отдельно не проверено. |
| `DOMAIN-WILDCARD,*.vk*` и `DOMAIN-WILDCARD,vk*` | `3, vk` | Близкое объединение. Оно расширено: `avk.example` тоже DIRECT, хотя не начинается с `vk` и не содержит `.vk`. Для известных suffix-корней учитывается оригинальный wildcard. |
| `GEOIP,RU/KZ,DIRECT` | CIDR RU/KZ из Loyalsoldier/geoip | Это другая GeoIP-база, обновляемая upstream. Распределение стран может отличаться от базы Shadowrocket. |
| `RULE-SET,...,ACTION` | Нормализованные отдельные наборы | Действие берётся из родительского правила исходника. Содержимое может быть plain IP, plain domain или типизированным правилом. |
| `no-resolve` | Нет индивидуального аналога | Разрешение IP fallback регулируется настройкой Anywhere целиком. |
| `pre-matching` | Нет отдельной стадии в `.arrs` | Ранний keyword учитывается при компиляции известных корней; полный runtime-приоритет не воспроизводится. |
| `FINAL,PROXY` | Основной выбранный proxy/chain | Catch-all CIDR или keyword не добавляется: отсутствие совпадений использует основной маршрут. |

Shadowrocket применяет порядок правил. Anywhere внутри пользовательского
уровня выбирает suffix раньше keyword, более глубокий suffix раньше широкого,
а для IP — более длинный префикс. Перестановка наборов в интерфейсе разрешает
только одинаковые шаблоны и не возвращает линейную семантику.

Генератор компенсирует это в пределах выразимого формата:

- Для каждого известного suffix находит самое раннее подходящее доменное
  правило исходника и помещает suffix в набор с его итоговым действием.
  Например, `ads.yandex.com` из позднего reject получает DIRECT, а
  `adeventtracker.spotify.com` — PROXY по раннему antifilter.
- Для CIDR вычитает уже обработанные сети из поздних правил. Например,
  `127.0.0.1` из `domain_ips.list` остаётся локальным DIRECT. RU/KZ также
  сохраняют приоритет перед этим поздним IP-списком.
- Все наборы одного основного варианта проверяются на противоречащие
  действия у одинаковых шаблонов.

**Две границы остаются:**

1. Произвольные новые поддомены невозможно перечислить заранее. Например,
   `tiktok.bank.ru` в Anywhere попадёт под suffix `ru` → DIRECT раньше keyword
   `tiktok` → PROXY; `ads.yandex.some-reject-domain.example` попадёт под
   существующий REJECT suffix раньше keyword `yandex`. Известные корни
   компенсируются, бесконечное множество будущих имён — нет.
2. В Anywhere доменный вердикт принимается раньше CIDR. В исходнике GEOIP
   RU/KZ стоят перед поздними DIRECT/REJECT-доменами; в Anywhere REJECT-домен,
   который разрешается в RU/KZ IP, может остаться REJECT. Определять IP всех
   доменов при сборке было бы неточно из-за CDN и изменений DNS, поэтому это
   не делается. IP fallback применяется только к доменам без доменного совпадения
   и по документации проверяет реальный IPv4, не всю модель GEOIP Shadowrocket.

Подробные счётчики и первые 25 примеров каждого вида преобразования есть
в `dist/report.json`. Исходные DNS/General/Host-настройки тоже записаны там.

## Re:filter и переход со старого проекта

`dist/optional/refilter-domains-001.arrs` и `refilter-ip-001.arrs` — отдельные
PROXY-наборы из официального Re:filter. Они **не входят** в основные action-
или source-наборы. Их подключение расширяет политику Ru-Direct.conf; может
изменить DIRECT/REJECT при пересечениях. Для переноса исходника их оставить
неподключёнными. Отключить их скачивание можно через
`sources.json → refilter.enabled = false` или `--without-refilter`.

ECH/noECH-разделение старого генератора не переносится в основную схему:
в исходнике нет ECH → DIRECT. Кроме того, отсутствие домена в noECH-списке
не доказывает поддержку ECH. Старые `force-proxy.arrs`, `refilter-ech.arrs`,
`refilter-noech.arrs`, `refilter-all-domains.arrs`, `refilter-ip.arrs` в корне
`dist/` заменяются новой структурой. Их прежние подписки в Anywhere нужно
удалить либо отключить и подключить новые action-URL.

## Обновление в GitHub

Проект опубликован в [Conv3lsive/anywhere-refilter](https://github.com/Conv3lsive/anywhere-refilter).
Для дальнейших изменений обновить **содержимое** папки в этом репозитории.
В корне должны быть `build_rules.py`, `source/`,
`dist/`, `.github/`, а не ещё один вложенный `anywhere-refilter/`.
Публичные raw-URL доступны Anywhere без GitHub-авторизации.

В терминале из существующей папки проекта, после изменения исходника:

```sh
git add .
git commit -m "chore: update Ru-Direct routing policy"
git push origin main
```

Если GitHub просит войти снова: `gh auth login -h github.com`.
Архив содержит `.github/workflows/update.yml`, включая скрытую папку `.github`.

Затем **Actions → Update Anywhere Shadowrocket routing → Run workflow**.
Workflow скачивает списки, запускает тесты, собирает и проверяет `dist/`,
коммитит изменения только при наличии изменений. Ежедневное расписание:
**03:17 UTC = 06:17 по Москве**; фактический старт может задерживаться.
Обновление содержимого `source/` или генератора в `main` тоже запускает Action.
Schedule и ручной запуск используют default branch; при другой default branch
поменять `push.branches` в YAML. Автокоммит обновляет только `dist/`.

Workflow имеет `contents: write`. Если организация/репозиторий запрещает
запись токеном, проверить **Settings → Actions → General → Workflow permissions**.
Защита ветки может потребовать PR вместо автокоммита; данный workflow
использует обычный push и не обходит защиту. Он не делает force push.
GitHub может отключать schedule после 60 дней отсутствия активности публичного
репозитория; включить его снова через Actions при необходимости.

## Локальная сборка и проверка

```sh
python3 -m unittest discover -s tests -v
python3 build_rules.py
python3 build_rules.py --check
python3 build_rules.py --explain-host rutracker.ru
python3 build_rules.py --explain-host ads.yandex.com
python3 build_rules.py --explain-host ad.doubleclick.net
python3 build_rules.py --explain-ip 127.0.0.1
```

`--explain-host` и `--explain-ip` показывают решения **сгенерированного
пользовательского уровня**. Они не выполняют DNS, не эмулируют встроенные
наборы и не подтверждают фактический маршрут iOS.

Для повторения уже скачанной локальной сборки: `python3 build_rules.py --offline`.
Кэш хранится в `.cache/upstream/`, игнорируется Git и не включён в архив.
GitHub Action всегда скачивает свежие upstream и не использует offline/fallback
на старый кэш. Ошибка HTTP, пустой список, HTML вместо списка, неизвестный
тип правила или невалидный CIDR останавливают сборку. Старый `dist/`
сохраняется; автокоммит не выполняется. Переключение на новый `dist/`
происходит после успешной сборки и валидации. Отдельные подписки Anywhere
обновляются приложением независимо, общей атомарной транзакции между ними нет.

После подключения на устройстве проверить по журналу Anywhere:

| Назначение | Ожидаемая маршрутизация основной сборки |
|---|---|
| `rutracker.ru` | PROXY: antifilter раньше `.ru` DIRECT. |
| `bank131.com`, `mangalib.me`, `example.ru` | DIRECT: явные suffix-правила. |
| `browserleaks.com` | DIRECT: `domains_geo_detect.list`. |
| `ads.yandex.com`, `ad.mail.ru` | DIRECT: ранний keyword/TLD раньше позднего reject. |
| `ad.doubleclick.net` | REJECT, если upstream по-прежнему содержит соответствующий suffix. |
| `127.0.0.1`, `192.168.1.1` | DIRECT: исходные локальные исключения. |
| Неизвестный домен без совпадений и без RU/KZ IPv4 fallback | Основной VLESS/chain, то есть FINAL → PROXY. |

## Проверенные первичные источники

- [Anywhere: формат, приоритеты, лимиты и DNS/IP fallback](https://github.com/NodePassProject/Anywhere/blob/main/Documentations/Routing.md).
- [Anywhere: экран DNS-настроек](https://github.com/NodePassProject/Anywhere/blob/main/Anywhere/Views/Pages/AdvancedSettings/DNSSettingsView.swift).
- [Cloudflare: DoH endpoint](https://developers.cloudflare.com/1.1.1.1/encryption/dns-over-https/make-api-requests/).
- [Loyalsoldier/geoip: источник RU/KZ и текстовый формат](https://github.com/Loyalsoldier/geoip).
- [Re:filter: исходные списки](https://github.com/1andrevich/Re-filter-lists).
- [actions/setup-python: текущий пример checkout@v7 / setup-python@v7](https://github.com/actions/setup-python).
- [GitHub: автоматическое отключение schedule](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows).

Точные URL четырёх внешних списков сохраняются в исходном конфиге, а URL и
контрольные суммы каждой скачанной версии — в `dist/sources.lock.json`.
