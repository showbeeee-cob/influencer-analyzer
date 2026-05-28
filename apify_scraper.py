import logging
import statistics
from typing import Any, Dict, Iterable, List

from apify_client import ApifyClient

from config import Settings


logger = logging.getLogger(__name__)


def _first_present(data: Dict[str, Any], keys: Iterable[str], default: Any = None) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return default


def _to_number(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return default


class ApifyInstagramScraper:
    """Runs an Apify Instagram scraper actor and normalizes returned data."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = ApifyClient(settings.apify_token)

    def scrape_profile(self, instagram_url: str) -> Dict[str, Any]:
        actor_input = self._build_actor_input(instagram_url)
        logger.info("Starting Apify actor '%s' for URL: %s", self.settings.apify_actor_id, instagram_url)

        run = self.client.actor(self.settings.apify_actor_id).call(
            run_input=actor_input,
            timeout_secs=self.settings.apify_timeout_seconds,
        )

        if not run or not run.get("defaultDatasetId"):
            raise RuntimeError("Apify actor finished without a default dataset.")

        dataset_id = run["defaultDatasetId"]
        dataset_items = self.client.dataset(dataset_id).list_items().items

        if not dataset_items:
            raise RuntimeError("Apify returned an empty dataset. Check the Instagram URL or actor settings.")

        normalized = self._normalize_dataset(dataset_items)
        normalized["source_url"] = instagram_url
        return normalized

    def _build_actor_input(self, instagram_url: str) -> Dict[str, Any]:
        return {
            "directUrls": [instagram_url],
            "resultsType": "posts",
            "resultsLimit": self.settings.apify_results_limit,
            "addParentData": True,
        }

    def _normalize_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        flattened_items = self._flatten_items(items)
        first_item = flattened_items[0]

        followers = self._extract_followers(flattened_items)
        like_values = []
        comment_values = []
        view_values = []
        share_values = []

        for item in flattened_items:
            like_values.append(_to_number(_first_present(item, ["likesCount", "likeCount", "likes", "likes_count"])))
            comment_values.append(_to_number(_first_present(item, ["commentsCount", "commentCount", "comments", "comments_count"])))

            view_value = _to_number(
                _first_present(
                    item,
                    [
                        "videoViewCount",
                        "videoPlayCount",
                        "videoViews",
                        "viewsCount",
                        "viewCount",
                        "views",
                        "plays",
                    ],
                )
            )
            if view_value > 0:
                view_values.append(view_value)

            share_value = _to_number(_first_present(item, ["sharesCount", "shareCount", "shares", "shares_count"]))
            if share_value > 0:
                share_values.append(share_value)

        avg_likes = round(statistics.mean(like_values), 2) if like_values else 0
        avg_comments = round(statistics.mean(comment_values), 2) if comment_values else 0
        avg_views = round(statistics.mean(view_values), 2) if view_values else 0
        avg_shares = round(statistics.mean(share_values), 2) if share_values else 0

        engagement_rate_number = ((avg_likes + avg_comments) / followers * 100) if followers > 0 else 0

        return {
            "followers": int(followers),
            "avg_likes": avg_likes,
            "avg_comments": avg_comments,
            "avg_views": avg_views,
            "avg_shares": avg_shares,
            "engagement_rate_number": engagement_rate_number,
            "engagement_rate": f"{engagement_rate_number:.2f}%",
            "raw_item_count": len(flattened_items),
            "username": self._extract_username(first_item),
            "full_name": self._extract_first_text(flattened_items, ["fullName", "full_name", "ownerFullName", "name"]),
            "biography": self._extract_first_text(flattened_items, ["biography", "bio", "ownerBiography", "profileBio"]),
            "profile_text": self._extract_profile_text(flattened_items),
            "sample_captions": self._extract_captions(flattened_items),
        }

    def _flatten_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        flattened: List[Dict[str, Any]] = []

        for item in items:
            flattened.append(item)

            for nested_key in ["latestPosts", "posts", "items", "edges"]:
                nested_items = item.get(nested_key)
                if isinstance(nested_items, list):
                    for nested_item in nested_items:
                        if isinstance(nested_item, dict):
                            merged = {**item, **nested_item}
                            flattened.append(merged)

        return flattened

    def _extract_followers(self, items: List[Dict[str, Any]]) -> int:
        follower_keys = [
            "followersCount",
            "followers",
            "followers_count",
            "ownerFollowersCount",
            "ownerFollowers",
            "profileFollowers",
        ]

        for item in items:
            value = _first_present(item, follower_keys)
            number = _to_number(value)
            if number > 0:
                return int(number)

            owner = item.get("owner")
            if isinstance(owner, dict):
                owner_value = _first_present(owner, follower_keys)
                owner_number = _to_number(owner_value)
                if owner_number > 0:
                    return int(owner_number)

        return 0

    def _extract_username(self, item: Dict[str, Any]) -> str:
        username = _first_present(item, ["username", "ownerUsername", "handle", "profileName"], "")
        if username:
            return str(username)

        owner = item.get("owner")
        if isinstance(owner, dict):
            owner_username = _first_present(owner, ["username", "ownerUsername", "handle"], "")
            if owner_username:
                return str(owner_username)

        return ""

    def _extract_first_text(self, items: List[Dict[str, Any]], keys: List[str]) -> str:
        for item in items:
            value = _first_present(item, keys, "")
            if value:
                return str(value)

            owner = item.get("owner")
            if isinstance(owner, dict):
                owner_value = _first_present(owner, keys, "")
                if owner_value:
                    return str(owner_value)
        return ""

    def _extract_profile_text(self, items: List[Dict[str, Any]]) -> str:
        parts = []
        for key_group in [
            ["username", "ownerUsername", "handle", "profileName"],
            ["fullName", "full_name", "ownerFullName", "name"],
            ["biography", "bio", "ownerBiography", "profileBio"],
        ]:
            value = self._extract_first_text(items, key_group)
            if value:
                parts.append(value)
        return " ".join(parts)

    def _extract_captions(self, items: List[Dict[str, Any]]) -> List[str]:
        captions: List[str] = []
        caption_keys = ["caption", "text", "title", "description", "alt", "hashtags"]

        for item in items:
            value = _first_present(item, caption_keys, "")
            if isinstance(value, list):
                value = " ".join(str(part) for part in value)
            if value:
                captions.append(str(value)[:500])
            if len(captions) >= 12:
                break

        return captions
