import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, time, timedelta

DB_FILE = "collab_platform.db"


def init_time_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS member_schedules (
                room_code TEXT,
                user_name TEXT,
                target_date TEXT,
                time_slot TEXT,
                join_type TEXT,
                PRIMARY KEY(room_code, user_name, target_date, time_slot)
            )"""
        )
        conn.commit()


init_time_db()


def save_member_schedule(room_code, user_name, target_date, slots_dict):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            "DELETE FROM member_schedules WHERE room_code = ? AND user_name = ? AND target_date = ?",
            (room_code, user_name, str(target_date)),
        )
        for slot, join_type in slots_dict.items():
            conn.execute(
                """INSERT INTO member_schedules (room_code, user_name, target_date, time_slot, join_type)
                   VALUES (?, ?, ?, ?, ?)""",
                (room_code, user_name, str(target_date), slot, join_type),
            )
        conn.commit()


def generate_30min_slots():
    slots = []
    current = datetime.strptime("08:00", "%H:%M")
    end = datetime.strptime("20:00", "%H:%M")
    while current <= end:
        slots.append(current.strftime("%H:%M"))
        current += timedelta(minutes=30)
    return slots


def parse_slider_to_slots(start_time, end_time, join_type):
    slots_map = {}
    current_dt = datetime.combine(datetime.today(), start_time)
    end_dt = datetime.combine(datetime.today(), end_time)
    while current_dt < end_dt:
        slots_map[current_dt.strftime("%H:%M")] = join_type
        current_dt += timedelta(minutes=30)
    return slots_map


# --- UI ---
room = st.session_state.get("platform_room_code", "TEST_ROOM")
user = st.session_state.get("platform_user_name", "匿名組員")

st.title("📆 大團隊跨日智慧時間調度系統")
st.markdown("##### 支援整月多日期排程。透過「先挑大日子、再選小時段」的聯動機制，徹底消滅資訊過載。")
st.divider()

col_input, col_dashboard = st.columns([1, 1.3])

with col_input:
    st.subheader("⏱️ 填寫我的空檔")
    st.caption(f"操作者：`{user}` | 房間：`{room}`")

    input_date = st.date_input(
        "選擇要登記空檔的日期：",
        min_value=datetime.today(),
        key="input_date_picker",
    )
    st.divider()

    st.markdown("🏢 **我可以「實體參與」的時間區間：**")
    physical_range = st.slider(
        "選擇實體區間",
        min_value=time(8, 0),
        max_value=time(20, 0),
        value=(time(9, 0), time(12, 0)),
        step=timedelta(minutes=30),
        format="HH:mm",
        key="p_slider",
        label_visibility="collapsed",
    )

    st.markdown("💻 **我可以「線上參與」的時間區間：**")
    online_range = st.slider(
        "選擇線上區間",
        min_value=time(8, 0),
        max_value=time(20, 0),
        value=(time(14, 0), time(17, 0)),
        step=timedelta(minutes=30),
        format="HH:mm",
        key="o_slider",
        label_visibility="collapsed",
    )

    if st.button("💾 提交此日期空檔", type="primary", use_container_width=True):
        physical_slots = parse_slider_to_slots(physical_range[0], physical_range[1], "🏢 實體")
        online_slots = parse_slider_to_slots(online_range[0], online_range[1], "💻 線上")
        combined_slots = {**online_slots, **physical_slots}

        if physical_range[0] == physical_range[1] and online_range[0] == online_range[1]:
            st.error("❌ 請至少拉動一條滑桿選擇有效的時間範圍。")
        else:
            save_member_schedule(room, user, input_date, combined_slots)
            st.toast(f"🎉 {input_date} 的時間已成功同步！", icon="📅")
            st.rerun()

with col_dashboard:
    with sqlite3.connect(DB_FILE) as conn:
        df_all_raw = pd.read_sql_query(
            "SELECT user_name, target_date, time_slot, join_type FROM member_schedules WHERE room_code = ?",
            conn,
            params=(room,),
        )

    if df_all_raw.empty:
        st.info("⏳ 目前資料庫內尚無任何組員遞交任何日期的時間。請在左側提交以解鎖看板！")
    else:
        st.subheader("🗓️ 第一層：黃金日期風向球")
        st.caption("統計各個日期的參與熱度。**點擊下方任一日期**可解鎖當天的精細時間明細。")

        df_date_user_count = (
            df_all_raw.groupby("target_date")["user_name"].nunique().reset_index(name="total_respondents")
        )
        df_date_slot_peak = (
            df_all_raw.groupby(["target_date", "time_slot"]).size().reset_index(name="slot_users")
        )
        df_date_peak = (
            df_date_slot_peak.groupby("target_date")["slot_users"].max().reset_index(name="peak_consensus")
        )

        df_date_rank = pd.merge(df_date_user_count, df_date_peak, on="target_date")
        df_date_rank = df_date_rank.sort_values(
            by=["peak_consensus", "total_respondents", "target_date"],
            ascending=[False, False, True],
        )

        df_date_display = df_date_rank.copy().rename(
            columns={
                "target_date": "📅 候選日期",
                "total_respondents": "👥 已填寫人數",
                "peak_consensus": "🔥 最高共識人數 (單一時段)",
            }
        )

        date_selection_event = st.dataframe(
            df_date_display,
            column_config={
                "📅 候選日期": st.column_config.TextColumn("📅 候選日期", width="medium"),
                "👥 已填寫人數": st.column_config.NumberColumn("👥 已填寫人數", format="%d 人"),
                "🔥 最高共識人數 (單一時段)": st.column_config.ProgressColumn(
                    "🔥 最高共識共識度",
                    format="%d 人",
                    min_value=0,
                    max_value=max(df_date_rank["total_respondents"]),
                ),
            },
            hide_index=True,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
            key="date_selector_table",
        )

        selected_date_rows = date_selection_event.get("selection", {}).get("rows", [])
        if selected_date_rows:
            active_date_str = df_date_rank.iloc[selected_date_rows[0]]["target_date"]
            is_default_date = False
        else:
            active_date_str = df_date_rank.iloc[0]["target_date"]
            is_default_date = True

        st.markdown(
            f"📍 當前聚焦檢視：{'🌟 推薦首選 ➔ ' if is_default_date else '🔍 已選取 ➔ '} **`{active_date_str}`**"
        )

        df_day_raw = df_all_raw[df_all_raw["target_date"] == active_date_str].copy()
        day_total_respondents = df_day_raw["user_name"].nunique()

        st.divider()
        st.subheader(f"📊 第二層：⏱️ {active_date_str} 時間微觀明細")
        st.caption("點擊下方表格內的**特定時段**，即可在最下方查閱該時段的實體與線上點名簿。")

        def analyze_day_slots(group):
            p_count = sum(group["join_type"].str.contains("實體"))
            o_count = sum(group["join_type"].str.contains("線上"))
            return pd.Series(
                {
                    "total_count": len(group),
                    "summary_text": f"🏢 實體 {p_count} 人 | 💻 線上 {o_count} 人",
                }
            )

        df_day_stats = (
            df_day_raw.groupby("time_slot").apply(analyze_day_slots, include_groups=False).reset_index()
        )

        all_slots_df = pd.DataFrame({"time_slot": generate_30min_slots()})
        df_macro = pd.merge(all_slots_df, df_day_stats, on="time_slot", how="left")
        df_macro["total_count"] = df_macro["total_count"].fillna(0).astype(int)
        df_macro["summary_text"] = df_macro["summary_text"].fillna("─")

        col_f1, col_f2 = st.columns([1.2, 1])
        with col_f1:
            hide_zero = st.toggle(
                "🔍 自動隱藏無人可參與的冷門時段",
                value=True,
                key=f"toggle_{active_date_str}",
            )
        with col_f2:
            time_bucket = st.radio(
                "🕒 時段分流",
                ["全天", "☀️ 上半天", "🌆 下半天"],
                horizontal=True,
                key=f"radio_{active_date_str}",
            )

        if hide_zero:
            df_macro = df_macro[df_macro["total_count"] > 0]
        if time_bucket == "☀️ 上半天":
            df_macro = df_macro[df_macro["time_slot"] < "14:00"]
        elif time_bucket == "🌆 下半天":
            df_macro = df_macro[df_macro["time_slot"] >= "14:00"]

        def format_macro_range(slot_str):
            h, m = map(int, slot_str.split(":"))
            end_dt = datetime.combine(datetime.today(), time(h, m)) + timedelta(minutes=30)
            return f"{slot_str} ─ {end_dt.strftime('%H:%M')}"

        if df_macro.empty:
            st.info("💡 提示：目前篩選條件下，該日期沒有對應的時間數據。")
        else:
            df_macro["⏰ 時間段"] = df_macro["time_slot"].apply(format_macro_range)
            df_macro_display = df_macro[["time_slot", "⏰ 時間段", "total_count", "summary_text"]].rename(
                columns={"total_count": "👥 共識人數", "summary_text": "📊 分流狀態"}
            )

            slot_selection_event = st.dataframe(
                df_macro_display.drop(columns=["time_slot"]),
                column_config={
                    "⏰ 時間段": st.column_config.TextColumn("⏰ 時間段", width="medium"),
                    "👥 共識人數": st.column_config.ProgressColumn(
                        "👥 共識人數",
                        format="%d 人",
                        min_value=0,
                        max_value=day_total_respondents,
                    ),
                    "📊 分流狀態": st.column_config.TextColumn("📊 分流狀態", width="medium"),
                },
                hide_index=True,
                use_container_width=True,
                on_select="rerun",
                selection_mode="single-row",
                key=f"slot_selector_table_{active_date_str}",
            )

            selected_slot_rows = slot_selection_event.get("selection", {}).get("rows", [])

            if selected_slot_rows and selected_slot_rows[0] < len(df_macro_display):
                chosen_slot_index = selected_slot_rows[0]
                chosen_slot_range = df_macro_display.iloc[chosen_slot_index]["⏰ 時間段"]
                chosen_slot_id = df_macro.iloc[chosen_slot_index]["time_slot"]

                df_detail = df_day_raw[df_day_raw["time_slot"] == chosen_slot_id]

                st.markdown(f"##### 🔍 第三層：`{active_date_str}`【`{chosen_slot_range}`】點名簿")

                col_p, col_o = st.columns(2)
                with col_p:
                    st.markdown("**🏢 實體組成員：**")
                    p_list = df_detail[df_detail["join_type"] == "🏢 實體"]["user_name"].tolist()
                    if p_list:
                        for name in p_list:
                            st.markdown(f"• `{name}`")
                    else:
                        st.caption("無人選擇實體")

                with col_o:
                    st.markdown("**💻 線上組成員：**")
                    o_list = df_detail[df_detail["join_type"] == "💻 線上"]["user_name"].tolist()
                    if o_list:
                        for name in o_list:
                            st.markdown(f"• `{name}`")
                    else:
                        st.caption("無人選擇線上")
            else:
                st.caption("💡 提示：點擊上方微觀明細中的任何時段，可在此處查閱該時段的詳細成員名單。")
