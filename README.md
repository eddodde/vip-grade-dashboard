# VIP 등급 수불 대시보드

VIP 등급 **수불(유지·유입·이탈)·전환·활성도**를 월별로 진단하는 Streamlit 대시보드.
데이터: `(제휴제외)VIP_등급수불_TEMPLATE_auto_v3` 원본 xlsx 에서 추출한 CSV.

## 3대 축
1. **수불·전환 진단** — 등급별 유지/유입/이탈률, VIP vs 일반 잔존력, 일반→VIP 전환율 & 일반 내부 대사비중(99.3%), VIP 순증·필요신규 시나리오.
2. **이동 방향성 (From→To)** — 전이 히트맵, Sankey, 등급별 유입 출처/이탈 행선지.
3. **DAU/MAU 활성도 교차** — 등급별 Stickiness(DAU/MAU), 이동유형별 활성도, 활성도↔유지율 상관. *(원본 RAW 에만 있고 기존 분석엔 안 쓰인 신규 축)*

## 등급 체계
`RD < PP < BK < SV < GD < PT < SP` (승급/하락 방향에서 역산)
- **VIP**: BK·SV·GD·PT·SP (Black=진입티어, S-Platinum=최상위)
- **일반**: RD·PP

## 데이터 갱신
원본 xlsx 의 `RAW_입력` 시트만 갱신하면 나머지 분석 시트는 자동 수식으로 갱신됨.
그 후 아래 실행 → `data/*.csv` 재생성 → 커밋/푸시:

```powershell
./convert.ps1 -Src "원본 xlsx 경로"
```

`convert.ps1` 은 원본을 Excel COM 으로 메모리에서 읽어(시트는 ASCII 헤더 앵커로 탐지)
6개 CSV 를 UTF-8(BOM)로 추출한다. **원본 xlsx 는 repo 에 커밋하지 않음**(`.gitignore`).

| CSV | 내용 |
|---|---|
| `raw_grade.csv` | RAW 원천 (MAU/DAU 포함) — 3축 집계용 |
| `monthly_grade.csv` | (월×등급) 수불표 |
| `vip_vs_normal.csv` | VIP vs 일반 그룹 비교 |
| `conversion.csv` | 일반→VIP 전환 & 내부 대사 |
| `vip_growth.csv` | VIP 순증·필요신규 시나리오 |
| `move_matrix.csv` | From→To 전이행렬 |

## 알려진 데이터 caveat
- **202508**: 원본에 '이탈' 레코드가 없어 유지율이 100%로 왜곡됨. 사이드바 *보정* 토글(기본 ON)로 비율 추세에서 제외.

## 로컬 실행
```bash
pip install -r requirements.txt
streamlit run app.py
```
