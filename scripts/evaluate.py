"""Run reviewed semantic examples against the deterministic MVP."""
from __future__ import annotations
import json
from backend.app import AnalyzeRequest, _run
from semantic import GOLDEN_EXAMPLES

def evaluate() -> dict[str, object]:
    passed = failed = 0
    details = []
    for case in GOLDEN_EXAMPLES:
        result = _run(AnalyzeRequest(query=case["question"]))
        ok = result.get("next_action") == ("clarify" if case.get("clarification_required") else "done") and not (result.get("error") and not case.get("clarification_required"))
        if ok:
            passed += 1
        else:
            failed += 1
        details.append({"id": case["id"], "ok": ok, "next_action": result.get("next_action"), "error": result.get("error")})
    return {"total": len(GOLDEN_EXAMPLES), "passed": passed, "failed": failed, "details": details}

if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
