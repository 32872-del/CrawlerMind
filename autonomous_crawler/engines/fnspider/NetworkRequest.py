from . import settings
from .utils import hash_md5
from .common import MockResponse
from botasaurus.lang import Lang
import curl_cffi.requests
from botasaurus.browser import browser, Driver
from botasaurus.soupify import soupify
import threading
import json, importlib, time, redis,os,sys
from urllib import parse
from loguru import logger
from fake_useragent import UserAgent
from .utils import encrypto
from .agent_pool import agent_pool
from playwright.sync_api import sync_playwright
from concurrent.futures import ThreadPoolExecutor
import asyncio
CACHE_DIR = settings.CACHE_DIR # 缓存目录
requests = importlib.import_module("requests")



class NetworkRequest:

    def __init__(self,name,driver1_config,driver2_config,thread_count=2):
        full_path = sys.argv[0]

        self.headers = {}
        self.name = name
        self.driver1_config = driver1_config
        self.driver2_config = driver2_config
        self.ua = UserAgent(platforms='desktop')
        self.thread_count = thread_count
        requests.packages.urllib3.disable_warnings()
        requests.adapters.DEFAULT_RETRIES = 5

        # 线程锁
        self._local = threading.local()
        self.error = None
        self.executor = ThreadPoolExecutor(max_workers=4)


    def get_request_info(self, url, headers, is_proxy, proxy_safety, **kwargs):
        """
        获取请求信息

        :param url: 请求 URL
        :param headers: 请求头
        :param is_proxy: 是否使用代理
        :param proxy_safety: 代理安全级别（例如 "http" 或 "https"）
        :param kwargs: 额外参数
        :return: 代理和请求头
        """
        # 代理获取有问题
        # 没有代理自动调用代理
        # if not is_proxy:
        #     proxy = agent_pool(url)
        #     proxies = proxy
        # else:
        #     proxies = kwargs["proxies"]
        for key, value in self.headers.items():
            headers[key] = value

        if not (headers.get('User-Agent') or headers.get('user-agent')):
            headers['User-Agent'] = self.ua.random
        return None, headers

    def send_request(self, method, url, headers, data=None, cookies=None, proxy_safety="http", request_type="requests", **kwargs):
        """
        发送请求

        :param method: 请求方法
        :param url: 请求 URL
        :param headers: 请求头
        :param proxy_safety: 代理安全级别（例如 "http" 或 "https"）
        :param data: 请求数据
        :param cookies: 请求 cookie
        :param request_type: 请求方法，默认为 requests，可选 curl_cffi
        :param kwargs: 额外参数
        :return: 响应对象
        """
        global requests
        request_model = {
            "curl_cffi": curl_cffi.requests
        }
        is_proxy = bool(kwargs.get('proxies'))
        if request_type in request_model.keys():
            requests = request_model[request_type]
        for _ in range(settings.REQUEST_RETRY):
            kwargs["proxies"], headers = self.get_request_info(url, headers, is_proxy, proxy_safety, **kwargs)
            try:
                response = requests.request(method, url, headers=headers, data=data, cookies=cookies, **kwargs)
                break
            except Exception as error:
                self.error = error
                logger.info(self.error)
        else:
            print(kwargs["proxies"],'代理已失效')
            del kwargs["proxies"]
            # print(kwargs)
            try:
                response = requests.request(method, url, headers=headers, data=data, cookies=cookies, **kwargs)
            except Exception as error:
                raise error

        return response

    def get(self, url: str, headers: dict = {}, cookies: dict = None, request_type="requests", proxy_safety="http", verify=False, cache=True,timeout=settings.REQUEST_TIME_OUT,save=True, **kwargs):
        """
        url: 页面链接
        proxy_safety: 代理选择默认为 http，可选 https
        request_type: 请求方法，默认为 requests，可选 curl_cffi
        """
        if cache:
            cache_data = self.read_cache(url,req_type=1)
            if cache_data:
                return cache_data
        response = self.send_request("get", url, headers, cookies=cookies, request_type=request_type,
                                 proxy_safety=proxy_safety, verify=verify, timeout=timeout, **kwargs)
        code = response.status_code
        if code != 200:
            logger.error(F'页面请求失败 URL:{url} 状态码: {code}')
        if save and code == 200:
            # self.save_cache(url, response,req_type=1)
            self.executor.submit(self.save_cache, url, response, 1)
        return response

    def post(self, url: str, headers: dict = {}, data: dict = None, cookies: dict = None, request_type="requests", proxy_safety="http",save=True, cache=True, timeout=settings.REQUEST_TIME_OUT, verify=False, **kwargs):
        """
        url：页面链接
        data：请求参数
        proxy_safety：代理选择默认为 http，可选 https
        request_type：请求方法，默认为 requests，可选 curl_cffi
        """
        if cache:
            json_str = json.dumps(data, separators=(',', ':'))
            cache_data = self.read_cache(url+json_str,req_type=2)
            if cache_data:
                return cache_data

        response = self.send_request("post", url, headers, data=data, cookies=cookies, request_type=request_type,
                                     proxy_safety=proxy_safety,
                                     timeout=timeout, verify=verify, **kwargs)
        code = response.status_code
        if code != 200:
            logger.error(F'页面请求失败 URL:{url} 状态码: {code}')
        if save and code == 200:
            json_str = json.dumps(data, separators=(',', ':'))
            # self.save_cache(url+json_str, response,req_type=2)
            self.executor.submit(self.save_cache, url, response, 2)
        return response


    def _get_driver(self):
        # 线程第一次调用时，会在这里初始化
        if not hasattr(self._local, "driver"):
            logger.info(f"线程 {threading.current_thread().name} 初始化本地浏览器")
            self._local.driver = Driver(
                lang=Lang.English,
                # lang=Lang.Polish,  #波兰语
                # parallel=3,  # 最大浏览器数量
                headless=True,  # 是否启用无头模式
                # max_retry=3,  # 单个任务失败重试次数
                # retry_wait=3,  # 重试等待时间
                # block_images=True,  # 屏蔽图片加载
                # window_size=WindowSize.HASHED,
                # block_images_and_css=False,  # 屏蔽图片和CSS
                wait_for_complete_page_load=False,  # 是否等待页面完全加载
                # wait_for_complete_page_load=False,
                # reuse_driver=False,  # 是否复用浏览器窗口
                # output=None,
                # proxy="http://user:pass@gate.rola.vip:2000"
            )
        return self._local.driver

    def _get_driver2(self):
        if not hasattr(self._local, "driver"):
            cfg = self.driver1_config

            p = sync_playwright().start()

            # ===== 浏览器类型 =====
            browser_type = {
                "chromium": p.chromium,
                "firefox": p.firefox,
                "webkit": p.webkit
            }.get(cfg.get("driver_type", "chromium"))

            # ===== 启动参数 =====
            launch_args = {
                "headless": cfg.get("headless", True),
            }

            if cfg.get("executable_path"):
                launch_args["executable_path"] = cfg["executable_path"]

            if cfg.get("browser_args"):
                launch_args["args"] = list(cfg["browser_args"])

            # ===== 代理 =====
            if cfg.get("proxy"):
                proxy = cfg["proxy"]
                if "@" in proxy:
                    user_pass, server = proxy.split("@")
                    username, password = user_pass.split(":")
                    launch_args["proxy"] = {
                        "server": f"http://{server}",
                        "username": username,
                        "password": password
                    }
                else:
                    launch_args["proxy"] = {"server": proxy}

            browser = browser_type.launch(**launch_args)

            # ===== context（重点）=====
            context_args = {}

            # UA
            if cfg.get("user_agent"):
                ua = cfg["user_agent"]
                context_args["user_agent"] = ua() if callable(ua) else ua

            # 窗口大小
            if cfg.get("window_size"):
                w, h = cfg["window_size"]
                context_args["viewport"] = {"width": w, "height": h}

            context = browser.new_context(**context_args)

            self._local.driver = {
                "p": p,
                "browser": browser,
                "context": context,
                # "page": None
            }

        return self._local.driver

    def quit_driver(self):
        if hasattr(self._local, "driver"):
            driver = self._local.driver

            if hasattr(driver, "quit"):
                driver.quit()
            elif hasattr(driver, "close"):
                driver.close()
            elif hasattr(driver, "stop"):
                driver.stop()
            elif hasattr(driver, "shutdown"):
                driver.shutdown()
            elif hasattr(driver, "browser"):
                # 常见封装写法
                if hasattr(driver.browser, "quit"):
                    driver.browser.quit()

            del self._local.driver

    def render_page(self, url, return_driver=False, sleep_time=0, await_condition="",save=True,cache=True,driver_type=1, scroll_count=0, scroll_delay=1.0, **kwargs):
        """
        url：页面链接
        page_data_type：页面数据（默认页面的html数据，可选cookies）
        sleep_time：渲染等待时间（默认6秒）
        await_condition：等待元素加载完成（css选择器）
        """


        if cache:
            cache_data = self.read_cache(url,req_type=3 if driver_type==1 else 4)
            if cache_data:
                return cache_data

        if driver_type == 1:
            driver = self._get_driver2()
            context = driver["context"]

            page = context.new_page()

            cfg = self.driver1_config

            # 超时
            page.set_default_timeout(cfg.get("timeout", 30000))

            # 打开页面
            page.goto(
                url,
                wait_until=cfg.get("wait_until", "domcontentloaded"),
                timeout=cfg.get("timeout", 30000)
            )

            # 渲染等待
            if cfg.get("render_time"):
                time.sleep(cfg["render_time"])

            # 等待元素（可选）
            if await_condition:
                try:
                    page.wait_for_selector(await_condition, timeout=20000)
                except:
                    logger.warning(f"等待元素失败: {await_condition}")

            # 强制等待
            if sleep_time:
                time.sleep(sleep_time)

            # 获取 HTML
            for _ in range(int(scroll_count or 0)):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(float(scroll_delay or 1.0))
            html = page.content()

            if save:
                cache_data = {
                    "url": url,
                    "text": html
                }

                # self.save_cache(url, cache_data,req_type=3)
                self.executor.submit(self.save_cache, url, cache_data, 3)

            # 关闭 page（重要！）
            if return_driver:
                return page
            else:
                page.close()
                return MockResponse({'url': url, 'text': html})
        elif driver_type == 2:
            # 使用botasaurus
            driver = self._get_driver()
            driver.google_get(url)

            # 2. 等待某个元素加载完成（如有必要）
            if await_condition:
                driver.wait_for_element(await_condition, wait=20)

            # 3. 强制休眠（如有必要）
            if sleep_time:
                time.sleep(sleep_time)
            for _ in range(int(scroll_count or 0)):
                try:
                    driver.run_js("window.scrollTo(0, document.body.scrollHeight)")
                except Exception:
                    break
                time.sleep(float(scroll_delay or 1.0))
            html = driver.page_html

            if save:
                cache_data = {
                    "url": url,
                    "text": html
                }
                # self.save_cache(url, cache_data,req_type=4)
                self.executor.submit(self.save_cache, url, cache_data, 4)

            if return_driver:
                return driver
            else:
                return MockResponse({'url': url, 'text': html})
        # 进行缓存


        # 进行调试输出driver



    def read_cache(self,url,req_type):
        url_md5 = hash_md5(url+str(req_type))

        cache_file = os.path.join(settings.CACHE_DIR,self.name, f"{url_md5}.json")

        if not os.path.exists(cache_file):
            return None

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                response = MockResponse(cache_data)
                # logger.success('读取缓存成功 URL: {}', url)
            return response

        except Exception as e:
            logger.error(f"读取缓存失败: {cache_file}, error: {str(e)}")
            return None


    def save_cache(self, url, response, req_type):
        url_md5 = hash_md5(url + str(req_type))
        cache_file = os.path.join(settings.CACHE_DIR, self.name, f"{url_md5}.json")

        try:
            cache_data = {
                "url": url,
                "text": None,
                "json": None
            }

            if hasattr(response, "json"):
                try:
                    cache_data["json"] = response.json()
                except:
                    cache_data["text"] = getattr(response, "text", "")
            else:
                try:
                    cache_data["text"] = response.text
                except:
                    cache_data["text"] = response.get("text")

            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False)

        except Exception as e:
            logger.error(f"写入缓存失败: url: {url}, error: {str(e)}")

