def calculate_trimmed_er(posts, followers, trim_percent=0.1):
    """
    Calculates Engagement Rate using trimmed mean logic.
    Removes the top and bottom `trim_percent` of posts by engagement.
    """
    if not followers or followers == 0:
        return 0.0

    if not posts:
        return 0.0

    # Calculate engagement per post (likes + comments)
    engagements = []
    for post in posts:
        # Defaults to 0 if keys are missing
        likes = post.get("likesCount", 0)
        comments = post.get("commentsCount", 0)
        engagements.append(likes + comments)
    
    n_posts = len(engagements)
    
    if n_posts == 0:
        return 0.0

    engagements.sort()
    
    trim_count = int(n_posts * trim_percent)
    
    # Trim top and bottom
    if trim_count > 0 and n_posts > 2 * trim_count:
        trimmed_engagements = engagements[trim_count:-trim_count]
    else:
        trimmed_engagements = engagements
        
    avg_engagement = sum(trimmed_engagements) / len(trimmed_engagements) if trimmed_engagements else 0.0
    
    er = (avg_engagement / followers) * 100
    return er

def grade_influencer(er):
    """
    Grades influencer based on ER.
    A = 5%+
    B = 2~5%
    C = below 2%
    """
    if er >= 5.0:
        return "A"
    elif er >= 2.0:
        return "B"
    else:
        return "C"
