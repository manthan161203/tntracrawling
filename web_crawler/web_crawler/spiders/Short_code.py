import scrapy
from scrapy_splash import SplashRequest
from urllib.parse import urlparse, urljoin
import os
import re
from html import unescape
from langdetect import detect
from scrapy.loader import ItemLoader
from scrapy import Item, Field

class PageItem(Item):
    url = Field()
    title = Field()
    content = Field()

class MySpider(scrapy.Spider):
    name = 'spider_for_data_short'
    start_urls = ['https://evgateway.com/']
    allowed_domains = {urlparse(url).netloc for url in start_urls}

    custom_settings = {
        'COOKIES_ENABLED': True,
        'COOKIES_DEBUG': True,
        'ROBOTSTXT_OBEY': True,
        'USER_AGENT': 'Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Googlebot/2.1; http://www.google.com/bot.html) Chrome/W.X.Y.Z Safari/537.36',
        'FILES_STORE': 'downloaded_files_automotive',
        'DUPEFILTER_CLASS': 'scrapy.dupefilters.RFPDupeFilter',
    }

    def start_requests(self):
        for url in self.start_urls:
            yield SplashRequest(url, self.parse, args={'wait': 2, 'cookies': 'accept_all_cookies'})

    def parse(self, response):
        self.logger.debug(f"Parsing URL: {response.url}")

        if not self.is_english(response):
            self.logger.debug(f"Ignoring non-English URL: {response.url}")
            return

        text_content = self.extract_text(response)
        if text_content:
            loader = ItemLoader(item=PageItem(), response=response)
            loader.add_value('url', response.url)
            loader.add_value('title', response.css('title::text').get())
            loader.add_value('content', text_content)
            yield loader.load_item()

            self.logger.debug(f"Scraped URL: {response.url}")

        for link in self.extract_links(response):
            yield link

    def is_english(self, response):
        lang = response.css('html::attr(lang)').get()
        if lang is None or lang.lower() != 'en':
            text_sample = ' '.join(response.css('body *::text').getall()).strip()
            if text_sample:
                detected_lang = detect(text_sample)
                return detected_lang == 'en'
        return True

    def extract_text(self, response):
        seen_content = set()
        text_content = ""
        target_tags = ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'strong', 'article', 'a']

        for element in response.css('body :not(header):not(footer) *'):
            tag = element.root.tag
            if tag in target_tags:
                text_parts = element.css('::text').getall()
                if text_parts:
                    text = ' '.join(text_parts).strip()
                    if text and text not in seen_content:
                        seen_content.add(text)
                        cleaned_text = self.clean_text(text)
                        text_content += cleaned_text + '\n'
        return text_content

    def extract_links(self, response):
        links = response.css('a::attr(href)').getall()
        for link in links:
            full_url = urljoin(response.url, link)
            parsed_url = urlparse(full_url)

            if not self.is_valid_url(parsed_url, full_url):
                continue

            self.logger.debug(f"Adding URL to crawl: {full_url}")

            if full_url.endswith('.pdf'):
                yield self.create_file_request(full_url, self.save_pdf)
            elif full_url.endswith('.xls') or full_url.endswith('.xlsx'):
                yield self.create_file_request(full_url, self.save_excel)
            else:
                yield SplashRequest(full_url, self.parse, args={'wait': 2, 'cookies': 'accept_all_cookies'})

    def is_valid_url(self, parsed_url, full_url):
        if parsed_url.scheme not in ['http', 'https']:
            self.logger.debug(f"Ignoring URL with invalid scheme: {full_url}")
            return False
        if parsed_url.netloc not in self.allowed_domains:
            self.logger.debug(f"Ignoring URL outside allowed domain: {full_url}")
            return False
        return True

    def create_file_request(self, url, callback):
        return SplashRequest(url, callback, args={'wait': 2, 'cookies': 'accept_all_cookies'}, meta={'url': url})

    def save_file(self, response, file_type):
        url = response.meta['url']
        file_name = os.path.basename(urlparse(url).path)
        file_path = os.path.join(self.custom_settings['FILES_STORE'], file_name)

        os.makedirs(self.custom_settings['FILES_STORE'], exist_ok=True)

        with open(file_path, 'wb') as f:
            f.write(response.body)

        self.logger.info(f"Saved {file_type}: {file_name}")

    def save_pdf(self, response):
        self.save_file(response, 'PDF')

    def save_excel(self, response):
        self.save_file(response, 'Excel')

    def clean_text(self, text):
        text = text.strip()
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        text = unescape(text)
        text = re.sub(r'\s+', ' ', text)
        # Remove non-English characters and emojis
        text = re.sub(r'[^\x00-\x7F]+', '', text)
        return text

    def closed(self, reason):
        self.logger.info(f"Spider closed due to: {reason}.")
