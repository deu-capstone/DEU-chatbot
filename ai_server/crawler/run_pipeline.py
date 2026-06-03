import requests
import time
import subprocess
import os
import threading
import sys

# ==========================================
# 1. 로딩 애니메이션 함수
# ==========================================
def show_spinner(stop_event, message="처리 중..."):
    spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    i = 0
    while not stop_event.is_set():
        sys.stdout.write(f"\r{spinner[i % len(spinner)]} {message}")
        sys.stdout.flush()
        time.sleep(0.1)
        i += 1
    sys.stdout.write('\r' + ' ' * (len(message) + 4) + '\r')

# ==========================================
# 2. 파이프라인 실행 함수
# ==========================================
def run_step(command, description):
    print(f"\n🚀 [단계 시작] {description}...")
    result = subprocess.run(["python", "-m", command])

    if result.returncode == 0:
        print(f"✅ {description} 완료!")
        return "SUCCESS"
    elif result.returncode == 99:
        return "NO_DATA"
    else:
        print(f"❌ {description} 실패!")
        return "FAIL"

# ==========================================
# 🚀 메인 실행 로직
# ==========================================
def main():
    print("🔔 [자동 업데이트] 전체 파이프라인을 시작합니다.")

    # 1. 크롤링 (대표 홈페이지 단독 진행)
    deu_result = run_step("crawler.deu_notice_crawler", "대표 홈페이지 새 글 크롤링")

    # 예외 처리 1: 크롤링 실패
    if deu_result == "FAIL":
        print("\n❌ 크롤링이 실패했습니다. 파이프라인을 종료합니다.")
        return

    # 예외 처리 2: 새로운 글이 없을 경우
    if deu_result == "NO_DATA":
        print("\n🛑 [조기 종료] 새로운 공지사항이 없으므로 파싱 및 DB 업데이트를 생략합니다.")
        return

    # 2. 첨부파일 파싱 (크롤링이 SUCCESS일 때만 실행됨)
    if run_step("crawler.attachment_parser", "첨부파일 및 이미지 OCR 파싱") != "SUCCESS":
        return

    # 3. 서버 API 호출
    print("\n🔗 [단계 시작] 벡터 DB 업데이트 요청...")

    stop_spinner = threading.Event()
    spinner_thread = threading.Thread(target=show_spinner, args=(stop_spinner, "서버에서 DB를 업데이트하고 있습니다 (잠시만 기다려주세요)..."))

    try:
        spinner_thread.start()
        # 주의: FastAPI 서버가 켜져 있어야 작동합니다!
        response = requests.post("http://127.0.0.1:8000/update_db")
        stop_spinner.set()
        spinner_thread.join()

        if response.status_code == 200:
            res_data = response.json()
            print(f"✅ DB 업데이트 성공! (추가된 청크: {res_data.get('added_chunks', 0)}개)")
        else:
            print(f"❌ DB 업데이트 요청 실패 (코드: {response.status_code})")
    except Exception as e:
        stop_spinner.set()
        spinner_thread.join()
        print(f"❌ 서버 연결 오류: {e} (FastAPI 서버가 켜져 있는지 확인하세요!)")

if __name__ == "__main__":
    main()