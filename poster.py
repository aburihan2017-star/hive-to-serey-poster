import os
import json
import re
import time
from datetime import datetime, timedelta, timezone
import requests

# ============================================================
# SETTINGS & TOKEN (HIVE -> SEREY)
# ============================================================

HIVE_USERNAME = os.environ.get("HIVE_USERNAME", "aburihan1").replace("@", "").strip()
SEREY_LOGIN = os.environ.get("SEREY_LOGIN", os.environ.get("SEREY_USERNAME", "raihan123")).replace("@", "").strip()

FALLBACK_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0eXBlIjoib3duZXIiLCJ1c2VybmFtZSI6InJhaWhhbjEyMyIsInBvc3RpbmciOiI1S0hDS292c1JZNUs3RUNGTk1HUlZwTTJucFNXNTF0Q0x4R3dmWGU2SjV4eTVYNkFHcTgiLCJhY3RpdmUiOiI1S2h2Y1BKZEdKbU1ycURpRHh1c1dYY1BDV0xpdjlaWk1RdWd2TUR1MnhWcnBoNEw5eEciLCJpYXQiOjE3OTEwMjk2Mzd9.ZH2rsz_EARVvbSY7E6D5HvtXLmLZM0qKYrMvWchf4Vw"
SEREY_TOKEN = os.environ.get("SEREY_TOKEN", FALLBACK_TOKEN).strip()

SEREY_API_POST = "https://bengali.serey.io/api/posts"
SUMMARIZE_API = "https://global-api.serey.io/api/v2/serey-web/summarize-post"

SYNC_FILE = "synced_posts.json"
POSTS_PER_RUN = 1
DAYS_LIMIT = 365

HIVE_NODES = [
    "https://api.hive.blog",
    "https://api.openhive.network",
    "https://api.deathwing.me",
    "https://rpc.ecency.com",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ============================================================
# HIVE RPC
# ============================================================

def rpc(method, params):
    payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    for node in HIVE_NODES:
        try:
            r = requests.post(node, json=payload, headers=HEADERS, timeout=20)
            r.raise_for_status()
            data = r.json()
            if "error" in data:
                continue
            return data.get("result")
        except Exception:
            pass
    raise Exception("All Hive RPC nodes failed")

# ============================================================
# SYNC FILE
# ============================================================

def load_synced():
    if not os.path.exists(SYNC_FILE):
        return set()
    try:
        with open(SYNC_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data) if isinstance(data, list) else set()
    except Exception:
        return set()

def save_synced(data):
    temp_file = SYNC_FILE + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(sorted(data), f, ensure_ascii=False, indent=2)
    os.replace(temp_file, SYNC_FILE)

# ============================================================
# BODY FORMATTING & THUMBNAIL
# ============================================================

def format_body_and_thumbnail(body, metadata):
    thumbnail = None
    try:
        meta = json.loads(metadata or "{}") if isinstance(metadata, str) else (metadata or {})
        images = meta.get("image", [])
        if isinstance(images, list) and images:
            thumbnail = images[0]
    except Exception:
        pass

    if not thumbnail:
        m = re.search(r'!\[[^\]]*\]\((https?://[^)\s]+)', body, re.I)
        if m: thumbnail = m.group(1)
    if not thumbnail:
        m = re.search(r'<img[^>]+src=["\'](https?://[^"\'>\s]+)', body, re.I)
        if m: thumbnail = m.group(1)

    clean = re.sub(r'!\[[^\]]*\]\(\s*https?://[^)\s]+\s*\)', '', body, flags=re.I)
    clean = re.sub(r'<img\b[^>]*>', '', clean, flags=re.I)
    clean = re.sub(r'<[^>]+>', '', clean)
    clean = re.sub(r'^\s{0,3}#{1,6}\s*', '', clean, flags=re.M)
    clean = re.sub(r'\*\*(.*?)\*\*', r'\1', clean, flags=re.S)
    clean = re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)', r'\1', clean, flags=re.I)

    paragraphs = [p.strip() for p in clean.split("\n\n") if p.strip()]
    html_body = "".join(f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs)

    if not thumbnail:
        thumbnail = "https://bengali.serey.io/thumbnails/thumbnail.png"

    return html_body, thumbnail

# ============================================================
# GET POSTS (OLDEST TO NEWEST)
# ============================================================

def get_posts():
    cutoff = datetime.now(timezone.utc) - timedelta(days=DAYS_LIMIT)
    posts, seen = [], set()
    start_author, start_permlink = None, None
    reached_old = False

    print(f"Collecting Hive posts for @{HIVE_USERNAME} (last {DAYS_LIMIT} days)...", flush=True)
    print(f"Cut-off date: {cutoff.strftime('%Y-%m-%d')}", flush=True)

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    while len(posts) < 3000 and not reached_old:
        try:
            res = rpc("condenser_api.get_discussions_by_author_before_date", [HIVE_USERNAME, start_permlink or "", now_str, 100])
        except Exception:
            res = None

        if not res:
            params = {"tag": HIVE_USERNAME, "limit": 100}
            if start_author and start_permlink:
                params["start_author"] = start_author
                params["start_permlink"] = start_permlink
            try:
                res = rpc("condenser_api.get_discussions_by_blog", params)
            except Exception:
                break

        if not res:
            break

        batch = res[1:] if (start_author and start_permlink) else res
        if not batch:
            break

        for p in batch:
            if p.get("author") != HIVE_USERNAME:
                continue
            pid = f"{p['author']}/{p['permlink']}"
            if pid in seen:
                continue

            created = datetime.strptime(p["created"], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
            if created < cutoff:
                reached_old = True
                break

            seen.add(pid)
            body_html, thumb = format_body_and_thumbnail(p.get("body", ""), p.get("json_metadata", "{}"))
            posts.append({
                "id": pid,
                "title": p.get("title", "").strip(),
                "body": body_html,
                "thumbnail": thumb,
                "created": p["created"]
            })

        if reached_old or len(res) < 100:
            break

        if res[-1]["author"] == start_author and res[-1]["permlink"] == start_permlink:
            break
        start_author, start_permlink = res[-1]["author"], res[-1]["permlink"]
        time.sleep(0.2)

    posts.reverse()
    return posts

# ============================================================
# PUBLISH VIA REST API
# ============================================================

def publish_post_api(token, post):
    print(f"Submitting via REST API: {post['title']}", flush=True)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:156.0) Gecko/20100101 Firefox/156.0",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json; charset=UTF-8",
        "authorization": f"Bearer {token}",
        "Origin": "https://bengali.serey.io",
        "Referer": "https://bengali.serey.io/write/new",
        "Cookie": f'serey_no_cookie_notice_seen=1; serey_new_jwt_auth_token={{"token":"{token}","username":"{SEREY_LOGIN}"}}'
    }

    payload = {
        "images": [post["thumbnail"]],
        "videos": [],
        "categories": "News",
        "subcategories": ["Others"],
        "title": post["title"],
        "desc": "",
        "body": post["body"],
        "other_blockchain": False,
        "post_to_blockchain": True,
        "forever": False,
        "hive_community": "",
        "steem_community": "",
        "post_to_hive": False,
        "post_to_steem": False,
        "steem_tags": [],
        "hive_tags": [],
        "is_post_video_component": False,
        "is_video_component_only": False,
        "is_ai_generated": False,
        "type": 1,
        "publish_scope_community_id": None,
        "site_credit": f'<p>This was posted using <a title="This link will take you away current website" href="https://bengali.serey.io" rel="nofollow noopener">Serey.io</a> cross platform posting from <a href="https://ecency.com/@{HIVE_USERNAME}">Hive</a>.</p>',
        "community_id": 2
    }

    response = requests.post(SEREY_API_POST, json=payload, headers=headers, timeout=30)
    print(f"Serey API Response Code: {response.status_code}", flush=True)
    print(f"Serey API Response: {response.text[:300]}", flush=True)

    if response.status_code in [200, 201]:
        try:
            res_data = response.json()
            permlink = res_data.get("permlink") or res_data.get("data", {}).get("permlink")
            if permlink:
                requests.post(SUMMARIZE_API, json={"author": SEREY_LOGIN, "permlink": permlink}, timeout=10)
        except Exception:
            pass
        return True

    return False

# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("HIVE -> SEREY PURE REST API SYNC")
    print("ORDER: OLDEST TO NEWEST")
    print("=" * 60)

    if not HIVE_USERNAME:
        print("❌ Missing HIVE_USERNAME!", flush=True)
        return

    token = SEREY_TOKEN
    print("✓ Token loaded successfully.", flush=True)

    synced = load_synced()
    posts = get_posts()
    new_posts = [p for p in posts if p["id"] not in synced]

    print(f"Total Hive Posts: {len(posts)}")
    print(f"Unsynced Posts: {len(new_posts)}")

    if not new_posts:
        print("No new posts to publish.")
        return

    post_to_run = new_posts[0]
    print(f"Target Post (Oldest): {post_to_run['id']}", flush=True)
    print(f"Post Date: {post_to_run['created']}", flush=True)

    success = publish_post_api(token, post_to_run)
    if success:
        print(f"\n✓✓✓ SUCCESSFULLY PUBLISHED: {post_to_run['id']} ✓✓✓", flush=True)
        synced.add(post_to_run["id"])
        save_synced(synced)
        print("✓ Updated synced_posts.json successfully.", flush=True)
    else:
        print(f"\n❌ FAILED TO PUBLISH: {post_to_run['id']}", flush=True)
        raise Exception("API Submission failed!")

if __name__ == "__main__":
    main()
