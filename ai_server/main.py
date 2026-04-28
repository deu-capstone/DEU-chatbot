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
import os
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

# 2. DB 폴더가 없다면? (처음 실행할 때) -> PDF 읽어서 새로 만들기
else:
    print("📚 DB가 없네요! docs 폴더의 PDF를 읽어 벡터 DB를 구축합니다...")
    loader = PyPDFDirectoryLoader("./docs")
    docs = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    splits = text_splitter.split_documents(docs)

    # DB를 만들면서 './chroma_db' 폴더에 영구 저장합니다.
    vectorstore = Chroma.from_documents(
        documents=splits,
        embedding=OpenAIEmbeddings(),
        persist_directory=DB_DIR
    )
    print("✅ 벡터 DB 로컬 저장 완료!")

retriever = vectorstore.as_retriever()
# =====================================================================

# 3. 데이터 규격 정의
class QuestionRequest(BaseModel):
    question: str

# 4. 프롬프트 세팅 (RAG 전용)
prompt = ChatPromptTemplate.from_template("""
당신은 동의대학교 학사 상담 챗봇입니다. 아래 제공된 [참고 문서]를 바탕으로 학생의 질문에 다정하고 명확하게 답변하세요.
문서에 없는 내용이라면 지어내지 말고 "해당 내용은 규정에서 찾을 수 없습니다"라고 정직하게 답변하세요.

[참고 문서]
{context}

질문: {question}
""")

# 검색된 여러 문서를 하나의 텍스트로 합쳐주는 함수
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

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
    # RAG 체인에 질문을 넣고 답변을 뽑아냄
    result = rag_chain.invoke(request.question)
    return {"answer": result}