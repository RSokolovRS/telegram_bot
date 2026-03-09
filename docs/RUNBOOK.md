# Runbook: staging / production

## 1. DNS и Cloudflare
1. Установите `A` записи `sokolrock.org` и `staging.sokolrock.org` на `185.250.151.137`.
2. Cloudflare: режим `DNS only` (серое облако).

## 2. Подготовка VPS
1. Установите Docker + Docker Compose plugin.
2. Клонируйте проект в `/opt/vpnbot`.
3. Создайте `.env` и `.env.staging` из `.env.example`.
4. Заполните `BOT_TOKEN`, `YOO_KASSA_*`, `WEBHOOK_SHARED_SECRET`, `DATABASE_URL`.

## 3. Первый выпуск сертификатов Let’s Encrypt
1. Запустите только `nginx` и `certbot`.
2. Выполните вручную:
   ```bash
   docker compose run --rm certbot certonly --webroot -w /var/www/certbot -d sokolrock.org --email admin@sokolrock.org --agree-tos --no-eff-email
   docker compose -f docker-compose.staging.yml run --rm certbot certonly --webroot -w /var/www/certbot -d staging.sokolrock.org --email admin@sokolrock.org --agree-tos --no-eff-email
   ```
3. Перезапустите `nginx`.

## 4. Staging deploy
1. `git checkout develop && git pull`
2. `docker compose -f docker-compose.staging.yml --env-file .env.staging up -d --build`
3. `docker compose -f docker-compose.staging.yml --env-file .env.staging exec app alembic upgrade head`
4. Проверка: `curl -k https://staging.sokolrock.org:8443/health`

## 5. Production deploy
1. `git checkout main && git pull`
2. `docker compose --env-file .env up -d --build`
3. `docker compose --env-file .env exec app alembic upgrade head`
4. Проверка: `curl https://sokolrock.org/health`

## 6. Обновление сертификатов
- Certbot container уже запускает renew-loop каждые 12 часов.
- Добавьте host cron для перезагрузки nginx после renew:
  ```bash
  15 */12 * * * cd /opt/vpnbot && docker compose exec -T nginx nginx -s reload
  ```

## 7. Webhook URLs
- YooKassa: `https://<domain>/api/webhooks/yookassa`
- Crypto: `https://<domain>/api/webhooks/crypto`

## 8. Операционные команды
- Логи: `make logs`
- Миграции: `make migrate`
- Тесты: `make test`
- Линт: `make lint`
