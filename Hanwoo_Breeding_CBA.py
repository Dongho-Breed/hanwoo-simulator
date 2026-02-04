import streamlit as st
import pandas as pd
import altair as alt
import math

st.set_page_config(page_title="Hanwoo Integrated CBA (V2.3)", layout="wide")

# ---------------------------
# 1. Helpers & Callbacks
# ---------------------------
def clamp_int(x, lo=0):
    try:
        return max(lo, int(x))
    except Exception:
        return lo

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

def input_with_comma(label, value, step=None, key=None):
    if key and key not in st.session_state:
        st.session_state[key] = f"{int(value):,}"
    
    st.text_input(
        label,
        key=key,
        on_change=format_callback,
        args=(key,)
    )
    
    try:
        current_val = st.session_state[key]
        return float(str(current_val).replace(",", ""))
    except (ValueError, TypeError):
        return float(value)

def stage_cost_per_head(calf_common_months, ship_months, cost_rearing_y, cost_fatten_early_y, cost_fatten_late_y):
    calf_common_months = clamp_int(calf_common_months, 0)
    ship_months = clamp_int(ship_months, 0)
    months_rearing = max(0, 12 - calf_common_months)
    months_early = 0 if ship_months < 13 else min(6, max(0, ship_months - 12))
    months_late = max(0, ship_months - 18)
    
    cost = (cost_rearing_y * (months_rearing / 12.0) + 
            cost_fatten_early_y * (months_early / 12.0) + 
            cost_fatten_late_y * (months_late / 12.0))
    return {"cost_per_head": cost}

# ---------------------------
# 2. Core Logic
# ---------------------------
def compute_scenario(
    name, 
    base_cows, conception_rate, female_birth_ratio, 
    heifer_nonprofit_months, calf_common_months, kpn_exit_months,
    # Allocations
    annual_culls, female_calf_sell, female_fatten_in, female_fatten_out, female_loss,
    male_calf_sell, male_fatten_in, male_fatten_out, male_loss, kpn_male,
    # Costs & Prices
    cow_cost_y, cost_rearing_y, cost_fatten_early_y, cost_fatten_late_y,
    price_calf_female, price_calf_male, price_fatten_female, price_fatten_male, price_cull_cow,
    ship_m_female, ship_m_male,
    ext_buy_n, ext_buy_p, ext_sell_n, ext_sell_p, ext_cost_y, ext_period_y
):
    base_cows = clamp_int(base_cows, 1)
    annual_culls = clamp_int(annual_culls, 0)
    replacements_female = annual_culls
    
    # 1. 출생
    births_total = base_cows * float(conception_rate)
    births_female = births_total * float(female_birth_ratio)
    births_male = births_total * (1.0 - float(female_birth_ratio))
    
    # 2. 번식 농장 수익
    val_cull = annual_culls * price_cull_cow
    val_calf_f = clamp_int(female_calf_sell) * price_calf_female
    val_calf_m = clamp_int(male_calf_sell) * price_calf_male
    val_fat_out_f = clamp_int(female_fatten_out) * price_fatten_female
    val_fat_out_m = clamp_int(male_fatten_out) * price_fatten_male
    rev_internal = val_cull + val_calf_f + val_calf_m + val_fat_out_f + val_fat_out_m
    
    # 3. 번식 농장 비용
    cost_breeding_main = base_cows * cow_cost_y
    heifer_years = clamp_int(heifer_nonprofit_months, 0) / 12.0
    cost_breeding_repl = (annual_culls * heifer_years) * cow_cost_y
    calf_prod_cost = cow_cost_y / conception_rate if conception_rate > 0 else 0
    val_kpn_loss = clamp_int(kpn_male) * calf_prod_cost * (clamp_int(kpn_exit_months, 0) / 12.0)
    
    cost_per_f = stage_cost_per_head(calf_common_months, ship_m_female, cost_rearing_y, cost_fatten_early_y, cost_fatten_late_y)["cost_per_head"]
    cost_per_m = stage_cost_per_head(calf_common_months, ship_m_male, cost_rearing_y, cost_fatten_early_y, cost_fatten_late_y)["cost_per_head"]
    val_fat_cost_f = clamp_int(female_fatten_in) * cost_per_f
    val_fat_cost_m = clamp_int(male_fatten_in) * cost_per_m
    
    cost_internal = cost_breeding_main + cost_breeding_repl + val_kpn_loss + val_fat_cost_f + val_fat_cost_m
    net_internal = rev_internal - cost_internal

    # 4. 외부 비육 농장
    val_ext_rev = ext_sell_n * ext_sell_p
    val_ext_buy = ext_buy_n * ext_buy_p
    val_ext_maint = (ext_sell_n * ext_period_y) * ext_cost_y
    net_external = val_ext_rev - val_ext_buy - val_ext_maint

    # 5. 최종 합산
    net_final = net_internal + net_external
    rev_final = rev_internal + val_ext_rev
    cost_final = cost_internal + val_ext_buy + val_ext_maint
    
    # 6. 경고 메시지 (출하 > 투입일 때만 에러)
    issues = []
    if female_fatten_out > female_fatten_in:
        issues.append(f"[암] 출하({female_fatten_out}) > 투입({female_fatten_in}) : 투입보다 많이 팔 수 없습니다.")
    if male_fatten_out > male_fatten_in:
        issues.append(f"[수] 출하({male_fatten_out}) > 투입({male_fatten_in}) : 투입보다 많이 팔 수 없습니다.")

    return {
        "Scenario": name,
        "Net Final": net_final, "Rev Final": rev_final, "Cost Final": cost_final,
        # 상세 데이터
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
        "v_ext_rev": val_ext_rev, "n_ext_sell": ext_sell_n,
        "c_ext_buy": val_ext_buy, "n_ext_buy": ext_buy_n,
        "c_ext_maint": val_ext_maint, "n_ext_stock": ext_sell_n * ext_period_y,
        "n_loss_f": female_loss, "n_loss_m": male_loss,
        # 단가
        "p_cull": price_cull_cow, "p_calf_f": price_calf_female, "p_calf_m": price_calf_male,
        "p_fat_f": price_fatten_female, "p_fat_m": price_fatten_male,
        "cost_y_cow": cow_cost_y, "cost_head_fat_f": cost_per_f, "cost_head_fat_m": cost_per_m,
        "p_ext_sell": ext_sell_p, "p_ext_buy": ext_buy_p, "cost_y_ext": ext_cost_y
    }, issues

# ---------------------------
# 3. UI & Inputs
# ---------------------------
st.title("Hanwoo Integrated CBA (V2.3)")
st.caption("투입 대비 출하량 검증 수정 (적게 출하하는 건 OK, 많이 출하하는 건 에러)")

with st.sidebar:
    st.header("1. Core Assumptions")
    with st.expander("A. 기초/생물학", expanded=True):
        base_cows = st.number_input("기초 번식우(두)", 100, step=10, format="%d")
        conception_rate = st.number_input("수태율 (권장: 0~1)", value=0.75, step=0.01)
        female_birth_ratio = st.number_input("암 성비 (권장: 0~1)", value=0.50, step=0.01)
        heifer_nonprofit_months = st.number_input("대체우 무수익(월)", 19)
        calf_common_months = st.number_input("송아지 공통육성(월)", 7)
        kpn_exit_months = st.number_input("KPN 종료월령", 7)
        
    with st.expander("B. 비용 (원/년/두)", expanded=False):
        cow_cost_y = input_with_comma("번식우 유지비", 3200000, key="cow_cost")
        cost_rearing_y = input_with_comma("육성기 비용", 2400000, key="rearing_cost")
        cost_fatten_early_y = input_with_comma("비육전기 비용", 3000000, key="early_cost")
        cost_fatten_late_y = input_with_comma("비육후기 비용", 3600000, key="late_cost")
        
    with st.expander("C. 가격 (원/두)", expanded=False):
        p_calf_f = input_with_comma("암송아지", 1300000, key="p_calf_f")
        p_calf_m = input_with_comma("수송아지", 2500000, key="p_calf_m")
        p_fat_f = input_with_comma("암비육우", 7500000, key="p_fat_f")
        p_fat_m = input_with_comma("수비육우", 9000000, key="p_fat_m")
        p_cull = input_with_comma("도태우", 2500000, key="p_cull")
        
    with st.expander("D. 출하월령", expanded=False):
        ship_m_f = st.number_input("암 출하월령", 30)
        ship_m_m = st.number_input("수 출하월령", 30)
        
    st.header("2. External Farm")
    with st.expander("외부 비육 설정", expanded=True):
        ext_buy_n = st.number_input("Ext 매입(두)", value=50, step=1)
        ext_buy_p = input_with_comma("Ext 매입가", 2500000, key="ebp")
        
        # [자유 입력]
        ext_sell_n = st.number_input("Ext 출하(두)", value=50, step=1)
        
        ext_sell_p = input_with_comma("Ext 출하가", 9000000, key="esp")
        ext_cost_y = input_with_comma("Ext 유지비", 3500000, key="ecy")
        ext_period = st.number_input("Ext 기간(년)", 2.5)

# Scenarios Inputs
t1, t2 = st.tabs(["A 설정", "B 설정"])
birth_total = base_cows * conception_rate
birth_female = birth_total * female_birth_ratio
birth_male = birth_total * (1 - female_birth_ratio)

def get_inputs(tab, key):
    with tab:
        st.info(f"💡 **생산 가이드 (참고용)** | 암송아지: **{birth_female:.1f}두** | 수송아지: **{birth_male:.1f}두**")
        c1, c2, c3 = st.columns(3)
        
        # 1. 도태
        culls = c1.number_input(f"[{key}] 연간 도태(두)", 15, key=f"c_{key}")
        
        # 2. 암송아지 분배
        c2.markdown(f"**[{key}] 암송아지 분배**")
        c2.text_input(f"대체우 선발(두) [고정]", value=f"{culls} (자동)", disabled=True, key=f"repl_disp_{key}")
        fsell = c2.number_input(f"판매(두)", 0, key=f"fs_{key}")
        
        # 자가비육 투입 (In)
        ffat_in = c2.number_input(f"자가비육 투입(In)", value=10, key=f"fi_{key}")
        
        # 자가비육 출하 (Out) - 입력 제한 없음, 논리 체크만 함
        ffat_out = c2.number_input(f"자가비육 출하(Out)", value=10, key=f"fo_{key}")
        
        # [핵심 수정] 출하 > 투입 (10마리 넣고 11마리 출하) -> 에러 O
        #             출하 <= 투입 (10마리 넣고 9마리 출하) -> 에러 X (정상)
        if ffat_out > ffat_in:
             c2.error(f"🚨 오류: 투입({ffat_in})보다 많은 두수({ffat_out})를 출하할 수 없습니다.")

        floss = c2.number_input(f"폐사/병사(두)", 0, key=f"fl_{key}")

        # 합계 검증 (Out 제외)
        female_sum = culls + fsell + ffat_in + floss
        c2.caption(f"총 소모: {female_sum}두 (생산가이드: {birth_female:.1f}두)")
        if female_sum > birth_female:
            c2.error(f"🚨 생산량 초과!")

        # 3. 수송아지 분배
        c3.markdown(f"**[{key}] 수송아지 분배**")
        kpn = c3.number_input(f"KPN 위탁(두)", 10, key=f"k_{key}")
        msell = c3.number_input(f"판매(두)", 0, key=f"ms_{key}")
        
        # 자가비육 투입 (In)
        mfat_in = c3.number_input(f"자가비육 투입(In)", value=25, key=f"mi_{key}")
        
        # 자가비육 출하 (Out)
        mfat_out = c3.number_input(f"자가비육 출하(Out)", value=25, key=f"mo_{key}")
        
        # [핵심 수정] 수송아지도 동일 적용
        if mfat_out > mfat_in:
             c3.error(f"🚨 오류: 투입({mfat_in})보다 많은 두수({mfat_out})를 출하할 수 없습니다.")

        mloss = c3.number_input(f"폐사/병사(두)", 0, key=f"ml_{key}")
        
        # 합계 검증 (Out 제외)
        male_sum = kpn + msell + mfat_in + mloss
        c3.caption(f"총 소모: {male_sum}두 (생산가이드: {birth_male:.1f}두)")
        if male_sum > birth_male:
            c3.error(f"🚨 생산량 초과!")
        
        return {
            "annual_culls": culls,
            "female_calf_sell": fsell,
            "female_fatten_in": ffat_in,
            "female_fatten_out": ffat_out,
            "female_loss": floss,
            "kpn_male": kpn,
            "male_calf_sell": msell,
            "male_fatten_in": mfat_in,
            "male_fatten_out": mfat_out,
            "male_loss": mloss
        }

av = get_inputs(t1, "A")
bv = get_inputs(t2, "B")

# Calculation Execution
def run_computation(name, alloc_dict):
    return compute_scenario(
        name=name,
        # Core
        base_cows=base_cows, conception_rate=conception_rate, female_birth_ratio=female_birth_ratio,
        heifer_nonprofit_months=heifer_nonprofit_months, calf_common_months=calf_common_months, kpn_exit_months=kpn_exit_months,
        # Allocations
        annual_culls=alloc_dict["annual_culls"],
        female_calf_sell=alloc_dict["female_calf_sell"],
        female_fatten_in=alloc_dict["female_fatten_in"],
        female_fatten_out=alloc_dict["female_fatten_out"],
        female_loss=alloc_dict["female_loss"],
        male_calf_sell=alloc_dict["male_calf_sell"],
        male_fatten_in=alloc_dict["male_fatten_in"],
        male_fatten_out=alloc_dict["male_fatten_out"],
        male_loss=alloc_dict["male_loss"],
        kpn_male=alloc_dict["kpn_male"],
        # Costs
        cow_cost_y=cow_cost_y, cost_rearing_y=cost_rearing_y,
        cost_fatten_early_y=cost_fatten_early_y, cost_fatten_late_y=cost_fatten_late_y,
        # Prices
        price_calf_female=p_calf_f, price_calf_male=p_calf_m,
        price_fatten_female=p_fat_f, price_fatten_male=p_fat_m, price_cull_cow=p_cull,
        # Shipping
        ship_m_female=ship_m_f, ship_m_male=ship_m_m,
        # External
        ext_buy_n=ext_buy_n, ext_buy_p=ext_buy_p,
        ext_sell_n=ext_sell_n, ext_sell_p=ext_sell_p,
        ext_cost_y=ext_cost_y, ext_period_y=ext_period
    )

res_A, iss_A = run_computation("A", av)
res_B, iss_B = run_computation("B", bv)

# ---------------------------
# Layout: Graphs First
# ---------------------------
st.divider()
c1, c2 = st.columns(2)
if iss_A: c1.warning(f"A 알림: {iss_A}") 
else: c1.success("A 정상")
if iss_B: c2.warning(f"B 알림: {iss_B}")
else: c2.success("B 정상")

st.subheader("📊 시나리오 비교 결과 (그래프)")
years = list(range(1, 11))
chart_data = []
for r in [res_A, res_B]:
    for y in years:
        chart_data.append({"Scenario": r['Scenario'], "Year": y, "Type": "Revenue", "Value": r['Rev Final']})
        chart_data.append({"Scenario": r['Scenario'], "Year": y, "Type": "Cost", "Value": r['Cost Final']})
        chart_data.append({"Scenario": r['Scenario'], "Year": y, "Type": "Net Income", "Value": r['Net Final']})

df_chart = pd.DataFrame(chart_data)

def create_chart(data, type_filter, color, title):
    return alt.Chart(data[data['Type'] == type_filter]).mark_line(point=True).encode(
        x=alt.X("Year:O", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("Value:Q", axis=alt.Axis(format=",.0f")),
        color=alt.Color("Scenario:N", scale=alt.Scale(range=color)),
        tooltip=["Scenario", "Year", alt.Tooltip("Value", format=",.0f")]
    ).properties(width=400, height=350, title=title)

c_left, c_center, c_right = st.columns([1, 2, 1])
with c_center:
    st.altair_chart(create_chart(df_chart, "Revenue", ['#1f77b4', '#aec7e8'], "Total Revenue (매출)"))
    st.altair_chart(create_chart(df_chart, "Cost", ['#d62728', '#ff9896'], "Total Cost (비용)"))
    st.altair_chart(create_chart(df_chart, "Net Income", ['#2ca02c', '#98df8a'], "Net Income (순이익)"))

# ---------------------------
# Excel Detail View
# ---------------------------
def make_excel_view(res):
    data = []
    # 1. 번식 농장 수익
    data.append({"Category (구분)": "1. 번식농장 수익", "Item (항목)": "도태우 판매", "Basis (산출 근거)": f"{res['n_cull']}두 x {fmt_money(res['p_cull'])}", "Amount (금액)": res["v_cull"]})
    data.append({"Category (구분)": "1. 번식농장 수익", "Item (항목)": "암송아지 판매", "Basis (산출 근거)": f"{res['n_calf_f']}두 x {fmt_money(res['p_calf_f'])}", "Amount (금액)": res["v_calf_f"]})
    data.append({"Category (구분)": "1. 번식농장 수익", "Item (항목)": "수송아지 판매", "Basis (산출 근거)": f"{res['n_calf_m']}두 x {fmt_money(res['p_calf_m'])}", "Amount (금액)": res["v_calf_m"]})
    data.append({"Category (구분)": "1. 번식농장 수익", "Item (항목)": "암 자가비육 출하", "Basis (산출 근거)": f"{res['n_fat_out_f']}두 x {fmt_money(res['p_fat_f'])}", "Amount (금액)": res["v_fat_out_f"]})
    data.append({"Category (구분)": "1. 번식농장 수익", "Item (항목)": "수 자가비육 출하", "Basis (산출 근거)": f"{res['n_fat_out_m']}두 x {fmt_money(res['p_fat_m'])}", "Amount (금액)": res["v_fat_out_m"]})
    
    # 2. 번식 농장 비용
    data.append({"Category (구분)": "2. 번식농장 비용", "Item (항목)": "기초 번식우 유지", "Basis (산출 근거)": f"{res['n_base']}두 x {fmt_money(res['cost_y_cow'])}", "Amount (금액)": -res["c_breed_main"]})
    data.append({"Category (구분)": "2. 번식농장 비용", "Item (항목)": "대체우 육성비", "Basis (산출 근거)": f"{res['n_repl']}두 x 무수익기간", "Amount (금액)": -res["c_breed_repl"]})
    data.append({"Category (구분)": "2. 번식농장 비용", "Item (항목)": "KPN 위탁 손실", "Basis (산출 근거)": f"{res['n_kpn']}두 x 육성비", "Amount (금액)": -res["c_kpn"]})
    data.append({"Category (구분)": "2. 번식농장 비용", "Item (항목)": "암 자가비육 사육", "Basis (산출 근거)": f"{res['n_fat_in_f']}두 x {fmt_money(res['cost_head_fat_f'])}", "Amount (금액)": -res["c_fat_in_f"]})
    data.append({"Category (구분)": "2. 번식농장 비용", "Item (항목)": "수 자가비육 사육", "Basis (산출 근거)": f"{res['n_fat_in_m']}두 x {fmt_money(res['cost_head_fat_m'])}", "Amount (금액)": -res["c_fat_in_m"]})
    
    # 폐사/병사
    data.append({"Category (구분)": "2.1 손실(폐사)", "Item (항목)": "암송아지 폐사", "Basis (산출 근거)": f"{res['n_loss_f']}두 (매출 없음)", "Amount (금액)": 0})
    data.append({"Category (구분)": "2.1 손실(폐사)", "Item (항목)": "수송아지 폐사", "Basis (산출 근거)": f"{res['n_loss_m']}두 (매출 없음)", "Amount (금액)": 0})

    # 3. 별도 비육 수익/비용
    data.append({"Category (구분)": "3. 외부 비육장", "Item (항목)": "비육우 매출", "Basis (산출 근거)": f"{res['n_ext_sell']}두 x {fmt_money(res['p_ext_sell'])}", "Amount (금액)": res["v_ext_rev"]})
    data.append({"Category (구분)": "3. 외부 비육장", "Item (항목)": "송아지 매입비", "Basis (산출 근거)": f"{res['n_ext_buy']}두 x {fmt_money(res['p_ext_buy'])}", "Amount (금액)": -res["c_ext_buy"]})
    data.append({"Category (구분)": "3. 외부 비육장", "Item (항목)": "사육 유지비", "Basis (산출 근거)": f"재고 {res['n_ext_stock']:.1f}두 x {fmt_money(res['cost_y_ext'])}", "Amount (금액)": -res["c_ext_maint"]})
    
    # 4. 최종 합계
    data.append({"Category (구분)": "4. 최종 결과", "Item (항목)": "순이익 (Net)", "Basis (산출 근거)": "Total Revenue - Total Cost", "Amount (금액)": res["Net Final"]})

    return pd.DataFrame(data)

st.markdown("---")
view_t1, view_t2 = st.tabs(["📋 [상세] 시나리오 A", "📋 [상세] 시나리오 B"])

with view_t1:
    st.subheader("Detailed Breakdown (A)")
    df_a = make_excel_view(res_A)
    st.dataframe(df_a.style.format({"Amount (금액)": "{:,.0f}"}), use_container_width=True, height=600)

with view_t2:
    st.subheader("Detailed Breakdown (B)")
    df_b = make_excel_view(res_B)
    st.dataframe(df_b.style.format({"Amount (금액)": "{:,.0f}"}), use_container_width=True, height=600)
