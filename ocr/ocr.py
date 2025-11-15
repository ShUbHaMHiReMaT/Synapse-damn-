import base64
import google.generativeai as genai
from dotenv import load_dotenv
import os

# ----------------------------------------------
# LOAD ENVIRONMENT VARIABLES
# ----------------------------------------------
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

model = genai.GenerativeModel("gemini-2.5-flash")


# ----------------------------------------------
# ENCODE IMAGE
# ----------------------------------------------
def load_image_as_b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


# ----------------------------------------------
# EXTRACT CLAIM FIELDS
# ----------------------------------------------
def extract_claim_fields(image_path):
    img_b64 = load_image_as_b64(image_path)

    prompt = """
Extract the following fields from the insurance claim form image.

Return PURE JSON only:
{
  "policy_number": "",
  "incident_date": "",
  "incident_description": ""
}

Rules:
- Decode handwriting fully.
- Extract policy number exactly as written.
- Extract date of loss (DD/MM/YYYY).
- Extract the handwritten cause-of-loss description.
- Do not include commentary.
"""

    result = model.generate_content(
        [prompt, {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}}]
    )
    
    return result.text


# ----------------------------------------------
# RUN TEST
# ----------------------------------------------
if __name__ == "__main__":
    print(extract_claim_fields("IMG_20251115_132123.jpg"))
