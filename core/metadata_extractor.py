from __future__ import annotations

import base64
import io
import os
import re
from pathlib import Path


class MetadataExtractor:

    VALID_ISA_PREFIXES = {
        "PI", "PDI", "PDIT", "PT", "PIT", "PG", "PCV", "PSV", "PSE", "PAH", "PAL",
        "PAHH", "PALL", "PIC", "PR", "PY", "PDT",
        "TI", "TT", "TE", "TC", "TIC", "TR", "TCV", "TAH", "TAL",
        "FI", "FT", "FE", "FIT", "FC", "FCV", "FIC", "FR", "FAH", "FAL", "FL",
        "LI", "LT", "LE", "LC", "LCV", "LIC", "LAH", "LAL", "LAHH", "LALL",
        "AI", "AT", "AE", "AC", "ACV", "AIC",
        "SI", "ST", "SE", "SC", "SCV", "SIC", "SV",
        "VI", "VT", "VE", "VC",
        "HV", "XV", "ZV", "YV",
        "HS", "XS", "ZS", "YS",
        "HI", "XI", "ZI", "YI",
        "PH", "PL", "TH", "TL", "FH", "FL", "LH", "LL",
        "PAH", "TAH", "FAH", "LAH",
    }

    TILE_INSTRUMENT_PROMPT = (
        "You are an ISA 5.1 instrumentation specialist reading a CROPPED SECTION of a P&ID or engineering diagram.\n\n"
        "YOUR ONLY JOB: List every instrument tag bubble visible in this image section.\n\n"
        "STRICT RULES:\n"
        "- Instrument tags ONLY appear inside circles, ovals, squares, or hexagons drawn on the diagram\n"
        "- Valid ISA prefixes: PI, PDI, PDIT, PDT, PT, PIT, PG, PCV, PSV, PSE, PAH, PAL, PAHH, PALL, PH, "
        "TI, TT, TE, TC, TCV, TAH, TAL, "
        "FI, FT, FE, FIT, FC, FCV, FAH, FAL, FL, "
        "LI, LT, LE, LC, LCV, LAH, LAL, LAHH, LALL, "
        "SV, SI, ST, SE, HV, XV, ZV, HS, XS, ZS, "
        "PIT, FIC, LIC, TIC, PIC\n"
        "- DO NOT read numbers from: title blocks, revision tables, coordinates, borders, dates, "
        "P.O. numbers, contract numbers, drawing numbers, personnel initials/signatures\n"
        "- If you cannot clearly read a tag, write UNREADABLE\n"
        "- DO NOT guess or fabricate. If unsure of a digit, write the prefix and UNREADABLE (e.g. PDI-????)\n"
        "- Note any HI/LO/HH/LL setpoint values shown adjacent to bubbles\n\n"
        "OUTPUT FORMAT — return ONLY a plain list, one tag per line, nothing else:\n"
        "PDI-1610 (HI, LO)\n"
        "FIT-1611 (HI, LO)\n"
        "FCV-1611\n"
        "UNREADABLE\n"
    )

    CONTEXT_PROMPT = (
        "You are a senior process engineer reading a full engineering diagram.\n\n"
        "Extract ONLY the following — be factual, do not guess:\n\n"
        "1. DOCUMENT TYPE: (P&ID, PFD, System Diagram, GA, Isometric, etc.)\n\n"
        "2. TITLE BLOCK: Extract exactly as written:\n"
        "   - Drawing title\n"
        "   - Drawing/document number\n"
        "   - Revision number\n"
        "   - Date\n"
        "   - Company/vendor name\n"
        "   - Client name\n"
        "   - Project name\n"
        "   - Sheet number (e.g. SH. 1 OF 2)\n\n"
        "3. MAJOR EQUIPMENT: List each piece of process equipment with its exact label as written:\n"
        "   - Compressors, pumps, motors, drivers\n"
        "   - Vessels, drums, tanks\n"
        "   - Heat exchangers, coolers\n"
        "   - Skid boundaries and panel boundaries (dashed box labels)\n\n"
        "4. PIPE SPECIFICATIONS: List any pipe spec labels visible (e.g. 0.5-089-7, 1.0-089-7, 2.0-256-216C)\n\n"
        "5. PROCESS STREAMS: Named streams, supply lines, vent lines, drain lines\n\n"
        "6. NOTES/SAFETY: Any general notes, safety annotations, or legend content\n\n"
        "7. UNIQUE ELEMENTS: Anything distinctive about this diagram\n\n"
        "DO NOT list instrument tags here — those are handled separately.\n"
        "If you cannot read something clearly, omit it rather than guessing.\n"
    )

    RECONCILIATION_PROMPT = (
        "You are an ISA 5.1 instrumentation specialist.\n\n"
        "Below is a RAW LIST of instrument tags extracted from multiple tile scans of a P&ID. "
        "Some may be duplicates, some may be misread, and some may be fabricated by the AI.\n\n"
        "Your job:\n"
        "1. Deduplicate — merge identical tags\n"
        "2. Correct obvious misreads — e.g. if you see both PDI-1610 and POI-1610, keep PDI-1610\n"
        "3. Remove any tags whose prefix is not a valid ISA function letter combination\n"
        "4. Remove any tags that look like they came from a title block "
        "(drawing numbers, dates, contract numbers, P.O. numbers tend to be 7+ digits or contain slashes)\n"
        "5. Flag any tag you are uncertain about with a ? suffix\n\n"
        "RAW TAG LIST:\n"
        "{raw_tags}\n\n"
        "Return ONLY a clean deduplicated list, one tag per line. No commentary.\n"
    )

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
        try:
            if ext in (".png", ".jpg", ".jpeg"):
                image_b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
                mime = "image/png" if ext == ".png" else "image/jpeg"
                pil_image = self._b64_to_pil(image_b64)
            elif ext == ".pdf":
                pil_image = self._pdf_to_pil(path)
                image_b64 = None
                mime = "image/png"
            else:
                return ""
        except Exception as e:
            return f"Image load failed: {e}"

        return self._multi_pass_analysis(pil_image, mime, api_key)

    def _multi_pass_analysis(self, pil_image, mime: str, api_key: str) -> str:
        from PIL import Image

        width, height = pil_image.size

        context_b64 = self._pil_to_b64(pil_image)
        context_text = self._call_vision(context_b64, mime, self.CONTEXT_PROMPT, api_key, max_tokens=1200)

        tiles = self._make_tiles(pil_image, cols=3, rows=2, overlap_frac=0.12)

        all_raw_tags = []
        tile_texts = []
        for i, tile in enumerate(tiles):
            tile_b64 = self._pil_to_b64(tile)
            tile_result = self._call_vision(tile_b64, mime, self.TILE_INSTRUMENT_PROMPT, api_key, max_tokens=600)
            tile_texts.append(f"[Tile {i+1}]\n{tile_result}")
            tags = self._parse_tag_list(tile_result)
            all_raw_tags.extend(tags)

        if width > 3000 or height > 2000:
            detail_tiles = self._make_tiles(pil_image, cols=5, rows=3, overlap_frac=0.15)
            for i, tile in enumerate(detail_tiles):
                tile_b64 = self._pil_to_b64(tile)
                tile_result = self._call_vision(tile_b64, mime, self.TILE_INSTRUMENT_PROMPT, api_key, max_tokens=600)
                tags = self._parse_tag_list(tile_result)
                all_raw_tags.extend(tags)

        validated_tags = self._validate_tags_local(all_raw_tags)
        reconciled_tags = self._reconcile_tags(validated_tags, api_key)

        description = (
            f"=== CONTEXT ANALYSIS ===\n{context_text}\n\n"
            f"=== INSTRUMENT TAGS (multi-tile extraction) ===\n"
            + "\n".join(reconciled_tags) +
            f"\n\n=== RAW TILE OUTPUTS ===\n" + "\n\n".join(tile_texts)
        )

        return description

    def _make_tiles(self, image, cols: int, rows: int, overlap_frac: float = 0.1):
        from PIL import Image
        w, h = image.size
        tile_w = int(w / cols)
        tile_h = int(h / rows)
        overlap_x = int(tile_w * overlap_frac)
        overlap_y = int(tile_h * overlap_frac)
        tiles = []
        for row in range(rows):
            for col in range(cols):
                x0 = max(0, col * tile_w - overlap_x)
                y0 = max(0, row * tile_h - overlap_y)
                x1 = min(w, (col + 1) * tile_w + overlap_x)
                y1 = min(h, (row + 1) * tile_h + overlap_y)
                tiles.append(image.crop((x0, y0, x1, y1)))
        return tiles

    def _pil_to_b64(self, image) -> str:
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def _b64_to_pil(self, b64_str: str):
        from PIL import Image
        data = base64.b64decode(b64_str)
        return Image.open(io.BytesIO(data))

    def _pdf_to_pil(self, path: Path):
        import fitz
        from PIL import Image
        doc = fitz.open(str(path))
        page = doc[0]
        mat = fitz.Matrix(4.0, 4.0)
        pix = page.get_pixmap(matrix=mat)
        doc.close()
        img_data = pix.tobytes("png")
        return Image.open(io.BytesIO(img_data))

    def _call_vision(self, image_b64: str, mime: str, prompt: str, api_key: str, max_tokens: int = 800) -> str:
        from openai import OpenAI
        key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not key:
            return ""
        client = OpenAI(api_key=key)
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                max_tokens=max_tokens,
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
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            return f"Vision call failed: {e}"

    def _parse_tag_list(self, text: str) -> list[str]:
        tags = []
        for line in text.splitlines():
            line = line.strip().strip("-").strip("*").strip()
            if not line or line.startswith("[") or line.lower().startswith("unreadable"):
                continue
            match = re.match(r"([A-Z]{2,5}-\d{3,6}[A-Z]?)(\s.*)?$", line)
            if match:
                tags.append(match.group(1))
        return tags

    def _validate_tags_local(self, tags: list[str]) -> list[str]:
        validated = []
        seen = set()
        for tag in tags:
            m = re.match(r"^([A-Z]+)-(\d+)([A-Z]?)$", tag)
            if not m:
                continue
            prefix = m.group(1)
            if prefix not in self.VALID_ISA_PREFIXES:
                continue
            if tag not in seen:
                seen.add(tag)
                validated.append(tag)
        return validated

    def _reconcile_tags(self, tags: list[str], api_key: str) -> list[str]:
        if not tags:
            return []
        raw_str = "\n".join(tags)
        key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not key:
            return tags
        from openai import OpenAI
        client = OpenAI(api_key=key)
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                max_tokens=600,
                messages=[
                    {
                        "role": "user",
                        "content": self.RECONCILIATION_PROMPT.format(raw_tags=raw_str),
                    }
                ],
            )
            result_text = response.choices[0].message.content or ""
            reconciled = []
            seen = set()
            for line in result_text.splitlines():
                line = line.strip()
                if not line:
                    continue
                m = re.match(r"([A-Z]{2,5}-\d{3,6}[A-Z]?\??)", line)
                if m:
                    tag = m.group(1)
                    if tag not in seen:
                        seen.add(tag)
                        reconciled.append(tag)
            return reconciled if reconciled else tags
        except Exception:
            return tags

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
        instrument_section = ""
        if "=== INSTRUMENT TAGS" in vision_text:
            parts = vision_text.split("=== INSTRUMENT TAGS (multi-tile extraction) ===")
            if len(parts) > 1:
                instrument_section = parts[1].split("===")[0].strip()

        context_section = ""
        if "=== CONTEXT ANALYSIS ===" in vision_text:
            parts = vision_text.split("=== CONTEXT ANALYSIS ===")
            if len(parts) > 1:
                context_section = parts[1].split("===")[0].strip()

        combined = context_section + " " + instrument_section

        tags = []
        for line in instrument_section.splitlines():
            line = line.strip()
            m = re.match(r"([A-Z]{2,5}-\d{3,6}[A-Z]?\??)", line)
            if m:
                tags.append(m.group(1))

        meta = {
            "project_number": self._find_project_number(path.name, context_section),
            "revision": self._find_revision(path.name, context_section),
            "description": self._find_description(path.name),
            "client": self._find_client(context_section),
            "date": self._find_date(context_section),
            "unit_operations": self._find_unit_operations(context_section),
            "instrumentation": tags if tags else self._find_instrumentation(combined),
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
            "gas seal", "seal panel", "skid",
        ]
        found = []
        lower = text.lower()
        for kw in keywords:
            if kw in lower and kw not in found:
                found.append(kw)
        return found

    def _find_instrumentation(self, text: str) -> list[str]:
        candidates = re.findall(r"\b([A-Z]{2,5}-\d{3,5}[A-Z]?)\b", text)
        seen = []
        for tag in candidates:
            prefix = re.match(r"^([A-Z]+)", tag)
            if not prefix:
                continue
            if prefix.group(1) not in self.VALID_ISA_PREFIXES:
                continue
            if tag not in seen:
                seen.append(tag)
        return seen[:60]

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
