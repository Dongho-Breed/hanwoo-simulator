import streamlit as st
import pandas as pd
import altair as alt
from dataclasses import dataclass

# =========================
# 1) Parameters (from your script)
# =========================
@dataclass
class Params:
    herd_size: int = 100
    initial_cow_age_m: int = 18
    conception_rate: float = 0.70
    female_ratio: float = 0.50
    max_preg: int = 10
    open_m: int = 2
    mating_m: int = 2
    gestation_m: int = 10
    replacement_n_each_mating: int = 3
    consignment_m_per_birth: int = 5
    female_common_rearing_m: int = 6
    female_eval_m: int = 2
    female_total_fatten_m: int = 30
    female_replacement_age_m: int = 18
    male_consignment_age_m: int = 6
    beef_ship_age_m: int = 30

    max_total_capacity: int = 250
    price_calf_sale: int = 0
    price_beef_female: int = 0
    price_beef_male: int = 0
    price_old_cow: int = 0
    cost_monthly_per_head: int = 0


def push(q, c: int, m: int):
    if c > 0:
        q.append([c, m])

def elapse_one_month(q) -> int:
    out = 0
    nq = []
    for c, m in q:
        m -= 1
        if m <= 0:
            out += c
        else:
            nq.append([c, m])
    q[:] = nq
    return out


def simulate(total_months: int, p: Params):
    cows_by_preg = [0] * p.max_preg
    cows_by_preg[0] = p.herd_size

    stage, stage_left = 0, p.open_m
    pregnant_this_cycle = 0
    ready_replacements = 0

    q_female_grow6, q_female_eval2, q_female_beef_rest = [], [], []
    q_replacement_to_18m = []
    q_male_consignment, q_male_beef = [], []

    누적_교체축_투입 = 0
    누적_교체로_출하된_암소 = 0
    누적_어미소_10산_출하 = 0
    누적_암컷_비육출하 = 0
    누적_숫컷_비육출하 = 0
    누적_수컷_위탁검정 = 0

    누적_송아지_판매_암 = 0
    누적_송아지_판매_수 = 0
    누적_유지비용 = 0

    female_beef_rest_m = p.female_total_fatten_m - (p.female_common_rearing_m + p.female_eval_m)

    # NOTE: get_current_total is used both inside loop and at return-time
    def get_current_total():
        return (
            sum(cows_by_preg) + ready_replacements
            + sum(c for c, _ in q_female_grow6) + sum(c for c, _ in q_female_eval2)
            + sum(c for c, _ in q_female_beef_rest) + sum(c for c, _ in q_replacement_to_18m)
            + sum(c for c, _ in q_male_consignment) + sum(c for c, _ in q_male_beef)
        )

    monthly_trace = []  # for plotting

    for month in range(1, total_months + 1):
        # 유지비 누적
        cur_total = get_current_total()
        누적_유지비용 += cur_total * p.cost_monthly_per_head

        # 파이프라인 진행
        done_grow6 = elapse_one_month(q_female_grow6)
        if done_grow6 > 0:
            push(q_female_eval2, done_grow6, p.female_eval_m)

        done_eval2 = elapse_one_month(q_female_eval2)
        if done_eval2 > 0:
            selected_rep = min(p.replacement_n_each_mating, done_eval2)
            remains = done_eval2 - selected_rep

            # capacity check
            space = p.max_total_capacity - get_current_total()
            to_beef = min(remains, max(0, space))
            to_sell = remains - to_beef

            push(q_female_beef_rest, to_beef, female_beef_rest_m)
            누적_송아지_판매_암 += to_sell

            m_to_18 = max(0, p.female_replacement_age_m - (p.female_common_rearing_m + p.female_eval_m))
            push(q_replacement_to_18m, selected_rep, m_to_18)

        ready_replacements += elapse_one_month(q_replacement_to_18m)
        누적_암컷_비육출하 += elapse_one_month(q_female_beef_rest)
        누적_수컷_위탁검정 += elapse_one_month(q_male_consignment)
        누적_숫컷_비육출하 += elapse_one_month(q_male_beef)

        # 배치 사이클 진행
        stage_left -= 1
        if stage_left == 0:
            if stage == 0:  # MATING
                stage = 1
                stage_left = p.mating_m

                enter = min(p.replacement_n_each_mating, ready_replacements)
                if enter > 0:
                    누적_교체축_투입 += enter
                    ready_replacements -= enter

                    # replacement enters: ship out same number of cows
                    누적_교체로_출하된_암소 += enter
                    left = enter
                    for preg in range(p.max_preg - 1, -1, -1):
                        if left <= 0:
                            break
                        take = min(cows_by_preg[preg], left)
                        cows_by_preg[preg] -= take
                        left -= take
                    cows_by_preg[0] += enter

            elif stage == 1:  # GESTATION
                stage = 2
                stage_left = p.gestation_m
                pregnant_this_cycle = int(sum(cows_by_preg) * p.conception_rate)

            elif stage == 2:  # CALVING -> OPEN
                stage = 0
                stage_left = p.open_m
                births = pregnant_this_cycle

                # 산차 이동
                to_assign = births
                new_c = cows_by_preg[:]
                for preg in range(p.max_preg):
                    if to_assign <= 0:
                        break
                    can = min(new_c[preg], to_assign)
                    new_c[preg] -= can
                    if preg + 1 >= p.max_preg:
                        누적_어미소_10산_출하 += can
                    else:
                        new_c[preg + 1] += can
                    to_assign -= can
                cows_by_preg = new_c

                female = int(births * p.female_ratio)
                male = births - female
                push(q_female_grow6, female, p.female_common_rearing_m)

                # male capacity check
                consign = min(p.consignment_m_per_birth, male)
                remains_m = male - consign
                space = p.max_total_capacity - get_current_total()
                to_beef_m = min(remains_m, max(0, space))
                to_sell_m = remains_m - to_beef_m

                push(q_male_consignment, consign, p.male_consignment_age_m)
                push(q_male_beef, to_beef_m, p.beef_ship_age_m)
                누적_송아지_판매_수 += to_sell_m

                pregnant_this_cycle = 0

        # 월별 trace (간단 KPI)
        monthly_trace.append({
            "month": month,
            "total_heads": get_current_total(),
            "cum_cost": 누적_유지비용,
        })

    총_매출 = (
        (누적_교체로_출하된_암소 + 누적_어미소_10산_출하) * p.price_old_cow
        + (누적_암컷_비육출하 * p.price_beef_female)
        + (누적_숫컷_비육출하 * p.price_beef_male)
        + (누적_송아지_판매_암 + 누적_송아지_판매_수) * p.price_calf_sale
    )

    총_비육출하 = 누적_교체로_출하된_암소 + 누적_어미소_10산_출하 + 누적_암컷_비육출하 + 누적_숫컷_비육출하

    res = {
        "시뮬레이션_개월수": total_months,
        "실제_투입된_교체축_수": 누적_교체축_투입,
        "교체로_출하된_암소_수": 누적_교체로_출하된_암소,
        "어미소_10산_출하수": 누적_어미소_10산_출하,
        "암컷_비육출하_두수": 누적_암컷_비육출하,
        "숫컷_비육출하_두수": 누적_숫컷_비육출하,
        "수컷_위탁검정_두수": 누적_수컷_위탁검정,
        "송아지_판매_두수(암)": 누적_송아지_판매_암,
        "송아지_판매_두수(수)": 누적_송아지_판매_수,
        "총_비육출하_두수": 총_비육출하,
        "현재_선발집단_암소_수": sum(cows_by_preg),
        "현재_농장_총_사육두수": get_current_total(),
        "누적_총_매출": 총_매출,
        "누적_총_유지비용": 누적_유지비용,
        "누적_순수익": 총_매출 - 누적_유지비용,
    }

    return res, pd.DataFrame(monthly_trace)


# =========================
# Streamlit UI
# =========================
st.set_page_config(page_title="Hanwoo Simulator", layout="wide")
st.title("한우 교체·사육 시뮬레이터 (입력 → 결과 자동 계산)")

with st.sidebar:
    st.header("입력값")

    months = st.number_input("시뮬레이션 기간(개월)", min_value=12, value=120, step=12)

    st.markdown("---")
    st.subheader("번식/교체 핵심")
    herd_size = st.number_input("기초 번식암소(두)", min_value=1, value=100, step=10)
    conception_rate = st.number_input("수태율(0~1)", min_value=0.0, max_value=1.0, value=0.70, step=0.01)
    female_ratio = st.number_input("암컷 비율(0~1)", min_value=0.0, max_value=1.0, value=0.50, step=0.01)
    replacement_n_each_mating = st.number_input("교배 1회당 선발 교체축(두)", min_value=0, value=3, step=1)

    st.markdown("---")
    st.subheader("사육 상한/가격/비용 (단위: 만원)")
    max_total_capacity = st.number_input("농장 최대 사육두수 상한", min_value=1, value=250, step=10)
    cost_monthly_per_head = st.number_input("두당 월 유지비(만원)", min_value=0, value=0, step=1)

    price_calf_sale = st.number_input("송아지 판매가(만원/두)", min_value=0, value=0, step=10)
    price_beef_female = st.number_input("암소 비육 출하가(만원/두)", min_value=0, value=0, step=10)
    price_beef_male = st.number_input("수소 비육 출하가(만원/두)", min_value=0, value=0, step=10)
    price_old_cow = st.number_input("도태/노산우 출하가(만원/두)", min_value=0, value=0, step=10)

    run = st.button("시뮬레이션 실행")


if run:
    p = Params()
    p.herd_size = int(herd_size)
    p.conception_rate = float(conception_rate)
    p.female_ratio = float(female_ratio)
    p.replacement_n_each_mating = int(replacement_n_each_mating)

    p.max_total_capacity = int(max_total_capacity)
    p.cost_monthly_per_head = int(cost_monthly_per_head)

    p.price_calf_sale = int(price_calf_sale)
    p.price_beef_female = int(price_beef_female)
    p.price_beef_male = int(price_beef_male)
    p.price_old_cow = int(price_old_cow)

    res, trace = simulate(int(months), p)

    st.subheader("요약 KPI")
    c1, c2, c3 = st.columns(3)
    c1.metric("누적 총매출(만원)", f"{res['누적_총_매출']:,.0f}")
    c2.metric("누적 유지비(만원)", f"{res['누적_총_유지비용']:,.0f}")
    c3.metric("누적 순수익(만원)", f"{res['누적_순수익']:,.0f}")

    st.subheader("핵심 결과")
    out = pd.DataFrame([res]).T.reset_index()
    out.columns = ["항목", "값"]
    st.dataframe(out, use_container_width=True)

    st.subheader("추이(월별)")

    chart_heads = (
        alt.Chart(trace)
        .mark_line()
        .encode(
            x=alt.X("month:Q", title="Month"),
            y=alt.Y("total_heads:Q", title="Total heads"),
            tooltip=[alt.Tooltip("month:Q"), alt.Tooltip("total_heads:Q", format=",.0f")]
        )
        .properties(height=300)
    )
    st.altair_chart(chart_heads, use_container_width=True)

    chart_cost = (
        alt.Chart(trace)
        .mark_line()
        .encode(
            x=alt.X("month:Q", title="Month"),
            y=alt.Y("cum_cost:Q", title="Cumulative cost (만원)"),
            tooltip=[alt.Tooltip("month:Q"), alt.Tooltip("cum_cost:Q", format=",.0f")]
        )
        .properties(height=300)
    )
    st.altair_chart(chart_cost, use_container_width=True)

else:
    st.info("왼쪽에서 값을 입력하고 '시뮬레이션 실행'을 누르면 결과가 자동 계산됩니다.")

