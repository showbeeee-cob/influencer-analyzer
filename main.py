import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import time

# --- Render 포트 체크 통과용 가짜 서버 ---
def run_fake_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), BaseHTTPRequestHandler)
    print(f"Fake server started on port {port}")
    server.serve_forever()

threading.Thread(target=run_fake_server, daemon=True).start()

# --- 도구 가져오기 ---
from apify_scraper import scrape_instagram_profile, extract_influencer_data
from analyzer import calculate_trimmed_er, grade_influencer
from ai_generator import analyze_influencer_data
from sheets_db import get_sheet, get_pending_rows, update_row

POLL_INTERVAL_SECONDS = 30

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

    # 3. 지표 계산
    avg_likes = (sum(p.get("likesCount", 0) for p in posts) / len(posts)) if posts else 0
    avg_comments = (sum(p.get("commentsCount", 0) for p in posts) / len(posts)) if posts else 0
    avg_views = (sum(p.get("videoViewCount", 0) for p in posts) / len(posts)) if posts else 0
    er = calculate_trimmed_er(posts, followers, trim_percent=0.1)
    grade = grade_influencer(er)

    # 4. AI 분석 (에러가 나도 전체가 멈추지 않게 처리)
    try:
        ai_comments = analyze_influencer_data({
            "er": er,
            "followers": followers,
            "grade": grade
        })
    except Exception as e:
        print(f"⚠️ AI 분석 중 오류 발생: {e}")
        ai_comments = "AI 분석 일시 오류"

    # 시트 업데이트를 위한 딕셔너리 (Key 이름을 sheets_db.py와 맞춤)
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

def run_polling():
    print("🚀 Polling started...")
    while True:
        try:
            sheet = get_sheet()
            if not sheet:
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            pending_rows = get_pending_rows(sheet)
            for row in pending_rows:
                row_idx = row["row_idx"]
                url = row["url"]

                # 상태 변경: PROCESSING
                sheet.update(values=[["PROCESSING"]], range_name=f"J{row_idx}")

                results = process_influencer(url)

                if results:
                    update_row(sheet, row_idx, results)
                    print(f"✅ Row {row_idx} 업데이트 완료!")
                else:
                    sheet.update(values=[["FAILED"]], range_name=f"J{row_idx}")

        except Exception as e:
            print(f"🔥 루프 에러: {e}")

        time.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    run_polling()