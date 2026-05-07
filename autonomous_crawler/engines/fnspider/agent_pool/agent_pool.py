import re

from .. import settings

import requests

import json
import os


def random_agent():
    ip_list = []
    proxy_path = os.path.join(os.path.dirname(__file__), 'ProxyServersConfig.json')
    with open(proxy_path, mode='r', encoding='utf-8') as file:
        ip_infos = json.loads(file.read())['ProxyServers']
    for info in ip_infos:
        ip = info['ip']
        port = info['port']
        user_name = info['userName']
        password = info['password']
        ip_list.append(
            {
                'http': 'http://{}:{}@{}:{}'.format(user_name, password, ip, port)
            })

    return ip_list

def agent_pool(page_url):
    return {
        "http": "http://127.0.0.1:7890",
        "https": "http://127.0.0.1:7890"
    }