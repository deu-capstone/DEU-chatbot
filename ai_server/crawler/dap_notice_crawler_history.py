import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
from tqdm import tqdm
import sys
from dap_notice_crawler import get_dap_notice_content, save_to_json, save_update_status, STATUS_FILE, HEADERS
from dap_auth import get_authenticated_session

def crawl_dap_history(session, category_name, mst_id):
    crawled_data = []
    page = 1
    max_id = 0
    seen_article_nos = set()

    while True:
        # 🌟 페이지 번호(PageNo)를 1, 2, 3... 올려가며 접속합니다.
        url = f"https://dap.deu.ac.kr/StdNotice.aspx?NoticeMst={mst_id}&PageNo={page}"

        response = session.get(url, headers=HEADERS)
        if response.status_code != 200:
            break

        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.select('table.table-hover tr')

        if len(rows) == 0:
            break # 더 이상 게시글이 없으면 종료

        print(f"\n[{category_name}] {page}페이지 탐색 중...")
        valid_items_in_page = 0

        for row in rows:
            a_tag = row.select_one('td.text-left a')
            if not a_tag: continue

            href = a_tag.get('href')
            match = re.search(r'NoticeNo=(\d+)', href)
            article_no = int(match.group(1)) if match else 0

            # 고정 공지사항 중복 방지
            if article_no in seen_article_nos:
                continue
            seen_article_nos.add(article_no)

            max_id = max(max_id, article_no)

            raw_title = a_tag.next_sibling
            title = raw_title.strip() if raw_title else "제목 없음"

            td_centers = row.select('td.text-center')
            date_text = td_centers[1].get_text(strip=True) if len(td_centers) > 1 else "1900.01.01"

            # 🌟 날짜 비교 (2026.05.27 -> 20260527 변환)
            clean_date = date_text.replace(".", "")
            date_num = int(clean_date) if clean_date.isdigit() else 99999999

            if date_num < 20260201:
                continue # 2026년 2월 이전 글은 건너뜁니다.

            valid_items_in_page += 1
            full_link = f"https://dap.deu.ac.kr/{href}"

            print(f"  [수집] {title} ({date_text})")
            content_text, attachments_list = get_dap_notice_content(session, full_link)
            time.sleep(0.5)

            crawled_data.append({
                "category": f"DAP_{category_name}",
                "title": title,
                "date": date_text,
                "link": full_link,
                "content": content_text,
                "attachments": attachments_list
            })

        # 이번 페이지에서 유효한 글(2026.02 이후)이 0개였다면 과거로 너무 온 것이므로 종료!
        if valid_items_in_page == 0:
            print(f"  [종료] {page}페이지부터는 2026년 2월 이전 글입니다. 탐색을 종료합니다.")
            break

        page += 1

    return crawled_data, max_id

if __name__ == "__main__":
    print("DAP 로그인 진행 중...")
    auth_session = get_authenticated_session()
    time.sleep(3)

    dap_boards = {"학사공지": "001", "취업공지": "004"}
    status = {}
    all_new_results = []

    print("\n📢 DAP 과거 데이터(2026.02 ~ 현재) 1회성 크롤링을 시작합니다...\n")

    for name, mst_id in dap_boards.items():
        result_data, new_max_id = crawl_dap_history(auth_session, name, mst_id)
        all_new_results.extend(result_data)
        status[name] = new_max_id

    if all_new_results:
        save_to_json(all_new_results)
        save_update_status(status)
        print("✅ 초기 데이터 수집 및 상태 파일 생성이 완료되었습니다.")
    else:
        print("\n✨ 조건에 맞는 데이터가 없습니다.")