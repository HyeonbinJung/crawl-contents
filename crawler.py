#!/usr/bin/env python3
"""
DC Inside Real-time Best (dcbest) Humor Crawler
Curates ~100 posts appealing to an American / global audience:
- Visual humor (images/GIFs)
- Universal themes: Animals/Pets, Gaming, Sports/UFC, Tech/Stocks, Absurd Fails, Relatable Moments
- Filters out domestic Korean politics, hyper-local drama, and text-only rants.
- Produces CSV and automatically commits/pushes if git remote is configured.
"""

import os
import sys
import csv
import re
import datetime
import urllib.request
import subprocess
from lxml import html

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LATEST_CSV = os.path.join(BASE_DIR, 'dcbest_humor_latest.csv')
HISTORY_DIR = os.path.join(BASE_DIR, 'history')
os.makedirs(HISTORY_DIR, exist_ok=True)

POLITICS_KEYWORDS = [
    '이재명', '윤석열', '한동훈', '민주당', '국민의힘', '국힘', '대통령', '탄핵', '비대위',
    '여가부', '한남', '한녀', '페미', '조국', '총선', '국회', '당대표', '계엄'
]

UNIVERSAL_THEMES = [
    (r'(고양이|강아지|댕댕|냥이|동물|새|참새|햄스터|호랑이|사자|펫|cat|dog)', 'Animals & Pets'),
    (r'(롤|롤잘알|제우스|페이커|스팀|게임|닌텐도|플스|플레이스테이션|lol|esports|gta)', 'Gaming & Esports'),
    (r'(ufc|격투기|축구|손흥민|야구|헬스|헬창|피트니스|스포츠|골프|농구)', 'Sports & Fitness'),
    (r'(amd|엔비디아|애플|아이폰|테슬라|주식|비트코인|코인|ai|챗gpt|gpu)', 'Tech & Stocks'),
    (r'(요리|음식|라면|치킨|피자|배달|식당|맛집|디저트)', 'Food & Cooking'),
    (r'(어이없|레전드|대참사|실시간|근황|반전|실패|사고|웃긴|미친|ㅋㅋㅋ|jpg|gif)', 'WTF & Absurd Fails')
]

def fetch_dcbest_page(page=1):
    url = f'https://m.dcinside.com/board/dcbest?page={page}'
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            content = resp.read().decode('utf-8', errors='ignore')
            tree = html.fromstring(content)
            items = tree.xpath('//ul[contains(@class, "gall-detail-lst")]/li')
            posts = []
            for it in items:
                link = it.xpath('.//a[contains(@class, "lt")]')
                if not link:
                    continue
                href = link[0].get('href', '')
                m = re.search(r'dcbest/(\d+)', href)
                if not m:
                    continue
                post_id = m.group(1)
                
                subj = it.xpath('.//span[contains(@class, "subjectin")]')
                title = subj[0].text_content().strip() if subj else ''
                
                views_raw = it.xpath('.//ul[contains(@class, "ginfo")]/li[contains(text(), "조회")]/text()')
                rec_raw = it.xpath('.//ul[contains(@class, "ginfo")]/li[contains(@class, "up")]//text()')
                nick_raw = it.xpath('.//li[contains(@class, "list-nick")]//text()')
                
                views = int(''.join(re.findall(r'\d+', ''.join(views_raw)))) if views_raw else 0
                rec = int(''.join(re.findall(r'\d+', ''.join(rec_raw)))) if rec_raw else 0
                writer = ''.join(nick_raw).strip() if nick_raw else 'ㅇㅇ'
                
                has_media = bool(it.xpath('.//div[contains(@class, "thum-img")]')) or '이미지' in ''.join(it.xpath('.//span[contains(@class, "subject-add")]//text()'))
                
                desktop_url = f'https://gall.dcinside.com/board/view/?id=dcbest&no={post_id}'

                posts.append({
                    'id': post_id,
                    'title': title,
                    'url': desktop_url,
                    'recommend': rec,
                    'views': views,
                    'writer': writer,
                    'has_media_flag': has_media
                })
            return posts
    except Exception as e:
        print(f"Error fetching page {page}: {e}", file=sys.stderr)
        return []

def filter_and_categorize(post):
    title = post['title']
    
    # 1. Skip political or toxic local drama
    for kw in POLITICS_KEYWORDS:
        if kw in title:
            return None

    # 2. Extract gallery tag e.g. [치갤], [싱갤]
    match = re.match(r'^\[(.*?)\]\s*(.*)$', title)
    if match:
        gallery = match.group(1)
        clean_title = match.group(2)
    else:
        gallery = '기타'
        clean_title = title

    # 3. Check for visual media indicator
    has_media = bool(re.search(r'\.(jpg|png|gif|jpeg|webp)|짤|움짤|만화', title, re.IGNORECASE)) or post.get('has_media_flag', False)

    # 4. Categorize by universal humor appeal
    category = 'General Humor & Memes'
    for pattern, cat_name in UNIVERSAL_THEMES:
        if re.search(pattern, title, re.IGNORECASE):
            category = cat_name
            break

    # Calculate universal appeal score
    score = 10
    if has_media:
        score += 30
    if category in ['Animals & Pets', 'WTF & Absurd Fails', 'Sports & Fitness']:
        score += 25
    elif category in ['Gaming & Esports', 'Tech & Stocks']:
        score += 20
    score += min(post['recommend'], 50)

    return {
        'id': post['id'],
        'gallery': gallery,
        'title': clean_title,
        'original_title': title,
        'category': category,
        'has_media': 'Yes' if has_media else 'No',
        'recommend': post['recommend'],
        'views': post['views'],
        'score': score,
        'url': post['url'],
        'crawled_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

def main():
    print(f"Starting DC Inside crawl at {datetime.datetime.now()}...")
    raw_posts = []
    # Fetch first 5 pages (~150 posts)
    for p in range(1, 6):
        items = fetch_dcbest_page(p)
        raw_posts.extend(items)

    print(f"Total raw posts collected: {len(raw_posts)}")
    curated = []
    seen_ids = set()

    for item in raw_posts:
        if item['id'] in seen_ids:
            continue
        seen_ids.add(item['id'])
        res = filter_and_categorize(item)
        if res:
            curated.append(res)

    # Sort by score descending and take top 100
    curated.sort(key=lambda x: (x['score'], x['recommend'], x['views']), reverse=True)
    top_100 = curated[:100]

    print(f"Curated {len(top_100)} posts for American / Global audience.")

    # Save to CSV
    fieldnames = ['rank', 'id', 'category', 'has_media', 'gallery', 'title', 'recommend', 'views', 'score', 'url', 'crawled_at']
    timestamp_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    history_csv = os.path.join(HISTORY_DIR, f'dcbest_humor_{timestamp_str}.csv')

    for filepath in [LATEST_CSV, history_csv]:
        with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for idx, item in enumerate(top_100, 1):
                row = dict(item)
                row['rank'] = idx
                del row['original_title']
                writer.writerow(row)

    print(f"Saved results to {LATEST_CSV} and {history_csv}")

    # Git commit / push
    try:
        subprocess.run(['git', 'add', '.'], cwd=BASE_DIR, check=True)
        commit_msg = f"Update hourly DC Inside humor crawl ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M')})"
        # Check if there are changes to commit
        status_proc = subprocess.run(['git', 'status', '--porcelain'], cwd=BASE_DIR, capture_output=True, text=True)
        if status_proc.stdout.strip():
            subprocess.run(['git', 'commit', '-m', commit_msg], cwd=BASE_DIR, check=True)
            print("Git commit created.")
            # Check if remote exists
            remotes_proc = subprocess.run(['git', 'remote'], cwd=BASE_DIR, capture_output=True, text=True)
            if 'origin' in remotes_proc.stdout:
                push_proc = subprocess.run(['git', 'push', 'origin', 'main'], cwd=BASE_DIR, capture_output=True, text=True)
                if push_proc.returncode == 0:
                    print("Pushed to GitHub origin main successfully.")
                else:
                    print(f"Git push warning: {push_proc.stderr}", file=sys.stderr)
            else:
                print("No remote 'origin' configured yet. Local commit ready.")
        else:
            print("No changes to commit.")
    except Exception as ge:
        print(f"Git operation note: {ge}", file=sys.stderr)

if __name__ == '__main__':
    main()
