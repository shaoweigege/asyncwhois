"""
WHOIS module written in Python

Copyright (c) 2020 Joe Obarzanek

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import asyncio
import re
import socket
from typing import Union, Dict, Any

import tldextract # 2.2.2
import aiodns # 2.0.0

from .query import WhoIsQuery, AsyncWhoIsQuery
from .parser import WhoIsParser
from .errors import WhoIsQueryError


# https://www.regextester.com/104038
IPV4_OR_V6 = re.compile(r"((^\s*((([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5]))\s*$)|(^\s*((([0-9A-Fa-f]{1,4}:){7}([0-9A-Fa-f]{1,4}|:))|(([0-9A-Fa-f]{1,4}:){6}(:[0-9A-Fa-f]{1,4}|((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3})|:))|(([0-9A-Fa-f]{1,4}:){5}(((:[0-9A-Fa-f]{1,4}){1,2})|:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3})|:))|(([0-9A-Fa-f]{1,4}:){4}(((:[0-9A-Fa-f]{1,4}){1,3})|((:[0-9A-Fa-f]{1,4})?:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(([0-9A-Fa-f]{1,4}:){3}(((:[0-9A-Fa-f]{1,4}){1,4})|((:[0-9A-Fa-f]{1,4}){0,2}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(([0-9A-Fa-f]{1,4}:){2}(((:[0-9A-Fa-f]{1,4}){1,5})|((:[0-9A-Fa-f]{1,4}){0,3}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(([0-9A-Fa-f]{1,4}:){1}(((:[0-9A-Fa-f]{1,4}){1,6})|((:[0-9A-Fa-f]{1,4}){0,4}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(:(((:[0-9A-Fa-f]{1,4}){1,7})|((:[0-9A-Fa-f]{1,4}){0,5}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:)))(%.+)?\s*$))")


class _PyWhoIs:

    def __init__(self):
        self.__query = None
        self.__parser = None

    @staticmethod
    def _get_tld_extract(url: str) -> tldextract.tldextract.ExtractResult:
        extract_result = tldextract.extract(url)
        return extract_result

    @staticmethod
    def _get_hostname_from_ip(ip_address: str) -> Union[str, None]:
        try:
            host, _, _ = socket.gethostbyaddr(ip_address)
            return host
        except socket.gaierror:
            raise WhoIsQueryError(f'Could not resolve {ip_address}')

    @staticmethod
    async def _aio_get_hostname_from_ip(ip_address: str) -> Union[str, None]:
        loop = asyncio.get_event_loop()
        resolver = aiodns.DNSResolver(loop=loop)
        try:
            host = await resolver.gethostbyaddr(ip_address)
            return host.name
        except aiodns.error.DNSError:
            raise WhoIsQueryError(f'Could not resolve {ip_address}')

    @property
    def parser_output(self) -> Dict[str, Any]:
        return self.__parser.parser_output

    @property
    def query_output(self) -> str:
        return self.__query.query_output

    @classmethod
    def _from_url(cls, url: str, timeout: int):
        pywhois = cls()
        extract_result = tldextract.extract(url)

        if IPV4_OR_V6.match(extract_result.domain):
            host = pywhois._get_hostname_from_ip(extract_result.domain)
            extract_result = tldextract.extract(host)

        tld = extract_result.suffix
        if len(tld.split('.')) > 1:
            tld = tld.split('.')[-1]

        domain_and_tld = extract_result.domain + '.' + tld
        parser = WhoIsParser(tld)
        query = WhoIsQuery(domain_and_tld, parser._parser.server, timeout)
        parser.parse(query.query_output)
        pywhois.__query = query
        pywhois.__parser = parser
        return pywhois

    @classmethod
    async def _aio_from_url(cls, url: str, timeout: int):
        pywhois = cls()
        extract_result = tldextract.extract(url)

        if IPV4_OR_V6.match(extract_result.domain):
            host = await pywhois._aio_get_hostname_from_ip(extract_result.domain)
            extract_result = tldextract.extract(host)

        tld = extract_result.suffix
        if len(tld.split('.')) > 1:
            tld = tld.split('.')[-1]

        domain_and_tld = extract_result.domain + '.' + tld
        parser = WhoIsParser(tld)
        query = await AsyncWhoIsQuery.create(domain_and_tld, parser._parser.server, timeout)
        parser.parse(query.query_output)
        pywhois.__query = query
        pywhois.__parser = parser
        return pywhois
