import logging
from typing import Any, Dict

from google import genai

from config import Settings


logger = logging.getLogger(__name__)


class GeminiCommentGenerator:
    """Creates concise influencer evaluation comments with Gemini."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = genai.Client(api_key=settings.gemini_api_key)

    def generate_comment(self, analysis: Dict[str, Any]) -> str:
        prompt = self._build_prompt(analysis)

        try:
            response = self.client.models.generate_content(
                model=self.settings.gemini_model,
                contents=prompt,
            )
            text = getattr(response, "text", "") or ""
            text = text.strip()
            if not text:
                return self._fallback_comment(analysis)
            return text[:900]
        except Exception as exc:
            logger.exception("Gemini comment generation failed: %s", exc)
            return self._fallback_comment(analysis)

    def _build_prompt(self, analysis: Dict[str, Any]) -> str:
        return f"""
당신은 브랜드 마케팅 담당자를 돕는 인스타그램 인플루언서 분석가입니다.
아래 지표만 근거로, 한국어로 3~5문장의 짧고 실무적인 평가 코멘트를 작성하세요.
과장하지 말고, 협업 적합성, 강점, 주의점, 다음 확인 포인트를 균형 있게 포함하세요.

- Username: {analysis.get('username', '')}
- Followers: {analysis.get('followers', 0)}
- Average Likes: {analysis.get('avg_likes', 0)}
- Average Comments: {analysis.get('avg_comments', 0)}
- Average Views: {analysis.get('avg_views', 0)}
- Engagement Rate: {analysis.get('engagement_rate', '0.00%')}
- Grade: {analysis.get('grade', 'N/A')}
- Raw Item Count: {analysis.get('raw_item_count', 0)}
""".strip()

    def _fallback_comment(self, analysis: Dict[str, Any]) -> str:
        grade = analysis.get("grade", "N/A")
        er = analysis.get("engagement_rate", "0.00%")
        followers = analysis.get("followers", 0)
        return (
            f"Gemini 코멘트 생성에 실패하여 기본 평가를 입력합니다. "
            f"해당 계정은 팔로워 {followers:,}명, 참여율 {er}, 등급 {grade}로 계산되었습니다. "
            "협업 전에는 최근 콘텐츠 품질, 댓글의 실제 반응, 브랜드 적합성을 추가로 확인하는 것이 좋습니다."
        )
