"""
run_evals.py
Reads test_cases.csv, runs every message through run_agent(), and reports:
  - Classification accuracy (got_category == expected_category)
  - Escalation accuracy (got_escalation == expected_escalation)
  - Per-row pass/fail breakdown
  - Saves full results (including drafted replies) to evals/results/results_TIMESTAMP.csv

Re-run this any time you change a prompt to catch regressions.
Cost note: each non-escalation row makes 1 Haiku + 1 Sonnet call.
Escalation rows skip Haiku (keyword match fires first). Caching keeps cost low.
"""

import csv
import os
import sys
from datetime import datetime

# Allow importing agent.py from the parent directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent import run_agent

TEST_CASES_PATH = os.path.join(os.path.dirname(__file__), "test_cases.csv")
RESULTS_DIR     = os.path.join(os.path.dirname(__file__), "results")


def load_test_cases() -> list[dict]:
    with open(TEST_CASES_PATH, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def run_evals():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    test_cases = load_test_cases()
    total = len(test_cases)

    print(f"LuxePress CS Agent — Eval Run")
    print(f"Test cases: {total}")
    print(f"{'─'*65}")

    results      = []
    cat_correct  = 0
    esc_correct  = 0

    for i, tc in enumerate(test_cases, 1):
        message       = tc["message"].strip('"')
        expected_cat  = tc["expected_category"].strip()
        expected_esc  = tc["expected_escalation"].strip().lower() == "true"
        notes         = tc.get("notes", "")

        # Run the full agent pipeline
        result = run_agent(message)

        got_cat = result["category"]
        got_esc = result["escalate"]

        cat_ok = got_cat == expected_cat
        esc_ok = got_esc == expected_esc

        if cat_ok:  cat_correct += 1
        if esc_ok:  esc_correct += 1

        # Per-row status line
        row_pass = cat_ok and esc_ok
        marker   = "✅" if row_pass else "❌"
        cat_mark = "✓" if cat_ok else f"✗ got '{got_cat}'"
        esc_mark = "✓" if esc_ok else f"✗ got {got_esc}"

        print(f"[{i:02d}/{total}] {marker}  {message[:52]:<52}")
        if not row_pass:
            print(f"        category: {cat_mark}  |  escalation: {esc_mark}")
            print(f"        expected: {expected_cat} / {expected_esc}")

        results.append({
            "id":                   i,
            "message":              message,
            "notes":                notes,
            "expected_category":    expected_cat,
            "got_category":         got_cat,
            "category_correct":     cat_ok,
            "expected_escalation":  expected_esc,
            "got_escalation":       got_esc,
            "escalation_correct":   esc_ok,
            "escalation_reason":    result["escalation_reason"],
            "sop_used":             ", ".join(result["sop_used"]),
            "draft":                result["draft"],
        })

    # ── Summary ───────────────────────────────────────────────────────────────
    both_correct = sum(1 for r in results if r["category_correct"] and r["escalation_correct"])

    print(f"\n{'═'*65}")
    print(f"  Classification accuracy : {cat_correct}/{total}  ({cat_correct/total*100:.0f}%)")
    print(f"  Escalation accuracy     : {esc_correct}/{total}  ({esc_correct/total*100:.0f}%)")
    print(f"  Both correct            : {both_correct}/{total}  ({both_correct/total*100:.0f}%)")
    print(f"{'═'*65}")

    # ── Save results ──────────────────────────────────────────────────────────
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path  = os.path.join(RESULTS_DIR, f"results_{timestamp}.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    print(f"\n  Drafted replies saved to: {out_path}")
    print(f"  Open in Excel or any CSV viewer to review responses.\n")


if __name__ == "__main__":
    run_evals()
