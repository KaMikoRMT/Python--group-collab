import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import pandas as pd
import streamlit as st

from database import (
    create_room,
    get_member_responses,
    get_members,
    get_phase,
    get_project_settings,
    get_questions,
    get_room,
    get_submitted_members,
    get_tasks,
    has_submitted,
    init_db,
    join_room,
    save_assignments,
    save_member_response,
    save_project_settings,
    save_questions,
    save_tasks,
    update_phase,
)
from optimizer import combine_assignment_tables, run_assignment
from utils import (
    DEFAULT_QUESTIONS,
    DEFAULT_TASKS,
    build_heatmap,
    summarize_missing_members,
    validate_ranks,
    validate_task_requirements,
)


st.set_page_config(page_title="?極撱箄降?遙??蝵桃頂蝯?, layout="wide")
init_db()


def ensure_session_defaults():
    st.session_state.setdefault("room_code", "")
    st.session_state.setdefault("nickname", "")
    st.session_state.setdefault("is_host", False)


def current_room_code():
    return st.session_state.get("room_code", "")


@st.fragment(run_every="2s")
def rerun_when_phase_changes(room_code, current_phase):
    latest_phase = get_phase(room_code)
    if latest_phase != current_phase:
        st.rerun()


def show_lobby():
    st.title("?極撱箄降?遙??蝵桃頂蝯?)
    create_tab, join_tab = st.tabs(["撱箇??輸?", "??輸?"])

    with create_tab:
        with st.form("create_room_form"):
            nickname = st.text_input("雿? nickname", key="create_nickname")
            submitted = st.form_submit_button("撱箇??輸?")
        if submitted:
            try:
                room_code = create_room(nickname)
                st.session_state.room_code = room_code
                st.session_state.nickname = nickname.strip()
                st.session_state.is_host = True
                st.success(f"?輸?撌脣遣蝡?{room_code}")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    with join_tab:
        with st.form("join_room_form"):
            room_code = st.text_input("room_code").upper()
            nickname = st.text_input("雿? nickname", key="join_nickname")
            submitted = st.form_submit_button("??輸?")
        if submitted:
            try:
                member = join_room(room_code, nickname)
                st.session_state.room_code = member["room_code"]
                st.session_state.nickname = member["nickname"]
                st.session_state.is_host = member["is_host"]
                st.success("???")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))


def show_room_header():
    room = get_room(current_room_code())
    if not room:
        st.error("?曆??啁???隢??啣??乓?)
        if st.button("????):
            st.session_state.clear()
            st.rerun()
        st.stop()

    role = "Host" if st.session_state.is_host else "Member"
    left, mid, right = st.columns([2, 2, 1])
    left.metric("Room Code", current_room_code())
    mid.metric("Nickname", st.session_state.nickname)
    right.metric("頨怠?", role)
    st.caption(f"撠?嚗room['project_name']}嚚??畾蛛?{room['phase']}")

    if st.button("?ａ??輸?"):
        st.session_state.clear()
        st.rerun()
    st.divider()
    return room


def load_or_default_tasks(room_code):
    tasks = get_tasks(room_code)
    if tasks.empty:
        tasks = DEFAULT_TASKS.copy()
    return tasks[["task_code", "task_name", "task_type", "required_count"]]


def load_or_default_questions(room_code):
    questions = get_questions(room_code)
    if questions.empty:
        questions = DEFAULT_QUESTIONS.copy()
    return questions[["task_code", "question_code", "question_text"]]


def show_host_settings():
    room_code = current_room_code()
    settings = get_project_settings(room_code)
    tasks = load_or_default_tasks(room_code)
    questions = load_or_default_questions(room_code)

    st.header("Host 閮剖?")
    with st.form("project_settings_form"):
        project_name = st.text_input("撠??迂", value=settings.get("project_name") or "?芸??獢?)
        member_count = st.number_input(
            "?鈭箸",
            min_value=1,
            step=1,
            value=int(settings.get("member_count") or 1),
        )

        st.subheader("撌乩??漲")
        edited_tasks = st.data_editor(
            tasks,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "task_code": st.column_config.TextColumn("隞?Ⅳ嚗?憒?A"),
                "task_name": st.column_config.TextColumn("撌乩??迂"),
                "task_type": st.column_config.SelectboxColumn("憿?", options=["main", "sub"]),
                "required_count": st.column_config.NumberColumn("?閬犖??, min_value=1, step=1),
            },
            key="task_editor",
        )

        st.subheader("憿閮剖?")
        edited_questions = st.data_editor(
            questions,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "task_code": st.column_config.TextColumn("撌乩?隞?Ⅳ"),
                "question_code": st.column_config.TextColumn("憿隞?Ⅳ嚗?憒?A1"),
                "question_text": st.column_config.TextColumn("憿??"),
            },
            key="question_editor",
        )
        submitted = st.form_submit_button("?脣?閮剖?")

    if submitted:
        try:
            cleaned_tasks = clean_tasks(edited_tasks)
            cleaned_questions = clean_questions(edited_questions, cleaned_tasks)
            errors, slots = validate_task_requirements(cleaned_tasks, int(member_count))
            if errors:
                for error in errors:
                    st.error(error)
                return
            save_project_settings(room_code, project_name, int(member_count))
            save_tasks(room_code, cleaned_tasks)
            save_questions(room_code, cleaned_questions)
            st.success(
                f"閮剖?撌脣摮?雿??∩蜓撌乩? {slots['main_slots_per_member']} ???臬極雿?{slots['sub_slots_per_member']} ??
            )
        except ValueError as exc:
            st.error(str(exc))

    st.subheader("?桀?閮剖?瑼Ｘ")
    saved_tasks = load_or_default_tasks(room_code)
    errors, slots = validate_task_requirements(saved_tasks, int(settings.get("member_count") or 1))
    if errors:
        for error in errors:
            st.error(error)
    else:
        st.info(
            f"銝餃極雿蜇?瘙?{slots['main_total']}嚗?鈭?{slots['main_slots_per_member']} ??"
            f"?臬極雿蜇?瘙?{slots['sub_total']}嚗?鈭?{slots['sub_slots_per_member']} ??
        )

    if st.session_state.is_host:
        if st.button("?脣?憛怎??挾"):
            settings = get_project_settings(room_code)
            tasks = get_tasks(room_code)
            questions = get_questions(room_code)
            errors, _ = validate_task_requirements(tasks, int(settings.get("member_count") or 1))
            if tasks.empty or questions.empty:
                st.error("隢??脣?撌乩????株身摰?)
            elif errors:
                for error in errors:
                    st.error(error)
            else:
                update_phase(room_code, 1)
                st.rerun()


def clean_tasks(tasks_df):
    df = tasks_df.dropna(how="all").copy()
    required = ["task_code", "task_name", "task_type", "required_count"]
    if df.empty or any(col not in df.columns for col in required):
        raise ValueError("撌乩?閮剖?甈?銝???)
    df = df[required]
    df["task_code"] = df["task_code"].astype(str).str.strip().str.upper()
    df["task_name"] = df["task_name"].astype(str).str.strip()
    df["task_type"] = df["task_type"].astype(str).str.strip()
    df["required_count"] = df["required_count"].astype(int)
    if df[["task_code", "task_name", "task_type"]].eq("").any().any():
        raise ValueError("撌乩?隞?Ⅳ??蝔晞????舐征??)
    if not df["task_type"].isin(["main", "sub"]).all():
        raise ValueError("撌乩?憿??芾??main ??sub")
    if df["task_code"].duplicated().any():
        raise ValueError("撌乩?隞?Ⅳ銝??")
    return df


def clean_questions(questions_df, tasks_df):
    df = questions_df.dropna(how="all").copy()
    required = ["task_code", "question_code", "question_text"]
    if df.empty or any(col not in df.columns for col in required):
        raise ValueError("憿閮剖?甈?銝???)
    df = df[required]
    df["task_code"] = df["task_code"].astype(str).str.strip().str.upper()
    df["question_code"] = df["question_code"].astype(str).str.strip().str.upper()
    df["question_text"] = df["question_text"].astype(str).str.strip()
    if df.eq("").any().any():
        raise ValueError("憿甈?銝蝛箇")
    if df["question_code"].duplicated().any():
        raise ValueError("憿隞?Ⅳ銝??")
    valid_codes = set(tasks_df["task_code"])
    if not set(df["task_code"]).issubset(valid_codes):
        raise ValueError("憿?極雿誨蝣澆????冽撌乩??漲銝?)
    missing_question_tasks = valid_codes - set(df["task_code"])
    if missing_question_tasks:
        raise ValueError(f"瘥極雿撠???憿?蝻箏?嚗', '.join(sorted(missing_question_tasks))}")
    return df


def show_member_form():
    room_code = current_room_code()
    tasks = get_tasks(room_code)
    questions = get_questions(room_code)
    members = get_members(room_code)
    submitted_members = get_submitted_members(room_code)

    st.header("?憛怎?")
    st.write("撌脫?鈭斗??∴?", "??.join(submitted_members) if submitted_members else "撠")
    if has_submitted(room_code, st.session_state.nickname):
        st.success("雿歇蝬?鈭文???隢?敺?Host ?脣蝯?????)
        rerun_when_phase_changes(room_code, 1)
    else:
        with st.form("member_response_form"):
            st.subheader("蝚砌??典?嚗?璈?銵?)
            raw_rows = []
            for _, task in tasks.iterrows():
                with st.expander(f"{task['task_code']}嚗task['task_name']}", expanded=True):
                    task_questions = questions[questions["task_code"] == task["task_code"]]
                    for _, question in task_questions.iterrows():
                        score = st.radio(
                            f"{question['question_code']}嚗question['question_text']}",
                            options=[1, 2, 3, 4, 5],
                            index=2,
                            horizontal=True,
                            key=f"score_{question['question_code']}",
                        )
                        raw_rows.append(
                            {
                                "task_code": task["task_code"],
                                "question_code": question["question_code"],
                                "score": score,
                            }
                        )

            st.subheader("蝚砌??典?嚗?憟賣?摨?)
            rank_rows = []
            for task_type, label in [("main", "銝餃極雿?摨?), ("sub", "?臬極雿?摨?)]:
                type_tasks = tasks[tasks["task_type"] == task_type]
                st.write(label)
                columns = st.columns(min(3, max(1, len(type_tasks))))
                for index, (_, task) in enumerate(type_tasks.iterrows()):
                    with columns[index % len(columns)]:
                        rank = st.selectbox(
                            f"{task['task_code']} {task['task_name']}",
                            options=list(range(1, len(type_tasks) + 1)),
                            key=f"rank_{task_type}_{task['task_code']}",
                        )
                    rank_rows.append(
                        {
                            "task_code": task["task_code"],
                            "task_type": task_type,
                            "rank": rank,
                        }
                    )

            submitted = st.form_submit_button("?漱憛怎?")

        if submitted:
            raw_df = pd.DataFrame(raw_rows)
            rank_df = pd.DataFrame(rank_rows)
            errors = []
            if len(raw_df) != len(questions):
                errors.append("?敹?摰????璈?銵券?")
            for task_type in ["main", "sub"]:
                expected_codes = tasks[tasks["task_type"] == task_type]["task_code"].tolist()
                rank_map = dict(zip(rank_df[rank_df["task_type"] == task_type]["task_code"], rank_df[rank_df["task_type"] == task_type]["rank"]))
                ok, message = validate_ranks(rank_map, expected_codes)
                if not ok:
                    errors.append(f"{task_type} {message}")
            if errors:
                for error in errors:
                    st.error(error)
            else:
                avg_df = raw_df.groupby("task_code", as_index=False)["score"].mean()
                avg_df = avg_df.rename(columns={"score": "avg_score"})
                try:
                    save_member_response(room_code, st.session_state.nickname, raw_df, avg_df, rank_df)
                    st.success("?漱??")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

    st.divider()
    if st.session_state.is_host:
        missing = summarize_missing_members(members, submitted_members)
        if missing:
            st.warning("撠?漱嚗? + "??.join(missing))
        if st.button("?脣蝯???"):
            settings = get_project_settings(room_code)
            expected_count = int(settings.get("member_count") or 0)
            if len(submitted_members) < expected_count or missing:
                st.error("撠?典?漱嚗??賡脣蝯???)
                if missing:
                    st.write("撠?漱嚗?, "??.join(missing))
            else:
                update_phase(room_code, 2)
                st.rerun()


def show_results():
    room_code = current_room_code()
    tasks = get_tasks(room_code)
    responses = get_member_responses(room_code)
    scores = responses["scores"]
    ranks = responses["ranks"]

    st.header("蝯???")
    rerun_when_phase_changes(room_code, 2)
    if scores.empty or ranks.empty:
        st.error("?桀?瘝?頞喳?憛怎?鞈??臭誑????)
        return

    main_assignment, main_cost, main_summary = run_assignment(scores, ranks, tasks, "main")
    sub_assignment, sub_cost, sub_summary = run_assignment(scores, ranks, tasks, "sub")
    all_assignment = pd.concat([main_assignment, sub_assignment], ignore_index=True)
    if st.session_state.is_host and st.button("?脣??祆活??蝯?"):
        save_assignments(room_code, all_assignment)
        st.success("撌脣摮?assignments")

    tab_a, tab_b, tab_c, tab_d = st.tabs(["?極撱箄降銵?, "蝯???", "???勗???, "??拚"])
    with tab_a:
        result_table = combine_assignment_tables(main_assignment, sub_assignment, tasks)
        st.dataframe(result_table, use_container_width=True)

    with tab_b:
        total_cost = main_summary["total_cost"] + sub_summary["total_cost"]
        first_choice_rate = all_assignment["preference_rank"].eq(1).mean()
        avg_score = all_assignment["motivation_score"].mean()
        min_score = all_assignment["motivation_score"].min()
        cols = st.columns(4)
        cols[0].metric("銝餃極雿蜇?", f"{main_summary['total_cost']:.2f}")
        cols[1].metric("?臬極雿蜇?", f"{sub_summary['total_cost']:.2f}")
        cols[2].metric("?湧?蝮賣???, f"{total_cost:.2f}")
        cols[3].metric("蝚砌?敹?????, f"{first_choice_rate:.0%}")
        cols2 = st.columns(2)
        cols2[0].metric("撟喳????", f"{avg_score:.2f}")
        cols2[1].metric("?雿?璈???, f"{min_score:.2f}")

        main_counts = main_assignment.groupby("nickname").size().rename("銝餃極雿")
        sub_counts = sub_assignment.groupby("nickname").size().rename("?臬極雿")
        count_df = pd.concat([main_counts, sub_counts], axis=1).fillna(0).astype(int).reset_index()
        count_df = count_df.rename(columns={"nickname": "?"})
        st.dataframe(count_df, use_container_width=True)

    with tab_c:
        main_tasks = tasks[tasks["task_type"] == "main"]
        sub_tasks = tasks[tasks["task_type"] == "sub"]
        st.plotly_chart(build_heatmap(scores, main_tasks, main_assignment, "銝餃極雿?璈??"), use_container_width=True)
        st.plotly_chart(build_heatmap(scores, sub_tasks, sub_assignment, "?臬極雿?璈??"), use_container_width=True)

    with tab_d:
        st.write("銝餃極雿??祉??)
        st.dataframe(main_cost, use_container_width=True)
        st.write("?臬極雿??祉??)
        st.dataframe(sub_cost, use_container_width=True)

    if st.session_state.is_host:
        st.divider()
        col1, col2 = st.columns(2)
        if col1.button("???∪‵蝑?畾?):
            update_phase(room_code, 1)
            st.rerun()
        if col2.button("??Host 閮剖??挾"):
            update_phase(room_code, 0)
            st.rerun()


def main():
    ensure_session_defaults()
    if not current_room_code():
        show_lobby()
        return

    room = show_room_header()
    phase = get_phase(current_room_code())
    if phase == 0:
        if st.session_state.is_host:
            show_host_settings()
        else:
            st.info("Host 甇?閮剖?撌乩????殷?隢???)
            rerun_when_phase_changes(current_room_code(), 0)
    elif phase == 1:
        show_member_form()
    elif phase == 2:
        show_results()
    else:
        st.error(f"?芰?挾嚗phase}")


if __name__ == "__main__":
    main()

