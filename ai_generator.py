import google.generativeai as genai
from config import GEMINI_API_KEY


def analyze_influencer_data(data):

    if not GEMINI_API_KEY:
        print("❌ Gemini API 키 없음")
        return "Gemini API Key Missing"

    try:

        genai.configure(
            api_key=GEMINI_API_KEY
        )

        model = genai.GenerativeModel(
            "gemini-1.5-flash"
        )

        prompt = f"""
아래 인플루언서 데이터를 분석해줘.

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

        print(f"⚠️ Gemini 오류: {e}")

        return "AI 분석 일시 오류"