import requests
from bs4 import BeautifulSoup
import json
import os
import time
from tqdm import tqdm
from markdownify import markdownify as md


# 상세 페이지에 들어가서 본문만 긁어오기
def get_notice_content(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')

            content_area = soup.select_one('.fr-view')

            if content_area:
                # HMTL 덩어리(content_area)를 마크다운 텍스트로 변환
                markdown_text = md(str(content_area))

                # 앞뒤 쓸데없는 공백을 지우고 반환
                return markdown_text.strip()
            else:
                return "본문 내용을 찾을 수 없습니다."

    except Exception as e:
        print(f"본문 크롤링 중 에러 발생: {e}")

    return "내용을 불러올 수 없습니다."

# 1페이지: https://www.deu.ac.kr/www/deu-notice.do?mode=list&&articleLimit=10&article.offset=0
# 2페이지: https://www.deu.ac.kr/www/deu-notice.do?mode=list&&articleLimit=10&article.offset=1

def crawl_deu_notice(category):
    # 1. 크롤링할 대상 URL (동의대 홈페이지 공지사항 예시 주소, 실제 주소로 변경 필요)
    category = category
    url = "https://www.deu.ac.kr/www/deu-" + category + ".do"

    # 2. 봇(Bot) 차단을 막기 위해 일반 브라우저인 척하는 헤더 추가
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    response = requests.get(url, headers=headers)

    # 정상적으로 페이지를 불러왔는지 확인 (200이면 성공)
    if response.status_code == 200:
        # 3. BeautifulSoup을 이용해 HTML 구조를 파이썬이 읽기 쉽게 변환
        soup = BeautifulSoup(response.text, 'html.parser')

        # 1. 제목이 들어있는 <td> 태그들을 모두 찾습니다.
        subjects = soup.select('.subject')

        crawled_data = []
        for td_subject in subjects:
            # 2. 부모 태그인 <tr>(게시글 한 줄 전체)을 찾아냅니다.
            tr = td_subject.find_parent('tr')

            # 3. 제목과 링크 가져오기
            a_tag = td_subject.select_one('a')
            if not a_tag:
                continue  # 혹시 빈 줄이 있으면 건너뜀

            title = a_tag.get_text(strip=True)
            link = a_tag.get('href')
            link_url = f"https://www.deu.ac.kr/www/deu-{category}.do{link}"

            # 4. 작성일자 가져오기
            date_td = tr.select_one('.data')

            # 날짜 태그를 찾았다면 텍스트를 뽑고, 아니면 '날짜없음' 처리
            date_text = date_td.get_text(strip=True) if date_td else "날짜없음"

            # 본문 내용 가져오기
            content_text = get_notice_content(link_url)
            time.sleep(0.5)

            crawled_data.append({
                "category": category,
                "title": title,
                "date": date_text,
                "link": link_url,
                "content": content_text
            })
        # 너무 빨리 끝나면 로딩 바를 볼 수 없으니 0.5초 time sleep(크롤링 봇 차단 방지용으로도 좋음)
        time.sleep(0.5)
        return crawled_data
    else:
        print(f"페이지 접속 실패! 에러 코드: {response.status_code}")
        return []


def save_to_json(data):
    if not data:
        print("저장할 데이터가 없습니다.")
        return

    # 저장할 data 폴더 경로 설정 (없으면 자동으로 만듦)
    save_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(save_dir, exist_ok=True)

    file_path = os.path.join(save_dir, "deu_notices.json")

    # JSON 파일로 저장
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    print(f"크롤링 완료! 총 {len(data)}개의 데이터가 '{file_path}'에 저장되었습니다.")


# 이 스크립트를 직접 실행했을 때만 작동하도록 하는 안전장치
if __name__ == "__main__":
    # notice: 일반, scholarship: 장학, education: 교육/모집, job: 채용
    category_list = ["notice", "scholarship", "education", "job"]

    all_results = []

    print("공지사항 크롤링을 시작합니다...")
    for cat in tqdm(category_list, desc="크롤링 진행률", unit="게시판"):
        result_data = crawl_deu_notice(cat)
        all_results.extend(result_data)

    print(f"\n✅ 크롤링 완료! 총 {len(all_results)}개의 데이터를 수집했습니다.")

    # ==========================================
    print("=== 📄 수집된 데이터 목록 ===")
    for i, item in enumerate(all_results, 1):
        # enumerate(..., 1)은 1번부터 숫자를 세어주는 기능입니다.
        print(f"[{item['category'].upper()}] {item['title']}  📅 [{item['date']}]")
        print(f"    🔗 {item['link']}")
        print(f"    📝 {item['content'][:80]}...")
    print("=============================\n")

    save_to_json(all_results)
