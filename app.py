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

# Modules whose names collide between the two packages
SHARED_NAMES = ("database", "utils", "optimizer")


def load_module(name, path, extra_path):
    # Remove conflicting cached modules from the other package
    for conflicting in SHARED_NAMES:
        sys.modules.pop(conflicting, None)
    # Remove any sibling package path so this package's modules win
    sys.path[:] = [p for p in sys.path if p not in (
        os.path.join(base, "consensus"),
        os.path.join(base, "division"),
    )]
    sys.path.insert(0, extra_path)

    # Always re-exec so a previously failed/cached module gets replaced
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(name, None)
        raise
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
