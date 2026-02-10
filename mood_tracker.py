import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import streamlit as st

# 密码验证：只有输入正确密码才显示内容
def check_password():
    # 从Secrets里获取密码
    correct_password = st.secrets.get("app_password", "")
    if not correct_password:
        st.error("请先在Secrets里设置app_password")
        return False
    
    # 显示密码输入框
    password = st.text_input("请输入访问密码", type="password")
    if password != correct_password:
        st.error("密码错误，无权访问")
        return False
    return True

# 验证不通过就停止运行
if not check_password():
    st.stop()

# ===================== 核心修改1：适配手机端 + 页面配置 =====================
st.set_page_config(
    page_title="每日情绪记录",
    layout="centered",  # 手机端自适应
    initial_sidebar_state="collapsed"  # 隐藏侧边栏，更适配手机
)
st.title("📝 每日情绪变量记录")

# ===================== 核心修改2：Google Sheets 数据持久化（替代本地CSV） =====================
# 【重要】下方需要你替换为自己的 Google Sheets 配置（步骤3会教你怎么获取）
# 先创建一个空字典，后续配置
gs_credentials = st.secrets.get("google_sheets", {})
if gs_credentials:
    # 授权访问 Google Sheets
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(gs_credentials, scope)
    client = gspread.authorize(creds)
    # 打开你的 Google Sheet（替换为你自己的表格名称）
    sheet = client.open("情绪记录").sheet1
    
    # 读取数据到DataFrame
    try:
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        # 确保日期列是datetime类型
        if not df.empty:
            df["日期"] = pd.to_datetime(df["日期"]).dt.date
    except:
        # 首次使用，初始化表格结构
        df = pd.DataFrame(columns=[
            "日期", "起床入睡时间", "中午饮食重口度", "晚上饮食重口度",
            "有无运动", "有无冥想", "额外学习任务强度", "家人有无变故",
            "女友情绪稳定度", "情绪自评", "加权情绪分"
        ])
else:
    # 备用方案：本地CSV（部署时会丢失，仅本地测试用）
    csv_file = "mood_records.csv"
    try:
        df = pd.read_csv(csv_file)
        df["日期"] = pd.to_datetime(df["日期"]).dt.date
    except FileNotFoundError:
        df = pd.DataFrame(columns=[
            "日期", "起床入睡时间", "中午饮食重口度", "晚上饮食重口度",
            "有无运动", "有无冥想", "额外学习任务强度", "家人有无变故",
            "女友情绪稳定度", "情绪自评", "加权情绪分"
        ])

# ===================== 记录表单（适配手机操作） =====================
with st.form("record_form", clear_on_submit=True):  # 提交后清空表单，方便下次记录
    st.subheader("今日数据记录")
    # 日期选择：默认今日，手机端点击友好
    date = st.date_input("📅 记录日期", value=datetime.today(), format="YYYY-MM-DD")
    # 文本输入：起床入睡时间
    sleep_time = st.text_input("⏰ 起床/入睡时间", placeholder="例：7:00 起床 / 23:30 入睡")
    # 滑块：1-5分，手机端滑动操作方便
    lunch_spicy = st.slider("🍚 中午饮食重口度（1=清淡 → 5=极重口）", 1, 5, 3)
    dinner_spicy = st.slider("🍲 晚上饮食重口度（1=清淡 → 5=极重口）", 1, 5, 3)
    # 单选框：0/1，手机端点击清晰
    exercise = st.radio("🏃 有无运动", [0, 1], format_func=lambda x: "✅ 有" if x==1 else "❌ 无", horizontal=True)
    meditation = st.radio("🧘 有无冥想", [0, 1], format_func=lambda x: "✅ 有" if x==1 else "❌ 无", horizontal=True)
    study_task = st.slider("📚 额外学习任务强度（1=无 → 5=极多）", 1, 5, 1)
    family_change = st.radio("👨‍👩‍👧 家人有无变故", [0, 1], format_func=lambda x: "⚠️ 有" if x==1 else "✅ 无", horizontal=True)
    gf_mood = st.slider("❤️ 女友情绪稳定度（1=极不稳定 → 5=完全稳定）", 1, 5, 3)
    mood_self = st.slider("😊 当日情绪自评（1=极差 → 10=极好）", 1, 10, 5)

    # 加权情绪分计算（可自定义权重，强迫症友好）
    weight_dict = {
        "饮食": 0.1, "运动": 0.2, "冥想": 0.2,
        "学习任务": 0.1, "家人变故": 0.15, "女友情绪": 0.25
    }
    diet_avg = (lunch_spicy + dinner_spicy) / 2
    # 家人变故：0=无（正向，转5分），1=有（负向，转0分）
    family_score = (1 - family_change) * 5
    weighted_score = (
        diet_avg * weight_dict["饮食"]
        + exercise * weight_dict["运动"] * 5  # 运动0/1转0-5分
        + meditation * weight_dict["冥想"] * 5
        + study_task * weight_dict["学习任务"]
        + family_score * weight_dict["家人变故"]
        + gf_mood * weight_dict["女友情绪"]
    )
    weighted_score = round(weighted_score, 2)  # 保留2位小数，符合强迫症

    # 提交按钮（手机端点击醒目）
    submit_btn = st.form_submit_button("💾 保存记录", type="primary")
    if submit_btn:
        # 构造新记录行
        new_row = {
            "日期": str(date),  # 转字符串方便存入Google Sheets
            "起床入睡时间": sleep_time,
            "中午饮食重口度": lunch_spicy,
            "晚上饮食重口度": dinner_spicy,
            "有无运动": exercise,
            "有无冥想": meditation,
            "额外学习任务强度": study_task,
            "家人有无变故": family_change,
            "女友情绪稳定度": gf_mood,
            "情绪自评": mood_self,
            "加权情绪分": weighted_score
        }
        # 追加到DataFrame
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        
        # 保存到Google Sheets（核心：数据不丢失）
        if gs_credentials:
            # 清空表格后重新写入（简单高效，适合少量数据）
            sheet.clear()
            sheet.update([df.columns.values.tolist()] + df.values.tolist())
        else:
            # 本地CSV备用
            df.to_csv(csv_file, index=False)
        
        st.success(f"✅ 记录保存成功！\n当日加权情绪分：{weighted_score}")

# ===================== 历史记录 + 趋势图（手机端适配） =====================
st.divider()
st.subheader("📜 历史记录")
# 1. 给每条记录加“行号”（对应Google Sheets的实际行：表头是第1行，记录从第2行开始）
df["行号"] = range(2, len(df) + 2)
# 2. 显示记录（隐藏“行号”列，只给用户看内容）
show_df = df.drop("行号", axis=1)
st.dataframe(show_df, use_container_width=True, height=300)

# 3. 添加“删除记录”功能（修复无记录时的错误）
if len(df) > 0:  # 只有有记录时才显示删除区域
    st.subheader("🗑️ 删除记录")
    delete_row = st.number_input(
        "输入要删除的记录对应的行号",
        min_value=2,  # 最小是第2行（第一条记录）
        max_value=len(df) + 1,  # 最大是最后一条记录的行号
        step=1
    )
    if st.button("确认删除这条记录"):
        sheet.delete_rows(delete_row)  # 直接删除Google Sheets里对应的行
        st.success(f"✅ 已成功删除第{delete_row}行的记录！")
        st.rerun()  # 自动刷新页面，显示最新数据
else:
    st.info("暂无历史记录，无法删除")
# 数据框适配手机：宽度100%，可滚动
st.dataframe(df, use_container_width=True, height=300)

# 趋势图：仅当有2条以上记录时显示
if len(df) > 1:
    st.divider()
    st.subheader("📈 情绪趋势")
    # 转换日期为datetime，方便绘图
    df_plot = df.copy()
    df_plot["日期"] = pd.to_datetime(df_plot["日期"])
    # 绘制折线图，手机端自适应

    st.line_chart(df_plot, x="日期", y=["情绪自评", "加权情绪分"], color=["#1f77b4", "#ff7f0e"])


