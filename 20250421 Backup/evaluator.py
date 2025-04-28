from openai import OpenAI
import os
import json
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def evaluate_dmv_entry(entry):
    #print(f"\n🔍 Evaluating {entry['state']}...")

    prompt = f"""
        You are evaluating whether this DMV quote provides clear evidence about whether a license plate is retained by the seller,  
        should be transferred with the vehicle, or surrendered to the DMV when a vehicle is sold or transferred. 
        Your task is to classify the quote and provide a summary of the policy. 

        Inputs for {entry['state']}:
        Summary: "{entry['policy_summary']}"
        Quote: "{entry['dmv_excerpt']}"
        Source: {entry['source_url']}

        Classify confidence based on the following criteria:

        - **High Confidence** → The quote:
        - Explicitly states what happens to license plates when a vehicle is sold or transferred (e.g., “plates stay with vehicle”, “plates must be surrendered when selling”, etc.)
        - AND the source is an official DMV or state government website.

        - **Medium - Validation Needed** → Applies when:
        - The quote is vague, indirect, or implies rather than states the rule
        - OR the quote talks about plate surrender unrelated to vehicle sale (e.g., surrender due to insurance cancellation or moving out of state)
        - OR the source is a non-government site that appears reputable

        - **Low - Manual Validation Needed** → Applies when:
        - The quote does not mention license plate policy at all
        - OR refers only to insurance cancellation, registration renewal, or other unrelated processes
        - OR the source is unreliable or not clearly a DMV or government site

        Output only valid JSON structured exactly like this:

        Return JSON:
        {{
        "valid": true or false,
        "confidence": "High" or "Medium - Validation Needed" or "Low - Manual Validation Needed",
        "issues": "Brief reason for confidence score, ideally 3–5 words (e.g., 'Not specific to vehicle sale', 'Unofficial site', 'Unclear policy').",
        "final_summary": "{entry['policy_summary']}",
        "final_quote": "{entry['dmv_excerpt']}"
        }}
        """

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    print(f"✅ GPT evaluation complete for {entry['state']}")
    print(f"→ Confidence: {entry.get('confidence')}")


    try:
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Eval parsing failed for {entry['state']}: {e}")
        return {"valid": False, "confidence": "Low", "issues": "Parsing error"}
