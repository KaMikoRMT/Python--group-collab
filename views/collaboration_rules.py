import streamlit as st
import pandas as pd
import sqlite3
import re
from pydantic import BaseModel, Field, field_validator
from google import genai
from google.genai import types

DB_FILE = "collab_platform.db"


# --- Pydantic models ---

class RuleSubmission(BaseModel):
    room_code: str
    user_name: str
    content: str = Field(..., min_length=4, max_length=150)

    @field_validator("content")
    @classmethod
    def check_logic(cls, v: str) -> str:
        if re.findall(r"-\d+", v):
            raise ValueError("規範條文中的時間或懲罰數值不可為負數！")
        return v


class StructuredRule(BaseModel):
    category: str = Field(..., description="公約的繁體分類名稱")
    rule_text: str = Field(..., description="正式繁體中文公約條文")


class GeminiClusteredOutput(BaseModel):
    rules: list[StructuredRule] = Field(..., description="整併後的公約條文列表")


# --- DB helpers ---

def init_rules_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS raw_suggestions (room_code TEXT, content TEXT)"
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS cluster_rules
               (room_code TEXT, category TEXT, rule_text TEXT, votes_count INTEGER DEFAULT 0)"""
        )
        conn.commit()


def init_voting_tables():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS rule_votes
               (room_code TEXT, rule_rowid INTEGER, user_name TEXT,
                vote_type TEXT, preferred_param TEXT,
                PRIMARY KEY(room_code, rule_rowid, user_name))"""
        )
        conn.commit()


init_rules_db()
init_voting_tables()


def submit_vote(room_code, rule_id, user_name, vote_type, param):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """INSERT OR REPLACE INTO rule_votes
               (room_code, rule_rowid, user_name, vote_type, preferred_param)
               VALUES (?, ?, ?, ?, ?)""",
            (room_code, rule_id, user_name, vote_type, param),
        )
        conn.commit()


def save_raw_suggestion(room_code, content):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            "INSERT INTO raw_suggestions (room_code, content) VALUES (?, ?)",
            (room_code, content),
        )
        conn.commit()


def get_raw_suggestions(room_code):
    with sqlite3.connect(DB_FILE) as conn:
        df = pd.read_sql_query(
            "SELECT content FROM raw_suggestions WHERE room_code = ?",
            conn,
            params=(room_code,),
        )
    return df["content"].tolist()


def save_gemini_rules(room_code, structured_rules):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DELETE FROM cluster_rules WHERE room_code = ?", (room_code,))
        for rule in structured_rules:
            conn.execute(
                "INSERT INTO cluster_rules (room_code, category, rule_text) VALUES (?, ?, ?)",
                (room_code, rule.category, rule.rule_text),
            )
        conn.commit()


# --- Gemini integration ---

def run_gemini_integration(room_code):
    suggestions = get_raw_suggestions(room_code)

    if len(suggestions) < 2:
        st.warning("⚠️ 目前房間內的意見太少（少於 2 則），請先邀請組員多填寫一些想法再啟動 AI！")
        return

    if "GEMINI_API_KEY" not in st.secrets:
        st.error("❌ 找不到 GEMINI_API_KEY！請在 `.streamlit/secrets.toml` 中設定。")
        return

    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    suggestions_block = "\n".join([f"- {s}" for s in suggestions])

    prompt = f"""
    你是一個專業的團隊教練與文字修飾專家。
    以下是某個大學專案小組成員針對「團隊合作規範」匿名提交的原始發散意見：

    {suggestions_block}

    請幫我嚴格執行以下任務，並遵守絕對底線：

    1. 【嚴格禁止腦補與無中生有（最高天條）】：
       - 你只能、也必須「完全根據」上方提供的原始意見進行歸納修飾。
       - 原始意見中「沒有提到」的主題或觀念，你「絕對不能」自行憑空捏造或延伸！

    2. 【規定與罰則分離】：
       - 請仔細分辨意見中的「行為標準（規定）」與「違反後果（罰則）」，兩者絕對「不可以」合併成同一條！

    3. 【同屬性去重】：
       - 只有在「同為規定」或「同為罰則」且語意高度相似時，才需要進行合併去重。

    4. 【條文化修飾與分類】：
       - 將口語化的碎碎念修飾為語氣專業、條理清晰的「正式小組公約草案」。
       - 依據內容性質分組，分類名稱後方明確標註性質，例如：「會議紀律（規定）」與「會議紀律（罰則）」。

    5. 【繁體中文輸出】：
       - 所有輸出必須「完全使用台灣習慣的繁體中文」。
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=GeminiClusteredOutput,
                temperature=0.1,
            ),
        )
        structured_data = GeminiClusteredOutput.model_validate_json(response.text)
        save_gemini_rules(room_code, structured_data.rules)
        st.success("🧠 Gemini 智慧公約整併完成！重複意見已去重，且已全面轉換為繁體中文。")
    except Exception as e:
        st.error(f"🤖 Gemini 運算過程中發生錯誤：{str(e)}")


# --- UI ---

st.title("🤝 合作規範制定系統 (Gemini 智慧大腦版)")
st.markdown("##### 透過匿名意見徵集與 Gemini AI 語意歸納，自動撰寫結構化的小組專屬核心公約。")
st.divider()

room = st.session_state.get("platform_room_code", "TEST_ROOM")
user = st.session_state.get("platform_user_name", "匿名組員")

col_left, col_right = st.columns([1, 1.2])

with col_left:
    st.subheader("📝 步驟 1：匿名核心公約徵集")
    st.caption("每位成員皆可自由表達期待，本區塊不會記錄提交者姓名。")

    with st.form("suggestion_form", clear_on_submit=True):
        raw_input = st.text_area(
            "對於小組合作的期待或底線：",
            placeholder="例如：群組訊息要在 2 小時內回覆、開會遲到要請飲料...",
        )
        submit_btn = st.form_submit_button("提交意見 (匿名)", use_container_width=True)

        if submit_btn:
            if not raw_input.strip():
                st.warning("⚠️ 請先輸入內容再點擊提交！")
            else:
                try:
                    validated_data = RuleSubmission(
                        room_code=room, user_name=user, content=raw_input.strip()
                    )
                    save_raw_suggestion(room, validated_data.content)
                    st.toast("✅ 匿名意見提交成功！", icon="📩")
                    st.rerun()
                except ValueError as e:
                    st.error(f"❌ 填寫不合規範：{e.errors()[0]['msg']}")

    st.divider()
    current_suggestions = get_raw_suggestions(room)
    st.metric(label="📥 目前房間已收集的原始意見總數", value=f"{len(current_suggestions)} 則")

    if current_suggestions:
        with st.expander("👀 查看目前已收集的原始意見 (匿名清單)"):
            for s in current_suggestions:
                st.markdown(f"• {s}")

with col_right:
    st.subheader("🤖 步驟 2：Gemini 智慧整合與背書區")
    st.caption("點擊下方按鈕，Gemini 大模型將自動對所有人提交的散亂意見進行理解、去重、語意精修與條文化撰寫。")

    if st.button("✨ 啟動 Gemini 大腦進行公約精修", type="primary", use_container_width=True):
        with st.spinner("🧠 Gemini 正在精讀條文、梳理邏輯並撰寫標準公約中... 請稍候"):
            run_gemini_integration(room)

    with st.container(border=True):
        st.markdown("##### 📥 公約草案背書區 (Gemini 精修狀態)")

        with sqlite3.connect(DB_FILE) as conn:
            df_display = pd.read_sql_query(
                "SELECT category AS '規範類別', rule_text AS '核心標準條文' FROM cluster_rules WHERE room_code = ?",
                conn,
                params=(room,),
            )

        if df_display.empty:
            st.info("💡 目前背書區尚無條文。請先在左側收集足夠意見（至少 2 則），並點擊上方按鈕啟動 Gemini 整合。")
        else:
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            st.caption("ℹ️ 後續步驟：小組成員可針對上述 AI 歸納出的標準條文進行討論與投票背書。")

st.divider()

# --- Step 3: Voting ---

st.header("🗳️ 步驟 3：草案二次背書與參數衝突調節")
st.markdown("##### 針對 Gemini 生成的草案進行表態。若遇到「回覆時間」或「罰則數值」等參數，請選擇你的偏好選項。")

with sqlite3.connect(DB_FILE) as conn:
    df_rules = pd.read_sql_query(
        "SELECT rowid, category, rule_text FROM cluster_rules WHERE room_code = ?",
        conn,
        params=(room,),
    )

if df_rules.empty:
    st.info("💡 尚無公約草案可供投票。請先執行步驟 2 生成 Gemini 公約草案。")
else:
    with st.form("voting_form"):
        st.markdown(f"👤 **目前投票操作者：`{user}`**")
        current_votes = {}

        for idx, row in df_rules.iterrows():
            rule_id = int(row["rowid"])

            with st.container(border=True):
                st.markdown(f"### 【{row['category']}】")
                st.info(f"📜 {row['rule_text']}")

                has_param_conflict = any(
                    kw in row["rule_text"] for kw in ["小時", "分鐘", "天", "元", "飲料"]
                )

                col_v1, col_v2 = st.columns([1, 2])

                with col_v1:
                    vote_decision = st.radio(
                        "你的態度：",
                        ["支持 (Approve)", "不可行 (Reject)"],
                        key=f"dec_{rule_id}",
                        horizontal=True,
                    )

                chosen_param = "無參數"
                with col_v2:
                    if has_param_conflict and vote_decision == "支持 (Approve)":
                        if "小時" in row["rule_text"] or "回覆" in row["rule_text"]:
                            options = ["1 小時內", "2 小時內", "4 小時內 (半天)", "12 小時內 (隔天)"]
                        elif "飲料" in row["rule_text"] or "罰" in row["rule_text"]:
                            options = ["請喝純茶 ($35)", "請喝鮮奶茶 ($60)", "請喝星巴克 ($150)", "純警告不罰錢"]
                        else:
                            options = ["方案 A (嚴格執行)", "方案 B (中度彈性)", "方案 C (寬鬆處理)"]

                        chosen_param = st.radio(
                            "⚖️ 你偏好的「具體參數標準」是？",
                            options,
                            key=f"param_{rule_id}",
                            horizontal=True,
                        )

                current_votes[rule_id] = {"type": vote_decision, "param": chosen_param}

        submit_votes_btn = st.form_submit_button(
            "💾 遞交並同步我的公約投票數據", use_container_width=True
        )

        if submit_votes_btn:
            for r_id, v_data in current_votes.items():
                submit_vote(room, r_id, user, v_data["type"], v_data["param"])
            st.toast("🎉 你的背書與參數權重已成功同步！", icon="📊")
            st.rerun()

    # --- Step 4: Decision dashboard ---
    st.divider()
    st.header("📊 步驟 4：小組公約即時決策看板")
    st.markdown("##### 透過 Pandas 後端矩陣即時計算「絕對支持率」與「衝突參數最高得票」，自動分流公約狀態。")

    with sqlite3.connect(DB_FILE) as conn:
        df_raw_votes = pd.read_sql_query(
            "SELECT rule_rowid, vote_type, preferred_param FROM rule_votes WHERE room_code = ?",
            conn,
            params=(room,),
        )

    if df_raw_votes.empty:
        st.warning("⏳ 目前尚無任何組員遞交投票數據，無法計算共識門檻。")
    else:
        df_raw_votes["is_approve"] = df_raw_votes["vote_type"] == "支持 (Approve)"

        stats = (
            df_raw_votes.groupby("rule_rowid")
            .agg(total_votes=("vote_type", "count"), approve_count=("is_approve", "sum"))
            .reset_index()
        )
        stats["approve_rate"] = (stats["approve_count"] / stats["total_votes"]) * 100

        def get_best_param(group):
            valid_params = group[group["preferred_param"] != "無參數"]
            if valid_params.empty:
                return "依草案原文執行"
            return valid_params["preferred_param"].value_counts().idxmax()

        best_params = df_raw_votes.groupby("rule_rowid").apply(get_best_param).reset_index()
        best_params.columns = ["rule_rowid", "final_decision_param"]

        df_analysis = df_rules.merge(stats, left_on="rowid", right_on="rule_rowid", how="left")
        df_analysis = df_analysis.merge(best_params, on="rule_rowid", how="left")
        df_analysis["approve_rate"] = df_analysis["approve_rate"].fillna(0.0)
        df_analysis["final_decision_param"] = df_analysis["final_decision_param"].fillna("尚未決定")

        df_active = df_analysis[df_analysis["approve_rate"] >= 50.0]
        df_backlog = df_analysis[df_analysis["approve_rate"] < 50.0]

        col_active, col_backlog = st.columns(2)

        with col_active:
            st.markdown("### 🟢 正式生效公約區 (`Active`)")
            st.caption("以下條目已跨越 50% 共識門檻，將作為小組專案執行的最高指導原則。")

            if df_active.empty:
                st.info("暫無任何條文通過 50% 門檻，團隊仍需努力凝聚共識！")
            else:
                for _, r in df_active.iterrows():
                    with st.container(border=True):
                        st.markdown(f"#### ✅ {r['category']}")
                        st.markdown(f"**核心公約：** {r['rule_text']}")
                        st.markdown(f"⚙️ **團隊協調決議標準：** :green[{r['final_decision_param']}]")
                        st.progress(int(r["approve_rate"]) / 100)
                        st.caption(
                            f"共識支持率：**{r['approve_rate']:.1f}%** ({int(r['approve_count'])}/{int(r['total_votes'])} 票)"
                        )

        with col_backlog:
            st.markdown("### 🟡 爭議待議保留區 (`Pending`)")
            st.caption("支持率未過半、或組員存在重大分歧的條款。請團隊召開實體會議進行實時修正。")

            if df_backlog.empty:
                st.success("✨ 太棒了！目前沒有任何一條公約存在爭議待議。")
            else:
                for _, r in df_backlog.iterrows():
                    with st.container(border=True):
                        st.markdown(f"#### ⚠️ {r['category']} (存在異議)")
                        st.markdown(f"**草案原文：** {r['rule_text']}")
                        st.markdown("🚨 **當前狀態：** :red[支持率過低，暫不生效。需要重啟談判。]")
                        st.progress(int(r["approve_rate"]) / 100)
                        st.caption(
                            f"當前支持率：**{r['approve_rate']:.1f}%** ({int(r['approve_count'])}/{int(r['total_votes'])} 票)"
                        )
