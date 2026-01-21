from unittest.mock import MagicMock, patch

from pandoraspec.config import PandoraConfig
from pandoraspec.modules.ai_judge import run_ai_assessment

# Mock data
RESULTS_PASS = {"module_A": [{"status": "PASS", "issue": "Drift", "details": "ok"}]}
RESULTS_FAIL_RESILIENCE = {
    "module_B": [
        {"status": "FAIL", "issue": "Rate Limiting", "details": "Missing 429 response during flood", "severity": "MEDIUM"}
    ]
}

def test_ai_module_skipped_no_key():
    config = PandoraConfig(openai_api_key=None)
    results = run_ai_assessment(None, RESULTS_PASS, config)
    assert results == []

@patch.dict('sys.modules', {'openai': MagicMock()})
def test_ai_module_pass_scenario():
    # Setup Mock
    import openai  # Now it exists
    mock_client = MagicMock()
    # We need to assign it to the mocked module
    openai.OpenAI.return_value = mock_client

    mock_response = MagicMock()
    mock_response.choices[0].message.content = '{"risk_score": 0, "verdict": "PASS", "executive_summary": "All good."}'
    mock_client.chat.completions.create.return_value = mock_response

    config = PandoraConfig(openai_api_key="sk-test-key")
    results = run_ai_assessment(None, RESULTS_PASS, config)

    assert len(results) == 1
    assert results[0]["module"] == "E"
    assert results[0]["status"] == "PASS"
    assert "Risk Score: 0/10" in results[0]["details"]
    assert "All good" in results[0]["details"]

@patch.dict('sys.modules', {'openai': MagicMock()})
def test_ai_module_fail_scenario():
    import openai
    mock_client = MagicMock()
    openai.OpenAI.return_value = mock_client

    mock_response = MagicMock()
    mock_response.choices[0].message.content = '{"risk_score": 8, "verdict": "FAIL", "executive_summary": "Critical resilience failure detected."}'
    mock_client.chat.completions.create.return_value = mock_response

    config = PandoraConfig(openai_api_key="sk-test-key")
    results = run_ai_assessment(None, RESULTS_FAIL_RESILIENCE, config)

    assert len(results) == 1
    assert results[0]["module"] == "E"
    assert results[0]["status"] == "FAIL"
    assert "Risk Score: 8/10" in results[0]["details"]
    assert "Critical resilience" in results[0]["details"]

@patch.dict('sys.modules', {'openai': MagicMock()})
def test_ai_module_invalid_response():
    import openai
    mock_client = MagicMock()
    openai.OpenAI.return_value = mock_client

    mock_response = MagicMock()
    mock_response.choices[0].message.content = 'NOT A JSON'
    mock_client.chat.completions.create.return_value = mock_response

    config = PandoraConfig(openai_api_key="sk-test-key")
    results = run_ai_assessment(None, RESULTS_PASS, config)

    # Should handle error gracefully
    assert len(results) == 1
    assert results[0]["issue"] == "AI Assessment Error"
    assert results[0]["status"] == "FAIL"
