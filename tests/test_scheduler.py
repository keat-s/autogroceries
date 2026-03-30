"""Tests for reminder settings and scheduler configuration."""

from __future__ import annotations

import pytest

from autogroceries.scheduler.reminders import (
    ReminderSettings,
    load_reminders,
    save_reminders,
)
from autogroceries.scheduler.scheduler import configure_scheduler, get_scheduler


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_storage(tmp_path, monkeypatch):
    """Redirect storage paths to tmp_path for test isolation."""
    monkeypatch.setattr("autogroceries.storage.DATA_DIR", tmp_path)
    monkeypatch.setattr("autogroceries.storage.RECIPES_DIR", tmp_path / "recipes")
    monkeypatch.setattr("autogroceries.storage.PLANS_DIR", tmp_path / "plans")
    monkeypatch.setattr(
        "autogroceries.scheduler.reminders.REMINDERS_PATH",
        tmp_path / "reminders.json",
    )
    monkeypatch.setattr(
        "autogroceries.scheduler.reminders.DATA_DIR",
        tmp_path,
    )


@pytest.fixture(autouse=True)
def _reset_scheduler(monkeypatch):
    """Reset the singleton scheduler between tests."""
    monkeypatch.setattr("autogroceries.scheduler.scheduler._scheduler", None)


# ---------------------------------------------------------------------------
# ReminderSettings model
# ---------------------------------------------------------------------------


class TestReminderSettings:
    def test_defaults(self) -> None:
        settings = ReminderSettings()
        assert settings.enabled is False
        assert settings.reminder_day == "sunday"
        assert settings.reminder_time == "09:00"
        assert settings.auto_generate_list is False
        assert settings.notification_method == "console"

    def test_to_dict_roundtrip(self) -> None:
        settings = ReminderSettings(
            enabled=True,
            reminder_day="saturday",
            reminder_time="10:30",
            auto_generate_list=True,
            notification_method="console",
        )
        data = settings.to_dict()
        restored = ReminderSettings.from_dict(data)
        assert restored == settings

    def test_from_dict_with_missing_keys(self) -> None:
        settings = ReminderSettings.from_dict({})
        assert settings.enabled is False
        assert settings.reminder_day == "sunday"


# ---------------------------------------------------------------------------
# Reminder storage
# ---------------------------------------------------------------------------


class TestReminderStorage:
    def test_save_and_load(self) -> None:
        settings = ReminderSettings(enabled=True, reminder_day="friday")
        save_reminders(settings)
        loaded = load_reminders()
        assert loaded.enabled is True
        assert loaded.reminder_day == "friday"

    def test_load_defaults_when_no_file(self) -> None:
        loaded = load_reminders()
        assert loaded.enabled is False


# ---------------------------------------------------------------------------
# Scheduler configuration
# ---------------------------------------------------------------------------


class TestSchedulerConfiguration:
    def test_disabled_scheduler_has_no_jobs(self) -> None:
        settings = ReminderSettings(enabled=False)
        scheduler = configure_scheduler(settings)
        ag_jobs = [j for j in scheduler.get_jobs() if j.id.startswith("autogroceries_")]
        assert len(ag_jobs) == 0

    def test_enabled_scheduler_adds_reminder_job(self) -> None:
        settings = ReminderSettings(enabled=True, reminder_day="monday", reminder_time="08:00")
        scheduler = configure_scheduler(settings)
        job_ids = [j.id for j in scheduler.get_jobs()]
        assert "autogroceries_planning_reminder" in job_ids
        assert "autogroceries_auto_shopping_list" not in job_ids

    def test_auto_generate_adds_second_job(self) -> None:
        settings = ReminderSettings(
            enabled=True,
            reminder_day="wednesday",
            reminder_time="09:00",
            auto_generate_list=True,
        )
        scheduler = configure_scheduler(settings)
        job_ids = [j.id for j in scheduler.get_jobs()]
        assert "autogroceries_planning_reminder" in job_ids
        assert "autogroceries_auto_shopping_list" in job_ids

    def test_reconfigure_removes_old_jobs(self) -> None:
        settings = ReminderSettings(enabled=True, auto_generate_list=True)
        scheduler = configure_scheduler(settings)
        assert len([j for j in scheduler.get_jobs() if j.id.startswith("autogroceries_")]) == 2

        # Disable
        settings_off = ReminderSettings(enabled=False)
        scheduler = configure_scheduler(settings_off)
        assert len([j for j in scheduler.get_jobs() if j.id.startswith("autogroceries_")]) == 0

    def test_get_scheduler_returns_singleton(self) -> None:
        s1 = get_scheduler()
        s2 = get_scheduler()
        assert s1 is s2
