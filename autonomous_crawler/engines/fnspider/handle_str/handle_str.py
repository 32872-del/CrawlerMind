
import re
from lxml import etree
from urllib.parse import urljoin



def parse_html_obj(dom_obj):
    """
    将HTML对象转换为str
    """
    return etree.tostring(dom_obj, encoding='utf-8').decode('utf-8')



def completion_url(text, url):
    """
    链接补全
    """
    
    hrefs = re.findall(r'(src|href)=(["|\'])(.*?)(["|\'])', text)
    for href in hrefs:
        if _is_list_item_prfix(['', '#', 'javascript:;', 'javascript:void(0);'], href[2]):
            continue
        full_href = urljoin(url, href[2])
        text = text.replace(f"{href[0]}={href[1]}{href[2]}{href[3]}", f"{href[0]}={href[1]}{full_href}{href[3]}")

    return text

def _is_list_item_prfix(lst, prefix):
    for item in lst:
        if item == prefix:
            return True
    return False

def create_counter():
    i = [6000]
    def counter():
        i[0] += 1
        return 'model' + str(i[0]).zfill(5)
    return counter

