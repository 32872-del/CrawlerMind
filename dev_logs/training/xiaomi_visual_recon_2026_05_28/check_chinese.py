import os
import re

output_dir = r'F:\datawork\agent\dev_logs\training\xiaomi_visual_recon_2026_05_28'
json_files = sorted([f for f in os.listdir(output_dir) if f.startswith('visual_') and f.endswith('.json')])

chinese_pattern = re.compile(r'[一-鿿]')
chinese_files = []

for f in json_files:
    filepath = os.path.join(output_dir, f)
    with open(filepath, 'r', encoding='utf-8') as file:
        content = file.read()
        if chinese_pattern.search(content):
            chinese_files.append(f)

print(f"Total JSON files: {len(json_files)}")
print(f"Files with Chinese characters: {len(chinese_files)}")
if chinese_files:
    print("Affected files:")
    for f in chinese_files:
        print(f"  - {f}")
