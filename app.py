# -*- coding: utf-8 -*-
"""VIP 등급 수불 대시보드
모든 수치는 원본 RAW(유입/유지/이탈 행)에서 직접 계산한다.
모델: '유입'+'유지' 행으로 단일기입 전이행렬 M[FROM(전월)→TO(당월)] 을 만들고
      유지/유입/이탈·승급/하락·전환을 일관되게 파생(인구 보존 ΣFROM=ΣTO).
      ※ '이탈' 행은 유입/유지의 거울복제(이중기입)라 사용하지 않음.
연1회 고정등급(SP·PT)은 VIP 유지율 집계에서 제외(BK/SV/GD = VIP core).
"""
import io
import pathlib
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="VIP 등급 수불 대시보드", page_icon="📊",
                   layout="wide", initial_sidebar_state="expanded")
DATA = pathlib.Path(__file__).parent / "data"

# ── 등급 체계 (상위→하위 순서) ──────────────────────────────
ORDER = ["SP", "PT", "GD", "SV", "BK", "PP", "RD"]          # 표시 순서(상→하)
RANK = {"RD": 1, "PP": 2, "BK": 3, "SV": 4, "GD": 5, "PT": 6, "SP": 7}
NAME = {"SP": "S-Platinum", "PT": "Platinum", "GD": "Gold", "SV": "Silver",
        "BK": "Black", "PP": "Purple", "RD": "Red"}
VIP_ALL = ["BK", "SV", "GD", "PT", "SP"]
VIP_CORE = ["BK", "SV", "GD"]          # SP·PT(연1회 고정) 제외
NORMAL = ["PP", "RD"]
FIXED = ["SP", "PT"]
GCOLOR = {"SP": "#2980B9", "PT": "#16A085", "GD": "#D4AC0D", "SV": "#7F8C8D",
          "BK": "#2C3E50", "PP": "#8E44AD", "RD": "#C0392B"}
KFONT = "'Noto Sans KR','Malgun Gothic','Apple SD Gothic Neo',sans-serif"
ACCENT = "#2C5F8A"
glabel = {g: f"{g} {NAME[g]}" for g in ORDER}

# ── VIP 에이징(가입후 경과월) 구간 ──
VIP_AGING = ["SP", "PT", "GD", "SV", "BK"]   # 에이징은 VIP 등급만(상→하)
AGING_ORDER = ["신규 유입(0~2M)", "온보딩(3~5M)", "안정화(6~11M)",
               "하락가망(12M)", "장기 유지(13M~)"]
AGING_COLOR = {"신규 유입(0~2M)": "#3498DB", "온보딩(3~5M)": "#9B59B6",
               "안정화(6~11M)": "#27AE60", "하락가망(12M)": "#E67E22",
               "장기 유지(13M~)": "#2C3E50"}
DIRCOLOR = {"승급": "#27AE60", "하락": "#E74C3C", "유지": "#95A5A6"}

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');
html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif; }
.metric-card { background:#f7f9fc; border-radius:10px; padding:13px 18px;
  border-left:4px solid #2C5F8A; margin-bottom:10px; }
.metric-label { font-size:13px; color:#667; margin-bottom:4px; }
.metric-value { font-size:23px; font-weight:700; color:#1a2236; }
.metric-sub  { font-size:12px; color:#8a94a6; margin-top:2px; }
.section-title { font-size:18px; font-weight:700; color:#1a2236;
  margin:28px 0 12px; padding-bottom:6px; border-bottom:2px solid #e7ebf2;
  scroll-margin-top:60px; }
.hint { font-size:12px; color:#9aa3b2; margin:-4px 0 10px; }
a.navlink { display:block; padding:7px 12px; margin:3px 0; border-radius:8px;
  background:#eef3f9; color:#2C5F8A; text-decoration:none; font-size:14px;
  font-weight:600; border:1px solid #dde7f2; }
a.navlink:hover { background:#e0ebf7; color:#1d4666; }
.subnav-label { font-size:11px; font-weight:700; color:#9aa3b2;
  letter-spacing:.04em; margin:10px 0 2px; }
.subnav-preview { font-size:12px; color:#9aa3b2; line-height:1.5; margin-top:6px; }
.insight { background:#eef3f9; border-left:4px solid #2C5F8A; border-radius:8px;
  padding:12px 16px; margin:6px 0 14px; font-size:14px; line-height:1.6; }
.insight.warn { background:#fdf1ee; border-left-color:#E67E22; }
.insight.ok   { background:#eef7f0; border-left-color:#27AE60; }
.insight b { color:#1a2236; }
</style>
""", unsafe_allow_html=True)


def section(title, hint="", anchor=None):
    aid = f' id="{anchor}"' if anchor else ""
    st.markdown(f'<div class="section-title"{aid}>{title}</div>',
                unsafe_allow_html=True)
    if hint:
        st.markdown(f'<div class="hint">{hint}</div>', unsafe_allow_html=True)


def insight(html, kind=""):
    st.markdown(f'<div class="insight {kind}">{html}</div>',
                unsafe_allow_html=True)


def plot(fig, height=380, legend=True):
    # 천단위 콤마(안전: 날짜·카테고리 축엔 무영향). 카운트 축의 ',d'는 차트별 명시.
    fig.update_xaxes(separatethousands=True)
    fig.update_yaxes(separatethousands=True)
    fig.update_layout(font=dict(family=KFONT), height=height,
                      margin=dict(t=30, b=10, l=10, r=10),
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0)
                      if legend else dict())
    st.plotly_chart(fig, use_container_width=True,
                    config={"displayModeBar": False})


def ymlab(ym):
    s = str(ym)
    return f"{s[2:4]}-{s[4:6]}"


def _rgba(hexc, a):
    h = hexc.lstrip("#")
    return f"rgba({int(h[0:2],16)},{int(h[2:4],16)},{int(h[4:6],16)},{a})"


# ── 데이터 로드 & 전 지표 계산 ──────────────────────────────
RENAME = {"CURR_STD_YM": "YM", "GRAD_STATUS": "STATUS", "GRAD_MOVEMENT": "MOVE",
          "CURR_GRAD_GB": "CURR_GB", "CURR_NLINE_MEM_GRAD_CD": "CURR",
          "CURR_NLINE_MEM_GRAD_NM": "CURR_NM", "PREV_GRAD_GB": "PREV_GB",
          "PREV_NLINE_MEM_GRAD_CD": "PREV", "PREV_NLINE_MEM_GRAD_NM": "PREV_NM",
          "CUST_CNT": "CUST"}


def _parse_xlsx(b):
    """업로드된 원본 xlsx에서 RAW 시트(A1=CURR_STD_YM)를 찾아 DataFrame 반환."""
    xls = pd.ExcelFile(io.BytesIO(b))
    for sh in xls.sheet_names:
        head = xls.parse(sh, header=None, nrows=1).iloc[0].tolist()
        if head and str(head[0]).strip() == "CURR_STD_YM":
            return xls.parse(sh, header=0)
    raise ValueError("원본에서 RAW 시트(첫 셀 'CURR_STD_YM')를 찾지 못했습니다.")


def _parse_aging_xlsx(b):
    """에이징 원본에서 헤더행(c1='YM' & c7='MAU')을 가진 시트를 찾아 추출."""
    xls = pd.ExcelFile(io.BytesIO(b))
    for sh in xls.sheet_names:
        g = xls.parse(sh, header=None)
        for r in range(min(6, len(g))):
            row = g.iloc[r].tolist()
            if (len(row) >= 7 and str(row[0]).strip() == "YM"
                    and str(row[6]).strip() == "MAU"):
                t = g.iloc[r + 1:, [0, 2, 3, 4, 5, 6, 7]].copy()
                t.columns = ["YM", "GRADE_CD", "GRADE_NM", "AGING",
                             "EFF_CNT", "MAU", "DAU"]
                return t[t["YM"].astype(str).str.match(r"^\d{6}")]
    raise ValueError("에이징 시트(헤더 YM..MAU)를 찾지 못했습니다.")


@st.cache_data(show_spinner=False)
def load_and_build(uploaded: bytes | None):
    # 업로드 1개 파일에 수불(등급수불 시트)·에이징(에이징 시트)이 함께 들어있음.
    df = (_parse_xlsx(uploaded) if uploaded
          else pd.read_csv(DATA / "raw_grade.csv", encoding="utf-8-sig"))
    df = df.rename(columns=RENAME)
    df["YM"] = df["YM"].astype(str).str.replace(r"\.0$", "", regex=True)
    for c in ("CUST", "MAU", "DAU"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    for c in ("CURR", "PREV", "STATUS"):
        df[c] = df[c].astype(str).str.strip()

    # 단일기입 전이행렬 M (유입+유지)
    flow = df[df["STATUS"].isin(["유입", "유지"])].copy()
    mat = (flow.groupby(["YM", "PREV", "CURR"], as_index=False)["CUST"].sum()
               .rename(columns={"PREV": "FROM", "CURR": "TO", "CUST": "CNT"}))
    mat = mat[mat["FROM"].isin(ORDER) & mat["TO"].isin(ORDER)]
    mat["dir"] = mat.apply(
        lambda r: "유지" if r.FROM == r.TO
        else ("승급" if RANK[r.TO] > RANK[r.FROM] else "하락"), axis=1)

    yms = sorted(mat["YM"].unique())
    keep = mat[mat.FROM == mat.TO].groupby(["YM", "TO"])["CNT"].sum()
    inf = mat[mat.FROM != mat.TO].groupby(["YM", "TO"])["CNT"].sum()
    out = mat[mat.FROM != mat.TO].groupby(["YM", "FROM"])["CNT"].sum()
    # 양식 정의: 유입=승급(하위→)+하락(상위→), 이탈=승급(→상위)+하락(→하위)
    mv = mat[mat.FROM != mat.TO]
    inf_up = mv[mv.dir == "승급"].groupby(["YM", "TO"])["CNT"].sum()   # 하위에서 올라옴
    inf_dn = mv[mv.dir == "하락"].groupby(["YM", "TO"])["CNT"].sum()   # 상위에서 내려옴
    out_up = mv[mv.dir == "승급"].groupby(["YM", "FROM"])["CNT"].sum()  # 상위로 올라감
    out_dn = mv[mv.dir == "하락"].groupby(["YM", "FROM"])["CNT"].sum()  # 하위로 내려감

    idx = pd.MultiIndex.from_product([yms, ORDER], names=["YM", "GRADE"])
    gm = pd.DataFrame(index=idx)
    gm["유지"] = keep.reindex(idx, fill_value=0)
    gm["유입"] = inf.reindex(idx, fill_value=0)
    gm["이탈"] = out.reindex(idx, fill_value=0)
    gm["유입_승급"] = inf_up.reindex(idx, fill_value=0)
    gm["유입_하락"] = inf_dn.reindex(idx, fill_value=0)
    gm["이탈_승급"] = out_up.reindex(idx, fill_value=0)
    gm["이탈_하락"] = out_dn.reindex(idx, fill_value=0)
    gm = gm.reset_index()
    gm["유효회원"] = gm["유지"] + gm["유입"]       # 당월유효(양식의 헤드라인)
    gm["전월유효"] = gm["유지"] + gm["이탈"]
    gm["당월유효"] = gm["유효회원"]
    gm["순증"] = gm["유입"] - gm["이탈"]
    # 양식 분모: 유지/유입 구성비는 '당월 유효회원', 이탈률은 '전월 유효회원'
    gm["유지구성"] = gm["유지"] / gm["유효회원"].where(gm["유효회원"] != 0)
    gm["유입구성"] = gm["유입"] / gm["유효회원"].where(gm["유효회원"] != 0)
    gm["이탈률"] = gm["이탈"] / gm["전월유효"].where(gm["전월유효"] != 0)
    gm["잔존율"] = gm["유지"] / gm["전월유효"].where(gm["전월유효"] != 0)  # =1-이탈률
    gm["GROUP"] = gm["GRADE"].map(
        lambda g: "VIP" if g in VIP_ALL else "일반")

    # 월별 승급/유지/하락 총량
    flowdir = (mat.groupby(["YM", "dir"])["CNT"].sum().unstack(fill_value=0)
                  .reindex(columns=["승급", "유지", "하락"], fill_value=0)
                  .reset_index())

    # 그룹 집계(VIP core = SP·PT 제외)
    def grp(grades, name):
        s = (gm[gm.GRADE.isin(grades)].groupby("YM")[["유지", "유입", "이탈"]].sum())
        s["전월유효"] = s["유지"] + s["이탈"]
        s["당월유효"] = s["유지"] + s["유입"]
        s["순증"] = s["유입"] - s["이탈"]
        s["유지율"] = s["유지"] / s["전월유효"]
        s["GROUP"] = name
        return s.reset_index()
    group = pd.concat([grp(VIP_CORE, "VIP(SP·PT제외)"), grp(NORMAL, "일반")],
                      ignore_index=True)

    # 전환 & 일반 내부 대사
    def flowsum(cond):
        return mat[cond(mat)].groupby("YM")["CNT"].sum()
    n2v = flowsum(lambda m: m.FROM.isin(NORMAL) & m.TO.isin(VIP_ALL))
    v2n = flowsum(lambda m: m.FROM.isin(VIP_ALL) & m.TO.isin(NORMAL))
    n_eff = gm[gm.GRADE.isin(NORMAL)].groupby("YM")["전월유효"].sum()
    n_keep = gm[gm.GRADE.isin(NORMAL)].groupby("YM")["유지"].sum()
    n_up = flowsum(lambda m: (m.FROM == "RD") & (m.TO == "PP"))
    n_dn = flowsum(lambda m: (m.FROM == "PP") & (m.TO == "RD"))
    conv = pd.DataFrame({"전월일반유효": n_eff}).reset_index()
    conv["일반→VIP"] = conv["YM"].map(n2v).fillna(0)
    conv["VIP→일반"] = conv["YM"].map(v2n).fillna(0)
    conv["VIP순증"] = conv["일반→VIP"] - conv["VIP→일반"]
    conv["전환율"] = conv["일반→VIP"] / conv["전월일반유효"]
    conv["일반내대사"] = (conv["YM"].map(n_up).fillna(0)
                         + conv["YM"].map(n_dn).fillna(0)
                         + conv["YM"].map(n_keep).fillna(0))
    conv["대사비중"] = conv["일반내대사"] / conv["전월일반유효"]

    # 활성도(DAU/MAU): 당월유효(=유입+유지) 기준
    fa = flow[flow["CURR"].isin(ORDER)].copy()
    fa["dir"] = fa.apply(
        lambda r: "유지" if r.CURR == r.PREV
        else ("승급" if RANK.get(r.CURR, 0) > RANK.get(r.PREV, 0) else "하락"),
        axis=1)
    sticky = (fa.groupby(["YM", "CURR"])[["MAU", "DAU", "CUST"]].sum()
                .reset_index().rename(columns={"CURR": "GRADE"}))
    sticky["stickiness"] = sticky["DAU"] / sticky["MAU"].where(sticky["MAU"] != 0)
    actdir = (fa.groupby(["YM", "dir"])[["MAU", "DAU", "CUST"]].sum().reset_index())
    actdir["1인당MAU"] = actdir["MAU"] / actdir["CUST"].where(actdir["CUST"] != 0)
    actdir["stickiness"] = actdir["DAU"] / actdir["MAU"].where(actdir["MAU"] != 0)

    # ── VIP 에이징(가입후 경과월) ──
    aging = (_parse_aging_xlsx(uploaded) if uploaded
             else pd.read_csv(DATA / "aging.csv", encoding="utf-8-sig"))
    aging = aging.rename(columns={"EFF_CNT": "유효회원수"})
    aging["YM"] = aging["YM"].astype(str).str.replace(r"\.0$", "", regex=True)
    for c in ("유효회원수", "MAU", "DAU"):
        aging[c] = pd.to_numeric(aging[c], errors="coerce").fillna(0)
    aging["AGING"] = aging["AGING"].astype(str).str.strip()
    aging["GRADE_CD"] = aging["GRADE_CD"].astype(str).str.strip()

    for d in (gm, flowdir, group, conv, sticky, actdir, mat, aging):
        d["LABEL"] = d["YM"].map(ymlab)
    return dict(gm=gm, flowdir=flowdir, group=group, conv=conv, mat=mat,
                sticky=sticky, actdir=actdir, yms=yms, aging=aging)


# ── 사이드바: 업로드 · 목차 · 필터 ──────────────────────────
with st.sidebar:
    st.header("⚙️ 설정")
    with st.expander("📤 원본 올리기 (월 갱신)", expanded=False):
        st.caption("**수불·에이징이 함께 든 원본 xlsx 1개**를 올리면 git push 없이 "
                   "즉시 재계산합니다. (시트: '등급수불' + '에이징'). "
                   "또는 convert.ps1 로 data/*.csv 갱신 후 push.")
        up = st.file_uploader("등급수불 + 에이징 원본 (xlsx)", type=["xlsx"], key="up")

try:
    B = load_and_build(up.getvalue() if up else None)
except Exception as e:
    st.error(f"데이터를 읽는 중 오류: {e}")
    st.stop()

gm, flowdir, group, conv = B["gm"], B["flowdir"], B["group"], B["conv"]
mat, sticky, actdir, YMS = B["mat"], B["sticky"], B["actdir"], B["yms"]
aging = B["aging"]

PAGES = {
    "📊 수불 현황": [
        ("sec-summary", "1 · 현황 한눈에"),
        ("sec-flow", "2 · 이동은 활발한가(승급·유지·하락)"),
        ("sec-grade", "3 · 등급별 잔존·이탈"),
        ("sec-group", "4 · VIP는 자라나(순증)"),
        ("sec-conv", "5 · 핵심 병목(일반→VIP)"),
        ("sec-matrix", "6 · 심화: 어디서 어디로"),
        ("sec-detail", "7 · 심화: 등급 분해"),
        ("sec-activity", "8 · 보조: DAU/MAU 활성도"),
    ],
    "⏳ VIP 에이징": [
        ("sec-aging", "에이징 분포 개요"),
        ("sec-aging-mix", "구간 구성 추세"),
        ("sec-aging-act", "구간별 활성도"),
    ],
}
active = st.session_state.setdefault("page", list(PAGES)[0])
if active not in PAGES:
    active = list(PAGES)[0]
with st.sidebar:
    st.markdown("#### 📂 메뉴")
    # 아코디언: 상위 메뉴 클릭 → 하위 메뉴 펼침. 활성 그룹만 열림(LMS 스타일)
    for pname, items in PAGES.items():
        is_act = pname == active
        with st.expander(pname, expanded=is_act):
            if is_act:
                st.markdown(
                    "".join(f'<a href="#{a}" class="navlink">{l}</a>'
                            for a, l in items), unsafe_allow_html=True)
            else:
                if st.button("이 메뉴 보기 →", key=f"sw_{pname}",
                             use_container_width=True):
                    st.session_state.page = pname
                    st.rerun()
                st.markdown('<div class="subnav-preview">'
                            + " · ".join(l for _, l in items) + "</div>",
                            unsafe_allow_html=True)
    page = active
    st.markdown("#### 🔎 기간")
    ym0, ym1 = st.select_slider("기간(월)", options=YMS, value=(YMS[0], YMS[-1]),
                                format_func=ymlab)
    src = "업로드 원본" if up else "커밋된 data/raw_grade.csv"
    st.caption(f"데이터 출처: **{src}** · {len(YMS)}개월")
    st.caption("등급(상→하): SP·PT·GD·SV·BK(=VIP) / PP·RD(=일반). "
               "**SP·PT는 연1회(1/1) 고정**이라 VIP 유지율 집계에서 제외.")


def rng(df, col="YM"):
    return df[(df[col] >= ym0) & (df[col] <= ym1)].copy()


def metric_card(col, label, value, sub=""):
    col.markdown(
        f'<div class="metric-card"><div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value}</div>'
        f'<div class="metric-sub">{sub}</div></div>', unsafe_allow_html=True)


def how_to(html):
    """차트 읽는 법 안내(접이식)."""
    with st.expander("📖 이 차트 읽는 법"):
        st.markdown(html, unsafe_allow_html=True)


def render_aging():
    section("VIP 에이징 분포 개요",
            "VIP 가입후 경과월 코호트: 신규유입(0~2M) → 온보딩(3~5M) → 안정화(6~11M) "
            "→ 하락가망(12M) → 장기유지(13M~). 소스=에이징 원본(수불 템플릿과 동일 기준).",
            anchor="sec-aging")
    with st.expander("📖 구간 정의 & 상태(의미)"):
        st.markdown(
            "| 구간 | 기간 | 상태(의미) |\n|---|---|---|\n"
            "| 신규 유입 | 0~2M | 정착 전, 이탈 가능성 有 |\n"
            "| 온보딩 | 3~5M | 정착 판단·구매 루틴 형성 |\n"
            "| 안정화 | 6~11M | 로열티 기반 형성·구매 패턴 고착 |\n"
            "| 하락가망 | 12M | VIP 12개월차. 등급은 **직전 12개월 구매**로 산정 → "
            "가입 후 추가 구매가 없으면 최초 자격 구매가 산정창에서 빠져 **다음 달 하락 위험** |\n"
            "| 장기유지 | 13M+ | 로열티 高 고객군 |")
    ac1, ac2 = st.columns([1, 3])
    with ac1:
        ametric = st.radio("지표", ["유효회원수", "MAU", "DAU"], key="ametric")
        ascope = st.multiselect("등급", VIP_AGING, default=VIP_AGING,
                                format_func=lambda g: glabel[g], key="ascope")
    ag = rng(aging)
    ag = ag[ag.GRADE_CD.isin(ascope)]
    alatest = ag[ag.YM == ym1]
    atot = alatest[ametric].sum()

    def ashare(bucket):
        return alatest[alatest.AGING == bucket][ametric].sum() / atot if atot else 0

    risk = ashare("하락가망(12M)")
    longp = ashare("장기 유지(13M~)")
    newp = ashare("신규 유입(0~2M)")
    # ── 판단·시사점용 구간 요약(인원·활성도, ametric 무관) ──
    _b = (alatest.groupby("AGING")[["유효회원수", "MAU", "DAU"]].sum()
          .reindex(AGING_ORDER).fillna(0))
    _tot = _b["유효회원수"].sum()
    _stick = (_b["DAU"] / _b["MAU"].where(_b["MAU"] != 0)).fillna(0)   # 방문빈도
    _maur = (_b["MAU"] / _b["유효회원수"].where(_b["유효회원수"] != 0)).fillna(0)  # 월방문율
    LONG, RISK = "장기 유지(13M~)", "하락가망(12M)"
    share_long = _b["유효회원수"][LONG] / _tot if _tot else 0
    risk_cnt = _b["유효회원수"][RISK]
    risk_act = _maur[RISK]
    valley = _stick.drop(LONG).idxmin() if _tot else "온보딩(3~5M)"   # 활성 최저 구간
    valley_s = _stick[valley] if _tot else 0
    mid_act = _maur[["온보딩(3~5M)", "안정화(6~11M)"]].mean()
    _rs = ag[ag.AGING == RISK].groupby("YM")["유효회원수"].sum().sort_index()
    risk_dir = ("줄어드는" if len(_rs) >= 2 and _rs.iloc[-1] < _rs.iloc[0]
                else ("늘어나는" if len(_rs) >= 2 and _rs.iloc[-1] > _rs.iloc[0]
                      else "비슷한"))
    with ac2:
        kk = st.columns(4)
        metric_card(kk[0], f"VIP {ametric} 합", f"{atot:,.0f}",
                    f"{ymlab(ym1)} · 선택등급")
        metric_card(kk[1], "하락가망(12M) 비중", f"{risk*100:.1f}%",
                    "12개월차·추가구매 없으면 하락")
        metric_card(kk[2], "장기유지(13M~) 비중", f"{longp*100:.1f}%", "로열티 高")
        metric_card(kk[3], "신규유입(0~2M) 비중", f"{newp*100:.1f}%",
                    "정착 전·이탈 가능")
    _valley_note = ("진입 직후 높던 방문이 이 시기에 식는 '온보딩 밸리'입니다"
                    if valley.startswith("온보딩")
                    else "이 시기에 방문이 가장 가라앉습니다")
    insight(
        f"📌 <b>현황 판단</b> — {ymlab(ym1)} 선택 VIP {_tot:,.0f}명 중 "
        f"<b>장기유지(13M~)가 {share_long*100:.0f}%</b>로 충성 기반은 탄탄합니다. "
        f"다만 방문빈도(Stickiness)는 <b>{valley} 구간에서 최저({valley_s*100:.0f}%)</b> — "
        f"{_valley_note}. 하락가망(12M)은 {risk_cnt:,.0f}명으로 {risk_dir} 추세입니다.")

    section("구간 구성 추세", "월별로 에이징 구간 비중이 어떻게 변하는지 (코호트 이동)",
            anchor="sec-aging-mix")
    how_to("• <b>색</b>: 신규유입=파랑, 온보딩=보라, 안정화=초록, 하락가망=주황, "
           "장기유지=남색.<br>"
           "• <b>왼쪽(누적 막대)</b>: 한 달의 100%를 5개 구간이 나눠 가짐.<br>"
           "• <b>오른쪽</b>: 선택월의 <b>등급별</b> 구간 구성. 막대 길이=인원.<br>"
           "• 하락가망(주황)·신규유입(파랑) 비중이 커지면 향후 하락 압력 신호.")
    c1, c2 = st.columns(2)
    with c1:
        anorm = st.checkbox("구성비(100%)로 보기", value=True, key="agnorm")
        t1 = ag.groupby(["YM", "LABEL", "AGING"], as_index=False)[ametric].sum()
        if anorm:
            t1["tot"] = t1.groupby("YM")[ametric].transform("sum")
            t1["val"] = t1[ametric] / t1["tot"].where(t1["tot"] != 0)
        else:
            t1["val"] = t1[ametric]
        fig = px.bar(t1.sort_values("YM"), x="LABEL", y="val", color="AGING",
                     category_orders={"AGING": AGING_ORDER},
                     color_discrete_map=AGING_COLOR)
        fig.update_yaxes(tickformat=".0%" if anorm else ",d")
        fig.update_layout(legend_title="에이징", barmode="stack",
                          yaxis_title="구성비" if anorm else ametric)
        plot(fig, height=380)
        st.caption("에이징 구간 구성 추세.")
    with c2:
        t2 = ag[ag.YM == ym1].groupby(["GRADE_CD", "AGING"],
                                      as_index=False)[ametric].sum()
        fig = px.bar(t2, x=ametric, y="GRADE_CD", color="AGING", orientation="h",
                     category_orders={"AGING": AGING_ORDER, "GRADE_CD": VIP_AGING},
                     color_discrete_map=AGING_COLOR)
        fig.update_xaxes(tickformat=",d")
        fig.update_layout(yaxis=dict(autorange="reversed"), legend_title="에이징",
                          barmode="stack")
        plot(fig, height=380)
        st.caption(f"{ymlab(ym1)} 등급별 에이징 구성 (상위→하위).")

    section("구간별 활성도 (DAU/MAU Stickiness)",
            "에이징 구간별로 얼마나 자주 방문하는지 — 온보딩 약화·정착 여부 점검",
            anchor="sec-aging-act")
    t3 = ag.groupby(["YM", "LABEL", "AGING"], as_index=False)[["DAU", "MAU"]].sum()
    t3["stickiness"] = t3["DAU"] / t3["MAU"].where(t3["MAU"] != 0)
    fig = px.line(t3.sort_values("YM"), x="LABEL", y="stickiness", color="AGING",
                  markers=True, symbol="AGING", category_orders={"AGING": AGING_ORDER},
                  color_discrete_map=AGING_COLOR)
    fig.update_traces(line=dict(width=2.5), marker=dict(size=7))
    fig.update_yaxes(tickformat=".0%")
    fig.update_layout(legend_title="에이징")
    plot(fig, height=360)
    _save = ("오히려 높아" if risk_act >= mid_act else "낮지 않아")
    insight(
        "🎯 <b>시사점 · 해야 할 일</b><br>"
        f"① <b>하락가망(12M) {risk_cnt:,.0f}명 = 다음 달 하락 위험에 노출된 코호트.</b> "
        "등급은 직전 12개월 구매로 산정되므로, VIP 12개월차인 이 구간 중 "
        "<b>최근 12개월에 추가 구매가 없는 사람은 자격 구매가 산정창에서 빠져 하락</b>합니다 "
        "(추가 구매가 있은 사람은 유지 — <b>누가 안 샀는지는 이 데이터로는 알 수 없고 구매 내역이 필요</b>). "
        f"다만 이 코호트의 월방문율은 {risk_act*100:.0f}%로 온보딩·안정화 평균({mid_act*100:.0f}%)보다 {_save} "
        "<b>여전히 앱을 쓰는 활성 코호트</b>이므로, 쿠폰·리마인드 같은 구매 유도 리텐션의 반응 여지가 큽니다.<br>"
        f"② <b>활성 최저 '{valley}' 구간({valley_s*100:.0f}%) 온보딩 강화.</b> "
        "진입 직후 방문이 식기 전 이 시기에 혜택·푸시를 집중해 방문 습관을 굳히면, "
        "이후 안정화→장기유지로 넘어가는 전환을 늘리고 하락가망으로 새는 인원을 줄입니다.<br>"
        f"③ <b>장기유지 {share_long*100:.0f}% 기반 유지.</b> 충성층 혜택을 지키되, "
        "신규유입→온보딩 누수를 막아 장기유지 풀을 키우는 게 순증의 핵심.", "warn")
    # 실제 결측 월만 자동 안내(원본에 채워지면 사라짐)
    _agy = set(aging["YM"])
    _miss = [m for m in YMS if ym0 <= m <= ym1 and m not in _agy]
    if _miss:
        st.caption("ⓘ 에이징 원본에 " + ", ".join(ymlab(m) for m in _miss)
                   + " 데이터가 없어 해당 월은 비어 있습니다.")


st.title("📊 VIP 등급 수불 대시보드")
st.caption(f"기간 {ymlab(ym0)} ~ {ymlab(ym1)} · 모든 수치는 RAW에서 직접 산출 "
           "(유입+유지 단일기입 전이모델)")
PAGE_INTRO = {
    "📊 수불 현황": "월별 등급 <b>수불(유지·유입·이탈, 승급·하락)</b>·전환·활성도를 봅니다. "
    "VIP 유지율은 연1회 고정등급 SP·PT를 제외(BK·SV·GD)합니다.",
    "⏳ VIP 에이징": "VIP <b>가입후 경과월(에이징)</b> 코호트별 규모·활성도를 봅니다. "
    "하락가망(12M) 구간이 하락 위험의 핵심 타깃입니다.",
}
insight(PAGE_INTRO[page])

if not page.startswith("📊"):      # 에이징 페이지 → 렌더 후 종료
    render_aging()
    st.stop()

insight(
    "🧭 <b>이 페이지의 흐름 — \"이동은 활발한데 왜 VIP는 안 늘어나는가?\"</b><br>"
    "① 현황 → ② 등급 이동이 활발한지(승급·유지·하락) → ③ 등급별 잔존·이탈 → "
    "④ <b>그래도 VIP 순증이 나는지</b> → ⑤ 안 난다면 <b>유입 병목(일반→VIP)은 어디인지</b> "
    "→ ⑥·⑦ 심화(어디서 어디로·등급 분해) → ⑧ 활성도 보조단서, 순으로 진단합니다.")

# ════════ 1 현황 ════════
section("1 · 현황 한눈에",
        f"최신월 {ymlab(ym1)} 기준 VIP/일반 핵심 지표. VIP 유지율은 연1회 고정 SP·PT 제외.",
        anchor="sec-summary")
gV = group[(group.GROUP == "VIP(SP·PT제외)") & (group.YM == ym1)]
gN = group[(group.GROUP == "일반") & (group.YM == ym1)]
cV = conv[conv.YM == ym1]
fd = flowdir[flowdir.YM == ym1]
k = st.columns(5)
metric_card(k[0], "VIP 유지율 (SP·PT 제외)",
            f"{gV['유지율'].iloc[0]*100:.1f}%" if len(gV) else "—",
            "BK·SV·GD 기준")
metric_card(k[1], "일반 유지율",
            f"{gN['유지율'].iloc[0]*100:.1f}%" if len(gN) else "—", "PP·RD")
metric_card(k[2], "일반→VIP 전환율",
            f"{cV['전환율'].iloc[0]*100:.2f}%" if len(cV) else "—",
            f"{cV['일반→VIP'].iloc[0]:,.0f}명" if len(cV) else "")
metric_card(k[3], "VIP 순증",
            f"{cV['VIP순증'].iloc[0]:+,.0f}명" if len(cV) else "—",
            "일반→VIP − VIP→일반")
metric_card(k[4], "이번달 승급 / 하락",
            f"{fd['승급'].iloc[0]:,.0f} / {fd['하락'].iloc[0]:,.0f}"
            if len(fd) else "—", "명")

# ════════ 수불 한눈에 ════════
section("2 · 등급 이동은 활발한가 — 승급 · 유지 · 하락",
        "이번 기간 전체에서 등급을 올린 사람(승급)·내린 사람(하락)이 얼마나 되는지, "
        "그리고 등급별로 들어오고(유입) 빠지는(이탈) 균형을 한눈에.",
        anchor="sec-flow")
how_to("• <b>왼쪽</b>: 월별로 <b>위 막대=승급 인원, 아래 막대=하락 인원</b>, "
       "검은 선=순이동(승급−하락). 선이 0 위면 그 달은 전반적으로 등급이 올랐다는 뜻.<br>"
       "• <b>오른쪽</b>: 선택월의 <b>등급별 유입(오른쪽,파랑)·이탈(왼쪽,주황)</b> 균형. "
       "막대가 오른쪽으로 길면 그 등급은 순증, 왼쪽으로 길면 순감.")
_fr = rng(flowdir)
_up, _dn = _fr["승급"].sum(), _fr["하락"].sum()
insight(f"🔎 <b>진단</b> — 기간 누적 <b>승급 {_up:,.0f} · 하락 {_dn:,.0f}명</b> "
        f"(순 {_up-_dn:+,.0f}). 이동량은 큰데 승급과 하락이 거의 맞물려 돌아 등급 구조가 "
        "<b>고착</b>(올라가는 만큼 내려옴)에 가깝습니다. <b>→ 그렇다면 이 활발한 이동이 정작 "
        "VIP 순증으로 이어질까? ④에서 확인합니다.</b>")
c1, c2 = st.columns([3, 2])
with c1:
    fdr = rng(flowdir).sort_values("YM")
    fig = go.Figure()
    fig.add_bar(x=fdr["LABEL"], y=fdr["승급"], name="승급", marker_color="#27AE60")
    fig.add_bar(x=fdr["LABEL"], y=-fdr["하락"], name="하락", marker_color="#E74C3C")
    fig.add_scatter(x=fdr["LABEL"], y=fdr["승급"] - fdr["하락"], name="순이동(승급-하락)",
                    mode="lines+markers", line=dict(color="#2C3E50", width=2))
    fig.update_layout(barmode="relative", yaxis_title="명 (위=승급, 아래=하락)")
    fig.update_yaxes(tickformat=",d")
    plot(fig, height=360)
    st.caption("막대 위=승급, 아래=하락. 검은 선=순이동. 0 근처면 승강이 균형(고착).")
with c2:
    msel = st.select_slider("등급 밸런스 기준월", options=YMS, value=ym1,
                            format_func=ymlab, key="balm")
    gmm = gm[gm.YM == msel].set_index("GRADE").reindex(ORDER)
    fig = go.Figure()
    fig.add_bar(y=gmm.index, x=gmm["유입"], name="유입", orientation="h",
                marker_color="#2980B9")
    fig.add_bar(y=gmm.index, x=-gmm["이탈"], name="이탈", orientation="h",
                marker_color="#E67E22")
    fig.update_layout(barmode="relative", yaxis=dict(autorange="reversed"),
                      xaxis_title="명 (오른쪽=유입, 왼쪽=이탈)")
    fig.update_xaxes(tickformat=",d")
    plot(fig, height=360)
    st.caption(f"{ymlab(msel)} 등급별 유입(+)·이탈(−). 상위→하위 순.")

# ════════ 등급별 수불 추세 ════════
section("3 · 등급별 잔존·이탈 추세",
        "어느 등급이 잘 남고 잘 빠지나. 잔존율=유지/전월유효 · 구성비=유지·유입/당월유효 "
        "· 이탈률=이탈/전월유효 (양식 정의)",
        anchor="sec-grade")
METRICS = {"잔존율(전월대비)": "잔존율", "유지 구성비": "유지구성",
           "유입 구성비": "유입구성", "이탈률": "이탈률", "순증(명)": "순증"}
c1, c2 = st.columns([1, 3])
with c1:
    mlbl = st.radio("지표", list(METRICS), key="gmet")
    metric = METRICS[mlbl]
    gsel = st.multiselect("등급", ORDER, default=ORDER,
                          format_func=lambda g: glabel[g], key="gsel")
with c2:
    gd = rng(gm)
    gd = gd[gd.GRADE.isin(gsel)].sort_values("YM")
    fig = px.line(gd, x="LABEL", y=metric, color="GRADE", markers=True,
                  color_discrete_map=GCOLOR, category_orders={"GRADE": ORDER})
    fig.update_yaxes(tickformat=".0%" if metric != "순증" else ",d")
    fig.update_layout(legend_title="등급", yaxis_title=mlbl)
    plot(fig, height=380)
insight("VIP 등급(BK·SV·GD)은 잔존율 변동이 크고, <b>RD(Red)는 ~99%</b>로 사실상 고착. "
        "SP·PT는 연1회 고정등급이라 월 단위 잔존율 해석에서 제외했습니다.")

# ════════ VIP vs 일반 ════════
section("4 · 그래서 VIP는 자라나? — 순증·잔존",
        "②③에서 이동은 활발했는데, 그 결과 VIP 풀이 실제로 느는지(순증) 본다. "
        "VIP는 SP·PT 제외(BK·SV·GD).",
        anchor="sec-group")
GC = {"VIP(SP·PT제외)": "#2C5F8A", "일반": "#E67E22"}
c1, c2 = st.columns(2)
with c1:
    st.markdown("**① 잔존율 — VIP vs 일반**")
    gr = rng(group).sort_values("YM")
    fig = px.line(gr, x="LABEL", y="유지율", color="GROUP", markers=True,
                  color_discrete_map=GC)
    fig.update_yaxes(tickformat=".0%")
    fig.update_layout(legend_title="")
    plot(fig, height=320)
    st.caption("VIP는 ~80%로 출렁이고 일반은 ~99%로 평탄. (잔존율=유지/전월유효)")
with c2:
    st.markdown("**② VIP가 실제로 느나? — 월 순증(막대)·풀 규모(선)**")
    # 월 순증(부호색 막대) + 실제 풀 규모(당월유효) 선. 누적합은 월간 스냅샷
    # 공백(예: 202508 이탈누락)으로 실제 풀 변화와 어긋나 오해 소지 → 풀 규모를 직접 표시.
    gv = rng(group[group.GROUP == "VIP(SP·PT제외)"]).sort_values("YM")
    bar_c = ["#C0392B" if v < 0 else "#2C5F8A" for v in gv["순증"]]
    fig = go.Figure()
    fig.add_bar(x=gv["LABEL"], y=gv["순증"], name="월 순증", marker_color=bar_c)
    fig.add_scatter(x=gv["LABEL"], y=gv["당월유효"], name="VIP core 풀(유효회원)",
                    mode="lines+markers", line=dict(color="#E67E22", width=2.5),
                    yaxis="y2")
    fig.update_layout(
        yaxis=dict(title="월 순증(명)", zeroline=True, zerolinecolor="#bbb",
                   tickformat=",d"),
        yaxis2=dict(title="풀 규모(명)", overlaying="y", side="right",
                    showgrid=False, tickformat=",d"))
    plot(fig, height=320)
    _s, _e = gv["당월유효"].iloc[0], gv["당월유효"].iloc[-1]
    _r = _e - gv["당월유효"].iloc[-4] if len(gv) >= 4 else 0
    _ans = "거의 못 늘고 있습니다" if _e <= _s else "소폭 늘었습니다"
    _tail = (f" 다만 <b>최근 3개월 {_r:+,.0f}으로 반등 조짐</b>." if _r > 0
             else (f" 최근 3개월도 {_r:+,.0f}." if _r < 0 else ""))
    insight(f"💡 <b>답: VIP는 {_ans}.</b> 풀 {_s:,.0f} → {_e:,.0f}명 "
            f"(기간 {_e-_s:+,.0f}, 감소는 대부분 2025년).{_tail}",
            "ok" if _e > _s or _r > 0 else "warn")
    st.caption("파랑=순증(+)·빨강=순감(−), 주황선=VIP core(BK·SV·GD) 풀 규모(당월유효).")
insight("🔎 <b>진단</b> — 이동은 활발했지만 승급·하락이 상쇄돼 VIP 풀은 <b>2025년 감소 후 "
        "정체(2026 상반기 소폭 반등)</b> 수준 — 자력으론 크게 못 큽니다. 추세를 위로 돌릴 "
        "유일한 길은 <b>외부 유입(일반→VIP)</b>인데, 그게 충분한지 "
        "<b>→ ⑤에서 병목을 확인합니다.</b>", "warn")

# ════════ 전환 & 내부 대사 ════════
section("5 · 핵심 병목 — 일반→VIP 유입",
        "④에서 VIP 순증이 안 났다면, 외부 유입원인 '일반→VIP'가 막혔다는 뜻. "
        "전환율 vs 일반(RD·PP) 내부 순환 비중으로 병목을 확인한다.",
        anchor="sec-conv")
cd = rng(conv).sort_values("YM")
fig = go.Figure()
fig.add_bar(x=cd["LABEL"], y=cd["전환율"], name="일반→VIP 전환율",
            marker_color="#27AE60", yaxis="y")
fig.add_scatter(x=cd["LABEL"], y=cd["대사비중"], name="일반 내부 대사비중",
                mode="lines+markers", marker_color="#C0392B", yaxis="y2")
fig.update_layout(
    yaxis=dict(title="전환율", tickformat=".2%"),
    yaxis2=dict(title="대사비중", overlaying="y", side="right",
                tickformat=".0%", range=[0.95, 1.0]),
    legend=dict(orientation="h", y=1.1))
plot(fig, height=360, legend=False)
avg_conv = conv["전환율"].mean()
insight(f"🎯 <b>결론(병목)</b> — 일반 고객의 <b>약 {conv['대사비중'].mean()*100:.1f}%가 "
        f"RD↔PP 내부에서만</b> 순환하고, VIP로 올라오는 전환율은 평균 "
        f"<b>{avg_conv*100:.2f}%</b>에 불과합니다. 즉 ②③의 활발한 이동도, ④의 VIP 정체도 "
        "결국 <b>여기서 외부 유입이 막힌 탓</b> — <b>일반 상위(PP)를 겨냥한 승급 부스팅이 "
        "VIP 순증의 가장 큰 레버</b>입니다. (어느 등급을 건드릴지는 ⑥·⑦에서 구체화)", "warn")

# ════════ 이동 방향성 ════════
section("6 · 심화: 어디서 어디로 (From → To)",
        "①~⑤로 큰 그림을 봤다면, 여기서부터는 드릴다운. 선택한 달에 전월 등급 → 당월 "
        "등급으로 어떻게 옮겨갔는지(전체 등급). Sankey는 '유지 포함' 토글 제공.",
        anchor="sec-matrix")
mm = st.select_slider("기준월", options=YMS, value=ym1, format_func=ymlab,
                      key="mxm")
mx = mat[mat.YM == mm]
how_to("두 차트 모두 같은 데이터(전월→당월 이동)를 보여줍니다(전체 등급).<br>"
       "• <b>왼쪽 히트맵</b>: <b>행=전월, 열=당월</b>. 칸 숫자=이동 인원, 색 진할수록 많음. "
       "대각선=유지(같은 등급), 그 외=이동. ('유지 제외' 체크로 대각선 끄기).<br>"
       "• <b>오른쪽 Sankey</b>: <b>왼쪽 마디=전월, 오른쪽 마디=당월</b>. 띠 하나 = "
       "'전월 A → 당월 B', <b>띠 두께=인원</b>. "
       "<span style='color:#27AE60'>초록=승급</span> / "
       "<span style='color:#E74C3C'>빨강=하락</span> / "
       "유지(같은 등급)=<b>해당 등급색 연하게</b>. 유지는 규모가 커서(특히 RD) 기본은 빼고 "
       "이동만 표시 — <b>'유지 포함'</b> 체크하면 함께 보입니다.<br>"
       "• 등급은 <b>위에서 아래로 상위→하위</b> 순.")
# 자동 인사이트: 이번 달 가장 큰 '이동'(유지 제외) 3건
_mv = mx[mx.FROM != mx.TO].nlargest(3, "CNT")
if len(_mv):
    _txt = ", ".join(
        f"<b>{r.FROM}→{r.TO}</b> {r.CNT:,.0f}명"
        f"(<span style='color:{DIRCOLOR[r.dir]}'>{r.dir}</span>)"
        for r in _mv.itertuples())
    insight(f"{ymlab(mm)} 가장 큰 이동 — {_txt}.")
c1, c2 = st.columns(2)
with c1:
    excl = st.checkbox("유지(대각) 제외", value=True, key="hk")
    h = mx[mx.FROM != mx.TO] if excl else mx
    piv = (h.pivot_table(index="FROM", columns="TO", values="CNT", aggfunc="sum")
             .reindex(index=ORDER, columns=ORDER))
    fig = px.imshow(piv, text_auto=",d", color_continuous_scale="Blues",
                    labels=dict(x="당월(TO)", y="전월(FROM)", color="명"))
    fig.update_layout(coloraxis_showscale=False)
    plot(fig, height=420, legend=False)
    st.caption("행=전월 등급, 열=당월 등급. 대각선=유지. 상위→하위 순.")
with c2:
    keep_in = st.checkbox("유지(머문 사람) 포함", value=False, key="sk_keep")
    s = mx if keep_in else mx[mx.FROM != mx.TO]
    L = {g: i for i, g in enumerate(ORDER)}
    R = {g: i + len(ORDER) for i, g in enumerate(ORDER)}
    # 승급=초록·하락=빨강·유지=해당 등급색 연하게
    lc = ["rgba(39,174,96,.55)" if d == "승급"
          else "rgba(231,76,60,.55)" if d == "하락"
          else _rgba(GCOLOR[f], .30)
          for d, f in zip(s["dir"], s["FROM"])]
    fig = go.Figure(go.Sankey(
        valueformat=",d", valuesuffix="명",      # 숫자 천단위 콤마(SI k/M 금지)
        node=dict(label=[f"{g}·전월" for g in ORDER] + [f"{g}·당월" for g in ORDER],
                  color=[GCOLOR[g] for g in ORDER] * 2, pad=14, thickness=16),
        link=dict(source=s["FROM"].map(L), target=s["TO"].map(R),
                  value=s["CNT"], color=lc)))
    fig.update_layout(font=dict(family=KFONT, size=11), height=420,
                      margin=dict(t=30, b=10, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True,
                    config={"displayModeBar": False})
    st.caption("좌=전월, 우=당월. 초록=승급·빨강=하락. 기본은 이동만 — "
               "'유지 포함' 켜면 머문 사람이 등급색(연하게)으로 함께 표시(규모 큼).")

# ── 등급별 수불 상세 (양식 정의) ──
section("7 · 심화: 등급 단위 수불 분해",
        "한 등급을 골라 그 달의 유효회원이 어떻게 구성됐는지 — "
        "유지·유입(승급/하락)·이탈(승급/하락)을 양식 정의대로 분해해 봅니다.",
        anchor="sec-detail")
gsel2 = st.selectbox(f"등급 선택 (기준월 {ymlab(mm)})", ORDER,
                     index=ORDER.index("BK"), format_func=lambda g: glabel[g],
                     key="gd2")
DIRC = {"승급": "#27AE60", "하락": "#E74C3C"}
row = gm[(gm.YM == mm) & (gm.GRADE == gsel2)].iloc[0]
kk = st.columns(4)
metric_card(kk[0], "유효회원 (유지+유입)", f"{row['유효회원']:,.0f}명", f"{ymlab(mm)} 당월")
metric_card(kk[1], "유지", f"{row['유지']:,.0f}명",
            f"유효회원의 {row['유지구성']*100:.0f}%")
metric_card(kk[2], "유입", f"{row['유입']:,.0f}명",
            f"유효회원의 {row['유입구성']*100:.0f}% · 승급 {row['유입_승급']:,.0f} / "
            f"하락 {row['유입_하락']:,.0f}")
metric_card(kk[3], "이탈", f"{row['이탈']:,.0f}명",
            f"전월유효의 {row['이탈률']*100:.0f}% · 승급 {row['이탈_승급']:,.0f} / "
            f"하락 {row['이탈_하락']:,.0f}")
cc1, cc2 = st.columns(2)
with cc1:
    sdf = (mx[(mx.TO == gsel2) & (mx.FROM != gsel2)]
           .groupby(["FROM", "dir"], as_index=False)["CNT"].sum())
    fig = px.bar(sdf, x="CNT", y="FROM", color="dir", orientation="h",
                 color_discrete_map=DIRC, category_orders={"FROM": ORDER},
                 labels=dict(CNT="명", FROM="전월 등급", dir="유형"))
    fig.update_layout(yaxis=dict(autorange="reversed"), legend_title="")
    fig.update_xaxes(tickformat=",d")
    plot(fig, height=320)
    st.caption(f"⬆ {gsel2} 유입 출처 — 초록=하위에서 승급, 빨강=상위에서 하락")
with cc2:
    ddf = (mx[(mx.FROM == gsel2) & (mx.TO != gsel2)]
           .groupby(["TO", "dir"], as_index=False)["CNT"].sum())
    fig = px.bar(ddf, x="CNT", y="TO", color="dir", orientation="h",
                 color_discrete_map=DIRC, category_orders={"TO": ORDER},
                 labels=dict(CNT="명", TO="당월 등급", dir="유형"))
    fig.update_layout(yaxis=dict(autorange="reversed"), legend_title="")
    fig.update_xaxes(tickformat=",d")
    plot(fig, height=320)
    st.caption(f"⬇ {gsel2} 이탈 행선지 — 초록=상위로 승급, 빨강=하위로 하락")
_net = row["순증"]
_g = NAME[gsel2]
insight(
    f"{ymlab(mm)} <b>{gsel2}({_g})</b>는 유입 {row['유입']:,.0f}명 / 이탈 "
    f"{row['이탈']:,.0f}명으로 순증 <b>{_net:+,.0f}명</b>. "
    + (f"유입의 {row['유입_승급']/row['유입']*100:.0f}%가 하위에서 올라온 승급" if row['유입']
       else "유입 없음")
    + (f", 이탈의 {row['이탈_하락']/row['이탈']*100:.0f}%가 하위로 내려간 하락입니다."
       if row['이탈'] else "."),
    "ok" if _net >= 0 else "warn")

# ════════ DAU/MAU 활성도 ════════
section("8 · 보조 단서: DAU/MAU 활성도",
        "RAW의 MAU/DAU를 등급·이동방향과 교차. 활성도가 잔존·승강과 어떻게 맞물리는지 "
        "보조 단서. Stickiness=DAU/MAU(높을수록 자주 방문).",
        anchor="sec-activity")
c1, c2 = st.columns(2)
with c1:
    asel = st.multiselect("등급", ORDER, default=["GD", "SV", "BK", "PP", "RD"],
                          format_func=lambda g: glabel[g], key="asel")
    sd = rng(sticky)[rng(sticky).GRADE.isin(asel)].sort_values("YM")
    fig = px.line(sd, x="LABEL", y="stickiness", color="GRADE", markers=True,
                  color_discrete_map=GCOLOR, category_orders={"GRADE": ORDER})
    fig.update_yaxes(tickformat=".0%")
    fig.update_layout(legend_title="등급")
    plot(fig, height=360)
    st.caption("등급별 당월유효(유입+유지) 인구의 DAU/MAU.")
with c2:
    ad = rng(actdir).sort_values("YM")
    fig = px.line(ad, x="LABEL", y="1인당MAU", color="dir", markers=True,
                  color_discrete_map={"승급": "#27AE60", "유지": "#2980B9",
                                      "하락": "#E74C3C"})
    fig.update_yaxes(tickformat=".0%")   # MAU/인원=월방문율(0~1)
    fig.update_layout(legend_title="이동", yaxis_title="월 방문율(MAU/인원)")
    plot(fig, height=360)
    st.caption("이동방향별 월 방문율(MAU/인원). 하락 코호트의 활성도가 낮다면 "
               "'활성 저하 → 하락' 선행지표로 활용 가능.")

cor = sticky.merge(gm[["YM", "GRADE", "잔존율"]], on=["YM", "GRADE"])
cor = rng(cor)
cor["GROUP"] = cor["GRADE"].map(lambda g: "VIP" if g in VIP_ALL else "일반")
fig = px.scatter(cor, x="stickiness", y="잔존율", color="GRADE", symbol="GROUP",
                 size="CUST", size_max=30, color_discrete_map=GCOLOR,
                 hover_data=["LABEL"], category_orders={"GRADE": ORDER})
fig.update_xaxes(tickformat=".0%", title="Stickiness (DAU/MAU)")
fig.update_yaxes(tickformat=".0%", title="잔존율(전월대비)")
plot(fig, height=440)
insight("우상향이면 <b>자주 오는 등급일수록 잘 남는다</b> → 활성도 부스팅이 곧 잔존율 "
        "방어. 버블=인원, 모양=VIP/일반.")
st.caption("ⓘ SP·PT(연1회 고정)는 월 유지율 집계 제외 — 활성도 차트에는 선택 시 표시됩니다.")
