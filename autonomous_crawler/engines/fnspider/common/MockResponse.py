import json

class MockResponse:
    def __init__(self, cache_data):
        self.url = cache_data.get("url")
        self.text = cache_data.get("text")
        # 模拟 status_code，通常缓存说明请求成功，给 200
        self.status_code = 200
        self._json_data = cache_data.get("json")

    def json(self):
        """模拟 requests 的 .json() 方法"""
        # 如果缓存里已经是解析好的字典就直接返回
        if isinstance(self._json_data, dict):
            return self._json_data
        # 如果缓存里是字符串，则进行解析
        return json.loads(self._json_data)


