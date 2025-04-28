from generator import generate_policy_data, save_manual_overrides
from evaluator import evaluate_dmv_entry
import json
import time
import subprocess


TEST_MODE = True

if TEST_MODE:
    states = ["California", "New York", "Texas", "New Jersey", "Florida", "Louisiana", "Georgia", "Illinois"] 
    ##states = ["California"]
else:
    states = [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut",
    "Delaware", "District of Columbia", "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa",
    "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan",
    "Minnesota", "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire",
    "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio",
    "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota",
    "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington", "West Virginia",
    "Wisconsin", "Wyoming"]
    

final_results = []

for state in states:
    print(f"\n=== Processing {state} ===")
    gen_data = generate_policy_data(state)

    if not gen_data:
        print(f"Skipping {state}")
        continue

    # Skip evaluation if manual validation needed
    if gen_data['plate_retention_policy'] == "Manual validation required":
        final_results.append(gen_data)
        print(f"⚠️ {state} added for manual validation.")
        continue

    eval_data = evaluate_dmv_entry(gen_data)

    if eval_data["valid"]:
        combined = {
            **gen_data,
            "verified_policy_content": True,
            "confidence": eval_data["confidence"],
            "final_summary": eval_data["final_summary"],
            "final_quote": eval_data["final_quote"]
        }
        final_results.append(combined)
        print(f"✅ {state} passed evaluation")
    else:
        print(f"❌ {state} rejected: {eval_data['issues']}")
        final_results.append(gen_data)

    time.sleep(3)

with open("data.json", "w") as f:
    json.dump(final_results, f, indent=2)

save_manual_overrides()
print("\nData written to data.json and manual_overrides.json")

# Run the generate_webpage.py script after successful data generation
print("\n✅ All states processed. Generating HTML...")
subprocess.run(["python", "generate_webpage.py"], check=True)