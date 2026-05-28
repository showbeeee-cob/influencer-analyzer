import logging
from typing import Any, Dict, Iterable

from ai_generator import GeminiCommentGenerator
from apify_scraper import ApifyInstagramScraper
from config import Settings


logger = logging.getLogger(__name__)


CATEGORY_KEYWORDS = {
    "뷰티": [
        "뷰티", "beauty", "makeup", "메이크업", "화장", "스킨케어", "skincare", "피부", "코스메틱", "cosmetic", "립", "향수", "헤어",
    ],
    "패션": [
        "패션", "fashion", "ootd", "룩북", "코디", "스타일", "style", "의류", "옷", "데일리룩", "신발", "가방", "주얼리",
    ],
    "육아": [
        "육아", "맘", "엄마", "아기", "아이", "키즈", "baby", "kids", "parenting", "맘스타그램", "육아맘",
    ],
    "인테리어": [
        "인테리어", "interior", "홈", "집", "리빙", "living", "가구", "소품", "홈스타일링", "집꾸미기", "살림",
    ],
    "음식": [
        "음식", "맛집", "먹방", "요리", "레시피", "카페", "디저트", "food", "recipe", "restaurant", "cafe", "baking",
    ],
    "여행": [
        "여행", "travel", "trip", "호텔", "숙소", "항공", "vacation", "여행스타그램", "국내여행", "해외여행",
    ],
    "운동/건강": [
        "운동", "헬스", "피트니스", "필라테스", "요가", "다이어트", "건강", "fitness", "workout", "gym", "health",
    ],
    "반려동물": [
        "반려", "강아지", "고양이", "댕댕", "냥", "펫", "pet", "dog", "cat", "puppy",
    ],
    "IT/테크": [
        "테크", "tech", "it", "앱", "디지털", "가전", "전자", "아이폰", "갤럭시", "노트북", "ai", "software",
    ],
    "교육": [
        "교육", "공부", "강의", "클래스", "책", "독서", "study", "class", "lecture", "book", "영어", "학습",
    ],
    "엔터테인먼트": [
        "엔터", "배우", "가수", "댄스", "음악", "영화", "드라마", "공연", "artist", "music", "dance", "movie",
    ],
    "일상": [
        "일상", "daily", "데일리", "소통", "셀카", "셀피", "life", "lifestyle", "브이로그", "vlog",
    ],
}


class InfluencerAnalyzer:
    """Coordinates scraping, metric normalization, grading, tiering, and categorization."""

    def __init__(self, settings: Settings):
        self.scraper = ApifyInstagramScraper(settings)
        self.ai_generator = GeminiCommentGenerator(settings)

    def analyze(self, instagram_url: str) -> Dict[str, Any]:
        scraped = self.scraper.scrape_profile(instagram_url)
        scraped["grade"] = self.calculate_grade(scraped)
        scraped["tier"] = self.calculate_tier(scraped.get("followers", 0))
        scraped["category"] = self.classify_category(scraped)

        # The old AI comment is kept internally for compatibility, but it is no longer written to the sheet.
        try:
            scraped["ai_comment"] = self.ai_generator.generate_comment(scraped)
        except Exception as exc:
            logger.warning("AI comment generation skipped: %s", exc)
            scraped["ai_comment"] = ""

        return scraped

    @staticmethod
    def calculate_tier(followers_value: Any) -> str:
        followers = int(float(followers_value or 0))
        if followers >= 1_000_000:
            return "Mega"
        if followers >= 100_000:
            return "Macro"
        if followers >= 10_000:
            return "Micro"
        return "Nano"

    @staticmethod
    def _iter_category_text(metrics: Dict[str, Any]) -> Iterable[str]:
        keys = [
            "username",
            "full_name",
            "biography",
            "profile_text",
            "sample_captions",
        ]
        for key in keys:
            value = metrics.get(key)
            if isinstance(value, list):
                for item in value:
                    if item:
                        yield str(item)
            elif value:
                yield str(value)

    @classmethod
    def classify_category(cls, metrics: Dict[str, Any]) -> str:
        text = " ".join(cls._iter_category_text(metrics)).lower()
        if not text.strip():
            return "기타"

        scores = {}
        for category, keywords in CATEGORY_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword.lower() in text)
            if score > 0:
                scores[category] = score

        if not scores:
            return "일상"

        return sorted(scores.items(), key=lambda item: (-item[1], item[0]))[0][0]

    @staticmethod
    def calculate_grade(metrics: Dict[str, Any]) -> str:
        followers = int(metrics.get("followers") or 0)
        er = float(metrics.get("engagement_rate_number") or 0)
        avg_views = float(metrics.get("avg_views") or 0)
        avg_likes = float(metrics.get("avg_likes") or 0)
        avg_comments = float(metrics.get("avg_comments") or 0)

        score = 0

        if followers >= 1_000_000:
            score += 30
        elif followers >= 300_000:
            score += 26
        elif followers >= 100_000:
            score += 22
        elif followers >= 50_000:
            score += 18
        elif followers >= 10_000:
            score += 14
        elif followers >= 1_000:
            score += 8
        else:
            score += 3

        if er >= 6:
            score += 40
        elif er >= 4:
            score += 34
        elif er >= 2.5:
            score += 28
        elif er >= 1.5:
            score += 20
        elif er >= 0.8:
            score += 12
        else:
            score += 5

        if avg_views > 0 and followers > 0:
            view_rate = avg_views / followers * 100
            if view_rate >= 25:
                score += 15
            elif view_rate >= 15:
                score += 12
            elif view_rate >= 8:
                score += 9
            elif view_rate >= 3:
                score += 5
            else:
                score += 2
        else:
            score += 5

        if avg_comments >= 100:
            score += 15
        elif avg_comments >= 30:
            score += 12
        elif avg_comments >= 10:
            score += 8
        elif avg_likes >= 100:
            score += 5
        else:
            score += 2

        if score >= 85:
            return "S"
        if score >= 70:
            return "A"
        if score >= 55:
            return "B"
        if score >= 40:
            return "C"
        return "D"
