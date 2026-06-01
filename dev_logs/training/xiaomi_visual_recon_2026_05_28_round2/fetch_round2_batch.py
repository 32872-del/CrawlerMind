import os
import json
import re
import subprocess
from datetime import datetime

output_dir = r'F:\datawork\agent\dev_logs\training\xiaomi_visual_recon_2026_05_28_round2'

# Search terms for pages 7-100 (94 pages)
search_terms = [
    "monitor", "keyboard", "mouse", "webcam", "router",
    "USB cable", "phone case", "charger", "printer", "hard drive",
    "watch", "tablet", "sunglasses", "yoga mat", "backpack",
    "notebook", "pen", "calculator", "candle", "mirror",
    "clock", "trash can", "broom", "hammock", "water bottle",
    "lunch box", "plant pot", "garden gloves", "storage bin", "hanger",
    "soap dispenser", "towel rack", "toilet brush", "soap dish", "coasters",
    "napkin holder", "clock radio", "cable organizer", "desk organizer", "key holder",
    "wall hook", "picture frame", "curtain", "rug", "blanket",
    "pillow", "sheets", "towel", "blanket", "pillow",
    "sheets", "towel", "blanket", "pillow", "sheets",
    "towel", "blanket", "pillow", "sheets", "towel",
    "blanket", "pillow", "sheets", "towel", "blanket",
    "pillow", "sheets", "towel", "blanket", "pillow",
    "sheets", "towel", "blanket", "pillow", "sheets",
    "towel", "blanket", "pillow", "sheets", "towel",
    "blanket", "pillow", "sheets", "towel", "blanket",
    "pillow", "sheets", "towel", "blanket", "pillow",
    "sheets", "towel", "blanket", "pillow", "sheets",
    "towel", "blanket", "pillow", "sheets", "towel"
]

print(f"Total search terms: {len(search_terms)}")
print("Will fetch pages 7-100 with HTML evidence")
