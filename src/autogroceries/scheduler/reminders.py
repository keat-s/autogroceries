"""ReminderSettings model and JSON file storage."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from autogroceries.storage import DATA_DIR


REMINDERS_PATH = DATA_DIR / "reminders.json"


@dataclass
class ReminderSettings:
    """Configuration for weekly meal-planning reminders."""

    enabled: bool = False
    reminder_day: str = "sunday"
    reminder_time: str = "09:00"
    auto_generate_list: bool = False
    notification_method: str = "console"

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "reminder_day": self.reminder_day,
            "reminder_time": self.reminder_time,
            "auto_generate_list": self.auto_generate_list,
            "notification_method": self.notification_method,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReminderSettings:
        return cls(
            enabled=data.get("enabled", False),
            reminder_day=data.get("reminder_day", "sunday"),
            reminder_time=data.get("reminder_time", "09:00"),
            auto_generate_list=data.get("auto_generate_list", False),
            notification_method=data.get("notification_method", "console"),
        )


def save_reminders(settings: ReminderSettings) -> Path:
    """Save reminder settings to disk as JSON."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REMINDERS_PATH.write_text(json.dumps(settings.to_dict(), indent=2))
    return REMINDERS_PATH


def load_reminders() -> ReminderSettings:
    """Load reminder settings, or return defaults if none exist."""
    if not REMINDERS_PATH.exists():
        return ReminderSettings()
    data = json.loads(REMINDERS_PATH.read_text())
    return ReminderSettings.from_dict(data)
