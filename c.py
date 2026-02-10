import streamlit as st
import pandas as pd
import altair as alt
import math
import numpy as np
import plotly.express as px
from scipy.optimize import minimize

# 페이지 설정
st.set_page_config(page_title="🐂 한우 경영·사료 최적화 플랫폼", layout="wide")

# ---------------------------
# 0. 데이터 초기화
# ---------------------------

# [비용 데이터] - 천원 단위 적용 (기존 값 / 1000)
if 'cost_items' not in st.session_state:
    items = [
        "사료비", "수도광열비", "방역치료비", "자동차비", "농구비", "영농시설비", "기타재료비", "종부료",
        "차입금이자", "토지임차료", "고용노동비", "분뇨처리비", "생산관리비", "기타비용",
        "자가노동비", "자본용역비", "토지용역비"
    ]
    # 입력 편의를 위해 '천원' 단위로 초기화
    data_breed = {
        "항목": items,
        "금액(천원/년)": [1500, 140, 110, 80, 50, 40, 30, 50, 60, 5, 20, 10, 20, 30, 800, 200, 50]
    }
    data_fatten = {
        "항목": items,
        "금액(천원/년)": [2300, 140, 80, 80, 50, 40, 30, 0, 60, 5, 20, 20, 20, 30, 600, 150, 50]
    }
    st.session_state.df_cost_breed = pd.DataFrame(data_breed)
    st.session_state.df_cost_fatten = pd.DataFrame(data_fatten)

# [매출 데이터]
if 'df_cow' not in st.session_state:
    data_cow = {
        "Grade": ["1++A", "1++B", "1++C", "1+A", "1+B", "1+C", "1A", "1B", "1C", "2A", "2B", "2C", "3A", "3B", "3C", "D"],
        "Ratio(%)": [5, 5, 5, 10, 10, 10, 10, 10, 10, 5, 5, 5, 2, 2, 1, 5], 
        "Price(KRW/kg)": [25000, 24000, 23000, 21000, 20000, 19000, 18000, 17000, 16000, 14000, 13000, 12000, 10000, 9000, 8000, 5000],
        "Weight(kg)": [350]*16 
    }
    st.session_state.df_cow = pd.DataFrame(data_cow)

if 'df_steer' not in st.session_state:
    data_steer = {
        "Grade": ["1++A", "1++B", "1++C", "1+A", "1+B", "1+C", "1A", "1B", "1C", "2A", "2B", "2C", "3A", "3B", "3C", "D"],
        "Ratio(%)": [10, 10, 5, 15, 15, 5, 10, 10, 5, 5, 5, 2, 1, 1, 0, 1], 
        "Price(KRW/kg)": [29000, 28000, 27000, 25000, 24000, 23000, 21000, 20000, 19000, 17000, 16000, 15000, 13000, 12000, 11000, 8000],
        "Weight(kg)": [450]*16
    }
    st.session_state.df_steer = pd.DataFrame(data_steer)

# [사료 데이터]
if 'feeds_db' not in st.session_state:
    st.session_state.feeds_db = [
        {"name": "알팔파", "cat": "조사료", "price": 900, "tdn": 52.5, "cp": 19.8, "ndf": 49.9},
        {"name": "IRG 사일리지", "cat": "조사료", "price": 350, "tdn": 37.6, "cp": 6.4, "ndf": 33.8},
        {"name": "볏짚", "cat": "조사료", "price": 200, "tdn": 39.0, "cp": 4.5, "ndf": 70.0},
        {"name": "옥수수", "cat": "농후사료", "price": 550, "tdn": 76.7, "cp": 7.2, "ndf": 8.4},
        {"name": "배합사료", "cat": "농후사료", "price": 650, "tdn": 70.0, "cp": 17.0, "ndf": 27.0},
        {"name": "TMR", "cat": "TMR", "price": 600, "tdn": 68.0, "cp": 14.0, "ndf": 32.0},
    ]

# ---------------------------
# 1. 헬퍼 함수
# ---------------------------
def clamp_int(x, lo=0):
    try: return max(lo, int(x))
    except: return lo

def fmt_money(x):
    if x is None or (isinstance(x, float) and math.isnan(x)): return "-"
    return f"{x:,.0f}"

def format_callback(key):
    val = st.session_state[key]
    try:
        num = int(float(str(val).replace(",", "")))
        st.session_state[key] = f"{num:,}"
    except ValueError:
        pass

def input_with_comma(label, value, key=None):
    if key and key not in st.session_state:
        st.session_state[key] = f"{int(value):,}"
    st.text_input(label, key=key, on_change=format_callback, args=(key,))
    try:
        return float(str(st.session_state[key]).replace(",", ""))
    except:
        return float(value)

def calculate_cost_from_table(df, mode="경영비"):
    exclude_items = ["자가노동비", "자본용역비", "토지용역비"]
    total = 0
    for _, row in df.iterrows():
        item = row['항목']
        if '금액(천원/년)' in df.columns:
            amount = row['금액(천원/년)'] * 1000
        else:
            amount = row['금액(원/년)']
        if mode == "경영비" and item in exclude_items:
            continue
        total += amount
    return total

def calculate_opportunity_cost(df):
    target_items = ["자가노동비", "자본용역비", "토지용역비"]
    total_opp = 0
    for _, row in df.iterrows():
        item = row['항목']
        if item in target_items:
            if '금액(천원/년)' in df.columns:
                amount = row['금액(천원/년)'] * 1000
            else:
                amount = row['금액(원/년)']
            total_opp += amount
    return total_opp

def calculate_avg_price(df):
    weighted_sum = 0
    for _, row in df.iterrows():
        weighted_sum += (row["Ratio(%)"] / 100) * (row["Price(KRW/kg)"] * row["Weight(kg)"])
    return int(weighted_sum)

st.title("🐂 한우 경영·사료 최적화 플랫폼")

# ---------------------------
# 2. 사이드바 UI
# ---------------------------
with st.sidebar:
    st.header("1. 분석 기준 설정")
    cost_mode = st.radio("비용 산출 기준", ["경영비 기준 (실지출, 일반비소계)", "생산비 기준 (비용합계, 기회비용(자가노동비 등) 포함)"], index=0)
    mode_key = "경영비" if "경영비" in cost_mode else "생산비"
    
    calc_breed_cost = calculate_cost_from_table(st.session_state.df_cost_breed, mode_key)
    calc_fatten_cost = calculate_cost_from_table(st.session_state.df_cost_fatten, mode_key)
    calc_cow_price = calculate_avg_price(st.session_state.df_cow)
    calc_steer_price = calculate_avg_price(st.session_state.df_steer)

    st.divider()
    st.header("2. 기본 환경 설정")
    
    with st.expander("A. 농장 공통 설정", expanded=False):
        base_cows = st.number_input("기초 번식우(두)", value=100, step=10, format="%d")
        if 'conception_rate' not in st.session_state: st.session_state.conception_rate = 0.70
        conception_rate = st.number_input("수태율 (0~1)", value=st.session_state.conception_rate, step=0.01, key='sb_concept')
        st.session_state.conception_rate = conception_rate
        female_birth_ratio = st.number_input("암 성비 (0~1)", value=0.50, step=0.01)
        heifer_nonprofit_months = st.number_input("대체우 무수익(월)", value=18)
        calf_common_months = st.number_input("송아지 공통육성(월)", value=6)
        kpn_exit_months = st.number_input("KPN 종료월령", value=6)

    with st.expander("B. 비용 (원/년/두) - 자동 연동", expanded=False):
        st.caption(f"※ {mode_key} 기준 자동 계산된 값입니다.")
        st.text_input("번식우 유지비", value=f"{int(calc_breed_cost):,}", disabled=True)
        st.text_input("비육우 연간 유지비", value=f"{int(calc_fatten_cost):,}", disabled=True)
        cow_cost_y = calc_breed_cost
        avg_cost_calc = calc_fatten_cost

    with st.expander("C. 가격 (원/두) - 자동 연동", expanded=False):
        p_calf_f = input_with_comma("암송아지", 2302000, key="p_calf_f")
        p_calf_m = input_with_comma("수송아지", 4441000, key="p_calf_m")
        st.text_input("암비육우", value=f"{int(calc_cow_price):,}", disabled=True)
        st.text_input("수비육우", value=f"{int(calc_steer_price):,}", disabled=True)
        p_cull = input_with_comma("도태우", 468000, key="p_cull")
        p_fat_f = calc_cow_price
        p_fat_m = calc_steer_price

    with st.expander("D. 출하월령", expanded=False):
        ship_m_f = st.number_input("암 출하월령", value=30)
        ship_m_m = st.number_input("수 출하월령", value=30)

    with st.expander("E. 외부 비육 농가", expanded=False):
        ext_buy_n = st.number_input("수송아지 매입(두)", value=80)
        ext_buy_p = input_with_comma("수송아지 매입가", 3950000, key="ebp")
        ext_sell_n = st.number_input("비육우 출하(두)", value=78)
        ext_sell_p = input_with_comma("비육우 출하가", 10721983, key="esp")
        ext_cost_y = input_with_comma("비육우 유지비", 4330500, key="ecy") 
        ext_period = st.number_input("비육우 기간(년)", value=2.0)

    st.divider()
    st.header("3. 형질별 경제적 가치")
    with st.expander("F. 개량 가치 (원/단위)", expanded=False):
        econ_cw = input_with_comma("도체중 (CW, kg)", 18564, key="ec_cw")
        econ_ms = input_with_comma("근내지방 (MS)", 591204, key="ec_ms")
        econ_ema = input_with_comma("등심단면적 (EMA)", 9163, key="ec_ema")
        econ_bft = input_with_comma("등지방 (BFT)", -57237, key="ec_bft")

    st.divider()
    st.header("4. 사료(체중/체중비) 설정")
    with st.expander("G. 사료 섭취량 설정", expanded=False):
        feed_avg_weight = st.number_input("평균 체중 (kg)", value=450.0, step=10.0, key="feed_weight")
        feed_weight_ratio = st.number_input("체중비 (DMI율)", value=0.0211, step=0.001, format="%.4f", key="feed_ratio")
        dmi = feed_avg_weight * feed_weight_ratio
        st.info(f"일일 목표 섭취량(DMI): {dmi:.2f} kg")

# ---------------------------
# 3. 경제성 분석 로직
# ---------------------------
def compute_scenario(name, base_cows, conception_rate, female_birth_ratio, heifer_nonprofit_months, calf_common_months, kpn_exit_months, annual_culls, female_calf_sell, female_fatten_in, female_fatten_out, female_loss, loss_months, male_calf_sell, male_fatten_in, male_fatten_out, male_loss, kpn_male, cow_cost_y, cost_fatten_avg_y, price_calf_female, price_calf_male, price_fatten_female, price_fatten_male, price_cull_cow, ship_m_female, ship_m_male, ext_buy_n, ext_buy_p, ext_sell_n, ext_sell_p, ext_cost_y, ext_period_y, by_product_income_cow):
    base_cows = clamp_int(base_cows, 1)
    annual_culls = clamp_int(annual_culls, 0)

    val_cull = annual_culls * price_cull_cow
    val_calf_f = clamp_int(female_calf_sell) * price_calf_female
    val_calf_m = clamp_int(male_calf_sell) * price_calf_male
    val_fat_out_f = clamp_int(female_fatten_out) * price_fatten_female
    val_fat_out_m = clamp_int(male_fatten_out) * price_fatten_male
    val_byprod = base_cows * by_product_income_cow
    rev_internal = val_cull + val_calf_f + val_calf_m + val_fat_out_f + val_fat_out_m + val_byprod
    
    cost_breeding_main = base_cows * cow_cost_y
    heifer_years = clamp_int(heifer_nonprofit_months, 0) / 12.0
    cost_breeding_repl = (annual_culls * heifer_years) * cow_cost_y
    if conception_rate > 0:
        calf_prod_cost_unit = (cow_cost_y / conception_rate) - by_product_income_cow
    else:
        calf_prod_cost_unit = 0
    val_kpn_loss = clamp_int(kpn_male) * calf_prod_cost_unit * (clamp_int(kpn_exit_months, 0) / 12.0)
    
    fatten_period_f = max(0, ship_m_female - calf_common_months) / 12.0
    fatten_period_m = max(0, ship_m_male - calf_common_months) / 12.0
    cost_per_f = fatten_period_f * cost_fatten_avg_y
    cost_per_m = fatten_period_m * cost_fatten_avg_y
    val_fat_cost_f = clamp_int(female_fatten_in) * cost_per_f
    val_fat_cost_m = clamp_int(male_fatten_in) * cost_per_m
    
    cost_loss_head = calf_prod_cost_unit * (loss_months / 12.0)
    val_loss_f = female_loss * cost_loss_head
    val_loss_m = male_loss * cost_loss_head
    
    cost_internal = cost_breeding_main + cost_breeding_repl + val_kpn_loss + val_fat_cost_f + val_fat_cost_m + val_loss_f + val_loss_m
    net_internal = rev_internal - cost_internal

    val_ext_rev = ext_sell_n * ext_sell_p
    val_ext_buy = ext_buy_n * ext_buy_p
    val_ext_maint = (ext_buy_n * ext_period_y) * ext_cost_y
    net_external = val_ext_rev - val_ext_buy - val_ext_maint

    net_final = net_internal + net_external
    rev_final = rev_internal + val_ext_rev
    cost_final = cost_internal + val_ext_buy + val_ext_maint

    cost_breakdown = [
        {"Category": "기초 번식우 유지", "Value": cost_breeding_main + cost_breeding_repl},
        {"Category": "자가 사육비", "Value": val_fat_cost_f + val_fat_cost_m},
        {"Category": "폐사 손실", "Value": val_loss_f + val_loss_m},
        {"Category": "외부 송아지 매입", "Value": val_ext_buy},
        {"Category": "외부 사육비", "Value": val_ext_maint},
        {"Category": "기타 (KPN 위탁 등)", "Value": val_kpn_loss}
    ]

    return {
        "Scenario": name,
        "Net Final": net_final, "Rev Final": rev_final, "Cost Final": cost_final,
        "Cost Breakdown": cost_breakdown,
        "months_heifer": heifer_nonprofit_months, "months_kpn": kpn_exit_months, "rate_concept": conception_rate,
        "period_f": fatten_period_f, "period_m": fatten_period_m, "period_ext": ext_period_y, "cost_avg_fatten": cost_fatten_avg_y,
        "v_cull": val_cull, "n_cull": annual_culls, "v_calf_f": val_calf_f, "n_calf_f": female_calf_sell,
        "v_calf_m": val_calf_m, "n_calf_m": male_calf_sell, "v_fat_out_f": val_fat_out_f, "n_fat_out_f": female_fatten_out,
        "v_fat_out_m": val_fat_out_m, "n_fat_out_m": male_fatten_out, "c_breed_main": cost_breeding_main, "n_base": base_cows,
        "c_breed_repl": cost_breeding_repl, "n_repl": annual_culls, "c_kpn": val_kpn_loss, "n_kpn": kpn_male,
        "c_fat_in_f": val_fat_cost_f, "n_fat_in_f": female_fatten_in, "c_fat_in_m": val_fat_cost_m, "n_fat_in_m": male_fatten_in,
        "val_loss_f": val_loss_f, "val_loss_m": val_loss_m, "n_loss_f": female_loss, "n_loss_m": male_loss,
        "cost_loss_head": cost_loss_head, "loss_months": loss_months, "v_ext_rev": val_ext_rev, "n_ext_sell": ext_sell_n,
        "c_ext_buy": val_ext_buy, "n_ext_buy": ext_buy_n, "c_ext_maint": val_ext_maint, "n_ext_stock": ext_sell_n * ext_period_y,
        "p_cull": price_cull_cow, "p_calf_f": price_calf_female, "p_calf_m": price_calf_male,
        "p_fat_f": price_fatten_female, "p_fat_m": price_fatten_male, "cost_y_cow": cow_cost_y, 
        "p_ext_sell": ext_sell_p, "p_ext_buy": ext_buy_p, "cost_y_ext": ext_cost_y,
        "v_byprod": val_byprod, "unit_byprod": by_product_income_cow
    }

def run_base_calc(name, inputs):
    bp_income = st.session_state.get('by_product_income', 0)
    return compute_scenario(name, base_cows, conception_rate, female_birth_ratio, heifer_nonprofit_months, calf_common_months, kpn_exit_months, inputs["annual_culls"], inputs["female_calf_sell"], inputs["female_fatten_in"], inputs["female_fatten_out"], inputs["female_loss"], inputs["loss_months"], inputs["male_calf_sell"], inputs["male_fatten_in"], inputs["male_fatten_out"], inputs["male_loss"], inputs["kpn_male"], cow_cost_y, avg_cost_calc, p_calf_f, p_calf_m, p_fat_f, p_fat_m, p_cull, ship_m_f, ship_m_m, ext_buy_n, ext_buy_p, ext_sell_n, ext_sell_p, ext_cost_y, ext_period, bp_income)

def make_excel_view(res):
    data = []
    data.append({"구분": "수익", "항목": "도태우 판매", "산출 근거": f"{res['n_cull']}두 * {fmt_money(res['p_cull'])}", "금액 (Amount)": res["v_cull"]})
    data.append({"구분": "수익", "항목": "암송아지 판매", "산출 근거": f"{res['n_calf_f']}두 * {fmt_money(res['p_calf_f'])}", "금액 (Amount)": res["v_calf_f"]})
    data.append({"구분": "수익", "항목": "수송아지 판매", "산출 근거": f"{res['n_calf_m']}두 * {fmt_money(res['p_calf_m'])}", "금액 (Amount)": res["v_calf_m"]})
    data.append({"구분": "수익", "항목": "암비육우 출하", "산출 근거": f"{res['n_fat_out_f']}두 * {fmt_money(res['p_fat_f'])}", "금액 (Amount)": res["v_fat_out_f"]})
    data.append({"구분": "수익", "항목": "수비육우 출하", "산출 근거": f"{res['n_fat_out_m']}두 * {fmt_money(res['p_fat_m'])}", "금액 (Amount)": res["v_fat_out_m"]})
    data.append({"구분": "수익", "항목": "부산물 수입", "산출 근거": f"{res['n_base']}두 * {fmt_money(res['unit_byprod'])}", "금액 (Amount)": res["v_byprod"]})
    data.append({"구분": "비용", "항목": "기초 번식우 유지", "산출 근거": f"{res['n_base']}두 * {fmt_money(res['cost_y_cow'])}", "금액 (Amount)": -res["c_breed_main"]})
    data.append({"구분": "비용", "항목": "대체우 육성", "산출 근거": f"{res['n_repl']}두 * ({res['months_heifer']}/12) * {fmt_money(res['cost_y_cow'])}", "금액 (Amount)": -res["c_breed_repl"]})
    data.append({"구분": "비용", "항목": "자가 암비육", "산출 근거": f"{res['n_fat_in_f']}두 * {res['period_f']:.1f}년 * {fmt_money(res['cost_avg_fatten'])}", "금액 (Amount)": -res["c_fat_in_f"]})
    data.append({"구분": "비용", "항목": "자가 수비육", "산출 근거": f"{res['n_fat_in_m']}두 * {res['period_m']:.1f}년 * {fmt_money(res['cost_avg_fatten'])}", "금액 (Amount)": -res["c_fat_in_m"]})
    data.append({"구분": "비용(손실)", "항목": "암송아지 폐사", "산출 근거": f"{res['n_loss_f']}두 * ({fmt_money(res['cost_y_cow'])}/{res['rate_concept']}) * ({res['loss_months']}/12)", "금액 (Amount)": -res["val_loss_f"]})
    data.append({"구분": "비용(손실)", "항목": "수송아지 폐사", "산출 근거": f"{res['n_loss_m']}두 * ({fmt_money(res['cost_y_cow'])}/{res['rate_concept']}) * ({res['loss_months']}/12)", "금액 (Amount)": -res["val_loss_m"]})
    data.append({"구분": "외부", "항목": "비육우 매출", "산출 근거": f"{res['n_ext_sell']}두 * {fmt_money(res['p_ext_sell'])}", "금액 (Amount)": res["v_ext_rev"]})
    data.append({"구분": "외부", "항목": "송아지 매입", "산출 근거": f"{res['n_ext_buy']}두 * {fmt_money(res['p_ext_buy'])}", "금액 (Amount)": -res["c_ext_buy"]})
    data.append({"구분": "외부", "항목": "사육 유지비", "산출 근거": f"{res['n_ext_buy']}두 x {res['period_ext']}년 x {fmt_money(res['cost_y_ext'])}", "금액 (Amount)": -res["c_ext_maint"]})
    data.append({"구분": "결과", "항목": "순이익 (Net Profit)", "산출 근거": "수익 - 비용", "금액 (Amount)": res["Net Final"]})
    return pd.DataFrame(data)

def create_net_profit_chart(res_a, res_b):
    years = list(range(1, 11))
    chart_data = []
    for y in years:
        chart_data.append({"Scenario": "시나리오 A", "Year": y, "Value": res_a['Net Final']})
        chart_data.append({"Scenario": "시나리오 B", "Year": y, "Value": res_b['Net Final']})
    df_chart = pd.DataFrame(chart_data)
    color_scale = alt.Scale(domain=["시나리오 A", "시나리오 B"], range=["#1f77b4", "#d62728"])
    return alt.Chart(df_chart).mark_line(point=True).encode(x=alt.X("Year:O", axis=alt.Axis(labelAngle=0)), y=alt.Y("Value:Q", axis=alt.Axis(format=",.0f")), color=alt.Color("Scenario:N", scale=color_scale, title="시나리오"), tooltip=["Scenario", "Year", alt.Tooltip("Value", format=",.0f")]).properties(width='container', height=300, title="순이익 비교 (10년 추이)")

def create_pie_chart(res_data):
    df_cost = pd.DataFrame(res_data['Cost Breakdown'])
    base = alt.Chart(df_cost).encode(theta=alt.Theta("Value", stack=True))
    pie = base.mark_arc(outerRadius=100).encode(color=alt.Color("Category", title="비용 항목"), tooltip=["Category", alt.Tooltip("Value", format=",.0f")])
    return pie.properties(width='container', height=300, title=f"{res_data['Scenario']} 비용 구조")

# ---------------------------
# 4. 탭 및 레이아웃 구성
# ---------------------------
birth_total = base_cows * conception_rate
birth_female = birth_total * female_birth_ratio
birth_male = birth_total * (1 - female_birth_ratio)

def get_alloc_inputs(tab, key):
    with tab:
        st.info(f"생산 가이드 | 암송아지: **{birth_female:.1f}두** | 수송아지: **{birth_male:.1f}두**")
        c1, c2, c3 = st.columns(3)
        
        # 1. 교체율 및 대체우 설정 (c1)
        culls = c1.number_input(f"[{key}] 연간 도태(두)", value=15, key=f"c_{key}")
        repl_rate = (culls / base_cows) * 100 if base_cows > 0 else 0
        c1.metric(f"교체율 ({key})", f"{repl_rate:.1f}%")
        
        # 2. 암송아지 분배 (c2)
        c2.markdown(f"**[{key}] 암송아지 분배**")
        c2.text_input(f"대체우 선발 [고정]", value=f"{culls} (자동)", disabled=True, key=f"rd_{key}_{culls}")
        fsell = c2.number_input(f"판매(두)", value=0, key=f"fs_{key}")
        ffat_in = c2.number_input(f"자가비육 투입", value=10, key=f"fi_{key}")
        ffat_out = c2.number_input(f"자가비육 출하", value=10, key=f"fo_{key}")
        
        if ffat_out > ffat_in: c2.error(f"오류: 투입({ffat_in}) < 출하({ffat_out})")
        
        floss = c2.number_input(f"폐사(두)", value=0, key=f"fl_{key}")
        loss_months = c2.number_input(f"폐사 월령", value=4, key=f"lm_{key}")

        # [추가됨] 암송아지 합계 검증
        # 대체우(culls) + 판매 + 투입 + 폐사
        sum_female = culls + fsell + ffat_in + floss
        if sum_female > birth_female:
            c2.error(f"⚠️ 합계({sum_female}두)가 생산({birth_female:.1f}두)을 초과했습니다.")

        # 3. 수송아지 분배 (c3)
        c3.markdown(f"**[{key}] 수송아지 분배**")
        kpn = c3.number_input(f"KPN 위탁", value=10, key=f"k_{key}")
        msell = c3.number_input(f"판매(두)", value=0, key=f"ms_{key}")
        mfat_in = c3.number_input(f"자가비육 투입", value=25, key=f"mi_{key}")
        mfat_out = c3.number_input(f"자가비육 출하", value=25, key=f"mo_{key}")
        
        if mfat_out > mfat_in: c3.error(f"오류: 투입({mfat_in}) < 출하({mfat_out})")
        
        mloss = c3.number_input(f"폐사(두)", value=0, key=f"ml_{key}")

        # [추가됨] 수송아지 합계 검증
        # KPN + 판매 + 투입 + 폐사 (출하는 투입에서 나오는 것이므로 합계 검증에서는 제외하는 것이 논리적으로 맞습니다)
        sum_male = kpn + msell + mfat_in + mloss
        if sum_male > birth_male:
            c3.error(f"⚠️ 합계({sum_male}두)가 생산({birth_male:.1f}두)을 초과했습니다.")

        return {
            "annual_culls": culls, "female_calf_sell": fsell, "female_fatten_in": ffat_in, "female_fatten_out": ffat_out, "female_loss": floss, "loss_months": loss_months,
            "kpn_male": kpn, "male_calf_sell": msell, "male_fatten_in": mfat_in, "male_fatten_out": mfat_out, "male_loss": mloss, "repl_rate": repl_rate
        }

# 탭 구성
tabs = st.tabs([
    "교체율 설정 A", 
    "교체율 설정 B", 
    "분석: 교체율 vs 개량효과", 
    " [부록] 비육우 매출 상세", 
    " [부록] 비용 상세 설정",
    " 🌾 배합비 최적화", 
    " 🌾 영양소 시뮬레이션"
])
tab_a, tab_b, tab_analysis, tab_revenue, tab_cost, tab_opt, tab_sim = tabs

# =============================================================================
# TABS 1~5: 경제성 분석
# =============================================================================

inputs_a = get_alloc_inputs(tab_a, "A")
inputs_b = get_alloc_inputs(tab_b, "B")
sc_name_a = f"교체율 {inputs_a['repl_rate']:.1f}%"
sc_name_b = f"교체율 {inputs_b['repl_rate']:.1f}%"
res_a = run_base_calc(sc_name_a, inputs_a)
res_b = run_base_calc(sc_name_b, inputs_b)

# --- Tab A ---
with tab_a:
    st.divider()
    st.metric("순이익 (Net Profit)", f"{fmt_money(res_a['Net Final'])}원")
    c1, c2 = st.columns([1.5, 1])
    with c1: st.altair_chart(create_net_profit_chart(res_a, res_b), use_container_width=True)
    with c2: st.altair_chart(create_pie_chart(res_a), use_container_width=True)
    st.subheader("상세 계산 내역")
    st.dataframe(make_excel_view(res_a).style.format({"금액 (Amount)": "{:,.0f}"}), use_container_width=True)

# --- Tab B ---
with tab_b:
    st.divider()
    st.metric("순이익 (Net Profit)", f"{fmt_money(res_b['Net Final'])}원")
    c1, c2 = st.columns([1.5, 1])
    with c1: st.altair_chart(create_net_profit_chart(res_a, res_b), use_container_width=True)
    with c2: st.altair_chart(create_pie_chart(res_b), use_container_width=True)
    st.subheader("상세 계산 내역")
    st.dataframe(make_excel_view(res_b).style.format({"금액 (Amount)": "{:,.0f}"}), use_container_width=True)

# --- Tab Analysis ---
with tab_analysis:
    st.header("분석: 교체율 증가 vs 개량 이득")
    col_setup, col_result = st.columns([1, 1.2])
    with col_setup:
        cull_a = res_a['n_cull']
        cull_b = res_b['n_cull']
        extra_repl = cull_b - cull_a
        rate_diff = inputs_b['repl_rate'] - inputs_a['repl_rate']
        st.metric("추가 교체 두수 (B-A)", f"{extra_repl}두", f"교체율 {rate_diff:+.1f}%p")
        if extra_repl <= 0: st.warning("시나리오 B의 교체율이 A보다 높아야 교체율 증가 비용이 계산됩니다.")
        st.markdown("**예상 개량 형질 입력 (증분 Δ)**")
        g1, g2 = st.columns(2)
        d_cw = g1.number_input("도체중 (CW) 증분 (kg)", value=5.0)
        d_ms = g2.number_input("근내지방 (MS) 증분", value=2.0)
        d_ema = g1.number_input("등심단면적 (EMA) 증분", value=1.0)
        d_bft = g2.number_input("등지방 (BFT) 증분", value=-0.5)
    with col_result:
        repl_unit_cost = (heifer_nonprofit_months / 12.0) * cow_cost_y
        added_cost = extra_repl * repl_unit_cost
        
        # 1. Premium per Head Calculation
        val_cw = d_cw * econ_cw
        val_ms = d_ms * econ_ms
        val_ema = d_ema * econ_ema
        val_bft = d_bft * econ_bft
        premium_per_head = val_cw + val_ms + val_ema + val_bft
        
        # 2. Volume Calculation (Fattening Cattle Only)
        # Target = Auto-fattened (F/M) + External Sales (Fattened)
        # Note: Selling calves (n_calf_f/m) is excluded from carcass premium
        target_cattle_a = res_a['n_fat_out_f'] + res_a['n_fat_out_m'] + res_a['n_ext_sell']
        target_cattle_b = res_b['n_fat_out_f'] + res_b['n_fat_out_m'] + res_b['n_ext_sell']
        
        # 3. Revenue Calculation
        added_revenue_a = target_cattle_a * premium_per_head # Hypothetical
        added_revenue_b = target_cattle_b * premium_per_head # Realized for B
        
        # Net Profit = Benefit of B (Genetic Revenue) - Cost of B (Extra Replacement)
        net_profit = added_revenue_b - added_cost
        
        chart_df = pd.DataFrame([
            {"Type": "1. 유전적 수익", "Amount": added_revenue_b, "Category": "수익"},
            {"Type": "2. 추가 비용", "Amount": -added_cost, "Category": "비용"},
            {"Type": "3. 분석 순이익", "Amount": net_profit, "Category": "순이익"}
        ])
        analysis_color = alt.Scale(domain=['수익', '비용', '순이익'], range=['#1f77b4', '#d62728', '#2ca02c'])
        chart = alt.Chart(chart_df).mark_bar(size=60).encode(
            x=alt.X("Type", axis=alt.Axis(labelAngle=0, title=None)), 
            y=alt.Y("Amount", axis=alt.Axis(format=",.0f")),
            color=alt.Color("Category", scale=analysis_color),
            tooltip=[alt.Tooltip("Type"), alt.Tooltip("Amount", format=",.0f")]
        ).properties(title="경제적 분석 결과 비교")
        st.altair_chart(chart, use_container_width=True)

        # ---------------------------------------------------------------------
        # DETAILED CALCULATION SECTION (NEW)
        # ---------------------------------------------------------------------
        st.divider()
        st.subheader("상세 계산 내역")
        
        # Step 1
        st.markdown("**1. 1두당 개량 가치 (Premium) 산출**")
        df_prem = pd.DataFrame({
            "형질": ["도체중(CW)", "근내지방(MS)", "등심단면적(EMA)", "등지방(BFT)"],
            "증분(Delta)": [d_cw, d_ms, d_ema, d_bft],
            "단가(원)": [econ_cw, econ_ms, econ_ema, econ_bft],
            "가치(원)": [val_cw, val_ms, val_ema, val_bft]
        })
        st.dataframe(df_prem, hide_index=True, use_container_width=True)
        st.caption(f"합계 (두당 가치): {fmt_money(premium_per_head)}원")
        
        # Step 2
        st.markdown("**2. 시나리오별 비육우 출하 두수 및 수익**")
        st.caption("※ 계산 대상: 자가비육 출하(암/수) + 외부비육 출하 (송아지 판매 제외)")
        df_vol = pd.DataFrame([
            {"시나리오": "시나리오 A", "비육우 출하(두)": target_cattle_a, "적용단가(원)": premium_per_head, "유전적 수익(가정)": added_revenue_a},
            {"시나리오": "시나리오 B", "비육우 출하(두)": target_cattle_b, "적용단가(원)": premium_per_head, "유전적 수익(실제)": added_revenue_b}
        ])
        st.dataframe(df_vol, hide_index=True, use_container_width=True)
        
        # Step 3
        st.markdown("**3. 최종 순이익 산출**")
        st.write("순이익 = (시나리오 B 유전적 수익) - (교체율 증가 비용)")
        st.write(f"{fmt_money(net_profit)}원 = {fmt_money(added_revenue_b)}원 - {fmt_money(added_cost)}원")

# --- Tab Revenue ---
with tab_revenue:
    st.header("4. 비육우 매출 상세 설정")
    edited_cow = st.data_editor(st.session_state.df_cow, column_config={"Ratio(%)": st.column_config.NumberColumn("출현율(%)", format="%.1f%%"), "Price(KRW/kg)": st.column_config.NumberColumn("지육단가(원/kg)", format="%d"), "Weight(kg)": st.column_config.NumberColumn("도체중(kg)", format="%d")}, use_container_width=True, key="editor_cow")
    st.success(f"계산된 암비육우 평균 가격: **{fmt_money(calc_cow_price)}원**")
    st.markdown("---")
    edited_steer = st.data_editor(st.session_state.df_steer, column_config={"Ratio(%)": st.column_config.NumberColumn("출현율(%)", format="%.1f%%"), "Price(KRW/kg)": st.column_config.NumberColumn("지육단가(원/kg)", format="%d"), "Weight(kg)": st.column_config.NumberColumn("도체중(kg)", format="%d")}, use_container_width=True, key="editor_steer")
    st.success(f"계산된 수비육우 평균 가격: **{fmt_money(calc_steer_price)}원**")
    
    st.markdown("#### 💡 매출 산출 상세 내역")
    rev_breakdown = []
    rev_breakdown.append({"구분": "암비육우", "계산식": "Σ (지육단가 × 도체중 × 출현율)", "결과": f"{fmt_money(calc_cow_price)}원"})
    rev_breakdown.append({"구분": "수비육우", "계산식": "Σ (지육단가 × 도체중 × 출현율)", "결과": f"{fmt_money(calc_steer_price)}원"})
    st.table(pd.DataFrame(rev_breakdown))

# --- Tab Cost ---
with tab_cost:
    st.header("5. 비용 상세 항목 설정")
    st.info(f"현재 선택된 모드: **{cost_mode}**")
    
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        st.subheader("① 번식우 유지비 상세(단위:천원)")
        edited_breed_cost = st.data_editor(
            st.session_state.df_cost_breed, 
            key="editor_cost_breed", 
            use_container_width=True, 
            column_config={
                "금액(천원/년)": st.column_config.NumberColumn("금액(천원/년)", format="%d")
            }
        )
        st.success(f" 번식우 합계 ({mode_key}): **{fmt_money(calc_breed_cost)}원**")
        
        st.markdown("---")
        st.markdown("**송아지 생산 관련 입력**")
        st.number_input("수태율 (0~1)", value=st.session_state.conception_rate, disabled=True, key='cost_concept_disp')
        st.caption("※ 수태율은 사이드바 또는 'A. 농장 공통 설정'에서 변경하세요.")
        
        bp_income = st.number_input("부산물 수입 (원/두)", value=st.session_state.get('by_product_income', 0), step=10000, key='bp_income_input')
        st.session_state.by_product_income = bp_income

    with col_c2:
        st.subheader("② 비육우 유지비 상세(단위:천원)")
        edited_fatten_cost = st.data_editor(
            st.session_state.df_cost_fatten, 
            key="editor_cost_fatten", 
            use_container_width=True, 
            column_config={
                "금액(천원/년)": st.column_config.NumberColumn("금액(천원/년)", format="%d")
            }
        )
        st.success(f" 비육우 합계 ({mode_key}): **{fmt_money(calc_fatten_cost)}원**")
        st.markdown("---")
        stock_cost = st.number_input("가축비 (송아지 구입비, 참고용, 계산 X)", value=4000000, step=100000)
        total_fatten_prod = calc_fatten_cost + stock_cost
        st.caption(f"※ (참고) 가축비 포함 총 투입비: {fmt_money(total_fatten_prod)}원")

    st.divider()
    
    # [추가] 상세 산출 내역 표시 (기회비용 차감 로직 구체화)
    st.markdown("#### 💡 비용 산출 상세 내역")
    
    # 기회비용 합계 계산
    opp_cols = ["자가노동비", "자본용역비", "토지용역비"]
    opp_sum_breed = calculate_opportunity_cost(st.session_state.df_cost_breed)
    opp_sum_fatten = calculate_opportunity_cost(st.session_state.df_cost_fatten)
    
    # 번식우 전체 합계(생산비 기준)
    total_breed_prod = calculate_cost_from_table(st.session_state.df_cost_breed, mode="생산비")
    total_fatten_prod = calculate_cost_from_table(st.session_state.df_cost_fatten, mode="생산비")
    
    cost_breakdown_data = []
    
    # 1. 번식우
    if mode_key == "경영비":
        formula_breed = f"전체 합계({fmt_money(total_breed_prod)}) - 기회비용({fmt_money(opp_sum_breed)})"
    else:
        formula_breed = f"전체 합계(기회비용 {fmt_money(opp_sum_breed)} 포함)"
        
    cost_breakdown_data.append({
        "항목": f"번식우 유지비 ({mode_key})",
        "산출식": formula_breed,
        "금액": f"{fmt_money(calc_breed_cost)}원"
    })
    
    # 2. 송아지
    if st.session_state.conception_rate > 0:
        calf_prod = (calc_breed_cost / st.session_state.conception_rate) - bp_income
        cost_breakdown_data.append({
            "항목": "송아지 생산비 (두당)",
            "산출식": "(번식우 유지비 ÷ 수태율) - 부산물 수입",
            "금액": f"{fmt_money(calf_prod)}원"
        })
    
    # 3. 비육우
    if mode_key == "경영비":
        formula_fatten = f"전체 합계({fmt_money(total_fatten_prod)}) - 기회비용({fmt_money(opp_sum_fatten)})"
    else:
        formula_fatten = f"전체 합계(기회비용 {fmt_money(opp_sum_fatten)} 포함)"
        
    cost_breakdown_data.append({
        "항목": f"비육우 유지비 ({mode_key})",
        "산출식": formula_fatten,
        "금액": f"{fmt_money(calc_fatten_cost)}원"
    })
    
    st.table(pd.DataFrame(cost_breakdown_data))
    
    if mode_key == "경영비":
        st.caption(f"※ 제외된 기회비용 항목: {', '.join(opp_cols)}")

    st.session_state.df_cost_breed = edited_breed_cost
    st.session_state.df_cost_fatten = edited_fatten_cost


# =============================================================================
# TAB 6: 배합비 최적화
# =============================================================================
with tab_opt:
    st.header("배합비 최적화 (비용 최소화)")
    
    # 1. 설정 (Expander)
    with st.expander("원료 단가 및 선호 사료 설정", expanded=False):
        c_conf1, c_conf2 = st.columns(2)
        with c_conf1:
            st.subheader("단가 수정")
            updated_feeds = st.session_state.feeds_db.copy()
            for i, feed in enumerate(updated_feeds):
                new_price = st.number_input(
                    f"{feed['name']} 단가 (원)", value=feed['price'], step=10, key=f"t1_price_{i}"
                )
                updated_feeds[i]['price'] = new_price
            st.session_state.feeds_db = updated_feeds
        with c_conf2:
            st.subheader("선호 사료 지정")
            feed_names = [f['name'] for f in st.session_state.feeds_db]
            priority_feeds = st.multiselect("의무 사용 원료", feed_names)
            min_ratio = 0.0
            if priority_feeds:
                min_ratio = st.slider("최소 사용 비율 (%)", 1.0, 50.0, 10.0)

    # 2. 목표치 입력
    col_input, col_result = st.columns([1, 1.5])
    
    with col_input:
        st.subheader("목표 영양소 설정")
        with st.container(border=True):
            target_tdn = st.number_input("TDN (에너지) % 이상", value=62.0, step=0.5, key="t1_tdn")
            target_cp = st.number_input("CP (단백질) % 이상", value=12.0, step=0.5, key="t1_cp")
            target_ndf = st.number_input("NDF (섬유소) % 이상", value=35.0, step=0.5, key="t1_ndf")
            
            st.write("---")
            price_hike = st.slider("가격 인상 시뮬레이션 (%)", 0, 50, 0, key="t1_hike")
            st.caption("설정된 단가에서 %만큼 인상되었을 때의 비용을 계산합니다.")

        run_opt = st.button("최적화 실행 (Run)", type="primary", use_container_width=True)

    # 3. 결과 로직
    with col_result:
        if run_opt:
            feeds = st.session_state.feeds_db
            prices = np.array([f['price'] for f in feeds])
            tdn_arr = np.array([f['tdn'] for f in feeds])
            cp_arr = np.array([f['cp'] for f in feeds])
            ndf_arr = np.array([f['ndf'] for f in feeds])
            names = [f['name'] for f in feeds]
            targets = {'tdn': target_tdn, 'cp': target_cp, 'ndf': target_ndf}

            def optimize(p_feeds, p_min_r):
                bounds = []
                for name in names:
                    if name in p_feeds: bounds.append((p_min_r, 100))
                    else: bounds.append((0, 100))
                
                cons = [
                    {'type': 'eq', 'fun': lambda x: np.sum(x) - 100},
                    {'type': 'ineq', 'fun': lambda x: np.dot(x, tdn_arr) - targets['tdn'] * 100},
                    {'type': 'ineq', 'fun': lambda x: np.dot(x, cp_arr) - targets['cp'] * 100},
                    {'type': 'ineq', 'fun': lambda x: np.dot(x, ndf_arr) - targets['ndf'] * 100}
                ]
                x0 = [100/len(feeds)] * len(feeds)
                return minimize(lambda x: np.dot(x, prices), x0, bounds=bounds, constraints=cons, method='SLSQP')

            res = optimize(priority_feeds, min_ratio)
            
            success = res.success
            if not success and priority_feeds:
                res = optimize([], 0)
                if res.success:
                    st.warning("선호 조건을 제외하고 최적화를 수행했습니다.")
                    success = True

            if not success:
                st.error("조건을 만족하는 배합을 찾을 수 없습니다.")
            else:
                st.success("최적 배합 산출 완료")
                ratios = np.round(res.x, 2)
                
                final_tdn = np.dot(ratios, tdn_arr) / 100
                final_cp = np.dot(ratios, cp_arr) / 100
                final_ndf = np.dot(ratios, ndf_arr) / 100
                
                amounts = dmi * (ratios / 100)
                base_daily_cost = np.dot(amounts, prices)
                hiked_daily_cost = base_daily_cost * (1 + price_hike / 100)
                cost_diff = hiked_daily_cost - base_daily_cost

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("TDN", f"{final_tdn:.1f}%", f"{final_tdn-target_tdn:.1f}")
                m2.metric("CP", f"{final_cp:.1f}%", f"{final_cp-target_cp:.1f}")
                m3.metric("NDF", f"{final_ndf:.1f}%", f"{final_ndf-target_ndf:.1f}")
                
                cost_label = "예상 비용(일)" if price_hike > 0 else "현재 비용(일)"
                m4.metric(cost_label, f"{int(hiked_daily_cost):,}원", f"+{int(cost_diff):,}원 (인상)" if price_hike > 0 else None, delta_color="inverse")

                df_res = pd.DataFrame({"원료": names, "비율(%)": ratios, "급여량(kg)": amounts, "단가": prices, "금액": amounts*prices})
                df_res = df_res[df_res["비율(%)"] > 0.1].sort_values("비율(%)", ascending=False)
                st.dataframe(df_res, hide_index=True, use_container_width=True)

                st.divider()
                st.subheader("배합 비율 차트")
                fig = px.pie(df_res, values='비율(%)', names='원료', title='최적 배합 비율', hole=0.4)
                fig.update_traces(textposition='inside', textinfo='percent+label')
                fig.update_layout(showlegend=True)
                st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# TAB 7: 영양소 시뮬레이션
# =============================================================================
with tab_sim:
    st.header("사용자 지정 배합 시뮬레이션")
    
    stage_specs = {
        "비육우 육성기(6~12개월)": {"tdn": 69.0, "cp": 15.0, "ndf": 30.0},
        "비육기 전기(13~18개월)": {"tdn": 71.0, "cp": 11.5, "ndf": 28.0},
        "비육기 후기(19~30개월)": {"tdn": 72.5, "cp": 10.5, "ndf": 25.0},
        "번식우 (임신/포유)": {"tdn": 62.0, "cp": 13.0, "ndf": 35.0}
    }
    
    col_sel, col_empty = st.columns([1, 2])
    with col_sel:
        selected_stage = st.selectbox("비교할 사양 표준 단계 선택", list(stage_specs.keys()))
    std = stage_specs[selected_stage]

    st.subheader("사료 배합 비율 설정 (%)")
    feeds = st.session_state.feeds_db
    user_ratios = []
    
    cols = st.columns(3)
    for i, feed in enumerate(feeds):
        with cols[i % 3]:
            val = st.number_input(f"{feed['name']} (%)", 0.0, 100.0, 0.0, 1.0, key=f"sim_{i}")
            user_ratios.append(val)
    
    total_ratio = sum(user_ratios)
    if abs(total_ratio - 100.0) > 0.1 and total_ratio > 0:
        st.warning(f"현재 비율 합계: {total_ratio:.1f}% (100%를 맞춰주세요)")

    cur_tdn = sum([r * f['tdn'] for r, f in zip(user_ratios, feeds)]) / 100
    cur_cp = sum([r * f['cp'] for r, f in zip(user_ratios, feeds)]) / 100
    cur_ndf = sum([r * f['ndf'] for r, f in zip(user_ratios, feeds)]) / 100

    # 일일 사료비 계산
    total_daily_cost = 0
    for r, f in zip(user_ratios, feeds):
        total_daily_cost += (dmi * (r / 100)) * f['price']

    def check(val, target, is_min=True):
        diff = val - target
        if is_min:
            return "충족" if val >= target else f"부족 ({diff:.1f})"
        return val 

    st.divider()
    st.subheader("분석 결과")
    
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("TDN (에너지)", f"{cur_tdn:.2f}%", f"목표: {std['tdn']}%")
    r1.caption(f"판정: {check(cur_tdn, std['tdn'])}")
    r2.metric("CP (단백질)", f"{cur_cp:.2f}%", f"목표: {std['cp']}%")
    r2.caption(f"판정: {check(cur_cp, std['cp'])}")
    r3.metric("NDF (섬유소)", f"{cur_ndf:.2f}%", f"목표: {std['ndf']}%")
    r3.caption(f"판정: {check(cur_ndf, std['ndf'])}")
    r4.metric("일일 사료비", f"{int(total_daily_cost):,}원", f"DMI {dmi:.1f}kg 기준")

    st.divider()
    c_chart, c_desc = st.columns([1, 1])
    
    sim_df = pd.DataFrame({"원료": [f['name'] for f in feeds], "비율": user_ratios})
    sim_df = sim_df[sim_df['비율'] > 0]
    
    with c_chart:
        if not sim_df.empty:
            fig2 = px.pie(sim_df, values='비율', names='원료', title='현재 입력 배합 비율', hole=0.4)
            fig2.update_traces(textposition='inside', textinfo='percent+label')
            fig2.update_layout(showlegend=True)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("사료 비율을 입력하면 차트가 표시됩니다.")

    with c_desc:
        st.markdown("#### 상세 계산 내역")
        st.write(f"**총 DMI: {dmi:.2f} kg** (사이드바 설정 기준)")
        
        with st.expander("영양소 계산식 보기"):
            terms_tdn = [f"{r}%×{f['tdn']}" for r, f in zip(user_ratios, feeds) if r > 0]
            terms_cp = [f"{r}%×{f['cp']}" for r, f in zip(user_ratios, feeds) if r > 0]
            terms_ndf = [f"{r}%×{f['ndf']}" for r, f in zip(user_ratios, feeds) if r > 0]
            
            st.markdown("**1. TDN (Total Digestible Nutrients)**")
            if terms_tdn:
                st.code(f"Sum({terms_tdn}) / 100", language="python")
            else:
                st.code("0")
                
            st.markdown("**2. CP (Crude Protein)**")
            if terms_cp:
                st.code(f"Sum({terms_cp}) / 100", language="python")
            else:
                st.code("0")

            st.markdown("**3. NDF (Neutral Detergent Fiber)**")
            if terms_ndf:
                st.code(f"Sum({terms_ndf}) / 100", language="python")
            else:
                st.code("0")

        st.markdown("**원료별 급여량**")
        for idx, row in sim_df.iterrows():
            amt = dmi * (row['비율'] / 100)
            st.write(f"- {row['원료']}: **{amt:.2f} kg**")

    st.divider()
    
    st.subheader("📊 원료별 영양성분 및 단가표")
    df_feeds_info = pd.DataFrame(st.session_state.feeds_db)
    df_feeds_info = df_feeds_info[['name', 'cat', 'price', 'tdn', 'cp', 'ndf']]
    df_feeds_info.columns = ['원료명', '분류', '단가(원/kg)', 'TDN(%)', 'CP(%)', 'NDF(%)']
    
    st.dataframe(
        df_feeds_info, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "단가(원/kg)": st.column_config.NumberColumn(format="%d원"),
            "TDN(%)": st.column_config.NumberColumn(format="%.1f%%"),
            "CP(%)": st.column_config.NumberColumn(format="%.1f%%"),
            "NDF(%)": st.column_config.NumberColumn(format="%.1f%%"),
        }
    )
