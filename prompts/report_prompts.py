from __future__ import annotations


REPORT_SYSTEM_PROMPT = """\
You are a senior process engineer with 20+ years of experience in oil & gas, \
petrochemical, and industrial process engineering. You write technical reports \
that are precise, professionally structured, and consistent with industry standards \
(API, ASME, ISA, ISO).

Your job is to take a skeletal report template and fill it with technically accurate, \
detailed content based on:
1. The project information provided by the engineer
2. Relevant excerpts from the company's own past reports (provided as reference context)
3. Any web research results provided to you

Rules you must follow:
- Use only SI or Imperial units as specified - never mix them
- All equations must be written out with variable definitions
- Where you make assumptions, state them explicitly in an Assumptions section
- Do not fabricate specific numeric results - use placeholder variables (e.g. Q_duty, T_in) \
  where actual process data has not been provided
- Where company reference documents show a specific format, table structure, or \
  calculation approach, follow that convention in preference to generic approaches
- Output only valid Markdown - no commentary outside the report body
- Do not add a preamble or sign-off; output the report and nothing else
"""

def build_report_user_prompt(
    report_type: str,
    project_info: dict,
    skeleton: str,
    reference_context: str,
    web_results: str,
) -> str:
    pi = project_info
    return f"""\
## Task
Fill in the following {report_type} skeleton for the project described below. \
Replace all placeholder sections marked with italics or dashes with technically \
accurate engineering content.

## Project Information
- **Project Name:** {pi.get("project_name", "—")}
- **Project Number:** {pi.get("project_number", "—")}
- **Client:** {pi.get("client", "—")}
- **Unit System:** {pi.get("unit_system", "SI (metric)")}
- **Revision:** {pi.get("revision", "Rev0")}
- **Description:** {pi.get("description", "—")}
- **Special Notes / Constraints:** {pi.get("special_notes", "None")}

## Company Reference Context
The following excerpts are from past reports in the company's reference library. \
Use these to match formatting conventions, calculation approaches, and terminology.

{reference_context or "No company reference documents available."}

## Web Research
The following results were retrieved from engineering sources on the web. \
Use these for equations, standards references, and industry norms.

{web_results or "No web research performed."}

## Report Skeleton to Fill
{skeleton}
"""


def build_web_search_query(report_type: str, project_info: dict) -> str:
    desc = project_info.get("description", "")
    name = project_info.get("project_name", "")
    unit = project_info.get("unit_system", "SI")
    return (
        f"{report_type} calculation methodology {desc} {name} "
        f"engineering standard formula {unit}"
    ).strip()