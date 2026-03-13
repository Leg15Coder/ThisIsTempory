from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from app.core.config import get_settings

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
except Exception:
    service_account = None
    build = None


class GoogleCalendarService:
    """Минимальная интеграция с Google Calendar API через service account."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.calendar_id = self.settings.google_calendar_id or "primary"
        self.scopes = ["https://www.googleapis.com/auth/calendar"]

    @property
    def enabled(self) -> bool:
        return bool(self.settings.google_calendar_service_account_file)

    def _get_client(self):
        if service_account is None or build is None:
            raise RuntimeError("Google Calendar dependencies не установлены")
        if not self.settings.google_calendar_service_account_file:
            raise RuntimeError("Не настроен GOOGLE_CALENDAR_SERVICE_ACCOUNT_FILE")
        credentials = service_account.Credentials.from_service_account_file(
            self.settings.google_calendar_service_account_file,
            scopes=self.scopes,
        )
        return build("calendar", "v3", credentials=credentials, cache_discovery=False)

    def list_events(self, date_from: Optional[str] = None, date_to: Optional[str] = None) -> dict[str, Any]:
        if not self.enabled:
            return {"events": [], "source": "stub", "enabled": False}
        service = self._get_client()
        events = service.events().list(
            calendarId=self.calendar_id,
            timeMin=date_from,
            timeMax=date_to,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        return {"events": events.get("items", []), "source": "google_calendar", "enabled": True}

    def create_event(self, event_data: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            return {"created": False, "event": event_data, "source": "stub", "enabled": False}
        service = self._get_client()
        title = event_data.get("title") or event_data.get("name") or "Новое событие"
        description = event_data.get("description") or ""
        start_iso = event_data.get("start") or self._combine_date_time(event_data.get("date"), event_data.get("time"))
        end_iso = event_data.get("end") or start_iso
        body = {
            "summary": title,
            "description": description,
            "start": {"dateTime": start_iso},
            "end": {"dateTime": end_iso},
        }
        created = service.events().insert(calendarId=self.calendar_id, body=body).execute()
        return {"created": True, "event": created, "source": "google_calendar", "enabled": True}

    @staticmethod
    def _combine_date_time(date_value: Optional[str], time_value: Optional[str]) -> str:
        date_part = date_value or datetime.now().date().isoformat()
        time_part = time_value or "09:00"
        if len(time_part) == 5:
            time_part = f"{time_part}:00"
        return f"{date_part}T{time_part}"

