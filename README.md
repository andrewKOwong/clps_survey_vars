# Canadian Legal Problems Survey - Survey Metadata
## Project Summary
The [Canadian Legal Problems
Survey](https://www.justice.gc.ca/eng/rp-pr/jr/survey-enquete.html) (CLPS) is a national survey of Canadians' experiences with the justice system, most recently conducted by Statisics Canada in 2021.
Data from the survey is provided by Statistics Canada via a [Public Use Microdata
File](https://www150.statcan.gc.ca/n1/pub/35-25-0002/352500022022001-eng.htm) (PUMF).
The provided data includes a codebook containing information and metadata about
 survey variables in PDF format that is not readily machine-readable.

This repo contains scripts to extract data from the codebook PDF.
It also contains an app to browse the extracted data and verify correct
extraction.

A blogpost describing this project is available
[here](https://mixedconclusions.com/blog/clps_survey_vars/).

For a related project on creating a dashboard for the main
CLPS dataset, see [here](
  https://github.com/andrewKOwong/clps_data
).

## Instructions
### Description of Files
- `extract_cdbk_pdf_answer.py` --- python script for data extraction.
- `codebook.pdf` --- the original PDF codebook provided in the PUMF.
- `codebook.html` --- intermediary html file for extraction.
- `survey_vars.json` --- JSON formatted extracted data.
- `verify_app.py` --- streamlit app for browsing and verifying the data.
- `archive` --- previous versions of extracted data and a defunct script for
  extracting the table of contents.
- `.streamlit/config.toml` --- configuration file for the streamlit app.


### Libraries Required
I haven't tested for strict minimum versions as I usually work out of a
very generalized data science environment.
- `python` 3.10+
- `beautifulsoup4`
- `streamlit`
- `pdfminer.six` this is a PDF extraction library that I use for its CLI tool.
  See its [repo](https://github.com/pdfminer/pdfminer.six) and [docs](https://pdfminersix.readthedocs.io/en/latest/).


### Extracting the Data
Data is extracted by first converting the PDF to an HTML file, then extracting
from the HTML file to a JSON formatted output file.
#### Converting the PDF to an HTML File
`pdfminer.six` provides a CLI utility. To convert the PDF to an html, run:
```
pdf2txt.py codebook.pdf -o codebook.html --output_type html
```
This intermediary HTML field contains `div` elements for each apparent chunk of
data on the PDF page. Opening it in a web browser displays a fairly good
facsimile of the original PDF for inspection.

#### Extracting Data from the HTML File
To extract the data from the HTML file, run in the command line:
```
python extract_cdbk_pdf_answers.py codebook.html
```
This writes out the data as a JSON file, by default as `survey_vars.json`. Use
`--help` for further options.



### Running the Verification App
The extracted JSON data can be viewed and inspected by running `verify_app.py`.
An instance of this app is hosted on the
Streamlit Community Cloud.

[Click here to access the app](https://clps-survey-variables.streamlit.app/).

Alternatively, you can run the app locally.
After [installing
streamlit](https://docs.streamlit.io/library/get-started/installation),
start the app in the command line with:
```
streamlit run verify_app.py
```
Note: the app is currently
hard-coded to read in the file `survey_vars.json` as the data source.