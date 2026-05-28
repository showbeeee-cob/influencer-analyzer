# Instagram + YouTube Influencer Automation

이 프로젝트는 기존 **Instagram Influencer Automation**을 그대로 유지하면서, 동일한 Google Spreadsheet의 **Sheet2**에 **YouTube Influencer Analyzer**를 추가한 자동화 시스템입니다. Sheet1은 기존 Instagram 분석용으로 사용하고, Sheet2는 YouTube 채널 분석용으로 사용합니다.

YouTube 분석은 단순 조회수 수집이 아니라 광고대행사 실무에서 후보 유튜버를 빠르게 선별하기 위한 평가 구조입니다. YouTube Data API로 채널과 최근 영상을 수집하고, 영상 길이 기준으로 Shorts와 Longform을 구분한 뒤 평균 조회수, 평균 댓글, 참여율, 카테고리, 등급, AI 코멘트를 Google Sheets에 자동 입력합니다.

---

## 1. 전체 구조

```txt
instagram_influencer_automation/
├── main.py
├── wsgi.py
├── config.py
├── sheets_db.py
├── analyzer.py
├── apify_scraper.py
├── ai_generator.py
├── youtube_sheets_db.py
├── youtube_scraper.py
├── youtube_analyzer.py
├── requirements.txt
├── .env.example
├── Procfile
├── render.yaml
└── README.md
```

| 파일 | 역할 |
|---|---|
| `main.py` | Flask 서버와 백그라운드 polling loop를 실행합니다. Sheet1 Instagram과 Sheet2 YouTube를 함께 감지합니다. |
| `wsgi.py` | Render의 Gunicorn 실행 진입점입니다. |
| `config.py` | Google Sheets, Apify, Gemini, YouTube API, Render 포트 설정을 중앙 관리합니다. |
| `sheets_db.py` | 기존 Instagram Sheet1 연동 파일입니다. 기존 기능을 유지합니다. |
| `youtube_sheets_db.py` | Sheet2 YouTube 전용 Trigger 감지와 결과 기록을 담당합니다. |
| `youtube_scraper.py` | YouTube Data API로 채널, 최근 영상, 조회수, 댓글, duration을 수집합니다. |
| `youtube_analyzer.py` | Shorts/Longform 기반 등급 계산, 카테고리 추론, Gemini AI 코멘트 생성을 담당합니다. |

---

## 2. Google Sheets 구성

기존 Spreadsheet는 그대로 사용합니다.

```txt
https://docs.google.com/spreadsheets/d/1VBdahTl8s-qzGszqYCm2wrDw0IKC9QoGF-dRLej-o7o/edit?gid=0#gid=0
```

Sheet1은 기존 Instagram 자동화가 사용합니다. Sheet2는 YouTube 분석 전용으로 사용합니다. Sheet2가 없으면 코드가 자동으로 생성하고 헤더를 입력합니다. 다만 초보자라면 직접 Sheet2를 만들고 아래 컬럼을 먼저 입력하는 방식을 권장합니다.

| 열 | 컬럼명 | 설명 |
|---|---|---|
| A | Channel URL | 분석할 YouTube 채널 URL, @핸들 URL, channel ID URL |
| B | Subscribers | 구독자 수 |
| C | Avg Shorts Views | 최근 영상 중 60초 이하 Shorts 평균 조회수 |
| D | Avg Longform Views | 최근 영상 중 60초 초과 Longform 평균 조회수 |
| E | Shorts Count | 분석 대상 최근 영상 중 Shorts 개수 |
| F | Longform Count | 분석 대상 최근 영상 중 Longform 개수 |
| G | Avg Comments | 최근 영상 평균 댓글 수 |
| H | Engagement Rate | 평균 댓글 수를 구독자 수로 나눈 참여율 |
| I | Category | 제목, 설명, 태그 기반 추론 카테고리 |
| J | Grade | 광고대행사 실무형 등급 |
| K | AI Comment | 최대 2문장의 실무형 AI 평가 코멘트 |
| L | Trigger | 체크박스 |
| M | Status | RUNNING, DONE, FAILED |

Sheet2의 L열에는 체크박스를 넣어주세요. Google Sheets에서 `삽입 → 체크박스`를 선택하면 됩니다.

---

## 3. YouTube URL 지원 형식

아래 형식을 지원합니다.

| 입력 예시 | 설명 |
|---|---|
| `https://www.youtube.com/@handle` | YouTube 핸들 URL |
| `@handle` | 핸들만 입력 |
| `https://www.youtube.com/channel/UC...` | Channel ID URL |
| `UC...` | Channel ID만 입력 |
| `https://www.youtube.com/c/channelname` | 커스텀 URL. 검색 기반으로 채널을 해석합니다. |
| `https://www.youtube.com/user/username` | 레거시 사용자 URL. 검색 기반으로 채널을 해석합니다. |

가장 안정적인 형식은 `https://www.youtube.com/@handle` 또는 `https://www.youtube.com/channel/UC...`입니다.

---

## 4. YouTube 분석 기준

영상 구분은 duration 기준입니다.

| 구분 | 기준 |
|---|---|
| Shorts | 60초 이하 |
| Longform | 60초 초과 |

최근 영상 개수는 환경변수 `YOUTUBE_RECENT_VIDEO_LIMIT`로 조정합니다. 기본값은 30개이며 YouTube Data API의 요청량을 고려해 30개를 권장합니다.

Engagement Rate는 다음 방식으로 계산합니다.

```txt
Engagement Rate = 평균 댓글 수 / 구독자 수 × 100
```

YouTube에서는 공개 API에서 모든 영상의 좋아요 수나 쇼츠 피드 내 실제 노출 맥락을 항상 동일하게 해석하기 어렵기 때문에, 이 버전에서는 댓글 기반 참여율을 안정 지표로 사용합니다.

---

## 5. Google Cloud 설정 방법

Google Sheets API와 YouTube Data API를 함께 사용하려면 Google Cloud Console에서 API를 활성화해야 합니다.

1. [Google Cloud Console](https://console.cloud.google.com/)에 접속합니다.
2. 새 프로젝트를 만들거나 기존 프로젝트를 선택합니다.
3. `API 및 서비스 → 라이브러리`로 이동합니다.
4. **Google Sheets API**를 검색해 활성화합니다.
5. **Google Drive API**를 검색해 활성화합니다.
6. **YouTube Data API v3**를 검색해 활성화합니다.

Google Sheets 연동은 서비스 계정이 필요하고, YouTube Data API는 API Key가 필요합니다.

---

## 6. Google Service Account 설정 방법

1. Google Cloud Console에서 `IAM 및 관리자 → 서비스 계정`으로 이동합니다.
2. 서비스 계정을 생성합니다.
3. 생성한 서비스 계정에서 `키 → 키 추가 → 새 키 만들기 → JSON`을 선택합니다.
4. JSON 파일을 다운로드합니다.
5. JSON 안의 `client_email` 값을 복사합니다.
6. Google Sheets 문서에서 `공유` 버튼을 누르고, 해당 `client_email`을 편집자로 초대합니다.

Render에서는 `credentials.json` 파일을 올리는 방식보다 `GOOGLE_SERVICE_ACCOUNT_JSON` 환경변수에 JSON 전체를 한 줄로 넣는 방식을 권장합니다.

로컬에서 JSON을 한 줄로 바꾸려면 다음 명령을 사용하세요.

```bash
python -c "import json; print(json.dumps(json.load(open('service-account.json'))))"
```

출력된 문자열 전체를 Render 환경변수 `GOOGLE_SERVICE_ACCOUNT_JSON` 값으로 넣으면 됩니다.

---

## 7. YouTube API Key 발급 방법

1. Google Cloud Console에서 `API 및 서비스 → 사용자 인증 정보`로 이동합니다.
2. `사용자 인증 정보 만들기 → API 키`를 선택합니다.
3. 생성된 API 키를 복사합니다.
4. Render 환경변수에 `YOUTUBE_API_KEY`로 추가합니다.

운영 안정성을 위해 API Key 제한을 설정하는 것을 권장합니다. `API 제한`에서 **YouTube Data API v3**만 허용하면 됩니다.

---

## 8. .env 설정

로컬 실행 시에는 `.env.example`을 복사해 `.env` 파일을 만들고 값을 채웁니다.

```bash
cp .env.example .env
```

필수 환경변수는 다음과 같습니다.

| 환경변수 | 설명 |
|---|---|
| `GOOGLE_SHEET_URL` | 기존 Google Spreadsheet URL |
| `GOOGLE_WORKSHEET_NAME` | Instagram용 Sheet 이름. 기본값 `Sheet1` |
| `YOUTUBE_WORKSHEET_NAME` | YouTube용 Sheet 이름. 기본값 `Sheet2` |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Google 서비스 계정 JSON 한 줄 문자열 |
| `APIFY_TOKEN` | 기존 Instagram Apify 토큰 |
| `GEMINI_API_KEY` | Gemini AI 코멘트 생성용 API 키 |
| `YOUTUBE_API_KEY` | YouTube Data API 키 |
| `POLLING_INTERVAL_SECONDS` | Google Sheets polling 주기. 기본값 10초 |

---

## 9. Render 배포 방법

Render의 기존 Web Service를 그대로 사용합니다. GitHub 저장소에 변경 파일을 반영한 뒤 재배포하면 됩니다.

Render 설정값은 아래처럼 맞춥니다.

| 항목 | 값 |
|---|---|
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 120 --access-logfile - --error-logfile -` |
| Health Check Path | `/health` |

환경변수에는 기존 Instagram용 값에 더해 아래 값을 추가해야 합니다.

| 환경변수 | 값 |
|---|---|
| `YOUTUBE_API_KEY` | Google Cloud에서 발급한 YouTube Data API Key |
| `YOUTUBE_WORKSHEET_NAME` | `Sheet2` |
| `YOUTUBE_RECENT_VIDEO_LIMIT` | `30` 권장 |
| `YOUTUBE_REQUEST_TIMEOUT_SECONDS` | `20` 권장 |

재배포는 Render Dashboard에서 **Manual Deploy → Clear build cache & deploy**를 선택하는 것이 가장 안전합니다.

---

## 10. 사용 방법

Sheet2에서 A열에 YouTube 채널 URL을 입력하고 L열 체크박스를 체크하면 자동으로 분석됩니다. 시스템은 10초마다 Sheet1과 Sheet2를 확인합니다.

| 단계 | 작업 |
|---|---|
| 1 | Sheet2 A열에 YouTube 채널 URL 입력 |
| 2 | Sheet2 L열 Trigger 체크 |
| 3 | Status가 RUNNING으로 변경됨 |
| 4 | 분석 완료 후 B~K열에 결과 입력 |
| 5 | Status가 DONE으로 변경되고 Trigger가 자동 해제됨 |
| 6 | 오류 발생 시 Status가 FAILED로 변경되고 AI Comment 영역에 오류 메시지가 입력됨 |

---

## 11. 트러블슈팅

| 증상 | 원인 | 해결 방법 |
|---|---|---|
| `gunicorn: command not found` | `requirements.txt`에 gunicorn이 없거나 빌드 캐시 문제 | `requirements.txt` 확인 후 Render에서 `Clear build cache & deploy` 실행 |
| YouTube 행이 FAILED | `YOUTUBE_API_KEY` 누락 또는 API 비활성화 | Render 환경변수와 Google Cloud의 YouTube Data API v3 활성화 확인 |
| 채널을 찾지 못함 | 커스텀 URL 해석 실패 | `@handle` URL 또는 `/channel/UC...` URL 사용 |
| Sheet2가 자동 생성되지 않음 | 서비스 계정 권한 부족 | Google Sheets 공유 설정에서 서비스 계정 이메일을 편집자로 추가 |
| AI Comment가 비어 있음 | Gemini API Key 누락 또는 모델 접근 오류 | `GEMINI_API_KEY`, `GEMINI_MODEL` 확인 |
| Instagram도 같이 FAILED | 기존 `APIFY_TOKEN` 또는 Gemini 설정 누락 | 기존 Instagram 환경변수 유지 여부 확인 |

---

## 12. 주의사항

기존 Instagram 자동화 파일은 삭제하지 않았으며, Sheet1 기반 동작도 유지됩니다. 이번 추가 기능은 Sheet2와 `youtube_*.py` 파일 중심으로 확장되었습니다. Render에서는 하나의 Flask 서버와 하나의 백그라운드 polling loop가 실행되고, 해당 loop 안에서 Sheet1 Instagram과 Sheet2 YouTube를 순서대로 처리합니다.

YouTube Data API는 일일 quota 제한이 있으므로, `YOUTUBE_RECENT_VIDEO_LIMIT`를 너무 크게 설정하지 않는 것이 좋습니다. 기본값 30개는 실무 평가에 필요한 최근 반응을 확인하면서도 요청량을 비교적 낮게 유지하기 위한 설정입니다.
