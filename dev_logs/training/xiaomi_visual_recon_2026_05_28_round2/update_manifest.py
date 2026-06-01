import os
import json
from datetime import datetime

output_dir = r'F:\datawork\agent\dev_logs\training\xiaomi_visual_recon_2026_05_28_round2'

# Get all JSON files
json_files = sorted([f for f in os.listdir(output_dir) if f.startswith('visual_') and f.endswith('.json')])

# Get all screenshots
screenshot_files = [f for f in os.listdir(output_dir) if f.startswith('screenshot_') and f.endswith('.png')]

# Build manifest items
items = []
for jf in json_files:
    filepath = os.path.join(output_dir, jf)
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Get screenshot path from JSON
    screenshot_path = data.get('input_artifacts', {}).get('screenshot_path', '')

    # Check if screenshot exists
    screenshot_full_path = os.path.join(output_dir, screenshot_path)
    exists = os.path.exists(screenshot_full_path)

    # Get file size
    file_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0

    items.append({
        "json_file": jf,
        "screenshot_path_in_json": screenshot_path,
        "actual_screenshot_path": screenshot_path if exists else "",
        "exists": exists,
        "file_size": file_size
    })

# Create manifest
manifest = {
    "schema_version": "clm-visual-artifact-manifest-v1",
    "created_at": datetime.now().isoformat() + "Z",
    "task": "Round 2: Visual Recon with HTML/network evidence",
    "total_items": len(items),
    "total_screenshots": len(screenshot_files),
    "output_directory": output_dir,
    "items": items,
    "unused_screenshots": []
}

# Write manifest
manifest_path = os.path.join(output_dir, 'manifest.json')
with open(manifest_path, 'w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)

print(f"Manifest updated: {manifest_path}")
print(f"Total items: {len(items)}")
print(f"Total screenshots: {len(screenshot_files)}")
print(f"Items with screenshots: {sum(1 for item in items if item['exists'])}")
