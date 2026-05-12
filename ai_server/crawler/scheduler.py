import schedule
import time
from run_pipeline import main as run_pipeline

# 매일 새벽 4시에 업데이트를 수행하도록 설정
schedule.every().day.at("04:00").do(run_pipeline)

# 테스트를 위해 1시간마다 실행하고 싶다면?
# schedule.every(1).hours.do(run_pipeline)

print("⏰ 스케줄러가 시작되었습니다. 매일 새벽 4시에 데이터가 동기화됩니다.")

while True:
    schedule.run_pending()
    time.sleep(60) # 1분마다 체크