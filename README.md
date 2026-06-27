# VIP 등급 수불 대시보드

VIP 등급 **수불(승급·유지·하락/유입·이탈)·전환·활성도**를 월별로 진단하는 Streamlit 대시보드.
**모든 수치는 원본 RAW 데이터에서 직접 계산**한다(사용자 수동 집계 시트는 참고만, 숫자는 재계산).

## 계산 모델 (중요)
원본 RAW는 한 이동을 '유입'(목적지 기준)과 '이탈'(출발지 기준)로 **이중 기록**한다.
→ 그대로 합치면 이동 인원이 2배가 된다(원본 `이동_방향성` 시트가 그런 케이스).
이 대시보드는 **'유입'+'유지' 행만** 써서 단일기입 전이행렬 `M[FROM(전월)→TO(당월)]` 을 만들고
모든 지표를 일관되게 파생한다(인구 보존: ΣFROM = ΣTO).

- 유지(g)=M[g,g] · 유입(g)=Σ_{f≠g}M[f,g] · 이탈(g)=Σ_{t≠g}M[g,t]
- 유지율=유지/전월유효, 전월유효=유지+이탈
- 승급/하락=등급 RANK 비교, 전환(일반→VIP)=Σ M[일반→VIP]

## 등급 체계 (상위→하위)
`SP > PT > GD > SV > BK > PP > RD`
- **VIP**: BK·SV·GD·PT·SP / **일반**: PP·RD
- **SP·PT는 연1회(매년 1/1) 고정 등급**이라 월 단위 VIP 유지율 집계에서 **제외**(= VIP core: BK·SV·GD).
  활성도 차트 등에는 선택 시 표시.

## 섹션
핵심 요약 · **수불 한눈에(승급/유지/하락 + 등급별 유입·이탈 밸런스)** · 등급별 수불 추세 ·
VIP vs 일반 · 일반→VIP 전환 & 내부 대사 · 이동 방향성(히트맵·Sankey·유입출처/이탈행선지) ·
DAU/MAU 활성도 교차. 사이드바에 **목차(앵커 이동)** 제공.

## 데이터 갱신 — 2가지
1. **사이드바 업로드(권장)**: 원본 `VIP_등급수불 xlsx` 를 그대로 사이드바에 올리면
   앱이 `RAW_입력` 시트를 읽어 git push 없이 즉시 재계산. (RAW_입력만 갱신돼 있으면 됨)
2. **CSV 커밋**: 아래 실행 → `data/raw_grade.csv` 재생성 → commit/push
   ```powershell
   ./convert.ps1 -Src "원본 xlsx 경로"
   ```
   `convert.ps1` 은 원본을 Excel COM 으로 메모리에서 읽어(시트는 A1='CURR_STD_YM' 헤더로 탐지)
   `data/raw_grade.csv` 1개를 UTF-8(BOM)로 추출. **원본 xlsx 는 커밋하지 않음**(`.gitignore`).

## RAW 컬럼
`CURR_STD_YM, GRAD_STATUS(유입/유지/이탈), GRAD_MOVEMENT(승급/하락/-), CURR_GRAD_GB,
CURR_NLINE_MEM_GRAD_CD/NM, PREV_GRAD_GB, PREV_NLINE_MEM_GRAD_CD/NM, CUST_CNT, MAU, DAU`

## 참고
- 원본 `202508` 은 '이탈' 레코드가 누락됐지만, 본 모델은 '유입+유지'만 쓰므로 영향 없음(정상 계산).

## 로컬 실행
```bash
pip install -r requirements.txt
streamlit run app.py
```
