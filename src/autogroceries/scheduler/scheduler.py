"""Background task scheduling using APScheduler.

Provides weekly reminders to plan meals and optional auto-generation
of shopping lists from the current meal plan.
"""

from __future__ import annotations

import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from autogroceries.planner.consolidator import generate_shopping_list, write_shopping_csv
from autogroceries.scheduler.reminders import ReminderSettings, load_reminders
from autogroceries.storage import list_plans, load_profile

logger = logging.getLogger(__name__)

DAYS_MAP = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    """Return the singleton BackgroundScheduler, creating it if needed."""
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
    return _scheduler


def send_planning_reminder() -> None:
    """Send a reminder to plan meals for the upcoming week.

    Currently logs to the console. Extensible to email/push later.
    """
    settings = load_reminders()
    if settings.notification_method == "console":
        logger.info(
            "Reminder: Time to plan your meals for the week! "
            "Run 'autogroceries plan' or visit the web UI."
        )


def auto_generate_shopping_list() -> None:
    """Auto-generate a shopping list from the most recent meal plan.

    Writes the CSV to the current directory using the plan name.
    """
    plans = list_plans()
    if not plans:
        logger.info("No meal plans found -- skipping auto-generate.")
        return

    plan = plans[-1]
    profile = load_profile()
    shopping_list = generate_shopping_list(plan, profile=profile)

    if not shopping_list:
        logger.info("Plan '%s' has no ingredients -- nothing to generate.", plan.name)
        return

    from pathlib import Path

    out = Path(f"{plan.name}-shopping.csv")
    write_shopping_csv(shopping_list, out)
    logger.info(
        "Auto-generated shopping list for '%s' (%d items) -> %s",
        plan.name,
        len(shopping_list),
        out,
    )


def configure_scheduler(settings: ReminderSettings | None = None) -> BackgroundScheduler:
    """Configure (or reconfigure) scheduler jobs from reminder settings.

    Args:
        settings: Reminder settings. If None, loads from disk.

    Returns:
        The configured BackgroundScheduler instance.
    """
    if settings is None:
        settings = load_reminders()

    scheduler = get_scheduler()

    # Remove existing autogroceries jobs before reconfiguring
    for job in scheduler.get_jobs():
        if job.id.startswith("autogroceries_"):
            job.remove()

    if not settings.enabled:
        return scheduler

    # Parse time
    hour, minute = 9, 0
    if ":" in settings.reminder_time:
        parts = settings.reminder_time.split(":")
        hour, minute = int(parts[0]), int(parts[1])

    day_of_week = DAYS_MAP.get(settings.reminder_day.lower(), 6)

    # Weekly planning reminder
    scheduler.add_job(
        send_planning_reminder,
        trigger=CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute),
        id="autogroceries_planning_reminder",
        replace_existing=True,
    )

    # Optional auto-generate shopping list (runs 30 min after reminder)
    if settings.auto_generate_list:
        list_minute = (minute + 30) % 60
        list_hour = hour + ((minute + 30) // 60)
        scheduler.add_job(
            auto_generate_shopping_list,
            trigger=CronTrigger(day_of_week=day_of_week, hour=list_hour, minute=list_minute),
            id="autogroceries_auto_shopping_list",
            replace_existing=True,
        )

    return scheduler
