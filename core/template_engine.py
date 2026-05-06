from __future__ import annotations

from pathlib import Path
from jinja2 import Environment, BaseLoader


REPORT_TEMPLATES: dict[str, str] = {
    "Heat & Energy Balance Report": """\
# Heat & Energy Balance Report
**Project:** {{ project_name }}{% if project_number %} · {{ project_number }}{% endif %}
**Client:** {{ client | default("—") }}
**Revision:** {{ revision }}
**Unit System:** {{ unit_system }}
{% if date %}**Date:** {{ date }}{% endif %}

---

## 1. Introduction

{{ description }}

---

## 2. Basis of Design

| Parameter | Value |
|---|---|
| Unit System | {{ unit_system }} |
| Revision | {{ revision }} |
{% if special_notes %}
**Notes:** {{ special_notes }}
{% endif %}

---

## 3. Process Description

*To be completed by agent using reference documents and project description.*

---

## 4. Heat & Energy Balance Summary

| Stream | Temperature ({{ temp_unit }}) | Pressure ({{ pressure_unit }}) | Flow Rate ({{ flow_unit }}) | Duty ({{ duty_unit }}) |
|---|---|---|---|---|
| Feed | — | — | — | — |
| Product | — | — | — | — |

---

## 5. Equipment Summary

| Tag | Description | Duty ({{ duty_unit }}) | Notes |
|---|---|---|---|
| — | — | — | — |

---

## 6. Assumptions & Limitations

*To be completed by agent.*

---

## 7. References

*Standards, codes, and reference documents to be listed by agent.*
""",

    "Equipment Sizing Report": """\
# Equipment Sizing Report
**Project:** {{ project_name }}{% if project_number %} · {{ project_number }}{% endif %}
**Client:** {{ client | default("—") }}
**Revision:** {{ revision }}
**Unit System:** {{ unit_system }}

---

## 1. Introduction

{{ description }}

---

## 2. Design Basis

| Parameter | Value |
|---|---|
| Unit System | {{ unit_system }} |
| Revision | {{ revision }} |
{% if special_notes %}
**Notes:** {{ special_notes }}
{% endif %}

---

## 3. Equipment List

| Tag | Type | Description | Design Conditions |
|---|---|---|---|
| — | — | — | — |

---

## 4. Sizing Calculations

*To be completed by agent using first-principles equations and reference documents.*

---

## 5. Results Summary

| Tag | Key Parameter | Calculated Value | Selected Size | Notes |
|---|---|---|---|---|
| — | — | — | — | — |

---

## 6. References

*Standards, codes, and reference documents to be listed by agent.*
""",

    "Project Proposal": """\
# Project Proposal
**Project:** {{ project_name }}{% if project_number %} · {{ project_number }}{% endif %}
**Client:** {{ client | default("—") }}
**Revision:** {{ revision }}

---

## 1. Executive Summary

{{ description }}

---

## 2. Scope of Work

*To be completed by agent.*

---

## 3. Technical Approach

*To be completed by agent.*

---

## 4. Deliverables

| # | Deliverable | Format | Timeline |
|---|---|---|---|
| 1 | — | — | — |

---

## 5. Assumptions & Exclusions

*To be completed by agent.*

---

## 6. References

*To be listed by agent.*
""",

    "General Technical Report": """\
# Technical Report
**Project:** {{ project_name }}{% if project_number %} · {{ project_number }}{% endif %}
**Client:** {{ client | default("—") }}
**Revision:** {{ revision }}

---

## 1. Introduction

{{ description }}

---

## 2. Background

*To be completed by agent.*

---

## 3. Technical Content

*To be completed by agent.*

---

## 4. Conclusions & Recommendations

*To be completed by agent.*

---

## 5. References

*To be listed by agent.*
""",
}


_UNIT_MAP = {
    "SI (metric)": {
        "temp_unit": "°C",
        "pressure_unit": "kPa(g)",
        "flow_unit": "kg/h",
        "duty_unit": "kW",
    },
    "Imperial (US)": {
        "temp_unit": "°F",
        "pressure_unit": "psig",
        "flow_unit": "lb/h",
        "duty_unit": "BTU/h",
    },
}


class TemplateEngine:

    def __init__(self):
        self._env = Environment(loader=BaseLoader())

    def render_skeleton(self, report_type: str, project_info: dict) -> str:
        template_str = REPORT_TEMPLATES.get(report_type, REPORT_TEMPLATES["General Technical Report"])
        template = self._env.from_string(template_str)

        unit_system = project_info.get("unit_system", "SI (metric)")
        units = _UNIT_MAP.get(unit_system, _UNIT_MAP["SI (metric)"])

        context = {**project_info, **units}
        return template.render(**context)

    def available_templates(self) -> list[str]:
        return list(REPORT_TEMPLATES.keys())