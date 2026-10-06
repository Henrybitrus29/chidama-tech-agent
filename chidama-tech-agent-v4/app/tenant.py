"""A tenant is one business: its identity, rules, booking hours and synonyms. Loaded from tenant.json."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class TenantError(ValueError):
    pass


@dataclass(frozen=True)
class BookingConfig:
    enabled: bool = False
    slot_minutes: int = 30
    days_ahead: int = 45
    min_notice_hours: int = 4
    hours: dict = field(default_factory=dict)        # weekday index -> (start time, end time)
    topics: tuple[str, ...] = ()


@dataclass(frozen=True)
class Tenant:
    slug: str
    business_name: str
    assistant_name: str
    about: str
    welcome_message: str
    suggested_questions: tuple[str, ...]
    timezone: str
    booking: BookingConfig
    synonyms: dict
    extra_rules: tuple[str, ...]
    handoff_text: str
    privacy_notice: str

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def slots_for(self, day: date, now: datetime) -> list[datetime]:
        """Bookable start times on `day` (timezone-aware, in the business timezone)."""
        b = self.booking
        if not b.enabled or day.weekday() not in b.hours:
            return []
        start, end = b.hours[day.weekday()]
        earliest = now + timedelta(hours=b.min_notice_hours)
        latest = now + timedelta(days=b.days_ahead)
        cursor = datetime.combine(day, start, tzinfo=self.tz)
        close = datetime.combine(day, end, tzinfo=self.tz)
        slots = []
        while cursor + timedelta(minutes=b.slot_minutes) <= close:
            if earliest <= cursor <= latest:
                slots.append(cursor)
            cursor += timedelta(minutes=b.slot_minutes)
        return slots


def _parse_time(value: str, where: str) -> time:
    try:
        h, m = value.split(":")
        return time(int(h), int(m))
    except Exception as exc:
        raise TenantError(f"{where}: '{value}' is not HH:MM") from exc


def _require(data: dict, key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TenantError(f"tenant.json is missing a non-empty '{key}'")
    return value.strip()


def parse_tenant(slug: str, data: dict) -> Tenant:
    tz = data.get("timezone", "UTC")
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise TenantError(f"unknown timezone '{tz}'") from exc

    raw = data.get("booking") or {}
    hours: dict = {}
    for name, window in (raw.get("hours") or {}).items():
        if name.lower() not in DAYS:
            raise TenantError(f"booking.hours: '{name}' is not one of {DAYS}")
        if not (isinstance(window, list) and len(window) == 2):
            raise TenantError(f"booking.hours.{name} must be [start, end]")
        start, end = _parse_time(window[0], f"booking.hours.{name}"), _parse_time(window[1], f"booking.hours.{name}")
        if start >= end:
            raise TenantError(f"booking.hours.{name}: start must be before end")
        hours[DAYS.index(name.lower())] = (start, end)
    booking = BookingConfig(
        enabled=bool(raw.get("enabled", False)) and bool(hours),
        slot_minutes=int(raw.get("slot_minutes", 30)),
        days_ahead=int(raw.get("days_ahead", 45)),
        min_notice_hours=int(raw.get("min_notice_hours", 4)),
        hours=hours,
        topics=tuple(raw.get("topics", ())),
    )
    if booking.slot_minutes < 10:
        raise TenantError("booking.slot_minutes must be at least 10")

    return Tenant(
        slug=slug,
        business_name=_require(data, "business_name"),
        assistant_name=_require(data, "assistant_name"),
        about=_require(data, "about"),
        welcome_message=_require(data, "welcome_message"),
        suggested_questions=tuple(data.get("suggested_questions", ())),
        timezone=tz,
        booking=booking,
        synonyms={k: list(v) for k, v in (data.get("synonyms") or {}).items()},
        extra_rules=tuple(data.get("extra_rules", ())),
        handoff_text=data.get("handoff_text", "A team member will follow up with you soon."),
        privacy_notice=data.get("privacy_notice", "Chats are processed by an AI service and stored briefly to help the team follow up."),
    )


def load_tenant(knowledge_dir: str | Path, slug: str) -> Tenant:
    path = Path(knowledge_dir) / slug / "tenant.json"
    if not path.is_file():
        raise TenantError(f"no tenant.json at {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TenantError(f"{path} is not valid JSON: {exc}") from exc
    return parse_tenant(slug, data)
