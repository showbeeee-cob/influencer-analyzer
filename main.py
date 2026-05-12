import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import time

# -----------------------------
# Render 포트 체크 통과용 서버
# -----------------------------
def run_fake_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), BaseHTTPRequestHandler)
    print(f"Fake server started on port {port}")
    server.serve_forever()

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

    print(f"--- Processing: {url} ---")

    # 1. 데이터 수집
    raw_data = scrape_instagram_profile(url)

    if not raw_data:
        print("❌ Apify 수집 실패")
        return None

    # 2. 데이터 추출
    extracted = extract_influencer_data(raw_data)

    if not extracted:
        print("❌ 데이터 추출 실패")
        return None

    followers = extracted.get("followers", 0)
    profile_image = extracted.get("profile_image", "")
    posts = extracted.get("posts", [])

    # 3. 평균 계산
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

    # 4. ER 계산
    er = calculate_trimmed_er(
        posts,
        followers,
        trim_percent=0.1
    )

    # 5. 등급 계산
    grade = grade_influencer(er)

    print(f"✅ ER: {er:.2f}%")
    print(f"✅ Grade: {grade}")

    # 6. AI 분석
    try:

        ai_comments = analyze_influencer_data({
            "er": er,
            "followers": followers,
            "grade": grade
        })

    except Exception as e:

        print(f"⚠️ AI 분석 오류: {e}")

        ai_comments = "AI 분석 일시 오류"

    # 7. 결과 반환
    return {

        "followers": followers,

        "avg_likes": avg_likes,

        "avg_comments": avg_comments,

        "avg_views": avg_views,

        "er": er,

        "grade": grade,

        "profile_image": profile_image,

        "ai_comments": ai_comments
    }

# -----------------------------
# Polling Loop
# -----------------------------
def run_polling():

    print("🚀 Polling started...")

    while True:

        try:

            sheet = get_sheet()

            if not sheet:

                print("❌ Google Sheets 연결 실패")

                time.sleep(POLL_INTERVAL_SECONDS)

                continue

            pending_rows = get_pending_rows(sheet)

            if not pending_rows:

                print("⏳ 대기 중...")

            for row in pending_rows:

                row_idx = row["row_idx"]
                url = row["url"]

                print(f"📌 Row {row_idx} 처리 시작")

                # 상태 변경
                sheet.update(
                    values=[["PROCESSING"]],
                    range_name=f"J{row_idx}"
                )

                # 분석 실행
                results = process_influencer(url)

                if results:

                    update_row(
                        sheet,
                        row_idx,
                        results
                    )

                    print(f"✅ Row {row_idx} 완료")

                else:

                    sheet.update(
                        values=[["FAILED"]],
                        range_name=f"J{row_idx}"
                    )

                    print(f"❌ Row {row_idx} 실패")

        except Exception as e:

            print(f"🔥 루프 오류: {e}")

        time.sleep(POLL_INTERVAL_SECONDS)

# -----------------------------
# 실행
# -----------------------------
if __name__ == "__main__":
    run_polling()