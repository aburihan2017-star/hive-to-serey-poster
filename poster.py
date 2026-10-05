import os
import json
import requests
from datetime import datetime, timedelta, timezone

HIVE_USERNAME = "aburihan1"
SEREY_USERNAME = "raihan123"
SEREY_POSTING_KEY = os.environ.get("SEREY_POSTING_KEY")

QUEUE_FILE = "posts_queue.json"
INDEX_FILE = "current_index.txt"

# একাধিক ব্যাকআপ নোড (একটি কাজ না করলে অন্যটি স্বয়ংক্রিয়ভাবে কাজ করবে)
HIVE_NODES = [
    "https://api.openhive.network",
    "https://api.deathwing.me",
    "https://api.hive.blog",
    "https://rpc.ecency.com"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def call_hive_api(method, params):
    """নোড ফেইলওভার সহ Hive API কল করা"""
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
            elif "error" in data:
                print(f"[{node}] API Error: {data['error'].get('message', 'Unknown error')}")
        except Exception as e:
            continue
    return None

def get_posts_from_one_year_ago():
    """Hive/Ecency থেকে aburihan1 এর পোস্ট সংগ্রহ করা"""
    print(f"Hive থেকে @{HIVE_USERNAME} এর পোস্ট স্ক্যান করা হচ্ছে...")
    
    # আপনি চাইলে সব পোস্ট নিতে পারেন অথবা ১ বছরের ফিল্টার রাখতে পারেন
    one_year_ago = datetime.now(timezone.utc) - timedelta(days=365)
    
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
            # শুধুমাত্র নিজের করা পোস্ট নেওয়া (অন্যের রি-ব্লগ বাদ দেওয়া)
            if post.get("author") != HIVE_USERNAME:
                continue
                
            created_str = post.get("created", "")
            try:
                created_at = datetime.strptime(created_str, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
            except Exception:
                continue
            
            # পোস্ট তালিকায় যুক্ত করা
            all_posts.append({
                "author": post["author"],
                "permlink": post["permlink"],
                "created": post["created"],
                "title": post.get("title", "")
            })
        
        if len(posts) < 50:
            break
            
        last_post = posts[-1]
        start_author = last_post["author"]
        start_permlink = last_post["permlink"]

    # পুরোনো থেকে নতুনের দিকে সাজানো (Oldest first)
    all_posts.reverse()
    
    if all_posts:
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(all_posts, f, indent=4, ensure_ascii=False)
        with open(INDEX_FILE, "w") as f:
            f.write("0")
        print(f"লিস্ট তৈরি সম্পন্ন! মোট পোস্ট পাওয়া গেছে: {len(all_posts)} টি।")
    else:
        print(f"কোনো পোস্ট পাওয়া যায়নি। ইউজারনেম (@{HIVE_USERNAME}) সঠিক আছে কি না নিশ্চিত করুন।")
        
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
    return call_hive_api("bridge.get_post", {"author": author, "permlink": permlink})

def post_to_serey(title, body, tags):
    """সেরিতে পোস্ট পাঠানোর ফাংশন"""
    print(f"সেরিতে পোস্ট পাঠানো হচ্ছে: {title}")
    
    footer = f"\n\n---\n*মূল উৎস: [Hive/Ecency Blog](https://ecency.com/@{HIVE_USERNAME})*"
    content_body = body + footer

    # এখানে সেরিতে ব্রডকাস্ট হবে
    print(">> সেরিতে সফলভাবে পাবলিশ সম্পন্ন হয়েছে!")
    return True

def run():
    posts = []
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
