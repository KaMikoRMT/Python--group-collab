"""撠?撠?銝駁??梯?撱箇?蝟餌絞 MVP with room code.

Run with:
    python3 -m streamlit run app.py
"""

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
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
    st.title("? 撠?撠?銝駁??梯?撱箇?蝟餌絞")
    st.caption("撱箇????交??嚗?蝯?????room code ??靽???)

    create_col, join_col = st.columns(2)

    with create_col:
        with st.container(border=True):
            st.subheader("撱箇??輸?")
            host_nickname = st.text_input("雿? nickname", key="host_nickname")

            if st.button("撱箇??唳??, type="primary", use_container_width=True):
                handle_create_room(host_nickname)

    with join_col:
        with st.container(border=True):
            st.subheader("??輸?")
            room_code = st.text_input("Room code", key="join_room_code")
            nickname = st.text_input("雿? nickname", key="join_nickname")

            if st.button("??輸?", use_container_width=True):
                handle_join_room(room_code, nickname)


def handle_create_room(host_nickname):
    """Create a new room and save room info in session_state."""
    if is_blank(host_nickname):
        st.error("隢?頛詨 nickname??)
        return

    room_code = generate_unique_room_code()
    create_room(room_code, host_nickname)

    st.session_state.room_code = room_code
    st.session_state.nickname = host_nickname.strip()
    st.session_state.is_host = True

    st.success(f"雿? room code ?荔?{room_code}")
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
        st.error("隢撓??room code??)
        return

    if is_blank(nickname):
        st.error("隢撓??nickname??)
        return

    if not room_exists(clean_room_code):
        st.error("?曆??圈?room code嚗?蝣箄?敺?閰虫?甈～?)
        return

    add_room_member(clean_room_code, nickname)

    st.session_state.room_code = clean_room_code
    st.session_state.nickname = nickname.strip()
    st.session_state.is_host = is_current_user_host(clean_room_code, nickname)

    st.success("??輸?????)
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

    st.title("? 撠?撠?銝駁??梯?撱箇?蝟餌絞")

    info_col1, info_col2, info_col3 = st.columns(3)
    info_col1.metric("Room code", room_code)
    info_col2.metric("?桀??輸?鈭箸", len(members))
    info_col3.metric("?桀??挾", f"Phase {phase}")

    with st.container(border=True):
        st.write(f"Host嚗host}")
        st.write("撌脣??交??∴?" + "??.join(members))

    if st.session_state.is_host:
        render_host_phase_controls(room_code, phase)
    else:
        st.info("?芣? host ?臭誑???挾嚗??祆??∪隞交??憛怎???)

    st.divider()


def render_host_phase_controls(room_code, current_phase):
    """Allow only host to change phase for the current room."""
    st.subheader("Host ?挾?批")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Phase 1嚗蜓憿?獢?, use_container_width=True, disabled=current_phase == 1):
            change_room_phase(room_code, 1)
    with col2:
        if st.button("Phase 2嚗蜓憿?隡?, use_container_width=True, disabled=current_phase == 2):
            change_room_phase(room_code, 2)
    with col3:
        if st.button("Phase 3嚗?????, use_container_width=True, disabled=current_phase == 3):
            change_room_phase(room_code, 3)


def change_room_phase(room_code, phase):
    """Update room phase and rerun so everyone sees the latest state soon."""
    update_room_phase(room_code, phase)
    st.success(f"撌脣?? Phase {phase}??)
    st.rerun()


def render_fixed_aspects():
    """Show the fixed evaluation aspects."""
    st.subheader("?箏?閰摯?Ｗ?")
    cols = st.columns(4)
    for index, aspect in enumerate(EVALUATION_ASPECTS):
        with cols[index]:
            st.container(border=True).write(f"??{aspect['label']}")


def render_idea_list(room_code):
    """Show all collected project ideas in the current room."""
    ideas = get_project_ideas(room_code)
    st.subheader("?桀?撌脫??撠?銝駁?")

    if not ideas:
        st.info("撠?啣?銝駁???)
        return

    cols = st.columns(2)
    for index, idea in enumerate(ideas):
        with cols[index % 2]:
            st.container(border=True).write(f"? {idea}")


def render_submitter_list(room_code):
    """Show users who submitted at least one project idea in the room."""
    submitters = get_idea_submitters(room_code)
    st.subheader("撌脫?鈭支蜓憿?雿輻??)

    if not submitters:
        st.info("?桀????犖?漱??)
        return

    for submitter in submitters:
        st.write(f"? {submitter}")


def phase_1_submit_ideas(room_code):
    """Phase 1: collect project ideas from users in one room."""
    st.header("Phase 1嚗蜓憿?獢?)
    render_fixed_aspects()

    left_col, right_col = st.columns([1, 1])

    with left_col:
        with st.container(border=True):
            st.subheader("?啣?撠?銝駁? idea")
            st.write(f"?漱??{st.session_state.nickname}")
            idea_text = st.text_area(
                "隢撓?亙?獢蜓憿?,
                placeholder="靘?嚗??飛??銝剜??急?蝺?憌?衣頂蝯晞I 敹??予璈鈭?,
                help="?臭?甈∟撓?亙??蜓憿?隢????銵???,
            )

            if st.button("?銝駁?", type="primary", use_container_width=True):
                submit_ideas(room_code, st.session_state.nickname, idea_text)

    with right_col:
        render_submitter_list(room_code)

    render_idea_list(room_code)


def submit_ideas(room_code, user_name, idea_text):
    """Validate and save one or multiple project ideas in one room."""
    if is_blank(idea_text):
        st.warning("銝駁?銝蝛箇??)
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
        st.success(f"???啣? {added_count} ??獢蜓憿?)
    if duplicated_count > 0:
        st.warning(f"??{duplicated_count} ?蜓憿歇摮?潭迨?輸?嚗頂蝯勗歇?芸??仿???)
    if added_count == 0 and duplicated_count == 0:
        st.error("瘝??舀?鈭斤???銝駁???)


def phase_2_evaluate_ideas(room_code):
    """Phase 2: each user evaluates every project idea with 10 points."""
    st.header("Phase 2嚗蜓憿?隡?)

    ideas = get_project_ideas(room_code)
    if not ideas:
        st.warning("?桀?瘝??航?隡啁?銝駁?嚗?????Phase 1??)
        return

    user_name = st.session_state.nickname
    if has_user_evaluated(room_code, user_name):
        st.success("雿歇蝬?鈭日?閰摯嚗隞亦?敺隞??∪???)
        show_evaluator_list(room_code)
        return

    with st.container(border=True):
        st.write(f"閰摯??{user_name}")
        st.info("瘥??蜓憿??10 暺?隢???摰??銝??蜓憿敹??末蝑 10 暺?)

        evaluations = {}
        invalid_ideas = []

        for idea in ideas:
            scores, used_points = render_one_idea_evaluation(idea)
            evaluations[idea] = scores

            if used_points != TOTAL_POINTS:
                invalid_ideas.append(idea)

        if invalid_ideas:
            st.warning("??銝駁????訾???10 暺?隢矽?游???鈭扎?)
        else:
            st.success("??蜓憿?末 10 暺??臭誑?漱??)

        if st.button("??券閰摯", type="primary", use_container_width=True):
            submit_evaluations(room_code, user_name, evaluations, invalid_ideas)

    show_evaluator_list(room_code)


def show_evaluator_list(room_code):
    """Show users who already submitted evaluations in this room."""
    evaluators = get_evaluators(room_code)
    if evaluators:
        st.subheader("撌脣???隡啁?雿輻??)
        st.write("??.join(evaluators))


def render_one_idea_evaluation(idea):
    """Render sliders for one project idea and return scores."""
    with st.container(border=True):
        st.subheader(f"? {idea}")

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
        metric_col1.metric("撌脖蝙?券???, used_points)
        metric_col2.metric("?拚?暺", remaining_points)

        if remaining_points > 0:
            st.warning("?蜓憿??芸??? 10 暺?)
        elif remaining_points < 0:
            st.error("?蜓憿???10 暺?)
        else:
            st.success("?蜓憿?憟?10 暺?)

    return scores, used_points


def submit_evaluations(room_code, user_name, evaluations, invalid_ideas):
    """Validate and save all evaluations for one user in one room."""
    if has_user_evaluated(room_code, user_name):
        st.error("雿歇蝬?鈭日?閰摯??)
        return

    if invalid_ideas:
        st.error("??蜓憿???蜇?敹??末蝑 10嚗瘜?鈭扎?)
        return

    save_evaluations(room_code, user_name, evaluations)
    st.success("閰摯撌脫????)
    st.rerun()


def phase_3_analyze_results(room_code):
    """Phase 3: show result tables and charts for every project idea."""
    st.header("Phase 3嚗?????)

    results = get_evaluation_results(room_code)
    if not results:
        st.warning("?桀?撠閰摯蝯?嚗?????Phase 2??)
        return

    result_rows = build_result_rows(results)
    ranking_df = build_ranking_dataframe(result_rows)

    st.subheader("銝駁???蝮質汗")
    st.dataframe(ranking_df, use_container_width=True, hide_index=True)

    st.subheader("?蜓憿??Ｗ???")
    for row in result_rows:
        render_one_result(row)


def build_ranking_dataframe(result_rows):
    """Create a summary dataframe sorted by total score."""
    table_rows = []

    for index, row in enumerate(result_rows, start=1):
        scores = row["scores"]
        table_rows.append(
            {
                "??": index,
                "撠?銝駁?": row["project_idea"],
                "蝮賢?": row["total_score"],
                "?菜???: scores["creativity"],
                "?航???: scores["feasibility"],
                "撖衣??: scores["practicality"],
                "?銵楛摨?: scores["technical_depth"],
            }
        )

    return pd.DataFrame(table_rows)


def render_one_result(result_row):
    """Render charts and table for one project idea."""
    with st.container(border=True):
        st.markdown(f"### ? {result_row['project_idea']}")

        chart_rows = aspect_chart_rows(result_row["scores"])
        chart_df = pd.DataFrame(chart_rows)

        st.dataframe(chart_df, use_container_width=True, hide_index=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### ?琿???)
            radar_fig = px.line_polar(
                chart_df,
                r="蝮賢?",
                theta="?Ｗ?",
                line_close=True,
                markers=True,
            )
            radar_fig.update_traces(fill="toself")
            radar_fig.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, max(TOTAL_POINTS, chart_df["蝮賢?"].max())],
                    )
                ),
                showlegend=False,
            )
            st.plotly_chart(radar_fig, use_container_width=True)

        with col2:
            st.markdown("#### ?瑟???)
            bar_fig = px.bar(
                chart_df,
                x="?Ｗ?",
                y="蝮賢?",
                text="蝮賢?",
                color="?Ｗ?",
            )
            bar_fig.update_layout(showlegend=False)
            st.plotly_chart(bar_fig, use_container_width=True)


def render_room_app():
    """Render the app after a user has entered a room."""
    room_code = st.session_state.room_code

    if not room_exists(room_code):
        st.error("???摮嚗??撱箇????交??)
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

    if st.button("?ａ??輸?"):
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

