import html

import streamlit as st

_CSS = """
<style>
.hero {
  background: linear-gradient(100deg, #C62828 0%, #E65100 100%);
  border-bottom: 6px solid #FFC107;
  border-radius: 16px;
  padding: 1.5rem 1.8rem;
  margin-bottom: 1rem;
}
.hero h1 {
  color: #FFFFFF;
  margin: 0;
  padding: 0;
  font-size: clamp(1.5rem, 4vw, 2.4rem);
  line-height: 1.2;
}
.hero p {
  color: #FFF8E1;
  margin: 0.4rem 0 0 0;
  font-size: 1.05rem;
}
div[data-testid="stImage"] img { border-radius: 10px; }
.stButton > button:hover { border-color: #E65100; color: #E65100; }
.stButton > button[kind="primary"]:hover {
  background-color: #E65100; border-color: #E65100; color: #FFFFFF;
}
</style>
"""


def apply_theme():
    st.markdown(_CSS, unsafe_allow_html=True)


def banner(title, subtitle=""):
    st.markdown(
        f'<div class="hero"><h1>{html.escape(title)}</h1>'
        f"<p>{html.escape(subtitle)}</p></div>",
        unsafe_allow_html=True,
    )