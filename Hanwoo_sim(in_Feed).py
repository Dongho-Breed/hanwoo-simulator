import streamlit as st
import pandas as pd
import altair as alt
import math
import numpy as np
from scipy.optimize import minimize

# 페이지 설정
st.set_page_config(page_title="한우 통합 경제성 분석 (V5.4.1)", layout="wide")

# ---------------------------
# 0. Data Initialization
# ---------------------------
# 비용 항목 초기 데이터
if 'cost_items' not in st.session_state:
    items = [
        "사료비", "수도광열비", "방역치료비", "자동차비", "농구비", "영농시설비", "기타재료비", "종부료",
        "차입금이자", "토지임차료", "고용노동비", "분뇨처리비", "생산관리비", "기타비용",
        "자가노동비", "자본용역비", "토지용역비"
    ]
    data_breed = {
        "항목": items,
        "금액(원/년)": [1500000, 140000, 110000, 80000, 50000, 40000, 30000, 50000, 60000, 5000, 20000, 10000, 20000, 30000, 800000, 200000, 50000]
    }
    data_fatten = {
        "항목": items,
        "금액(원/년)": [2300000, 140000, 80000, 80000, 50000, 40000, 30000, 0, 60000, 5000, 20000, 20000, 20000, 30000, 600000, 150000, 50000]
    }
    st.session_state.df_cost_breed = pd.DataFrame(data_breed)
    st.session_state.df_cost_fatten = pd.DataFrame(data_fatten)

# 등급별 매출 데이터
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

# Tab 6용 사료 데이터
if 'feeds_db' not in st.session_state:
    st.session_state.feeds_db = [
        {"name": "알팔파", "cat": "조사료", "price": 900, "tdn": 52.5, "cp": 19.8, "ndf": 49.9},
        {"name": "IRG 사일리지", "cat": "조사료", "price": 350, "tdn": 37.6, "cp": 6.4, "ndf": 33.8},
        {"name": "볏짚", "cat": "조사료", "price": 200, "tdn": 39.0, "cp": 4.5, "ndf": 70.0},
        {"name": "옥수수", "cat": "농후사료", "price": 550, "tdn": 76.7, "cp": 7.2, "ndf": 8.4},
        {"name": "배합사료", "cat": "농후사료", "price": 650, "tdn": 70.0, "cp": 17.0, "ndf": 27.0},
        {"name": "TMR", "cat": "TMR", "price": 350, "tdn": 68.0, "cp": 12.0, "ndf": 35.0},
    ]

# ---------------------------
# 1. Helpers & Callbacks
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

def input_with_comma(label, value, key=None, force_value=None):
    if force_value is not None:
        st.session_state[key] = f"{int(force_value):,}"
    elif key and key not in st.session_state:
        st.session_state[key] = f"{int(value):,}"
    st.text_input(label, key=key, on_change=format_callback, args=(key,))
    try:
        return float(str(st.session_state[key]).replace(",", ""))
    except:
        return float(value)

# ---------------------------
# 2. Calculation Logic
# ---------------------------
def calculate_cost_from_table(df, mode="경영비"):
    exclude_items = ["자가노동비", "자본용역비", "토지용역비"]
    total = 0
    for _, row in df.iterrows():
        item = row['항목']
        amount = row['금액(원/년)']
        if mode == "경영비" and item in exclude_items:
            continue
        total += amount
    return total

def calculate_avg_price(df):
    weighted_sum = 0
    for _, row in df.iterrows():
        weighted_sum += (row["Ratio(%)"] / 100) * (row["Price(KRW/kg)"] * row["Weight(kg)"])
    return int(weighted_sum)

# ---------------------------
# 3. Sidebar UI
# ---------------------------
calc_cow_price = calculate_avg_price(st.session_state.df_cow)
calc_steer_price = calculate_avg_price(st.session_state.df_steer)

st.title("한우 통합 경제성 분석 (V5.4.1)")
st.caption("모든 탭 기능 정상화 및 사료 최적화 기능 탑재")

with st.sidebar:
    st.header("1. 분석 기준 설정")
    cost_mode = st.radio("비용 산출 기준", ["경영비 기준 (실지출)", "생산비 기준 (기회비용 포함)"], index=0)
    mode_key = "경영비" if "경영비" in cost_mode else "생산비"
    
    calc_breed_cost = calculate_cost_from_table(st.session_state.df_cost_breed, mode_key)
    calc_fatten_cost = calculate_cost_from_table(st.session_state.df_cost_fatten, mode_key)
    
    st.divider()
    st.header("2. 기본 환경 설정")
    with st.expander("A. 농장 공통 설정", expanded=True):
        base_cows = st.number_input("기초 번식우(두)", value=100, step=10, format="%d")
        if 'conception_rate' not in st.session_state: st.session_state.conception_rate = 0.75
        conception_rate = st.number_input("수태율 (0~1)", value=st.session_state.conception_rate, step=0.01, key='sb_concept')
        female_birth_ratio = st.number_input("암 성비 (0~1)", value=0.50, step=0.01)
        heifer_nonprofit_months = st.number_input("대체우 무수익(월)", 19)
        calf_common_months = st.number_input("송아지 공통육성(월)", 7)
        kpn_exit_months = st.number_input("KPN 종료월령", 7)
        
    with st.expander("B. 비용 (원/년/두) - 자동 연동", expanded=True):
        st.caption(f"※ {mode_key} 기준으로 자동 계산된 값입니다.")
        cow_cost_y = input_with_comma("번식우 유지비", 3200000, key="cow_cost", force_value=calc_breed_cost)
        avg_cost_calc = input_with_comma("비육우 연간 유지비", 2500000, key="fatten_avg_cost", force_value=calc_fatten_cost)
        cost_rearing_y = avg_cost_calc
        cost_fatten_early_y = avg_cost_calc
        cost_fatten_late_y = avg_cost_calc

    with st.expander("C. 가격 (원/두) - 자동 연동", expanded=False):
        p_calf_f = input_with_comma("암송아지", 1300000, key="p_calf_f")
        p_calf_m = input_with_comma("수송아지", 2500000, key="p_calf_m")
        p_fat_f = input_with_comma("암비육우", 7500000, key="p_fat_f", force_value=calc_cow_price)
        p_fat_m = input_with_comma("수비육우", 9000000, key="p_fat_m", force_value=calc_steer_price)
        p_cull = input_with_comma("도태우", 2500000, key="p_cull")
        
    with st.expander("D. 출하월령", expanded=False):
        ship_m_f = st.number_input("암 출하월령", 30)
        ship_m_m = st.number_input("수 출하월령", 30)
        
    with st.expander("E. 외부 비육 농가", expanded=False):
        ext_buy_n = st.number_input("수송아지 매입(두)", value=50, step=1)
        ext_buy_p = input_with_comma("수송아지 매입가", 2500000, key="ebp")
        ext_sell_n = st.number_input("비육우 출하(두)", value=50, step=1)
        ext_sell_p = input_with_comma("비육우 출하가", 9000000, key="esp")
        ext_cost_y = input_with_comma("비육우 유지비", 2165000, key="ecy") 
        ext_period = st.number_input("비육우 기간(년)", value=2.5, min_value=0.1, step=0.1, format="%.1f")

    st.header("2. 형질별 경제적 가치")
    with st.expander("F. 개량 가치 (원/단위)", expanded=True):
        econ_cw = input_with_comma("도체중 (CW, kg)", 18564, key="ec_cw")
        econ_ms = input_with_comma("근내지방 (MS)", 591204, key="ec_ms")
        econ_ema = input_with_comma("등심단면적 (EMA)", 9163, key="ec_ema")
        econ_bft = input_with_comma("등지방 (BFT)", -57237, key="ec_bft")

# ---------------------------
# 4. Core Logic Scenarios
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
    val_ext_maint = (ext_sell_n * ext_period_y) * ext_cost_y
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
    data.append({"구분": "외부", "항목": "사육 유지비", "산출 근거": f"{res['n_ext_sell']}두 * {res['period_ext']}년 * {fmt_money(res['cost_y_ext'])}", "금액 (Amount)": -res["c_ext_maint"]})
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
# UI Layout
# ---------------------------
birth_total = base_cows * conception_rate
birth_female = birth_total * female_birth_ratio
birth_male = birth_total * (1 - female_birth_ratio)

def get_alloc_inputs(tab, key):
    with tab:
        st.info(f"생산 가이드 | 암송아지: **{birth_female:.1f}두** | 수송아지: **{birth_male:.1f}두**")
        c1, c2, c3 = st.columns(3)
        culls = c1.number_input(f"[{key}] 연간 도태(두)", value=15, key=f"c_{key}")
        repl_rate = (culls / base_cows) * 100 if base_cows > 0 else 0
        c1.metric(f"교체율 ({key})", f"{repl_rate:.1f}%")
        c2.markdown(f"**[{key}] 암송아지 분배**")
        c2.text_input(f"대체우 선발 [고정]", value=f"{culls} (자동)", disabled=True, key=f"rd_{key}_{culls}")
        fsell = c2.number_input(f"판매(두)", value=0, key=f"fs_{key}")
        ffat_in = c2.number_input(f"자가비육 투입", value=10, key=f"fi_{key}")
        ffat_out = c2.number_input(f"자가비육 출하", value=10, key=f"fo_{key}")
        if ffat_out > ffat_in: c2.error(f"오류: 투입({ffat_in}) < 출하({ffat_out})")
        floss = c2.number_input(f"폐사(두)", value=0, key=f"fl_{key}")
        loss_months = c2.number_input(f"폐사 월령", value=4, key=f"lm_{key}")
        c3.markdown(f"**[{key}] 수송아지 분배**")
        kpn = c3.number_input(f"KPN 위탁", value=10, key=f"k_{key}")
        msell = c3.number_input(f"판매(두)", value=0, key=f"ms_{key}")
        mfat_in = c3.number_input(f"자가비육 투입", value=25, key=f"mi_{key}")
        mfat_out = c3.number_input(f"자가비육 출하", value=25, key=f"mo_{key}")
        if mfat_out > mfat_in: c3.error(f"오류: 투입({mfat_in}) < 출하({mfat_out})")
        mloss = c3.number_input(f"폐사(두)", value=0, key=f"ml_{key}")
        return {
            "annual_culls": culls, "female_calf_sell": fsell, "female_fatten_in": ffat_in, "female_fatten_out": ffat_out, "female_loss": floss, "loss_months": loss_months,
            "kpn_male": kpn, "male_calf_sell": msell, "male_fatten_in": mfat_in, "male_fatten_out": mfat_out, "male_loss": mloss, "repl_rate": repl_rate
        }

tab_a, tab_b, tab_analysis, tab_revenue, tab_cost, tab_feed_opt = st.tabs(["교체율 설정 A", "교체율 설정 B", "분석: 교체율 vs 개량효과", " [부록] 비육우 매출 상세", " [부록] 비용 상세 설정", "🐂 [부록] 사료 배합 최적화"])

# ---------------------------
# [중요] 탭 내용 채우기 (With blocks)
# ---------------------------

# Inputs for Scenarios (미리 실행)
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
    st.subheader("📋 상세 계산 내역")
    st.dataframe(make_excel_view(res_a).style.format({"금액 (Amount)": "{:,.0f}"}), use_container_width=True)

# --- Tab B ---
with tab_b:
    st.divider()
    st.metric("순이익 (Net Profit)", f"{fmt_money(res_b['Net Final'])}원")
    c1, c2 = st.columns([1.5, 1])
    with c1: st.altair_chart(create_net_profit_chart(res_a, res_b), use_container_width=True)
    with c2: st.altair_chart(create_pie_chart(res_b), use_container_width=True)
    st.subheader("📋 상세 계산 내역")
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
        if extra_repl <= 0: st.warning("⚠️ 시나리오 B의 교체율이 A보다 높아야 교체율 증가 비용이 계산됩니다.")
        st.markdown("**예상 개량 형질 입력 (증분 Δ)**")
        g1, g2 = st.columns(2)
        d_cw = g1.number_input("도체중 (CW) 증분 (kg)", value=5.0)
        d_ms = g2.number_input("근내지방 (MS) 증분", value=2.0)
        d_ema = g1.number_input("등심단면적 (EMA) 증분", value=1.0)
        d_bft = g2.number_input("등지방 (BFT) 증분", value=-0.5)
    with col_result:
        repl_unit_cost = (heifer_nonprofit_months / 12.0) * cow_cost_y
        added_cost = extra_repl * repl_unit_cost
        premium_per_head = (d_cw * econ_cw) + (d_ms * econ_ms) + (d_ema * econ_ema) + (d_bft * econ_bft)
        total_sold = (res_b['n_fat_out_f'] + res_b['n_fat_out_m'] + res_b['n_ext_sell'] + res_b['n_calf_f'] + res_b['n_calf_m'])
        added_revenue = total_sold * premium_per_head
        net_profit = added_revenue - added_cost
        chart_df = pd.DataFrame([
            {"Type": "1. 유전적 수익", "Amount": added_revenue, "Category": "수익"},
            {"Type": "2. 추가 비용", "Amount": -added_cost, "Category": "비용"},
            {"Type": "3. 분석 순이익", "Amount": net_profit, "Category": "순이익"}
        ])
        analysis_color = alt.Scale(domain=['수익', '비용', '순이익'], range=['#1f77b4', '#d62728', '#2ca02c'])
        st.altair_chart(alt.Chart(chart_df).mark_line(color='gray').encode(x=alt.X("Type", sort=None), y="Amount") + alt.Chart(chart_df).mark_circle(size=150).encode(x=alt.X("Type", sort=None), y="Amount", color=alt.Color("Category", scale=analysis_color), tooltip=[alt.Tooltip("Type"), alt.Tooltip("Amount", format=",.0f")]), use_container_width=True)

# --- Tab Revenue ---
with tab_revenue:
    st.header("4. 비육우 매출 상세 설정")
    edited_cow = st.data_editor(st.session_state.df_cow, column_config={"Ratio(%)": st.column_config.NumberColumn("출현율(%)", format="%.1f%%"), "Price(KRW/kg)": st.column_config.NumberColumn("지육단가(원/kg)", format="%d원"), "Weight(kg)": st.column_config.NumberColumn("도체중(kg)", format="%dkg")}, use_container_width=True, key="editor_cow")
    st.success(f"💰 계산된 암비육우 평균 가격: **{fmt_money(calc_cow_price)}원**")
    st.markdown("---")
    edited_steer = st.data_editor(st.session_state.df_steer, column_config={"Ratio(%)": st.column_config.NumberColumn("출현율(%)", format="%.1f%%"), "Price(KRW/kg)": st.column_config.NumberColumn("지육단가(원/kg)", format="%d원"), "Weight(kg)": st.column_config.NumberColumn("도체중(kg)", format="%dkg")}, use_container_width=True, key="editor_steer")
    st.success(f"💰 계산된 수비육우 평균 가격: **{fmt_money(calc_steer_price)}원**")

# --- Tab Cost ---
with tab_cost:
    st.header("5. 비용 상세 항목 설정")
    st.info(f"현재 선택된 모드: **{cost_mode}**")
    
    col_c1, col_c2 = st.columns(2)
    
    # [좌측] 번식우 비용
    with col_c1:
        st.subheader("① 번식우 유지비 상세")
        edited_breed_cost = st.data_editor(
            st.session_state.df_cost_breed, 
            key="editor_cost_breed", 
            use_container_width=True, 
            column_config={"금액(원/년)": st.column_config.NumberColumn(format="%d원")}
        )
        
        sum_breed = calculate_cost_from_table(edited_breed_cost, mode_key)
        st.success(f" 번식우 합계 ({mode_key}): **{fmt_money(sum_breed)}원**")
        
        st.markdown("---")
        st.markdown("**송아지 생산 관련 입력**")
        c_rate = st.number_input("수태율 (0~1)", value=st.session_state.conception_rate, step=0.01, key='cost_concept')
        bp_income = st.number_input("부산물 수입 (원/두)", value=st.session_state.get('by_product_income', 0), step=10000, key='bp_income_input')
        st.session_state.conception_rate = c_rate
        st.session_state.by_product_income = bp_income

    # [우측] 비육우 비용
    with col_c2:
        st.subheader("② 비육우 유지비 상세")
        edited_fatten_cost = st.data_editor(
            st.session_state.df_cost_fatten, 
            key="editor_cost_fatten", 
            use_container_width=True, 
            column_config={"금액(원/년)": st.column_config.NumberColumn(format="%d원")}
        )
        
        sum_fatten = calculate_cost_from_table(edited_fatten_cost, mode_key)
        st.success(f" 비육우 합계 ({mode_key}): **{fmt_money(sum_fatten)}원**")
        
        st.markdown("---")
        stock_cost = st.number_input("가축비 (송아지 구입비, 참고용, 계산 X)", value=4000000, step=100000)
        total_fatten_prod = sum_fatten + stock_cost
        st.caption(f"※ (참고) 가축비 포함 총 투입비: {fmt_money(total_fatten_prod)}원")

    # [하단] 송아지 생산비 표시
    st.divider()
    if c_rate > 0:
        calf_prod = (sum_breed / c_rate) - bp_income
        st.info(f"🍼 **계산된 송아지 생산비 (기회비용 포함): {fmt_money(calf_prod)}원** \n*(산식: (번식우 유지비 ÷ 수태율) - 부산물 수입)*")
    else:
        st.warning("⚠️ 수태율이 0보다 커야 송아지 생산비를 계산할 수 있습니다.")

    # Update State for Sidebar
    st.session_state.df_cost_breed = edited_breed_cost
    st.session_state.df_cost_fatten = edited_fatten_cost

# --- Tab Feed Optimization (V5.4 Logic) ---
with tab_feed_opt:
    st.header("6. 사료 배합비 최적화 (Feed Optimizer)")
    st.markdown("사용자 입력(체중, 체중비, 영양소) 기반 **최소 비용 배합비**를 계산합니다.")
    
    # [1] Input Section
    fc1, fc2, fc3 = st.columns(3)
    
    with fc1:
        st.subheader("1. 섭취량 설정")
        input_weight = st.number_input("평균 체중 (kg)", value=450, step=10)
        input_ratio = st.number_input("체중비 (%)", value=2.0, step=0.1)
        target_dmi = input_weight * (input_ratio / 100)
        st.metric("목표 섭취량 (DMI)", f"{target_dmi:.2f} kg/일")

    with fc2:
        st.subheader("2. 영양소 요구량 (최소)")
        limit_tdn = st.number_input("TDN 최소 (%)", value=70.0)
        limit_cp = st.number_input("CP 최소 (%)", value=13.0)
        limit_ndf = st.number_input("NDF 최소 (%)", value=30.0)

    with fc3:
        st.subheader("3. 가격 변동 및 선호")
        price_hike = st.slider("사료 단가 인상 시뮬레이션 (%)", 0, 50, 0)
        df_feeds_temp = pd.DataFrame(st.session_state.feeds_db)
        preferred_feeds = st.multiselect("선호 사료 (최우선 사용)", df_feeds_temp['name'].tolist(), default=[])

    st.markdown("---")
    
    # [2] Feed Management & Logic
    col_setup, col_result = st.columns([1, 1.2])
    
    with col_setup:
        st.subheader("원료 단가 관리 (Expanders)")
        
        all_feeds = st.session_state.feeds_db
        categories = sorted(list(set(f['cat'] for f in all_feeds)))
        
        updated_feeds = []
        for cat in categories:
            with st.expander(f"{cat} 관리", expanded=False):
                cat_feeds = [f for f in all_feeds if f['cat'] == cat]
                df_cat = pd.DataFrame(cat_feeds)
                edited_df = st.data_editor(
                    df_cat,
                    column_config={"name": "원료명", "price": st.column_config.NumberColumn("단가(원)", format="%d"), "tdn": "TDN", "cp": "CP"},
                    hide_index=True,
                    key=f"editor_{cat}"
                )
                updated_feeds.extend(edited_df.to_dict('records'))
        
        st.session_state.feeds_db = updated_feeds
        
        def optimize_feed_logic(feeds, dmi, min_tdn, min_cp, min_ndf, preferred_list, hike_pct):
            df = pd.DataFrame(feeds)
            df['final_price'] = df['price'] * (1 + hike_pct/100)
            prices = df['final_price'].values
            n = len(df)
            
            cons_base = [
                {'type': 'eq', 'fun': lambda x: np.sum(x) - dmi}, # Total Weight
                {'type': 'ineq', 'fun': lambda x: np.sum(x * df['tdn'].values) - dmi * min_tdn}, # TDN
                {'type': 'ineq', 'fun': lambda x: np.sum(x * df['cp'].values) - dmi * min_cp}, # CP
                {'type': 'ineq', 'fun': lambda x: np.sum(x * df['ndf'].values) - dmi * min_ndf} # NDF
            ]
            bnds = tuple((0, dmi) for _ in range(n))
            x0 = np.ones(n) * (dmi / n)
            
            if preferred_list:
                pref_indices = [i for i, row in df.iterrows() if row['name'] in preferred_list]
                cons_s1 = cons_base + [{'type': 'ineq', 'fun': lambda x: np.sum(x[pref_indices]) - (dmi * 0.1)}]
                res = minimize(lambda x: np.dot(x, prices), x0, method='SLSQP', bounds=bnds, constraints=cons_s1)
                if res.success: return res, "1단계: 선호 사료 포함 최적화 성공"

            res = minimize(lambda x: np.dot(x, prices), x0, method='SLSQP', bounds=bnds, constraints=cons_base)
            if res.success: return res, "2단계: 최소 비용 최적화 성공 (선호 조건 제외)"
            
            def error_objective(x):
                curr_tdn = np.sum(x * df['tdn'].values) / dmi
                curr_cp = np.sum(x * df['cp'].values) / dmi
                return (curr_tdn - min_tdn)**2 + (curr_cp - min_cp)**2 + (np.sum(x) - dmi)**2
            
            res = minimize(error_objective, x0, method='SLSQP', bounds=bnds)
            return res, "3단계: 영양소 오차 최소화 (목표 미달 가능)"

        btn_calc = st.button("🚀 최적 배합비 계산", type="primary")

    with col_result:
        st.subheader("계산 결과")
        if btn_calc:
            res, msg = optimize_feed_logic(updated_feeds, target_dmi, limit_tdn, limit_cp, limit_ndf, preferred_feeds, price_hike)
            
            if res.success:
                st.success(msg)
                amounts = res.x
                df_res = pd.DataFrame(updated_feeds)
                df_res['급여량(kg)'] = amounts
                df_res['비율(%)'] = (amounts / target_dmi) * 100
                df_res['단가(인상후)'] = df_res['price'] * (1 + price_hike/100)
                df_res['비용(원)'] = df_res['급여량(kg)'] * df_res['단가(인상후)']
                
                df_display = df_res[df_res['급여량(kg)'] > 0.001].copy()
                
                total_cost = df_display['비용(원)'].sum()
                real_tdn = np.sum(df_display['급여량(kg)'] * df_display['tdn']) / target_dmi
                real_cp = np.sum(df_display['급여량(kg)'] * df_display['cp']) / target_dmi
                
                m1, m2, m3 = st.columns(3)
                m1.metric("일일 사료비", f"{int(total_cost):,}원")
                m2.metric("실제 TDN", f"{real_tdn:.1f}%", f"{real_tdn-limit_tdn:.1f}")
                m3.metric("실제 CP", f"{real_cp:.1f}%", f"{real_cp-limit_cp:.1f}")
                
                def highlight_preferred(row):
                    if row['name'] in preferred_feeds:
                        return ['background-color: #d0e8f2; color: black'] * len(row)
                    return [''] * len(row)

                st.dataframe(
                    df_display[['name', 'cat', '급여량(kg)', '비율(%)', '비용(원)']].style.apply(highlight_preferred, axis=1).format({
                        "급여량(kg)": "{:.2f}", "비율(%)": "{:.1f}", "비용(원)": "{:,.0f}"
                    }),
                    use_container_width=True
                )
                
                pie = alt.Chart(df_display).mark_arc(outerRadius=100).encode(
                    theta=alt.Theta("급여량(kg)", stack=True),
                    color=alt.Color("name", legend=alt.Legend(title="원료명")),
                    tooltip=["name", alt.Tooltip("급여량(kg)", format=".2f"), alt.Tooltip("비율(%)", format=".1f")]
                )
                st.altair_chart(pie, use_container_width=True)
                
            else:
                st.error("해를 찾을 수 없습니다.")

    # [3] Bottom Static Info
    st.markdown("---")
    st.markdown("#### 📝 참고: 영양소 계산 산식 및 고정 정보")
    
    info_c1, info_c2 = st.columns(2)
    with info_c1:
        st.markdown("**1. 주요 계산 산식**")
        st.latex(r"DMI_{target} = Weight \times \frac{\text{Ratio}}{100}")
        st.latex(r"Cost_{daily} = \sum (DMI \times \frac{Ratio_i}{100} \times Price_i)")

    with info_c2:
        st.markdown("**2. 한우 사양표준 권장치 (참고)**")
        ref_data = {
            "단계": ["번식우(임신)", "번식우(포유)", "비육 전기", "비육 후기"],
            "TDN(%)": [58.0, 62.0, 70.0, 74.0],
            "CP(%)": [10.0, 12.0, 13.0, 11.0]
        }
        st.dataframe(pd.DataFrame(ref_data), use_container_width=True, hide_index=True)
