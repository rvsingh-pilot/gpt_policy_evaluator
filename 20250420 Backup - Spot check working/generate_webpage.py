import json
import re

def markdown_to_html(text):
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)

with open('data.json') as f:
    data = json.load(f)
data.sort(key=lambda x: x['state'])  # ✅ Ensure this comes AFTER loading

html = """
<!DOCTYPE html>
<html>
<head>
<title>License Plate Retention Policies by State</title>
<style>
body { font-family: Arial, sans-serif; margin: 20px; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #ccc; padding: 8px; vertical-align: top; }
th { background-color: #f2f2f2; }
h1 { margin-bottom: 10px; }
p { margin-bottom: 20px; }

.high-confidence { color: green; }
.medium-confidence { color: orange; }
.low-confidence { color: red; }
</style>
</head>
<body>
<h1>License Plate Retention Policies by State</h1>
<p>This table summarizes whether license plates stay with the vehicle or the seller upon sale or transfer, based on each state's DMV policy.</p>
<table>
<tr>
<th>State</th>
<th>Plate Retention Policy</th>
<th>Confidence</th>
<th>Policy Summary</th>
<th>Supporting DMV Quote</th>
<th>Source</th>
</tr>
"""

for row in sorted(data, key=lambda x: x['state']):
    confidence = row.get('confidence', 'Manual validation needed')

    if "High" in confidence:
        confidence_class = "high-confidence"
    elif "Medium" in confidence:
        confidence_class = "medium-confidence"
    else:
        confidence_class = "low-confidence"

    # Convert markdown bold (**word**) to HTML <strong>word</strong>
    quote_raw = row.get('highlighted_quote', row.get('final_quote', row.get('dmv_excerpt', 'N/A')))
    quote_html = markdown_to_html(quote_raw)

    html += f"""
    <tr>
        <td>{row['state']}</td>
        <td>{row.get('plate_retention_policy', 'N/A')}</td>
        <td class="{confidence_class}">{confidence}</td>
        <td>{row.get('final_summary', row.get('policy_summary', 'N/A'))}</td>
        <td>{quote_html}</td>
        <td><a href="{row['source_url']}" target="_blank">{row['source_url']}</a></td>
        </tr>
        """

html += """
    </table>
    </body>
    </html>
    """

with open("index.html", "w", encoding='utf-8') as f:
    f.write(html)

print("index.html generated successfully; please open page to review results.")
