import os
import json
import requests
import re
import random
import string
from datetime import datetime, timezone
from beem import Steem

HIVE_USERNAME = "aburihan1"
SEREY_USERNAME = "raihan123"
SEREY_POSTING_KEY = os.environ.get("SEREY_POSTING_KEY")

QUEUE_FILE = "posts_queue.json"
INDEX_FILE = "current_index.txt"

# একাধিক অ্যাক্টিভ Hive RPC নোড
HIVE_NODES = [
    "https://api.hive.blog",
    "https://api.openhive.network",
    "https://api.deathwing.me",
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

def fetch_hive_posts():
    """Hive/Ecency থেকে aburihan1 এর সমস্ত পোস্ট (কমিউনিটি পোস্ট সহ) আনা"""
    print(f"Hive থেকে @{HIVE_USERNAME} এর সমস্ত পোস্ট সংগ্রহ করা হচ্ছে...")
    
    # এই মেথডটি সব ধরনের কমিউনিটি পোস্ট খুঁজে নিয়ে আসে
    payload = {
        "jsonrpc": "2.0",
        "method": "condenser_api.get_discussions_by_author_before_date",
        "params": [HIVE_USERNAME, "", "2099-01-01T00:00:00", 50],
        "id": 1
    }
    
    posts_data = None
    for node in HIVE_NODES:
        try:
            res = requests.post(node, json=payload, headers=HEADERS, timeout=15)
            data = res.json()
            if "result" in data and isinstance(data["result"], list) and len(data["result"]) > 0:
                posts_data = data["result"]
                print(f"[{node}] থেকে সফলভাবে কানেক্ট হয়েছে!")
                break
        except Exception:
            continue

    if not posts_data:
        print("কোনো নোড থেকে পোস্ট পাওয়া যায়নি।")
        return []

    all_posts = []
    for post in posts_data:
        # শুধুমাত্র aburihan1 এর নিজের তৈরি পোস্ট নেওয়া
        if post.get("author") != HIVE_USERNAME:
            continue
            
        all_posts.append({
            "author": post["author"],
            "permlink": post["permlink"],
            "title": post.get("title", ""),
            "body": post.get("body", ""),
            "json_metadata": post.get("json_metadata", "{}"),
            "created": post.get("created", "")
        })

    # পুরোনো থেকে নতুনের ক্রমানুসারে সাজানো (Oldest first)
    all_posts.reverse()

    if all_posts:
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(all_posts, f, indent=4, ensure_ascii=False)
        with open(INDEX_FILE, "w") as f:
            f.write("0")
        print(f"✅ সফল! মোট {len(all_posts)} টি পোস্ট পাওয়া গেছে।")
        print("\nখুঁজে পাওয়া সাম্প্রতিক কিছু পোস্টের শিরোনাম:")
        for i, p in enumerate(all_posts[-5:], 1):
            print(f"  {i}. {p['title']}")
    else:
        print("কোনো পোস্ট তালিকায় যুক্ত করা যায়নি।")

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

def post_to_serey(title, body, tags):
    """beem ব্যবহার করে সরাসরি Serey ব্লকচেইনে পোস্ট পাঠানো"""
    print(f"\nসেরিতে পোস্ট পাঠানোর প্রস্তুতি: {title}")
    
    if not SEREY_POSTING_KEY:
        print("❌ এরর: SEREY_POSTING_KEY পাওয়া যায়নি! GitHub Secrets চেক করুন।")
        return False

    footer = f"\n\n---\n*মূল উৎস: [Hive/Ecency Blog](https://ecency.com/@{HIVE_USERNAME})*"
    content_body = body + footer

    # সেরির পারমালিংক তৈরি
    clean_title = re.sub(r'[^a-zA-Z0-9\s-]', '', title).strip().lower()
    slug = re.sub(r'[\s-]+', '-', clean_title)
    rand_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    permlink = f"{slug}-{rand_suffix}" if slug else f"post-{rand_suffix}"

    # ট্যাগ প্রক্রিয়াকরণ
    valid_tags = []
    if isinstance(tags, list):
        for t in tags:
            clean_tag = re.sub(r'[^a-zA-Z0-9-]', '', str(t)).lower()
            if clean_tag and len(clean_tag) >= 2:
                valid_tags.append(clean_tag)
    if not valid_tags:
        valid_tags = ["bengali", "hive", "serey"]

    try:
        # Serey ব্লকচেইনে ট্রানজাকশন পাঠানো
        stm = Steem(
            node=SEREY_NODES,
            keys=[SEREY_POSTING_KEY],
            num_retries=3
        )
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
        posts = fetch_hive_posts()

    if not posts:
        print("পোস্টের তালিকা খালি রয়েছে।")
        return

    index = get_current_index()

    if index >= len(posts):
        print("সবগুলো পোস্ট সেরিতে পাঠানো সম্পন্ন হয়েছে!")
        return

    target = posts[index]
    print(f"\n--- পোস্ট নম্বর {index + 1}/{len(posts)} প্রসেস হচ্ছে ---")
    print(f"শিরোনাম: {target.get('title')}")
    print(f"মূল প্রকাশের তারিখ: {target.get('created')}")

    # মেটাডাটা থেকে ট্যাগ নেওয়া
    tags = ["bengali", "hive"]
    raw_meta = target.get("json_metadata", "{}")
    try:
        meta = json.loads(raw_meta) if isinstance(raw_meta, str) else raw_meta
        if "tags" in meta and isinstance(meta["tags"], list):
            tags = meta["tags"]
    except Exception:
        pass

    success = post_to_serey(target["title"], target["body"], tags)
    if success:
        update_index(index + 1)
        print(f">> পরবর্তী ১২ ঘণ্টা পর পোস্ট নং {index + 2} স্বয়ংক্রিয়ভাবে যাবে।")

if __name__ == "__main__":
    run()
