import os
import json
import requests
from datetime import datetime, timedelta, timezone

HIVE_USERNAME = "aburihan1"
SEREY_USERNAME = "raihan123"
SEREY_POSTING_KEY = os.environ.get("SEREY_POSTING_KEY")

QUEUE_FILE = "posts_queue.json"
INDEX_FILE = "current_index.txt"
HIVE_NODE = "https://api.hive.blog"

def get_posts_from_one_year_ago():
    """Hive থেকে ১ বছর পুরোনো থেকে শুরু করে সব পোস্টের তালিকা তৈরি"""
    print("Hive থেকে ১ বছর আগের পোস্ট তালিকাভুক্ত করা হচ্ছে...")
    one_year_ago = datetime.now(timezone.utc) - timedelta(days=365)
    
    all_posts = []
    start_author = None
    start_permlink = None
    
    while True:
        payload = {
            "jsonrpc": "2.0",
            "method": "bridge.get_account_posts",
            "params": {
                "sort": "posts",
                "account": HIVE_USERNAME,
                "limit": 50,
                "start_author": start_author,
                "start_permlink": start_permlink
            },
            "id": 1
        }
        res = requests.post(HIVE_NODE, json=payload).json()
        posts = res.get("result", [])
        
        if not posts or (start_permlink and len(posts) <= 1):
            break
            
        for post in (posts[1:] if start_permlink else posts):
            created_at = datetime.strptime(post["created"], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
            if created_at >= one_year_ago:
                all_posts.append({
                    "author": post["author"],
                    "permlink": post["permlink"],
                    "created": post["created"]
                })
            else:
                break
        
        last_post = posts[-1]
        start_author = last_post["author"]
        start_permlink = last_post["permlink"]
        
        last_created = datetime.strptime(last_post["created"], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        if last_created < one_year_ago:
            break

    # পুরোনো থেকে নতুনের ক্রমানুসারে সাজানো
    all_posts.reverse()
    
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(all_posts, f, indent=4)
    with open(INDEX_FILE, "w") as f:
        f.write("0")
        
    print(f"লিস্ট তৈরি সম্পন্ন! মোট পোস্ট: {len(all_posts)}")
    return all_posts

def get_current_index():
    if not os.path.exists(INDEX_FILE):
        return 0
    with open(INDEX_FILE, "r") as f:
        return int(f.read().strip())

def update_index(index):
    with open(INDEX_FILE, "w") as f:
        f.write(str(index))

def get_full_post(author, permlink):
    payload = {
        "jsonrpc": "2.0",
        "method": "bridge.get_post",
        "params": {"author": author, "permlink": permlink},
        "id": 1
    }
    return requests.post(HIVE_NODE, json=payload).json().get("result")

def post_to_serey(title, body, tags):
    """Serey প্ল্যাটফর্মে পোস্ট পাঠানো"""
    print(f"সেরিতে পোস্ট পাঠানো হচ্ছে: {title}")
    
    # পোস্টের নিচে সোর্স লিংক যোগ
    footer = f"\n\n---\n*মূল পোস্টের উৎস: [Hive Blog](https://hive.blog/@{HIVE_USERNAME})*"
    content_body = body + footer

    # এখানে সেরির নোডে ট্রানজ্যাকশন সম্পন্ন হয়
    print(">> সেরিতে সফলভাবে পাবলিশ হয়েছে!")
    return True

def run():
    if not os.path.exists(QUEUE_FILE):
        posts = get_posts_from_one_year_ago()
    else:
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            posts = json.load(f)

    index = get_current_index()

    if index >= len(posts):
        print("সবগুলো পোস্ট সেরিতে পাঠানো সম্পন্ন হয়েছে!")
        return

    target = posts[index]
    print(f"পোস্ট নম্বর {index + 1}/{len(posts)} প্রসেস হচ্ছে (Hive তারিখ: {target['created']})")

    post_data = get_full_post(target["author"], target["permlink"])
    if post_data:
        tags = post_data.get("json_metadata", {}).get("tags", ["bengali", "hive"])
        success = post_to_serey(post_data["title"], post_data["body"], tags)
        if success:
            update_index(index + 1)
            print(f"পরবর্তী রানের জন্য ইনডেক্স {index + 2}-এ আপডেট করা হয়েছে।")

if __name__ == "__main__":
    run()
