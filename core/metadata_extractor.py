from __future__ import annotations

import base64
import os
import re
from pathlib import Path


class MetadataExtractor:

    def extract_text_sample(self, path: Path, max_chars: int = 2000) -> str:
        ext = path.suffix.lower()
        try:
            if ext == ".pdf":
                return self._read_pdf(path, max_chars)
            elif ext in (".docx", ".doc"):
                return self._read_docx(path, max_chars)
            elif ext in (".xlsx", ".xls"):
                return self._read_xlsx(path, max_chars)
            elif ext in (".pptx", ".ppt"):
                return self._read_pptx(path, max_chars)
            elif ext == ".txt":
                return path.read_text(errors="ignore")[:max_chars]
            elif ext in (".png", ".jpg", ".jpeg"):
                return ""
        except Exception:
            return ""
        return ""

    def extract_vision_description(self, path: Path, api_key: str = "") -> str:
        ext = path.suffix.lower()
        if ext not in (".png", ".jpg", ".jpeg"):
            try:
                pdf_image = self._pdf_first_page_as_image(path)
                if pdf_image:
                    return self._call_vision_api(pdf_image, "image/png", api_key)
            except Exception:
                return ""
            return ""
        mime = "image/png" if ext == ".png" else "image/jpeg"
        image_b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
        return self._call_vision_api(image_b64, mime, api_key)

    def _call_vision_api(self, image_b64: str, mime: str, api_key: str) -> str:
        from openai import OpenAI
        key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not key:
            return ""
        client = OpenAI(api_key=key)
        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=1200,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime};base64,{image_b64}",
                                "detail": "high",
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "You are an expert process engineer analysing an engineering diagram. "
                                "Examine this image carefully and extract the following as a structured description:\n\n"
                                "1. DOCUMENT TYPE: What kind of diagram is this? (P&ID, PFD, isometric, GA, etc.)\n"
                                "2. TITLE BLOCK: Any project name, number, revision, date, client, or document number visible\n"
                                "3. UNIT OPERATIONS: Every piece of process equipment visible — compressors, pumps, vessels, "
                                "heat exchangers, columns, reactors, drums, tanks, motors, drivers. Include their tag numbers if labelled.\n"
                                "4. INSTRUMENTATION: Every instrument tag visible (e.g. PT-101, FIC-202, LV-301). "
                                "List all you can read.\n"
                                "5. CONTROL LOOPS: Any control loops or signal lines described in legends or shown on the diagram\n"
                                "6. PROCESS STREAMS: Key streams, flow directions, pipe sizes if shown\n"
                                "7. UNIQUE ELEMENTS: Anything distinctive about this diagram — unusual equipment, "
                                "special annotations, non-standard symbols\n"
                                "8. LEGEND / ABBREVIATIONS: Any legend box content\n\n"
                                "Be as specific and complete as possible. Read every label you can make out."
                            ),
                        },
                    ],
                }
            ],
        )
        return response.choices[0].message.content or ""

    def _pdf_first_page_as_image(self, path: Path) -> str:
        import fitz
        doc = fitz.open(str(path))
        page = doc[0]
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat)
        doc.close()
        return base64.b64encode(pix.tobytes("png")).decode("utf-8")

    def extract_metadata(self, path: Path, text_sample: str, doc_type: str) -> dict:
        meta = {
            "doc_type": doc_type,
            "project_number": self._find_project_number(path.name, text_sample),
            "revision": self._find_revision(path.name, text_sample),
            "description": self._find_description(path.name),
            "client": self._find_client(text_sample),
            "date": self._find_date(text_sample),
            "unit_operations": self._find_unit_operations(text_sample),
            "instrumentation": self._find_instrumentation(text_sample),
        }
        return {k: v for k, v in meta.items() if v}

    def extract_metadata_from_vision(self, vision_text: str, path: Path) -> dict:
        meta = {
            "project_number": self._find_project_number(path.name, vision_text),
            "revision": self._find_revision(path.name, vision_text),
            "description": self._find_description(path.name),
            "client": self._find_client(vision_text),
            "date": self._find_date(vision_text),
            "unit_operations": self._find_unit_operations(vision_text),
            "instrumentation": self._find_instrumentation(vision_text),
            "vision_description": vision_text,
        }
        return {k: v for k, v in meta.items() if v}

    def _find_project_number(self, filename: str, text: str) -> str:
        patterns = [
            r"\bPRJ[-_]?\d{2,6}\b",
            r"\bP[-_]?\d{4,6}\b",
            r"\b\d{4,6}[-_][A-Z]{2,4}\b",
            r"Project\s*(?:No|Number|#)[.:\s]*([A-Z0-9\-]{4,12})",
        ]
        combined = filename + " " + text
        for pat in patterns:
            m = re.search(pat, combined, re.IGNORECASE)
            if m:
                return m.group(0).strip()
        return ""

    def _find_revision(self, filename: str, text: str) -> str:
        patterns = [
            r"\bRev\.?\s*[A-Z0-9]{1,3}\b",
            r"\bR[0-9]{1,2}\b",
            r"\b[Rr]evision\s+[A-Z0-9]{1,3}\b",
        ]
        combined = filename + " " + text
        for pat in patterns:
            m = re.search(pat, combined, re.IGNORECASE)
            if m:
                return m.group(0).strip()
        return ""

    def _find_description(self, filename: str) -> str:
        stem = Path(filename).stem
        stem = re.sub(r"(PRJ[-_]?\d+|Rev\.?\s*\w+|R\d+|\d{4,})", "", stem, flags=re.IGNORECASE)
        stem = re.sub(r"[-_]+", " ", stem).strip()
        words = [w for w in stem.split() if len(w) > 1]
        return " ".join(words[:6])

    def _find_client(self, text: str) -> str:
        patterns = [
            r"Client[:\s]+([A-Za-z0-9 &,.\-]{3,40})",
            r"Prepared\s+for[:\s]+([A-Za-z0-9 &,.\-]{3,40})",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return ""

    def _find_date(self, text: str) -> str:
        patterns = [
            r"\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b",
            r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\b",
            r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\b",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return ""

    def _find_unit_operations(self, text: str) -> list[str]:
        keywords = [
            "separator", "heat exchanger", "compressor", "pump", "vessel",
            "column", "distillation", "absorber", "stripper", "reactor",
            "filter", "scrubber", "cooler", "heater", "reboiler", "condenser",
            "flash drum", "knock-out drum", "slug catcher", "electric motor",
            "driver motor", "aftercooler", "suction drum", "discharge drum",
            "control valve", "relief valve", "check valve", "blowdown",
        ]
        found = []
        lower = text.lower()
        for kw in keywords:
            if kw in lower and kw not in found:
                found.append(kw)
        return found

    def _find_instrumentation(self, text: str) -> list[str]:
        tags = re.findall(r"\b([A-Z]{1,3}[A-Z][-_]?\d{3,5}[A-Z]?)\b", text)
        seen = []
        for t in tags:
            if t not in seen:
                seen.append(t)
        return seen[:40]

    def _read_pdf(self, path: Path, max_chars: int) -> str:
        import fitz
        doc = fitz.open(str(path))
        text = ""
        for page in doc:
            text += page.get_text()
            if len(text) >= max_chars:
                break
        doc.close()
        return text[:max_chars]

    def _read_docx(self, path: Path, max_chars: int) -> str:
        from docx import Document
        doc = Document(str(path))
        text = "\n".join(p.text for p in doc.paragraphs)
        return text[:max_chars]

    def _read_xlsx(self, path: Path, max_chars: int) -> str:
        import openpyxl
        wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
        text = ""
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                text += " ".join(str(c) for c in row if c is not None) + "\n"
                if len(text) >= max_chars:
                    break
        return text[:max_chars]

    def _read_pptx(self, path: Path, max_chars: int) -> str:
        from pptx import Presentation
        prs = Presentation(str(path))
        text = ""
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    text += shape.text + "\n"
                if len(text) >= max_chars:
                    break
        return text[:max_chars]
