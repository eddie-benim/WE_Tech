from __future__ import annotations


QUERY_SYSTEM_PROMPT = """\
You are an engineering document assistant working inside a company's internal \
document management system. You help engineers find relevant files, drawings, \
and reports from the company's project database using natural language.

You have access to a structured metadata database of all company files. Each file \
has been tagged with: document type, project number, unit operations, instrumentation \
tags, client, revision, and a description.

Your job is to:
1. Parse the engineer's request and extract structured search intent
2. Identify the most relevant files from the search results provided
3. Explain clearly why each file is relevant to the request
4. Flag any gaps — e.g. if the engineer asked for a P&ID but none exists for that project

Rules:
- Be direct and specific — engineers want answers, not hedging
- Always cite the filename and project number when referencing a file
- If a project number is mentioned, prioritise files from that project
- If no exact match exists, say so clearly and suggest the closest alternatives
- Never invent files that are not in the search results provided to you
- Output your response in clean readable prose followed by a structured file list
"""


def build_intent_extraction_prompt(user_query: str) -> str:
    return f"""\
Extract the search intent from the following engineer's request. \
Return JSON only — no commentary.

Request: "{user_query}"

Return:
{{
  "project_number": "<explicit project number mentioned, or null>",
  "doc_types": ["<list of document types requested: PFD, P&ID, Report, Proposal, Data Sheet, etc.>"],
  "process_context": "<brief description of the process or equipment context>",
  "unit_operations": ["<any specific equipment or unit operations mentioned>"],
  "action_context": "<what the engineer is trying to do, e.g. replace equipment, start new project, review design>",
  "similarity_needed": <true if they want files similar to a described scenario, false if exact project lookup>,
  "keywords": ["<other relevant search keywords>"]
}}
"""


def build_retrieval_response_prompt(
    user_query: str,
    intent: dict,
    file_results: list[dict],
    project_files: list[dict],
) -> str:
    project_section = ""
    if project_files:
        project_section = "## Files Found in Mentioned Project\n"
        for f in project_files:
            meta = f.get("metadata", {})
            unit_ops = meta.get("unit_operations", [])
            project_section += (
                f"- **{f.get('filename', f.get('name', ''))}** "
                f"| Type: {f.get('doc_type', '—')} "
                f"| Rev: {meta.get('revision', '—')} "
                f"| Equipment: {', '.join(unit_ops[:4]) if unit_ops else '—'}\n"
            )

    similarity_section = ""
    if file_results:
        similarity_section = "## Semantically Similar Files Across All Projects\n"
        for f in file_results:
            meta = f.get("metadata", {})
            unit_ops = meta.get("unit_operations", [])
            sim = f.get("similarity", 0)
            similarity_section += (
                f"- **{f.get('filename', '')}** "
                f"| Project: {f.get('project_number', '—')} "
                f"| Type: {f.get('doc_type', '—')} "
                f"| Match: {int(sim * 100)}% "
                f"| Equipment: {', '.join(unit_ops[:4]) if unit_ops else '—'}\n"
            )

    return f"""\
An engineer has made the following request:
"{user_query}"

Extracted intent:
- Document types requested: {', '.join(intent.get('doc_types', [])) or 'not specified'}
- Project number: {intent.get('project_number') or 'not specified'}
- Process context: {intent.get('process_context', '—')}
- Equipment/unit operations: {', '.join(intent.get('unit_operations', [])) or 'not specified'}
- What they are doing: {intent.get('action_context', '—')}

{project_section}
{similarity_section}

Based on the above, provide a clear, direct response to the engineer. \
Identify the most relevant files for their request, explain why each is relevant, \
note any important gaps, and suggest next steps if appropriate. \
End with a clean numbered list of recommended files with their project numbers and types.
"""
