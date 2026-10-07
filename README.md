# Anywhere + Re:filter

Готовые обновляемые наборы для Anywhere. Все ссылки ниже ведут в
[ваш репозиторий](https://github.com/Conv3lsive/anywhere-refilter); подставлять адреса не нужно.

## Добавить всю схему

### ECH / noECH — прежняя схема

**[➜ Добавить все 4 набора в Anywhere](https://conv3lsive.github.io/anywhere-refilter/?preset=ech&open=1)**

Открой ссылку на устройстве с установленным Anywhere и подтверди импорт.
Если приложение не открылось само, нажми **«Добавить в Anywhere»** на странице.
Ссылка передаёт четыре `.arrs` за одно открытие приложения.

| Набор | Куда направлять | При первом добавлении |
|---|---|---|
| **Force Proxy** | **PROXY** | Выбрать PROXY в Routing. |
| **ReFilter noECH — PROXY** | **PROXY** | Выбрать PROXY в Routing. |
| **ReFilter ECH — DIRECT** | **DIRECT** | Назначается автоматически из файла. |
| **ReFilter IP — PROXY** | **PROXY** | Выбрать PROXY в Routing. |

**Один раз после импорта:**

1. Выбери свой VLESS/chain основным маршрутом.
2. Включи режим **Rule**.
3. В **Routing** назначь **PROXY** наборам **Force Proxy**, **ReFilter noECH**
   и **ReFilter IP**. Для **ReFilter ECH** проверь **DIRECT**.
4. Поставь **Force Proxy выше ReFilter ECH** в списке Routing.
5. Включи **Country Bypass → Russia / RU**, чтобы остальные российские назначения
   шли напрямую. Остальной трафик использует основной VLESS/chain.

**Автоматически:** добавление списков одной ссылкой и начальный DIRECT для ECH.
**Вручную один раз:** PROXY, выбранный VLESS/chain, Rule и Country Bypass.
У Anywhere в `.arrs` нет начального назначения PROXY, а импорт-ссылка не
переключает режим или Country Bypass. Оставленный **Default** использует основной
маршрут, но имеет другой приоритет; для этой схемы выбери именно **PROXY**.
При обновлении подписок твои назначения сохраняются.

### Без разделения ECH

**[➜ Добавить схему без ECH в Anywhere](https://conv3lsive.github.io/anywhere-refilter/?preset=all&open=1)**

Добавляются **Force Proxy**, **ReFilter Domains** и **ReFilter IP** — всем трём
назначить **PROXY**. VLESS/chain, Rule и Country Bypass RU выбрать так же.
В этом варианте все домены Re:filter идут через прокси; ECH/noECH-подписки
отключить, чтобы DIRECT из другой схемы не вмешивался.

## Добавить отдельный набор

Кнопки «Добавить» открывают Anywhere через страницу импорта. Raw — постоянный
URL подписки для ручного добавления через Routing → Add / Subscribe from URL.

| Набор | Куда | Добавить | URL подписки |
|---|---|---|---|
| Force Proxy | **PROXY** | [Добавить](https://conv3lsive.github.io/anywhere-refilter/?set=force-proxy&open=1) | [Raw](https://raw.githubusercontent.com/Conv3lsive/anywhere-refilter/main/dist/force-proxy.arrs) |
| ReFilter noECH | **PROXY** | [Добавить](https://conv3lsive.github.io/anywhere-refilter/?set=refilter-noech&open=1) | [Raw](https://raw.githubusercontent.com/Conv3lsive/anywhere-refilter/main/dist/refilter-noech.arrs) |
| ReFilter ECH | **DIRECT** | [Добавить](https://conv3lsive.github.io/anywhere-refilter/?set=refilter-ech&open=1) | [Raw](https://raw.githubusercontent.com/Conv3lsive/anywhere-refilter/main/dist/refilter-ech.arrs) |
| ReFilter IP | **PROXY** | [Добавить](https://conv3lsive.github.io/anywhere-refilter/?set=refilter-ip&open=1) | [Raw](https://raw.githubusercontent.com/Conv3lsive/anywhere-refilter/main/dist/refilter-ip.arrs) |
| ReFilter Domains: все домены | **PROXY** | [Добавить](https://conv3lsive.github.io/anywhere-refilter/?set=refilter-all-domains&open=1) | [Raw](https://raw.githubusercontent.com/Conv3lsive/anywhere-refilter/main/dist/refilter-all-domains.arrs) |

Если списки уже добавлены, обнови существующие подписки в Anywhere.
Повторный импорт может создать ещё один набор. Если использовал перенос
Shadowrocket, отключи старые подписки `dist/actions/*` и подключи эти.

## Если кнопка не открывает приложение

Открой [страницу импорта](https://conv3lsive.github.io/anywhere-refilter/) в Safari
на iPhone/iPad или в браузере на Mac с Anywhere. Нажми **«Добавить в Anywhere»**.
Во встроенном браузере GitHub открытие приложений может требовать перехода в Safari.

Для ручного добавления копируй нужный URL целиком:

```text
https://raw.githubusercontent.com/Conv3lsive/anywhere-refilter/main/dist/force-proxy.arrs
https://raw.githubusercontent.com/Conv3lsive/anywhere-refilter/main/dist/refilter-noech.arrs
https://raw.githubusercontent.com/Conv3lsive/anywhere-refilter/main/dist/refilter-ech.arrs
https://raw.githubusercontent.com/Conv3lsive/anywhere-refilter/main/dist/refilter-ip.arrs
```

Для варианта без ECH вместо noECH/ECH используй:

```text
https://raw.githubusercontent.com/Conv3lsive/anywhere-refilter/main/dist/refilter-all-domains.arrs
```

GitHub README не запускает `anywhere://` как обычную ссылку. Поэтому кнопки ведут
на нашу HTTPS-страницу GitHub Pages, которая передаёт Anywhere его официальный
`anywhere://add-rule-set?link=…&link=…`. Страница не запрашивает данные твоего VLESS.

## DNS и порядок

- Для применения IP-правил к доменам без доменного совпадения
  **Prevent DNS Leak выключить**. При включении IP-набор остаётся полезен для
  подключений к буквальным IP, но проверка разрешённого IPv4 отключается.
- **Force Proxy** содержит `cloudflare-ech.com`. Его положение выше ECH
  разрешает совпадения одинаковых suffix-правил в пользу PROXY.
- Встроенные ADBlock и сервисные правила с явно назначенными действиями имеют
  приоритет над пользовательскими списками. Если нужен результат именно этой
  схемы, проверь их назначения отдельно.

## Автоматическое обновление

[GitHub Action](https://github.com/Conv3lsive/anywhere-refilter/actions/workflows/update.yml)
обновляет правила ежедневно в **03:17 UTC / 06:17 по Москве** и коммитит только
изменения. Для немедленного обновления: **Actions → Update Anywhere ReFilter rules
→ Run workflow**. После этого обнови подписки в Anywhere; GitHub Action не
управляет частотой обновления на твоём устройстве.

## Что лежит в репозитории

- `build_anywhere_refilter.py` — прежний Python-генератор Re:filter.
- `dist/*.arrs` — пять готовых наборов.
- `.github/workflows/update.yml` — ежедневный Action с автокоммитом.
- `docs/index.html` — страница массового и отдельного импорта.

Локальная сборка: `python3 build_anywhere_refilter.py`.

Разделение сохранено прежним: noECH — пересечение текущего Re:filter с
dnsmasq-списком Akiyamov; ECH — оставшиеся домены. Это практическое приближение:
отсутствие домена в noECH-списке само по себе не доказывает поддержку ECH.
Вариант без разделения использует весь Re:filter → PROXY.

Первичные источники: [импорт нескольких наборов](https://github.com/NodePassProject/Anywhere#import-rule-sets),
[формат и приоритеты Anywhere](https://github.com/NodePassProject/Anywhere/blob/main/Documentations/Routing.md),
[парсер начальных назначений](https://github.com/NodePassProject/Anywhere/blob/main/Anywhere/Views/Pages/Routing/RoutingRuleParser.swift),
[Re:filter](https://github.com/1andrevich/Re-filter-lists),
[Akiyamov noECH](https://github.com/Akiyamov/singbox-ech-list).
