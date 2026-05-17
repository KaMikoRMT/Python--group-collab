import streamlit as st
import sys
import os
import importlib.util

st.set_page_config(
    page_title="小組合作輔助系統",
    page_icon="🤝",
    layout="wide",
)

# Silently ignore any subsequent set_page_config calls from page modules
st.set_page_config = lambda *a, **k: None

base = os.path.dirname(os.path.abspath(__file__))


def load_module(name, path, extra_path):
    if name not in sys.modules:
        if extra_path not in sys.path:
            sys.path.insert(0, extra_path)
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[name]


with st.sidebar:
    st.title("🤝 小組合作輔助系統")
    st.divider()
    page = st.radio(
        "選擇功能模組",
        ["🌱 共識建立", "⚙️ 任務分工"],
        label_visibility="collapsed",
    )

if page == "🌱 共識建立":
    mod = load_module(
        "consensus_app",
        os.path.join(base, "consensus", "app.py"),
        os.path.join(base, "consensus"),
    )
    mod.main()
else:
    mod = load_module(
        "division_app",
        os.path.join(base, "division", "app.py"),
        os.path.join(base, "division"),
    )
    mod.main()
