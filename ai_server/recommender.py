import json
import re
from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever
from datetime import datetime, timedelta

with open('./crawler/data/deu_notices_parsed.json', 'r', encoding='utf-8') as f:
    notices = json.load(f)

# 1. 기준 날짜 설정 (현재 시점으로부터 6개월 전)
# days=180을 365로 바꾸면 1년치 기준으로 변경할 수 있습니다.
cutoff_date = datetime.now() - timedelta(days=180)

documents = []
for notice in notices:
    date_str = notice.get('date', '') # 예: "2026-05-12"

    try:
        # 문자열(String) 날짜를 파이썬 datetime 객체로 변환 (형식에 맞게 "%Y-%m-%d" 등 수정 필요)
        notice_date = datetime.strptime(date_str, "%Y-%m-%d")

        # 2. 날짜를 비교하여 기준일 이후(최신) 공지만 필터링
        if notice_date >= cutoff_date:
            doc = Document(
                page_content=notice.get('title', ''),
                metadata={
                    'id': notice.get('id'),
                    'link': notice.get('link'),
                    'date': date_str,
                }
            )
            documents.append(doc)

    except ValueError:
        # 날짜가 없거나 형식이 깨진 불량 데이터는 스킵
        continue

print(f"전체 공지 {len(notices)}개 중, 최근 6개월 이내 유효 공지 {len(documents)}개만 추출 완료!")

# ==========================================
# 2. 한국어 맞춤형 토크나이저 정의 (★중요)
# ==========================================
# BM25는 기본적으로 띄어쓰기 기준으로 단어를 쪼갭니다.
# 하지만 한국어는 "장학금은", "장학금을"처럼 조사(은/는/이/가/를)가 붙기 때문에
# 간단한 형태소 분석기나 명사 추출기를 붙여주면 추천 품질이 압도적으로 좋아집니다.
# (여기서는 가장 대중적인 KoNLPy의 Okt를 예시로 들겠습니다. 없다면 아래 주석처리된 기본 split을 쓰셔도 됩니다.)

try:
    from konlpy.tag import Okt
    print("Okt를 이용합니다")
    okt = Okt()
    def korean_tokenizer(text):
        # 텍스트에서 명사만 추출하여 토큰화
        return okt.nouns(text)
except ImportError:
    # KoNLPy가 설치되어 있지 않은 경우 예외 처리 (띄어쓰기 + 특수문자 제거 기준)
    def korean_tokenizer(text):
        print("KoNLPy가 설치되어 있지 않아 기본 토크나이저를 사용합니다. 추천 품질이 떨어질 수 있습니다.")
        clean_text = re.sub(r'[^\w\s]', ' ', text)
        return clean_text.split()

# ==========================================
# 3. BM25 Retriever 초기화
# ==========================================
# 위에서 만든 한국어 토크나이저 함수를 preprocess_func에 넘겨줍니다.
retriever = BM25Retriever.from_documents(
    documents=documents,
    preprocess_func=korean_tokenizer
)

# 추천 개수를 5개로 고정
retriever.k = 5


# ==========================================
# 4. 추천 기능 함수 정의
# ==========================================

def get_recommendations_by_dept(dept_name):
    """ 사용자의 학과명을 쿼리로 전송하여 관련 공지 5개 추천 """
    print(f"🔍 '{dept_name}' 기반 맞춤 공지 추천 중...")
    # BM25 검색 실행
    return retriever.invoke(dept_name)

def get_recommendations_by_history(search_history):
    """ 사용자의 최근 검색 기록 목록을 하나의 문장으로 합쳐 5개 추천 """
    if not search_history:
        return []

    # 검색 기록 배열을 하나의 쿼리 문장으로 변환 ("장학금 수강신청 휴학")
    query = " ".join(search_history)
    print(f"🔍 최근 검색어 관여도('{query}') 기반 공지 추천 중...")

    return retriever.invoke(query)


# ==========================================
# 5. 실전 테스트 및 사용 예시
# ==========================================
if __name__ == "__main__":
    # 가상의 유저 데이터
    user_department = "응용소프트웨어공학과"
    user_search_history = ["국가장학금 신청 기간", "대면 수강신청 변경", "졸업학점 확인"]

    # 1) 학과 추천 공지 사항 출력
    dept_recommendations = get_recommendations_by_dept(user_department)
    print("\n[🎓 학과 맞춤 추천 공지 TOP 5]")
    for i, doc in enumerate(dept_recommendations, 1):
        print(f"{i}. {doc.page_content} (링크: {doc.metadata.get('link', '링크 없음')})")

    print("\n" + "="*50 + "\n")

    # 2) 검색 기록 추천 공지 사항 출력
    history_recommendations = get_recommendations_by_history(user_search_history)
    print("\n[⏱️ 나의 관심사 기반 추천 공지 TOP 5]")
    for i, doc in enumerate(history_recommendations, 1):
        print(f"{i}. {doc.page_content} (링크: {doc.metadata.get('link', '링크 없음')})")