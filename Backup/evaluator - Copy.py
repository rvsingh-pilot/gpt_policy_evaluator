from openai import OpenAI
import os
import json
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def evaluate_dmv_entry(entry):
    prompt = f"""
Evaluate this DMV policy for {entry['state']}.

Summary: "{entry['policy_summary']}"
Quote: "{entry['dmv_excerpt']}"
Source: {entry['source_url']}

Return JSON:
{{
  "valid": true or false,
  "confidence": "",
  "issues": "",
  "final_summary": "",
  "final_quote": ""
}}
"""

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )

    try:
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Eval parsing failed for {entry['state']}: {e}")
        return {"valid": False, "confidence": "Low", "issues": "Parsing error"}
