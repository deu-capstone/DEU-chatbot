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

    # 크롤링한 JSON 파일 경로
    json_file_path = "./crawler/data/deu_notices.json"

    # JSON 파일 읽기
    with open(json_file_path, "r", encoding="utf-8") as f:
        crawled_data = json.load(f)

    # JSON 데이터를 LangChain Document 객체로 변환
    docs = []
    for item in crawled_data:
        content_text = item.get("content", "본문 내용이 없습니다.")

        doc = Document(
            page_content=item["content"], # 챗봇이 읽고 판단할 진짜 본문 내용
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
답변을 할 때는 내용 설명 후, 반드시 [참고 문서]에 있는 [출처 링크]를 활용하여 "자세한 내용은 [링크]를 참고해 주세요." 형태의 안내를 덧붙이세요.
문서에 없는 내용이라면 지어내지 말고 "해당 내용은 규정에서 찾을 수 없습니다"라고 정직하게 답변하세요.

[참고 문서]
{context}

질문: {question}
""")

# 검색된 여러 문서를 하나의 텍스트로 합쳐주는 함수
def format_docs(docs):
    formatted_texts = []
    for doc in docs:
        text = f"[내용]: {doc.page_content}\n[출처 링크]: {doc.metadata.get('link', '링크 없음')}"
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