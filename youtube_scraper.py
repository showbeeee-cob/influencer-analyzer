import logging
import re
import time
from statistics import mean
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

from config import Settings


logger = logging.getLogger(__name__)


class YouTubeScraper:
    """YouTube Data API based channel analyzer.

    This class uses a public API key, not OAuth. It supports /channel/UC..., /@handle,
    and general channel-like URLs by resolving them into a channel ID first.
    """

    BASE_URL = "https://www.googleapis.com/youtube/v3"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.api_key = settings.youtube_api_key
        self.timeout = settings.youtube_request_timeout_seconds
        self.recent_video_limit = max(1, min(settings.youtube_recent_video_limit, 50))

    def analyze_channel(self, channel_url: str) -> Dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("YOUTUBE_API_KEY is missing. Add it to Render environment variables.")

        channel = self._resolve_channel(channel_url)
        channel_id = channel["id"]
        uploads_playlist_id = (
            channel.get("contentDetails", {})
            .get("relatedPlaylists", {})
            .get("uploads")
        )

        if not uploads_playlist_id:
            raise RuntimeError("Could not find this channel's uploads playlist.")

        video_ids = self._get_recent_video_ids(uploads_playlist_id)
        videos = self._get_video_details(video_ids) if video_ids else []
        return self._normalize(channel, videos, channel_url)

    def _request(self, endpoint: str, params: Dict[str, Any], retries: int = 3) -> Dict[str, Any]:
        url = f"{self.BASE_URL}/{endpoint}"
        request_params = dict(params)
        request_params["key"] = self.api_key

        last_error: Optional[Exception] = None
        for attempt in range(1, retries + 1):
            try:
                response = requests.get(url, params=request_params, timeout=self.timeout)
                if response.status_code >= 400:
                    try:
                        error_detail = response.json().get("error", {}).get("message", response.text)
                    except Exception:
                        error_detail = response.text
                    raise RuntimeError(f"YouTube API error {response.status_code}: {error_detail}")
                return response.json()
            except Exception as exc:
                last_error = exc
                if attempt >= retries:
                    break
                sleep_seconds = min(2 ** attempt, 8)
                logger.warning("YouTube API request failed. retry=%s endpoint=%s error=%s", attempt, endpoint, exc)
                time.sleep(sleep_seconds)

        raise RuntimeError(f"YouTube API request failed: {last_error}")

    def _resolve_channel(self, channel_url: str) -> Dict[str, Any]:
        identifier = self._extract_identifier(channel_url)

        if identifier.get("type") == "channel_id":
            channel = self._get_channel_by_id(identifier["value"])
            if channel:
                return channel

        if identifier.get("type") == "handle":
            channel = self._get_channel_by_handle(identifier["value"])
            if channel:
                return channel

        search_query = identifier.get("value") or channel_url
        channel = self._search_channel(search_query)
        if channel:
            return channel

        raise RuntimeError("Could not resolve YouTube channel URL. Use a valid channel URL, @handle URL, or channel ID URL.")

    @staticmethod
    def _extract_identifier(channel_url: str) -> Dict[str, str]:
        raw = channel_url.strip()
        if not raw:
            return {"type": "query", "value": ""}

        if re.match(r"^UC[a-zA-Z0-9_-]{20,}$", raw):
            return {"type": "channel_id", "value": raw}

        if raw.startswith("@"):
            return {"type": "handle", "value": raw}

        parsed = urlparse(raw if raw.startswith(("http://", "https://")) else f"https://{raw}")
        path = parsed.path.strip("/")
        parts = [part for part in path.split("/") if part]

        if not parts:
            return {"type": "query", "value": raw}

        if parts[0] == "channel" and len(parts) >= 2:
            return {"type": "channel_id", "value": parts[1]}

        if parts[0].startswith("@"):
            return {"type": "handle", "value": parts[0]}

        if parts[0] in {"c", "user"} and len(parts) >= 2:
            return {"type": "query", "value": parts[1]}

        return {"type": "query", "value": parts[-1]}

    def _get_channel_by_id(self, channel_id: str) -> Optional[Dict[str, Any]]:
        data = self._request(
            "channels",
            {
                "part": "snippet,statistics,contentDetails",
                "id": channel_id,
                "maxResults": 1,
            },
        )
        items = data.get("items", [])
        return items[0] if items else None

    def _get_channel_by_handle(self, handle: str) -> Optional[Dict[str, Any]]:
        candidates = [handle, handle.lstrip("@")]
        for candidate in candidates:
            try:
                data = self._request(
                    "channels",
                    {
                        "part": "snippet,statistics,contentDetails",
                        "forHandle": candidate,
                        "maxResults": 1,
                    },
                )
                items = data.get("items", [])
                if items:
                    return items[0]
            except Exception as exc:
                logger.info("Handle lookup failed for %s: %s", candidate, exc)
        return self._search_channel(handle.lstrip("@"))

    def _search_channel(self, query: str) -> Optional[Dict[str, Any]]:
        data = self._request(
            "search",
            {
                "part": "snippet",
                "type": "channel",
                "q": query,
                "maxResults": 1,
            },
        )
        items = data.get("items", [])
        if not items:
            return None
        channel_id = items[0].get("snippet", {}).get("channelId")
        if not channel_id:
            return None
        return self._get_channel_by_id(channel_id)

    def _get_recent_video_ids(self, uploads_playlist_id: str) -> List[str]:
        data = self._request(
            "playlistItems",
            {
                "part": "contentDetails",
                "playlistId": uploads_playlist_id,
                "maxResults": self.recent_video_limit,
            },
        )
        video_ids: List[str] = []
        for item in data.get("items", []):
            video_id = item.get("contentDetails", {}).get("videoId")
            if video_id:
                video_ids.append(video_id)
        return video_ids

    def _get_video_details(self, video_ids: List[str]) -> List[Dict[str, Any]]:
        if not video_ids:
            return []

        data = self._request(
            "videos",
            {
                "part": "snippet,statistics,contentDetails",
                "id": ",".join(video_ids),
                "maxResults": len(video_ids),
            },
        )
        return data.get("items", [])

    @staticmethod
    def _to_int(value: Any, default: int = 0) -> int:
        if value is None or value == "":
            return default
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _parse_duration_seconds(duration: str) -> int:
        """Parse ISO-8601 YouTube duration like PT1H2M3S into seconds."""
        if not duration:
            return 0
        pattern = re.compile(r"P(?:(?P<days>\d+)D)?T?(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?")
        match = pattern.fullmatch(duration)
        if not match:
            return 0
        days = int(match.group("days") or 0)
        hours = int(match.group("hours") or 0)
        minutes = int(match.group("minutes") or 0)
        seconds = int(match.group("seconds") or 0)
        return days * 86400 + hours * 3600 + minutes * 60 + seconds

    def _normalize(self, channel: Dict[str, Any], videos: List[Dict[str, Any]], source_url: str) -> Dict[str, Any]:
        snippet = channel.get("snippet", {})
        statistics = channel.get("statistics", {})
        subscribers = self._to_int(statistics.get("subscriberCount"))

        shorts: List[Dict[str, Any]] = []
        longforms: List[Dict[str, Any]] = []
        all_comments: List[int] = []
        total_views = 0
        text_parts = [
            snippet.get("title", ""),
            snippet.get("description", ""),
        ]

        for video in videos:
            video_snippet = video.get("snippet", {})
            video_stats = video.get("statistics", {})
            duration_seconds = self._parse_duration_seconds(video.get("contentDetails", {}).get("duration", ""))
            view_count = self._to_int(video_stats.get("viewCount"))
            comment_count = self._to_int(video_stats.get("commentCount"))
            like_count = self._to_int(video_stats.get("likeCount"))

            normalized_video = {
                "id": video.get("id"),
                "title": video_snippet.get("title", ""),
                "description": video_snippet.get("description", ""),
                "tags": video_snippet.get("tags", []),
                "duration_seconds": duration_seconds,
                "view_count": view_count,
                "comment_count": comment_count,
                "like_count": like_count,
            }

            total_views += view_count
            all_comments.append(comment_count)
            text_parts.extend([
                normalized_video["title"],
                normalized_video["description"],
                " ".join(normalized_video["tags"]),
            ])

            if duration_seconds <= 60:
                shorts.append(normalized_video)
            else:
                longforms.append(normalized_video)

        shorts_views = [video["view_count"] for video in shorts]
        longform_views = [video["view_count"] for video in longforms]
        avg_shorts_views = round(mean(shorts_views)) if shorts_views else 0
        avg_longform_views = round(mean(longform_views)) if longform_views else 0
        avg_comments = round(mean(all_comments), 1) if all_comments else 0
        engagement_rate_number = ((avg_comments / subscribers) * 100) if subscribers > 0 else 0

        return {
            "channel_id": channel.get("id", ""),
            "channel_title": snippet.get("title", ""),
            "channel_description": snippet.get("description", ""),
            "source_url": source_url,
            "subscribers": subscribers,
            "avg_shorts_views": avg_shorts_views,
            "avg_longform_views": avg_longform_views,
            "shorts_count": len(shorts),
            "longform_count": len(longforms),
            "avg_comments": avg_comments,
            "engagement_rate_number": engagement_rate_number,
            "engagement_rate": f"{engagement_rate_number:.2f}%",
            "recent_video_count": len(videos),
            "text_corpus": "\n".join(part for part in text_parts if part),
            "videos": shorts + longforms,
        }
