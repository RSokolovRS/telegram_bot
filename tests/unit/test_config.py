from app.core.config import Settings


def test_parse_admin_ids() -> None:
    settings = Settings(
        bot_token="x",
        admin_telegram_ids="1,2,3",
        database_url="postgresql+psycopg://x:x@localhost:5432/x",
        webhook_shared_secret="x",
        yoo_kassa_shop_id="x",
        yoo_kassa_secret_key="x",
        yoo_kassa_return_url="https://example.com",
    )
    assert settings.admin_telegram_ids == [1, 2, 3]
