import os
import requests
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

def inference(prompt):
    # Try Groq first
    try:
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="openai/gpt-oss-120b",
        )
        return chat_completion.choices[0].message.content, "Groq"
    # If Groq fails, fall back to Ollama
    except Exception as e:
        print(f"Groq failed ({e}), falling back to Ollama...")
        r = requests.post("http://localhost:11434/api/generate", json={
            "model": "llama3.2",
            "prompt": prompt,
            "stream": False
        })
        return r.json()["response"], "Ollama"
