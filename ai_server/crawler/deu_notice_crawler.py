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
STATUS_FILE = os.path.join(DATA_DIR, "deu_update_status.json")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(ATTACHMENT_DIR, exist_ok=True)

# ==========================================
# 0. 게시판별 URL 및 환경 설정
# ==========================================
BOARD_CONFIGS = {
    "notice": {"base_url": "https://www.deu.ac.kr/www/deu-notice.do", "domain": "https://www.deu.ac.kr", "type": "main"},
    "scholarship": {"base_url": "https://www.deu.ac.kr/www/deu-scholarship.do", "domain": "https://www.deu.ac.kr", "type": "main"},
    "education": {"base_url": "https://www.deu.ac.kr/www/deu-education.do", "domain": "https://www.deu.ac.kr", "type": "main"},
    "job": {"base_url": "https://www.deu.ac.kr/www/deu-job.do", "domain": "https://www.deu.ac.kr", "type": "main"},

    # 1. 새로 추가된 학사 공지 (기존 메인과 구조 동일)
    "gra_notice": {"base_url": "https://www.deu.ac.kr/www/gra-notice.do", "domain": "https://www.deu.ac.kr", "type": "main"},

    # 2. 새로 추가된 플러스센터 취업공지 (다른 구조)
    "pluscenter_job": {
        "base_url": "https://deu.ac.kr/pluscenter/sub04_09.do",
        "domain": "https://deu.ac.kr",
        "params": "?mst_cd=004",
        "type": "pluscenter"
    }
}

def get_update_status():
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_update_status(status_dict):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status_dict, f, ensure_ascii=False, indent=4)

def extract_article_id(link):
    """URL에서 게시글 번호를 유연하게 추출합니다."""
    # articleNo, idx, no, seq 등의 파라미터에서 숫자 추출
    match = re.search(r'(?:articleNo|idx|no|seq|board_no)=(\d+)', link, re.IGNORECASE)
    if match:
        return int(match.group(1))

    # 위 패턴이 없으면 링크 내의 가장 마지막 숫자 뭉치를 반환
    numbers = re.findall(r'\d+', link)
    if numbers:
        return int(numbers[-1])
    return 0

# ==========================================
# 1. 본문 및 첨부파일 크롤링 함수
# ==========================================
def get_notice_content(url, board_type="main"):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')

            # 사이트 타입에 따라 본문 영역을 다르게 탐색
            if board_type == "main":
                content_area = soup.select_one('.fr-view') or soup.select_one('.con')
            else:
                # 플러스센터의 경우 클래스명이 다를 수 있으므로 범용적인 컨테이너 추가 탐색
                content_area = soup.select_one('.fr-view') or soup.select_one('.con') or soup.select_one('.board_view') or soup.select_one('.view_content')

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

            return markdown_text, attachments
    except Exception as e:
        print(f"본문/첨부파일 크롤링 중 에러 발생: {e}")

    return "내용을 불러올 수 없습니다.", []

# ==========================================
# 2. 목록 크롤링 함수 (새 글 필터링 적용)
# ==========================================
def crawl_deu_notice(category, last_id):
    config = BOARD_CONFIGS[category]
    url = config["base_url"]
    if "params" in config:
        url += config["params"]

    headers = {"User-Agent": "Mozilla/5.0"}

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"페이지 접속 실패! 에러 코드: {response.status_code}")
        return [], last_id

    soup = BeautifulSoup(response.text, 'html.parser')

    # 1. 리스트 탐색: 사진에 나온 <td class="subject">를 정상적으로 찾습니다.
    subjects = soup.select('.subject')

    crawled_data = []
    max_id = last_id

    for td_subject in subjects:
        a_tag = td_subject.select_one('a')
        if not a_tag: continue

        title = a_tag.get_text(strip=True)
        link = a_tag.get('href')
        # 추출되는 link 형태: "?mode=view&mst_cd=004&no=171428&page=1&srSearchKey=&srSearchVal="

        # 2. 절대경로/상대경로 분기 처리
        if link.startswith('http'):
            link_url = link
        else:
            # 베이스 URL(https://deu.ac.kr/pluscenter/sub04_09.do) 뒤에
            # 사진의 상대 경로(?mode=view...)를 안전하게 이어 붙입니다.
            link_url = urllib.parse.urljoin(config["base_url"], link)

        # 3. 유연한 게시글 번호 추출: 'no=171428'에서 171428을 정확히 뽑아냅니다.
        article_no = extract_article_id(link)

        if article_no > 0 and article_no <= last_id:
            continue

        max_id = max(max_id, article_no)

        # 4. 날짜 추출: 사진에 나온 <td class="data">2026-06-02</td>를 찾아 텍스트를 추출합니다.
        tr = td_subject.find_parent('tr')
        if tr:
            date_td = tr.select_one('.data')
            date_text = date_td.get_text(strip=True) if date_td else "날짜없음"
        else:
            date_text = "날짜없음"

        print(f"\n  [새 글 수집 중] {title}")
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

    return crawled_data, max_id

# ==========================================
# 4. JSON 저장 함수 (반환값 추가)
# ==========================================
def save_to_json(new_data):
    if not new_data:
        return 0 # 추가된 데이터 0개

    file_path = os.path.join(DATA_DIR, "deu_notices.json")
    existing_data = []

    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)

    # 중복 걸러내기
    existing_urls = {item['link'] for item in existing_data}
    unique_new_data = [item for item in new_data if item['link'] not in existing_urls]

    # 진짜 새 글이 없으면 0 반환
    if not unique_new_data:
        return 0

    combined_data = unique_new_data + existing_data

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(combined_data, f, ensure_ascii=False, indent=4)

    print(f"\n📁 로컬 파일 업데이트 완료! (실제 추가됨: {len(unique_new_data)}건)")

    # 🌟 추가된 '진짜' 새 글의 개수를 반환합니다.
    return len(unique_new_data)


# ==========================================
# 🚀 메인 실행 로직
# ==========================================
if __name__ == "__main__":
    category_list = list(BOARD_CONFIGS.keys())
    status = get_update_status()
    all_new_results = []

    print("공지사항 크롤링(증분 업데이트)을 시작합니다...\n")

    for cat in tqdm(category_list, desc="전체 진행률", unit="게시판"):
        last_id = status.get(cat, 0)
        result_data, new_max_id = crawl_deu_notice(cat, last_id)
        all_new_results.extend(result_data)

        if new_max_id > last_id:
            status[cat] = new_max_id

    # 🌟 여기가 핵심 수정 포인트입니다!
    if all_new_results:
        # save_to_json이 반환한 '실제 추가된 개수'를 받습니다.
        actual_added = save_to_json(all_new_results)

        if actual_added > 0:
            print(f"\n✅ 진짜 새로운 공지사항 {actual_added}개를 DB에 넘깁니다!")
            save_update_status(status)
            sys.exit(0) # 0번 신호: 파이프라인 계속 진행!
        else:
            print("\n✨ 수집된 글이 있었지만 모두 중복 공지입니다. (조기 종료)")
            save_update_status(status)
            sys.exit(99) # 99번 신호: 중복뿐이니 파이프라인 중단!

    else:
        print("\n✨ 새로 올라온 공지사항이 없습니다. (최신 상태 유지 중)")
        sys.exit(99)


# ==========================================
# 🚀 메인 실행 로직
# ==========================================
if __name__ == "__main__":
    # 설정된 모든 게시판 카테고리 로드
    category_list = list(BOARD_CONFIGS.keys())

    status = get_update_status()
    all_new_results = []

    print("공지사항 크롤링(증분 업데이트)을 시작합니다...\n")

    for cat in tqdm(category_list, desc="전체 진행률", unit="게시판"):
        last_id = status.get(cat, 0)
        result_data, new_max_id = crawl_deu_notice(cat, last_id)
        all_new_results.extend(result_data)

        if new_max_id > last_id:            status[cat] = new_max_id

    if all_new_results:
        print(f"\n✅ 총 {len(all_new_results)}개의 새로운 공지사항을 찾았습니다!")
        save_to_json(all_new_results)
        save_update_status(status)
        sys.exit(0)
    else:
        print("\n✨ 새로 올라온 공지사항이 없습니다. (최신 상태 유지 중)")
        sys.exit(99)