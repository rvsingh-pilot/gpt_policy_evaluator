from openai import OpenAI
import os
import json
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def evaluate_dmv_entry(entry):
    prompt = f"""
        You are evaluating whether this DMV quote provides clear evidence about whether a license plate is retained by the seller,  
        should be transferred with the vehicle, or surrendered to the DMV when a vehicle is sold or transferred. 
        Your task is to classify the quote and provide a summary of the policy. 

        Inputs for {entry['state']}:
        Summary: "{entry['policy_summary']}"
        Quote: "{entry['dmv_excerpt']}"
        Source: {entry['source_url']}

        Classify confidence based on this criteria:
        - High Confidence → Quote explicitly refers to license plates staying with the owner or the vehicle, or if the plates must be 
        surrendered to the DMV (e.g., "plates stay with vehicle", "plates remain", "plates must be removed", "plates must be surrendered") 
        and the source URL is an official DMV site or official state government website.
        - Medium - Validation Needed → Quote exists but is indirect, vague, or may require interpretation (e.g., references surrendering plates without clear context) 
        or the source URL is not an official government website (but does appear reputable).  
        - Low Confidence → No quote provided,  quote does not mention plates or plate transfer policy at all, or the source URL does not seem reputable.

        Output only valid JSON structured exactly like this:

        Return JSON:
        {{
        "valid": true or false,
        "confidence": "High" or "Medium - Validation Needed" or "Low - Manual Validation Needed",
        "issues": "Explain any concerns or why manual validation may be needed.",
        "final_summary": "{entry['policy_summary']}",
        "final_quote": "{entry['dmv_excerpt']}"
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
