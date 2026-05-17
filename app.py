import streamlit as st
import sys
import os
import importlib.util

st.set_page_config(
    page_title="小組合作輔助系統",
    page_icon="🤝",
    layout="wide",
)

base = os.path.dirname(os.path.abspath(__file__))


def load_module(name, path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


with st.sidebar:
    st.title("🤝 小組合作輔助系統")
    st.divider()
    page = st.radio(
        "選擇功能模組",
        ["🌱 共識建立", "⚙️ 任務分工"],
        label_visibility="collapsed",
    )

if page == "🌱 共識建立":
    sys.path.insert(0, os.path.join(base, "consensus"))
    mod = load_module("consensus_app", os.path.join(base, "consensus", "app.py"))
    mod.main()
else:
    sys.path.insert(0, os.path.join(base, "division"))
    mod = load_module("division_app", os.path.join(base, "division", "app.py"))
    mod.main()
