import logging
import re
from typing import Any, Dict, List, Tuple

from google import genai

from config import Settings
from youtube_scraper import YouTubeScraper


logger = logging.getLogger(__name__)


CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "뷰티": ["뷰티", "메이크업", "화장", "스킨케어", "코スメ틱", "틴트", "쿠션", "피부", "beauty", "makeup", "cosmetic"],
    "패션": ["패션", "룩북", "코디", "옷", "가방", "신발", "데일리룩", "스타일", "fashion", "lookbook", "outfit"],
    "라이프스타일": ["브이로그", "일상", "라이프", "살림", "루틴", "집", "인테리어", "vlog", "routine", "lifestyle"],
    "육아": ["육아", "아이", "아기", "맘", "엄마", "임신", "출산", "키즈", "parenting", "baby", "kids"],
    "푸드": ["푸드", "먹방", "맛집", "요리", "레시피", "카페", "디저트", "음식", "food", "recipe", "mukbang"],
    "여행": ["여행", "숙소", "호텔", "항공", "해외", "국내여행", "트립", "travel", "trip", "hotel"],
    "테크": ["테크", "전자기기", "스마트폰", "노트북", "카메라", "리뷰", "가전", "tech", "gadget", "camera"],
    "운동": ["운동", "헬스", "필라테스", "요가", "다이어트", "러닝", "피트니스", "fitness", "workout", "health"],
    "교육": ["교육", "공부", "강의", "입시", "영어", "자기계발", "책", "education", "study", "lecture"],
    "엔터테인먼트": ["예능", "챌린지", "개그", "밈", "댄스", "음악", "엔터", "funny", "challenge", "music"],
}


class YouTubeInfluencerAnalyzer:
    """YouTube influencer analysis orchestrator for Sheet2."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.scraper = YouTubeScraper(settings)
        self.client = genai.Client(api_key=settings.gemini_api_key)

    def analyze(self, channel_url: str) -> Dict[str, Any]:
        scraped = self.scraper.analyze_channel(channel_url)
        categories = self._infer_categories(scraped.get("text_corpus", ""))
        grade = self._calculate_grade(scraped)
        ai_comment = self._generate_ai_comment(scraped, categories, grade)

        result = dict(scraped)
        result["category"] = ", ".join(categories)
        result["grade"] = grade
        result["ai_comment"] = ai_comment
        return result

    def _infer_categories(self, text: str) -> List[str]:
        normalized = text.lower()
        scores: List[Tuple[str, int]] = []

        for category, keywords in CATEGORY_KEYWORDS.items():
            score = 0
            for keyword in keywords:
                score += len(re.findall(re.escape(keyword.lower()), normalized))
            if score > 0:
                scores.append((category, score))

        scores.sort(key=lambda item: item[1], reverse=True)
        if not scores:
            return ["기타"]
        return [category for category, _ in scores[:2]]

    def _calculate_grade(self, data: Dict[str, Any]) -> str:
        subscribers = int(data.get("subscribers", 0) or 0)
        avg_shorts_views = int(data.get("avg_shorts_views", 0) or 0)
        avg_longform_views = int(data.get("avg_longform_views", 0) or 0)
        shorts_count = int(data.get("shorts_count", 0) or 0)
        longform_count = int(data.get("longform_count", 0) or 0)
        avg_comments = float(data.get("avg_comments", 0) or 0)

        primary_avg_views = self._weighted_average_views(
            avg_shorts_views=avg_shorts_views,
            avg_longform_views=avg_longform_views,
            shorts_count=shorts_count,
            longform_count=longform_count,
        )

        view_rate = (primary_avg_views / subscribers) if subscribers > 0 else 0
        comment_rate = (avg_comments / primary_avg_views) if primary_avg_views > 0 else 0

        score = 0
        if subscribers >= 100000:
            score += 20
        elif subscribers >= 30000:
            score += 16
        elif subscribers >= 10000:
            score += 12
        elif subscribers >= 3000:
            score += 8
        else:
            score += 4

        if view_rate >= 0.50:
            score += 35
        elif view_rate >= 0.25:
            score += 28
        elif view_rate >= 0.12:
            score += 20
        elif view_rate >= 0.05:
            score += 12
        else:
            score += 5

        if comment_rate >= 0.003:
            score += 20
        elif comment_rate >= 0.0015:
            score += 15
        elif comment_rate >= 0.0007:
            score += 10
        else:
            score += 4

        if shorts_count > 0 and longform_count > 0:
            score += 15
        elif shorts_count > 0 or longform_count > 0:
            score += 8

        if primary_avg_views >= 100000:
            score += 10
        elif primary_avg_views >= 30000:
            score += 8
        elif primary_avg_views >= 10000:
            score += 6
        elif primary_avg_views >= 3000:
            score += 4

        if score >= 85:
            return "S"
        if score >= 72:
            return "A"
        if score >= 58:
            return "B"
        if score >= 42:
            return "C"
        return "D"

    @staticmethod
    def _weighted_average_views(avg_shorts_views: int, avg_longform_views: int, shorts_count: int, longform_count: int) -> int:
        total_count = shorts_count + longform_count
        if total_count <= 0:
            return 0
        return round(((avg_shorts_views * shorts_count) + (avg_longform_views * longform_count)) / total_count)

    def _generate_ai_comment(self, data: Dict[str, Any], categories: List[str], grade: str) -> str:
        category_text = ", ".join(categories)
        prompt = f"""
당신은 광고대행사에서 유튜버 협업 후보를 평가하는 실무자입니다.
아래 지표만 근거로 한국어 코멘트를 최대 2문장으로 작성하세요.

규칙:
- 반드시 카테고리명을 포함하세요.
- 짧고 실무적으로 작성하세요.
- '~보입니다', '~필요합니다', '~같습니다' 같은 애매한 표현을 쓰지 마세요.
- 브랜드 협업 적합도, 광고성 계정 여부, 공구 적합도 중 최소 2가지를 반영하세요.
- 과장된 표현이나 확정 불가능한 주장은 금지합니다.

채널명: {data.get('channel_title', '')}
카테고리: {category_text}
구독자: {data.get('subscribers', 0)}
평균 Shorts 조회수: {data.get('avg_shorts_views', 0)}
평균 Longform 조회수: {data.get('avg_longform_views', 0)}
Shorts 수: {data.get('shorts_count', 0)}
Longform 수: {data.get('longform_count', 0)}
평균 댓글: {data.get('avg_comments', 0)}
Engagement Rate: {data.get('engagement_rate', '0.00%')}
Grade: {grade}
""".strip()

        try:
            response = self.client.models.generate_content(
                model=self.settings.gemini_model,
                contents=prompt,
            )
            text = (getattr(response, "text", "") or "").strip()
            return self._clean_comment(text, category_text, data, grade)
        except Exception as exc:
            logger.exception("YouTube Gemini comment generation failed: %s", exc)
            return self._fallback_comment(category_text, data, grade)

    def _clean_comment(self, text: str, category_text: str, data: Dict[str, Any], grade: str) -> str:
        if not text:
            return self._fallback_comment(category_text, data, grade)

        text = text.replace("보입니다", "입니다")
        text = text.replace("필요합니다", "권장됩니다")
        text = text.replace("같습니다", "입니다")
        text = " ".join(text.split())

        sentences = re.split(r"(?<=[.!?。])\s+", text)
        cleaned = " ".join(sentence.strip() for sentence in sentences if sentence.strip()[:2])
        if len(sentences) > 2:
            cleaned = " ".join(sentences[:2]).strip()

        if category_text not in cleaned:
            cleaned = f"{category_text} 카테고리 채널. {cleaned}"

        return cleaned[:500]

    def _fallback_comment(self, category_text: str, data: Dict[str, Any], grade: str) -> str:
        avg_shorts_views = int(data.get("avg_shorts_views", 0) or 0)
        avg_longform_views = int(data.get("avg_longform_views", 0) or 0)
        if avg_longform_views >= avg_shorts_views:
            return f"{category_text} 카테고리의 롱폼 반응 중심 채널이며, 브랜드 메시지 전달형 협업에 적합합니다. 등급 {grade} 기준으로 공구형 캠페인은 댓글 반응과 전환 조건을 함께 검토하세요."
        return f"{category_text} 카테고리의 Shorts 확산력이 강한 채널이며, 인지도 확보형 협업에 적합합니다. 등급 {grade} 기준으로 광고성 콘텐츠 비중과 최근 댓글 품질을 함께 확인하세요."
