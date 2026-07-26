# 배포 가이드 (수강생용)

이 대시보드를 본인 GitHub·Streamlit Cloud 계정으로 그대로 배포하는 방법입니다. BigQuery 접근 권한이 되는 사람도, 안 되는 사람도 **똑같이 아래 순서만 따라 하면 정상적으로 배포됩니다.**

## 왜 이런 구조인가

이 대시보드의 "상담원 관점: 직원만족도와 고객 경험" 섹션은 BigQuery를 직접 조회합니다. 그런데:

- Streamlit Community Cloud에는 여러분의 로컬 GCP 로그인 정보(ADC)가 없어서, 별도 인증 수단이 없으면 이 섹션에서 에러가 납니다.
- BigQuery용 서비스 계정 키를 새로 만들려면 조직 정책(`iam.disableServiceAccountKeyCreation`) 때문에 막히는 경우가 있는데, **계정마다 이 정책을 스스로 풀 수 있는지 여부가 다릅니다.**

그래서 이 앱은 아래처럼 동작하도록 만들어져 있습니다:

1. 배포 환경에 BigQuery 인증 정보가 있으면 → **라이브 데이터**로 조회
2. 없으면 → 미리 내려받아 둔 **로컬 스냅샷**(`data/agents_snapshot.csv`, `data/agent_consultations_snapshot.csv`)으로 자동 대체

어느 쪽이든 화면 상단에 배지로 어떤 데이터를 보고 있는지 항상 표시됩니다. **BigQuery 키를 못 만들어도 배포에는 전혀 문제가 없습니다.**

| 배지 | 뜻 |
|---|---|
| 🟡 **스냅샷** | `data/agents_snapshot.csv` 로 팀 필터·교육이수 비교가 작동. **현재 상태** |
| ⚪ **데이터 없음** | 스냅샷 파일이 없을 때. 팀 필터가 `전체` 하나로 비활성되고 07·08만 전체 기준으로 표시됨. 오류가 아니라 데이터 없음을 알리는 정상 상태 |
| 🟢 **라이브** | BigQuery 직접 조회. **현재 앱에는 미구현** — 배포 환경에 인증을 넣어도 🟡 로 동작합니다 |

## 1. 사전 준비

- GitHub 계정
- Streamlit Community Cloud 계정 (share.streamlit.io, GitHub 계정으로 로그인)
- (선택) BigQuery `project1_day1` 데이터셋 조회 권한이 있는 Google 계정

## 2. 로컬에서 실행해보기

```
pip install -r requirements.txt
streamlit run app.py
```

- BigQuery 접근 권한이 있고 `gcloud auth application-default login`으로 로그인되어 있다면 → "상담원 관점" 섹션이 🟢 라이브로 뜹니다.
- 없다면 → 자동으로 🟡 스냅샷으로 뜹니다. **둘 다 정상입니다.**

## 3. (선택) 본인 데이터로 스냅샷 새로 만들기

`data/agents_snapshot.csv`는 2026-07-26에 뽑아둔 스냅샷입니다(`agent_consultations_snapshot.csv` 는 사용하지 않습니다). 본인이 BigQuery에 접근 가능하고 최신 스냅샷으로 갱신하고 싶다면:

```python
from google.cloud import bigquery
import pandas as pd

PROJECT = "skilful-gantry-491911-h5"   # 본인 프로젝트 ID로 변경
DATASET = "project1_day1"
client = bigquery.Client(project=PROJECT)

agent_query = f"""
WITH agent_csat AS (
  SELECT c.agent_id, AVG(s.csat) AS avg_csat
  FROM `{PROJECT}.{DATASET}.consultations` c
  JOIN `{PROJECT}.{DATASET}.satisfaction` s ON c.consult_id = s.consult_id
  WHERE c.agent_id IS NOT NULL
  GROUP BY c.agent_id
)
SELECT a.agent_id, a.team, a.overtime_hours_avg, a.agent_satisfaction, ac.avg_csat
FROM `{PROJECT}.{DATASET}.agents` a
JOIN agent_csat ac ON a.agent_id = ac.agent_id
"""

consult_query = f"""
SELECT c.agent_id, a.team, a.training_completed_yn, c.is_recontact, s.csat
FROM `{PROJECT}.{DATASET}.consultations` c
JOIN `{PROJECT}.{DATASET}.satisfaction` s ON c.consult_id = s.consult_id
JOIN `{PROJECT}.{DATASET}.agents` a ON c.agent_id = a.agent_id
"""

client.query(agent_query).result().to_dataframe().to_csv("data/agents_snapshot.csv", index=False, encoding="utf-8-sig")
client.query(consult_query).result().to_dataframe().to_csv("data/agent_consultations_snapshot.csv", index=False, encoding="utf-8-sig")
```

`app.py` 상단의 `SNAPSHOT_DATE` 값도 오늘 날짜로 함께 바꿔주세요. **이 단계는 건너뛰어도 배포에는 지장 없습니다.**

## 4. GitHub에 올리기

```
git init
git add .
git commit -m "Initial commit"
```

GitHub CLI가 있다면:
```
gh repo create <본인계정>/customer-churn-dashboard --public --source=. --remote=origin --push
```
없다면 GitHub 웹에서 새 저장소를 만들고 안내되는 명령어로 push하면 됩니다.

## 5. Streamlit Community Cloud 배포

1. https://share.streamlit.io 접속 → GitHub 계정으로 로그인
2. **"Create app"** → **"Deploy a public app from GitHub"**
3. Repository: `<본인계정>/customer-churn-dashboard`, Branch: `main`, Main file path: `app.py`
4. **Deploy 누르기 전에 "Advanced settings" 클릭 → Python version을 3.12로 선택** (중요, 아래 트러블슈팅 참고)
5. **Deploy**

## 6. (선택) BigQuery 라이브 연결하고 싶다면

본인 계정에 BigQuery 서비스 계정 키를 만들 수 있는 권한이 있다면:

1. GCP 콘솔 → IAM 및 관리자 → 서비스 계정 → 키 추가 → JSON
   - "조직 정책으로 키 생성이 차단됨" 에러가 뜨면, 본인 계정이 그 정책을 바꿀 수 있는지 IAM 및 관리자 → 조직 정책에서 확인 (바꿀 수 없다면 **이 단계는 건너뛰고 3번 스냅샷 방식으로 그대로 진행하면 됩니다** — 아무 문제 없습니다)
   - 서비스 계정에 `BigQuery 데이터 뷰어`, `BigQuery 작업 사용자` 역할 부여 필요
2. Streamlit Cloud → Manage app → Settings → Secrets에 아래 형식으로 붙여넣기(JSON 키 파일의 값을 그대로 옮김):

```toml
[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "..."
client_email = "..."
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
universe_domain = "googleapis.com"
```

3. Save → 자동 재시작 → "상담원 관점" 섹션이 🟢 라이브로 바뀌는지 확인

## 트러블슈팅

| 증상 | 원인 | 해결 |
|---|---|---|
| 배포 로그가 `Using Python 3.14.x environment`에서 멈추거나 매우 느림 | Streamlit Cloud가 강제하는 최신 Python과 `requirements.txt`의 구버전 패키지 간 wheel 미지원 | 앱 **삭제 후 재배포**하면서 Advanced settings에서 Python 3.12 선택 (`runtime.txt`는 현재 Streamlit 버그로 무시되니 반드시 이 화면에서 지정) |
| `ModuleNotFoundError: statsmodels` | `trendline="ols"`가 내부적으로 statsmodels를 쓰는데 requirements.txt에 빠짐 | `requirements.txt`에 `statsmodels==0.14.6` 추가 확인 |
| "상담원 관점" 섹션에서 서비스 계정 키 관련 에러 | 조직 정책으로 키 생성이 막혀 있음 | 무시해도 됨 — 자동으로 🟡 스냅샷 모드로 전환되어 배포에는 지장 없음 |
| BigQuery Secrets 등록했는데도 안 됨 | 서비스 계정에 `BigQuery Job User` 역할 누락 | IAM에서 역할 추가 후 Reboot |
