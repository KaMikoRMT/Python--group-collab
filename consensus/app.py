import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

"""小組專案主題共識建立系統 MVP with room code.

Run with:
    python3 -m streamlit run app.py
"""

import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from database import (
    add_project_idea,
    add_room_member,
    create_room,
    get_evaluation_results,
    get_evaluators,
    get_idea_submitters,
    get_project_ideas,
    get_room_host,
    get_room_members,
    get_room_phase,
    has_user_evaluated,
    init_db,
    room_exists,
    save_evaluations,
    update_room_phase,
)
from utils import (
    EVALUATION_ASPECTS,
    TOTAL_POINTS,
    aspect_chart_rows,
    build_result_rows,
    generate_room_code,
    is_blank,
    split_multiple_lines,
)


def setup_page():
    """Set page config and simple CSS style."""
    st.set_page_config(
        page_title="小組專案主題共識建立系統",
        page_icon="🌱",
        layout="wide",
    )

    st.markdown(
        """
        <style>
        .main {
            background-color: #fffaf3;
        }
        .stButton > button {
            border-radius: 10px;
            font-weight: 600;
        }
        [data-testid="stMetricValue"] {
            color: #f28c28;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_session_state():
    """Prepare Streamlit session state for room usage.

    st.session_state keeps values for one browser session. After a user creates
    or joins a room, room_code and nickname stay available when Streamlit reruns
    the script every 5 seconds.
    """
    if "room_code" not in st.session_state:
        st.session_state.room_code = ""
    if "nickname" not in st.session_state:
        st.session_state.nickname = ""
    if "is_host" not in st.session_state:
        st.session_state.is_host = False


def auto_refresh_page():
    """Refresh the page every 5 seconds to read fresh SQLite data."""
    if st.session_state.room_code:
        st_autorefresh(interval=5000, key="room_auto_refresh")


def render_home_page():
    """Show create-room and join-room forms before entering the system."""
    st.title("🌱 小組專案主題共識建立系統")
    st.caption("建立或加入房間後，每組資料會用 room code 分開保存。")

    create_col, join_col = st.columns(2)

    with create_col:
        with st.container(border=True):
            st.subheader("建立房間")
            host_nickname = st.text_input("你的 nickname", key="host_nickname")

            if st.button("建立新房間", type="primary", use_container_width=True):
                handle_create_room(host_nickname)

    with join_col:
        with st.container(border=True):
            st.subheader("加入房間")
            room_code = st.text_input("Room code", key="join_room_code")
            nickname = st.text_input("你的 nickname", key="join_nickname")

            if st.button("加入房間", use_container_width=True):
                handle_join_room(room_code, nickname)


def handle_create_room(host_nickname):
    """Create a new room and save room info in session_state."""
    if is_blank(host_nickname):
        st.error("請先輸入 nickname。")
        return

    room_code = generate_unique_room_code()
    create_room(room_code, host_nickname)

    st.session_state.room_code = room_code
    st.session_state.nickname = host_nickname.strip()
    st.session_state.is_host = True

    st.success(f"你的 room code 是：{room_code}")
    st.rerun()


def generate_unique_room_code():
    """Generate a room code that does not exist yet."""
    room_code = generate_room_code(5)
    while room_exists(room_code):
        room_code = generate_room_code(5)
    return room_code


def handle_join_room(room_code, nickname):
    """Validate room code and nickname, then join the room."""
    clean_room_code = room_code.strip().upper()

    if is_blank(clean_room_code):
        st.error("請輸入 room code。")
        return

    if is_blank(nickname):
        st.error("請輸入 nickname。")
        return

    if not room_exists(clean_room_code):
        st.error("找不到這個 room code，請確認後再試一次。")
        return

    add_room_member(clean_room_code, nickname)

    st.session_state.room_code = clean_room_code
    st.session_state.nickname = nickname.strip()
    st.session_state.is_host = is_current_user_host(clean_room_code, nickname)

    st.success("加入房間成功。")
    st.rerun()


def is_current_user_host(room_code, nickname):
    """Return True when the nickname matches this room's host nickname.

    This lets the host close the browser and later rejoin the same room with the
    same nickname to regain phase-control permission. This is still an MVP
    without passwords, so host identity is nickname-based.
    """
    host_nickname = get_room_host(room_code)
    return host_nickname.strip().lower() == nickname.strip().lower()


def render_room_header(room_code):
    """Show current room info, members, and host-only phase controls."""
    members = get_room_members(room_code)
    phase = get_room_phase(room_code)
    host = get_room_host(room_code)

    st.title("🌱 小組專案主題共識建立系統")

    info_col1, info_col2, info_col3 = st.columns(3)
    info_col1.metric("Room code", room_code)
    info_col2.metric("目前房間人數", len(members))
    info_col3.metric("目前階段", f"Phase {phase}")

    with st.container(border=True):
        st.write(f"Host：{host}")
        st.write("已加入成員：" + "、".join(members))

    if st.session_state.is_host:
        render_host_phase_controls(room_code, phase)
    else:
        st.info("只有 host 可以切換階段；一般成員可以查看與填答。")

    st.divider()


def render_host_phase_controls(room_code, current_phase):
    """Allow only host to change phase for the current room."""
    st.subheader("Host 階段控制")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Phase 1：主題提案", use_container_width=True, disabled=current_phase == 1):
            change_room_phase(room_code, 1)
    with col2:
        if st.button("Phase 2：主題評估", use_container_width=True, disabled=current_phase == 2):
            change_room_phase(room_code, 2)
    with col3:
        if st.button("Phase 3：結果分析", use_container_width=True, disabled=current_phase == 3):
            change_room_phase(room_code, 3)


def change_room_phase(room_code, phase):
    """Update room phase and rerun so everyone sees the latest state soon."""
    update_room_phase(room_code, phase)
    st.success(f"已切換到 Phase {phase}。")
    st.rerun()


def render_fixed_aspects():
    """Show the fixed evaluation aspects."""
    st.subheader("固定評估面向")
    cols = st.columns(4)
    for index, aspect in enumerate(EVALUATION_ASPECTS):
        with cols[index]:
            st.container(border=True).write(f"✨ {aspect['label']}")


def render_idea_list(room_code):
    """Show all collected project ideas in the current room."""
    ideas = get_project_ideas(room_code)
    st.subheader("目前已收集的專案主題")

    if not ideas:
        st.info("尚未新增主題。")
        return

    cols = st.columns(2)
    for index, idea in enumerate(ideas):
        with cols[index % 2]:
            st.container(border=True).write(f"💡 {idea}")


def render_submitter_list(room_code):
    """Show users who submitted at least one project idea in the room."""
    submitters = get_idea_submitters(room_code)
    st.subheader("已提交主題的使用者")

    if not submitters:
        st.info("目前還沒有人提交。")
        return

    for submitter in submitters:
        st.write(f"👤 {submitter}")


def phase_1_submit_ideas(room_code):
    """Phase 1: collect project ideas from users in one room."""
    st.header("Phase 1：主題提案")
    render_fixed_aspects()

    left_col, right_col = st.columns([1, 1])

    with left_col:
        with st.container(border=True):
            st.subheader("新增專案主題 idea")
            st.write(f"提交者：{st.session_state.nickname}")
            idea_text = st.text_area(
                "請輸入專案主題",
                placeholder="例如：分析學生期中期末情緒、美食推薦系統、AI 心理聊天機器人",
                help="可一次輸入多個主題，請用逗號或換行分隔。",
            )

            if st.button("送出主題", type="primary", use_container_width=True):
                submit_ideas(room_code, st.session_state.nickname, idea_text)

    with right_col:
        render_submitter_list(room_code)

    render_idea_list(room_code)


def submit_ideas(room_code, user_name, idea_text):
    """Validate and save one or multiple project ideas in one room."""
    if is_blank(idea_text):
        st.warning("主題不可空白。")
        return

    added_count = 0
    duplicated_count = 0

    for idea_title in split_multiple_lines(idea_text):
        is_added = add_project_idea(room_code, user_name, idea_title)
        if is_added:
            added_count += 1
        else:
            duplicated_count += 1

    if added_count > 0:
        st.success(f"成功新增 {added_count} 個專案主題。")
    if duplicated_count > 0:
        st.warning(f"有 {duplicated_count} 個主題已存在於此房間，系統已自動略過。")
    if added_count == 0 and duplicated_count == 0:
        st.error("沒有可提交的有效主題。")


def phase_2_evaluate_ideas(room_code):
    """Phase 2: each user evaluates every project idea with 10 points."""
    st.header("Phase 2：主題評估")

    ideas = get_project_ideas(room_code)
    if not ideas:
        st.warning("目前沒有可評估的主題，請先完成 Phase 1。")
        return

    user_name = st.session_state.nickname
    if has_user_evaluated(room_code, user_name):
        st.success("你已經提交過評估，可以等待其他成員完成。")
        show_evaluator_list(room_code)
        return

    with st.container(border=True):
        st.write(f"評估者：{user_name}")
        st.info("每一個主題都有 10 點，請分配到四個固定面向，且每個主題都必須剛好等於 10 點。")

        evaluations = {}
        invalid_ideas = []

        for idea in ideas:
            scores, used_points = render_one_idea_evaluation(idea)
            evaluations[idea] = scores

            if used_points != TOTAL_POINTS:
                invalid_ideas.append(idea)

        if invalid_ideas:
            st.warning("還有主題的點數不是 10 點，請調整後再提交。")
        else:
            st.success("所有主題都剛好 10 點，可以提交。")

        if st.button("送出全部評估", type="primary", use_container_width=True):
            submit_evaluations(room_code, user_name, evaluations, invalid_ideas)

    show_evaluator_list(room_code)


def show_evaluator_list(room_code):
    """Show users who already submitted evaluations in this room."""
    evaluators = get_evaluators(room_code)
    if evaluators:
        st.subheader("已完成評估的使用者")
        st.write("、".join(evaluators))


def render_one_idea_evaluation(idea):
    """Render sliders for one project idea and return scores."""
    with st.container(border=True):
        st.subheader(f"💡 {idea}")

        scores = {}
        cols = st.columns(4)

        for index, aspect in enumerate(EVALUATION_ASPECTS):
            with cols[index]:
                points = st.slider(
                    aspect["label"],
                    0,
                    TOTAL_POINTS,
                    0,
                    key=f"{idea}_{aspect['key']}",
                )
                scores[aspect["key"]] = points

        used_points = sum(scores.values())
        remaining_points = TOTAL_POINTS - used_points

        metric_col1, metric_col2 = st.columns(2)
        metric_col1.metric("已使用點數", used_points)
        metric_col2.metric("剩餘點數", remaining_points)

        if remaining_points > 0:
            st.warning("這個主題尚未分配完 10 點。")
        elif remaining_points < 0:
            st.error("這個主題超過 10 點。")
        else:
            st.success("這個主題剛好 10 點。")

    return scores, used_points


def submit_evaluations(room_code, user_name, evaluations, invalid_ideas):
    """Validate and save all evaluations for one user in one room."""
    if has_user_evaluated(room_code, user_name):
        st.error("你已經提交過評估。")
        return

    if invalid_ideas:
        st.error("所有主題的四個面向總和都必須剛好等於 10，無法提交。")
        return

    save_evaluations(room_code, user_name, evaluations)
    st.success("評估已成功送出。")
    st.rerun()


def phase_3_analyze_results(room_code):
    """Phase 3: show result tables and charts for every project idea."""
    st.header("Phase 3：結果分析")

    results = get_evaluation_results(room_code)
    if not results:
        st.warning("目前尚無評估結果，請先完成 Phase 2。")
        return

    result_rows = build_result_rows(results)
    ranking_df = build_ranking_dataframe(result_rows)

    st.subheader("主題排序總覽")
    st.dataframe(ranking_df, use_container_width=True, hide_index=True)

    st.subheader("各主題四面向分析")
    for row in result_rows:
        render_one_result(row)


def build_ranking_dataframe(result_rows):
    """Create a summary dataframe sorted by total score."""
    table_rows = []

    for index, row in enumerate(result_rows, start=1):
        scores = row["scores"]
        table_rows.append(
            {
                "排名": index,
                "專案主題": row["project_idea"],
                "總分": row["total_score"],
                "創意性": scores["creativity"],
                "可行性": scores["feasibility"],
                "實用性": scores["practicality"],
                "技術深度": scores["technical_depth"],
            }
        )

    return pd.DataFrame(table_rows)


def render_one_result(result_row):
    """Render charts and table for one project idea."""
    with st.container(border=True):
        st.markdown(f"### 💡 {result_row['project_idea']}")

        chart_rows = aspect_chart_rows(result_row["scores"])
        chart_df = pd.DataFrame(chart_rows)

        st.dataframe(chart_df, use_container_width=True, hide_index=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 雷達圖")
            radar_fig = px.line_polar(
                chart_df,
                r="總分",
                theta="面向",
                line_close=True,
                markers=True,
            )
            radar_fig.update_traces(fill="toself")
            radar_fig.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, max(TOTAL_POINTS, chart_df["總分"].max())],
                    )
                ),
                showlegend=False,
            )
            st.plotly_chart(radar_fig, use_container_width=True)

        with col2:
            st.markdown("#### 長條圖")
            bar_fig = px.bar(
                chart_df,
                x="面向",
                y="總分",
                text="總分",
                color="面向",
            )
            bar_fig.update_layout(showlegend=False)
            st.plotly_chart(bar_fig, use_container_width=True)


def render_room_app():
    """Render the app after a user has entered a room."""
    room_code = st.session_state.room_code

    if not room_exists(room_code):
        st.error("這個房間不存在，請重新建立或加入房間。")
        clear_current_room()
        return

    render_room_header(room_code)

    phase = get_room_phase(room_code)
    if phase == 1:
        phase_1_submit_ideas(room_code)
    elif phase == 2:
        phase_2_evaluate_ideas(room_code)
    else:
        phase_3_analyze_results(room_code)

    if st.button("離開房間"):
        clear_current_room()


def clear_current_room():
    """Clear session room info for the current browser only."""
    st.session_state.room_code = ""
    st.session_state.nickname = ""
    st.session_state.is_host = False
    st.rerun()


def main():
    """Main entry point for the Streamlit app."""
    init_db()
    setup_page()
    init_session_state()
    auto_refresh_page()

    if st.session_state.room_code:
        render_room_app()
    else:
        render_home_page()


if __name__ == "__main__":
    main()
