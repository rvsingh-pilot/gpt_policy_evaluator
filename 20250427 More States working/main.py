from generator import generate_policy_data, save_manual_overrides
from evaluator import evaluate_dmv_entry
import json
import time
import subprocess
import os

# Current implementation will skip over states that already have high-confidence entries in data.json
# Will need some modification to regenerate all states regardless of existing data based on last updated run (e.g., if older
# than 3 months))

TEST_MODE = True #True only a subset of states, False for all states

if TEST_MODE:
    #states = ["Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut",
    #"Delaware", "District of Columbia", "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa"]
    #states = ["Kansas", "Kentucky", "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan",
    #"Minnesota", "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire"]
    #states = ["New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio",
    #"Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota"]
    #states = ["Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington", "West Virginia",
    #"Wisconsin", "Wyoming"]
    
    #states = ["Illinois", "Massachusetts"]
    states = ["Connecticut"]
    #states = ["Illinois", "Massachusetts", "Michigan", "Nebraska", "Nevada", "New Hampshire", "South Carolina", "Tennessee",
    #          "West Virginia", "Wisconsin"]
    #states = ["California", "New York", "Texas", "New Jersey", "Florida", "Louisiana", "Georgia", "Illinois"] 
    #states = ["Georgia"]
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
    

#Load existing data if available
existing_data = {}
if os.path.exists("data.json"):
    with open("data.json", "r", encoding="utf-8") as f:
        for entry in json.load(f):
            existing_data[entry["state"]] = entry

final_results = []

for state in states:
    print(f"\n=== Processing {state} ===")

    # ✅ Skip if existing entry has High confidence
    if state in existing_data and existing_data[state].get("confidence", "").startswith("High"):
        print(f"⏩ Skipping {state} — already has high-confidence entry.")
        final_results.append(existing_data[state])
        continue

    gen_data = generate_policy_data(state)

    if not gen_data:
        print(f"Skipping {state}")
        continue

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
            "final_quote": eval_data["final_quote"],
            "evaluation_notes": eval_data["issues"]
        }
        final_results.append(combined)
        print(f"✅ {state} passed evaluation")
    else:
        print(f"❌ {state} rejected: {eval_data['issues']}")
        final_results.append(gen_data)

    time.sleep(3)

# ✨ Merge unchanged high-confidence entries from existing data
for state, data in existing_data.items():
    if state not in [entry["state"] for entry in final_results]:
        final_results.append(data)

# 💾 Save to disk
with open("data.json", "w", encoding="utf-8") as f:
    json.dump(final_results, f, indent=2)

save_manual_overrides()
print("\nData written to data.json and manual_overrides.json")

# 🔁 Regenerate HTML
print("\n✅ All states processed. Generating HTML...")
subprocess.run(["python", "generate_webpage.py"], check=True)