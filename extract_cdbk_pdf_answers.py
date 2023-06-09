import argparse
from pathlib import Path
from bs4 import BeautifulSoup, Tag
from dataclasses import dataclass, field
from enum import Enum
from copy import deepcopy
import re
import json
import logging


class Field(Enum):
    """Data fields for questions.

    Field names can be used as dict keys or col names.
    Field values are used to extract data out of the original data.
    """
    variable_name = 'Variable Name:'
    length = 'Length:'
    position = 'Position:'
    question_name = 'Question Name:'
    concept = 'Concept:'
    question_text = 'Question Text:'
    universe = 'Universe:'
    note = 'Note:'
    source = 'Source:'
    answer_categories = 'Answer Categories'
    code = 'Code'
    frequency = 'Frequency'
    weighted_frequency = 'Weighted Frequency'
    percent = '%'
    total = 'Total'


START_PAGE = 9  # First data page
END_PAGE = 126  # Last data page (inclusive)

# These are known characters that the pdf extractor erroneously extracts.
FAULTY_CHARACTER_MAPPER = {
    'ﬁ': 'fi',
    "’": "'"
}


# Shim this in between steps of the pipeline during debugging
# to write out an html file for inspection.
def debug_shim(soup: BeautifulSoup, out: str = 'debug.html') -> None:
    with open(out, 'w') as f:
        f.write(soup.prettify())


# Use this to save the lists of data during extraction for debugging.
def debug_listed_data(data: list, out: str) -> None:
    with open(out, 'w') as f:
        for e in data:
            f.write(str(e))
            f.write('\n')


# Parse args
# Input file is the html output from running pdf2txt.py
parser = argparse.ArgumentParser()
parser.add_argument(
    'cdbk_html',
    help="HTML output from running e.g. "
         "`pdf2txt.py codebook.pdf -o codebook.html --output_type html`"
)
# Output file
parser.add_argument(
    '-o',
    '--output',
    help="Output file name. Default is 'survey_vars.json'.",
    default="survey_vars.json"
)
parser.add_argument(
    '-d',
    '--debug',
    help="Debug mode. Writes out intermediate files "
         "for inspection to current directory.",
    action='store_true'
)
args = parser.parse_args()

# Set debug mode and debug logging
debug_mode = args.debug
logging.basicConfig(level=logging.DEBUG if debug_mode else logging.INFO)

# Open and extract html
p = Path(args.cdbk_html)
with p.open() as f:
    soup = BeautifulSoup(f, 'html.parser')
soup = soup.body.extract()

# Regenerating just the data pages
# by finding all siblings of the start div,
# and iterating through and appending until we get the div that
# is right after the ending data page,
# then reconstituting the strings into another soup object.
# start_div is a div whose child is an anchor for the start of page 9
start_div = soup.select(f'a[name="{START_PAGE}"]')[0].parent
html_doc = str(start_div)
for tag in start_div.next_siblings:
    if (isinstance(tag, Tag)
            and tag.a is not None
            and tag.a['name'] == str(END_PAGE + 1)):
        break
    else:
        html_doc += str(tag)
soup = BeautifulSoup(html_doc, 'html.parser')


# Filter out all horizontal lines that aren't dividers for the variables.
# Helper filter func.
def is_non_divider_hline(tag: Tag) -> bool:
    """Filter function for non-divider hline spans.

    Dividers are horizontal lines drawn between each data variable.
    Also checks if the span is not a text containing span.

    Args:
        tag: BeautifulSoup html element.

    Returns:
        True if the span element is not a divider.
    """
    DIVIDER_LEFT_MATCH = 'left:36px'
    DIVIDER_HEIGHT_MATCH = 'height:0px'
    FF_MATCH = 'font-family'
    # Consider only span tags
    if tag.name != 'span':
        return False
    # Style attribute of the span tag
    style = tag['style']
    # Text fields contain a font family style, so use to exclude
    if FF_MATCH in style:
        return False
    # Exclude dividers
    elif DIVIDER_LEFT_MATCH in style and DIVIDER_HEIGHT_MATCH in style:
        return False
    else:
        return True


# Run loop to extract all the non-hlines.
for tag in [e for e in soup.children]:
    if isinstance(tag, Tag) and is_non_divider_hline(tag):
        tag.extract()

# Filter out header and footers
for tag in soup.children:
    if (isinstance(tag, Tag)
            and tag.span is not None
            and ("CLPS 2021 - Data Dictionary" in tag.span.text
                 or "Totals may not add up due to rounding" in tag.span.text
                 or re.search(r"Page.*\-", tag.span.text) is not None)):
        tag.extract()

# Remove page divs
for tag in soup.children:
    if (isinstance(tag, Tag) and tag.a is not None):
        tag.extract()


# For the remaining elements, pull out text and left/top info
# and place into a list of Element dataclass objects.
@dataclass
class Element:
    TEXT_TYPE = 'text'
    DIVIDER_TYPE = 'divider'
    elem_type: str
    left: int  # Left position (pos) of the original html element
    top: int  # Top pos of the original html element
    width: int  # Width of the original html element
    height: int  # Height of the original html element
    right: int = field(init=False)  # Right pos of the original html element
    bottom: int = field(init=False)  # Bottom pos of the original html element
    text: str = ''

    def __post_init__(self):
        # Convert to ints
        self.left = int(self.left)
        self.top = int(self.top)
        self.width = int(self.width)
        self.height = int(self.height)
        # Calculate right and bottom positions
        self.right = self.left + self.width
        self.bottom = self.top + self.height


# Create Element objects with loop.
elements = []
for tag in soup.children:
    # Check tags to see if they have attributes,
    # and if they have left and top styles.
    if isinstance(tag, Tag):
        try:
            style = tag['style']
        except AttributeError as e:
            raise AttributeError(
                f"Tag did not have a style attribute."
                f"\n\nTag contents:\n\n"
                f"{str(tag)}"
                ) from e
        # Left and top specify the corner of the box for the element.
        # Get 1 or more digits between left/top: and px;
        left = re.search(r"(?<=left:)\d+?(?=px;)", style).group(0)
        top = re.search(r"(?<=top:)\d+?(?=px;)", style).group(0)
        width = re.search(r"(?<=width:)\d+?(?=px;)", style).group(0)
        height = re.search(r"(?<=height:)\d+?(?=px;)", style).group(0)
        if left is None or top is None or width is None or height is None:
            raise ValueError(
                f"Did not find a left/top/width/height value."
                f"\n\nTag contents:\n"
                f"{str(tag)}"
                f"\n\nStyle attribute contents:\n"
                f"{str(style)}"
            )
        # Element type distinguishes
        # top level divs that have text fields
        # and top level spans that are dividers
        match tag.name:
            case 'div':
                type_val = Element.TEXT_TYPE
            case 'span':
                type_val = Element.DIVIDER_TYPE
            case _:
                raise ValueError("Unexpected non div/span element.")
        elements.append(Element(type_val, left, top, width, height, tag.text))


# Sorted elements will be in top to bottom order,
# then left to right order for ties.
elements = sorted(elements, key=lambda e: int(e.left))
elements = sorted(elements, key=lambda e: int(e.top))

# Remove leading/trailing whitespace from text fields
for e in elements:
    e.text = e.text.strip()

if debug_mode:
    debug_elements_fp = 'debug_elements.txt'
    debug_listed_data(elements, debug_elements_fp)
    logging.debug(f"Elements written to {debug_elements_fp}.")


# Group the elements into units corresponding
# to each question. These are separated by divider elements.
def group_elements(elements: list[Element]) -> list:
    """Group elements into units corresponding to question.

    Args:
        elements: a list of Elements.
    Returns:
        A list of lists of Elements, with each sublist corresponding
        to a questionnaire question, as separated by divider Elements.
    """
    units = []
    current_unit = []
    for e in elements:
        # Complete a unit when encountering a divider
        if e.elem_type == Element.DIVIDER_TYPE:
            units.append(current_unit)
            current_unit = []
        # Otherwise add to current unit
        else:
            current_unit.append(e)
    return units


units = group_elements(elements)

if debug_mode:
    debug_units_fp = 'debug_units.txt'
    debug_listed_data(units, debug_units_fp)
    logging.debug(f"Units written to {debug_units_fp}.")


# The following is helper funcs,
# followed by extraction funcs (starting with get_variable_name)
# for getting each data field.
def split_and_strip(s: str, sep: str = '\n') -> list:
    """Split a string on newlines and strip each element."""
    return [e.strip() for e in s.split(sep=sep)]


def replace_characters(s: str, mapper: dict) -> str:
    """Replace characters in a string with other characters.

    Useful for weird characters like ligatures.

    Args:
        s: the string to replace characters in.
        mapper: a dict mapping `to_be_replace: replacement`.

    Returns:
        The string with the characters replaced.
    """
    for k, v in mapper.items():
        s = s.replace(k, v)
    return s


def replace_hyphenated_words(s: str) -> str:
    """Replace multiline hyphenated words from a string.

    Some words in the original text fields are hyphenated as they are broken
    at the end of line. The result after extraction and processing takes on
    the form: "wordpart1- wordpart2". This function runs a regex to find
    these words and remove the internal hyphen and space.
    """
    # Finds '- ' between two lowercase letters. Must be lower case
    # to avoid a few cases where the question concept has e.g. "you- Bought".
    # Lower case requirement disappears if only running on question text.
    return re.sub(r"(?<=[a-z])- (?=[a-z])", "", s)


def get_elem_by_text(unit: list, text: str) -> Element:
    """Search a list of Elements for the first element with provided text."""
    for e in unit:
        if text in e.text:
            return e


def get_variable_name(unit: list, tol: int = 5) -> str:
    """Get variable name data.

    Args:
        unit: a list of Elements corresponding to a questionnaire question.
        tol: tolerance for finding variable name element.

    Returns:
        The variable name as a string.
    """
    # Set up triangulation boundaries
    left_elem = get_elem_by_text(unit, Field.variable_name.value)
    right_elem = get_elem_by_text(unit, Field.length.value)
    l, t = left_elem.left, left_elem.top
    r = right_elem.left
    out = []
    for e in unit:
        if (l < e.left < r) and (t - 5 < e.top < t + 5):
            out.append(e.text)
    # Should only find one element
    try:
        assert len(out) == 1
    except AssertionError:
        raise AssertionError(
            f"Found more than one element between "
            f"{l}, {r}, and within {tol}px of {t}."
            f"\nElements Founds:\n{out}"
            )
    return out[0]


def get_length(unit: list) -> str:
    """Get length data.

    Args:
        unit: a list of Elements corresponding to a questionnaire question.

    Returns:
        The length as a string.
    """
    return (get_elem_by_text(unit, Field.length.value)
            .text.split(':')[1].strip())


def get_position(unit: list) -> str:
    """Get position data.

    Args:
        unit: a list of Elements corresponding to a questionnaire question.

    Returns:
        The position as a string.
    """
    return (get_elem_by_text(unit, Field.position.value)
            .text.split(':')[1].strip())


def get_middle_section(
        unit: list,
        top: str,
        bottom: str,
        top_tol: int = 10,
        bottom_buffer: int = 10) -> str:
    """Helper funct for getting data from question through source fields.

    This is a func for getting individual data fields that sit in the same
    vertical column between the question name field down to the source field.

    It works by supplying the desired heading as top, and the next heading
    directly below as bottom. It then uses these headings to find the data
    fields that sit between vertically.

    Args:
        unit: a list of Elements corresponding to a questionnaire question.
        top: the actual heading value e.g. "Question Name:"
             of the desired data field.
        bottom: the heading value of the next data field below the desired
            field.
        top_tol: tolerance for finding top element.
        bottom_buffer: buffer above the bottom elements for finding elements
            between the top and bottom elements.

    Returns:
        The data as a string.
    """
    # Approximate position where text is expected to be,
    # with buffer in case of minor irregularities
    TEXT_LEFT_POS = 178
    TEXT_LEFT_BUFFER = 5
    # Left/right boundaries
    l, r = TEXT_LEFT_POS - TEXT_LEFT_BUFFER, TEXT_LEFT_POS + TEXT_LEFT_BUFFER
    # Get elements that are to the right of the top element
    # but above the bottom element, within tolerance/buffers.
    # Remember: top is a smaller number than bottom!
    t = get_elem_by_text(unit, top).top - top_tol  # top boundary
    b = get_elem_by_text(unit, bottom).top - bottom_buffer  # bottom boundary
    out = []
    for e in unit:
        if (t < e.top < b) and (l < e.left < r):
            out.append(e.text)

    # Join with spaces, replace ligatures etc., then remove
    # internal newlines and repeated whitespace, then rejoin.
    out = ' '.join(out)
    out = replace_characters(out, FAULTY_CHARACTER_MAPPER)
    out = ' '.join(split_and_strip(out, sep='\n'))
    # Remove multiline hyphenations
    out = replace_hyphenated_words(out)

    return out


def get_middle_section_broad(
        unit: list,
        top: str,
        bottom: str,
        top_tol: int = 10,
        bottom_buffer: int = 10) -> str:
    """Alternate version of get_middle_section.

    Questions ASTP20B,C,D,F,G have their question text field extracted
    into broken into left and right parts. For example, ASTP20B ends up having
    elements:
    'Only report the actions you took in Canada.\n      the dispute'
    '- Contacted the other party involved in'

    This is caused by the visual break from ' - ' in the middle of the line.

    The function is a modified version on `get_middle_section` that accounts
    for these issues. It should probably only be used for the question text
    field.

    Args:
        unit: a list of Elements corresponding to a questionnaire question.
        top: the actual heading value e.g. "Question Name:"
             of the desired data field.
        bottom: the heading value of the next data field below the desired
            field.
        top_tol: tolerance for finding top element.
        bottom_buffer: buffer above the bottom elements for finding elements
            between the top and bottom elements.

    Returns:
        The data as a string.
    """
    # Approximate position where text is expected to be,
    # with buffer in case of minor irregularities
    TEXT_LEFT_POS = 178
    TEXT_LEFT_BUFFER = 5
    # This position is somewhere in the middle-right of
    # the page, but good enough since we're using left boundaries to
    # find the elements.
    TEXT_RIGHT_POS = 567
    # Left/right boundaries
    left = TEXT_LEFT_POS - TEXT_LEFT_BUFFER
    right = TEXT_RIGHT_POS
    # Get elements that are to the right of the top element
    # but above the bottom element, within tolerance/buffers.
    # Remember: top is a smaller number than bottom!
    # Also within the left right boundaries
    t = get_elem_by_text(unit, top).top - top_tol  # top boundary
    b = get_elem_by_text(unit, bottom).top - bottom_buffer  # bottom boundary
    out = []
    for e in unit:
        if (t < e.top < b) and (left < e.left < right):
            out.append(e)

    # Break lines into multiple elements if they span multiple lines
    out_copy = deepcopy(out)
    for e in out_copy:
        if e.text.count('\n') > 0:
            # Remove the original element
            out.remove(e)
            # Add new elements for each line, adding buffer space for each
            # new line.
            for i, line in enumerate(e.text.split('\n')):
                out.append(Element(
                    elem_type=e.elem_type,
                    text=line.strip(),
                    top=e.top + (i * 10),
                    left=e.left,
                    width=e.width,
                    height=e.height,
                    ))

    # A priori, can't be certain that lines broken left-right
    # will have the exact same top position.
    # Thus, reset the top position of any elements that aren't aligned to the
    # left of the field to the closest element that aligned to the left.
    left_aligned_left_limit = TEXT_LEFT_POS - TEXT_LEFT_BUFFER
    left_aligned_right_limit = TEXT_LEFT_POS + TEXT_LEFT_BUFFER
    out_copy = deepcopy(out)
    for i, e in enumerate(out_copy):
        if not (left_aligned_left_limit < e.left < left_aligned_right_limit):
            # Find closest element that aligned to the left
            closest = min(out_copy, key=lambda x: abs(x.top - e.top))
            # Reset top position in original out list
            out[i].top = closest.top
    # Defensively re-sort so ascending by top, then by left
    out = sorted(out, key=lambda x: (x.top, x.left))
    # Get the text strings
    out = [e.text for e in out]
    # Join with spaces, replace ligatures etc., then remove
    # internal newlines and repeated whitespace, then rejoin.
    out = ' '.join(out)
    out = replace_characters(out, FAULTY_CHARACTER_MAPPER)
    out = ' '.join(split_and_strip(out, sep='\n'))
    # Remove multiline hyphenations
    out = replace_hyphenated_words(out)

    return out


def get_question_name(unit: list) -> str:
    """Get question name data.

    Args:
        unit: a list of Elements corresponding to a questionnaire question.

    Returns:
        The question name field as a string.
    """
    return get_middle_section(unit,
                              Field.question_name.value,
                              Field.concept.value)


def get_concept(unit: list) -> str:
    """Get concept data.

    Args:
        unit: a list of Elements corresponding to a questionnaire question.

    Returns:
        The concept field as a string.
    """
    return get_middle_section(unit,
                              Field.concept.value,
                              Field.question_text.value)


def get_question_text(unit: list) -> str:
    """Get question text data.

    Args:
        unit: a list of Elements corresponding to a questionnaire question.

    Returns:
        The question text field as a string.
    """
    return get_middle_section_broad(unit,
                                    Field.question_text.value,
                                    Field.universe.value)


def get_universe(unit: list) -> str:
    """Get universe data.

    Args:
        unit: a list of Elements corresponding to a questionnaire question.

    Returns:
        The universe field as a string.
    """
    return get_middle_section(unit,
                              Field.universe.value,
                              Field.note.value)


def get_note(unit: list) -> str:
    """Get question note data.

    Args:
        unit: a list of Elements corresponding to a questionnaire question.

    Returns:
        The note field as a string.
    """
    return get_middle_section(unit,
                              Field.note.value,
                              Field.source.value)


def get_source(unit: list) -> str:
    """Get source data.

    Args:
        unit: a list of Elements corresponding to a questionnaire question.

    Returns:
        The source field as a string.
    """
    return get_middle_section(unit,
                              Field.source.value,
                              Field.answer_categories.value)


class PageBreak:
    """Helper class to represent a page break.

    Insert into list of elements to indicate a page break.
    """
    def __len__(self):
        return 1


class CodeElementBreak:
    """Helper class to represent a break in the code elements.

    Insert into list of elements to indicate a break in the code elements.
    """
    def __len__(self):
        return 1


def flatten(lst: list) -> list:
    """Helper func for flattening a depth-2 nested lists."""
    out = []
    for e in lst:
        if isinstance(e, list):
            out.extend(e)
        else:
            out.append(e)
    return out


def get_answer_fields(unit: list[Element]) -> dict:
    """Get the answer fields from a unit.

    There are several problems that need to be addressed:
    - Answer fields may be split across multiple pages,
      resulting in more than one set of column headings.
      Occasionally, this occurs even within a single page.
      In either case, this results in columns being extracted as multiple
      elements.
    - Text in the answer categories column might be split
      across multiple lines. This results in the other columns containing
      a blank space, which results in those columns being extracted
      as multiple elements.
    - There is at least one case where text extraction resulted in
      a non-standard ligature character.

    Args:
        unit: A list of Elements corresponding to a single question.
            This unit should be pre-sorted by top position, then left position.

    Returns:
        A dict mapping column headings to data, including a extra key
        'total' for the total row.
    """
    # Abbreviated local variables keys and values for convenience
    # i.e. access keys/values with .name/.value
    ANS = Field.answer_categories
    CODE = Field.code
    FREQ = Field.frequency
    WEIGHTED = Field.weighted_frequency
    PERC = Field.percent
    TOTAL = Field.total
    # Position tolerance/buffer for elements in the same column
    POS_TOL = 10
    POS_BUFFER = 10
    # Hardcoded right position of frequency heading
    FREQ_RIGHT_POS = 386
    # Functions for converting strings to the correct type for total checking
    TOTAL_CHECK_TYPE_FUNCS = {FREQ.name: int,
                              WEIGHTED.name: int,
                              PERC.name: float}
    # Tolerance for total checking.
    # Frequencies should be exact, but weighted frequencies and percentages
    # may off from multiplying and rounding.
    TOTAL_TOLS = {FREQ.name: 0, WEIGHTED.name: 1, PERC.name: 0.2}

    out = {ANS.name: [],
           CODE.name: [],
           FREQ.name: [],
           WEIGHTED.name: [],
           PERC.name: []}

    # First, deal with the answer category and code columns.
    # We'll need to get the first heading, then get all the elements
    # in the same column.
    for heading in [ANS, CODE]:
        header_count = 0
        # Get the heading (units are presorted, so gets the first one)
        heading_elem = get_elem_by_text(unit, heading.value)
        # Get heading positioning
        top = heading_elem.top
        left = heading_elem.left
        right = heading_elem.right
        # Loop to get all elements in the same column.
        for e in unit:
            # Skip if an element is above the first heading.
            if e.top < top:
                continue
            # If there's a secondary heading, add a page break element.
            if (heading.value in e.text):
                if header_count == 0:
                    header_count += 1
                    continue
                else:
                    header_count += 1
                    out[heading.name].append(PageBreak())
                    continue
            match heading.value:
                # Answer categories are left aligned to their heading
                case ANS.value:
                    if left - POS_TOL < e.left < left + POS_TOL:
                        out[heading.name].append(split_and_strip(e.text))
                # Code values are right aligned to their heading
                case CODE.value:
                    if right - POS_TOL < e.right < right + POS_TOL:
                        out[heading.name].append(split_and_strip(e.text))
    # Since answer categories sometimes takes two lines, thus
    # breaking the corresponding code values into two elements,
    # insert a break to represent the end of a block of code elements,
    # provided that the next element is not a page break.
    code_out = []
    for i, e in enumerate(out[CODE.name]):
        if i > 0:
            if (not isinstance(e, PageBreak)
                    and not isinstance(out[CODE.name][i-1], PageBreak)):
                code_out.append(CodeElementBreak())
        code_out.append(e)
    # Place back into output and cleanup
    out[CODE.name] = code_out
    del code_out
    # Verify that the number of answer categories and code elements
    # are the same, by counting CodeElementBreaks as additional item.
    # (CodeElementBreaks and PageBreaks have __len__() == 1)
    try:
        a = sum([len(e) for e in out[ANS.name]])
    except TypeError:
        raise TypeError(f"Answer elements: {out[ANS.name]}")
    try:
        b = sum(len(e) for e in out[CODE.name])
    except TypeError:
        raise TypeError(f"Code elements: {out[CODE.name]}")
    try:
        assert a == b
    except AssertionError as e:
        raise AssertionError(
            f"Number of answer categories and code elements do not match."
            f"\nN uncorrected answer categories elements: {out[ANS.name]}"
            f"\nN code elements w/ breaks: {out[CODE.name]}"
        ) from e
    except Exception as e:
        raise Exception(
            f"Answer cats: {out[ANS.name]}"
            f"\nCode: {out[CODE.name]}"
        ) from e
    # Flatten the answer categories and code elements.
    out[ANS.name] = flatten(out[ANS.name])
    out[CODE.name] = flatten(out[CODE.name])
    # By going through zipped answers and codes, if we encounter a
    # CodeElementBreak, we know that the previous answer category
    # contains a line break, and we need to join the answer to the
    # preceding answer.
    merged = [[a, c] for a, c in zip(out[ANS.name], out[CODE.name])]
    ans_out = []
    code_out = []
    for i, (a, c) in enumerate(merged):
        # Check that PageBreaks line up, and skip them if so.
        if isinstance(a, PageBreak) or isinstance(c, PageBreak):
            try:
                assert isinstance(a, PageBreak) and isinstance(c, PageBreak)
            except AssertionError as e:
                raise AssertionError(
                    f"Page break mismatch at {i}"
                    f"\nAnswer: {a}"
                    f"\nCode: {c}") from e
            continue
        elif isinstance(c, CodeElementBreak):
            # Joining to the preceding answer upon CodeElementBreak
            ans_out[-1] = ' '.join([ans_out[-1], a])
        else:
            # Append regular elements
            ans_out.append(a)
            code_out.append(c)
    # The resulting answers/codes should be the same length.
    try:
        assert len(ans_out) == len(code_out)
    except AssertionError as e:
        raise AssertionError(
            f"Number of answer categories and code elements do not match "
            f"after syncing."
            f"\nAns Cats: {ans_out}"
            f"\nCode: {code_out}"
        ) from e
    # Place back into output and cleanup
    out[ANS.name] = ans_out
    out[CODE.name] = code_out
    del ans_out, code_out

    # Second, deal with frequency, weighted frequency, and percentage columns.
    for heading in [FREQ, WEIGHTED, PERC]:
        # Get the heading element
        heading_elem = get_elem_by_text(unit, heading.value)
        # Get heading positioning
        top = heading_elem.top
        left = heading_elem.left
        right = heading_elem.right
        # Loop to get all elements in the same column
        for i, e in enumerate(unit):
            # Skip element if not below the heading
            # or if it's a secondary heading.
            # Tracking pages breaks is not necessary here,
            # compared to above when we were dealing with
            # multiline answer categories.
            if (e.top < top or (heading.value in e.text)):
                continue
            match heading.value:
                # Frequency position is between the left position of the
                # combined frequency and weighted frequency heading,
                # and the hard-coded right position of the frequency column.
                case FREQ.value:
                    if left < e.left < FREQ_RIGHT_POS - POS_BUFFER:
                        out[heading.name].append(e.text)
                # Weighted frequency, and percentage are right aligned
                case _:
                    if right - POS_TOL < e.right < right + POS_TOL:
                        out[heading.name].append(e.text)
    # Split freq, weight freq, and percent into nested listed,
    # strip whitespace, and flatten.
    for k, v in out.items():
        if k in [CODE.name, FREQ.name, WEIGHTED.name, PERC.name]:
            out[k] = flatten([split_and_strip(e) for e in v])
    # Check that frequency, weighted frequency, and percentage columns
    # have the same number of elements.
    n_elems = []
    for k, v in out.items():
        if k in [FREQ.name, WEIGHTED.name, PERC.name]:
            n_elems.append(len(v))
    try:
        assert len(set(n_elems)) == 1
    except AssertionError as e:
        raise AssertionError(
            f"Frequency, weighted frequency, and percentage columns have "
            f"different lengths."
            f"\nLengths: {n_elems}"
            f"\n{out}"
            ) from e

    # Text cleanup
    for k, v in out.items():
        # Convert weird characters such as ligatures.
        if k in [ANS.name, CODE.name]:
            for i, e in enumerate(v):
                v[i] = replace_characters(e, FAULTY_CHARACTER_MAPPER)
        # Remove commas from frequency and weighted frequency columns.
        if k in [FREQ.name, WEIGHTED.name]:
            for i, e, in enumerate(v):
                v[i] = replace_characters(e, {',': ''})

    # Extract totals from freq, weighted freq, and percent columns.
    out[TOTAL.name] = {
        FREQ.name: out[FREQ.name].pop(),
        WEIGHTED.name: out[WEIGHTED.name].pop(),
        PERC.name: out[PERC.name].pop()}

    # Verify that totals are within tolerance for freq/weight freq/perc.
    for k in [FREQ.name, WEIGHTED.name, PERC.name]:
        try:
            s = sum(map(TOTAL_CHECK_TYPE_FUNCS[k], out[k]))
            t = TOTAL_CHECK_TYPE_FUNCS[k](out[TOTAL.name][k])
            diff = round(abs(s - t), 2)
            tol = TOTAL_TOLS[k]
            assert diff <= tol
        except AssertionError as e:
            raise AssertionError(
                f"{k} total {t} does not match sum {s} "
                f"within tolerance of {tol}."
                f"\nDiff: {diff}."
                f"\nData: {out[k]}"
            ) from e

    return out


def insert_blank_answer_categories(unit: list[Element]) -> None:
    """Helper func to append (in-place) a blank answer category Element.

    For the 'VERDATE' variable, there is an unnamed answer category
    which will cause exceptions in the get_answer_fields function.

    Args:
        unit (list[Elements]): A list of Elements for a single unit.
    """
    answer_heading = get_elem_by_text(unit, Field.answer_categories.value)
    e = Element(
        Element.TEXT_TYPE,
        left=answer_heading.left, top=answer_heading.top + 10,
        width=10, height=10, text='')
    unit.append(e)


# Get data fields for each unit.
# By manual checking, 'PUMFID' and 'WTPP' don't have answer categories.
# Thus, they don't have answer columns used for locating the source
# field of all other variables.
# A quick hack is just to set them manually, as they have blank fields anyways.
# Additionally, 'VERDATE' has answer columns, but an unnamed answer category,
# and only a value for the code.
# This could cause errors in get_answer_fields as get_answer_fields
# does checks to make sure the number elements matchs in
# answer and code columns.
# To get around this, insert an Element with an empty str to mimic a
# unnamed answer category.
NON_ANSWER_VARS = ['PUMFID', 'WTPP']
# Initalize a list of dicts to hold question answers.
questions = [{} for i in range(0, len(units))]
for unit, q in zip(units, questions):
    try:
        q[Field.variable_name.name] = get_variable_name(unit)
        q[Field.length.name] = get_length(unit)
        q[Field.position.name] = get_position(unit)
        q[Field.question_name.name] = get_question_name(unit)
        q[Field.concept.name] = get_concept(unit)
        q[Field.question_text.name] = get_question_text(unit)
        q[Field.universe.name] = get_universe(unit)
        q[Field.note.name] = get_note(unit)
        # Set source to blank for variables without answer categories.
        if q[Field.variable_name.name] in NON_ANSWER_VARS:
            q[Field.source.name] = ''
        else:
            q[Field.source.name] = get_source(unit)
        # Insert blank answer category for 'VERDATE' variable.
        if q[Field.variable_name.name] == 'VERDATE':
            insert_blank_answer_categories(unit)
        if q[Field.variable_name.name] not in NON_ANSWER_VARS:
            q.update(get_answer_fields(unit))
    except Exception as e:
        raise Exception(
            f"Unit causing error:\n\n{unit}."
        ) from e


if debug_mode:
    debug_questions_fp = 'debug_questions.txt'
    debug_listed_data(questions, debug_questions_fp)
    logging.debug(f"Questions written to {debug_questions_fp}.")
# Narrower debug output for just the answer categories
if debug_mode:
    debug_answers = []
    for q in questions:
        debug_answers.append({k: q[k] for k in q if k in [
            Field.answer_categories.name,
            Field.code.name,
            Field.frequency.name,
            Field.weighted_frequency.name,
            Field.percent.name,
            Field.total.name
        ]})
    debug_answers_fp = 'debug_answers.txt'
    debug_listed_data(debug_answers, debug_answers_fp)
    logging.debug(f"Answers written to {debug_answers_fp}.")

# Write the output to a JSON file.
with open(args.output, 'w') as f:
    json.dump(questions, f, indent=2)
