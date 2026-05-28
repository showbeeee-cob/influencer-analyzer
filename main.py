import logging
import os
import signal
import threading
import time
from datetime import datetime, timezone
from typing import Optional

from flask import Flask, jsonify

from analyzer import InfluencerAnalyzer
from config import Settings, get_settings, validate_required_settings
from sheets_db import SheetsDB
from youtube_analyzer import YouTubeInfluencerAnalyzer
from youtube_sheets_db import YouTubeSheetsDB


settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

_stop_event = threading.Event()
_worker_thread: Optional[threading.Thread] = None
_worker_lock = threading.Lock()
_worker_started_at: Optional[str] = None
_last_poll_at: Optional[str] = None
_last_error: Optional[str] = None
_processed_count = 0
_instagram_processed_count = 0
_youtube_processed_count = 0


def _worker_alive() -> bool:
    return bool(_worker_thread and _worker_thread.is_alive())


@app.route("/", methods=["GET"])
def index():
    ensure_worker_running()
    return "OK", 200


@app.route("/health", methods=["GET"])
def health():
    ensure_worker_running()
    return jsonify(
        {
            "ok": True,
            "worker_started": _worker_started_at is not None,
            "worker_alive": _worker_alive(),
            "worker_started_at": _worker_started_at,
            "last_poll_at": _last_poll_at,
            "last_error": _last_error,
            "processed_count": _processed_count,
            "instagram_processed_count": _instagram_processed_count,
            "youtube_processed_count": _youtube_processed_count,
            "polling_interval_seconds": settings.polling_interval_seconds,
        }
    ), 200


@app.route("/status", methods=["GET"])
def status():
    return health()


def process_instagram_rows(settings: Settings) -> int:
    sheets_db = SheetsDB(settings)
    analyzer = InfluencerAnalyzer(settings)
    triggered_rows = sheets_db.get_triggered_rows()
    processed = 0

    if triggered_rows:
        logger.info("Detected %s Instagram triggered row(s).", len(triggered_rows))

    for row in triggered_rows:
        if _stop_event.is_set():
            break

        logger.info("Processing Instagram row %s: %s", row.row_number, row.url)
        try:
            sheets_db.mark_running(row.row_number)
            result = analyzer.analyze(row.url)
            sheets_db.write_success(row.row_number, result)
            processed += 1
            logger.info("Instagram row %s completed successfully.", row.row_number)
        except Exception as row_exc:
            logger.exception("Instagram row %s failed: %s", row.row_number, row_exc)
            sheets_db.write_failure(row.row_number, str(row_exc))
        finally:
            sheets_db.clear_trigger(row.row_number)

    return processed


def process_youtube_rows(settings: Settings) -> int:
    youtube_sheets_db = YouTubeSheetsDB(settings)
    youtube_analyzer = YouTubeInfluencerAnalyzer(settings)
    triggered_rows = youtube_sheets_db.get_triggered_rows()
    processed = 0

    if triggered_rows:
        logger.info("Detected %s YouTube triggered row(s).", len(triggered_rows))

    for row in triggered_rows:
        if _stop_event.is_set():
            break

        logger.info("Processing YouTube row %s: %s", row.row_number, row.channel_url)
        try:
            youtube_sheets_db.mark_running(row.row_number)
            result = youtube_analyzer.analyze(row.channel_url)
            youtube_sheets_db.write_success(row.row_number, result)
            processed += 1
            logger.info("YouTube row %s completed successfully.", row.row_number)
        except Exception as row_exc:
            logger.exception("YouTube row %s failed: %s", row.row_number, row_exc)
            youtube_sheets_db.write_failure(row.row_number, str(row_exc))
        finally:
            youtube_sheets_db.clear_trigger(row.row_number)

    return processed


def polling_loop(settings: Settings) -> None:
    global _last_poll_at, _last_error, _processed_count, _instagram_processed_count, _youtube_processed_count

    logger.info("Background polling loop is starting. Interval: %s seconds", settings.polling_interval_seconds)

    while not _stop_event.is_set():
        try:
            _last_poll_at = datetime.now(timezone.utc).isoformat()
            validate_required_settings(settings)

            instagram_count = process_instagram_rows(settings)
            youtube_count = process_youtube_rows(settings)

            _instagram_processed_count += instagram_count
            _youtube_processed_count += youtube_count
            _processed_count += instagram_count + youtube_count
            _last_error = None
        except Exception as loop_exc:
            _last_error = str(loop_exc)
            logger.exception("Polling loop error: %s", loop_exc)

        _stop_event.wait(settings.polling_interval_seconds)

    logger.info("Background polling loop stopped.")


def ensure_worker_running() -> None:
    global _worker_thread, _worker_started_at

    with _worker_lock:
        if _worker_thread and _worker_thread.is_alive():
            return

        _stop_event.clear()
        _worker_thread = threading.Thread(
            target=polling_loop,
            args=(settings,),
            name="sheet-polling-worker",
            daemon=False,
        )
        _worker_thread.start()
        _worker_started_at = datetime.now(timezone.utc).isoformat()
        logger.info("Background worker thread started.")


def shutdown_handler(signum, frame) -> None:
    logger.info("Received shutdown signal: %s", signum)
    _stop_event.set()
    if _worker_thread and _worker_thread.is_alive():
        _worker_thread.join(timeout=10)


signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)

ensure_worker_running()


if __name__ == "__main__":
    port = int(os.getenv("PORT", settings.flask_port))
    app.run(host=settings.flask_host, port=port, threaded=True)
