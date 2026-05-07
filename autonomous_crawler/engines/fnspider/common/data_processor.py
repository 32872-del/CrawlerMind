import json
import os
from ..common import MockResponse
from ..handle_str import handle_str
from ..handle_str import parse_html_obj
from ..utils import hash_md5
from ..utils import get_latest_db
from ..OperateDB import OperateDB
from .. import settings
from lxml.html.clean import Cleaner
from bs4 import BeautifulSoup, Comment
from loguru import logger
from threading import Lock
import html
import re
import time
stamp_time = str(int(time.time()))

class DataProcessor:
    def __init__(self):
        # self.name = None
        is_recollect = getattr(self, 'is_recollect', 1)

        # 目录是否存在 不存在就创建
        self.name = getattr(self, 'name', None)
        if not os.path.exists(settings.OUT_PATH):
            os.mkdir(settings.OUT_PATH)
        self.cache_path = os.path.join(settings.CACHE_DIR, self.name)
        if not os.path.exists(settings.CACHE_DIR):
            os.mkdir(settings.CACHE_DIR)
        if not os.path.exists(self.cache_path):
            os.mkdir(self.cache_path)

        if is_recollect == 1:
            self.name = stamp_time + self.name + ".db"
        else:
            # 使用最新的文件
            name = getattr(self, 'name', None)
            self.name = get_latest_db(settings.OUT_PATH, name)
            logger.info('已开启增量采集，正在使用最新的文件: ' + str(self.name))
            if not self.name:
                self.name = stamp_time + name + ".db"
        self.db_path = os.path.join(settings.OUT_PATH, self.name)
        self.operate_db = OperateDB(self.db_path)
        self.result_field = ['handle', 'title', 'image_src','price']
        self.done_data = set()
        self.lock = Lock()




    def _filter_repeat_data(self, sole_id):
        """
        根据sole_id数据去重
        查找内存和数据库中是否存在sole_id
        数据不存在返回False
        数据存在返回True
        """
        with self.lock:
            if sole_id in self.done_data:
                return True
            self.done_data.add(sole_id)
            return False

    def _validate_field_value(self, result):
        """
        校验字段和数据  ['title','price','image_src','handle','sole_id'] 不能为空
        """
        self._inspect_field(result.keys())
        for key, value in result.items():
            if key == 'size_prize':
                if not isinstance(value, list):
                    raise ValueError(str(key) + ", 该字段的数据不是列表类型")

            if key not in ['title','price','image_src','handle','sole_id']:
                continue
            if (not bool(value)) or (value == "None"):
                raise ValueError(str(key) + ", 该字段为没有数据")
            if key in ['title','handle','sole_id'] and not isinstance(value, str):
                raise ValueError(str(key) + ", 该字段的数据不是字符串类型")
            if key in ['price'] and not isinstance(value, float):
                raise ValueError(str(key) + ", 该字段的数据不是浮点数类型")
            if key in ['image_src'] and not isinstance(value, list):
                raise ValueError(str(key) + ", 该字段的数据不是列表类型")


    def _inspect_field(self, content_keys):
        """
        字段校验,没有字段不存入
        """
        set_field = set(self.result_field)
        lack_field = set_field - (set_field & set(content_keys))
        if bool(lack_field):
            raise AttributeError("缺少字段: " + ", ".join(list(lack_field)))
        return True

