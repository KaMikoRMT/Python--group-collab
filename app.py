import streamlit as st

pg = st.navigation([
    st.Page("consensus/app.py", title="共識建立", icon="🌱"),
    st.Page("division/app.py", title="任務分工", icon="⚙️"),
])
pg.run()
