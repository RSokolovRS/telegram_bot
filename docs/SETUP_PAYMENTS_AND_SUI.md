# Настройка CryptoBot платежей и S-UI (HY2 + VLESS)

Этот проект поднимает **Telegram-бота** и **FastAPI** (вебхуки) в одном контейнере.

Цель:
- **Оплата через CryptoBot (Crypto Pay API)** — включена и защищена подписью.
- **YooKassa** — **временно отключена** (заглушка).
- **S-UI (alireza0/s-ui)** — создание одного клиента **сразу в двух inbound** (HY2 + VLESS) по подписке `/sub/...`.

---

## 1) Переменные окружения

Скопируй `.env.example` в `.env` (или `.env.staging` для staging compose) и заполни:

### Обязательное (бот + БД)
- `BOT_TOKEN`
- `DATABASE_URL`

### CryptoBot (обязательно)
- `CRYPTO_PROVIDER=cryptobot`
- `CRYPTO_BOT_TOKEN=<токен Crypto Pay API>`
- `CRYPTO_BOT_API_BASE=https://pay.crypt.bot/api`

### Webhook подпись (CryptoBot)
Crypto webhook проверяется по заголовку **`Crypto-Pay-API-Signature`** и секрету **`CRYPTO_BOT_TOKEN`**.

> Важно: если подписи нет — сервер вернёт `401`.

### S-UI (обязательно для выдачи доступа)
Рекомендованная конфигурация под nginx-прокси, как в твоём `Docker_S-UI-SAIT`:
- `SUI_PANEL_BASE_PATH=/app`
- `SUI_DEFAULT_PATH_PREFIX=/sub/`
- `SUI_API_TOKEN=<API token из панели S-UI>`
- `SUI_INBOUND_IDS=<hy2_inbound_id>,<vless_inbound_id>`

---

## 2) Как узнать inbound ID (HY2 и VLESS) в S-UI

Нужны **числовые** inbound id (например `10` и `11`), а не названия вида `hysteria2-23999`.

Через APIv2:

```bash
curl -sS -H "Token: <SUI_API_TOKEN>" \
  "https://panel.fish-house.su/app/apiv2/inbounds"
```

В JSON найди два inbound’а (HY2 и VLESS) и выпиши их поля `id`.
Поставь их в:

```bash
SUI_INBOUND_IDS=10,11
```

---

## 3) Настройка webhook’ов CryptoBot

### URL webhook’а
В этом проекте endpoint:
- `POST /api/webhooks/crypto`

Значит внешний URL будет примерно:
- `https://<твой-домен>/api/webhooks/crypto`

### Подпись webhook’а
CryptoBot присылает подпись в `Crypto-Pay-API-Signature`.
Сервер проверяет:
\[
HMAC\_SHA256(raw\_body,\; CRYPTO\_BOT\_TOKEN)
\]

---

## 4) YooKassa выключена (заглушка)

Сейчас:
- создание инвойса YooKassa **выключено** (будет ошибка “temporarily disabled”)
- webhook `/api/webhooks/yookassa` отвечает `501`

Это сделано намеренно, чтобы случайно не принимать платежи через неготовый контур.

---

## 5) Вариант B: один клиент на HY2 + VLESS

### Логика
При выдаче триала/подписки создаётся клиент:
- имя: `trial-<telegram_id>` или `sub-<telegram_id>`
- добавляется **сразу** в inbound’ы из `SUI_INBOUND_IDS` (или из колонки `servers.inbound_ids`, если она заполнена)
- пользователю сохраняется `subscription_url` вида:
  - `https://panel.fish-house.su/sub/<client_id>`

### Где хранить inbound’ы
Есть два способа:
- **в ENV**: `SUI_INBOUND_IDS=10,11`
- **в БД**: колонка `servers.inbound_ids` (строка `"10,11"`)

Приоритет: **БД `servers.inbound_ids` → ENV `SUI_INBOUND_IDS` → старое поле `servers.inbound_id`**.

---

## 6) Миграции БД

Добавлена миграция:
- `alembic/versions/20260325_0002_server_inbound_ids.py`

Контейнер сам запускает миграции в `deploy/entrypoint.sh`:
- `alembic upgrade head`

Если запускаешь вручную:

```bash
alembic upgrade head
```

---

## 7) Проверка “всё работает”

### 7.1 Проверить, что API жив

```bash
curl -k https://<твой-домен>/health
```

### 7.2 Создать crypto invoice из бота
В боте:
- “Купить подписку” → выбрать сервер → план → провайдер `crypto`

Ожидаемо: бот пришлёт ссылку `pay_url` от CryptoBot.

### 7.3 Принять webhook
После оплаты CryptoBot должен прислать webhook на `/api/webhooks/crypto`.
Ожидаемо:
- инвойс станет `PAID`
- создастся `VpnAccount`
- в S-UI появится клиент (в HY2 + VLESS inbound’ах)

---

## 8) Примечания про домены hy2.* и vless.*

Домены `hy2.fish-house.su` и `vless.fish-house.su` важны для SNI-маршрутизации на 443 (у тебя это сделано в nginx stream).
Но для бота и выдачи подписки ключевое — чтобы:
- `/sub/` проксировался на `s-ui:2096`
- и S-UI корректно генерировал sub для клиента

