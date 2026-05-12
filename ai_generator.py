import google.generativeai as genai
from config import GEMINI_API_KEY


def analyze_influencer_data(data):

    if not GEMINI_API_KEY:

        print("❌ Gemini API 키가 없습니다.")

        return "Gemini API Key missing"

    try:

        genai.configure(
            api_key=GEMINI_API_KEY
        )

        model = genai.GenerativeModel(
            "gemini-1.5-flash"
        )

        prompt = f"""
아래 인플루언서 데이터를 분석해서
짧은 마케팅 관점 코멘트를 작성해줘.

데이터:
{data}

형식:
[한 줄 평] 내용
[성장 가능성] 내용
"""

        response = model.generate_content(
            prompt
        )

        return response.text

    except Exception as e:

        print(f"⚠️ AI 분석 실패: {e}")

        return "AI 분석 일시 오류 (수치는 정상 처리됨)"