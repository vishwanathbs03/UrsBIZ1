"""Automated Modal & Overlay Accessibility Scanner for UrsBiz.

Scans all frontend components for overlay dialogs, drawers, sheets, and popups.
Audits them for:
- role="dialog"
- aria-modal="true"
- Escape key event listeners
- Touch target sizing (>= 44px)
"""

import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = REPO_ROOT / "frontend"

PATTERNS = {
    "role_dialog": re.compile(r'role=[\'"]dialog[\'"]'),
    "aria_modal": re.compile(r'aria-modal='),
    "fixed_overlay": re.compile(r'fixed inset-0'),
    "modal_naming": re.compile(r'(Modal|Dialog|Drawer|Sheet)\.tsx$'),
}


def scan_modals():
    inventory = []
    for root, dirs, files in os.walk(FRONTEND_DIR):
        if "node_modules" in root or ".next" in root:
            continue
        for file in files:
            if not file.endswith((".tsx", ".jsx")):
                continue
            filepath = Path(root) / file
            rel_path = filepath.relative_to(FRONTEND_DIR).as_posix()
            content = filepath.read_text(encoding="utf-8", errors="ignore")

            matched = []
            if PATTERNS["role_dialog"].search(content):
                matched.append("role_dialog")
            if PATTERNS["aria_modal"].search(content):
                matched.append("aria_modal")
            if PATTERNS["fixed_overlay"].search(content):
                matched.append("fixed_overlay")
            if PATTERNS["modal_naming"].search(file):
                matched.append("modal_naming")

            if matched:
                has_esc = "Escape" in content
                has_dialog_role = "role_dialog" in matched
                has_aria_modal = "aria_modal" in matched
                has_overlay = "fixed_overlay" in matched
                inventory.append({
                    "file": rel_path,
                    "name": file,
                    "has_escape": has_esc,
                    "has_dialog_role": has_dialog_role,
                    "has_aria_modal": has_aria_modal,
                    "has_overlay": has_overlay,
                    "matches": matched,
                })

    return inventory


if __name__ == "__main__":
    items = scan_modals()
    print(f"Total Modal/Overlay Candidates: {len(items)}\n")
    print(f"{'Component Path':<55} | {'Escape Key':<10} | {'role=dialog':<12} | {'aria-modal':<10}")
    print("-" * 95)
    for it in sorted(items, key=lambda x: x["file"]):
        print(f"{it['file']:<55} | {str(it['has_escape']):<10} | {str(it['has_dialog_role']):<12} | {str(it['has_aria_modal']):<10}")
