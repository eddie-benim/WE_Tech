from __future__ import annotations


FILE_SYSTEM_PROMPT = """\
You are an engineering document analyst specialising in process engineering \
documentation including PFDs, P&IDs, data sheets, equipment sizing reports, \
heat and energy balance reports, proposals, isometrics, and GA drawings.

Your job is to analyse engineering files and return structured metadata about them. \
You have access to company reference files for comparison.

Rules:
- Identify the document type based on content, layout clues, and filename
- Extract all identifiable metadata fields: project number, revision, client, \
  date, unit operations, instrumentation tags, process conditions
- Where the file is an image (PNG, JPG) describe what you can infer from the \
  filename and any text present
- Propose a clean filename following the company naming scheme provided
- Return your response as valid JSON only — no commentary, no markdown fences
- If you are uncertain about a field, set its value to null rather than guessing
"""


def build_file_analysis_prompt(
    filename: str,
    extension: str,
    text_sample: str,
    rule_based_result: dict,
    naming_scheme: dict,
    reference_context: str,
) -> str:
    return f"""\
Analyse the following engineering file and return a JSON metadata object.

## File Information
- **Filename:** {filename}
- **Extension:** {extension}
- **Rule-based classification (pre-computed):** {rule_based_result}

## Extracted Text Sample
{text_sample or "No text could be extracted (may be an image or scanned document)."}

## Company Naming Scheme
The company uses the following file naming convention:
- Scheme: {naming_scheme.get("scheme", "PROJECT-NUMBER_DOC-TYPE_DESCRIPTION_REVISION")}
- Example: {naming_scheme.get("example", "PRJ-001_PFD_Separation-Train_Rev0.pdf")}
- Separator: {naming_scheme.get("separator", "_")}

## Company Reference Context
{reference_context or "No company reference documents available."}

## Required JSON Output Schema
{{
  "original_name": "{filename}",
  "doc_type": "<one of: PFD, P&ID, Heat & Energy Balance, Equipment Sizing, Proposal, Data Sheet, Isometric, GA Drawing, Cause & Effect, Hazop, Report, Unknown>",
  "format": "<PDF | PNG Image | JPEG Image | Word Document | Excel Spreadsheet | PowerPoint | Plain Text>",
  "suggested_name": "<proposed filename following company naming scheme>",
  "metadata": {{
    "project_number": "<string or null>",
    "revision": "<string or null>",
    "client": "<string or null>",
    "date": "<string or null>",
    "description": "<brief human-readable description of content>",
    "unit_operations": ["<list of identified unit operations>"],
    "instrumentation": ["<list of instrument tag numbers>"],
    "process_conditions": {{
      "temperature": "<string or null>",
      "pressure": "<string or null>",
      "flow": "<string or null>"
    }},
    "unique_elements": ["<list of notable or unusual elements in this document>"]
  }},
  "confidence": "<high | medium | low>"
}}
"""


def build_naming_scheme_prompt(file_list: list[dict]) -> str:
    samples = "\n".join(f"- {f.get('name', '')}" for f in file_list[:20])
    return f"""\
You are analysing a set of engineering filenames to infer the naming convention \
used by this company.

## Sample Filenames
{samples}

Identify the naming pattern, separator character, and order of components \
(e.g. project number, document type, description, revision).

Return your response as JSON only:
{{
  "scheme": "<pattern using placeholder names>",
  "example": "<example filename>",
  "separator": "<_ or - or space>",
  "components": ["<ordered list of component names>"],
  "confidence": "<high | medium | low>",
  "notes": "<any observations about inconsistencies or variations>"
}}
"""