import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
from tqdm import tqdm
from markdownify import markdownify as md
import sys
from dap_auth import get_authenticated_session # 🔑 우리가 만든 인증 모듈
import urllib.parse

# 폴더 설정 (DAP 전용)
BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")
ATTACHMENT_DIR = os.path.join(DATA_DIR, "attachments")
STATUS_FILE = os.path.join(DATA_DIR, "dap_update_status.json") # DAP 전용 상태 파일
DAP_JSON_FILE = os.path.join(DATA_DIR, "dap_notices.json")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(ATTACHMENT_DIR, exist_ok=True)

# 봇 위장용 헤더
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_update_status():
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_update_status(status_dict):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status_dict, f, ensure_ascii=False, indent=4)

def get_dap_notice_content(session, url):
    """게시글 상세 페이지에 들어가서 본문을 마크다운으로 가져오고 '본문 이미지'만 다운로드합니다."""
    try:
        response = session.get(url, headers=HEADERS)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')

            # 1. 본문 텍스트 추출
            content_area = soup.select_one('#CP1_divContents') or soup.select_one('.board-contents')
            markdown_text = md(str(content_area)).strip() if content_area else "본문 태그를 찾을 수 없습니다."

            attachments = []

            # 2. 본문 이미지(포스터, 시간표 등) 다운로드
            if content_area:
                for img in content_area.select('img'):
                    img_src = img.get('src')
                    if img_src:
                        # 상대 경로일 수 있으므로 완전한 주소로 합쳐줍니다.
                        img_download_url = urllib.parse.urljoin(url, img_src)

                        # 파일 이름 꼬이지 않게 특수문자 치환
                        img_file_name = "본문이미지_" + img_download_url.split('/')[-1].replace("?", "_").replace("=", "_")
                        img_file_path = os.path.join(ATTACHMENT_DIR, img_file_name)

                        # 파일이 없으면 다운로드
                        if not os.path.exists(img_file_path):
                            print(f"      🖼️ 본문 이미지 다운로드 시도: {img_file_name}")
                            img_response = session.get(img_download_url, headers=HEADERS)
                            if img_response.status_code == 200:
                                with open(img_file_path, 'wb') as f:
                                    f.write(img_response.content)

                        # OCR 파싱을 위해 attachments 리스트에 추가
                        attachments.append({"file_name": img_file_name, "file_path": img_file_path})

            # 💡 일반 첨부파일(HWP, PDF 등) 다운로드 로직은 제거됨 (RAG 효율 최적화)

            return markdown_text, attachments

    except Exception as e:
        print(f"상세 페이지 크롤링 중 에러: {e}")

    return "내용을 불러올 수 없습니다.", []

def crawl_dap_incremental(session, category_name, mst_id, last_id):
    url = f"https://dap.deu.ac.kr/StdNotice.aspx?NoticeMst={mst_id}&PageNo=1"

    response = session.get(url, headers=HEADERS)
    if response.status_code != 200:
        print(f"[{category_name}] 접속 실패")
        return [], last_id

    soup = BeautifulSoup(response.text, 'html.parser')
    rows = soup.select('table.table-hover tr')

    crawled_data = []
    max_id = last_id

    for row in rows:
        a_tag = row.select_one('td.text-left a')
        if not a_tag: continue

        href = a_tag.get('href')

        # URL에서 글 번호(NoticeNo) 추출
        match = re.search(r'NoticeNo=(\d+)', href)
        article_no = int(match.group(1)) if match else 0

        # 🌟 이미 읽은 과거의 글이라면 패스! (증분 업데이트 핵심)
        if article_no > 0 and article_no <= last_id:
            continue

        max_id = max(max_id, article_no)

        raw_title = a_tag.next_sibling
        title = raw_title.strip() if raw_title else "제목 없음"

        # 날짜 추출 (이전 F12 캡처를 보면 두 번째 text-center에 날짜가 있었습니다)
        td_centers = row.select('td.text-center')
        date_text = td_centers[1].get_text(strip=True) if len(td_centers) > 1 else "날짜없음"

        full_link = f"https://dap.deu.ac.kr/{href}"

        print(f"  [새 글 수집 중] {title}")
        content_text, attachments_list = get_dap_notice_content(session, full_link)
        time.sleep(0.5) # 매너 딜레이

        crawled_data.append({
            "category": f"DAP_{category_name}",
            "title": title,
            "date": date_text,
            "link": full_link,
            "content": content_text,
            "attachments": attachments_list
        })

    return crawled_data, max_id

def save_to_json(new_data):
    if not new_data: return
    existing_data = []
    if os.path.exists(DAP_JSON_FILE):
        with open(DAP_JSON_FILE, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)

    combined_data = new_data + existing_data
    with open(DAP_JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(combined_data, f, ensure_ascii=False, indent=4)
    print(f"\n📁 DAP 데이터 저장 완료! (새로 추가: {len(new_data)}건 / 총 누적: {len(combined_data)}건)")


if __name__ == "__main__":
    print("DAP 로그인 진행 중...")
    auth_session = get_authenticated_session()
    time.sleep(3) # SSO 릴레이 대기

    dap_boards = {"학사공지": "001", "취업공지": "004"}
    status = get_update_status()
    all_new_results = []

    print("\n🚀 DAP 공지사항 크롤링(증분 업데이트) 시작!\n")

    for name, mst_id in dap_boards.items():
        last_id = status.get(name, 0)
        result_data, new_max_id = crawl_dap_incremental(auth_session, name, mst_id, last_id)
        all_new_results.extend(result_data)

        if new_max_id > last_id:
            status[name] = new_max_id

    if all_new_results:
        save_to_json(all_new_results)
        save_update_status(status)
        sys.exit(0)
    else:
        print("\n✨ 새로 올라온 DAP 공지사항이 없습니다.")
        sys.exit(99)