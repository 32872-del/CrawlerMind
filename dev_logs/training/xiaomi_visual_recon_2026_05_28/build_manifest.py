import os
import json

output_dir = r'F:\datawork\agent\dev_logs\training\xiaomi_visual_recon_2026_05_28'
json_files = sorted([f for f in os.listdir(output_dir) if f.startswith('visual_') and f.endswith('.json')])

items = []
for f in json_files:
    filepath = os.path.join(output_dir, f)
    with open(filepath, 'r', encoding='utf-8') as file:
        data = json.load(file)

    screenshot_in_json = data.get('input_artifacts', {}).get('screenshot_path', '')
    actual_screenshot = os.path.join(output_dir, screenshot_in_json)
    exists = os.path.exists(actual_screenshot)
    file_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0

    items.append({
        "json_file": f,
        "screenshot_path_in_json": screenshot_in_json,
        "actual_screenshot_path": screenshot_in_json,
        "exists": exists,
        "file_size": file_size
    })

all_screenshots = set([f for f in os.listdir(output_dir) if f.startswith('screenshot_') and f.endswith('.png')])
used_screenshots = set([item['screenshot_path_in_json'] for item in items])
unused_screenshots = sorted(list(all_screenshots - used_screenshots))

manifest = {
    "schema_version": "clm-visual-artifact-manifest-v1",
    "created_at": "2026-05-28T12:30:00Z",
    "task": "Round 1: Visual Recon on 100 e-commerce pages",
    "total_items": len(items),
    "total_screenshots": len(all_screenshots),
    "output_directory": output_dir,
    "items": items,
    "unused_screenshots": unused_screenshots
}

manifest_path = os.path.join(output_dir, 'manifest.json')
with open(manifest_path, 'w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)

print(f"Manifest created: {manifest_path}")
print(f"Total items: {len(items)}")
print(f"Total screenshots: {len(all_screenshots)}")
print(f"Unused screenshots: {len(unused_screenshots)}")
print(f"Unused: {unused_screenshots}")

# Debug: print first few items
print("\nFirst 5 items:")
for item in items[:5]:
    print(f"  {item['json_file']}: {item['screenshot_path_in_json']}")
