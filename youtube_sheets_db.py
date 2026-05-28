import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import gspread
from google.oauth2.service_account import Credentials

from config import Settings, load_service_account_info


logger = logging.getLogger(__name__)


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


@dataclass(frozen=True)
class YouTubeSheetRow:
    row_number: int
    channel_url: str
    status: str


class YouTubeSheetsDB:
    """Google Sheets access layer for Sheet2 YouTube influencer analysis."""

    COL_CHANNEL_URL = 1
    COL_SUBSCRIBERS = 2
    COL_AVG_SHORTS_VIEWS = 3
    COL_AVG_LONGFORM_VIEWS = 4
    COL_SHORTS_COUNT = 5
    COL_LONGFORM_COUNT = 6
    COL_AVG_COMMENTS = 7
    COL_ENGAGEMENT_RATE = 8
    COL_CATEGORY = 9
    COL_GRADE = 10
    COL_AI_COMMENT = 11
    COL_TRIGGER = 12
    COL_STATUS = 13

    HEADER = [
        "Channel URL",
        "Subscribers",
        "Avg Shorts Views",
        "Avg Longform Views",
        "Shorts Count",
        "Longform Count",
        "Avg Comments",
        "Engagement Rate",
        "Category",
        "Grade",
        "AI Comment",
        "Trigger",
        "Status",
    ]

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = self._authorize()
        self.sheet = self.client.open_by_url(settings.spreadsheet_url)
        self.worksheet = self._get_or_create_worksheet(settings.youtube_worksheet_name)
        self.ensure_header()

    def _authorize(self) -> gspread.Client:
        service_account_info = load_service_account_info(self.settings)
        if service_account_info:
            credentials = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
        elif self.settings.google_service_account_file:
            credentials = Credentials.from_service_account_file(self.settings.google_service_account_file, scopes=SCOPES)
        else:
            raise RuntimeError("Google service account credentials are not configured.")
        return gspread.authorize(credentials)

    def _get_or_create_worksheet(self, worksheet_name: str) -> gspread.Worksheet:
        try:
            return self.sheet.worksheet(worksheet_name)
        except gspread.WorksheetNotFound:
            logger.info("Worksheet '%s' was not found. Creating it for YouTube analysis.", worksheet_name)
            return self.sheet.add_worksheet(title=worksheet_name, rows=1000, cols=len(self.HEADER))

    def ensure_header(self) -> None:
        current_header = self.worksheet.row_values(1)
        if current_header[: len(self.HEADER)] != self.HEADER:
            logger.info("Writing YouTube header row to worksheet '%s'.", self.worksheet.title)
            self.worksheet.update("A1:M1", [self.HEADER], value_input_option="USER_ENTERED")

    @staticmethod
    def _is_true(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().upper() in {"TRUE", "YES", "Y", "1", "CHECKED"}

    def get_triggered_rows(self) -> List[YouTubeSheetRow]:
        rows = self.worksheet.get_all_values()
        triggered_rows: List[YouTubeSheetRow] = []

        for index, row in enumerate(rows[1:], start=2):
            channel_url = row[self.COL_CHANNEL_URL - 1].strip() if len(row) >= self.COL_CHANNEL_URL else ""
            trigger = row[self.COL_TRIGGER - 1] if len(row) >= self.COL_TRIGGER else ""
            status = row[self.COL_STATUS - 1].strip().upper() if len(row) >= self.COL_STATUS else ""

            if not channel_url:
                continue
            if not self._is_true(trigger):
                continue
            if status in {"RUNNING", "PROCESSING"}:
                continue

            triggered_rows.append(YouTubeSheetRow(row_number=index, channel_url=channel_url, status=status))

        return triggered_rows

    def mark_running(self, row_number: int) -> None:
        self.worksheet.update(f"M{row_number}", [["RUNNING"]], value_input_option="USER_ENTERED")

    def write_success(self, row_number: int, result: Dict[str, Any]) -> None:
        values = [[
            result.get("subscribers", 0),
            result.get("avg_shorts_views", 0),
            result.get("avg_longform_views", 0),
            result.get("shorts_count", 0),
            result.get("longform_count", 0),
            result.get("avg_comments", 0),
            result.get("engagement_rate", "0.00%"),
            result.get("category", "기타"),
            result.get("grade", "N/A"),
            result.get("ai_comment", ""),
            False,
            "DONE",
        ]]
        self.worksheet.update(f"B{row_number}:M{row_number}", values, value_input_option="USER_ENTERED")

    def write_failure(self, row_number: int, error_message: str) -> None:
        safe_message = str(error_message)[:500]
        values = [[
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            safe_message,
            False,
            "FAILED",
        ]]
        self.worksheet.update(f"B{row_number}:M{row_number}", values, value_input_option="USER_ENTERED")

    def clear_trigger(self, row_number: int) -> None:
        self.worksheet.update(f"L{row_number}", [[False]], value_input_option="USER_ENTERED")

    def get_basic_status(self) -> Dict[str, Optional[str]]:
        return {
            "spreadsheet_title": self.sheet.title,
            "worksheet_title": self.worksheet.title,
        }
