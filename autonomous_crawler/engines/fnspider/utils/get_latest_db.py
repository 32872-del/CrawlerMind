import os
import re


def get_latest_db(folder_path, target_name):
    matching_files = []
    for file in os.listdir(folder_path):
        match = re.findall(rf"^(\d{{10}}){target_name}\.db$", str(file))
        if match:
            timestamp = int(match[0])
            matching_files.append((timestamp, file))

    if not matching_files:
        return None
    # 根据时间戳降序排序，取第一个（即最大的）
    matching_files.sort(key=lambda x: x[0], reverse=True)

    return matching_files[0][1]