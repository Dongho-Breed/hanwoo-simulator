import streamlit as st
import pandas as pd
import altair as alt
import math

# 페이지 설정
st.set_page_config(page_title="한우 통합 경제성 분석 (V4.7)", layout="wide")

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

def input_with_comma(label, value, key=None):
    if key and key not in st.session_state:
        st.session_state[key] = f"{int(value):,}"
    st.text_input(label, key=key, on_change=format_callback, args=(key,))
    try:
        return float(str(st.session_state[key]).replace(",", ""))
    except:
        return float(value)

# ---------------------------
# 2. Core Logic
# ---------------------------
def compute_scenario(
    name, 
    base_cows, conception_rate, female_birth_ratio, 
    heifer_nonprofit_months, calf_common_months, kpn_exit_months,
    # Allocations
    annual_culls, female_calf_sell, female_fatten_in, female_fatten_out, female_loss, loss_months,
    male_calf_sell, male_fatten_in, male_fatten_out, male_loss, kpn_male,
    # Costs & Prices
    cow_cost_y, 
    cost_rearing_y, cost_fatten_early_y, cost_fatten_late_y,
    price_calf_female, price_calf_male, price_fatten_female, price_fatten_male, price_cull_cow,
    ship_m_female, ship_m_male,
    ext_buy_n, ext_buy_p, ext_sell_n, ext_sell_p, ext_cost_y, ext_period_y
):
    base_cows = clamp_int(base_cows, 1)
    annual_culls = clamp_int(annual_culls, 0)
    
    # 3단계 비용 단순 평균
    cost_fatten_avg_y = (cost_rearing_y + cost_fatten_early_y + cost_fatten_late_y) / 3.0

    # 1. 매출 (Revenue)
    val_cull = annual_culls * price_cull_cow
    val_calf_f = clamp_int(female_calf_sell) * price_calf_female
    val_calf_m = clamp_int(male_calf_sell) * price_calf_male
    val_fat_out_f = clamp_int(female_fatten_out) * price_fatten_female
    val_fat_out_m = clamp_int(male_fatten_out) * price_fatten_male
    rev_internal = val_cull + val_calf_f + val_calf_m + val_fat_out_f + val_fat_out_m
    
    # 2. 비용 (Cost)
    # 2-1. 기초 번식우 유지비
    cost_breeding_main = base_cows * cow_cost_y
    heifer_years = clamp_int(heifer_nonprofit_months, 0) / 12.0
    cost_breeding_repl = (annual_culls * heifer_years) * cow_cost_y
    calf_prod_cost = cow_cost_y / conception_rate if conception_rate > 0 else 0
    val_kpn_loss = clamp_int(kpn_male) * calf_prod_cost * (clamp_int(kpn_exit_months, 0) / 12.0)
    
    # 2-2. 자가 비육 사육비
    fatten_period_f = max(0, ship_m_female - calf_common_months) / 12.0
    fatten_period_m = max(0, ship_m_male - calf_common_months) / 12.0
    
    cost_per_f = fatten_period_f * cost_fatten_avg_y
    cost_per_m = fatten_period_m * cost_fatten_avg_y
    
    val_fat_cost_f = clamp_int(female_fatten_in) * cost_per_f
    val_fat_cost_m = clamp_int(male_fatten_in) * cost_per_m
    
    # 2-3. 폐사 매몰비용 (송아지 생산비 기준)
    cost_loss_head = calf_prod_cost * (loss_months / 12.0)
    val_loss_f = female_loss * cost_loss_head
    val_loss_m = male_loss * cost_loss_head
    
    cost_internal = cost_breeding_main + cost_breeding_repl + val_kpn_loss + val_fat_cost_f + val_fat_cost_m + val_loss_f + val_loss_m
    net_internal = rev_internal - cost_internal

    # 3. 외부 비육 농장
    val_ext_rev = ext_sell_n * ext_sell_p
    val_ext_buy = ext_buy_n * ext_buy_p
    val_ext_maint = (ext_sell_n * ext_period_y) * ext_cost_y
    net_external = val_ext_rev - val_ext_buy - val_ext_maint

    # 4. 최종 합산
    net_final = net_internal + net_external
    rev_final = rev_internal + val_ext_rev
    cost_final = cost_internal + val_ext_buy + val_ext_maint

    # 5. 비용 구조 데이터 (Cost Breakdown)
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
        # Basis Data
        "months_heifer": heifer_nonprofit_months,
        "months_kpn": kpn_exit_months,
        "rate_concept": conception_rate,
        "period_f": fatten_period_f,
        "period_m": fatten_period_m,
        "period_ext": ext_period_y,
        "cost_avg_fatten": cost_fatten_avg_y,
        
        # Detailed Data
        "v_cull": val_cull, "n_cull": annual_culls,
        "v_calf_f": val_calf_f, "n_calf_f": female_calf_sell,
        "v_calf_m": val_calf_m, "n_calf_m": male_calf_sell,
        "v_fat_out_f": val_fat_out_f, "n_fat_out_f": female_fatten_out,
        "v_fat_out_m": val_fat_out_m, "n_fat_out_m": male_fatten_out,
        "c_breed_main": cost_breeding_main, "n_base": base_cows,
        "c_breed_repl": cost_breeding_repl, "n_repl": annual_culls,
        "c_kpn": val_kpn_loss, "n_kpn": kpn_male,
        "c_fat_in_f": val_fat_cost_f, "n_fat_in_f": female_fatten_in,
        "c_fat_in_m": val_fat_cost_m, "n_fat_in_m": male_fatten_in,
        "val_loss_f": val_loss_f, "val_loss_m": val_loss_m, 
        "n_loss_f": female_loss, "n_loss_m": male_loss,
        "cost_loss_head": cost_loss_head, "loss_months": loss_months,
        "v_ext_rev": val_ext_rev, "n_ext_sell": ext_sell_n,
        "c_ext_buy": val_ext_buy, "n_ext_buy": ext_buy_n,
        "c_ext_maint": val_ext_maint, "n_ext_stock": ext_sell_n * ext_period_y,
        "p_cull": price_cull_cow, "p_calf_f": price_calf_female, "p_calf_m": price_calf_male,
        "p_fat_f": price_fatten_female, "p_fat_m": price_fatten_male,
        "cost_y_cow": cow_cost_y, 
        "p_ext_sell": ext_sell_p, "p_ext_buy": ext_buy_p, "cost_y_ext": ext_cost_y
    }

# ---------------------------
# 3. UI & Inputs
# ---------------------------
st.title("한우 통합 경제성 분석 (V4.7)")
st.caption("순이익 비교 그래프(A vs B) 및 파이차트 시인성 개선")

with st.sidebar:
    st.header("1. 기본 환경 설정")
    with st.expander("A. 농장 공통 설정", expanded=True):
        base_cows = st.number_input("기초 번식우(두)", value=100, step=10, format="%d")
        conception_rate = st.number_input("수태율 (0~1)", value=0.75, step=0.01)
        female_birth_ratio = st.number_input("암 성비 (0~1)", value=0.50, step=0.01)
        heifer_nonprofit_months = st.number_input("대체우 무수익(월)", 19)
        calf_common_months = st.number_input("송아지 공통육성(월)", 7)
        kpn_exit_months = st.number_input("KPN 종료월령", 7)
        
    with st.expander("B. 비용 (원/년/두)", expanded=False):
        cow_cost_y = input_with_comma("번식우 유지비", 3200000, key="cow_cost")
        
        st.markdown("**비육우 단계별 비용 (입력)**")
        cost_rearing_y = input_with_comma("육성기 비용", 1800000, key="rearing_cost")
        cost_fatten_early_y = input_with_comma("비육전기 비용", 2200000, key="early_cost")
        cost_fatten_late_y = input_with_comma("비육후기 비용", 2750000, key="late_cost")
        
        avg_cost_calc = (cost_rearing_y + cost_fatten_early_y + cost_fatten_late_y) / 3
        st.info(f"비육우 평균 연간 유지비: **{fmt_money(avg_cost_calc)}원**")

    with st.expander("C. 가격 (원/두)", expanded=False):
        p_calf_f = input_with_comma("암송아지", 1300000, key="p_calf_f")
        p_calf_m = input_with_comma("수송아지", 2500000, key="p_calf_m")
        p_fat_f = input_with_comma("암비육우", 7500000, key="p_fat_f")
        p_fat_m = input_with_comma("수비육우", 9000000, key="p_fat_m")
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

    # 형질별 경제적 가치 입력
    st.header("2. 형질별 경제적 가치 (Economic Values)")
    with st.expander("F. 개량 가치 (원/단위)", expanded=True):
        st.caption("단위 개량당 증가하는 추가 수익을 설정합니다.")
        econ_cw = input_with_comma("도체중 (CW, kg)", 18564, key="ec_cw")
        econ_ms = input_with_comma("근내지방 (MS)", 591204, key="ec_ms")
        econ_ema = input_with_comma("등심단면적 (EMA)", 9163, key="ec_ema")
        econ_bft = input_with_comma("등지방 (BFT)", -57237, key="ec_bft")

# ---------------------------
# Inputs Function (Tab A, B)
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
            "annual_culls": culls,
            "female_calf_sell": fsell, "female_fatten_in": ffat_in, "female_fatten_out": ffat_out,
            "female_loss": floss, "loss_months": loss_months,
            "kpn_male": kpn, "male_calf_sell": msell, "male_fatten_in": mfat_in, "male_fatten_out": mfat_out,
            "male_loss": mloss, "repl_rate": repl_rate
        }

def run_base_calc(name, inputs):
    return compute_scenario(
        name,
        base_cows, conception_rate, female_birth_ratio, heifer_nonprofit_months, calf_common_months, kpn_exit_months,
        inputs["annual_culls"], inputs["female_calf_sell"], inputs["female_fatten_in"], inputs["female_fatten_out"], inputs["female_loss"], inputs["loss_months"],
        inputs["male_calf_sell"], inputs["male_fatten_in"], inputs["male_fatten_out"], inputs["male_loss"], inputs["kpn_male"],
        cow_cost_y, cost_rearing_y, cost_fatten_early_y, cost_fatten_late_y,
        p_calf_f, p_calf_m, p_fat_f, p_fat_m, p_cull,
        ship_m_f, ship_m_m,
        ext_buy_n, ext_buy_p, ext_sell_n, ext_sell_p, ext_cost_y, ext_period
    )

# ---------------------------
# Excel View Generator
# ---------------------------
def make_excel_view(res):
    data = []
    # Revenue
    data.append({"구분": "수익", "항목": "도태우 판매", "산출 근거 (Basis)": f"{res['n_cull']}두 * {fmt_money(res['p_cull'])}", "금액 (Amount)": res["v_cull"]})
    data.append({"구분": "수익", "항목": "암송아지 판매", "산출 근거 (Basis)": f"{res['n_calf_f']}두 * {fmt_money(res['p_calf_f'])}", "금액 (Amount)": res["v_calf_f"]})
    data.append({"구분": "수익", "항목": "수송아지 판매", "산출 근거 (Basis)": f"{res['n_calf_m']}두 * {fmt_money(res['p_calf_m'])}", "금액 (Amount)": res["v_calf_m"]})
    data.append({"구분": "수익", "항목": "암비육우 출하", "산출 근거 (Basis)": f"{res['n_fat_out_f']}두 * {fmt_money(res['p_fat_f'])}", "금액 (Amount)": res["v_fat_out_f"]})
    data.append({"구분": "수익", "항목": "수비육우 출하", "산출 근거 (Basis)": f"{res['n_fat_out_m']}두 * {fmt_money(res['p_fat_m'])}", "금액 (Amount)": res["v_fat_out_m"]})
    
    # Cost
    data.append({"구분": "비용", "항목": "기초 번식우 유지", "산출 근거 (Basis)": f"{res['n_base']}두 * {fmt_money(res['cost_y_cow'])}", "금액 (Amount)": -res["c_breed_main"]})
    data.append({"구분": "비용", "항목": "대체우 육성", "산출 근거 (Basis)": f"{res['n_repl']}두 * ({res['months_heifer']}개월/12) * {fmt_money(res['cost_y_cow'])}", "금액 (Amount)": -res["c_breed_repl"]})
    data.append({"구분": "비용", "항목": "KPN 위탁", "산출 근거 (Basis)": f"{res['n_kpn']}두 * ({fmt_money(res['cost_y_cow'])}/{res['rate_concept']}) * ({res['months_kpn']}개월/12)", "금액 (Amount)": -res["c_kpn"]})
    data.append({"구분": "비용", "항목": "자가 암비육", "산출 근거 (Basis)": f"{res['n_fat_in_f']}두 * {res['period_f']:.1f}년 * 평균 {fmt_money(res['cost_avg_fatten'])}", "금액 (Amount)": -res["c_fat_in_f"]})
    data.append({"구분": "비용", "항목": "자가 수비육", "산출 근거 (Basis)": f"{res['n_fat_in_m']}두 * {res['period_m']:.1f}년 * 평균 {fmt_money(res['cost_avg_fatten'])}", "금액 (Amount)": -res["c_fat_in_m"]})
    
    # Mortality
    data.append({"구분": "비용(손실)", "항목": "암송아지 폐사", "산출 근거 (Basis)": f"{res['n_loss_f']}두 * ({fmt_money(res['cost_y_cow'])}/{res['rate_concept']}) * ({res['loss_months']}/12)", "금액 (Amount)": -res["val_loss_f"]})
    data.append({"구분": "비용(손실)", "항목": "수송아지 폐사", "산출 근거 (Basis)": f"{res['n_loss_m']}두 * ({fmt_money(res['cost_y_cow'])}/{res['rate_concept']}) * ({res['loss_months']}/12)", "금액 (Amount)": -res["val_loss_m"]})

    # External
    data.append({"구분": "외부", "항목": "비육우 매출", "산출 근거 (Basis)": f"{res['n_ext_sell']}두 * {fmt_money(res['p_ext_sell'])}", "금액 (Amount)": res["v_ext_rev"]})
    data.append({"구분": "외부", "항목": "송아지 매입", "산출 근거 (Basis)": f"{res['n_ext_buy']}두 * {fmt_money(res['p_ext_buy'])}", "금액 (Amount)": -res["c_ext_buy"]})
    data.append({"구분": "외부", "항목": "사육 유지비", "산출 근거 (Basis)": f"{res['n_ext_sell']}두 * {res['period_ext']}년 * {fmt_money(res['cost_y_ext'])}", "금액 (Amount)": -res["c_ext_maint"]})
    
    data.append({"구분": "결과", "항목": "순이익 (Net Profit)", "산출 근거 (Basis)": "수익 - 비용", "금액 (Amount)": res["Net Final"]})
    return pd.DataFrame(data)

# ---------------------------
# Chart Generators
# ---------------------------
def create_net_profit_chart(res_a, res_b):
    years = list(range(1, 11))
    chart_data = []
    
    # 순이익만 추출
    for y in years:
        chart_data.append({"Scenario": "시나리오 A", "Year": y, "Value": res_a['Net Final']})
        chart_data.append({"Scenario": "시나리오 B", "Year": y, "Value": res_b['Net Final']})
    
    df_chart = pd.DataFrame(chart_data)
    
    # 색상 지정: A=파랑, B=빨강
    color_scale = alt.Scale(domain=["시나리오 A", "시나리오 B"], range=["#1f77b4", "#d62728"])

    return alt.Chart(df_chart).mark_line(point=True).encode(
        x=alt.X("Year:O", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("Value:Q", axis=alt.Axis(format=",.0f")),
        color=alt.Color("Scenario:N", scale=color_scale, title="시나리오"),
        tooltip=["Scenario", "Year", alt.Tooltip("Value", format=",.0f")]
    ).properties(width='container', height=300, title="순이익 비교 (10년 추이)")

def create_pie_chart(res_data):
    df_cost = pd.DataFrame(res_data['Cost Breakdown'])
    
    # 텍스트 오버레이 제거 -> 범례(Legend)와 툴팁만 사용
    base = alt.Chart(df_cost).encode(
        theta=alt.Theta("Value", stack=True)
    )
    pie = base.mark_arc(outerRadius=100).encode(
        color=alt.Color("Category", title="비용 항목"),
        tooltip=["Category", alt.Tooltip("Value", format=",.0f")]
    )
    # 글씨 잘림 방지를 위해 mark_text 제거함
    return pie.properties(width='container', height=300, title=f"{res_data['Scenario']} 비용 구조")

# ---------------------------
# Tabs Layout
# ---------------------------
tab_a, tab_b, tab_analysis = st.tabs(["교체율 설정 A", "교체율 설정 B", "분석: 교체율 vs 개량효과"])

# --- Tab A & B ---
inputs_a = get_alloc_inputs(tab_a, "A")
inputs_b = get_alloc_inputs(tab_b, "B")

sc_name_a = f"교체율 {inputs_a['repl_rate']:.1f}%"
sc_name_b = f"교체율 {inputs_b['repl_rate']:.1f}%"

res_a = run_base_calc(sc_name_a, inputs_a)
res_b = run_base_calc(sc_name_b, inputs_b)

# --- Tab A Content ---
with tab_a:
    st.divider()
    st.metric("순이익 (Net Profit)", f"{fmt_money(res_a['Net Final'])}원")
    
    c1, c2 = st.columns([1.5, 1])
    with c1:
        # [변경] 순이익만 보여주는 그래프
        st.altair_chart(create_net_profit_chart(res_a, res_b), use_container_width=True)
    with c2:
        # [변경] 글씨 잘림 없는 파이 차트
        st.altair_chart(create_pie_chart(res_a), use_container_width=True)

    st.markdown("---")
    st.subheader("📋 상세 계산 내역")
    df_detail_a = make_excel_view(res_a)
    st.dataframe(df_detail_a.style.format({"금액 (Amount)": "{:,.0f}"}), use_container_width=True, height=500)

# --- Tab B Content ---
with tab_b:
    st.divider()
    st.metric("순이익 (Net Profit)", f"{fmt_money(res_b['Net Final'])}원")
    
    c1, c2 = st.columns([1.5, 1])
    with c1:
        # [변경] 순이익만 보여주는 그래프
        st.altair_chart(create_net_profit_chart(res_a, res_b), use_container_width=True)
    with c2:
        # [변경] 글씨 잘림 없는 파이 차트
        st.altair_chart(create_pie_chart(res_b), use_container_width=True)

    st.markdown("---")
    st.subheader("📋 상세 계산 내역")
    df_detail_b = make_excel_view(res_b)
    st.dataframe(df_detail_b.style.format({"금액 (Amount)": "{:,.0f}"}), use_container_width=True, height=500)


# --- Tab Analysis ---
with tab_analysis:
    st.header("분석: 교체율 증가 vs 개량 이득 (Analysis)")
    st.markdown("**시나리오 B(목표) - 시나리오 A(기준)**의 교체율 차이를 자동으로 분석합니다.")
    
    col_setup, col_result = st.columns([1, 1.2])
    
    with col_setup:
        st.subheader("1. 교체율 차이 (자동 계산)")
        
        cull_a = res_a['n_cull']
        cull_b = res_b['n_cull']
        
        extra_repl = cull_b - cull_a
        rate_diff = inputs_b['repl_rate'] - inputs_a['repl_rate']
        
        st.metric("기준 도태 (A)", f"{cull_a}두", f"{inputs_a['repl_rate']:.1f}%")
        st.metric("목표 도태 (B)", f"{cull_b}두", f"{inputs_b['repl_rate']:.1f}%")
        st.divider()
        st.metric("추가 교체 두수 (B-A)", f"{extra_repl}두", f"교체율 {rate_diff:+.1f}%p")
        
        if extra_repl <= 0:
            st.warning("⚠️ 시나리오 B의 교체율이 A보다 높아야 교체율 증가 비용이 계산됩니다.")
        
        st.markdown("---")
        st.markdown("**예상 개량 형질 입력 (증분 Δ)**")
        g1, g2 = st.columns(2)
        d_cw = g1.number_input("도체중 (CW) 증분 (kg)", value=5.0)
        d_ms = g2.number_input("근내지방 (MS) 증분", value=2.0)
        d_ema = g1.number_input("등심단면적 (EMA) 증분", value=1.0)
        d_bft = g2.number_input("등지방 (BFT) 증분", value=-0.5)

    with col_result:
        st.subheader("2. 경제성 분석 결과 (Graph)")
        
        # A. Added Cost
        repl_unit_cost = (heifer_nonprofit_months / 12.0) * cow_cost_y
        added_cost = extra_repl * repl_unit_cost
        
        # B. Added Revenue
        premium_per_head = (d_cw * econ_cw) + (d_ms * econ_ms) + (d_ema * econ_ema) + (d_bft * econ_bft)
        
        # Total Sold Heads
        total_sold = (res_b['n_fat_out_f'] + res_b['n_fat_out_m'] + 
                      res_b['n_ext_sell'] + 
                      res_b['n_calf_f'] + res_b['n_calf_m'])
                      
        added_revenue = total_sold * premium_per_head
        
        # C. Net Profit
        net_profit = added_revenue - added_cost
        
        # Analysis Chart (Line Chart with Points)
        chart_df = pd.DataFrame([
            {"Type": "1. 유전적 수익", "Amount": added_revenue, "Category": "수익"},
            {"Type": "2. 추가 비용", "Amount": -added_cost, "Category": "비용"},
            {"Type": "3. 분석 순이익", "Amount": net_profit, "Category": "순이익"}
        ])
        
        # 색상 지정
        analysis_color = alt.Scale(
            domain=['수익', '비용', '순이익'],
            range=['#1f77b4', '#d62728', '#2ca02c']
        )
        
        # 회색 연결선
        line = alt.Chart(chart_df).mark_line(color='gray').encode(
            x=alt.X("Type", sort=None, title="구분"),
            y=alt.Y("Amount", title="금액")
        )
        
        # 색상 포인트
        points = alt.Chart(chart_df).mark_circle(size=150).encode(
            x=alt.X("Type", sort=None),
            y="Amount",
            color=alt.Color("Category", scale=analysis_color, title="항목"),
            tooltip=[alt.Tooltip("Type"), alt.Tooltip("Amount", format=",.0f")]
        )
        
        c = (line + points).properties(height=250, title="경제성 분석 결과 (상세)")
        st.altair_chart(c, use_container_width=True)

    # D. Detailed Table
    st.markdown("---")
    st.subheader("📋 상세 계산 내역")
    
    analysis_data = []
    analysis_data.append({
        "구분": "수익(이득)", "항목": "두당 예상 프리미엄",
        "산출 근거 (Basis)": f"({d_cw}*{econ_cw:,.0f}) + ({d_ms}*{econ_ms:,.0f}) + ...",
        "금액 (Amount)": premium_per_head
    })
    analysis_data.append({
        "구분": "수익(이득)", "항목": "총 유전적 추가 수익",
        "산출 근거 (Basis)": f"판매두수(B) {total_sold} * {fmt_money(premium_per_head)}",
        "금액 (Amount)": added_revenue
    })
    analysis_data.append({
        "구분": "비용(손실)", "항목": "추가 대체우 육성비",
        "산출 근거 (Basis)": f"추가 {extra_repl}두 * 육성비 {fmt_money(repl_unit_cost)}",
        "금액 (Amount)": -added_cost
    })
    analysis_data.append({
        "구분": "결과", "항목": "분석 순이익 (Net Profit)",
        "산출 근거 (Basis)": "유전적 수익 - 추가 비용",
        "금액 (Amount)": net_profit
    })
    
    df_analysis = pd.DataFrame(analysis_data)
    st.dataframe(df_analysis.style.format({"금액 (Amount)": "{:,.0f}"}), use_container_width=True, hide_index=True)
    
