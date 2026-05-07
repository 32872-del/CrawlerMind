# -*- coding: utf-8 -*-
from .common import DataProcessor
from . import settings
from .utils import hash_md5
from .NetworkRequest import NetworkRequest
from loguru import logger
from queue import Queue
from threading import Thread, Lock
from abc import abstractmethod, ABCMeta
import traceback


class Spider(DataProcessor, metaclass=ABCMeta):
    def __init__(self):
        # 属性初始化
        self.name = getattr(self, 'name', 'no_name')
        self.collect_thread_number = getattr(self, 'collect_thread_number', 2)
        self.more_collect_thread_number = getattr(self, 'more_collect_thread_number', 2)
        self.driver1 = getattr(self, 'driver1', {})
        # 资源初始化
        self.is_recollect = getattr(self, 'is_recollect', 1)
        self.request = NetworkRequest(name=self.name, thread_count=self.collect_thread_number,driver1_config=self.driver1,driver2_config='')
        self.lock = Lock()
        super().__init__()

        # 队列定义
        self.list_queue = Queue(maxsize=1000)
        self.more_list_queue = Queue(maxsize=1000)

        # 配置项
        self.start_urls = getattr(self, 'start_urls', [])
        self.data_category = getattr(self, 'data_category', 0)

        # logger.info(f"爬虫 [{self.name}] 初始化完成")

    @classmethod
    def init_func(cls):
        """
        初始化方法
        """
        pass
    @abstractmethod
    def get_list(self, params):
        pass


    @abstractmethod
    def get_content(self, params):
        pass

    @abstractmethod
    def get_more_content(self, params):
        pass

    def monitor_list(self):
        """第一阶段：从起始链接提取列表项"""
        while True:
            try:
                with self.lock:
                    if not self.start_urls:
                        return
                    start_item = self.start_urls.pop(0)

                url = start_item['url']
                logger.info(f"列表解析开始: {url}")
                count = 0
                list_data = self.get_list(start_item)
                for data_item in list_data:
                    self.list_queue.put(data_item)
                    count += 1

                if count == 0:
                    logger.error(f'列表数据为空！url:{url}')
                else:
                    logger.info(f"列表获取完成: {url}，共 {count} 条数据")

            except Exception:
                logger.error(f"monitor_list 异常: {traceback.format_exc()}")

    def monitor_content(self):
        """第二阶段：从列表项提取详情/变体"""
        while True:
            params = self.list_queue.get()
            if params is None:
                break

            try:
                url = params.get('url')
                logger.success('开始请求商品页: {}', url)
                items = self.get_content(params)
                if not items:
                    continue
                count = 0
                for item in items:
                    count += 1

                    self.more_list_queue.put(item)

                if count == 0:
                    logger.error(f'商品数据为空！url:{url}')
            except Exception:
                logger.error(f"monitor_content 异常: {traceback.format_exc()}")
            finally:
                self.list_queue.task_done()

    def monitor_more_content(self):
        """第三阶段：最终详情抓取与入库"""
        while True:
            item = self.more_list_queue.get()
            if item is None:
                break

            try:

                url = item.get('url')
                sole_id = hash_md5(
                    item.get('categories_1', '') + item.get('categories_2', '') + item.get('categories_3', '') + item['url']
                )
                #   去重校验:返回True表示已存在
                if self._filter_repeat_data(sole_id):
                    logger.info(f"重复数据: {url} sole_id:{sole_id[:10]}")
                    continue
                logger.success('开始请求更多商品页: {}', url)
                # 获取最终结果
                final_results = self.get_more_content(item)
                if not final_results:
                    continue

                for res in final_results:
                    res['sole_id'] = sole_id
                    #  校验
                    self._validate_field_value(res)
                    #  保存
                    self.operate_db.gather_save(res)
                    logger.success(f"成功入库: {res['url']} sole_id:{res['sole_id'][:10]}")

            except Exception:
                logger.error(f"monitor_more_content 异常: {traceback.format_exc()}")
            finally:
                self.more_list_queue.task_done()

    def start(self):
        logger.info("任务启动...")
        self.init_func()

        l_threads = [Thread(target=self.monitor_list) for _ in range(1)]
        for t in l_threads: t.start()

        c_threads = [Thread(target=self.monitor_content) for _ in range(self.collect_thread_number)]
        for t in c_threads: t.start()

        m_threads = [Thread(target=self.monitor_more_content) for _ in range(self.more_collect_thread_number)]
        for t in m_threads: t.start()

        for t in l_threads: t.join()

        for _ in range(len(c_threads)): self.list_queue.put(None)
        for t in c_threads: t.join()

        for _ in range(len(m_threads)): self.more_list_queue.put(None)
        for t in m_threads: t.join()

        self.request.quit_driver()
        self.operate_db.close_data()
        logger.info("所有任务运行结束！")