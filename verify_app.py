import streamlit as st
import json
import argparse
from enum import Enum
from string import Template

DATA_FILE = "survey_vars_mini.json"

class Heading(Enum):
    """Enum for heading strs for display."""
    variable_name = 'Variable Name'
    length = 'Length'
    position = 'Position'
    question_name = 'Question Name'
    concept = 'Concept'
    question_text = 'Question Text'
    universe = 'Universe'
    note = 'Note'
    source = 'Source'
    answer_categories = 'Answer Categories'
    code = 'Code'
    frequency = 'Frequency'
    weighted_frequency = 'Weighted Frequency'
    percent = '%'
    total = 'Total'


# Convenience variable for Heading enum
H = Heading

def generate_variable_index(data: list):
    out = {}
    for i, q in enumerate(data):
        out.update({q[H.variable_name.name]: i})
    return out


# template for right aligned text
right_aligned = Template("<div style='text-align: right'>$text</div>")

if __name__ == "__main__":
    with open(DATA_FILE) as f:
        data = json.load(f)

    var_index = generate_variable_index(data)

    with st.sidebar:
        st.header("Canadian Legal Problems Survey Variable Verification")
        st.write("Introduction and description.")
        selected_var = st.selectbox(
            'Choose a variable.',
             var_index.keys(),
             index=1
             )

    # The current question to be displayed
    q = data[var_index[selected_var]]
    # The top row of metadata
    top1, top2, top3 = st.columns(3)
    top1.metric(H.variable_name.value, q[H.variable_name.name])
    top2.metric(H.length.value, q[H.length.name])
    top3.metric(H.position.value, q[H.position.name])
    # The middle section of metadata
    for h in [H.question_name, H.concept, H.question_text,
              H.universe, H.note, H.source]:
        mid1, mid2 = st.columns([2, 5], gap='medium')
        mid1.markdown(f"**{h.value}**")
        mid2.markdown(r'\-\-\-' if q[h.name] == '' else rf"{q[h.name]}")

    if q.get(H.answer_categories.name):
        st.write("\n\n")
        # Column widths
        widths = [2, 1, 1, 2, 0.5]
        # Headings
        headings = [H.answer_categories, H.code, H.frequency,
                    H.weighted_frequency, H.percent]
        headings_right = [H.frequency, H.weighted_frequency, H.percent]
        headings_freq = [H.frequency, H.weighted_frequency]
        bot = st.columns(widths, gap='small')
        for j, h in enumerate(headings):
            # Markdown emphasis doesn't work in middle of html,
            # so use all html for consistency
            text = f"<b>{h.value}</b>"
            if h in headings_right:
                text = right_aligned.substitute(text=text)
            bot[j].markdown(text, unsafe_allow_html=True)
        # Values
        for i, e in enumerate(q[H.answer_categories.name]):
            bot = st.columns(widths, gap='small')
            for j, h in enumerate(headings):
                text = f"{q[h.name][i]}"
                if h in headings_freq:
                    text = f"{int(q[h.name][i]):,}"
                if h in headings_right:
                    text = right_aligned.substitute(text=text)
                bot[j].markdown(text, unsafe_allow_html=True)
        # Total
        st.write("\n")
        bot = st.columns(widths, gap='small')
        bot[0].markdown(f"**{H.total.value}**")
        for i, h in zip(range(2, 5), headings_right):
            bot[i].markdown(
                right_aligned.substitute(text=f"{q[H.total.name][h.name]}"),
                unsafe_allow_html=True)

        # Disclaimer
        st.write("\n\n")
        st.write("*Note: totals are extracted from the codebook, and may not "
                 "add up due to rounding (off by up to 1 for weighted "
                 "frequency and up to 0.2% for percent).*")
