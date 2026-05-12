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
STATUS_FILE = os.path.join(DATA_DIR, "update_status.json") # 상태 저장 파일 경로

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(ATTACHMENT_DIR, exist_ok=True)

# ==========================================
# 1. 업데이트 상태 관리 함수 (마지막 ID 기억하기)
# ==========================================
def get_update_status():
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {} # 파일이 없으면 빈 딕셔너리 반환

def save_update_status(status_dict):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status_dict, f, ensure_ascii=False, indent=4)

# ==========================================
# 2. 본문 및 첨부파일 크롤링 함수
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

            # 본문 이미지 다운로드
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

            # 일반 첨부파일 다운로드
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
# 3. 목록 크롤링 함수 (새 글 필터링 적용)
# ==========================================
def crawl_deu_notice(category, last_id):
    url = f"https://www.deu.ac.kr/www/deu-{category}.do"
    headers = {"User-Agent": "Mozilla/5.0"}

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"페이지 접속 실패! 에러 코드: {response.status_code}")
        return [], last_id

    soup = BeautifulSoup(response.text, 'html.parser')
    subjects = soup.select('.subject')

    crawled_data = []
    max_id = last_id  # 현재 카테고리의 최고 번호를 추적합니다.

    for td_subject in subjects:
        a_tag = td_subject.select_one('a')
        if not a_tag: continue

        title = a_tag.get_text(strip=True)
        link = a_tag.get('href')
        link_url = f"https://www.deu.ac.kr/www/deu-{category}.do{link}"

        # URL에서 articleNo(글 번호)를 숫자로 추출합니다.
        match = re.search(r'articleNo=(\d+)', link)
        article_no = int(match.group(1)) if match else 0

        # 이미 읽은 글이면 수집을 건너뜁니다!
        # (상단 고정 '공지'는 옛날 글일 수 있으므로 break가 아닌 continue를 씁니다)
        if article_no > 0 and article_no <= last_id:
            continue

        # 새 글이라면 최고 번호 갱신
        max_id = max(max_id, article_no)

        tr = td_subject.find_parent('tr')
        date_td = tr.select_one('.data')
        date_text = date_td.get_text(strip=True) if date_td else "날짜없음"

        print(f"\n  [새 글 수집 중] {title}")
        content_text, attachments_list = get_notice_content(link_url)
        time.sleep(0.5)

        crawled_data.append({
            "category": category,
            "title": title,
            "date": date_text,
            "link": link_url,
            "content": content_text,
            "attachments": attachments_list
        })

    return crawled_data, max_id

# ==========================================
# 4. JSON 저장 함수 (기존 데이터에 이어 붙이기)
# ==========================================
def save_to_json(new_data):
    if not new_data:
        return

    file_path = os.path.join(DATA_DIR, "deu_notices.json")
    existing_data = []

    # 기존 데이터가 있으면 불러오기
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)

    # 새 데이터를 리스트 맨 앞(최신순)에 이어 붙입니다.
    combined_data = new_data + existing_data

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(combined_data, f, ensure_ascii=False, indent=4)

    print(f"\n📁 로컬 파일 업데이트 완료! (새로 추가됨: {len(new_data)}건 / 총 누적: {len(combined_data)}건)")


# ==========================================
# 🚀 메인 실행 로직
# ==========================================
if __name__ == "__main__":
    category_list = ["notice", "scholarship", "education", "job"]

    # 1. 어디까지 읽었는지 상태 불러오기
    status = get_update_status()
    all_new_results = []

    print("공지사항 크롤링(증분 업데이트)을 시작합니다...\n")

    for cat in tqdm(category_list, desc="전체 진행률", unit="게시판"):
        # 각 카테고리별 마지막 ID 가져오기 (처음엔 0)
        last_id = status.get(cat, 0)

        # 새 글만 크롤링
        result_data, new_max_id = crawl_deu_notice(cat, last_id)
        all_new_results.extend(result_data)

        # 최고 번호가 갱신되었다면 상태 업데이트
        if new_max_id > last_id:
            status[cat] = new_max_id

    # 2. 새로 수집된 데이터가 있다면 저장하고 상태 파일(update_status.json) 갱신!
    if all_new_results:
        print(f"\n✅ 총 {len(all_new_results)}개의 새로운 공지사항을 찾았습니다!")
        save_to_json(all_new_results)
        save_update_status(status) # 여기서 상태 파일이 생성/갱신됩니다.
        sys.exit(0)  # 0번 신호: "성공했고, 새 데이터도 있음!"
    else:
        print("\n✨ 새로 올라온 공지사항이 없습니다. (최신 상태 유지 중)")
        sys.exit(99) # 99번 신호: "성공했는데, 새 데이터는 없음!"