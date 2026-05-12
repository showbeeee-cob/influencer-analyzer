import gspread
import json
from config import GOOGLE_CREDENTIALS_JSON, GOOGLE_SHEET_URL

def get_sheet():
    try:
        if not GOOGLE_CREDENTIALS_JSON:
            print("❌ 구글 시트 인증 정보(JSON)가 없습니다.")
            return None
        
        creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
        gc = gspread.service_account_from_dict(creds_dict)
        
        if not GOOGLE_SHEET_URL:
            print("❌ 구글 시트 URL 정보가 없습니다.")
            return None
            
        return gc.open_by_url(GOOGLE_SHEET_URL).get_worksheet(0)
    except Exception as e:
        print(f"❌ 시트 연결 실패: {e}")
        return None

def get_pending_rows(sheet):
    records = sheet.get_all_records()
    pending = []
    for i, row in enumerate(records):
        trigger_val = str(row.get("Trigger", "")).upper()
        status_val = str(row.get("Status", "")).upper()
        
        if trigger_val == "TRUE" and status_val not in ["DONE", "PROCESSING"]:
            pending.append({
                "row_idx": i + 2,
                "url": row.get("URL")
            })
    return pending

def update_row(sheet, row_idx, data):
    try:
        stats = [[
            data.get("followers", 0),
            round(data.get("avg_likes", 0), 1),
            round(data.get("avg_comments", 0), 1),
            round(data.get("avg_views", 0), 1),
            f"{round(data.get('er', 0), 2)}%",
            data.get("grade", "-")
        ]]
        sheet.update(range_name=f"B{row_idx}:G{row_idx}", values=stats)
        sheet.update(range_name=f"H{row_idx}", values=[[data.get("ai_comments", "")]])
        sheet.update(range_name=f"J{row_idx}", values=[["DONE"]])
        sheet.update(range_name=f"K{row_idx}", values=[[data.get("profile_image", "")]])
        sheet.update(range_name=f"I{row_idx}", values=[[False]])
        print(f"✅ {row_idx}번 행 데이터 시트 입력 완료!")
    except Exception as e:
        print(f"❌ 시트 업데이트 실패: {e}")