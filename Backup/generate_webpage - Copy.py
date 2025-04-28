import json

with open('data.json') as f:
    data = json.load(f)

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
.verified { color: green; }
.manual { color: orange; }
.high-confidence { color: green; }
.medium-confidence { color: orange; }
.low-confidence { color: red; }
h1 { margin-bottom: 10px; }
p { margin-bottom: 20px; }
</style>
</head>
<body>
<h1>License Plate Retention Policies by State</h1>
<p>This table shows whether license plates stay with the vehicle or the owner upon sale or transfer, based on DMV policies. Rows flagged for manual validation indicate the policy was not automatically found and requires human review.</p>
<table>
<tr>
<th>State</th>
<th>Plate Retention Policy</th>
<th>Policy Summary</th>
<th>DMV Quote</th>
<th>Source</th>
<th>Confidence</th>
</tr>
"""

for row in data:
    confidence = row.get('confidence', 'Manual validation needed')


    confidence_class = "verified" if confidence != 'Manual validation needed' else "manual"

    html += f"""
<tr>
<td>{row['state']}</td>
<td>{row.get('plate_retention_policy', 'N/A')}</td>
<td>{row.get('final_summary', row.get('policy_summary', 'N/A'))}</td>
<td>{row.get('final_quote', row.get('dmv_excerpt', 'N/A'))}</td>
<td><a href="{row['source_url']}" target="_blank">{row['source_url']}</a></td>
<td class="{confidence_class}">{confidence}</td>
</tr>
"""

html += """
</table>
</body>
</html>
"""

with open("index.html", "w", encoding='utf-8') as f:
    f.write(html)

print("index.html generated successfully")
