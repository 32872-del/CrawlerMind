from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urljoin, urlparse, urlunparse, parse_qsl

from bs4 import BeautifulSoup

from .Spider import Spider
from .handle_str import completion_url, create_counter
from .site_spec import (
    all_values,
    clean_price,
    first_value,
    load_site_spec,
    normalize_site_spec,
)


class ConfigSpider(Spider):
    """A configuration-driven spider backed by the normal fnspider pipeline."""

    collect_thread_number = 3
    more_collect_thread_number = 3
    is_recollect = 1

    def __init__(self, spec_path: str | None = None, spec: dict[str, Any] | None = None):
        if spec_path:
            raw_spec = load_site_spec(spec_path)
            self.spec_path = str(Path(spec_path))
        elif spec:
            raw_spec = load_site_spec(spec)
            self.spec_path = ""
        else:
            raise ValueError("ConfigSpider requires spec_path or spec")

        self.spec = normalize_site_spec(raw_spec)
        self.name = "_" + self.spec["site"]
        self.result_field = self.spec.get("required_fields", ["handle", "title", "image_src", "price"])
        self.driver1 = self._driver_config()
        self.start_urls = []
        super().__init__()

    def _driver_config(self) -> dict[str, Any]:
        driver = {
            "user_agent": None,
            "headless": True,
            "driver_type": "chromium",
            "timeout": 30 * 1000,
            "window_size": (1600, 1000),
            "executable_path": None,
            "download_path": None,
            "render_time": 3,
            "wait_until": "domcontentloaded",
            "use_stealth_js": False,
            "page_on_event_callback": None,
            "storage_state_path": None,
            "url_regexes": None,
            "save_all": False,
        }
        driver.update(self.spec.get("driver") or {})
        return driver

    def init_func(self):
        self.start_urls.extend(self._start_items())

    def _start_items(self) -> list[dict[str, Any]]:
        result = []
        for item in self.spec.get("start_urls", []):
            if isinstance(item, str):
                result.append({"url": item})
            elif isinstance(item, dict) and item.get("url"):
                result.append(dict(item))
        return result

    def _fetch_html(self, url: str):
        mode = str(self.spec.get("mode", "browser")).lower()
        if mode == "browser":
            response = self.request.render_page(
                url,
                await_condition=self.spec.get("wait_selector", ""),
                sleep_time=float(self.spec.get("sleep_time", 0) or 0),
                scroll_count=int(self.spec.get("scroll_count", 0) or 0),
                scroll_delay=float(self.spec.get("scroll_delay", 1.0) or 1.0),
                cache=bool(self.spec.get("cache", True)),
            )
        else:
            response = self.request.get(
                url,
                request_type="curl_cffi" if mode == "curl_cffi" else "requests",
                cache=bool(self.spec.get("cache", True)),
            )
        return completion_url(response.text, url)

    def _page_url(self, base_url: str, page: int) -> str:
        pagination = self.spec.get("pagination") or {}
        if page <= 1:
            return base_url
        if pagination.get("url_template"):
            return str(pagination["url_template"]).format(url=base_url, page=page)
        page_param = pagination.get("page_param")
        if page_param:
            parsed = urlparse(base_url)
            query = dict(parse_qsl(parsed.query, keep_blank_values=True))
            query[str(page_param)] = str(page)
            return urlunparse(parsed._replace(query=urlencode(query)))
        return base_url

    def get_list(self, params):
        list_spec = self.spec["list"]
        pagination = self.spec.get("pagination") or {}
        max_pages = max(1, int(pagination.get("max_pages", 1) or 1))
        seen = set()

        for page in range(1, max_pages + 1):
            page_url = self._page_url(params["url"], page)
            soup = BeautifulSoup(self._fetch_html(page_url), "lxml")
            links = all_values(soup, list_spec["item_link"], base_url=page_url)
            if not links:
                break
            for link in links:
                if link in seen:
                    continue
                seen.add(link)
                item = deepcopy(params)
                item["url"] = link
                yield item

            next_selector = pagination.get("next_selector")
            if next_selector and not soup.select_one(str(next_selector)):
                break
            if not pagination.get("url_template") and not pagination.get("page_param") and not next_selector:
                break

    def get_content(self, params):
        variants = self.spec.get("variants") or {}
        html = self._fetch_html(params["url"])
        soup = BeautifulSoup(html, "lxml")
        links = all_values(soup, variants.get("links", ""), base_url=params["url"])
        if params["url"] not in links:
            links.insert(0, params["url"])

        handle = create_counter()
        for index, url in enumerate(links):
            item = deepcopy(params)
            item["url"] = url
            item["handle"] = f"{handle()}_{index + 1}"
            yield item

    def get_more_content(self, params):
        html = self._fetch_html(params["url"])
        soup = BeautifulSoup(html, "lxml")
        detail = self.spec.get("detail") or {}
        record = deepcopy(params)

        for field, rule in detail.items():
            if field in {"image_src", "images"}:
                record["image_src"] = all_values(soup, rule, base_url=params["url"])
            elif field == "body":
                record[field] = "".join(all_values(soup, rule, base_url=params["url"]))
            elif field == "price":
                record[field] = clean_price(first_value(soup, rule, base_url=params["url"]))
            else:
                record[field] = first_value(soup, rule, base_url=params["url"])

        for field, value in (self.spec.get("static_fields") or {}).items():
            record.setdefault(field, value)
        record.setdefault("image_src", [])
        yield record


def run_config_spider(spec_path: str) -> None:
    ConfigSpider(spec_path=spec_path).start()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run a fnspider site_spec.json")
    parser.add_argument("spec", help="Path to site_spec.json")
    args = parser.parse_args()
    run_config_spider(args.spec)
