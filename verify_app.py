import streamlit as st
import json
from enum import Enum
from string import Template

# Hardcoded location for survey vairables json file
DATA_FILE = "survey_vars_mini.json"
# Initial data index to display
START_INDEX = 0
# Template for right aligned text
right_aligned = Template("<div style='text-align: right'>$text</div>")


# Enum to track heading text
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


@st.cache_data
def load_data(data_file: str) -> list:
    """Returns survey variables json data."""
    with open(data_file) as f:
        data = json.load(f)
    return data


@st.cache_data
def generate_variable_index(data: list) -> dict:
    """Returns a dict matching variable names to their index in data.

    E.g. {'PUMFID': 0, 'PHHP10P': 1, ...}
    """
    out = {}
    for i, q in enumerate(data):
        out.update({q[H.variable_name.name]: i})
    return out


def on_select_box():
    """Callback for select box change."""
    st.session_state.current_var_index = \
        var_index[st.session_state.select_box]


def on_prev_button():
    """Callback for previous button click."""
    if st.session_state.current_var_index > 0:
        st.session_state.current_var_index -= 1


def on_next_button():
    """Callback for next button click."""
    if st.session_state.current_var_index < \
            st.session_state.max_var_index:
        st.session_state.current_var_index += 1


if __name__ == "__main__":
    # Load the data
    data = load_data(DATA_FILE)
    # Generate the variable index, a dict matching
    # variable names to their index in the data list
    var_index = generate_variable_index(data)
    # Initialize session state.
    # Variable index tracks the current variable to display by its index
    # in the data list.
    if 'current_var_index' not in st.session_state:
        st.session_state.current_var_index = START_INDEX
    # Max variable index tracks the last variable in the data list.
    # This is not expected to change.
    if 'max_var_index' not in st.session_state:
        st.session_state.max_var_index = len(var_index) - 1
    # Get select box state based on the current variable index
    st.session_state.select_box = \
        data[st.session_state.current_var_index][H.variable_name.name]
    # Set up the sidebar, with a select box for variable selection
    with st.sidebar:
        st.header("Canadian Legal Problems Survey Variable Verification")
        st.write("Introduction and description.")
        selected_var = st.selectbox(
            'Choose a variable.',
            var_index.keys(),
            on_change=on_select_box,
            key='select_box'
            )

    # Populate the data fields.
    # Container is unnecessary, but makes the code more readable by indent.
    with st.container():
        # The current question to be displayed
        q = data[st.session_state.current_var_index]
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

        # The bottom section of metadata, containing the answer categories
        # etc. in table-like format.
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
                    # Escape $ to prevent LaTeX trigger
                    text = text.replace('$', r'\$')
                    bot[j].markdown(text, unsafe_allow_html=True)
            # Total
            st.write("\n")
            bot = st.columns(widths, gap='small')
            bot[0].markdown(f"**{H.total.value}**")
            for i, h in zip(range(2, 5), headings_right):
                bot[i].markdown(
                    right_aligned.substitute(
                        text=f"{q[H.total.name][h.name]}"),
                    unsafe_allow_html=True)

            # Disclaimer
            st.write("\n\n")
            st.write("*Note: totals are extracted from the codebook,"
                     " and may not "
                     "add up due to rounding (off by up to 1 for weighted "
                     "frequency and up to 0.2% for percent).*")

    # Centred buttons appearing below the main question data
    st.write("\n\n")
    _, mid, _ = st.columns([1, 1, 1])
    prev_col, next_col = mid.columns(2)

    # Draw prev/next buttons, unless at beginning or end of list
    if st.session_state.current_var_index > 0:
        prev = prev_col.button("Previous", on_click=on_prev_button)
    if st.session_state.current_var_index < st.session_state.max_var_index:
        next = next_col.button("Next", on_click=on_next_button)
