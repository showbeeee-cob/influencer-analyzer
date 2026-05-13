from apify_client import ApifyClient
from config import APIFY_API_TOKEN


def scrape_instagram_profile(url):

    print("🔍 시작")

    if not APIFY_API_TOKEN:
        return None

    client = ApifyClient(APIFY_API_TOKEN)

    try:

        run = client.actor(
            "apify/instagram-scraper"
        ).call(
            run_input={
                "directUrls": [url],
                "resultsLimit": 1
            }
        )

        dataset = list(
            client.dataset(
                run["defaultDatasetId"]
            ).iterate_items()
        )

        return dataset

    except Exception as e:

        print(e)

        return None


def extract_influencer_data(data):

    try:

        if not data:
            return None

        item = data[0]

        followers = item.get(
            "followersCount",
            0
        )

        return {
            "followers": followers,
            "profile_image": "",
            "posts": []
        }

    except Exception as e:

        print(e)

        return None