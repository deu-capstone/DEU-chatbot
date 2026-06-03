import json
import os
from fastapi import FastAPI
from pydantic import BaseModel
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from dotenv import load_dotenv
from pydantic import BaseModel

# .env 파일에 있는 변수들을 파이썬 시스템 환경 변수로 불러옵니다.
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

# 1. API 키 설정
os.environ["OPENAI_API_KEY"] = openai_api_key

# 2. FastAPI 서버 객체 생성
app = FastAPI(title="동의대 RAG 챗봇 서버")

# =====================================================================
# [DB 로드 또는 생성 로직]
# =====================================================================
DB_DIR = "./chroma_db"  # DB를 저장할 폴더 이름

# 읽어올 파싱 데이터 파일 목록 (대표 홈페이지 단독)
JSON_FILES = [
    "./crawler/data/deu_notices_parsed.json"
]

# 1. 만약 기존에 만들어둔 DB 폴더가 있다면? -> 1초 만에 불러오기
if os.path.exists(DB_DIR):
    print("📁 기존에 만들어둔 벡터 DB를 빠르게 불러옵니다...")
    vectorstore = Chroma(
        persist_directory=DB_DIR,
        embedding_function=OpenAIEmbeddings()
    )

# 2. DB 폴더가 없다면? (처음 실행할 때) -> JSON 읽어서 새로 만들기
else:
    print("📚 DB가 없네요! 크롤링한 JSON 데이터를 읽어 벡터 DB를 구축합니다...")

    crawled_data = []

    # JSON 파일을 순회하며 데이터를 합칩니다.
    for file_path in JSON_FILES:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                crawled_data.extend(json.load(f))
        else:
            print(f"⚠️ [경고] {file_path} 파일을 찾을 수 없습니다. 건너뜁니다.")

    if not crawled_data:
        # 파일이 없으면 빈 DB 생성
        print("⚠️ [경고] 파싱된 JSON 파일이 하나도 없습니다! 일단 '빈 DB'로 서버를 실행합니다.")
        print("⚠️ 서버가 켜진 상태에서 'python run_pipeline.py'를 실행해 DB를 채워주세요!")
        vectorstore = Chroma(
            embedding_function=OpenAIEmbeddings(),
            persist_directory=DB_DIR
        )
    else:
        # JSON 데이터를 LangChain Document 객체로 변환
        docs = []
        for item in crawled_data:
            combined_text = f"제목: {item.get('title', '제목 없음')}\n\n내용:\n{item.get('content', '본문 내용이 없습니다.')}"

            doc = Document(
                page_content=combined_text, # 챗봇이 읽고 판단할 진짜 본문 내용
                metadata={
                    "category": item.get("category", "기타"),
                    "title": item.get("title", "제목 없음"),
                    "date": item.get("date", "날짜 없음"),
                    "link": item.get("link", "링크 없음")
                }
            )
            docs.append(doc)

        print(f"총 {len(docs)}개의 공지사항을 Document로 변환했습니다. 청크 분할을 시작합니다...")

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=300)
        splits = text_splitter.split_documents(docs)

        # DB를 만들면서 './chroma_db' 폴더에 영구 저장합니다.
        vectorstore = Chroma.from_documents(
            documents=splits,
            embedding=OpenAIEmbeddings(),
            persist_directory=DB_DIR
        )
        print("✅ JSON 데이터 기반 벡터 DB 로컬 저장 완료!")


# 검색 결과 개수 10개
retriever = vectorstore.as_retriever(search_kwargs={"k": 10})
# =====================================================================

# 3. 데이터 규격 정의
class QuestionRequest(BaseModel):
    question: str

# 4. 프롬프트 세팅 (RAG 전용)
prompt = ChatPromptTemplate.from_template("""
당신은 동의대학교 학사 상담 챗봇입니다. 아래 제공된 [참고 문서]를 바탕으로 학생의 질문에 다정하고 명확하게 답변하세요.

답변을 작성할 때 다음 규칙을 반드시 지켜주세요:
1. 정보의 출처가 명확하도록 [참고 문서]의 [제목]과 [작성일]을 자연스럽게 언급해 주세요. (예: "2026년 4월 20일에 올라온 [ㅇㅇ공지사항]에 따르면~")
2. 내용 설명 후, 반드시 "자세한 내용은 [링크]를 참고해 주세요." 형태의 안내를 덧붙이세요.
3. 문서에 없는 내용이라면 지어내지 말고 "해당 내용은 규정에서 찾을 수 없습니다"라고 정직하게 답변하세요.

[참고 문서]
{context}

질문: {question}
""")

# 검색된 여러 문서를 하나의 텍스트로 합쳐주는 함수
def format_docs(docs):
    formatted_texts = []
    for doc in docs:
        text = f"[제목]: {doc.metadata.get('title', '제목 없음')}\n[내용]: {doc.page_content}\n[작성일]: {doc.metadata.get('date', '날짜 없음')}\n[출처 링크]: {doc.metadata.get('link', '링크 없음')}"
        formatted_texts.append(text)
    return "\n\n---\n\n".join(formatted_texts)

# 5. RAG 체인 연결 (검색 -> 프롬프트 -> LLM -> 텍스트 출력)
llm = ChatOpenAI(model="gpt-4o-mini")
rag_chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
)

# 6. 통신 API 엔드포인트
@app.post("/ask")
async def ask_ai(request: QuestionRequest):
    # 🔍 검색기가 실제로 가져온 문서들을 미리 확인해봅니다.
    search_docs = retriever.invoke(request.question)
    print(f"\n--- [검색된 문서 조각 개수: {len(search_docs)}] ---")
    for i, doc in enumerate(search_docs):
        print(f"[{i+1}번 조각 일부]: {doc.page_content[:100]}...")

    result = rag_chain.invoke(request.question)
    return {"answer": result}

# =====================================================================
# 7. 벡터 DB 수동/자동 업데이트 API (증분 업데이트 지원)
# =====================================================================
@app.post("/update_db")
async def update_database():
    print("🔄 DB 업데이트 요청을 받았습니다! 최신 데이터를 읽어옵니다...")

    crawled_data = []

    # 🌟 파일 목록을 순회하며 대표 홈페이지 데이터를 읽어옵니다.
    for file_path in JSON_FILES:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                crawled_data.extend(json.load(f))
        else:
            print(f"⚠️ [경고] {file_path} 파일을 찾을 수 없습니다. 건너뜁니다.")

    if not crawled_data:
        return {"error": "파싱된 JSON 파일을 하나도 찾을 수 없습니다."}

    # 1. 업데이트 전 기존 DB의 조각(Chunk) 개수 확인
    old_count = vectorstore._collection.count()

    # 2. JSON 데이터를 Document 객체로 변환
    docs = []
    for item in crawled_data:
        combined_text = f"제목: {item.get('title', '제목 없음')}\n\n내용:\n{item.get('content', '본문 내용이 없습니다.')}"
        doc = Document(
            page_content=combined_text,
            metadata={
                "category": item.get("category", "기타"),
                "title": item.get("title", "제목 없음"),
                "date": item.get("date", "날짜 없음"),
                "link": item.get("link", "링크 없음")
            }
        )
        docs.append(doc)

    # 3. 청크 분할
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=300)
    splits = text_splitter.split_documents(docs)

    # 4. 핵심: 중복 저장을 막기 위한 '고유 ID' 생성
    ids = []
    chunk_counters = {}
    for split in splits:
        link = split.metadata["link"]
        chunk_counters[link] = chunk_counters.get(link, 0) + 1
        chunk_id = f"{link}_{chunk_counters[link]}"
        ids.append(chunk_id)

    # 5. DB에 덮어쓰기 (Upsert)
    vectorstore.add_documents(documents=splits, ids=ids)

    # 6. 업데이트 후 늘어난 개수 계산
    new_count = vectorstore._collection.count()
    added_count = new_count - old_count

    print(f"✅ DB 업데이트 완료! (새로 추가된 데이터 조각: {added_count}개)")
    return {
        "message": "DB 업데이트가 성공적으로 완료되었습니다.",
        "before_count": old_count,
        "after_count": new_count,
        "added_chunks": added_count
    }

# =====================================================================
# 8. 벡터 DB (의미 기반) 맞춤형 추천 API
# ========================================== ===========================
class RecommendRequest(BaseModel):
    department: str = ""
    history: list[str] = []

@app.post("/recommend")
async def get_recommendations(request: RecommendRequest):
    print(f"💡 [추천 요청] 학과: {request.department}, 검색기록: {request.history}")

    query = ""
    # 1. 프롬프트 엔지니어링: AI가 문맥을 더 잘 찾도록 질문을 예쁘게 포장합니다.
    if request.department:
        query = f"{request.department} 학과 대학생에게 유용한 장학금, 취업, 학사일정, 특강 관련 공지사항"
    elif request.history:
        history_str = " ".join(request.history)
        query = f"다음 키워드와 관련된 유용한 공지사항: {history_str}"

    if not query:
        return {"recommendations": []}

    # 2. 벡터 DB에서 의미상 가장 가까운 조각 15개를 가져옵니다.
    # (같은 공지사항에서 여러 조각이 나올 수 있으므로 넉넉하게 가져옵니다)
    search_results = vectorstore.similarity_search(query, k=15)

    unique_recommendations = []
    seen_links = set()

    # 3. 중복 제거 작업: 같은 공지사항(링크)은 한 번만 추천 리스트에 넣습니다.
    for doc in search_results:
        link = doc.metadata.get("link", "")
        title = doc.metadata.get("title", "제목 없음")

        if link not in seen_links:
            unique_recommendations.append({
                "title": title,
                "link": link
            })
            seen_links.add(link)

        # 정확히 상위 5개만 모이면 멈춥니다.
        if len(unique_recommendations) >= 5:
            break

    return {"recommendations": unique_recommendations}