from apify_client import ApifyClient
from config import APIFY_API_TOKEN

def scrape_instagram_profile(url):
    print(f"🔍 [Apify] 수집 시작: {url}")
    if not APIFY_API_TOKEN: 
        print("❌ APIFY_API_TOKEN이 설정되지 않았습니다.")
        return None
        
    client = ApifyClient(APIFY_API_TOKEN)
    run_input = {"directUrls": [url], "resultsLimit": 1}
    try:
        run = client.actor("apify/instagram-scraper").call(run_input=run_input)
        dataset = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        
        # 인스타 비공개 계정이거나, 수집기가 막혔을 때의 방어
        if not dataset:
            print("⚠️ [경고] Apify가 작동했으나 데이터를 가져오지 못했습니다. (비공개 계정이거나 인스타 차단)")
            return None
            
        return dataset
    except Exception as e: 
        print(f"❌ Apify 수집 중 심각한 오류: {e}")
        return None

def extract_influencer_data(data):
    try:
        if not data: return None
        item = data[0] if isinstance(data, list) else data
        followers = item.get("followersCount") or item.get("edge_followed_by", {}).get("count") or 0
        profile_image = item.get("profilePicUrlHD") or item.get("profilePicUrl") or ""
        
        raw_posts = item.get("latestPosts") or item.get("edge_owner_to_timeline_media", {}).get("edges", [])
        posts = []
        for p in raw_posts:
            node = p.get("node") if "node" in p else p
            posts.append({
                "likesCount": node.get("likesCount") or node.get("edge_liked_by", {}).get("count") or 0,
                "commentsCount": node.get("commentsCount") or node.get("edge_media_to_comment", {}).get("count") or 0,
                "videoViewCount": node.get("videoViewCount") or node.get("video_view_count") or 0
            })
        
        print(f"✅ [추출 성공] 팔로워 {followers}명, 게시물 {len(posts)}개 확보!")
        return {"followers": followers, "profile_image": profile_image, "posts": posts}
    except Exception as e: 
        print(f"❌ 데이터 추출 오류: {e}")
        return None