import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


def run_agent(form_data, image_data, question=None):

    url = "https://api.groq.com/openai/v1/chat/completions"

    # SYSTEM PROMPT (normal text mode)
    system_prompt = """
You are the FinSecure Claim Triage Reasoning Agent.
You speak in normal, clear, professional text. Do not use JSON in your responses unless explicitly asked.

You receive structured claim data which contains:
- OCR-extracted fields (policy number, incident date, incident description)
- Computer Vision analysis (damage location and severity)

Your responsibilities:
1. Summarize the claim in natural language.
2. Compare the claimant’s description with the detected damage.
3. Identify inconsistencies or possible fraud indicators.
4. Provide clear reasoning in normal sentences.
5. Give a triage decision using one of the following categories:
   - Auto-Approve
   - Flag for Review
   - High Priority
   - Fraud Risk
6. Answer the user's follow-up questions conversationally.
7. Never respond in JSON unless the user explicitly requests JSON.
8. Maintain calm, precise, confident explanations.
"""

    # Combine all claim data + question
    user_input = {
        "form_data": form_data,
        "image_analysis": image_data,
        "question": question
    }

    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_input)}
        ]
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)
    return response.json()
