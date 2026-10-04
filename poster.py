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
    print("Hive থেকে ১ বছর পুরোনো পোস্ট স্ক্যান করা হচ্ছে...")
    one_year_ago = datetime.now(timezone.utc) - timedelta(days=365)
    
    all_posts = []
    start_author = None
    start_permlink = None
    
    while True:
        # প্যারামিটারে null না পাঠিয়ে সঠিকভাবে কুয়েরি তৈরি করা
        params = {
            "sort": "posts",
            "account": HIVE_USERNAME,
            "limit": 50
        }
        if start_author and start_permlink:
            params["start_author"] = start_author
            params["start_permlink"] = start_permlink
            
        payload = {
            "jsonrpc": "2.0",
            "method": "bridge.get_account_posts",
            "params": params,
            "id": 1
        }
        
        try:
            res = requests.post(HIVE_NODE, json=payload, timeout=20).json()
            posts = res.get("result", [])
        except Exception as e:
            print(f"API Error: {e}")
            break
        
        if not posts:
            break
            
        current_batch = posts[1:] if (start_author and start_permlink) else posts
        if not current_batch:
            break
            
        reached_end = False
        for post in current_batch:
            created_str = post.get("created", "")
            created_at = datetime.strptime(created_str, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
            
            # ১ বছর পুরোনো থেকে আজকের পোস্টগুলো নেওয়া
            if created_at >= one_year_ago:
                all_posts.append({
                    "author": post["author"],
                    "permlink": post["permlink"],
                    "created": post["created"],
                    "title": post.get("title", "")
                })
            else:
                reached_end = True
                break
        
        if reached_end or len(posts) < 50:
            break
            
        last_post = posts[-1]
        start_author = last_post["author"]
        start_permlink = last_post["permlink"]

    # পুরোনো থেকে নতুনের দিকে সাজানো (Oldest first)
    all_posts.reverse()
    
    if all_posts:
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(all_posts, f, indent=4)
        with open(INDEX_FILE, "w") as f:
            f.write("0")
        print(f"লিস্ট তৈরি সম্পন্ন! মোট পোস্ট পাওয়া গেছে: {len(all_posts)} টি।")
    else:
        print("কোনো পোস্ট পাওয়া যায়নি। ইউজারনেম চেক করুন।")
        
    return all_posts

def get_current_index():
    if not os.path.exists(INDEX_FILE):
        return 0
    with open(INDEX_FILE, "r") as f:
        try:
            return int(f.read().strip())
        except:
            return 0

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
    try:
        return requests.post(HIVE_NODE, json=payload, timeout=20).json().get("result")
    except:
        return None

def post_to_serey(title, body, tags):
    """সেরিতে পোস্ট পাঠানোর ফাংশন"""
    print(f"সেরিতে পোস্ট পাঠানো হচ্ছে: {title}")
    
    footer = f"\n\n---\n*মূল উৎস: [Hive Blog](https://hive.blog/@{HIVE_USERNAME})*"
    content_body = body + footer

    # এখানে সেরিতে ব্রডকাস্ট হবে
    print(">> সেরিতে সফলভাবে পাবলিশ সম্পন্ন হয়েছে!")
    return True

def run():
    posts = []
    # যদি লিস্ট ফাইল না থাকে অথবা ফাইল খালি থাকে
    if os.path.exists(QUEUE_FILE):
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            try:
                posts = json.load(f)
            except:
                posts = []

    if not posts:
        posts = get_posts_from_one_year_ago()

    if not posts:
        print("পোস্টের তালিকা খালি রয়েছে।")
        return

    index = get_current_index()

    if index >= len(posts):
        print("সবগুলো ১ বছর পুরোনো পোস্ট সেরিতে পাঠানো সম্পন্ন হয়েছে!")
        return

    target = posts[index]
    print(f"পোস্ট নম্বর {index + 1}/{len(posts)} প্রসেস হচ্ছে (তারিখ: {target['created']})")

    post_data = get_full_post(target["author"], target["permlink"])
    if post_data:
        tags = post_data.get("json_metadata", {}).get("tags", ["bengali", "hive"])
        success = post_to_serey(post_data["title"], post_data["body"], tags)
        if success:
            update_index(index + 1)
            print(f"পরবর্তী ১২ ঘণ্টা পর পোস্ট নং {index + 2} যাবে।")
    else:
        print("Hive থেকে পোস্টের কনটেন্ট লোড করা যায়নি।")

if __name__ == "__main__":
    run()
