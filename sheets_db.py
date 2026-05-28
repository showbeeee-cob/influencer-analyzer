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
class SheetRow:
    row_number: int
    url: str
    status: str


class SheetsDB:
    """Google Sheets data-access layer for the Instagram influencer analyzer.

    Sheet layout after this fix:
    A URL
    B Followers
    C Avg Likes
    D Avg Comments
    E Avg Views
    F Avg Shares
    G ER
    H Grade
    I Trigger
    J Status
    K Tier
    L Category
    M 견적

    Profile image URLs are intentionally no longer written to the sheet.
    """

    COL_URL = 1
    COL_FOLLOWERS = 2
    COL_AVG_LIKES = 3
    COL_AVG_COMMENTS = 4
    COL_AVG_VIEWS = 5
    COL_AVG_SHARES = 6
    COL_ER = 7
    COL_GRADE = 8
    COL_TRIGGER = 9
    COL_STATUS = 10
    COL_TIER = 11
    COL_CATEGORY = 12
    COL_QUOTE = 13

    HEADER = [
        "URL",
        "Followers",
        "Avg Likes",
        "Avg Comments",
        "Avg Views",
        "Avg Shares",
        "ER",
        "Grade",
        "Trigger",
        "Status",
        "Tier",
        "Category",
        "견적",
    ]

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = self._authorize()
        self.sheet = self.client.open_by_url(settings.spreadsheet_url)
        self.worksheet = self._get_worksheet(settings.worksheet_name)
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

    def _get_worksheet(self, worksheet_name: str) -> gspread.Worksheet:
        try:
            return self.sheet.worksheet(worksheet_name)
        except gspread.WorksheetNotFound:
            logger.warning("Worksheet '%s' was not found. Falling back to the first worksheet.", worksheet_name)
            return self.sheet.sheet1

    def ensure_header(self) -> None:
        """Normalize the header row while preserving any existing quote column values.

        If the existing sheet still has K=Image URL and L=견적, this method changes K to Tier,
        L to Category, and M to 견적. Existing non-empty quote values in L are copied to M first.
        """
        current_header = self.worksheet.row_values(1)
        l_header = current_header[11].strip() if len(current_header) >= 12 else ""
        m_header = current_header[12].strip() if len(current_header) >= 13 else ""

        if l_header == "견적" and not m_header:
            try:
                quote_values = self.worksheet.col_values(self.COL_CATEGORY)
                if len(quote_values) > 1:
                    body_values = quote_values[1:]
                    rows_to_copy = [[value] for value in body_values]
                    if any(value[0] for value in rows_to_copy):
                        self.worksheet.update(
                            f"M2:M{len(rows_to_copy) + 1}",
                            rows_to_copy,
                            value_input_option="USER_ENTERED",
                        )
            except Exception as exc:
                logger.warning("Failed to preserve existing quote column values: %s", exc)

        if current_header[: len(self.HEADER)] != self.HEADER:
            logger.info("Writing expected header row to Google Sheets.")
            self.worksheet.update("A1:M1", [self.HEADER], value_input_option="USER_ENTERED")

    @staticmethod
    def _is_true(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().upper() in {"TRUE", "YES", "Y", "1", "CHECKED"}

    def get_triggered_rows(self) -> List[SheetRow]:
        rows = self.worksheet.get_all_values()
        triggered_rows: List[SheetRow] = []

        for index, row in enumerate(rows[1:], start=2):
            url = row[self.COL_URL - 1].strip() if len(row) >= self.COL_URL else ""
            trigger = row[self.COL_TRIGGER - 1] if len(row) >= self.COL_TRIGGER else ""
            status = row[self.COL_STATUS - 1].strip().upper() if len(row) >= self.COL_STATUS else ""

            if url and self._is_true(trigger) and status != "RUNNING":
                triggered_rows.append(SheetRow(row_number=index, url=url, status=status))

        return triggered_rows

    def mark_running(self, row_number: int) -> None:
        self.worksheet.update(f"J{row_number}", [["RUNNING"]], value_input_option="USER_ENTERED")

    def write_success(self, row_number: int, result: Dict[str, Any]) -> None:
        values = [[
            result.get("followers", 0),
            result.get("avg_likes", 0),
            result.get("avg_comments", 0),
            result.get("avg_views", 0),
            result.get("avg_shares", 0),
            result.get("engagement_rate", "0.00%"),
            result.get("grade", "N/A"),
            False,
            "DONE",
            result.get("tier", ""),
            result.get("category", ""),
        ]]
        self.worksheet.update(f"B{row_number}:L{row_number}", values, value_input_option="USER_ENTERED")

    def write_failure(self, row_number: int, error_message: str) -> None:
        safe_message = error_message[:800]
        values = [[
            "",
            "",
            "",
            "",
            "",
            "",
            "N/A",
            False,
            f"FAILED: {safe_message}",
            "",
            "",
        ]]
        self.worksheet.update(f"B{row_number}:L{row_number}", values, value_input_option="USER_ENTERED")

    def clear_trigger(self, row_number: int) -> None:
        self.worksheet.update(f"I{row_number}", [[False]], value_input_option="USER_ENTERED")

    def update_status(self, row_number: int, status: str) -> None:
        self.worksheet.update(f"J{row_number}", [[status]], value_input_option="USER_ENTERED")

    def get_basic_status(self) -> Dict[str, Optional[str]]:
        return {
            "spreadsheet_title": self.sheet.title,
            "worksheet_title": self.worksheet.title,
        }
