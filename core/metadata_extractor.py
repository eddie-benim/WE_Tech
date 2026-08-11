# -*- coding: utf-8 -*-
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
        "- CHARACTER AMBIGUITY -- on engineering drawings these pairs are frequently confused by OCR. "
        "Always resolve in favour of the ISA-valid interpretation:\n"
        "  * 0 vs O vs C: a circle-like character in a tag prefix is almost always 0 (zero), not O or C\n"
        "  * 1 vs I vs l: a vertical stroke in a tag prefix is almost always I (the ISA letter), not 1 or l\n"
        "  * Example: if you see C0 PDI or 7C PDI written on equipment, the likely reading is 70 PDI (number seventy, then PDI)\n"
        "  * Example: if you see PD1 in a bubble, the likely correct reading is PDI (Pressure Differential Indicating)\n"
        "- COMPOUND BUBBLES: some instrument bubbles contain TWO stacked tags in a single circle "
        "(e.g. PDI on top and PDIT below in the same bubble, or FIT above FI). "
        "These are TWO separate instruments sharing a bubble -- list BOTH on separate lines\n"
        "- ASSOCIATED TRANSMITTERS: wherever you see a PDI, also look for a co-located PDIT. "
        "Wherever you see an FI, look for a co-located FIT. List each separately if present\n"
        "- If you cannot clearly read a tag, write UNREADABLE\n"
        "- DO NOT guess or fabricate. If unsure of a digit, write the prefix and UNREADABLE (e.g. PDI-????)\n"
        "- Note any HI/LO/HH/LL setpoint values shown adjacent to bubbles\n\n"
        "OUTPUT FORMAT -- return ONLY a plain list, one tag per line, nothing else:\n"
        "PDI-1610 (HI, LO)\n"
        "PDIT-1610\n"
        "FIT-1611 (HI, LO)\n"
        "FCV-1611\n"
        "UNREADABLE\n"
    )

    CONTEXT_PROMPT = (
        "You are a senior process engineer reading a full engineering diagram.\n\n"
        "Extract ONLY the following -- be factual, do not guess:\n\n"
        "CHARACTER AMBIGUITY NOTE: On engineering drawings, 0 (zero) and O, and 1 (one) and I (capital i) "
        "are frequently confused. When reading equipment labels: prefer numeric reading for standalone numbers "
        "(e.g. '70 PDI COMPRESSOR' not '7C PDI' or '70 PD1'); prefer letter reading for ISA prefixes. "
        "Read equipment labels exactly as they appear character by character and favour the reading that "
        "makes engineering sense (e.g. a compressor labelled '70 PDI' is a 70-PDI type unit).\n\n"
        "1. DOCUMENT TYPE: (P&ID, PFD, System Diagram, GA, Isometric, etc.)\n\n"
        "2. TITLE BLOCK: Extract exactly as written -- preserve all distinctions:\n"
        "   - Drawing title (e.g. 'GAS SEAL SYSTEM DIAGRAM')\n"
        "   - Drawing number / document number (this is the vendor or engineering firm's internal drawing ID, "
        "NOT the project number -- label it clearly as DRAWING NUMBER)\n"
        "   - Revision number and date\n"
        "   - Vendor / contractor name (e.g. DRESSER-RAND, KBR, Worley)\n"
        "   - Client name (e.g. TRANSCONTINENTAL GAS PIPE LINE)\n"
        "   - Project name (e.g. MID ATLANTIC CONNECTOR EXPANSION PROJECT) -- "
        "this is NOT the same as the drawing number; label it clearly as PROJECT NAME\n"
        "   - Work order / purchase order number if present -- label as W.O. or P.O., NOT as project number\n"
        "   - Contract number if present\n"
        "   - Sheet number (e.g. SH. 1 OF 2)\n"
        "   - IMPORTANT: Do NOT use the drawing number or W.O./P.O. number as the project number. "
        "If no explicit project number is visible, write PROJECT NUMBER: NOT STATED\n\n"
        "3. MAJOR EQUIPMENT: List each piece of process equipment with its exact label as written:\n"
        "   - Compressors, pumps, motors, drivers -- read labels carefully, distinguishing 0 from O/C and 1 from I\n"
        "   - Vessels, drums, tanks\n"
        "   - Heat exchangers, coolers\n"
        "   - Skid boundaries and panel boundaries (dashed box labels)\n\n"
        "4. PIPE SPECIFICATIONS: List any pipe spec labels visible (e.g. 0.5-089-7, 1.0-089-7, 2.0-256-216C)\n\n"
        "5. PROCESS STREAMS: Named streams, supply lines, vent lines, drain lines\n\n"
        "6. NOTES/SAFETY: Any general notes, safety annotations, or legend content\n\n"
        "7. UNIQUE ELEMENTS: Only note elements that have specific engineering significance: "
        "unusual equipment configurations, non-standard connections, safety-critical markings, "
        "vendor-specific assemblies, or process features that distinguish this diagram from a typical one of its type. "
        "Do NOT note generic observations like 'diagram has a title block' or 'boundary boxes are present'.\n\n"
        "DO NOT list instrument tags here -- those are handled separately.\n"
        "If you cannot read something clearly, omit it rather than guessing.\n"
    )

    RECONCILIATION_PROMPT = (
        "You are an ISA 5.1 instrumentation specialist.\n\n"
        "Below is a RAW LIST of instrument tags extracted from multiple tile scans of a P&ID. "
        "Some may be duplicates, some may be misread, and some may be fabricated by the AI.\n\n"
        "Your job:\n"
        "1. Deduplicate -- merge identical tags\n"
        "2. Correct obvious character misreads using these rules:\n"
        "   - In tag PREFIXES: the letter I (capital i) is almost always an ISA function letter, not the digit 1\n"
        "     e.g. PD1-1610 should be corrected to PDI-1610\n"
        "   - In tag PREFIXES: the digit 0 (zero) should not appear -- if you see it, "
        "check whether it is a misread O or whether the whole prefix is invalid\n"
        "   - In tag NUMBERS (after the hyphen): digits only are expected; letters I and O "
        "should be corrected to 1 and 0 respectively if they appear in the number portion\n"
        "3. Where both PDI-XXXX and PDIT-XXXX appear with the same loop number, keep BOTH -- "
        "they are two separate instruments in the same loop\n"
        "4. Remove any tags whose prefix is not a valid ISA function letter combination\n"
        "5. Remove any tags that look like drawing numbers, dates, P.O. numbers, or contract numbers "
        "(7+ digit numbers, numbers containing slashes, numbers starting with year patterns like 19xx or 20xx)\n"
        "6. Flag any tag you remain uncertain about with a ? suffix\n\n"
        "RAW TAG LIST:\n"
        "{raw_tags}\n\n"
        "Return ONLY a clean deduplicated list, one tag per line. No commentary.\n"
    )

    PIPE_SPEC_PROMPT = (
        "You are reading a NARROW HORIZONTAL STRIP of a P&ID engineering drawing.\n\n"
        "YOUR ONLY JOB: Find and list every pipe specification label visible in this strip.\n"
        "Pipe specs appear as text inside rectangular boxes on or adjacent to pipe lines.\n"
        "They follow patterns like: SIZE-CLASS-SUFFIX (e.g. 0.5-DB9-7, 1.0-DB9-7, 2.0-256-216C, 1.0-356-416C)\n\n"
        "CHARACTER AMBIGUITY -- this is critical for pipe specs:\n"
        "- The letter B (uppercase B) and the digit 8 are commonly confused. "
        "Look at the character carefully: B has two bumps on the right side, 8 has two symmetric loops.\n"
        "- D and 0: D has a flat left vertical stroke, 0 is a closed oval.\n"
        "- Read EVERY character literally as you see it. Do NOT substitute or correct.\n"
        "- If a spec reads 0.5-DB9-7, write 0.5-DB9-7. Do not write 0.5-089-7.\n"
        "- If a spec reads 0.5-089-7, write 0.5-089-7. Do not write 0.5-DB9-7.\n\n"
        "There is also a NOTE BOX typically in the lower left area that says:\n"
        "  [pipe spec] TYP. FOR INSTRUMENTATION AND REFERENCE SIGNAL LINES\n"
        "Read that spec carefully -- it defines the typical spec for instrument lines.\n\n"
        "OUTPUT: one pipe spec per line, nothing else.\n"
        "Example:\n"
        "0.5-DB9-7\n"
        "1.0-DB9-7\n"
        "2.0-256-216C\n"
    )

    VALVE_SURVEY_PROMPT = (
        "You are an engineering drawing specialist examining a CROP of a P&ID.\n\n"
        "YOUR ONLY JOB: Catalogue every valve, fitting, and piping specialty item visible.\n\n"
        "VALVE SYMBOL GUIDE for P&IDs:\n"
        "- Check valve: bow-tie or arrowhead symbol on a line (allows flow one direction only)\n"
        "- Ball valve: filled solid square or circle on a line (quarter-turn isolation)\n"
        "- Gate valve: filled solid triangle pointing at line (on/off isolation)\n"
        "- Globe valve: circle with a line through it, or bowtie with circle (control/throttling)\n"
        "- Needle valve: small triangle or X symbol (fine flow control, instrumentation)\n"
        "- Control valve: globe/rotary body with actuator on top (diaphragm dome = pneumatic)\n"
        "- Solenoid valve: square symbol with S inside or coil symbol\n"
        "- Rupture disc / PSE: parallel lines or rectangular block across a line (bursting disc)\n"
        "- Orifice plate / restriction: double vertical lines across a pipe (flow restriction)\n"
        "- Filter element: diamond shape (FL- tagged)\n"
        "- Strainer: Y-shape or basket symbol\n"
        "- Spectacle blind: figure-8 symbol\n"
        "- Drain: small line with arrow pointing down\n"
        "- Vent: small line with arrow pointing up\n\n"
        "RULES:\n"
        "- List EVERY fitting visible regardless of size\n"
        "- For each item: identify its type, the pipe spec label on the line it is on, "
        "any tag (e.g. FCV-1611, FL-1610A), and any adjacent reference number\n"
        "- Reference numbers are small numbers (2-4 digits) near fittings -- "
        "note them as BOM reference numbers; state that a project BOM is needed to confirm meaning\n"
        "- Do NOT read instrument bubble tags (circles with text inside) -- focus only on fittings\n"
        "- If you cannot determine valve type, write UNKNOWN\n"
        "- A dashed rectangle around a group of fittings indicates a typical/repeated assembly\n\n"
        "OUTPUT FORMAT -- one item per line:\n"
        "- <valve/fitting type> | Line: <pipe spec> | Tag: <if present> | Ref#: <BOM number if present>\n"
        "Example:\n"
        "- Check valve | Line: 0.5-DB9-7 | Tag: none | Ref#: 231 (BOM ref -- project BOM needed)\n"
        "- Ball valve | Line: 0.5-DB9-7 | Tag: none | Ref#: 233 (BOM ref -- project BOM needed)\n"
        "- Rupture disc | Line: 2.0-356-416C | Tag: none | Ref#: 401 (BOM ref -- project BOM needed)\n"
        "- Orifice plate | Line: 0.5-DB9-7 | Tag: none | Ref#: 259\n"
    )

    # --- Verification pass: re-examines a tile flagged as ambiguous by the first valve
    # survey pass. Distinct from PIPE_SPEC_PROMPT (previously aliased here in error --
    # that alias meant the "detail zoom" pass, when it existed, was reading pipe specs
    # a second time instead of resolving symbol ambiguity).
    VALVE_DETAIL_ZOOM_PROMPT = (
        "You are re-examining a SMALL, HIGH-MAGNIFICATION crop of a P&ID or diagram. "
        "This crop was flagged as ambiguous or symbol-dense on a first pass -- your job is "
        "to resolve it with certainty, not to re-survey the whole area.\n\n"
        "SYMBOL DISAMBIGUATION -- read this before answering:\n"
        "- GATE valve vs NEEDLE valve: both can render as a triangle. A GATE valve's triangle "
        "sits directly ON the main process line, sized to match the line weight, no offset. "
        "A NEEDLE valve's triangle is SMALL, sits on a thin instrument impulse/takeoff line "
        "branching off the main line, and is usually near an instrument bubble it feeds. "
        "If the triangle is on a thin branch line near an instrument tag, it is a needle valve.\n"
        "- CHECK valve vs BALL valve: a check valve is a bow-tie / two-triangle arrowhead shape "
        "indicating one-way flow. A ball valve is a single filled circle or square directly on "
        "the line. Do not confuse a bow-tie (check) with two adjacent separate valve symbols.\n"
        "- ORIFICE PLATE / RESTRICTION vs CHECK VALVE: an orifice/restriction is two parallel "
        "bars perpendicular to the line, no directional arrowhead. An arrowhead or wedge shape "
        "means check valve, not orifice.\n"
        "- Reference numbers (2-4 digit numbers near a symbol) identify a BOM line item, not a "
        "valve type -- never infer type from the number, only from the drawn symbol shape.\n\n"
        "For EACH symbol in this crop, give your answer AND a short reason distinguishing it "
        "from the confusable alternative above.\n\n"
        "OUTPUT FORMAT -- one item per line:\n"
        "- <valve/fitting type> | Line: <pipe spec if visible> | Tag: <if present> | "
        "Ref#: <if present> | Why: <short clause>\n"
        "If, after this close look, you are still genuinely uncertain, write "
        "CANDIDATES: <type A> or <type B> instead of guessing a single type.\n"
    )

    # --- Non-piping-diagram document passes (data sheets, isometrics/GA, matrices) ---
    TABLE_FIELD_PROMPT = (
        "You are reading a scanned engineering document that is primarily tabular/field-based "
        "(e.g. a data sheet, equipment sizing report, proposal, or spec sheet), not a piping "
        "diagram.\n\n"
        "Extract every labelled field and every table exactly as written.\n"
        "RULES:\n"
        "- For label:value fields (e.g. 'Design Pressure: 150 psig'), extract as Label = Value\n"
        "- For tables, reproduce each row with its column headers\n"
        "- Preserve units exactly as written\n"
        "- Do not calculate, convert, or infer values not explicitly present\n"
        "- If a field or cell is blank/illegible, write N/A\n\n"
        "OUTPUT FORMAT:\n"
        "FIELDS:\n"
        "- <Label>: <Value>\n\n"
        "TABLES:\n"
        "<table name/title if any>\n"
        "| <header1> | <header2> | ... |\n"
        "| <row values> |\n\n"
        "(repeat for each table found)\n"
    )

    DIMENSION_CALLOUT_PROMPT = (
        "You are reading a scanned isometric or general arrangement (GA) drawing.\n\n"
        "Extract every dimension, weld number, coordinate, elevation, and callout visible.\n"
        "RULES:\n"
        "- Dimensions appear as numbers with arrows or extension lines -- record value and units\n"
        "- Weld numbers are small circled or boxed numbers along a pipe run -- list each with its "
        "approximate location description (e.g. 'near flange at north end')\n"
        "- Elevations/coordinates are typically labelled EL. or N/E/W/S with a numeric value\n"
        "- Note pipe spec labels and line numbers if present\n"
        "- Do not invent values not explicitly shown\n\n"
        "OUTPUT FORMAT:\n"
        "DIMENSIONS:\n- <value> <units>: <what it measures>\n\n"
        "WELD NUMBERS:\n- <number>: <location description>\n\n"
        "ELEVATIONS / COORDINATES:\n- <label>: <value>\n\n"
        "OTHER CALLOUTS:\n- <text as written>\n"
    )

    MATRIX_PROMPT = (
        "You are reading a scanned cause-and-effect matrix or HAZOP worksheet.\n\n"
        "RULES:\n"
        "- Extract row labels (causes/deviations) and column labels (effects/actions) exactly as "
        "written\n"
        "- For each marked intersection (X, dot, or shaded cell), record which row/column it links\n"
        "- Preserve any severity/likelihood ratings shown\n"
        "- Do not infer a mark where none is visibly present\n\n"
        "OUTPUT FORMAT:\n"
        "ROWS:\n- <row label>\n\n"
        "COLUMNS:\n- <column label>\n\n"
        "MARKED INTERSECTIONS:\n- <row label> -> <column label>\n"
    )

    # Maps a classifier/AI doc_type guess to which pass category should run.
    # Anything not listed (including "Unknown") defaults to the full diagram pipeline,
    # matching the existing coordinator philosophy: unclassified process content should
    # still get the thorough pass rather than a shallow one.
    _ISO_GA_TYPES = {"Isometric", "GA Drawing"}
    _TABULAR_TYPES = {"Data Sheet", "Equipment Sizing", "Proposal", "Report", "Heat & Energy Balance"}
    _MATRIX_TYPES = {"Cause & Effect", "Hazop"}

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

    def extract_vision_description(self, path: Path, api_key: str = "", doc_type_hint: str = "") -> str:
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

        return self._multi_pass_analysis(pil_image, mime, api_key, doc_type_hint=doc_type_hint)

    def _categorize_doc_type(self, doc_type_hint: str) -> str:
        """Which pass set applies. Unrecognised/Unknown types default to the full
        diagram pipeline rather than a shallow one -- an unclassified drawing is more
        likely under-classified than genuinely non-diagrammatic."""
        dt = (doc_type_hint or "").strip()
        if dt in self._ISO_GA_TYPES:
            return "iso_ga"
        if dt in self._MATRIX_TYPES:
            return "matrix"
        if dt in self._TABULAR_TYPES:
            return "tabular"
        return "diagram"

    def _adaptive_grid(self, width: int, height: int, target_edge: int = 1900) -> tuple[int, int]:
        """Compute a tile grid sized so each tile's base edge lands at/under target_edge px
        -- OpenAI's vision encoder downsamples anything larger before it ever reaches the
        model, so tiles bigger than this waste the resolution the rasteriser produced.
        target_edge is set with headroom under the ~2048px internal cap; overlap padding
        can push the largest interior tiles a few percent past that in practice. Fully
        compensating for worst-case double-sided overlap would need ~40% more tiles for a
        ~3-4% resolution gain on those tiles -- not worth it here, because the pass that
        actually needs pixel-perfect resolution on hard cases (valve symbol typing) already
        gets a dedicated, properly-sized re-crop via the zoom-verification pass below when a
        tile is flagged ambiguous. This grid just needs to be good enough for the first pass."""
        cols = max(1, -(-width // target_edge))    # ceil division
        rows = max(1, -(-height // target_edge))
        return cols, rows

    def _needs_zoom_verification(self, tile_result: str) -> bool:
        if not tile_result:
            return False
        lower = tile_result.lower()
        return any(t in lower for t in ("unknown", "uncertain", "candidates:"))

    def _multi_pass_analysis(self, pil_image, mime: str, api_key: str, doc_type_hint: str = "") -> str:
        width, height = pil_image.size
        category = self._categorize_doc_type(doc_type_hint)

        # --- Pass 1: Context (full image, layout / title block / equipment) -- always runs ---
        context_b64 = self._pil_to_b64(pil_image)
        context_text = self._call_vision(context_b64, mime, self.CONTEXT_PROMPT, api_key, max_tokens=1200)
        description = "=== CONTEXT ANALYSIS ===\n" + context_text

        if category == "tabular":
            table_b64 = self._pil_to_b64(pil_image)
            table_text = self._call_vision(table_b64, mime, self.TABLE_FIELD_PROMPT, api_key, max_tokens=1500)
            description += "\n\n=== FIELDS AND TABLES ===\n" + table_text
            return description

        if category == "matrix":
            matrix_b64 = self._pil_to_b64(pil_image)
            matrix_text = self._call_vision(matrix_b64, mime, self.MATRIX_PROMPT, api_key, max_tokens=1500)
            description += "\n\n=== MATRIX CONTENTS ===\n" + matrix_text
            return description

        if category == "iso_ga":
            diagram_body = pil_image.crop((0, int(height * 0.03), width, int(height * 0.9)))
            cols, rows = self._adaptive_grid(diagram_body.size[0], diagram_body.size[1])
            callout_results = []
            for tile in self._make_tiles(diagram_body, cols=cols, rows=rows, overlap_frac=0.12):
                tile_b64 = self._pil_to_b64(tile)
                result = self._call_vision(tile_b64, mime, self.DIMENSION_CALLOUT_PROMPT, api_key, max_tokens=500)
                if result.strip():
                    callout_results.append(result.strip())
            description += "\n\n=== DIMENSIONS AND CALLOUTS ===\n" + "\n---\n".join(callout_results)

            spec_results = []
            spec_cols = max(4, -(-width // 1900))  # single-row strips: width-only
            for tile in self._make_tiles(diagram_body, cols=spec_cols, rows=1, overlap_frac=0.1):
                tile_b64 = self._pil_to_b64(tile)
                result = self._call_vision(tile_b64, mime, self.PIPE_SPEC_PROMPT, api_key, max_tokens=300)
                if result.strip():
                    spec_results.append(result.strip())
            description += "\n\n=== PIPE SPECIFICATIONS ===\n" + "\n".join(spec_results)
            return description

        # --- category == "diagram": P&ID / System Diagram / PFD / Unknown -- full pipeline ---

        # --- Pass 2: Instrument tags -- single adaptive-resolution pass (replaces the old
        # fixed 3x2-then-conditional-5x3 approach, which duplicated coverage on large
        # drawings while still leaving tiles above the model's internal resize cap) ---
        all_raw_tags = []
        tile_texts = []
        i_cols, i_rows = self._adaptive_grid(width, height)
        for i, tile in enumerate(self._make_tiles(pil_image, cols=i_cols, rows=i_rows, overlap_frac=0.12)):
            tile_b64 = self._pil_to_b64(tile)
            result = self._call_vision(tile_b64, mime, self.TILE_INSTRUMENT_PROMPT, api_key, max_tokens=600)
            tile_texts.append(f"[Tile {i+1}]\n{result}")
            all_raw_tags.extend(self._parse_tag_list(result))

        reconciled_tags = self._reconcile_tags(self._validate_tags_local(all_raw_tags), api_key)

        # --- Pass 3: Pipe spec reading -- horizontal strips across diagram body ---
        pipe_spec_results = []
        diagram_body = pil_image.crop((0, int(height * 0.05), width, int(height * 0.82)))
        spec_cols = max(4, -(-diagram_body.size[0] // 1900))  # single-row strips: width-only
        for tile in self._make_tiles(diagram_body, cols=spec_cols, rows=1, overlap_frac=0.1):
            tile_b64 = self._pil_to_b64(tile)
            result = self._call_vision(tile_b64, mime, self.PIPE_SPEC_PROMPT, api_key, max_tokens=300)
            if result.strip():
                pipe_spec_results.append(result.strip())

        pipe_specs_unique = []
        seen_specs = set()
        for block in pipe_spec_results:
            for line in block.splitlines():
                spec = line.strip().strip("-").strip()
                if spec and spec not in seen_specs:
                    seen_specs.add(spec)
                    pipe_specs_unique.append(spec)

        pipe_spec_section = "\n=== PIPE SPECIFICATIONS (dedicated pass) ===\n" + "\n".join(pipe_specs_unique)

        # --- Pass 4: Valve survey -- adaptive grid over the diagram body, every tile ---
        valve_results = []
        zoom_results = []
        v_cols, v_rows = self._adaptive_grid(diagram_body.size[0], diagram_body.size[1])
        for tile in self._make_tiles(diagram_body, cols=v_cols, rows=v_rows, overlap_frac=0.15):
            tile_b64 = self._pil_to_b64(tile)
            result = self._call_vision(tile_b64, mime, self.VALVE_SURVEY_PROMPT, api_key, max_tokens=700)
            if result.strip() and len(result.strip()) > 20:
                valve_results.append(result.strip())

                # --- Pass 5 (targeted): only re-examine THIS tile at higher magnification
                # if the first pass itself flagged ambiguity. This gets close-inspection
                # accuracy on the handful of genuinely ambiguous symbols per drawing
                # instead of paying for a blanket high-zoom pass over every tile. ---
                if self._needs_zoom_verification(result):
                    for sub in self._make_tiles(tile, cols=2, rows=2, overlap_frac=0.2):
                        sub_b64 = self._pil_to_b64(sub)
                        zoom_out = self._call_vision(
                            sub_b64, mime, self.VALVE_DETAIL_ZOOM_PROMPT, api_key, max_tokens=500
                        )
                        if zoom_out.strip() and len(zoom_out.strip()) > 15:
                            zoom_results.append(zoom_out.strip())

        valve_section = "\n\n=== VALVE AND FITTING SURVEY ===\n" + "\n---\n".join(valve_results)
        zoom_section = ""
        if zoom_results:
            zoom_section = (
                "\n\n=== VALVE DETAIL ZOOM (verification pass on flagged-ambiguous items -- "
                "TAKES PRECEDENCE over the general survey above for the same item) ===\n"
                + "\n---\n".join(zoom_results)
            )

        description += (
            "\n\n=== INSTRUMENT TAGS (multi-tile extraction) ===\n"
            + "\n".join(reconciled_tags)
            + pipe_spec_section
            + valve_section
            + zoom_section
            + "\n\n=== RAW TILE OUTPUTS ===\n" + "\n\n".join(tile_texts)
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
        combined = filename + " " + text

        explicit_patterns = [
            (r"Project\s*(?:No|Number|#|Num)[.:\s]+([A-Z]{2,4}[-_]?\d{2,6})", 1),
            (r"\b(PRJ[-_]?\d{2,6})\b", 1),
            (r"\b(JOB[-_]?\d{2,6})\b", 1),
        ]
        for pat, group in explicit_patterns:
            m = re.search(pat, combined, re.IGNORECASE)
            if m:
                candidate = m.group(group).strip()
                if re.match(r"^\d{7,}$", candidate):
                    continue
                return candidate

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
