import streamlit as st
import pandas as pd
import altair as alt
import math

st.set_page_config(page_title="Hanwoo Breeding CBA (v0.2)", layout="wide")


# ---------------------------
# Helpers
# ---------------------------
def clamp_int(x, lo=0):
    try:
        return max(lo, int(x))
    except Exception:
        return lo


def fmt_int(x):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "-"
    return f"{int(round(x)):,.0f}"


def fmt_money(x):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "-"
    return f"{x:,.0f}"


def fmt_float(x, nd=4):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "-"
    return f"{x:,.{nd}f}"


def stage_cost_per_head(
    calf_common_months: int,
    ship_months: int,
    cost_rearing_y: float,
    cost_fatten_early_y: float,
    cost_fatten_late_y: float,
):
    """
    비용 입력 단위: 원/년/두
    기간 단위: 개월

    구조:
    - 송아지 공통 육성기간(개월): calf_common_months
    - 육성기(송아지 이후~12개월령): (12 - calf_common_months) 개월
    - 비육전기: 13~18개월령 = 6개월
    - 비육후기: 19개월령~출하 = (ship_months - 18) 개월
    """
    calf_common_months = clamp_int(calf_common_months, 0)
    ship_months = clamp_int(ship_months, 0)

    months_rearing = max(0, 12 - calf_common_months)

    months_early = 0
    if ship_months >= 13:
        months_early = min(6, max(0, ship_months - 12))

    months_late = max(0, ship_months - 18)

    cost = (
        cost_rearing_y * (months_rearing / 12.0)
        + cost_fatten_early_y * (months_early / 12.0)
        + cost_fatten_late_y * (months_late / 12.0)
    )

    return {
        "months_rearing": months_rearing,
        "months_early": months_early,
        "months_late": months_late,
        "cost_per_head": cost,
    }


def compute_scenario(
    name: str,
    base_cows: int,
    conception_rate: float,        # 0~1
    female_birth_ratio: float,     # 0~1
    annual_culls: int,             # heads/year  (Scenario-specific!)
    heifer_nonprofit_months: int,  # months
    calf_common_months: int,       # months
    kpn_exit_months: int,          # months
    # allocations (heads/year)
    female_calf_sell: int,
    female_fatten_in: int,
    male_calf_sell: int,
    male_fatten_in: int,
    kpn_male: int,
    # costs (KRW/head/year)
    cow_cost_y: float,
    cost_rearing_y: float,
    cost_fatten_early_y: float,
    cost_fatten_late_y: float,
    # prices (KRW/head)
    price_calf_female: float,
    price_calf_male: float,
    price_fatten_female: float,
    price_fatten_male: float,
    price_cull_cow: float,
    # shipping ages (months)
    ship_m_female: int,
    ship_m_male: int,
):
    base_cows = clamp_int(base_cows, 1)
    annual_culls = clamp_int(annual_culls, 0)

    # replacements fixed = annual_culls (per your rule)
    replacements_female = annual_culls

    # births per year (annual 1-calving assumption)
    births_total = base_cows * float(conception_rate)
    births_female = births_total * float(female_birth_ratio)
    births_male = births_total * (1.0 - float(female_birth_ratio))

    # allocations
    female_use_total = replacements_female + clamp_int(female_calf_sell) + clamp_int(female_fatten_in)
    male_use_total = clamp_int(kpn_male) + clamp_int(male_calf_sell) + clamp_int(male_fatten_in)

    issues = []

    # 0~1 checks
    if not (0.0 <= conception_rate <= 1.0):
        issues.append("수태율(conception_rate)은 0~1 범위여야 합니다.")
    if not (0.0 <= female_birth_ratio <= 1.0):
        issues.append("암송아지 출생 비율(female_birth_ratio)은 0~1 범위여야 합니다.")

    # ship age checks
    if ship_m_female < 19:
        issues.append(f"암 비육우 출하 월령은 19개월 이상 권장 (현재: {ship_m_female})")
    if ship_m_male < 19:
        issues.append(f"수 비육우 출하 월령은 19개월 이상 권장 (현재: {ship_m_male})")

    # replacement feasibility
    if replacements_female > births_female + 1e-9:
        issues.append(
            f"대체우 선발(=연간 도태두수) {replacements_female}두가 "
            f"연간 암 출생두수 {births_female:.2f}두를 초과합니다."
        )

    # allocations feasibility
    if female_use_total > births_female + 1e-9:
        issues.append(
            f"[암] (대체우 {replacements_female} + 암 송아지 판매 {female_calf_sell} + 암 비육투입 {female_fatten_in}) = {female_use_total}두가 "
            f"연간 암 출생두수 {births_female:.2f}두를 초과합니다."
        )

    if male_use_total > births_male + 1e-9:
        issues.append(
            f"[수] (KPN {kpn_male} + 수 송아지 판매 {male_calf_sell} + 수 비육투입 {male_fatten_in}) = {male_use_total}두가 "
            f"연간 수 출생두수 {births_male:.2f}두를 초과합니다."
        )

    # --- Derived indicators
    replacement_rate = (annual_culls / base_cows) if base_cows > 0 else 0.0

    # Replacement heifer stock (heads)
    heifer_nonprofit_years = clamp_int(heifer_nonprofit_months, 0) / 12.0
    repl_stock = annual_culls * heifer_nonprofit_years
    repl_stock_cost_y = repl_stock * cow_cost_y

    # Breeding cows annual maintenance cost
    breeding_cost_y = base_cows * cow_cost_y

    # Calf production cost (per head) — indicator & KPN loss basis
    if conception_rate > 1e-12:
        calf_prod_cost_per_head = cow_cost_y / conception_rate
    else:
        calf_prod_cost_per_head = float("inf")

    # KPN loss: cost only (no revenue), based on calf production cost scaled by months until taken
    kpn_loss = 0.0
    if math.isfinite(calf_prod_cost_per_head):
        kpn_loss = clamp_int(kpn_male) * calf_prod_cost_per_head * (clamp_int(kpn_exit_months, 0) / 12.0)

    # Fattening costs
    female_fatten_info = stage_cost_per_head(
        calf_common_months=calf_common_months,
        ship_months=ship_m_female,
        cost_rearing_y=cost_rearing_y,
        cost_fatten_early_y=cost_fatten_early_y,
        cost_fatten_late_y=cost_fatten_late_y,
    )
    male_fatten_info = stage_cost_per_head(
        calf_common_months=calf_common_months,
        ship_months=ship_m_male,
        cost_rearing_y=cost_rearing_y,
        cost_fatten_early_y=cost_fatten_early_y,
        cost_fatten_late_y=cost_fatten_late_y,
    )

    fatten_cost_total = (
        clamp_int(female_fatten_in) * female_fatten_info["cost_per_head"]
        + clamp_int(male_fatten_in) * male_fatten_info["cost_per_head"]
    )

    # Revenues
    rev_cull = annual_culls * price_cull_cow
    rev_calf = clamp_int(female_calf_sell) * price_calf_female + clamp_int(male_calf_sell) * price_calf_male
    rev_fatten = clamp_int(female_fatten_in) * price_fatten_female + clamp_int(male_fatten_in) * price_fatten_male
    rev_total = rev_cull + rev_calf + rev_fatten

    # Costs
    cost_total = breeding_cost_y + repl_stock_cost_y + fatten_cost_total + kpn_loss

    net = rev_total - cost_total

    return {
        "Scenario": name,
        "Annual culls (heads/yr)": annual_culls,
        "Replacement rate (%)": replacement_rate * 100.0,
        "Births total (yr)": births_total,
        "Births female (yr)": births_female,
        "Births male (yr)": births_male,
        "Replacement females (fixed)": replacements_female,
        "Female use total": female_use_total,
        "Male use total": male_use_total,
        "Replacement stock (heads)": repl_stock,
        "Calf production cost (per head)": calf_prod_cost_per_head,
        "KPN loss (KRW/yr)": kpn_loss,
        "Breeding cost (KRW/yr)": breeding_cost_y,
        "Replacement stock cost (KRW/yr)": repl_stock_cost_y,
        "Fatten cost total (KRW/yr)": fatten_cost_total,
        "Revenue cull (KRW/yr)": rev_cull,
        "Revenue calf (KRW/yr)": rev_calf,
        "Revenue fatten (KRW/yr)": rev_fatten,
        "Revenue total (KRW/yr)": rev_total,
        "Cost total (KRW/yr)": cost_total,
        "Net (KRW/yr)": net,
        "Female fatten cost/head": female_fatten_info["cost_per_head"],
        "Male fatten cost/head": male_fatten_info["cost_per_head"],
        "Female fatten months rearing": female_fatten_info["months_rearing"],
        "Female fatten months early": female_fatten_info["months_early"],
        "Female fatten months late": female_fatten_info["months_late"],
        "Male fatten months rearing": male_fatten_info["months_rearing"],
        "Male fatten months early": male_fatten_info["months_early"],
        "Male fatten months late": male_fatten_info["months_late"],
    }, issues


# ---------------------------
# UI
# ---------------------------
st.title("한우 번식·교체·비육 손익 계산기 (V0.2)")
st.caption("A/B는 '교체(도태) 두수'로 구분합니다. 송아지 분배는 두수 입력, 제약 위반 시 경고 표시.")


with st.sidebar:
    st.header("공통 기본값")

    base_cows = st.number_input("기초 번식암소 수(두)", min_value=1, value=100, step=10)

    conception_rate = st.number_input("수태율(0~1)", min_value=0.0, max_value=1.0, value=0.70, step=0.01)

    female_birth_ratio = st.number_input("암송아지 출생 비율(0~1)", min_value=0.0, max_value=1.0, value=0.50, step=0.01)

    st.markdown("---")
    st.subheader("기간(개월)")

    calf_common_months = st.number_input("송아지 공통 육성기간(개월)", min_value=0, value=7, step=1)

    heifer_nonprofit_months = st.number_input("대체우 무수익기간(개월)", min_value=0, value=19, step=1)

    kpn_exit_months = st.number_input("KPN 위탁 수송아지 나가는 월령(개월)", min_value=0, value=7, step=1)

    st.markdown("---")
    st.subheader("비육 출하 월령(개월)")

    ship_m_female = st.number_input("암 비육우 출하 월령(개월)", min_value=0, value=30, step=1)
    ship_m_male = st.number_input("수 비육우 출하 월령(개월)", min_value=0, value=30, step=1)

    st.markdown("---")
    st.subheader("연간 비용(원/년/두)")
    cow_cost_y = st.number_input("번식우 유지비(원/년/두) (사료+기타 포함)", min_value=0.0, value=3_200_000.0, step=50_000.0)

    cost_rearing_y = st.number_input("육성기(송아지 이후~12개월) 비용(원/년/두)", min_value=0.0, value=2_400_000.0, step=50_000.0)

    cost_fatten_early_y = st.number_input("비육전기(13~18개월) 비용(원/년/두)", min_value=0.0, value=3_000_000.0, step=50_000.0)

    cost_fatten_late_y = st.number_input("비육후기(19~출하) 비용(원/년/두)", min_value=0.0, value=3_600_000.0, step=50_000.0)

    st.markdown("---")
    st.subheader("가격(원/두)")

    price_calf_female = st.number_input("암 송아지 판매가격(원/두)", min_value=0.0, value=1_300_000.0, step=50_000.0)
    price_calf_male = st.number_input("수 송아지 판매가격(원/두)", min_value=0.0, value=1_200_000.0, step=50_000.0)

    price_fatten_female = st.number_input("암 비육우 출하가격(원/두)", min_value=0.0, value=7_500_000.0, step=100_000.0)
    price_fatten_male = st.number_input("수 비육우 출하가격(원/두)", min_value=0.0, value=8_500_000.0, step=100_000.0)

    price_cull_cow = st.number_input("도태 암소 판매가격(원/두)", min_value=0.0, value=2_500_000.0, step=50_000.0)


tabs = st.tabs(["시나리오 A", "시나리오 B", "비교/결과"])


def scenario_inputs(tab, label, defaults):
    with tab:
        st.subheader(f"{label} — 교체(도태) & 송아지 분배(두/년)")

        # Scenario-specific replacement lever
        annual_culls = st.number_input(
            f"[{label}] 연간 도태/교체 암소 수(두/년)",
            min_value=0,
            value=defaults["annual_culls"],
            step=1,
            key=f"{label}_annual_culls",
        )

        st.info(
            f"[{label}] 교체율(%) = {annual_culls} / {base_cows} × 100 = **{(annual_culls/base_cows*100 if base_cows else 0):.2f}%**\n\n"
            f"[{label}] 대체우 선발두수(암) = 연간 도태두수 = **{annual_culls}두/년** (자동 고정)"
        )

        c1, c2, c3 = st.columns(3)

        with c1:
            st.markdown("#### 암 송아지")
            female_calf_sell = st.number_input(
                f"[{label}] 암 송아지 판매(두/년)",
                min_value=0,
                value=defaults["female_calf_sell"],
                step=1,
                key=f"{label}_female_calf_sell",
            )
            female_fatten_in = st.number_input(
                f"[{label}] 암 비육우 투입(두/년)",
                min_value=0,
                value=defaults["female_fatten_in"],
                step=1,
                key=f"{label}_female_fatten_in",
            )

        with c2:
            st.markdown("#### 수 송아지")
            kpn_male = st.number_input(
                f"[{label}] KPN 위탁 수송아지(두/년)",
                min_value=0,
                value=defaults["kpn_male"],
                step=1,
                key=f"{label}_kpn_male",
            )
            male_calf_sell = st.number_input(
                f"[{label}] 수 송아지 판매(두/년)",
                min_value=0,
                value=defaults["male_calf_sell"],
                step=1,
                key=f"{label}_male_calf_sell",
            )
            male_fatten_in = st.number_input(
                f"[{label}] 수 비육우 투입(두/년)",
                min_value=0,
                value=defaults["male_fatten_in"],
                step=1,
                key=f"{label}_male_fatten_in",
            )

        with c3:
            st.markdown("#### 자동 체크(미리보기)")
            births_total = base_cows * float(conception_rate)
            births_female = births_total * float(female_birth_ratio)
            births_male = births_total * (1.0 - float(female_birth_ratio))

            female_use = int(annual_culls) + int(female_calf_sell) + int(female_fatten_in)
            male_use = int(kpn_male) + int(male_calf_sell) + int(male_fatten_in)

            st.write(f"- 연간 총 출생(예상): **{births_total:.2f}두**")
            st.write(f"- 연간 암 출생(예상): **{births_female:.2f}두**")
            st.write(f"- 연간 수 출생(예상): **{births_male:.2f}두**")
            st.write(f"- [암] 사용합계(대체우+판매+비육): **{female_use}두**")
            st.write(f"- [수] 사용합계(KPN+판매+비육): **{male_use}두**")

            if female_use > births_female + 1e-9:
                st.error("암 송아지 사용합계가 암 출생두수를 초과합니다.")
            if male_use > births_male + 1e-9:
                st.error("수 송아지 사용합계가 수 출생두수를 초과합니다.")

        return {
            "annual_culls": int(annual_culls),
            "female_calf_sell": int(female_calf_sell),
            "female_fatten_in": int(female_fatten_in),
            "kpn_male": int(kpn_male),
            "male_calf_sell": int(male_calf_sell),
            "male_fatten_in": int(male_fatten_in),
        }


# Sensible defaults for A/B (ONLY A/B lever differs)
defaults_A = {
    "annual_culls": 3,
    "female_calf_sell": 0,
    "female_fatten_in": 10,
    "kpn_male": 10,
    "male_calf_sell": 0,
    "male_fatten_in": 25,
}
defaults_B = {
    "annual_culls": 10,
    "female_calf_sell": 0,
    "female_fatten_in": 10,
    "kpn_male": 10,
    "male_calf_sell": 0,
    "male_fatten_in": 25,
}

alloc_A = scenario_inputs(tabs[0], "A", defaults_A)
alloc_B = scenario_inputs(tabs[1], "B", defaults_B)


# ---------------------------
# Compute & Compare
# ---------------------------
res_A, issues_A = compute_scenario(
    name="A",
    base_cows=int(base_cows),
    conception_rate=float(conception_rate),
    female_birth_ratio=float(female_birth_ratio),
    annual_culls=int(alloc_A["annual_culls"]),
    heifer_nonprofit_months=int(heifer_nonprofit_months),
    calf_common_months=int(calf_common_months),
    kpn_exit_months=int(kpn_exit_months),
    female_calf_sell=alloc_A["female_calf_sell"],
    female_fatten_in=alloc_A["female_fatten_in"],
    male_calf_sell=alloc_A["male_calf_sell"],
    male_fatten_in=alloc_A["male_fatten_in"],
    kpn_male=alloc_A["kpn_male"],
    cow_cost_y=float(cow_cost_y),
    cost_rearing_y=float(cost_rearing_y),
    cost_fatten_early_y=float(cost_fatten_early_y),
    cost_fatten_late_y=float(cost_fatten_late_y),
    price_calf_female=float(price_calf_female),
    price_calf_male=float(price_calf_male),
    price_fatten_female=float(price_fatten_female),
    price_fatten_male=float(price_fatten_male),
    price_cull_cow=float(price_cull_cow),
    ship_m_female=int(ship_m_female),
    ship_m_male=int(ship_m_male),
)

res_B, issues_B = compute_scenario(
    name="B",
    base_cows=int(base_cows),
    conception_rate=float(conception_rate),
    female_birth_ratio=float(female_birth_ratio),
    annual_culls=int(alloc_B["annual_culls"]),
    heifer_nonprofit_months=int(heifer_nonprofit_months),
    calf_common_months=int(calf_common_months),
    kpn_exit_months=int(kpn_exit_months),
    female_calf_sell=alloc_B["female_calf_sell"],
    female_fatten_in=alloc_B["female_fatten_in"],
    male_calf_sell=alloc_B["male_calf_sell"],
    male_fatten_in=alloc_B["male_fatten_in"],
    kpn_male=alloc_B["kpn_male"],
    cow_cost_y=float(cow_cost_y),
    cost_rearing_y=float(cost_rearing_y),
    cost_fatten_early_y=float(cost_fatten_early_y),
    cost_fatten_late_y=float(cost_fatten_late_y),
    price_calf_female=float(price_calf_female),
    price_calf_male=float(price_calf_male),
    price_fatten_female=float(price_fatten_female),
    price_fatten_male=float(price_fatten_male),
    price_cull_cow=float(price_cull_cow),
    ship_m_female=int(ship_m_female),
    ship_m_male=int(ship_m_male),
)

with tabs[2]:
    st.subheader("제약/경고")
    if issues_A:
        st.error("시나리오 A 경고:\n- " + "\n- ".join(issues_A))
    else:
        st.success("시나리오 A: 제약 위반 없음")

    if issues_B:
        st.error("시나리오 B 경고:\n- " + "\n- ".join(issues_B))
    else:
        st.success("시나리오 B: 제약 위반 없음")

    st.markdown("---")

    st.subheader("핵심 지표 요약")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("A 순이익(원/년)", fmt_money(res_A["Net (KRW/yr)"]))
    k2.metric("B 순이익(원/년)", fmt_money(res_B["Net (KRW/yr)"]))
    diff = res_B["Net (KRW/yr)"] - res_A["Net (KRW/yr)"]
    k3.metric("B - A (원/년)", fmt_money(diff))
    k4.metric("A 교체율(%) / B 교체율(%)", f"{res_A['Replacement rate (%)']:.2f}% / {res_B['Replacement rate (%)']:.2f}%")

    st.markdown("---")

    st.subheader("참고 지표(원가/기간)")
    c1, c2, c3 = st.columns(3)
    c1.write(f"- 송아지 생산비(두당) = 번식우유지비 / 수태율 = **{fmt_money(res_A['Calf production cost (per head)'])} 원/두**")
    c2.write(f"- 대체우 재고(두): A **{fmt_float(res_A['Replacement stock (heads)'], 2)}**, B **{fmt_float(res_B['Replacement stock (heads)'], 2)}**")
    c3.write(f"- KPN 손해(연간): A **{fmt_money(res_A['KPN loss (KRW/yr)'])}**, B **{fmt_money(res_B['KPN loss (KRW/yr)'])}**")

    st.markdown("---")

    df = pd.DataFrame([res_A, res_B])

    show_cols = [
        "Scenario",
        "Annual culls (heads/yr)",
        "Replacement rate (%)",
        "Births total (yr)", "Births female (yr)", "Births male (yr)",
        "Replacement females (fixed)",
        "Female use total", "Male use total",
        "Revenue total (KRW/yr)", "Cost total (KRW/yr)", "Net (KRW/yr)",
        "Breeding cost (KRW/yr)", "Replacement stock cost (KRW/yr)",
        "Fatten cost total (KRW/yr)", "KPN loss (KRW/yr)",
        "Revenue calf (KRW/yr)", "Revenue fatten (KRW/yr)", "Revenue cull (KRW/yr)",
    ]
    df_show = df[show_cols].copy()

    # Format
    df_show["Annual culls (heads/yr)"] = df_show["Annual culls (heads/yr)"].map(fmt_int)
    df_show["Replacement females (fixed)"] = df_show["Replacement females (fixed)"].map(fmt_int)
    df_show["Female use total"] = df_show["Female use total"].map(fmt_int)
    df_show["Male use total"] = df_show["Male use total"].map(fmt_int)

    df_show["Replacement rate (%)"] = df_show["Replacement rate (%)"].map(lambda x: f"{x:.2f}")

    for col in ["Births total (yr)", "Births female (yr)", "Births male (yr)"]:
        df_show[col] = df_show[col].map(lambda x: f"{x:.2f}")

    money_cols = [c for c in df_show.columns if "(KRW/yr)" in c]
    for col in money_cols:
        df_show[col] = df_show[col].map(fmt_money)

    st.subheader("A/B 결과표(연간)")
    st.dataframe(df_show, use_container_width=True)

    st.markdown("---")
    st.subheader("그래프(비교)")

    chart_df = pd.DataFrame([
        {"Scenario": "A", "Type": "Revenue", "Value": res_A["Revenue total (KRW/yr)"]},
        {"Scenario": "A", "Type": "Cost", "Value": res_A["Cost total (KRW/yr)"]},
        {"Scenario": "A", "Type": "Net", "Value": res_A["Net (KRW/yr)"]},
        {"Scenario": "B", "Type": "Revenue", "Value": res_B["Revenue total (KRW/yr)"]},
        {"Scenario": "B", "Type": "Cost", "Value": res_B["Cost total (KRW/yr)"]},
        {"Scenario": "B", "Type": "Net", "Value": res_B["Net (KRW/yr)"]},
    ])

    chart = (
        alt.Chart(chart_df)
        .mark_bar()
        .encode(
            x=alt.X("Scenario:N", title="Scenario"),
            y=alt.Y("Value:Q", title="KRW/year"),
            column=alt.Column("Type:N", title=None),
            tooltip=[
                alt.Tooltip("Scenario:N"),
                alt.Tooltip("Type:N"),
                alt.Tooltip("Value:Q", format=",.0f"),
            ],
        )
        .properties(height=320)
    )

    st.altair_chart(chart, use_container_width=True)

    st.markdown("---")
    st.subheader("CSV 다운로드")
    out_df = pd.DataFrame([res_A, res_B])
    csv = out_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("A/B 결과 CSV 다운로드", data=csv, file_name="hanwoo_v0.2_results.csv", mime="text/csv")

    st.caption(
        "주의: '송아지 생산비(두당)=번식우유지비/수태율'은 생산비(원가) 지표(참고용)입니다. "
        "번식우유지비는 이미 비용에 포함되어 있으므로 생산비를 비용에 다시 더하지 않습니다(이중계산 방지)."
    )

