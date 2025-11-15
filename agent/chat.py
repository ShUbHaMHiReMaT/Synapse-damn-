from agent import run_agent

# Mock claim data (replace with real OCR + YOLO later)
mock_ocr = {
    "policy_number": "FS-123456",
    "incident_date": "2025-01-11",
    "incident_description": "Severe collision on right side."
}

mock_yolo = {
    "damage_location": "Right Door",
    "damage_severity": "Moderate"
}

print("Agent ready. Ask anything about the claim.\n")

while True:
    q = input("You: ")

    if q.lower() in ["exit", "quit", "bye"]:
        print("Agent: Understood. Ending the session.")
        break

    response = run_agent(mock_ocr, mock_yolo, q)

    try:
        # Extract the actual assistant text
        message = response["choices"][0]["message"]["content"]
        print("\nAgent:", message, "\n")
    except Exception as e:
        print("\nAgent: I encountered an unexpected issue.")
        print("Error:", e)
        print("Full response:", response, "\n")
