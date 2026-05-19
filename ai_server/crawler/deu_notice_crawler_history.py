import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
from tqdm import tqdm
from markdownify import markdownify as md
import urllib.parse
import sys

# 폴더 설정
BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")
ATTACHMENT_DIR = os.path.join(DATA_DIR, "attachments")
STATUS_FILE = os.path.join(DATA_DIR, "update_status.json")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(ATTACHMENT_DIR, exist_ok=True)

# ==========================================
# 1. 본문 및 첨부파일 크롤링 함수
# ==========================================
def get_notice_content(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')

            content_area = soup.select_one('.fr-view') or soup.select_one('.con')
            markdown_text = md(str(content_area)).strip() if content_area else "본문 내용을 찾을 수 없습니다."

            attachments = []

            if content_area:
                for img in content_area.select('img'):
                    img_src = img.get('src')
                    if img_src:
                        img_download_url = urllib.parse.urljoin(url, img_src)
                        img_file_name = "본문이미지_" + img_download_url.split('/')[-1].replace("?", "_").replace("=", "_")
                        img_file_path = os.path.join(ATTACHMENT_DIR, img_file_name)

                        if not os.path.exists(img_file_path):
                            print(f"      🖼️ 본문 이미지 다운로드 중: {img_file_name}")
                            img_response = requests.get(img_download_url, headers=headers)
                            if img_response.status_code == 200:
                                with open(img_file_path, 'wb') as f:
                                    f.write(img_response.content)

                        attachments.append({"file_name": img_file_name, "file_path": img_file_path})

            file_area = soup.select_one('.file')
            if file_area:
                for a_tag in file_area.select('a'):
                    file_name = a_tag.get_text(strip=True)
                    file_href = a_tag.get('href')

                    if not file_href or file_href == "#" or "첨부파일" in file_name:
                        continue

                    download_url = urllib.parse.urljoin(url, file_href)
                    safe_file_name = file_name.replace("/", "_").replace("\\", "_")
                    file_path = os.path.join(ATTACHMENT_DIR, safe_file_name)

                    if not os.path.exists(file_path):
                        print(f"      ⬇️ 첨부파일 다운로드 중: {safe_file_name}")
                        file_response = requests.get(download_url, headers=headers)
                        if file_response.status_code == 200:
                            with open(file_path, 'wb') as f:
                                f.write(file_response.content)

                    attachments.append({"file_name": safe_file_name, "file_path": file_path})

            return markdown_text, attachments
    except Exception as e:
        print(f"본문/첨부파일 크롤링 중 에러 발생: {e}")

    return "내용을 불러올 수 없습니다.", []

# ==========================================
# 2. 과거 목록 크롤링 (2026.02 이후 데이터만 수집)
# ==========================================
def crawl_history(category):
    crawled_data = []
    offset = 0
    page = 1
    max_id = 0
    seen_article_nos = set()  # 중복 방지를 위한 글 번호를 저장할 세트

    while True:
        url = f"https://www.deu.ac.kr/www/deu-{category}.do?mode=list&articleLimit=10&article.offset={offset}"
        headers = {"User-Agent": "Mozilla/5.0"}

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"페이지 접속 실패! 에러 코드: {response.status_code}")
            break

        soup = BeautifulSoup(response.text, 'html.parser')
        subjects = soup.select('.subject')

        if not subjects:
            break

        print(f"\n[{category}] {page}페이지(offset={offset}) 탐색 중...")
        valid_items_in_page = 0

        for td_subject in subjects:
            a_tag = td_subject.select_one('a')
            if not a_tag: continue

            link = a_tag.get('href')
            link_url = f"https://www.deu.ac.kr/www/deu-{category}.do{link}"

            # URL 뒷부분이 페이지마다 바뀌더라도 절대 변하지 않는 글 번호 추출
            match = re.search(r'articleNo=(\d+)', link)
            article_no = int(match.group(1)) if match else 0

            # 글 번호가 0이 아니면서, 이미 확인한 글 번호(고정 공지)라면 패스!
            if article_no and (article_no in seen_article_nos):
                continue
            seen_article_nos.add(article_no)

            tr = td_subject.find_parent('tr')
            date_td = tr.select_one('.data')
            date_text = date_td.get_text(strip=True) if date_td else "1900-01-01"

            # 2026년 2월 1일 이전 글인지 확인
            clean_date = re.sub(r'[^0-9]', '', date_text)
            date_num = int(clean_date[:8]) if len(clean_date) >= 8 else 99999999

            if date_num < 20260201:
                continue

            valid_items_in_page += 1

            title = a_tag.get_text(strip=True)

            # 상태 기록을 위한 최고 번호 수집
            max_id = max(max_id, article_no)

            print(f"  [수집] {title} ({date_text})")
            content_text, attachments_list = get_notice_content(link_url)
            time.sleep(0.5) # 서버 부하 방지용 딜레이

            crawled_data.append({
                "category": category,
                "title": title,
                "date": date_text,
                "link": link_url,
                "content": content_text,
                "attachments": attachments_list
            })

        # 페이지 내 '새로 발견한 일반 글' 중 2026년 2월 이전 글밖에 없다면 종료
        if valid_items_in_page == 0:
            print(f"  [종료] {page}페이지의 남은 모든 글이 2026년 2월 이전 글이거나 중복입니다. 탐색을 종료합니다.")
            break

        offset += 10
        page += 1

    return crawled_data, max_id

# ==========================================
# 3. JSON 저장 (중복 방지)
# ==========================================
def save_to_json(new_data):
    if not new_data:
        return

    file_path = os.path.join(DATA_DIR, "deu_notices.json")
    existing_data = []

    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)

    existing_urls = {item['link'] for item in existing_data}
    unique_new_data = [item for item in new_data if item['link'] not in existing_urls]

    combined_data = unique_new_data + existing_data

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(combined_data, f, ensure_ascii=False, indent=4)

    print(f"\n📁 로컬 파일 업데이트 완료! (실제 추가됨: {len(unique_new_data)}건 / 총 누적: {len(combined_data)}건)")

# ==========================================
# 🚀 메인 실행 로직 (1회용)
# ==========================================
if __name__ == "__main__":
    category_list = ["notice", "scholarship", "education", "job"]

    # 기존 상태 파일이 있다면 불러오기 (없으면 새로 생성됨)
    status = {}
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            status = json.load(f)

    all_new_results = []

    print("📢 1회용 과거 데이터(2026.02 ~ 현재) 크롤링을 시작합니다...\n")

    for cat in tqdm(category_list, desc="전체 진행률", unit="게시판"):
        result_data, new_max_id = crawl_history(cat)
        all_new_results.extend(result_data)

        # 수집된 글 중 가장 번호가 높은 것을 내일 쓸 스크립트를 위해 저장해둠
        if new_max_id > status.get(cat, 0):
            status[cat] = new_max_id

    # 최종 결과 저장 및 상태 업데이트
    if all_new_results:
        print(f"\n✅ 수집 완료! 총 {len(all_new_results)}개의 공지사항을 찾았습니다.")
        save_to_json(all_new_results)

        # 내일 구동할 증분 스크립트를 위해 상태 파일 갱신
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False, indent=4)
        print("✅ update_status.json 파일이 성공적으로 설정되었습니다. 이제부터는 기존 스크립트를 사용하세요!")

        sys.exit(0)
    else:
        print("\n✨ 조건에 맞는 데이터가 없습니다.")
        sys.exit(99)