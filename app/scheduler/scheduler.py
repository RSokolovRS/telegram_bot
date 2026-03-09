from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.scheduler import jobs


def create_scheduler(bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(jobs.notify_finished_trials, "interval", minutes=10, args=[bot], id="notify_trials")
    scheduler.add_job(
        jobs.delete_unpaid_after_trial,
        "interval",
        minutes=15,
        args=[bot],
        id="delete_unpaid_trials",
    )
    scheduler.add_job(
        jobs.notify_subscription_expiry,
        "interval",
        minutes=30,
        args=[bot],
        id="notify_sub_expiry",
    )
    scheduler.add_job(
        jobs.delete_expired_subscriptions,
        "interval",
        minutes=30,
        args=[bot],
        id="delete_expired_subs",
    )
    scheduler.add_job(jobs.check_sui_servers_health, "interval", minutes=5, id="sui_health")
    return scheduler
