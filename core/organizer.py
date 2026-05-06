from __future__ import annotations

import shutil
from pathlib import Path


class Organizer:

    def __init__(self, output_root: Path):
        self.output_root = Path(output_root)

    def organize(self, results: list[dict]) -> dict:
        self.output_root.mkdir(parents=True, exist_ok=True)

        moved = 0
        folders_touched: set[Path] = set()

        for r in results:
            src = Path(r.get("original_path", ""))
            if not src.exists():
                continue

            dest_folder = self._resolve_folder(r)
            dest_folder.mkdir(parents=True, exist_ok=True)
            folders_touched.add(dest_folder)

            dest_file = dest_folder / r.get("suggested_name", src.name)
            dest_file = self._avoid_collision(dest_file)

            shutil.copy2(src, dest_file)
            r["organised_path"] = str(dest_file)
            moved += 1

        tree = self._build_tree(self.output_root)

        return {
            "moved": moved,
            "folders_created": len(folders_touched),
            "tree": tree,
        }

    def _resolve_folder(self, r: dict) -> Path:
        meta = r.get("metadata", {})
        doc_type = r.get("doc_type", "Unsorted")

        project_num = meta.get("project_number", "").strip()
        client = meta.get("client", "").strip()

        if project_num:
            project_folder = self._sanitize(project_num)
        elif client:
            project_folder = self._sanitize(client)
        else:
            project_folder = "Unassigned"

        type_folder = self._sanitize(doc_type)
        return self.output_root / project_folder / type_folder

    def _avoid_collision(self, dest: Path) -> Path:
        if not dest.exists():
            return dest
        stem = dest.stem
        suffix = dest.suffix
        counter = 1
        while dest.exists():
            dest = dest.parent / f"{stem}_{counter}{suffix}"
            counter += 1
        return dest

    def _sanitize(self, text: str) -> str:
        import re
        text = re.sub(r"[^\w\s\-]", "", text)
        text = re.sub(r"\s+", "_", text.strip())
        return text or "Unsorted"

    def _build_tree(self, root: Path, prefix: str = "") -> str:
        lines = []
        children = sorted(root.iterdir()) if root.exists() else []
        for i, child in enumerate(children):
            connector = "└── " if i == len(children) - 1 else "├── "
            lines.append(prefix + connector + child.name)
            if child.is_dir():
                extension = "    " if i == len(children) - 1 else "│   "
                lines.append(self._build_tree(child, prefix + extension))
        return "\n".join(l for l in lines if l)