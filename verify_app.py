import streamlit as st
import json
from enum import Enum
from string import Template

# Hardcoded location for survey vairables json file
DATA_FILE = "survey_vars.json"
# Initial data index to display
START_INDEX = 0
BROWSER_TITLE = "CLPS Codebook Browser"
TITLE = "Canadian Legal Problems Survey Codebook Browser"
INTRO = (
    "The [Canadian Legal Problems Survey (CLPS)]"
    "(https://www.justice.gc.ca/eng/rp-pr/jr/survey-enquete.html)"
    " is a national survey of Canadians' experiences with the justice system,"
    " most recently conducted by Statistics Canada in 2021."
    "\n\n"
    " Data from the survey is provided by Statistics Canada via a"
    " [Public Use Microdata File]"
    "(https://www150.statcan.gc.ca/n1/pub/35-25-0002/352500022022001-eng.htm)."
    " The provided data includes a codebook containing information about"
    " survey variables in PDF format that is not readily machine readable."
    "\n\n"
    " This app displays data extracted from the PDF codebook,"
    " allowing browsing or verification of the data."
    " Please see the "
    " [GitHub repo](https://github.com/andrewKOwong/clps_survey_vars)"
    " and an accompanying"
    " [blogpost](https://mixedconclusions.com/blog/clps_survey_vars/),"
    " as well as a [related dashboard]"
    "(https://clps-data.streamlit.app/) for the main CLPS dataset."
    "\n\n"
    "Click below to download the data as a JSON file."
)

# HTML template for right-aligned text
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


def generate_format_func(data: list) -> callable:
    """Returned func maps variable names to variable name plus concept string.

    E.g. {'PUMFID': 'Randomly generated sequence number ...', ...}
    """
    lookup = {}
    for q in data:
        lookup.update({q[H.variable_name.name]: q[H.concept.name]})

    def out(var_name: str) -> str:
        return f"{var_name} - {lookup[var_name]}"

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
    st.set_page_config(page_title=BROWSER_TITLE)
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
        st.header(TITLE)
        st.write(INTRO)
        # Download option for the data file
        st.write('\n\n')
        with open(DATA_FILE) as f:
            st.download_button("Download JSON", f, DATA_FILE)

    # Variable selection at the top of the page.
    selected_var = st.selectbox(
        'Choose a variable.',
        var_index.keys(),
        format_func=generate_format_func(data),
        on_change=on_select_box,
        key='select_box'
        )

    st.write('\n\n')
    # Set up a placeholder for extra previous next buttons at the top
    top_buttons = st.container()

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
                text = f"{q[H.total.name][h.name]}"
                # Commas for freq/weighted freq display
                if h in headings_freq:
                    text = f"{int(q[H.total.name][h.name]):,}"
                bot[i].markdown(
                    right_aligned.substitute(
                        text=text), unsafe_allow_html=True)

            # Disclaimer
            st.write("\n\n")
            st.write(
                "*Note: "
                " Totals are extracted from the codebook,"
                " and may not "
                "add up due to rounding (off by up to 1 for weighted "
                "frequency and up to 0.2% for percent).*")

    # Centred buttons appearing below the main question data
    st.write("\n\n")
    _, mid, _ = st.columns([1, 1, 1])
    prev_col, next_col = mid.columns(2)

    # Draw prev/next buttons, unless at beginning or end of list
    if st.session_state.current_var_index > 0:
        prev_col.button(
            "Previous", on_click=on_prev_button, key='prev_bottom')
    if st.session_state.current_var_index < st.session_state.max_var_index:
        next_col.button(
            "Next", on_click=on_next_button, key='next_bottom')

    # Also draw prev/next buttons at the top
    _, mid, _ = top_buttons.columns([1, 1, 1])
    prev_col, next_col = mid.columns(2)
    if st.session_state.current_var_index > 0:
        prev_col.button(
            "Previous", on_click=on_prev_button, key='prev_top')
    if st.session_state.current_var_index < st.session_state.max_var_index:
        next_col.button(
            "Next", on_click=on_next_button, key='next_top')
    top_buttons.write("\n")
