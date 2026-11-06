# 🎓 [동의대학교 맞춤형 학사 상담 챗봇]

> **팀명:** [FourInt(포인트)]  
> **구성원:** [팀장: 여태영, 팀원: 정석호, 김호현, 차승현]

# 유튜브 링크

## 시연 영상

- [동의대학교 맞춤형 학사 상담 챗봇 시연 영상](https://youtu.be/8UcXSupeDmc)

## 개인 프로젝트 결과 보고서(영상)

- [여태영](https://youtu.be/GfCQqsqogH8)
- [정석호](https://youtu.be/LzRJAhYZcyo)
- [김호현](https://youtu.be/kurwiM9kILM)
- [차승현](https://youtu.be/q5LnnLi8OpU)

## 1. 프로젝트 개요

- **한 줄 요약:** 동의대학교 학생들을 위한 학사 상담 및 맞춤형 공지사항 추천 챗봇 시스템입니다.
- **상세 설명:**
  - **목적:** 동의대학교 학생들이 학사 관련 질문에 빠르게 답변을 얻고, 개인 맞춤형 공지사항을 추천받을 수 있도록 지원하는 챗봇 시스템 개발
  - **주요 기능:**
    1. **학사 상담 챗봇:** 학생들의 학사 관련 질문에 대한 실시간 답변 제공 (예: 수강 신청, 졸업 요건, 학점 계산 등)
    2. **맞춤형 공지사항 추천:** 학생의 관심사와 학과에 맞는 공지사항을 자동으로 추천
    3. **RAG 기반 정보 검색:** 최신 학사 정보를 웹 크롤링 및 RAG 기술을 활용하여 제공

```
├── ai_server/               # AI 및 데이터 처리 서버 (Python, FastAPI / RAG 및 웹 크롤링)
├── main_server/             # 메인 백엔드 서버 (Java, Spring Boot / 웹 서비스 및 API 구현)
├── docs/                    # 프로젝트 문서 및 자료
└── README.md                # 레포지토리 메인 안내
```

## 2. 핵심 기능 및 특징 (Key Features)

### 1. 동의대 공지사항 크롤링 파이프라인

- **과거 데이터 구축:** 2026년 2월 1일 이후 작성된 일반·장학·학사·취업·교육/모집·채용 등 총 6개 카테고리의 공지사항을 수집합니다. 본문 텍스트와 함께 본문 내 이미지를 로컬에 다운로드하여 `deu_notices.json`으로 관리합니다.
- **이미지 텍스트 추출 (OCR):** Tesseract OCR과 정규표현식을 활용하여 다운로드된 본문 이미지에서 텍스트를 추출하고 노이즈를 필터링합니다. 추출된 텍스트는 기존 본문과 병합하여 `deu_notices_parsed.json`으로 저장됩니다.
- **신규 데이터 증분 수집:** `deu_update_status.json`에 게시판별 최신 글 번호를 기록하여, 이후에는 새롭게 등록된 게시글만 스마트하게 추적하여 수집합니다.

### 2. RAG 기반 맞춤형 학사 안내 챗봇

- **벡터 데이터베이스 구축:** 파싱된 JSON 데이터를 LangChain의 `RecursiveCharacterTextSplitter`로 분할한 뒤, OpenAI 임베딩을 통해 벡터화하여 로컬 Chroma DB에 저장합니다. 고유 ID 기반의 Upsert 로직으로 중복 없이 증분 업데이트를 지원합니다.
- **출처 기반 질의응답 (Anti-Hallucination):** 사용자의 질문과 가장 관련성이 높은 문서를 검색한 후 `gpt-4o-mini` 모델을 통해 답변을 생성합니다. 프롬프트 엔지니어링을 통해 답변 내에 **[공지사항 제목], [작성일], [출처 링크]**를 반드시 명시하도록 하여 환각 현상을 차단합니다.
- **문맥 기반 맞춤형 추천:** 사용자의 소속 학과 및 이전 검색 기록(히스토리)을 기반으로 맞춤형 쿼리를 생성합니다. 이를 통해 학과 맞춤형 공지사항과 학생 관심사 맞춤형 공지사항을 각각 최대 5개까지 중복 없이 필터링하여 선제적으로 제안합니다.
- **자동화 파이프라인:** `run_pipeline.py` 스크립트 하나로 `[최신 글 크롤링 ➡️ 이미지 OCR 파싱 ➡️ 벡터 DB 업데이트 API 호출]` 프로세스를 일괄 처리합니다.

---

## 3. 설치 및 실행 방법 (Installation & Setup)

### 사전 요구사항 (Prerequisites)

1. **DB 환경:** MongoDB (로컬 또는 클러스터 서버 구동 필요)
2. **외부 프로그램 설치 (필수):** Tesseract-OCR이 시스템의 다음 경로에 설치되어 있어야 합니다.
   - `C:\Program Files\Tesseract-OCR\tesseract.exe`

### 환경 설정 (Environment Variables)

**1. AI 서버 (.env)**
`ai_server/` 폴더 내에 `.env` 파일을 생성하고 아래 내용을 입력합니다.

```env
OPENAI_API_KEY=your-openai-api-key-here
```

**2. 메인 백엔드 서버 (application.properties)**
`main_server/src/main/resources/` 경로에 `application.properties` 파일을 생성하고 MongoDB 접속 정보를 입력합니다.

```properties
spring.mongodb.uri=your-mongodb-uri-here
```

**3. 프론트엔드 구글 로그인 설정**
발급받은 구글 OAuth 2.0 클라이언트 ID를 `index.html` 파일 내 GOOGLE_CLIENT_ID 값에 넣어줍니다.

### 실행 순서 (Execution Steps)

**단계 1: 패키지 설치 및 초기 데이터베이스 구축**
Tesseract OCR 및 환경 변수 세팅이 완료되었다면 아래 명령어를 순서대로 실행하여 과거 데이터를 수집하고 벡터 DB를 구축합니다.

```Bash
# 1. AI 서버 폴더로 이동 및 필수 라이브러리 설치
cd ai_server
pip install -r requirements.txt

# 2. 2026년 2월 이후 과거 데이터 최초 크롤링 진행
python deu_notice_crawler_history.py

# 3. 다운로드된 본문 이미지의 텍스트 추출 (OCR) 및 병합 작업 수행
python attachment_parser.py
```

**단계 2: 서버 구동**
초기 데이터 구축이 완료되면 각 서버를 실행합니다.

- **AI 서버 실행(FastAPI)**

```Bash
cd ai_server
uvicorn main:app --reload
```

- **메인 웹 서버 실행(Sping Boot)**
  IDE(IntelliJ IDEA 등)에서 MainServerApplication.java 파일을 찾아 실행(Run)합니다.

## 4. 기술 스택 (Tech Stack)

- **1. Development Languages & Frameworks**
  - **Backend (Main Server)**
    - Language: Java
    - Framework: Spring Boot
    - Role: 메인 웹 서버 개발, 웹 서비스 제공, 회원 인증 및 맞춤형 추천 로직 제어
  - **AI & Data Pipeline Server**
    - Language: Python
    - Framework: FastAPI, LangChain
    - Role: AI 서버 및 크롤러 개발, RAG 파이프라인 구축, 검색기 및 LLM 오케스트레이션, 벡터 검색 API 제공
- **2. Database**
  - NoSQL DB: MongoDB - 유저 정보 및 챗봇 대화 이력 저장
  - Vector DB: ChormaDB - 크롤링된 공지사항 임베딩 데이터 저장 및 관리
- **3. AI / Libraries**
  - LLM API: OpenAI GPT-4o-mini - RAG 답변 생성 및 검색어 임베딩 활용
  - OCR & Crawler: Tesseract OCR / BeautifulSoup4 - 공지사항 수집 및 이미지 내 텍스트 추출
- **4. Development Tools**
  - IDE: IntelliJ IDEA (with Python Plugin) - Java Spring Boot, Python FastAPI, 크롤링 배치 프로그램 통합 환경 개발
  - DB GUI: MongoDB Compass - NoSQL 데이터 상태 및 컬렉션 모니터링
- **5. Collaboration & Configuration Management**
  - Version Control: Git & GitHub - 소스코드 버전 관리 및 개발 협업
  - Documentation: Notion - 프로젝트 자료 정리, 회의록 문서화 및 개발 내용 작성
