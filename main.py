import os
import time
import threading

from flask import Flask

from sheets_db import get_sheet
from apify_scraper import scrape_instagram_data
from analyzer import grade_influencer
from ai_generator import generate_ai_comment


# ==================================================
# Flask 서버 (Render 포트 체크용)
# ==================================================

app = Flask(__name__)

@app.route("/")
def home():
    return "OK"


def run_server():
    port = int(os.environ.get("PORT", 10000))

    print(f"🌐 Fake server started on port {port}")

    app.run(
        host="0.0.0.0",
        port=port
    )


threading.Thread(
    target=run_server,
    daemon=True
).start()

time.sleep(2)


# ==================================================
# 시트 업데이트 함수
# ==================================================

def update_row(sheet, row_idx, results):

    values = [[
        results.get("followers", ""),
        results.get("avg_likes", ""),
        results.get("avg_comments", ""),
        results.get("avg_views", ""),
        results.get("er", ""),
        results.get("grade", ""),
        results.get("ai_comment", ""),
        False,
        "DONE",
        results.get("image_url", "")
    ]]

    sheet.update(
        range_name=f"B{row_idx}:K{row_idx}",
        values=values
    )


# ==================================================
# 메인 폴링 함수
# ==================================================

def run_polling():

    print("🚀 Polling started...")

    while True:

        try:

            sheet = get_sheet()
            rows = sheet.get_all_values()

            for idx, row in enumerate(rows[1:], start=2):

                trigger = row[8]

                if str(trigger).upper() != "TRUE":
                    continue

                url = row[0]

                print(f"🔥 Processing Row {idx}")
                print(f"🔗 URL: {url}")

                try:

                    data = scrape_instagram_data(url)

                    grade = grade_influencer(
                        data["followers"],
                        data["avg_likes"],
                        data["avg_comments"]
                    )

                    ai_comment = generate_ai_comment(
                        grade,
                        data["followers"],
                        data["er"]
                    )

                    results = {
                        "followers": data["followers"],
                        "avg_likes": data["avg_likes"],
                        "avg_comments": data["avg_comments"],
                        "avg_views": data["avg_views"],
                        "er": data["er"],
                        "grade": grade,
                        "ai_comment": ai_comment,
                        "image_url": data["image_url"]
                    }

                    update_row(
                        sheet,
                        idx,
                        results
                    )

                    print(f"✅ Row {idx} 완료")

                except Exception as e:

                    print(f"❌ Row {idx} 처리 오류")
                    print(e)

                    sheet.update(
                        range_name=f"J{idx}",
                        values=[["FAILED"]]
                    )

            print("😴 sleeping...")
            time.sleep(10)

        except Exception as e:

            print("🔥 루프 전체 오류")
            print(e)

            time.sleep(10)


# ==================================================
# 실행
# ==================================================

if __name__ == "__main__":
    run_polling()