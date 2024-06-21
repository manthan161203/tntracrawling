import scrapy
from scrapy_splash import SplashRequest
from urllib.parse import urlparse, urljoin
import os
import re
from html import unescape
from langdetect import detect

class MySpider(scrapy.Spider):
    name = 'spider_for_data_short'
    start_urls = ['https://www.regeny.ae/']
    allowed_domains = [urlparse(url).netloc for url in start_urls]

    custom_settings = {
        'COOKIES_ENABLED': True,
        'COOKIES_DEBUG': True,
        'ROBOTSTXT_OBEY': True,
        'USER_AGENT': 'Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Googlebot/2.1; http://www.google.com/bot.html) Chrome/W.X.Y.Z‡ Safari/537.36',
        'FILES_STORE': 'downloaded_files_regeny',
        'DUPEFILTER_CLASS': 'scrapy.dupefilters.RFPDupeFilter',
    }

    def start_requests(self):
        for url in self.start_urls:
            yield SplashRequest(url, self.parse, args={'wait': 2, 'cookies': 'accept_all_cookies'})

    def parse(self, response):
        self.logger.debug(f"Parsing URL: {response.url}")

        title = response.css('title::text').get()
        lang = response.css('html::attr(lang)').get()
        if lang is None or lang.lower() != 'en':
            text_sample = ' '.join(response.css('body *::text').getall()).strip()
            if text_sample:
                detected_lang = detect(text_sample)
                if detected_lang != 'en':
                    self.logger.debug(f"Ignoring non-English URL: {response.url}")
                    return

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

        if text_content:
            yield {
                'title': title,
                'url': response.url,
                'content': text_content,
            }
            self.logger.debug(f"Scraped URL: {response.url}")

        links = response.css('a::attr(href)').getall()

        for link in links:
            full_url = urljoin(response.url, link)
            parsed_url = urlparse(full_url)

            if parsed_url.scheme not in ['http', 'https']:
                self.logger.debug(f"Ignoring URL with invalid scheme: {full_url}")
                continue

            if parsed_url.netloc != self.allowed_domains[0]:
                self.logger.debug(f"Ignoring URL outside allowed domain: {full_url}")
                continue

            self.logger.debug(f"Adding URL to crawl: {full_url}")

            if full_url.endswith('.pdf'):
                yield SplashRequest(full_url, self.save_pdf, args={'wait': 2, 'cookies': 'accept_all_cookies'}, meta={'url': full_url})
                self.logger.debug(f"Requesting PDF download: {full_url}")
            elif full_url.endswith('.xls') or full_url.endswith('.xlsx'):
                yield SplashRequest(full_url, self.save_excel, args={'wait': 2, 'cookies': 'accept_all_cookies'}, meta={'url': full_url})
                self.logger.debug(f"Requesting Excel download: {full_url}")
            else:
                yield SplashRequest(full_url, self.parse, args={'wait': 2, 'cookies': 'accept_all_cookies'})

    def save_pdf(self, response):
        url = response.meta['url']
        pdf_name = os.path.basename(urlparse(url).path)
        pdf_path = os.path.join(self.custom_settings['FILES_STORE'], pdf_name)

        if not os.path.exists(self.custom_settings['FILES_STORE']):
            os.makedirs(self.custom_settings['FILES_STORE'])

        with open(pdf_path, 'wb') as f:
            f.write(response.body)

        self.logger.info(f"Saved PDF: {pdf_name}")

    def save_excel(self, response):
        url = response.meta['url']
        excel_name = os.path.basename(urlparse(url).path)
        excel_path = os.path.join(self.custom_settings['FILES_STORE'], excel_name)

        if not os.path.exists(self.custom_settings['FILES_STORE']):
            os.makedirs(self.custom_settings['FILES_STORE'])

        with open(excel_path, 'wb') as f:
            f.write(response.body)

        self.logger.info(f"Saved Excel: {excel_name}")

    def clean_text(self, text):
        text = text.strip()
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        text = unescape(text)
        text = re.sub(r'\s+', ' ', text)
        return text

    def closed(self, reason):
        self.logger.info(f"Spider closed due to: {reason}.")
