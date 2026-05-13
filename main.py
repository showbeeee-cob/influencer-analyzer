import os
import time

from sheets_db import (
    get_sheet,
    get_pending_rows,
    update_row
)

from apify_scraper import (
    scrape_instagram_profile,
    extract_influencer_data
)

from analyzer import grade_influencer

POLL_INTERVAL_SECONDS = 10


def run_polling():

    print("🚀 Polling started...")

    while True:

        try:

            sheet = get_sheet()

            if not sheet:

                print("❌ sheet 연결 실패")

                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            pending_rows = get_pending_rows(sheet)

            print(f"📄 pending rows: {pending_rows}")

            if not pending_rows:

                print("😴 처리할 데이터 없음")

            for row in pending_rows:

                row_idx = row["row_idx"]
                url = row["url"]

                print("===================================")
                print(f"🚀 Row {row_idx} 처리 시작")
                print(f"🔗 URL: {url}")
                print("===================================")

                try:

                    raw_data = scrape_instagram_profile(url)

                    print("📦 raw_data:")
                    print(raw_data)

                    extracted = extract_influencer_data(raw_data)

                    print("📊 extracted:")
                    print(extracted)

                    if not extracted:

                        print("❌ extracted 실패")

                        sheet.update(
                            range_name=f"J{row_idx}",
                            values=[["FAILED"]]
                        )

                        continue

                    results = analyze_influencer(extracted)

                    print("🧠 analyze results:")
                    print(results)

                    if not results:

                        print("❌ results 실패")

                        sheet.update(
                            range_name=f"J{row_idx}",
                            values=[["FAILED"]]
                        )

                        continue

                    update_row(
                        sheet,
                        row_idx,
                        results
                    )

                    print(f"✅ Row {row_idx} 완료")

                except Exception as e:

                    print(f"🔥 Row {row_idx} 처리 오류")
                    print(e)

                    sheet.update(
                        range_name=f"J{row_idx}",
                        values=[["FAILED"]]
                    )

            print(f"😴 Sleeping {POLL_INTERVAL_SECONDS} seconds...")
            time.sleep(POLL_INTERVAL_SECONDS)

        except Exception as e:

            print("🔥 루프 전체 오류")
            print(e)

            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":

    run_polling()