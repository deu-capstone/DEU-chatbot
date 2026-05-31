from selenium import webdriver
from selenium.webdriver.common.by import By
import requests
import os
import time
from dotenv import load_dotenv

def get_authenticated_session():
    # 1. 환경변수에서 ID/PW 가져오기
    load_dotenv()
    user_id = os.getenv("DEU_ID")
    user_pw = os.getenv("DEU_PW")

    if not user_id or not user_pw:
        raise ValueError("환경 변수에 DEU_ID와 DEU_PW가 설정되지 않았습니다.")

    # 2. 크롬 드라이버 실행 (추후 백그라운드 실행을 위해 options 추가 가능)
    options = webdriver.ChromeOptions()
    # options.add_argument('--headless') # 개발 완료 후 주석 해제하면 브라우저 창이 안 뜹니다.
    driver = webdriver.Chrome(options=options)

    try:
        # 3. DAP 로그인 페이지 접속
        driver.get("https://dap.deu.ac.kr/sso/login.aspx")

        # 4. 아이디/비밀번호 입력 및 로그인 버튼 클릭 (실제 태그 ID 확인 필요)
        driver.find_element(By.ID, "id").send_keys(user_id)
        driver.find_element(By.ID, "pw").send_keys(user_pw)
        driver.find_element(By.ID, "btn-login").click()

        # 로그인 완료 대기 (예: 로그인 후 나타나는 특정 요소가 로드될 때까지)
        print("SSO 통합 로그인 처리 중... (약 3초 대기)")
        time.sleep(3)

        # 5. 로그인된 세션 쿠키 추출
        cookies = driver.get_cookies()

        # 6. Requests 세션 객체 생성 및 쿠키 주입
        session = requests.Session()
        for cookie in cookies:
            session.cookies.set(cookie['name'], cookie['value'])

        return session

    finally:
        # 볼일이 끝난 셀레니움 브라우저는 닫아줍니다.
        driver.quit()

if __name__ == "__main__":
    session = get_authenticated_session()