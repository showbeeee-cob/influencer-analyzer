import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables."""

    spreadsheet_url: str
    worksheet_name: str
    youtube_worksheet_name: str
    polling_interval_seconds: int

    google_service_account_json: Optional[str]
    google_service_account_file: Optional[str]

    apify_token: str
    apify_actor_id: str
    apify_results_limit: int
    apify_timeout_seconds: int

    gemini_api_key: str
    gemini_model: str

    youtube_api_key: str
    youtube_recent_video_limit: int
    youtube_request_timeout_seconds: int

    flask_host: str
    flask_port: int
    log_level: str


def _get_first_env(*names: str, default: str = "") -> str:
    """Return the first non-empty environment variable from a list of aliases."""
    for name in names:
        raw_value = os.getenv(name)
        if raw_value is not None and str(raw_value).strip() != "":
            return str(raw_value).strip()
    return default


def _get_int(*names: str, default: int) -> int:
    raw_value = _get_first_env(*names)
    if raw_value == "":
        return default
    try:
        return int(raw_value)
    except ValueError as exc:
        joined_names = " or ".join(names)
        raise ValueError(f"Environment variable {joined_names} must be an integer. Current value: {raw_value}") from exc


def _get_spreadsheet_url() -> str:
    spreadsheet_url = _get_first_env("GOOGLE_SHEET_URL", "GOOGLE_SPREADSHEET_URL")
    if spreadsheet_url:
        return spreadsheet_url

    spreadsheet_id = _get_first_env("GOOGLE_SHEETS_ID", "GOOGLE_SPREADSHEET_ID")
    if spreadsheet_id:
        return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"

    return "https://docs.google.com/spreadsheets/d/1VBdahTl8s-qzGszqYCm2wrDw0IKC9QoGF-dRLej-o7o/edit?usp=sharing"


def get_settings() -> Settings:
    return Settings(
        spreadsheet_url=_get_spreadsheet_url(),
        worksheet_name=os.getenv("GOOGLE_WORKSHEET_NAME", "Sheet1"),
        youtube_worksheet_name=os.getenv("YOUTUBE_WORKSHEET_NAME", "Sheet2"),
        polling_interval_seconds=_get_int("POLLING_INTERVAL_SECONDS", "POLL_INTERVAL_SECONDS", default=10),
        google_service_account_json=os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"),
        google_service_account_file=os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE"),
        apify_token=os.getenv("APIFY_TOKEN", ""),
        apify_actor_id=os.getenv("APIFY_ACTOR_ID", "apify/instagram-scraper"),
        apify_results_limit=_get_int("APIFY_RESULTS_LIMIT", default=12),
        apify_timeout_seconds=_get_int("APIFY_TIMEOUT_SECONDS", default=300),
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
        youtube_api_key=os.getenv("YOUTUBE_API_KEY", ""),
        youtube_recent_video_limit=_get_int("YOUTUBE_RECENT_VIDEO_LIMIT", default=30),
        youtube_request_timeout_seconds=_get_int("YOUTUBE_REQUEST_TIMEOUT_SECONDS", default=20),
        flask_host=os.getenv("FLASK_HOST", "0.0.0.0"),
        flask_port=_get_int("PORT", default=10000),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )


def load_service_account_info(settings: Settings) -> Optional[Dict[str, Any]]:
    """Load a Google service account JSON object from env var or file path.

    Render 환경에서는 파일 업로드보다 환경변수 입력이 편할 때가 많기 때문에
    GOOGLE_SERVICE_ACCOUNT_JSON을 우선 사용하고, 없으면 GOOGLE_SERVICE_ACCOUNT_FILE을 사용합니다.
    """

    if settings.google_service_account_json:
        try:
            return json.loads(settings.google_service_account_json)
        except json.JSONDecodeError as exc:
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON.") from exc

    if settings.google_service_account_file:
        with open(settings.google_service_account_file, "r", encoding="utf-8") as file:
            return json.load(file)

    return None


def validate_required_settings(settings: Settings) -> None:
    missing = []

    if not settings.spreadsheet_url:
        missing.append("GOOGLE_SHEET_URL or GOOGLE_SHEETS_ID")
    if not settings.google_service_account_json and not settings.google_service_account_file:
        missing.append("GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_FILE")
    if not settings.apify_token:
        missing.append("APIFY_TOKEN")
    if not settings.gemini_api_key:
        missing.append("GEMINI_API_KEY")

    if missing:
        raise RuntimeError("Missing required environment variables: " + ", ".join(missing))
