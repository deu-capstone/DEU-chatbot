import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
from tqdm import tqdm
import urllib.parse
import sys

# 🌟 메인 크롤러(deu_notice_crawler.py)에서 함수와 설정값들을 불러옵니다!
from deu_notice_crawler import (
    get_notice_content,
    save_to_json,
    BOARD_CONFIGS,
    extract_article_id,
    STATUS_FILE
)

# ==========================================
# 과거 목록 크롤링 (2026.02 이후 데이터만 수집 / 사이트별 페이징 처리 분기)
# ==========================================
def crawl_history(category):
    crawled_data = []
    config = BOARD_CONFIGS[category]
    offset = 0
    page = 1
    max_id = 0
    seen_article_nos = set()

    while True:
        # 사이트 타입별로 페이징 URL 다르게 생성
        if config["type"] == "main":
            # 기존 홈페이지 & 학사공지 방식 (offset 사용)
            url = f"{config['base_url']}?mode=list&articleLimit=10&article.offset={offset}"
        else:
            # 플러스센터 취업공지 방식 (page 사용)
            url = f"{config['base_url']}?mst_cd=004&page={page}"

        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"페이지 접속 실패! 에러 코드: {response.status_code}")
            break

        soup = BeautifulSoup(response.text, 'html.parser')

        # 목록 선택자 분기
        if config["type"] == "main":
            subjects = soup.select('.subject')
        else:
            subjects = soup.select('.subject') or soup.select('td.title') or soup.select('td.left')

        if not subjects:
            break

        print(f"\n[{category}] {page}페이지 탐색 중...")
        valid_items_in_page = 0

        for td_subject in subjects:
            a_tag = td_subject.select_one('a')
            if not a_tag: continue

            link = a_tag.get('href')
            if link.startswith('http'):
                link_url = link
            else:
                link_url = urllib.parse.urljoin(config["base_url"], link)

            # 가져온 extract_article_id 함수 사용
            article_no = extract_article_id(link)

            if article_no and (article_no in seen_article_nos):
                continue
            seen_article_nos.add(article_no)

            tr = td_subject.find_parent('tr')
            if tr:
                date_td = tr.select_one('.data') or tr.select_one('.date') or tr.find('td', text=re.compile(r'\d{4}-\d{2}-\d{2}'))
                date_text = date_td.get_text(strip=True) if date_td else "1900-01-01"
            else:
                date_text = "1900-01-01"

            clean_date = re.sub(r'[^0-9]', '', date_text)
            date_num = int(clean_date[:8]) if len(clean_date) >= 8 else 99999999

            # 2026년 2월 1일 이전 글인지 확인
            if date_num < 20260201:
                continue

            valid_items_in_page += 1
            title = a_tag.get_text(strip=True)
            max_id = max(max_id, article_no)

            print(f"  [수집] {title} ({date_text})")
            content_text, attachments_list = get_notice_content(link_url, board_type=config["type"])
            time.sleep(0.5)

            crawled_data.append({
                "category": category,
                "title": title,
                "date": date_text,
                "link": link_url,
                "content": content_text,
                "attachments": attachments_list
            })

        if valid_items_in_page == 0:
            print(f"  [종료] {page}페이지의 남은 모든 글이 2026년 2월 이전 글이거나 중복입니다.")
            break

        offset += 10
        page += 1

    return crawled_data, max_id

# ==========================================
# 🚀 메인 실행 로직 (1회용)
# ==========================================
if __name__ == "__main__":
    category_list = list(BOARD_CONFIGS.keys())

    status = {}
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            status = json.load(f)

    all_new_results = []

    print("📢 1회용 과거 데이터(2026.02 ~ 현재) 크롤링을 시작합니다...\n")

    for cat in tqdm(category_list, desc="전체 진행률", unit="게시판"):
        result_data, new_max_id = crawl_history(cat)
        all_new_results.extend(result_data)

        if new_max_id > status.get(cat, 0):
            status[cat] = new_max_id

    if all_new_results:
        print(f"\n✅ 수집 완료! 총 {len(all_new_results)}개의 공지사항을 찾았습니다.")

        # 가져온 save_to_json 함수 사용 (중복 검사 내장)
        save_to_json(all_new_results)

        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False, indent=4)
        print("✅ deu_update_status.json 파일이 성공적으로 설정되었습니다. 이제부터는 기존 스크립트를 사용하세요!")

        sys.exit(0)
    else:
        print("\n✨ 조건에 맞는 데이터가 없습니다.")
        sys.exit(99)