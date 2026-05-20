import streamlit as st
import sys
import os
import importlib.util

import rooms_db

st.set_page_config(
    page_title="小組合作輔助系統",
    page_icon="🤝",
    layout="wide",
)

# Silently ignore any subsequent set_page_config calls from page modules
st.set_page_config = lambda *a, **k: None

base = os.path.dirname(os.path.abspath(__file__))

# Modules whose names collide between the two packages
SHARED_NAMES = ("database", "utils", "optimizer")


def load_module(name, path, extra_path=None):
    for conflicting in SHARED_NAMES:
        sys.modules.pop(conflicting, None)
    if extra_path:
        sys.path[:] = [p for p in sys.path if p not in (
            os.path.join(base, "consensus"),
            os.path.join(base, "division"),
        )]
        sys.path.insert(0, extra_path)

    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return mod


rooms_db.init_platform_db()

# Init session state for platform room
if "platform_room_code" not in st.session_state:
    st.session_state.platform_room_code = None
if "platform_user_name" not in st.session_state:
    st.session_state.platform_user_name = None

# ==========================================
# 未登入 → 顯示大廳
# ==========================================
if st.session_state.platform_room_code is None:
    st.title("🤝 歡迎來到小組合作輔助系統")
    st.markdown("建立或加入房間後，即可使用所有功能模組（共識建立、任務分工、時間整合、合作規範制定）。")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🆕 創建新房間")
        host_name = st.text_input("你的暱稱", key="host_name")
        if st.button("創建房間", type="primary", use_container_width=True):
            if host_name.strip() == "":
                st.error("請輸入暱稱！")
            else:
                new_code = rooms_db.create_platform_room()
                st.session_state.platform_room_code = new_code
                st.session_state.platform_user_name = host_name.strip()
                st.rerun()

    with col2:
        st.subheader("🔑 加入現有房間")
        join_name = st.text_input("你的暱稱", key="join_name")
        room_input = st.text_input("輸入 6 位數 Room Code")
        if st.button("加入房間", use_container_width=True):
            if join_name.strip() == "" or room_input.strip() == "":
                st.error("請完整填寫暱稱與房間代碼！")
            elif rooms_db.verify_platform_room(room_input):
                st.session_state.platform_room_code = room_input.upper()
                st.session_state.platform_user_name = join_name.strip()
                st.rerun()
            else:
                st.error("找不到此房間，請確認代碼是否正確！")

# ==========================================
# 已登入 → 顯示主功能
# ==========================================
else:
    # 頂部資訊列
    info_col, refresh_col = st.columns([3, 1])
    with info_col:
        st.info(
            f"👤 用戶：**{st.session_state.platform_user_name}** ｜ "
            f"🏠 當前房間：**{st.session_state.platform_room_code}**"
        )
    with refresh_col:
        if st.button("🔄 刷新同步最新資料", use_container_width=True):
            st.rerun()

    # 側邊欄導航
    with st.sidebar:
        st.title("🤝 小組合作輔助系統")
        st.divider()
        page = st.radio(
            "選擇功能模組",
            ["🌱 共識建立", "⚙️ 任務分工", "🕒 時間整合", "📋 合作規範制定"],
            label_visibility="collapsed",
        )
        st.divider()
        if st.button("🚪 離開房間", use_container_width=True):
            st.session_state.platform_room_code = None
            st.session_state.platform_user_name = None
            st.rerun()

    if page == "🌱 共識建立":
        mod = load_module(
            "consensus_app",
            os.path.join(base, "consensus", "app.py"),
            os.path.join(base, "consensus"),
        )
        mod.main()

    elif page == "⚙️ 任務分工":
        mod = load_module(
            "division_app",
            os.path.join(base, "division", "app.py"),
            os.path.join(base, "division"),
        )
        mod.main()

    elif page == "🕒 時間整合":
        load_module(
            "time_integration",
            os.path.join(base, "views", "time_integration.py"),
        )

    else:
        load_module(
            "collaboration_rules",
            os.path.join(base, "views", "collaboration_rules.py"),
        )
