import os
import time
import threading

from flask import Flask

from sheets_db import (
    get_sheet,
    find_triggered_rows,
    update_row
)

from apify_scraper import (
    scrape_instagram_profile,
    extract_influencer_data
)

from analyzer import grade_influencer

from ai_generator import generate_ai_comment


# ==================================================
# Flask Server (Render 생존용)
# ==================================================

app = Flask(__name__)

@app.route("/")
def home():
    return "OK"


def run_server():

    port = int(os.environ.get("PORT", 10000))

    print(f"🌐 Server running on {port}")

    app.run(
        host="0.0.0.0",
        port=port
    )


# ==================================================
# 설정
# ==================================================

POLL_INTERVAL_SECONDS = 15


# ==================================================
# 메인 로직
# ==================================================

def process_row(sheet, row_idx, url):

    print("==================================================")
    print(f"🚀 Row {row_idx} 처리 시작")
    print(f"🔗 URL: {url}")
    print("==================================================")

    raw_data = scrape_instagram_profile(url)

    if not raw_data:

        print("❌ raw_data 없음")

        update_row(
            sheet,
            row_idx,
            {
                "status": "FAILED"
            }
        )

        return

    influencer_data = extract_influencer_data(raw_data)

    if not influencer_data:

        print("❌ influencer_data 없음")

        update_row(
            sheet,
            row_idx,
            {
                "status": "FAILED"
            }
        )

        return

    analyzed = grade_influencer(
        influencer_data
    )

    ai_comment = generate_ai_comment(
        analyzed
    )

    results = {
        "followers":
            analyzed.get("followers", 0),

        "avg_likes":
            analyzed.get("avg_likes", 0),

        "avg_comments":
            analyzed.get("avg_comments", 0),

        "avg_views":
            analyzed.get("avg_views", 0),

        "er":
            analyzed.get("er", 0),

        "grade":
            analyzed.get("grade", "C"),

        "ai_comment":
            ai_comment,

        "profile_image":
            influencer_data.get(
                "profile_image",
                ""
            ),

        "status":
            "DONE"
    }

    update_row(
        sheet,
        row_idx,
        results
    )

    print(f"✅ Row {row_idx} 완료")


# ==================================================
# Polling Loop
# ==================================================

def run_polling():

    print("🚀 Polling started...")

    while True:

        try:

            print("🔍 checking rows...")

            sheet = get_sheet()

            rows = find_triggered_rows(sheet)

            print(f"📦 triggered rows: {len(rows)}")

            for row in rows:

                try:

                    row_idx = row["row_idx"]
                    url = row["url"]

                    process_row(
                        sheet,
                        row_idx,
                        url
                    )

                except Exception as e:

                    print("🔥 row 처리 오류")
                    print(e)

            print(f"😴 sleeping {POLL_INTERVAL_SECONDS}s")

            time.sleep(
                POLL_INTERVAL_SECONDS
            )

        except Exception as e:

            print("🔥 polling 전체 오류")
            print(e)

            time.sleep(
                POLL_INTERVAL_SECONDS
            )


# ==================================================
# 실행
# ==================================================

if __name__ == "__main__":

    threading.Thread(
        target=run_polling,
        daemon=True
    ).start()

    run_server()