from . import settings

import sqlite3
import os
import json
from threading import Lock


class OperateDB:
    def __init__(self, path):
        self.path = path
        self.cursor = None
        self.conn = None
        self._lock = Lock()
        self.init_file_db()



    def create_db_file(self):

        conn = sqlite3.connect(self.path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS goods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT,
                handle TEXT,
                more_info TEXT,
                title TEXT,
                subtitle TEXT,
                price REAL,
                body TEXT,
                categories_1 TEXT,
                categories_2 TEXT,
                categories_3 TEXT,
                option1_name TEXT,
                option1_value TEXT,
                option2_name TEXT,
                option2_value TEXT,
                option3_name TEXT,
                option3_value TEXT,
                image_src TEXT,
                size_price TEXT,
                sole_id TEXT UNIQUE    
            )
            """)
        cursor.close()
        conn.commit()
        conn.close()

    def init_file_db(self):
        if not os.path.isfile(self.path):
            self.create_db_file()
        self.conn = sqlite3.connect(
            self.path, check_same_thread=False)
        self.conn.isolation_level = None
        self.cursor = self.conn.cursor()

    def gather_save(self, data_dict):
        with self._lock:
            for k, v in data_dict.items():
                if isinstance(v, list) or isinstance(v, dict):
                    data_dict[k] = json.dumps(v, ensure_ascii=False)
            sql = """INSERT INTO goods(
                        url, handle, more_info, title, subtitle, price, body,
                        categories_1, categories_2, categories_3,
                        option1_name, option1_value, option2_name, option2_value,
                        option3_name, option3_value, image_src, size_price, sole_id
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""

            # 从字典中提取对应的值，如果某个键不存在，默认存 None (Null)
            params = (
                data_dict.get('url'),
                data_dict.get('handle'),
                data_dict.get('more_info'),
                data_dict.get('title'),
                data_dict.get('subtitle'),
                data_dict.get('price'),
                data_dict.get('body'),
                data_dict.get('categories_1'),
                data_dict.get('categories_2'),
                data_dict.get('categories_3'),
                data_dict.get('option1_name'),
                data_dict.get('option1_value'),
                data_dict.get('option2_name'),
                data_dict.get('option2_value'),
                data_dict.get('option3_name'),
                data_dict.get('option3_value'),
                data_dict.get('image_src'),
                data_dict.get('size_price'),
                data_dict.get('sole_id')
            )
            cursor = self.conn.cursor()
            cursor.execute(sql, params)
            self.conn.commit()
            cursor.close()


    def inspect_data(self, sole_id):
        """
        数据去重,根据目录和url生成的唯一md5值进行去重  同一个目录下的url重复了就不再采集了
        """
        sql = "SELECT 1 FROM goods WHERE sole_id = ?"
        local_cursor = self.conn.cursor()
        try:
            local_cursor.execute(sql, (sole_id,))
            res = local_cursor.fetchone()
            return res is not None
        finally:
            local_cursor.close()


    def close_data(self):
        self.cursor.close()
        self.conn.close()
