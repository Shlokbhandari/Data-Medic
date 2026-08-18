import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
from llm import inference


def test_inference_uses_groq_when_successful():
    mock_choice = MagicMock()
    mock_choice.message.content = "Groq response"
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_completion

    with patch('llm.Groq', return_value=mock_client):
        content, backend = inference("test prompt")

    assert content == "Groq response"
    assert backend == "Groq"
    mock_client.chat.completions.create.assert_called_once_with(
        messages=[{"role": "user", "content": "test prompt"}],
        model="openai/gpt-oss-120b",
    )


def test_inference_falls_back_to_ollama_when_groq_fails():
    mock_groq_client = MagicMock()
    mock_groq_client.chat.completions.create.side_effect = Exception("Groq connection timeout")

    mock_ollama_resp = MagicMock()
    mock_ollama_resp.json.return_value = {"response": "Ollama fallback response"}

    with patch('llm.Groq', return_value=mock_groq_client), \
         patch('llm.requests.post', return_value=mock_ollama_resp) as mock_post:
        content, backend = inference("test prompt")

    assert content == "Ollama fallback response"
    assert backend == "Ollama"
    mock_post.assert_called_once_with(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3.2",
            "prompt": "test prompt",
            "stream": False
        }
    )
