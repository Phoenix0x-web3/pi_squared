from curl_cffi import CurlError
import asyncio
import random
import json
from typing import Dict, Tuple, Union, Optional
from loguru import logger

from data.settings import Settings
from utils.db_api.wallet_api import get_wallet_by_id, save_bearer_token, save_refresh_token
from utils.db_api.models import Wallet
from utils.browser import Browser
from utils.resource_manager import ResourceManager


class BaseHttpClient:
    """Base HTTP client for making requests"""
    def __init__(self, user: Wallet):
        """
        Initialize the base HTTP client

        Args:
            user: User with email data and proxy
        """
        self.user = user
        self.browser = Browser(user)
        self.cookies = {}
        # Proxy error counter
        self.proxy_errors = 0
        # Settings for automatic resource error handling
        self.settings = Settings()
        self.max_proxy_errors = self.settings.resources_max_failures
        self.base_headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate",
            'Origin': 'https://portal.pi2.network',
            "Connection": "keep-alive",
            'Referer': 'https://portal.pi2.network/',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            'Sec-Fetch-Site': 'cross-site',
            "Priority": "u=0",
        }


    async def get_headers(self, additional_headers: Optional[Dict] = None): 
        """
        Create base headers for requests

        Args:
            additional_headers: Additional headers

        Returns:
            Formatted headers
        """

        if additional_headers:
            self.base_headers.update(additional_headers)
        return self.base_headers


    async def request(
        self,
        url: str,
        method: str,
        data: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        timeout: int = 30,
        retries: int = 5,
        allow_redirects: bool = True,
    ) -> Tuple[bool, Union[Dict, str]]:
        """
        Perform HTTP request with automatic captcha and proxy error handling

        Args:
            url: Request URL
            method: Request method (GET, POST, etc.)
            data: Form data
            json_data: JSON data
            params: URL parameters
            headers: Additional headers
            timeout: Request timeout in seconds
            retries: Number of retry attempts
            allow_redirects: Follow redirects

        Returns:
            (bool, data): Success status and response data
        """
        base_headers = await self.get_headers(headers)

        # Set up request parameters
        request_kwargs = {
            "url": url,
            "headers": base_headers,
            "cookies": self.cookies,
            "timeout": timeout,
            "allow_redirects": allow_redirects,
        }
        # Add optional parameters
        if json_data is not None:
            request_kwargs["json"] = json_data
        if data is not None:
            request_kwargs["data"] = data
        if params is not None:
            request_kwargs["params"] = params

        logger.debug(request_kwargs)
        # Perform request with retries
        for attempt in range(retries):
            try:
              #  logger.debug(request_kwargs)
                method_func = getattr(self.browser, method.lower())
                resp = await method_func(**request_kwargs)

                # Save cookies from response
                if resp.cookies:
                    for name, cookie in resp.cookies.items():
                        self.cookies[name] = cookie

                if resp.headers and "x-access-token" in resp.headers:
                    logger.debug(f"Get x-access-token {resp.headers['x-access-token']}")
                    self.base_headers["Authorization"] = resp.headers['x-access-token']
                    save_bearer_token(id=self.user.id, bearer_token=resp.headers['x-access-token'])
                if resp.headers and "x-refresh-token" in resp.headers:
                    logger.debug(f"Get x-access-token {resp.headers['x-refresh-token']}")
                    self.base_headers["X-Refresh-Token"] = resp.headers['x-refresh-token']
                    save_refresh_token(id=self.user.id, refresh_token=resp.headers['x-refresh-token'])

                if resp.status_code == 304:
                    json_resp = resp.json()
                    return True, json_resp
                if 300 <= resp.status_code < 400 and not allow_redirects:
                    headers_dict = dict(resp.headers)
                    return False, headers_dict

                # Successful response
                if resp.status_code == 200 or resp.status_code == 202 or resp.status_code == 201:
                    # Reset proxy error counter on successful request
                    self.proxy_errors = 0
                    try:
                        json_resp = resp.json()
                        return True, json_resp
                    except Exception:
                        return True, resp.text

                # Get response text for analysis
                response_text = resp.text


                # Handle errors
                if 400 <= resp.status_code < 500:
                    logger.warning(
                        f"{self.user} received status {resp.status_code} for request {url}"
                    )

                    # Check for authorization issues
                    if resp.status_code == 401 or resp.status_code == 403:
                        if "!DOCTYPE" not in response_text:
                            logger.error(
                                f"{self.user} authorization error: {response_text}"
                            )
                        return False, response_text

                    # Check for rate limiting
                    if resp.status_code == 429:
                        logger.warning(f"{self.user} rate limit exceeded (429)")

                        # If not last attempt, wait and retry
                        if attempt < retries - 1:
                            wait_time = random.uniform(10, 30)  # 10-30 seconds
                            logger.info(
                                f"{self.user} waiting {int(wait_time)} seconds before next attempt"
                            )
                            await asyncio.sleep(wait_time)
                            continue

                        # Parse response for possible error JSON
                        try:
                            error_json = json.loads(response_text)
                            return False, error_json
                        except Exception:
                            return False, "RATE_LIMIT"

                    # Parse response for possible error JSON
                    try:
                        error_json = json.loads(response_text)
                        return False, error_json
                    except Exception:
                        return False, response_text

                elif 500 <= resp.status_code < 600:
                    logger.warning(
                        f"{self.user} received status {resp.status_code}, retry attempt {attempt + 1}/{retries}"
                    )
                    await asyncio.sleep(2**attempt)  # Exponential backoff
                    continue

                return False, response_text

            except CurlError as e:
                logger.warning(
                    f"{self.user} connection error during request {url}: {str(e)}"
                )

                # Increment proxy error counter
                if (
                    "proxy" in str(e).lower()
                    or "connection" in str(e).lower()
                    or "connect" in str(e).lower()
                ):
                    self.proxy_errors += 1

                    # If proxy error limit exceeded, mark proxy as bad
                    if self.proxy_errors >= self.max_proxy_errors:
                        logger.warning(
                            f"{self.user} proxy error limit exceeded ({self.proxy_errors}/{self.max_proxy_errors}), marking as BAD"
                        )

                        resource_manager = ResourceManager()
                        await resource_manager.mark_proxy_as_bad(self.user.id)

                        # If auto-replace is enabled, try to replace proxy
                        if self.settings.auto_replace_proxy:
                            success, message = await resource_manager.replace_proxy(
                                self.user.id
                            )
                            if success:
                                logger.info(
                                    f"{self.user} proxy automatically replaced: {message}"
                                )
                                # Update proxy for current client
                                updated_user = get_wallet_by_id(id=self.user.id)
                                if updated_user:
                                    self.user.proxy = updated_user.proxy
                                    # Reset error counter
                                    self.proxy_errors = 0
                                    # Update browser with new proxy
                                    self.browser = Browser(self.user)
                            else:
                                logger.error(
                                    f"{self.user} failed to replace proxy: {message}"
                                )

                await asyncio.sleep(2**attempt)  # Exponential backoff
                continue

            except Exception as e:
                logger.error(
                    f"{self.user} unexpected error during request {url}: {str(e)}"
                )
                return False, str(e)
        return False, ""
