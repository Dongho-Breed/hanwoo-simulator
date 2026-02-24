import streamlit as st
import pandas as pd
import altair as alt
import math
import numpy as np
import plotly.express as px

# 페이지 설정
st.set_page_config(page_title="한우 통합 플랫폼", layout="wide")

# ---------------------------
# 테마/스타일 상수 (색상·차트 재사용)
# ---------------------------
THEME = {
    "color_a": "#1f77b4",   # 시나리오 A / 수익
    "color_b": "#d62728",   # 시나리오 B / 비용
    "color_profit": "#2ca02c",  # 순이익
    "chart_height": 300,
}
_SCENARIO_SCALE = alt.Scale(domain=["시나리오 A", "시나리오 B"], range=[THEME["color_a"], THEME["color_b"]])
_ANALYSIS_SCALE = alt.Scale(domain=["수익", "비용", "순이익"], range=[THEME["color_a"], THEME["color_b"], THEME["color_profit"]])

def _inject_css():
    """최소한의 커스텀 CSS 주입 (한 번만 실행)"""
    st.markdown("""
    <style>
    /* 테이블/데이터프레임 가독성 */
    .stDataFrame { font-size: 0.9rem; }
    /* 메트릭 간격 조정 */
    [data-testid="stMetricValue"] { font-size: 1.4rem; }
    /* 사이드바 너비 */
    [data-testid="stSidebar"] { min-width: 280px; }
    </style>
    """, unsafe_allow_html=True)

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

_OPPORTUNITY_ITEMS: set[str] = {"자가노동비", "자본용역비", "토지용역비"}

def _get_amount_series(df: pd.DataFrame) -> pd.Series:
    match '금액(천원/년)' in df.columns:
        case True:
            return df['금액(천원/년)'] * 1000
        case False:
            return df['금액(원/년)']

def calculate_cost_from_table(df: pd.DataFrame, mode: str = "경영비") -> float:
    amounts = _get_amount_series(df)
    match mode:
        case "경영비":
            mask = ~df['항목'].isin(_OPPORTUNITY_ITEMS)
            return float(amounts[mask].sum())
        case "생산비" | _:
            return float(amounts.sum())

def calculate_opportunity_cost(df: pd.DataFrame) -> float:
    amounts  = _get_amount_series(df)
    mask     = df['항목'].isin(_OPPORTUNITY_ITEMS)
    return float(amounts[mask].sum())

def calculate_avg_price(df: pd.DataFrame) -> int:
    return int(
        (df["Ratio(%)"] / 100 * df["Price(KRW/kg)"] * df["Weight(kg)"]).sum()
    )

st.title("한우 통합 플랫폼")
_inject_css()

# ---------------------------
# 2. 사이드바 UI
# ---------------------------
with st.sidebar:
    st.header("1. 분석 기준 설정")
    cost_mode = st.radio("비용 산출 기준", ["경영비 기준 (실지출)", "생산비 기준 (기회비용 포함)"], index=0)
    mode_key = "경영비" if "경영비" in cost_mode else "생산비"

    EDITOR_TO_STATE: dict[str, str] = {
        "editor_cost_breed": "df_cost_breed",
        "editor_cost_fatten": "df_cost_fatten",
        "editor_cow":         "df_cow",
        "editor_steer":       "df_steer",
    }

    for editor_key, state_key in EDITOR_TO_STATE.items():
        if editor_key not in st.session_state:
            continue

        _edited = st.session_state[editor_key]

        match type(_edited).__name__:
            case "DataFrame":
                st.session_state[state_key] = _edited
            case "dict":
                _df = st.session_state[state_key].copy()
                for row_idx, changes in _edited.get("edited_rows", {}).items():
                    for col, val in changes.items():
                        _df.at[int(row_idx), col] = val
                st.session_state[state_key] = _df
            case _:
                pass

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
    cost_breeding_repl = annual_culls * cow_cost_y

    if conception_rate > 0:
        calf_prod_cost_unit = (cow_cost_y / conception_rate) - by_product_income_cow
    else:
        calf_prod_cost_unit = 0
    val_kpn_loss = clamp_int(kpn_male) * calf_prod_cost_unit * (clamp_int(kpn_exit_months, 0) / 12.0)
    
    val_fat_cost_f = clamp_int(female_fatten_in) * cost_fatten_avg_y
    val_fat_cost_m = clamp_int(male_fatten_in) * cost_fatten_avg_y
    
    cost_loss_head = calf_prod_cost_unit * (loss_months / 12.0)
    val_loss_f = female_loss * cost_loss_head
    val_loss_m = male_loss * cost_loss_head
    
    cost_internal = cost_breeding_main + cost_breeding_repl + val_kpn_loss + val_fat_cost_f + val_fat_cost_m + val_loss_f + val_loss_m
    net_internal = rev_internal - cost_internal

    val_ext_rev = ext_sell_n * ext_sell_p
    val_ext_buy = ext_buy_n * ext_buy_p
    val_ext_maint = ext_buy_n * ext_cost_y
    
    net_external = val_ext_rev - val_ext_buy - val_ext_maint

    net_final = net_internal + net_external
    rev_final = rev_internal + val_ext_rev
    cost_final = cost_internal + val_ext_buy + val_ext_maint

    fatten_period_f = max(0, ship_m_female - calf_common_months) / 12.0
    fatten_period_m = max(0, ship_m_male - calf_common_months) / 12.0

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
    data.append({"구분": "비용", "항목": "대체우 육성", "산출 근거": f"투입 {res['n_repl']}두 * 1년 * {fmt_money(res['cost_y_cow'])}", "금액 (Amount)": -res["c_breed_repl"]})
    data.append({"구분": "비용", "항목": "자가 암비육", "산출 근거": f"투입 {res['n_fat_in_f']}두 * 1년 * {fmt_money(res['cost_avg_fatten'])}", "금액 (Amount)": -res["c_fat_in_f"]})
    data.append({"구분": "비용", "항목": "자가 수비육", "산출 근거": f"투입 {res['n_fat_in_m']}두 * 1년 * {fmt_money(res['cost_avg_fatten'])}", "금액 (Amount)": -res["c_fat_in_m"]})
    
    data.append({"구분": "비용(손실)", "항목": "암송아지 폐사", "산출 근거": f"{res['n_loss_f']}두 * ({fmt_money(res['cost_y_cow'])}/{res['rate_concept']}) * ({res['loss_months']}/12)", "금액 (Amount)": -res["val_loss_f"]})
    data.append({"구분": "비용(손실)", "항목": "수송아지 폐사", "산출 근거": f"{res['n_loss_m']}두 * ({fmt_money(res['cost_y_cow'])}/{res['rate_concept']}) * ({res['loss_months']}/12)", "금액 (Amount)": -res["val_loss_m"]})
    data.append({"구분": "외부", "항목": "비육우 매출", "산출 근거": f"{res['n_ext_sell']}두 * {fmt_money(res['p_ext_sell'])}", "금액 (Amount)": res["v_ext_rev"]})
    data.append({"구분": "외부", "항목": "송아지 매입", "산출 근거": f"{res['n_ext_buy']}두 * {fmt_money(res['p_ext_buy'])}", "금액 (Amount)": -res["c_ext_buy"]})
    data.append({"구분": "외부", "항목": "사육 유지비", "산출 근거": f"매입 {res['n_ext_buy']}두 * 1년 * {fmt_money(res['cost_y_ext'])}", "금액 (Amount)": -res["c_ext_maint"]})
    data.append({"구분": "결과", "항목": "순이익 (Net Profit)", "산출 근거": "수익 - 비용", "금액 (Amount)": res["Net Final"]})
    return pd.DataFrame(data)

def create_net_profit_chart(res_a, res_b):
    years = list(range(1, 11))
    chart_data = [{"Scenario": "시나리오 A", "Year": y, "Value": res_a['Net Final']} for y in years] + [{"Scenario": "시나리오 B", "Year": y, "Value": res_b['Net Final']} for y in years]
    df_chart = pd.DataFrame(chart_data)
    return alt.Chart(df_chart).mark_line(point=True).encode(
        x=alt.X("Year:O", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("Value:Q", axis=alt.Axis(format=",.0f")),
        color=alt.Color("Scenario:N", scale=_SCENARIO_SCALE, title="시나리오"),
        tooltip=["Scenario", "Year", alt.Tooltip("Value", format=",.0f")]
    ).properties(width='container', height=THEME["chart_height"], title="순이익 비교 (10년 추이)")

def create_pie_chart(res_data):
    df_cost = pd.DataFrame(res_data['Cost Breakdown'])
    base = alt.Chart(df_cost).encode(theta=alt.Theta("Value", stack=True))
    pie = base.mark_arc(outerRadius=100).encode(
        color=alt.Color("Category", title="비용 항목"),
        tooltip=["Category", alt.Tooltip("Value", format=",.0f")]
    )
    return pie.properties(width='container', height=THEME["chart_height"], title=f"{res_data['Scenario']} 비용 구조")

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

        sum_female = culls + fsell + ffat_in + floss
        if sum_female > birth_female:
            c2.error(f"합계({sum_female}두)가 생산({birth_female:.1f}두)을 초과했습니다.")

        c3.markdown(f"**[{key}] 수송아지 분배**")
        kpn = c3.number_input(f"KPN 위탁", value=10, key=f"k_{key}")
        msell = c3.number_input(f"판매(두)", value=0, key=f"ms_{key}")
        mfat_in = c3.number_input(f"자가비육 투입", value=25, key=f"mi_{key}")
        mfat_out = c3.number_input(f"자가비육 출하", value=25, key=f"mo_{key}")
        if mfat_out > mfat_in: c3.error(f"오류: 투입({mfat_in}) < 출하({mfat_out})")
        mloss = c3.number_input(f"폐사(두)", value=0, key=f"ml_{key}")

        sum_male = kpn + msell + mfat_in + mloss
        if sum_male > birth_male:
            c3.error(f"합계({sum_male}두)가 생산({birth_male:.1f}두)을 초과했습니다.")

        return {
            "annual_culls": culls, "female_calf_sell": fsell, "female_fatten_in": ffat_in, "female_fatten_out": ffat_out, "female_loss": floss, "loss_months": loss_months,
            "kpn_male": kpn, "male_calf_sell": msell, "male_fatten_in": mfat_in, "male_fatten_out": mfat_out, "male_loss": mloss, "repl_rate": repl_rate
        }

tabs = st.tabs([
    "교체율 설정 A", 
    "교체율 설정 B", 
    "분석: 교체율 vs 개량효과", 
    " [부록] 비육우 매출 상세", 
    " [부록] 비용 상세 설정"
])
tab_a, tab_b, tab_analysis, tab_revenue, tab_cost = tabs

# =============================================================================
# TABS 1~5: 경제성 분석
# =============================================================================

inputs_a = get_alloc_inputs(tab_a, "A")
inputs_b = get_alloc_inputs(tab_b, "B")
sc_name_a = f"교체율 {inputs_a['repl_rate']:.1f}%"
sc_name_b = f"교체율 {inputs_b['repl_rate']:.1f}%"
res_a = run_base_calc(sc_name_a, inputs_a)
res_b = run_base_calc(sc_name_b, inputs_b)

with tab_a:
    st.divider()
    st.metric("순이익 (Net Profit)", f"{fmt_money(res_a['Net Final'])}원")
    c1, c2 = st.columns([1.5, 1])
    with c1: st.altair_chart(create_net_profit_chart(res_a, res_b), use_container_width=True)
    with c2: st.altair_chart(create_pie_chart(res_a), use_container_width=True)
    st.subheader("상세 계산 내역")
    st.dataframe(make_excel_view(res_a).style.format({"금액 (Amount)": "{:,.0f}"}), use_container_width=True)

with tab_b:
    st.divider()
    st.metric("순이익 (Net Profit)", f"{fmt_money(res_b['Net Final'])}원")
    c1, c2 = st.columns([1.5, 1])
    with c1: st.altair_chart(create_net_profit_chart(res_a, res_b), use_container_width=True)
    with c2: st.altair_chart(create_pie_chart(res_b), use_container_width=True)
    st.subheader("상세 계산 내역")
    st.dataframe(make_excel_view(res_b).style.format({"금액 (Amount)": "{:,.0f}"}), use_container_width=True)

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
        
        val_cw = d_cw * econ_cw
        val_ms = d_ms * econ_ms
        val_ema = d_ema * econ_ema
        val_bft = d_bft * econ_bft
        premium_per_head = val_cw + val_ms + val_ema + val_bft
        
        target_cattle_a = res_a['n_fat_out_f'] + res_a['n_fat_out_m'] + res_a['n_ext_sell']
        target_cattle_b = res_b['n_fat_out_f'] + res_b['n_fat_out_m'] + res_b['n_ext_sell']
        
        added_revenue_a = target_cattle_a * premium_per_head 
        added_revenue_b = target_cattle_b * premium_per_head 
        
        net_profit = added_revenue_b - added_cost
        
        chart_df = pd.DataFrame([
            {"Type": "1. 유전적 수익", "Amount": added_revenue_b, "Category": "수익"},
            {"Type": "2. 추가 비용", "Amount": -added_cost, "Category": "비용"},
            {"Type": "3. 분석 순이익", "Amount": net_profit, "Category": "순이익"}
        ])
        chart = alt.Chart(chart_df).mark_bar(size=60).encode(
            x=alt.X("Type", axis=alt.Axis(labelAngle=0, title=None)),
            y=alt.Y("Amount", axis=alt.Axis(format=",.0f")),
            color=alt.Color("Category", scale=_ANALYSIS_SCALE),
            tooltip=[alt.Tooltip("Type"), alt.Tooltip("Amount", format=",.0f")]
        ).properties(title="경제적 분석 결과 비교")
        st.altair_chart(chart, use_container_width=True)

        st.divider()
        st.subheader("상세 계산 내역")
        
        st.markdown("**1. 1두당 개량 가치 (Premium) 산출**")
        df_prem = pd.DataFrame({
            "형질": ["도체중(CW)", "근내지방(MS)", "등심단면적(EMA)", "등지방(BFT)"],
            "증분(Delta)": [d_cw, d_ms, d_ema, d_bft],
            "단가(원)": [econ_cw, econ_ms, econ_ema, econ_bft],
            "가치(원)": [val_cw, val_ms, val_ema, val_bft]
        })
        st.dataframe(df_prem, hide_index=True, use_container_width=True)
        st.caption(f"합계 (두당 가치): {fmt_money(premium_per_head)}원")
        
        st.markdown("**2. 시나리오별 비육우 출하 두수 및 수익**")
        st.caption("※ 계산 대상: 자가비육 출하(암/수) + 외부비육 출하 (송아지 판매 제외)")
        df_vol = pd.DataFrame([
            {"시나리오": "시나리오 A", "비육우 출하(두)": target_cattle_a, "적용단가(원)": premium_per_head, "유전적 수익(가정)": added_revenue_a},
            {"시나리오": "시나리오 B", "비육우 출하(두)": target_cattle_b, "적용단가(원)": premium_per_head, "유전적 수익(실제)": added_revenue_b}
        ])
        st.dataframe(df_vol, hide_index=True, use_container_width=True)
        
        st.markdown("**3. 최종 순이익 산출**")
        st.write("순이익 = (시나리오 B 유전적 수익) - (교체율 증가 비용)")
        st.write(f"{fmt_money(net_profit)}원 = {fmt_money(added_revenue_b)}원 - {fmt_money(added_cost)}원")

with tab_revenue:
    st.header("4. 비육우 매출 상세 설정")
    edited_cow = st.data_editor(st.session_state.df_cow, column_config={"Ratio(%)": st.column_config.NumberColumn("출현율(%)", format="%.1f%%"), "Price(KRW/kg)": st.column_config.NumberColumn("지육단가(원/kg)", format="%d"), "Weight(kg)": st.column_config.NumberColumn("도체중(kg)", format="%d")}, use_container_width=True, key="editor_cow")
    if isinstance(edited_cow, pd.DataFrame):
        st.session_state.df_cow = edited_cow
        calc_cow_price = calculate_avg_price(st.session_state.df_cow)
    st.success(f"계산된 암비육우 평균 가격: **{fmt_money(calc_cow_price)}원**")
    st.markdown("---")
    edited_steer = st.data_editor(st.session_state.df_steer, column_config={"Ratio(%)": st.column_config.NumberColumn("출현율(%)", format="%.1f%%"), "Price(KRW/kg)": st.column_config.NumberColumn("지육단가(원/kg)", format="%d"), "Weight(kg)": st.column_config.NumberColumn("도체중(kg)", format="%d")}, use_container_width=True, key="editor_steer")
    if isinstance(edited_steer, pd.DataFrame):
        st.session_state.df_steer = edited_steer
        calc_steer_price = calculate_avg_price(st.session_state.df_steer)
    st.success(f"계산된 수비육우 평균 가격: **{fmt_money(calc_steer_price)}원**")
    
    st.markdown("#### 매출 산출 상세 내역")
    rev_breakdown = []
    rev_breakdown.append({"구분": "암비육우", "계산식": "Σ (지육단가 × 도체중 × 출현율)", "결과": f"{fmt_money(calc_cow_price)}원"})
    rev_breakdown.append({"구분": "수비육우", "계산식": "Σ (지육단가 × 도체중 × 출현율)", "결과": f"{fmt_money(calc_steer_price)}원"})
    st.table(pd.DataFrame(rev_breakdown))

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
        if isinstance(edited_breed_cost, pd.DataFrame):
            st.session_state.df_cost_breed = edited_breed_cost
            calc_breed_cost = calculate_cost_from_table(st.session_state.df_cost_breed, mode_key)
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
        if isinstance(edited_fatten_cost, pd.DataFrame):
            st.session_state.df_cost_fatten = edited_fatten_cost
            calc_fatten_cost = calculate_cost_from_table(st.session_state.df_cost_fatten, mode_key)
        st.success(f" 비육우 합계 ({mode_key}): **{fmt_money(calc_fatten_cost)}원**")
        st.markdown("---")
        stock_cost = st.number_input("가축비 (송아지 구입비, 참고용, 계산 X)", value=4000000, step=100000)
        total_fatten_prod = calc_fatten_cost + stock_cost
        st.caption(f"※ (참고) 가축비 포함 총 투입비: {fmt_money(total_fatten_prod)}원")

    st.divider()
    st.markdown("#### 비용 산출 상세 내역")

    opp_cols = ["자가노동비", "자본용역비", "토지용역비"]
    opp_sum_breed  = calculate_opportunity_cost(st.session_state.df_cost_breed)
    opp_sum_fatten = calculate_opportunity_cost(st.session_state.df_cost_fatten)
    total_breed_prod  = calculate_cost_from_table(st.session_state.df_cost_breed,  mode="생산비")
    total_fatten_prod = calculate_cost_from_table(st.session_state.df_cost_fatten, mode="생산비")

    FORMULA_MAP: dict[str, callable] = {
        "경영비": lambda total, opp: f"전체 합계({fmt_money(total)}) - 기회비용({fmt_money(opp)})",
        "생산비": lambda total, opp: f"전체 합계(기회비용 {fmt_money(opp)} 포함)",
    }
    make_formula = FORMULA_MAP[mode_key]

    cost_breakdown_data = [
        {
            "항목":  f"번식우 유지비 ({mode_key})",
            "산출식": make_formula(total_breed_prod,  opp_sum_breed),
            "금액":  f"{fmt_money(calc_breed_cost)}원",
        },
        {
            "항목":  f"비육우 유지비 ({mode_key})",
            "산출식": make_formula(total_fatten_prod, opp_sum_fatten),
            "금액":  f"{fmt_money(calc_fatten_cost)}원",
        },
    ]

    if st.session_state.conception_rate > 0:
        calf_prod = (calc_breed_cost / st.session_state.conception_rate) - bp_income
        cost_breakdown_data.insert(1, {
            "항목":  "송아지 생산비 (두당)",
            "산출식": "(번식우 유지비 ÷ 수태율) - 부산물 수입",
            "금액":  f"{fmt_money(calf_prod)}원",
        })
    
    st.table(pd.DataFrame(cost_breakdown_data))
    
    if mode_key == "경영비":
        st.caption(f"※ 제외된 기회비용 항목: {', '.join(opp_cols)}")

        