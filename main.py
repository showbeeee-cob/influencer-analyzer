import os
import time
import threading

from flask import Flask

# -----------------------------
# Render 포트 체크 통과용 서버
# -----------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "OK"


def run_fake_server():

    port = int(os.environ.get("PORT", 8080))

    print(f"🌐 Fake server started on port {port}")

    app.run(
        host="0.0.0.0",
        port=port
    )


threading.Thread(
    target=run_fake_server,
    daemon=True
).start()

# -----------------------------
# 모듈 import
# -----------------------------
from apify_scraper import (
    scrape_instagram_profile,
    extract_influencer_data
)

from analyzer import (
    calculate_trimmed_er,
    grade_influencer
)

from ai_generator import analyze_influencer_data

from sheets_db import (
    get_sheet,
    get_pending_rows,
    update_row
)

# -----------------------------
# 설정
# -----------------------------
POLL_INTERVAL_SECONDS = 30

# -----------------------------
# 인플루언서 처리
# -----------------------------
def process_influencer(url):

    print("--------------------------------------------------")
    print(f"🚀 Processing Start: {url}")
    print("--------------------------------------------------")

    raw_data = scrape_instagram_profile(url)

    print("📦 RAW DATA:")
    print(raw_data)

    if not raw_data:

        print("❌ Apify 수집 실패")

        return None

    extracted = extract_influencer_data(raw_data)

    print("📦 EXTRACTED DATA:")
    print(extracted)

    if not extracted:

        print("❌ 데이터 추출 실패")

        return None

    followers = extracted.get("followers", 0)

    profile_image = extracted.get(
        "profile_image",
        ""
    )

    posts = extracted.get(
        "posts",
        []
    )

    print(f"👥 Followers: {followers}")
    print(f"🖼️ Profile Image: {profile_image}")
    print(f"📝 Posts Count: {len(posts)}")

    avg_likes = (
        sum(
            p.get("likesCount", 0)
            for p in posts
        ) / len(posts)
    ) if posts else 0

    avg_comments = (
        sum(
            p.get("commentsCount", 0)
            for p in posts
        ) / len(posts)
    ) if posts else 0

    avg_views = (
        sum(
            p.get("videoViewCount", 0)
            for p in posts
        ) / len(posts)
    ) if posts else 0

    print(f"❤️ Avg Likes: {avg_likes}")
    print(f"💬 Avg Comments: {avg_comments}")
    print(f"🎥 Avg Views: {avg_views}")

    er = calculate_trimmed_er(
        posts,
        followers,
        trim_percent=0.1
    )

    grade = grade_influencer(er)

    print(f"📊 ER: {er:.2f}%")
    print(f"🏆 Grade: {grade}")

    try:

        print("🤖 AI 분석 시작")

        ai_comments = analyze_influencer_data({
            "er": er,
            "followers": followers,
            "grade": grade
        })

        print("✅ AI 분석 성공")
        print(ai_comments)

    except Exception as e:

        print(f"⚠️ AI 분석 오류: {e}")

        ai_comments = "AI 분석 일시 오류"

    results = {

        "followers": followers,

        "avg_likes": avg_likes,

        "avg_comments": avg_comments,

        "avg_views": avg_views,

        "er": er,

        "grade": grade,

        "profile_image": profile_image,

        "ai_comments": ai_comments
    }

    print("✅ FINAL RESULTS:")
    print(results)

    return results

# -----------------------------
# Polling Loop
# -----------------------------
def run_polling():

    print("🚀 Polling started...")

    while True:

        try:

            print("🔄 Checking Google Sheets...")

            sheet = get_sheet()

            if not sheet:

                print("❌ Google Sheets 연결 실패")

                time.sleep(POLL_INTERVAL_SECONDS)

                continue

            pending_rows = get_pending_rows(sheet)

            print(f"📋 Pending Rows: {pending_rows}")

            if not pending_rows:

                print("⏳ 대기 중...")

            for row in pending_rows:

                row_idx = row["row_idx"]

                url = row["url"]

                print("--------------------------------------------------")
                print(f"📌 Row {row_idx} 처리 시작")
                print("--------------------------------------------------")

                sheet.update(
                    values=[["PROCESSING"]],
                    range_name=f"J{row_idx}"
                )

                results = process_influencer(url)

                if results:

                    print("✅ update_row 실행")

                    update_row(
                        sheet,
                        row_idx,
                        results
                    )

                    print(f"✅ Row {row_idx} 완료")

                else:

                    print("❌ results가 None 입니다")

                    sheet.update(
                        values=[["FAILED"]],
                        range_name=f"J{row_idx}"
                    )

                    print(f"❌ Row {row_idx} 실패")

        except Exception as e:

            print("🔥🔥🔥 루프 전체 오류 🔥🔥🔥")
            print(e)

        print(f"😴 Sleeping {POLL_INTERVAL_SECONDS} seconds...")

        time.sleep(POLL_INTERVAL_SECONDS)

# -----------------------------
# 실행
# -----------------------------
if __name__ == "__main__":

    run_polling()