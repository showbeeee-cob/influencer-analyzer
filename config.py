import os
from dotenv import load_dotenv

load_dotenv()

# 환경변수 이름이 조금 달라도 모두 호환되도록 방어막 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") 
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON") or os.getenv("GOOGLE_SHEETS_CREDENTIALS")
GOOGLE_SHEET_URL = os.getenv("GOOGLE_SHEET_URL_OR_NAME") or os.getenv("GOOGLE_SHEET_URL")