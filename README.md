# 메이플스토리 디스코드 봇

메이플스토리 캐릭터 정보와 경험치를 조회하는 디스코드 봇입니다.

## 기능
- 캐릭터 정보 조회
- 주간 경험치 그래프
- 월간 경험치 히트맵
- 썬데이메이플 알림
- 환산 정보 링크

## 설치 방법
1. 필요한 패키지 설치:  
```bash
pip install -r requirements.txt
```

2. 환경 변수 설정:
    - `.env` 파일 생성
    - 환경 변수 추가:
    ```
    DISCORD_TOKEN=your_discord_token
    ```

3. 봇 실행:
    ```bash
    python bot.py
    ```

## 명령어
- `!주간 [캐릭터 이름]`: 주간 경험치 그래프 조회
- `!월간 [캐릭터 이름]`: 월간 경험치 히트맵 조회
- `!썬데이메이플`: 썬데이메이플 알림 확인
- `!환산 [캐릭터 이름]`: 환산 정보 링크 조회

## 썬데이메이플 알림
- 매주 금요일 오전 10시 1분(KST)에 알림 발송
- 알림 채널: "메이플" 카테고리의 "봇" 채널          