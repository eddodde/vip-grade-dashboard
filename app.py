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
    fig.update_layout(font=dict(family=KFONT), height=height,
                      margin=dict(t=24, b=10, l=10, r=10),
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0)
                      if legend else dict())
    st.plotly_chart(fig, use_container_width=True)


def ymlab(ym):
    s = str(ym)
    return f"{s[2:4]}-{s[4:6]}"


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


@st.cache_data(show_spinner=False)
def load_and_build(uploaded: bytes | None):
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

    idx = pd.MultiIndex.from_product([yms, ORDER], names=["YM", "GRADE"])
    gm = pd.DataFrame(index=idx)
    gm["유지"] = keep.reindex(idx, fill_value=0)
    gm["유입"] = inf.reindex(idx, fill_value=0)
    gm["이탈"] = out.reindex(idx, fill_value=0)
    gm = gm.reset_index()
    gm["전월유효"] = gm["유지"] + gm["이탈"]
    gm["당월유효"] = gm["유지"] + gm["유입"]
    gm["순증"] = gm["유입"] - gm["이탈"]
    for r, num, den in [("유지율", "유지", "전월유효"), ("유입률", "유입", "전월유효"),
                        ("이탈률", "이탈", "전월유효")]:
        gm[r] = gm[num] / gm[den].where(gm[den] != 0)
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

    for d in (gm, flowdir, group, conv, sticky, actdir, mat):
        d["LABEL"] = d["YM"].map(ymlab)
    return dict(gm=gm, flowdir=flowdir, group=group, conv=conv, mat=mat,
                sticky=sticky, actdir=actdir, yms=yms)


# ── 사이드바: 업로드 · 목차 · 필터 ──────────────────────────
with st.sidebar:
    st.header("⚙️ 설정")
    with st.expander("📤 원본 올리기 (월 갱신)", expanded=False):
        st.caption("원본 **VIP_등급수불 xlsx** 를 그대로 올리면 git push 없이 "
                   "RAW_입력 시트를 읽어 즉시 재계산합니다. (또는 convert.ps1 로 "
                   "data/raw_grade.csv 갱신 후 push)")
        up = st.file_uploader("등급수불 원본 (xlsx)", type=["xlsx"], key="up")

try:
    B = load_and_build(up.getvalue() if up else None)
except Exception as e:
    st.error(f"데이터를 읽는 중 오류: {e}")
    st.stop()

gm, flowdir, group, conv = B["gm"], B["flowdir"], B["group"], B["conv"]
mat, sticky, actdir, YMS = B["mat"], B["sticky"], B["actdir"], B["yms"]

MENU = [("sec-summary", "핵심 요약"), ("sec-flow", "수불 한눈에 (승급·유지·하락)"),
        ("sec-grade", "등급별 수불 추세"), ("sec-group", "VIP vs 일반"),
        ("sec-conv", "일반→VIP 전환 & 내부 대사"),
        ("sec-matrix", "이동 방향성 (From→To)"),
        ("sec-activity", "DAU/MAU 활성도 교차")]
with st.sidebar:
    st.markdown("#### 📑 목차")
    st.markdown("".join(f'<a href="#{a}" class="navlink">{l}</a>'
                        for a, l in MENU), unsafe_allow_html=True)
    st.markdown("#### 🔎 기간")
    ym0, ym1 = st.select_slider("기간(월)", options=YMS, value=(YMS[0], YMS[-1]),
                                format_func=ymlab)
    src = "업로드 원본" if up else "커밋된 data/raw_grade.csv"
    st.caption(f"데이터 출처: **{src}** · {len(YMS)}개월")
    st.caption("등급: SP·PT·GD·SV·BK(=VIP) / PP·RD(=일반). "
               "**SP·PT는 연1회(1/1) 고정**이라 VIP 유지율 집계에서 제외.")


def rng(df, col="YM"):
    return df[(df[col] >= ym0) & (df[col] <= ym1)].copy()


def metric_card(col, label, value, sub=""):
    col.markdown(
        f'<div class="metric-card"><div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value}</div>'
        f'<div class="metric-sub">{sub}</div></div>', unsafe_allow_html=True)


st.title("📊 VIP 등급 수불 대시보드")
st.caption(f"기간 {ymlab(ym0)} ~ {ymlab(ym1)} · 모든 수치는 RAW에서 직접 산출 "
           "(유입+유지 단일기입 전이모델)")

# ════════ 핵심 요약 ════════
section("핵심 요약", f"최신월 {ymlab(ym1)} 기준 · VIP 유지율은 SP·PT 제외",
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
section("수불 한눈에 — 승급 · 유지 · 하락",
        "전월→당월 등급 이동을 한 장으로. 유지는 규모가 커서 별도 축으로 표시.",
        anchor="sec-flow")
c1, c2 = st.columns([3, 2])
with c1:
    fdr = rng(flowdir).sort_values("YM")
    fig = go.Figure()
    fig.add_bar(x=fdr["LABEL"], y=fdr["승급"], name="승급", marker_color="#27AE60")
    fig.add_bar(x=fdr["LABEL"], y=-fdr["하락"], name="하락", marker_color="#E74C3C")
    fig.add_scatter(x=fdr["LABEL"], y=fdr["승급"] - fdr["하락"], name="순이동(승급-하락)",
                    mode="lines+markers", line=dict(color="#2C3E50", width=2))
    fig.update_layout(barmode="relative", yaxis_title="명 (위=승급, 아래=하락)")
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
    plot(fig, height=360)
    st.caption(f"{ymlab(msel)} 등급별 유입(+)·이탈(−). 상위→하위 순.")

# ════════ 등급별 수불 추세 ════════
section("등급별 수불 추세", "등급별 유지율·유입률·이탈률 (상위→하위)",
        anchor="sec-grade")
c1, c2 = st.columns([1, 3])
with c1:
    metric = st.radio("지표", ["유지율", "유입률", "이탈률", "순증"], key="gmet")
    gsel = st.multiselect("등급", ORDER, default=ORDER,
                          format_func=lambda g: glabel[g], key="gsel")
with c2:
    gd = rng(gm)
    gd = gd[gd.GRADE.isin(gsel)].sort_values("YM")
    fig = px.line(gd, x="LABEL", y=metric, color="GRADE", markers=True,
                  color_discrete_map=GCOLOR, category_orders={"GRADE": ORDER})
    if metric != "순증":
        fig.update_yaxes(tickformat=".0%")
    fig.update_layout(legend_title="등급")
    plot(fig, height=380)
insight("VIP 등급(BK·SV·GD)은 유지율 ~85%로 월변동이 크고, <b>RD(Red)는 ~99.6%</b>로 "
        "사실상 고착. SP·PT는 연1회 고정등급이라 월 단위 유지율 해석에서 제외했습니다.")

# ════════ VIP vs 일반 ════════
section("VIP vs 일반 잔존력", "VIP는 SP·PT 제외(BK·SV·GD). 유지율·순증 비교",
        anchor="sec-group")
GC = {"VIP(SP·PT제외)": "#2C5F8A", "일반": "#E67E22"}
c1, c2 = st.columns(2)
with c1:
    gr = rng(group).sort_values("YM")
    fig = px.line(gr, x="LABEL", y="유지율", color="GROUP", markers=True,
                  color_discrete_map=GC)
    fig.update_yaxes(tickformat=".0%")
    fig.update_layout(legend_title="")
    plot(fig, height=340)
with c2:
    fig = px.bar(rng(group).sort_values("YM"), x="LABEL", y="순증", color="GROUP",
                 barmode="group", color_discrete_map=GC)
    fig.update_layout(legend_title="")
    plot(fig, height=340)
insight("VIP(SP·PT 제외) 유지율 ~80% vs 일반 ~99%. VIP는 구조적으로 변동성이 크고 "
        "순증이 거의 매월 마이너스 — <b>유입 강화가 없으면 자연 감소</b>.", "warn")

# ════════ 전환 & 내부 대사 ════════
section("일반→VIP 전환 & 일반 내부 대사",
        "일반 고객이 VIP로 올라오는 비율 vs 일반(RD·PP) 안에서만 도는 비율",
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
insight(f"일반 고객의 <b>약 {conv['대사비중'].mean()*100:.1f}%가 RD↔PP 내부에서만</b> "
        f"순환하고, VIP로 올라오는 전환율은 평균 <b>{avg_conv*100:.2f}%</b>에 불과 — "
        "핵심 Pain Point. 일반 상위(PP)를 겨냥한 승급 부스팅 장치가 필요합니다.", "warn")

# ════════ 이동 방향성 ════════
section("이동 방향성 (From → To)",
        "전월→당월 등급 전이. 단일기입(이중계상 제거)으로 실제 이동 인원.",
        anchor="sec-matrix")
mm = st.select_slider("기준월", options=YMS, value=ym1, format_func=ymlab,
                      key="mxm")
mx = mat[mat.YM == mm]
c1, c2 = st.columns(2)
with c1:
    excl = st.checkbox("유지(대각) 제외", value=True, key="hk")
    h = mx[mx.FROM != mx.TO] if excl else mx
    piv = (h.pivot_table(index="FROM", columns="TO", values="CNT", aggfunc="sum")
             .reindex(index=ORDER, columns=ORDER))
    fig = px.imshow(piv, text_auto=",.0f", color_continuous_scale="Blues",
                    labels=dict(x="당월(TO)", y="전월(FROM)", color="명"))
    fig.update_layout(coloraxis_showscale=False)
    plot(fig, height=420, legend=False)
    st.caption("행=전월 등급, 열=당월 등급. 상위→하위 순.")
with c2:
    s = mx[mx.FROM != mx.TO]
    L = {g: i for i, g in enumerate(ORDER)}
    R = {g: i + len(ORDER) for i, g in enumerate(ORDER)}
    lc = s["dir"].map({"승급": "rgba(39,174,96,.45)", "하락": "rgba(231,76,60,.45)"})
    fig = go.Figure(go.Sankey(
        node=dict(label=[f"{g}·전월" for g in ORDER] + [f"{g}·당월" for g in ORDER],
                  color=[GCOLOR[g] for g in ORDER] * 2, pad=12, thickness=14),
        link=dict(source=s["FROM"].map(L), target=s["TO"].map(R),
                  value=s["CNT"], color=lc)))
    fig.update_layout(font=dict(family=KFONT, size=11), height=420,
                      margin=dict(t=24, b=10, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("좌=전월, 우=당월. 초록=승급, 빨강=하락 흐름.")

st.markdown("**등급별 유입 출처 / 이탈 행선지**")
gsel2 = st.selectbox("등급", ORDER, index=ORDER.index("BK"),
                     format_func=lambda g: glabel[g], key="gd2")
cc1, cc2 = st.columns(2)
with cc1:
    src_ = (mx[(mx.TO == gsel2) & (mx.FROM != gsel2)].groupby("FROM")["CNT"].sum()
            .reindex(ORDER).dropna())
    fig = px.bar(x=src_.values, y=src_.index, orientation="h", color=src_.index,
                 color_discrete_map=GCOLOR, labels=dict(x="명", y="전월"))
    fig.update_layout(yaxis=dict(autorange="reversed"), showlegend=False,
                      title=f"⬆ {gsel2} 유입 출처")
    plot(fig, height=300, legend=False)
with cc2:
    dst_ = (mx[(mx.FROM == gsel2) & (mx.TO != gsel2)].groupby("TO")["CNT"].sum()
            .reindex(ORDER).dropna())
    fig = px.bar(x=dst_.values, y=dst_.index, orientation="h", color=dst_.index,
                 color_discrete_map=GCOLOR, labels=dict(x="명", y="당월"))
    fig.update_layout(yaxis=dict(autorange="reversed"), showlegend=False,
                      title=f"⬇ {gsel2} 이탈 행선지")
    plot(fig, height=300, legend=False)

# ════════ DAU/MAU 활성도 ════════
section("DAU/MAU 활성도 교차",
        "RAW의 MAU/DAU를 등급·이동방향과 교차. Stickiness=DAU/MAU(높을수록 자주 방문).",
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
    fig.update_layout(legend_title="이동")
    plot(fig, height=360)
    st.caption("이동방향별 1인당 MAU. 하락 코호트의 활성도가 낮다면 "
               "'활성 저하 → 하락' 선행지표로 활용 가능.")

cor = sticky.merge(gm[["YM", "GRADE", "유지율"]], on=["YM", "GRADE"])
cor = rng(cor)
cor["GROUP"] = cor["GRADE"].map(lambda g: "VIP" if g in VIP_ALL else "일반")
fig = px.scatter(cor, x="stickiness", y="유지율", color="GRADE", symbol="GROUP",
                 size="CUST", size_max=30, color_discrete_map=GCOLOR,
                 hover_data=["LABEL"], category_orders={"GRADE": ORDER})
fig.update_xaxes(tickformat=".0%", title="Stickiness (DAU/MAU)")
fig.update_yaxes(tickformat=".0%", title="유지율")
plot(fig, height=440)
insight("우상향이면 <b>자주 오는 등급일수록 잘 남는다</b> → 활성도 부스팅이 곧 유지율 "
        "방어. 버블=인원, 모양=VIP/일반.")
st.caption("ⓘ SP·PT(연1회 고정)는 월 유지율 집계 제외 — 활성도 차트에는 선택 시 표시됩니다.")
