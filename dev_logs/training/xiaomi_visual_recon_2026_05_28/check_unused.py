import os
import json

output_dir = r'F:\datawork\agent\dev_logs\training\xiaomi_visual_recon_2026_05_28'
json_files = sorted([f for f in os.listdir(output_dir) if f.startswith('visual_') and f.endswith('.json')])

unused = ['screenshot_1c7ab2bc.png', 'screenshot_33a40d4c.png', 'screenshot_46a0b502.png', 'screenshot_a81b8d9c.png', 'screenshot_bedbb5d6.png', 'screenshot_d9866501.png']

for unused_screenshot in unused:
    found = False
    for jf in json_files:
        filepath = os.path.join(output_dir, jf)
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if data.get('input_artifacts', {}).get('screenshot_path') == unused_screenshot:
            found = True
            print(f"{unused_screenshot} found in {jf}")
            break
    if not found:
        print(f"{unused_screenshot} NOT found in any JSON file")
