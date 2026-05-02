"""Async HTTP client with connection pooling, ETag caching, retry logic with jitter."""

import asyncio
import hashlib
import json
import random
import time
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone
from collections import OrderedDict

import aiohttp
from aiohttp import ClientTimeout, TCPConnector
import backoff

from .config import get_headers_dict, get_concurrency, get_http_config
from .logging import get_logger

logger = get_logger(__name__)

# In-memory ETag cache: {url: (etag, response_data, timestamp)}
_ETAG_CACHE: OrderedDict[str, Tuple[str, Any, float]] = OrderedDict()
_CACHE_MAX_SIZE = 100


def cache_put(url: str, etag: str, data: Any):
    """Store response in ETag cache."""
    if len(_ETAG_CACHE) >= _CACHE_MAX_SIZE:
        _ETAG_CACHE.popitem(last=False)
    _ETAG_CACHE[url] = (etag, data, time.time())


def cache_get(url: str) -> Optional[Tuple[str, Any]]:
    """Get cached response if ETag still valid."""
    if url in _ETAG_CACHE:
        etag, data, ts = _ETAG_CACHE[url]
        return etag, data
    return None


def cache_clear():
    """Clear ETag cache."""
    _ETAG_CACHE.clear()


class AsyncHttpClient:
    """Async HTTP client with pooling, retries, ETag caching."""
    
    def __init__(self, max_concurrent: int = 20):
        self.max_concurrent = max_concurrent
        self.connector = None
        self.session = None
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self._closed = False
    
    async def __aenter__(self):
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc, tb):
        await self.close()
    
    async def _ensure_session(self):
        """Create or reuse aiohttp session with connection pooling."""
        if self.session is None or self.session.closed:
            cfg = get_http_config()
            self.connector = TCPConnector(
                limit=cfg.get("connection_pool_size", 20),
                limit_per_host=5,
                keepalive_timeout=cfg.get("keepalive_timeout", 30),
                ttl_dns_cache=300,
                enable_cleanup_closed=True,
                force_close=False,
            )
            timeout = ClientTimeout(total=cfg.get("request_timeout", 30))
            self.session = aiohttp.ClientSession(
                connector=self.connector,
                timeout=timeout,
                headers=get_headers_dict(),
                raise_for_status=False,
            )
    
    async def close(self):
        """Close session and connector."""
        if self.session and not self.session.closed:
            await self.session.close()
        if self.connector:
            await self.connector.close()
        self._closed = True
    
    async def request(
        self,
        method: str,
        url: str,
        data: Optional[Dict] = None,
        use_etag: bool = True,
        max_retries: Optional[int] = None,
    ) -> Optional[Any]:
        """
        Make async HTTP request with retry, jitter, ETag caching.
        """
        async with self.semaphore:
            # Check ETag cache for GET requests
            if method.upper() == "GET" and use_etag:
                cached = cache_get(url)
                if cached:
                    etag, cached_data = cached
                    # Add If-None-Match header
                    headers = {"If-None-Match": etag}
                    resp_text, status, resp_etag = await self._do_request(
                        method, url, data, extra_headers=headers,
                        max_retries=max_retries
                    )
                    if status == 304:
                        logger.debug(f"Cache hit (ETag): {url}")
                        return cached_data
                    # If new data, update cache
                    if status == 200 and resp_etag:
                        try:
                            data_parsed = json.loads(resp_text)
                            cache_put(url, resp_etag, data_parsed)
                            return data_parsed
                        except json.JSONDecodeError:
                            return resp_text
                else:
                    # No cache, normal request
                    return await self._request_with_retry(method, url, data, max_retries)
            else:
                return await self._request_with_retry(method, url, data, max_retries)
    
    async def _request_with_retry(
        self,
        method: str,
        url: str,
        data: Optional[Dict],
        max_retries: Optional[int] = None
    ) -> Optional[Any]:
        """Wrapper with exponential backoff + jitter."""
        cfg = get_concurrency()
        retries = max_retries or cfg.get("max_retries", 3)
        base_delay = cfg.get("retry_backoff_base", 2)
        jitter = cfg.get("retry_jitter", True)
        
        last_exc = None
        
        for attempt in range(retries + 1):
            try:
                resp_text, status, etag = await self._do_request(method, url, data)
                if status in (200, 201, 204):
                    if method.upper() == "GET" and etag:
                        try:
                            parsed = json.loads(resp_text)
                            cache_put(url, etag, parsed)
                            return parsed
                        except json.JSONDecodeError:
                            return resp_text
                    elif method.upper() == "GET":
                        try:
                            return json.loads(resp_text)
                        except json.JSONDecodeError:
                            return resp_text
                    return {"_status": status, "_text": resp_text, "_etag": etag}
                elif status in (429, 500, 502, 503, 504):
                    if attempt < retries:
                        delay = self._calc_delay(attempt, base_delay, jitter)
                        logger.warning(f"HTTP {status} for {url}, retrying in {delay:.1f}s (attempt {attempt + 1}/{retries})")
                        await asyncio.sleep(delay)
                        continue
                else:
                    logger.error(f"HTTP {status} for {url}: {resp_text[:200]}")
                    return None
                    
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_exc = e
                if attempt < retries:
                    delay = self._calc_delay(attempt, base_delay, jitter)
                    logger.warning(f"Request failed: {e}, retrying in {delay:.1f}s")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Request failed after {retries} retries: {e}")
        
        return None
    
    def _calc_delay(self, attempt: int, base: float, jitter: bool) -> float:
        """Exponential backoff with optional jitter."""
        delay = base ** attempt
        if jitter:
            delay *= (0.5 + random.random() * 0.5)  # ±50%
        return delay
    
    async def _do_request(
        self,
        method: str,
        url: str,
        data: Optional[Dict],
        extra_headers: Optional[Dict] = None
    ) -> Tuple[str, int, Optional[str]]:
        """Execute single HTTP request."""
        await self._ensure_session()
        
        headers = dict(self.session.headers)
        if extra_headers:
            headers.update(extra_headers)
        
        try:
            async with self.session.request(
                method=method,
                url=url,
                json=data if data else None,
                headers=headers,
                ssl=True,
                allow_redirects=True,
            ) as resp:
                text = await resp.text()
                etag = resp.headers.get("ETag", "").strip('"')
                return text, resp.status, etag if etag else None
        except Exception as e:
            logger.error(f"Request error for {url}: {e}")
            raise
    
    async def get(self, url: str, use_etag: bool = True) -> Optional[Any]:
        """GET request with ETag caching."""
        return await self.request("GET", url, use_etag=use_etag)
    
    async def post(self, url: str, data: Optional[Dict] = None) -> Optional[Any]:
        """POST request."""
        return await self.request("POST", url, data)


# Global client instance (reused across calls)
_global_client: Optional[AsyncHttpClient] = None


async def get_client() -> AsyncHttpClient:
    """Get or create global async HTTP client."""
    global _global_client
    if _global_client is None or _global_client._closed:
        cfg = get_concurrency()
        _global_client = AsyncHttpClient(max_concurrent=cfg.get("max_concurrent_matches", 20))
    return _global_client


async def close_client():
    """Close global client."""
    global _global_client
    if _global_client and not _global_client._closed:
        await _global_client.close()
    _global_client = None
