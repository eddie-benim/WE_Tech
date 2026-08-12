# -*- coding: utf-8 -*-
from __future__ import annotations


FILE_SYSTEM_PROMPT = (
    "You are an engineering document analyst specialising in process engineering "
    "documentation including PFDs, P&IDs, data sheets, equipment sizing reports, "
    "heat and energy balance reports, proposals, isometrics, and GA drawings.\n\n"
    "Your job is to analyse engineering files and return structured metadata about them.\n\n"
    "RULES:\n"
    "- Identify the document type based on content, layout clues, and filename\n"
    "- Extract all identifiable metadata fields: revision, client, date, unit operations, "
    "instrumentation tags, process conditions\n"
    "- Where vision analysis output is provided, treat it as the primary source of truth "
    "for equipment and instrumentation\n"
    "- Propose a clean filename following the company naming scheme provided\n"
    "- Return your response as valid JSON only -- no commentary, no markdown fences\n"
    "- If you are uncertain about a field, set its value to null rather than guessing\n\n"
    "PROJECT NUMBER RULES -- CRITICAL:\n"
    "A project number is a structured identifier used by the engineering firm to organise "
    "project folders (e.g. PRJ-0052, JOB-1234). It is NOT the same as:\n"
    "- A drawing number (e.g. 1000201422, DWG-4521) -- typically 7+ digits or vendor prefix\n"
    "- A work order or purchase order number (W.O., P.O.)\n"
    "- A contract number\n"
    "- A sheet number\n"
    "If the document contains only a drawing number, W.O., P.O., or contract number, "
    "set project_number to null. Do NOT put the drawing number in the project_number field.\n"
    "Only set project_number if the document explicitly states Project No:, PRJ-, or JOB- "
    "followed by a structured identifier that contains both letters and numbers.\n"
    "A purely numeric string of 7 or more digits is always a drawing/PO/contract number, "
    "never a project number.\n"
)


def build_file_analysis_prompt(
    filename: str,
    extension: str,
    text_sample: str,
    rule_based_result: dict,
    naming_scheme: dict,
    reference_context: str,
    vision_description: str = "",
) -> str:
    vision_section = ""
    if vision_description:
        vision_section = f"""
## Vision Analysis (GPT-4o image reading)
The following was extracted by visually reading the diagram image. \
This is the primary source for equipment, instrumentation, and layout details.
Use it to populate the requested metadata, but do NOT repeat or quote the vision analysis in the JSON:

{vision_description}
"""

    return f"""\
Analyse the following engineering file and return a JSON metadata object.

## File Information
- **Filename:** {filename}
- **Extension:** {extension}
- **Rule-based classification (pre-computed):** {rule_based_result}

## Extracted Text Sample
{text_sample or "No text could be extracted (image or scanned document — see vision analysis below)."}
{vision_section}
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
    "unit_operations": ["<every piece of process equipment identified>"],
    "instrumentation": ["<every instrument tag number identified>"],
    "control_loops": ["<control loop descriptions if visible>"],
    "process_streams": ["<key stream descriptions>"],
    "process_conditions": {{
      "temperature": "<string or null>",
      "pressure": "<string or null>",
      "flow": "<string or null>"
    }},
    "unique_elements": ["<notable or unusual elements>"]
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


def build_project_match_prompt(
    new_file_result: dict,
    similar_files: list[dict],
) -> str:
    meta = new_file_result.get("metadata", {})
    unit_ops = meta.get("unit_operations", [])
    instruments = meta.get("instrumentation", [])
    doc_type = new_file_result.get("doc_type", "Unknown")

    candidates = ""
    for i, f in enumerate(similar_files, 1):
        candidates += (
            f"{i}. {f.get('filename', '')} | Project: {f.get('project_number', '—')} | "
            f"Type: {f.get('doc_type', '—')} | Similarity: {f.get('similarity', 0):.2f} | "
            f"Equipment: {', '.join(f.get('unit_operations', [])[:5])}\n"
        )

    return f"""\
A new engineering file has been analysed. Determine which existing project it most \
likely belongs to, based on the evidence below.

## New File
- Document type: {doc_type}
- Unit operations identified: {', '.join(unit_ops) if unit_ops else 'none'}
- Instrumentation tags: {', '.join(instruments[:15]) if instruments else 'none'}
- Description: {meta.get('description', '—')}
- Vision summary: {meta.get('vision_description', '')[:400] if meta.get('vision_description') else 'not available'}

## Most Similar Existing Files (by vector similarity)
{candidates or "No existing files in the database yet."}

Return JSON only:
{{
  "matched_project_number": "<project number or null if no confident match>",
  "matched_project_confidence": "<high | medium | low | none>",
  "reasoning": "<one sentence explaining the match>",
  "recommended_folder": "<suggested folder path relative to output root>"
}}
"""
