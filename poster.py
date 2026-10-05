import os
import json
import requests
import re
import random
import string
from datetime import datetime, timedelta, timezone
from beem import Steem

HIVE_USERNAME = "aburihan1"
SEREY_USERNAME = "raihan123"
SEREY_POSTING_KEY = os.environ.get("SEREY_POSTING_KEY")

QUEUE_FILE = "posts_queue.json"
INDEX_FILE = "current_index.txt"

# Hive ব্যাকআপ নোড তালিকা
HIVE_NODES = [
    "https://api.openhive.network",
    "https://api.deathwing.me",
    "https://api.hive.blog",
    "https://rpc.ecency.com"
]

# Serey নোড তালিকা
SEREY_NODES = [
    "https://serey.io",
    "https://serey.io/wss"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def call_hive_api(method, params):
    """Hive API থেকে ডেটা আনা"""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1
    }
    for node in HIVE_NODES:
        try:
            res = requests.post(node, json=payload, headers=HEADERS, timeout=15)
            data = res.json()
            if "result" in data and data["result"] is not None:
                return data["result"]
        except Exception:
            continue
    return None

def get_posts_from_one_year_ago():
    """Hive/Ecency থেকে aburihan1 এর পোস্ট সংগ্রহ করা"""
    print(f"Hive থেকে @{HIVE_USERNAME} এর পোস্ট স্ক্যান করা হচ্ছে...")
    
    all_posts = []
    start_author = None
    start_permlink = None
    
    for _ in range(10):  # সর্বোচ্চ ৫০০ পোস্ট পর্যন্ত চেক করবে
        params = {
            "sort": "blog",
            "account": HIVE_USERNAME,
            "limit": 50
        }
        if start_author and start_permlink:
            params["start_author"] = start_author
            params["start_permlink"] = start_permlink
            
        posts = call_hive_api("bridge.get_account_posts", params)
        if not posts:
            break
            
        current_batch = posts[1:] if (start_author and start_permlink) else posts
        if not current_batch:
            break
            
        for post in current_batch:
            if post.get("author") != HIVE_USERNAME:
                continue
                
            all_posts.append({
                "author": post["author"],
                "permlink": post["permlink"],
                "created": post.get("created", ""),
                "title": post.get("title", "")
            })
        
        if len(posts) < 50:
            break
            
        last_post = posts[-1]
        start_author = last_post["author"]
        start_permlink = last_post["permlink"]

    # পুরোনো থেকে নতুনের ক্রমানুসারে সাজানো
    all_posts.reverse()
    
    if all_posts:
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(all_posts, f, indent=4, ensure_ascii=False)
        with open(INDEX_FILE, "w") as f:
            f.write("0")
        print(f"লিস্ট তৈরি সম্পন্ন! মোট পোস্ট পাওয়া গেছে: {len(all_posts)} টি।")
    else:
        print(f"কোনো পোস্ট পাওয়া যায়নি। ইউজারনেম (@{HIVE_USERNAME}) চেক করুন।")
        
    return all_posts

def get_current_index():
    if not os.path.exists(INDEX_FILE):
        return 0
    with open(INDEX_FILE, "r") as f:
        try:
            return int(f.read().strip())
        except Exception:
            return 0

def update_index(index):
    with open(INDEX_FILE, "w") as f:
        f.write(str(index))

def get_full_post(author, permlink):
    return call_hive_api("bridge.get_post", {"author": author, "permlink": permlink})

def post_to_serey(title, body, tags):
    """beem ব্যবহার করে সরাসরি Serey ব্লকচেইনে পোস্ট পাঠানো"""
    print(f"সেরিতে পোস্ট পাঠানো হচ্ছে: {title}")
    
    if not SEREY_POSTING_KEY:
        print("❌ এরর: SEREY_POSTING_KEY পাওয়া যায়নি! GitHub Secrets চেক করুন।")
        return False

    footer = f"\n\n---\n*মূল উৎস: [Hive/Ecency Blog](https://ecency.com/@{HIVE_USERNAME})*"
    content_body = body + footer

    # সেরির জন্য ইউনিক পারমালিংক তৈরি করা
    clean_title = re.sub(r'[^a-zA-Z0-9\s-]', '', title).strip().lower()
    slug = re.sub(r'[\s-]+', '-', clean_title)
    rand_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    permlink = f"{slug}-{rand_suffix}" if slug else f"post-{rand_suffix}"

    # ট্যাগ ফিল্টার করা
    valid_tags = []
    if isinstance(tags, list):
        for t in tags:
            clean_tag = re.sub(r'[^a-zA-Z0-9-]', '', str(t)).lower()
            if clean_tag and len(clean_tag) >= 2:
                valid_tags.append(clean_tag)
    if not valid_tags:
        valid_tags = ["bengali", "hive", "serey"]

    try:
        # Serey ব্লকচেইনে কানেক্ট করা
        stm = Steem(
            node=SEREY_NODES,
            keys=[SEREY_POSTING_KEY],
            num_retries=3
        )
        
        # পোস্ট ব্রডকাস্ট করা
        stm.post(
            title=title,
            body=content_body,
            author=SEREY_USERNAME,
            permlink=permlink,
            tags=valid_tags,
            self_vote=True
        )
        print("✅ সেরিতে সফলভাবে পাবলিশ সম্পন্ন হয়েছে!")
        return True
    except Exception as e:
        print(f"❌ সেরিতে পোস্ট করতে গিয়ে ত্রুটি ঘটেছে: {e}")
        return False

def run():
    posts = []
    if os.path.exists(QUEUE_FILE):
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            try:
                posts = json.load(f)
            except Exception:
                posts = []

    if not posts:
        posts = get_posts_from_one_year_ago()

    if not posts:
        print("পোস্টের তালিকা খালি রয়েছে।")
        return

    index = get_current_index()

    if index >= len(posts):
        print("সবগুলো পোস্ট সেরিতে পাঠানো সম্পন্ন হয়েছে!")
        return

    target = posts[index]
    print(f"পোস্ট নম্বর {index + 1}/{len(posts)} প্রসেস হচ্ছে (শিরোনাম: {target.get('title')})")

    post_data = get_full_post(target["author"], target["permlink"])
    if post_data:
        tags = post_data.get("json_metadata", {}).get("tags", ["bengali", "hive"])
        success = post_to_serey(post_data["title"], post_data["body"], tags)
        if success:
            update_index(index + 1)
            print(f"পরবর্তী ১২ ঘণ্টা পর পোস্ট নং {index + 2} যাবে।")
    else:
        print("Hive থেকে পোস্টের বিস্তারিত কনটেন্ট লোড করা যায়নি।")

if __name__ == "__main__":
    run()
