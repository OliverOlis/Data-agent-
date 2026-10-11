from scripts.evaluate import evaluate

def test_golden_evaluation_has_high_basic_success_rate():
    result = evaluate()
    assert result["total"] == 20
    assert result["passed"] >= 18
