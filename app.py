# -*- coding: utf-8 -*-
"""VIP 등급 수불 대시보드
3대 축: (1) 수불·전환 진단  (2) 이동 방향성(From→To)  (3) DAU/MAU 활성도 교차
데이터: data/*.csv (convert.ps1 이 원본 xlsx 에서 추출). 원본은 사내 DRM-free 템플릿.
"""
from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="VIP 등급 수불 대시보드", page_icon="📊", layout="wide")
DATA = Path(__file__).parent / "data"

# ── 등급 체계 (승급/하락 방향에서 역산: RD<PP<BK<SV<GD<PT<SP) ──
GRADE_ORDER = ["RD", "PP", "BK", "SV", "GD", "PT", "SP"]
GRADE_NAME = {"RD": "Red", "PP": "Purple", "BK": "Black", "SV": "Silver",
              "GD": "Gold", "PT": "Platinum", "SP": "S-Platinum"}
VIP_CODES = {"BK", "SV", "GD", "PT", "SP"}
NORMAL_CODES = {"PP", "RD"}
GRADE_COLOR = {"RD": "#C0392B", "PP": "#8E44AD", "BK": "#2C3E50", "SV": "#95A5A6",
               "GD": "#D4AC0D", "PT": "#16A085", "SP": "#2980B9"}
MOVE_COLOR = {"승급": "#27AE60", "하락": "#E74C3C", "유지": "#95A5A6"}
BROKEN_YM = "202508"  # 이탈 레코드 누락월(유지율 100%로 왜곡)


def ym_label(ym: str) -> str:
    s = str(ym)
    return f"{s[2:4]}-{s[4:6]}"


@st.cache_data
def load():
    def rd(name):
        return pd.read_csv(DATA / name, dtype={"YM": str, "CURR_STD_YM": str})
    raw = rd("raw_grade.csv")
    monthly = rd("monthly_grade.csv")
    vvn = rd("vip_vs_normal.csv")
    conv = rd("conversion.csv")
    growth = rd("vip_growth.csv")
    matrix = rd("move_matrix.csv")
    for df, col in [(raw, "CURR_STD_YM"), (monthly, "YM"), (vvn, "YM"),
                    (conv, "YM"), (growth, "YM"), (matrix, "YM")]:
        df["LABEL"] = df[col].map(ym_label)
    return raw, monthly, vvn, conv, growth, matrix


raw, monthly, vvn, conv, growth, matrix = load()
ALL_YM = sorted(monthly["YM"].unique())

# ── 사이드바 ──
st.sidebar.title("⚙️ 필터")
ym_min, ym_max = st.sidebar.select_slider(
    "기간(월)", options=ALL_YM, value=(ALL_YM[0], ALL_YM[-1]),
    format_func=ym_label)
fix_broken = st.sidebar.checkbox(
    f"{ym_label(BROKEN_YM)} 보정(이탈 누락월 비율차트 제외)", value=True)
st.sidebar.caption(
    "※ 202508 은 원본에 '이탈' 레코드가 없어 유지율이 100%로 튑니다. "
    "보정 ON 시 비율 추세에서 제외합니다.")


def in_range(df, col="YM"):
    return df[(df[col] >= ym_min) & (df[col] <= ym_max)].copy()


def drop_broken(df, col="YM"):
    if fix_broken:
        return df[df[col] != BROKEN_YM]
    return df


st.title("📊 VIP 등급 수불 대시보드")
st.caption(f"기간 {ym_label(ym_min)} ~ {ym_label(ym_max)} · 등급 RD<PP<BK<SV<GD<PT<SP "
           "(Black=VIP 진입티어, S-Platinum=최상위)")

tab1, tab2, tab3 = st.tabs(
    ["① 수불·전환 진단", "② 이동 방향성 (From→To)", "③ DAU/MAU 활성도 교차"])

# ════════════════════════════════════════════════════════════════
# ① 수불·전환 진단
# ════════════════════════════════════════════════════════════════
with tab1:
    latest = ym_max
    vv = vvn[vvn["YM"] == latest]
    g = growth[growth["YM"] == latest]
    c = conv[conv["YM"] == latest]
    vip_ret = vv[vv["GROUP"] == "VIP"]["유지율"].iloc[0] if len(vv) else float("nan")
    nor_ret = vv[vv["GROUP"] == "일반"]["유지율"].iloc[0] if len(vv) else float("nan")
    conv_rate = c["전환율"].iloc[0] if len(c) else float("nan")
    vip_net = g["VIP_순증(명)"].iloc[0] if len(g) else float("nan")
    need_new = g["현실성장_필요신규(명)"].iloc[0] if len(g) else float("nan")

    st.subheader(f"📌 최신월 {ym_label(latest)} 핵심지표")
    k = st.columns(5)
    k[0].metric("VIP 유지율", f"{vip_ret*100:.1f}%")
    k[1].metric("일반 유지율", f"{nor_ret*100:.1f}%")
    k[2].metric("일반→VIP 전환율", f"{conv_rate*100:.2f}%")
    k[3].metric("VIP 순증", f"{vip_net:,.0f}명",
                delta=None if pd.isna(vip_net) else f"{vip_net:+,.0f}")
    k[4].metric("현실성장 필요신규", f"{need_new:,.0f}명/월")

    st.divider()
    c1, c2 = st.columns(2)

    # 등급별 비율 추세
    with c1:
        st.markdown("**등급별 수불 추세**")
        metric = st.radio("지표", ["유지율", "유입률", "이탈률"], horizontal=True,
                          key="m1")
        sel = st.multiselect("등급", GRADE_ORDER, default=GRADE_ORDER,
                             format_func=lambda x: f"{x} {GRADE_NAME[x]}")
        md = drop_broken(in_range(monthly))
        md = md[md["GRADE"].isin(sel)]
        fig = px.line(md.sort_values("YM"), x="LABEL", y=metric, color="GRADE",
                      markers=True, color_discrete_map=GRADE_COLOR,
                      category_orders={"GRADE": GRADE_ORDER})
        fig.update_yaxes(tickformat=".0%")
        fig.update_layout(height=380, legend_title="등급",
                          margin=dict(t=10, b=0, l=0, r=0))
        st.plotly_chart(fig, use_container_width=True)

    # VIP vs 일반
    with c2:
        st.markdown("**VIP vs 일반 잔존력**")
        vd = drop_broken(in_range(vvn))
        fig = px.line(vd.sort_values("YM"), x="LABEL", y="유지율", color="GROUP",
                      markers=True,
                      color_discrete_map={"VIP": "#2980B9", "일반": "#E67E22"})
        fig.update_yaxes(tickformat=".0%")
        fig.update_layout(height=200, margin=dict(t=10, b=0, l=0, r=0),
                          legend_title="")
        st.plotly_chart(fig, use_container_width=True)
        fig2 = px.bar(in_range(vvn).sort_values("YM"), x="LABEL", y="순증",
                      color="GROUP", barmode="group",
                      color_discrete_map={"VIP": "#2980B9", "일반": "#E67E22"})
        fig2.update_layout(height=170, margin=dict(t=10, b=0, l=0, r=0),
                           legend_title="", title_text="")
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    c3, c4 = st.columns(2)

    # 일반→VIP 전환 + 일반내 대사
    with c3:
        st.markdown("**일반→VIP 전환율 & 일반 내부 대사비중**")
        cd = in_range(conv).sort_values("YM")
        fig = go.Figure()
        fig.add_bar(x=cd["LABEL"], y=cd["전환율"], name="일반→VIP 전환율",
                    marker_color="#27AE60", yaxis="y")
        fig.add_scatter(x=cd["LABEL"], y=cd["일반내 대사비중"], name="일반내 대사비중",
                        mode="lines+markers", marker_color="#C0392B", yaxis="y2")
        fig.update_layout(
            height=360, margin=dict(t=10, b=0, l=0, r=0),
            yaxis=dict(title="전환율", tickformat=".2%"),
            yaxis2=dict(title="대사비중", overlaying="y", side="right",
                        tickformat=".0%", range=[0.95, 1.0]),
            legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig, use_container_width=True)
        st.info("일반 등급 인원의 **약 99.3%가 RD↔PP 내부에서만** 순환합니다. "
                "VIP로 올라오는 비율은 0.2~0.3%대 → **핵심 Pain Point**.")

    # 필요신규 시나리오
    with c4:
        st.markdown("**VIP 순증 & 필요신규 시나리오**")
        gd = in_range(growth).sort_values("YM")
        fig = go.Figure()
        fig.add_bar(x=gd["LABEL"], y=gd["VIP_순증(명)"], name="VIP 순증",
                    marker_color="#34495E")
        for col, color in [("VIP_유지목표_필요신규(명)", "#95A5A6"),
                           ("현실성장_필요신규(명)", "#2980B9"),
                           ("공격성장(+2%p)_필요신규(명)", "#E74C3C")]:
            fig.add_scatter(x=gd["LABEL"], y=gd[col], name=col.replace("_필요신규(명)", ""),
                            mode="lines+markers")
        fig.update_layout(height=360, margin=dict(t=10, b=0, l=0, r=0),
                          legend=dict(orientation="h", y=1.12),
                          yaxis_title="명")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("필요신규 = VIP 등급 유지/성장을 위해 매월 새로 유입돼야 하는 인원.")

# ════════════════════════════════════════════════════════════════
# ② 이동 방향성
# ════════════════════════════════════════════════════════════════
with tab2:
    msel = st.select_slider("기준월", options=ALL_YM, value=ym_max,
                            format_func=ym_label, key="msel")
    mx = matrix[matrix["YM"] == msel].copy()
    st.subheader(f"🔀 {ym_label(msel)} 등급 이동 흐름")

    c1, c2 = st.columns([1, 1])
    # 히트맵 (전월 FROM × 당월 TO), 유지(대각) 제외 옵션
    with c1:
        st.markdown("**전이 히트맵** (행=전월, 열=당월)")
        excl_keep = st.checkbox("유지(대각선) 제외", value=True, key="hk")
        h = mx.copy()
        if excl_keep:
            h = h[h["FROM_CD"] != h["TO_CD"]]
        piv = (h.pivot_table(index="FROM_CD", columns="TO_CD", values="CNT",
                             aggfunc="sum")
                 .reindex(index=GRADE_ORDER, columns=GRADE_ORDER))
        fig = px.imshow(piv, text_auto=",.0f", color_continuous_scale="Blues",
                        labels=dict(x="당월(TO)", y="전월(FROM)", color="인원"))
        fig.update_layout(height=420, margin=dict(t=10, b=0, l=0, r=0),
                          coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

    # Sankey
    with c2:
        st.markdown("**이동 Sankey** (전월→당월)")
        only_move = st.checkbox("유지 흐름 제외", value=True, key="sk")
        s = mx.copy()
        if only_move:
            s = s[s["FROM_CD"] != s["TO_CD"]]
        left = {g: i for i, g in enumerate(GRADE_ORDER)}
        right = {g: i + len(GRADE_ORDER) for i, g in enumerate(GRADE_ORDER)}
        labels = ([f"{g}·전월" for g in GRADE_ORDER] +
                  [f"{g}·당월" for g in GRADE_ORDER])
        node_color = [GRADE_COLOR[g] for g in GRADE_ORDER] * 2
        link_color = s["MOVE_TYPE"].map(
            {"승급": "rgba(39,174,96,.45)", "하락": "rgba(231,76,60,.45)",
             "유지": "rgba(149,165,166,.35)"}).fillna("rgba(150,150,150,.3)")
        fig = go.Figure(go.Sankey(
            node=dict(label=labels, color=node_color, pad=12, thickness=14),
            link=dict(source=s["FROM_CD"].map(left),
                      target=s["TO_CD"].map(right),
                      value=s["CNT"], color=link_color)))
        fig.update_layout(height=420, margin=dict(t=10, b=0, l=0, r=0),
                          font_size=11)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.markdown("**등급별 유입 출처 / 이탈 행선지**")
    gsel = st.selectbox("등급 선택", GRADE_ORDER, index=GRADE_ORDER.index("BK"),
                        format_func=lambda x: f"{x} {GRADE_NAME[x]}")
    cc1, cc2 = st.columns(2)
    with cc1:
        src = mx[(mx["TO_CD"] == gsel) & (mx["FROM_CD"] != gsel)]
        src = src.groupby("FROM_CD")["CNT"].sum().reindex(GRADE_ORDER).dropna()
        fig = px.bar(x=src.values, y=src.index, orientation="h",
                     color=src.index, color_discrete_map=GRADE_COLOR,
                     labels=dict(x="인원", y="전월 등급"))
        fig.update_layout(height=300, showlegend=False,
                          title=f"⬆ {gsel} 유입 출처", margin=dict(t=30, b=0))
        st.plotly_chart(fig, use_container_width=True)
    with cc2:
        dst = mx[(mx["FROM_CD"] == gsel) & (mx["TO_CD"] != gsel)]
        dst = dst.groupby("TO_CD")["CNT"].sum().reindex(GRADE_ORDER).dropna()
        fig = px.bar(x=dst.values, y=dst.index, orientation="h",
                     color=dst.index, color_discrete_map=GRADE_COLOR,
                     labels=dict(x="인원", y="당월 등급"))
        fig.update_layout(height=300, showlegend=False,
                          title=f"⬇ {gsel} 이탈 행선지", margin=dict(t=30, b=0))
        st.plotly_chart(fig, use_container_width=True)

# ════════════════════════════════════════════════════════════════
# ③ DAU/MAU 활성도 교차
# ════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("📱 등급 이동 × 활성도 (DAU/MAU)")
    st.caption("원본 RAW 의 MAU/DAU 를 등급·이동유형과 교차. "
               "Stickiness = DAU/MAU (높을수록 자주 방문).")
    rraw = raw[(raw["CURR_STD_YM"] >= ym_min) & (raw["CURR_STD_YM"] <= ym_max)].copy()

    # 현재월 활성 인구 = 유입+유지 (당월유효), CURR 등급 기준
    cur = rraw[rraw["GRAD_STATUS"].isin(["유입", "유지"])]
    sticky = (cur.groupby(["CURR_STD_YM", "LABEL", "CURR_NLINE_MEM_GRAD_CD"])
                 .agg(MAU=("MAU", "sum"), DAU=("DAU", "sum"),
                      CUST=("CUST_CNT", "sum")).reset_index())
    sticky["stickiness"] = sticky["DAU"] / sticky["MAU"]
    sticky = sticky.rename(columns={"CURR_NLINE_MEM_GRAD_CD": "GRADE"})

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**등급별 Stickiness(DAU/MAU) 추세**")
        sel = st.multiselect("등급", GRADE_ORDER, default=["BK", "SV", "GD", "PP", "RD"],
                             format_func=lambda x: f"{x} {GRADE_NAME[x]}", key="s3")
        sd = sticky[sticky["GRADE"].isin(sel)].sort_values("CURR_STD_YM")
        fig = px.line(sd, x="LABEL", y="stickiness", color="GRADE", markers=True,
                      color_discrete_map=GRADE_COLOR,
                      category_orders={"GRADE": GRADE_ORDER})
        fig.update_yaxes(tickformat=".0%")
        fig.update_layout(height=380, margin=dict(t=10, b=0, l=0, r=0),
                          legend_title="등급")
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown("**이동유형별 활성도** (승급 vs 유지 vs 이탈)")
        by = (rraw.groupby(["CURR_STD_YM", "LABEL", "GRAD_STATUS"])
                  .agg(MAU=("MAU", "sum"), DAU=("DAU", "sum"),
                       CUST=("CUST_CNT", "sum")).reset_index())
        by["1인당 MAU"] = by["MAU"] / by["CUST"]
        bd = drop_broken(by, "CURR_STD_YM").sort_values("CURR_STD_YM")
        fig = px.line(bd, x="LABEL", y="1인당 MAU", color="GRAD_STATUS",
                      markers=True,
                      color_discrete_map={"유입": "#27AE60", "유지": "#2980B9",
                                          "이탈": "#E74C3C"})
        fig.update_layout(height=380, margin=dict(t=10, b=0, l=0, r=0),
                          legend_title="")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("1인당 MAU = 코호트 MAU 합 / 인원. 이탈 코호트의 활성도가 "
                   "유지·유입 대비 낮다면 '활성도 저하 → 이탈' 선행지표로 활용 가능.")

    st.divider()
    st.markdown("**활성도 ↔ 유지율 상관** (등급·월 단위)")
    mm = monthly[["YM", "GRADE", "유지율"]]
    corr = sticky.merge(mm, left_on=["CURR_STD_YM", "GRADE"],
                        right_on=["YM", "GRADE"], how="inner")
    corr = drop_broken(corr, "CURR_STD_YM")
    corr["GROUP"] = corr["GRADE"].map(
        lambda g: "VIP" if g in VIP_CODES else "일반")
    fig = px.scatter(corr, x="stickiness", y="유지율", color="GRADE",
                     symbol="GROUP", size="CUST", size_max=28,
                     color_discrete_map=GRADE_COLOR, hover_data=["LABEL"],
                     category_orders={"GRADE": GRADE_ORDER})
    fig.update_xaxes(tickformat=".0%", title="Stickiness (DAU/MAU)")
    fig.update_yaxes(tickformat=".0%", title="유지율")
    fig.update_layout(height=440, margin=dict(t=10, b=0, l=0, r=0))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("우상향 분포라면 '자주 오는 등급일수록 잘 남는다' → 활성도 부스팅이 "
               "곧 유지율 방어. 버블 크기=인원.")
