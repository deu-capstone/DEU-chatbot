import json
import os
import fitz  # PyMuPDF 라이브러리의 이름입니다.
import subprocess
import pandas as pd
import re
import pytesseract  # OCR 엔진 연결
from PIL import Image  # 이미지 처리
import zipfile
import tempfile
from tqdm import tqdm

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# ==========================================
# 📄 1. PDF 텍스트 추출 함수
# ==========================================
def extract_text_from_pdf(file_path):
    text = ""
    try:
        doc = fitz.open(file_path)
        for page in doc:
            text += page.get_text() + "\n"
        doc.close()
    except Exception as e:
        print(f"  [PDF 에러] {file_path}: {e}")
    return text.strip()


# ==========================================
# 🇰🇷 2. HWP 텍스트 추출 함수
# ==========================================
def extract_text_from_hwp(file_path):
    try:
        # 명령어 방식을 'hwp5txt' 직접 호출로 변경해 봅니다.
        result = subprocess.run(
            ["hwp5txt", file_path],
            capture_output=True,
            text=True,
            encoding='utf-8'
        )

        # 정상적으로 추출되었다면 텍스트 반환
        if result.returncode == 0:
            clean_text = result.stdout.strip()
            return clean_text
        else:
            print(f"\n❌ [HWP 변환 실패] {file_path}")
            print(f"👉 실패 원인: {result.stderr.strip()}")
            return ""

    except FileNotFoundError:
        print("\n❌ [HWP 시스템 에러] 'hwp5txt' 명령어를 찾을 수 없습니다. (라이브러리 설치 문제)")
        return ""
    except Exception as e:
        print(f"\n❌ [HWP 시스템 에러] 알 수 없는 에러: {e}")
        return ""


# ==========================================
# 📊 3. 엑셀 텍스트 추출 함수
# ==========================================
def extract_text_from_excel(file_path):
    try:
        # 엑셀의 모든 시트(Sheet)를 다 읽어옵니다.
        dfs = pd.read_excel(file_path, sheet_name=None)
        text = ""

        for sheet_name, df in dfs.items():
            # 비어있는 칸(NaN)을 빈 문자열로 처리
            df = df.fillna("")
            # 데이터프레임을 문자열로 변환 (AI가 읽기 좋게)
            sheet_text = df.to_string(index=False)
            text += f"\n[시트명: {sheet_name}]\n{sheet_text}\n"

        return text.strip()
    except Exception as e:
        print(f"\n  [Excel 에러] {file_path}: {e}")
        return ""

# ==========================================
# 🖼️ 4. 이미지 텍스트 추출 함수 (Tesseract OCR 사용)
# ==========================================
def extract_text_from_image(file_path):
    try:
        # 이미지를 엽니다.
        img = Image.open(file_path)

        # 🌟 Tesseract 엔진에게 한글과 영어 텍스트를 모두 읽어달라고 시킵니다.
        extracted_text = pytesseract.image_to_string(img, lang='kor+eng')

        # 정규표현식 필터를 적용하여 외계어(바이너리 찌꺼기) 전부 삭제!
        clean_text = re.sub(r'[^가-힣ㄱ-ㅎㅏ-ㅣa-zA-Z0-9\s\.\,\-\(\)\[\]\:\/\<\>\%\*]', '', extracted_text)

        # 쓸데없는 빈 줄들을 하나로 깔끔하게 압축합니다.
        final_text = re.sub(r'\n+', '\n', clean_text).strip()
        return final_text

    except Exception as e:
        print(f"\n  [Image 에러] {file_path}: {e}")
        return ""

# ==========================================
# 🗂️ 5. ZIP 압축 파일 텍스트 추출 함수
# ==========================================
def extract_text_from_zip(file_path):
    extracted_text = ""
    try:
        # 안전하게 작업하기 위해 '임시 폴더(temp_dir)'를 만듭니다.
        # (with문이 끝나면 컴퓨터가 알아서 폴더를 통째로 싹 지워줍니다)
        with tempfile.TemporaryDirectory() as temp_dir:

            # 1. 임시 폴더에 압축 풀기
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            # 2. 임시 폴더 안의 모든 파일을 싹 뒤집니다. (폴더 안에 폴더가 있어도 다 찾음)
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    ext_file_path = os.path.join(root, file)
                    file_name = file.lower()
                    text = ""

                    # 3. 확장자에 맞춰서 우리가 만들어둔 함수들을 재사용합니다!
                    if file_name.endswith(".pdf"):
                        text = extract_text_from_pdf(ext_file_path)
                    elif file_name.endswith(".hwp"):
                        text = extract_text_from_hwp(ext_file_path)
                    elif file_name.endswith(".xlsx") or file_name.endswith(".xls"):
                        text = extract_text_from_excel(ext_file_path)
                    elif file_name.endswith((".jpg", ".jpeg", ".png")):
                        text = extract_text_from_image(ext_file_path)

                    # 4. 뽑아낸 텍스트가 있다면, 어떤 파일에서 나왔는지 꼬리표를 달아 이어 붙입니다.
                    if text.strip():
                        extracted_text += f"\n\n--- [ZIP 내 압축해제 파일: {file}] ---\n{text}"

        return extracted_text.strip()

    except Exception as e:
        print(f"\n  [ZIP 에러] {file_path}: {e}")
        return ""

# ==========================================
# 🚀 6. 메인 파싱 파이프라인
# ==========================================
def parse_attachments():
    # 어제 만든 JSON 파일 위치
    input_json_path = os.path.join(os.path.dirname(__file__), "data", "deu_notices.json")

    # 텍스트가 추가되어 새롭게 저장될 JSON 파일 위치
    output_json_path = os.path.join(os.path.dirname(__file__), "data", "deu_notices_parsed.json")

    # 1. 파일 열기
    if not os.path.exists(input_json_path):
        print("❌ deu_notices.json 파일이 없습니다. 먼저 크롤링을 진행해 주세요!")
        return

    with open(input_json_path, "r", encoding="utf-8") as f:
        notices = json.load(f)

    print(f"총 {len(notices)}개의 공지사항을 검사합니다...")

    # 2. 공지사항을 하나씩 돌면서 첨부파일 확인
    for notice in tqdm(notices, desc="첨부파일 파싱 진행률"):
        attachments = notice.get("attachments", [])

        for att in attachments:
            file_path = att.get("file_path")
            file_name = att.get("file_name", "").lower()

            if not file_path or not os.path.exists(file_path):
                continue

            extracted_text = ""

            # 확장자에 따라 알맞은 추출기 사용
            if file_name.endswith(".pdf"):
                extracted_text = extract_text_from_pdf(file_path)
            elif file_name.endswith(".hwp"):
                extracted_text = extract_text_from_hwp(file_path)
            elif file_name.endswith(".xlsx") or file_name.endswith(".xls"):
                extracted_text = extract_text_from_excel(file_path)
            elif file_name.endswith(".jpg") or file_name.endswith(".jpeg") or file_name.endswith(".png"):
                extracted_text = extract_text_from_image(file_path)
            elif file_name.endswith(".zip"):
                extracted_text = extract_text_from_zip(file_path)
            else:
                continue

            # 3. 추출된 텍스트가 있다면, 기존 본문(content) 맨 아래에 예쁘게 이어 붙입니다!
            if extracted_text:
                notice["content"] += f"\n\n--- [첨부파일 내용: {file_name}] ---\n{extracted_text}"

    # 4. 파싱이 끝난 새로운 데이터를 JSON으로 저장
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(notices, f, ensure_ascii=False, indent=4)

    print(f"\n✅ 파싱 완료! 결과물이 '{output_json_path}'에 저장되었습니다.")


if __name__ == "__main__":
    parse_attachments()
