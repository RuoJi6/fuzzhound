#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
请求发送模块
发送 HTTP 请求并记录响应 (AsyncIO 版本)
"""

import asyncio
import aiohttp
import time
import json
import logging
import ssl
from pathlib import Path
from datetime import datetime
from urllib.parse import urlencode, urlparse

logger = logging.getLogger('fuzzhound.request_sender')


class RequestSender:
    """请求发送器 (AsyncIO)"""
    
    def __init__(self, config):
        self.config = config
        self.timeout = config['target'].get('timeout', 10)
        self.verify_ssl = config['target'].get('verify_ssl', False)
        self.retry = config['request'].get('retry', 1)
        self.delay = config['request'].get('delay', 0)

        # 调试配置
        self.debug_config = config.get('debug', {})
        self.debug_enabled = self.debug_config.get('enabled', False)
        self.save_requests = self.debug_config.get('save_requests', False)
        self.save_responses = self.debug_config.get('save_responses', False)

        # 创建调试目录
        if self.debug_enabled and (self.save_requests or self.save_responses):
            log_dir = config.get('logging', {}).get('log_dir', 'logs')
            self.debug_dir = Path(log_dir) / 'debug'
            self.debug_dir.mkdir(parents=True, exist_ok=True)

        # 配置代理
        self.proxy = None
        proxy_config = config.get('proxy', {})
        if proxy_config.get('enabled', False):
            # aiohttp 只支持单个代理 URL，通常使用 http 代理即可处理 https 请求
            if proxy_config.get('http'):
                self.proxy = proxy_config['http']
            elif proxy_config.get('https'):
                self.proxy = proxy_config['https']

        # SSL 上下文
        self.ssl_context = ssl.create_default_context()
        if not self.verify_ssl:
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE

        # Session 将在 enter_context 中创建，或者在第一次发送时创建
        self.session = None
        
    async def __aenter__(self):
        """上下文管理器入口"""
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        connector = aiohttp.TCPConnector(ssl=self.ssl_context, limit=0) # limit=0 禁用连接池限制，由外部控制并发
        self.session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        if self.session:
            await self.session.close()

    async def close(self):
        """关闭 session"""
        if self.session:
            await self.session.close()

    async def send(self, request_data):
        """发送请求 (异步)"""
        if not self.session:
            # 如果没有使用上下文管理器，临时创建一个 session (不推荐，性能较差)
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            connector = aiohttp.TCPConnector(ssl=self.ssl_context, limit=0)
            self.session = aiohttp.ClientSession(timeout=timeout, connector=connector)

        method = request_data['method']
        url = request_data['url']
        headers = request_data.get('headers', {})
        params = request_data.get('params', {})
        body = request_data.get('body')

        logger.debug(f"📤 发送请求: {method} {url}")
        if params:
            logger.debug(f"   参数: {params}")
        if body:
            logger.debug(f"   请求体: {str(body)[:100]}...")

        # 延迟
        if self.delay > 0:
            await asyncio.sleep(self.delay)

        # 准备请求数据
        kwargs = {
            'headers': headers,
            'params': params,
            'proxy': self.proxy
        }
        
        # 处理请求体
        if body is not None:
            content_type = headers.get('Content-Type', '')
            
            if 'application/json' in content_type:
                kwargs['json'] = body
            elif 'application/x-www-form-urlencoded' in content_type:
                kwargs['data'] = body
            elif 'multipart/form-data' in content_type:
                # aiohttp 处理 multipart 比较特殊，这里简化处理，假设 body 是 FormData
                # 如果 body 是 dict，aiohttp 会自动处理为 form-data
                kwargs['data'] = body
            else:
                kwargs['data'] = body
        
        # 发送请求
        response = None
        error = None
        start_time = time.time()
        resp_content = b''
        resp_text = ''
        status_code = 0
        resp_headers = {}

        for attempt in range(self.retry + 1):
            try:
                async with self.session.request(method, url, **kwargs) as resp:
                    status_code = resp.status
                    resp_headers = dict(resp.headers)
                    # 读取响应内容
                    resp_content = await resp.read()
                    try:
                        resp_text = resp_content.decode('utf-8', errors='replace')
                    except:
                        resp_text = str(resp_content)
                    
                    # 请求成功
                    response = resp # 仅用于标记成功
                    break
            except Exception as e:
                error = str(e)
                if attempt < self.retry:
                    await asyncio.sleep(1)
                    continue

        end_time = time.time()
        elapsed_time = end_time - start_time

        # 构造结果
        result = {
            'request': request_data,
            'method': method,
            'url': url,
            'status_code': status_code,
            'response_length': len(resp_content),
            'response_time': elapsed_time,
            'response_headers': resp_headers,
            'response_body': self._parse_response_body(resp_text, resp_headers),
            'error': error,
            'success': response is not None and status_code < 400,
            'raw_request': self._build_raw_request(method, url, headers, params, body),
            'raw_response': self._build_raw_response(status_code, resp_headers, resp_text) if response is not None else ''
        }

        # 记录响应信息
        if response is not None:
            logger.debug(f"📥 收到响应: {status_code} ({len(resp_content)} bytes, {elapsed_time:.2f}s)")
        else:
            logger.debug(f"❌ 请求失败: {error}")

        # 调试模式：保存请求和响应详情
        if self.debug_enabled:
            self._save_debug_info(result)

        return result

    def _save_debug_info(self, result):
        """保存调试信息到文件"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            method = result['method']
            status = result['status_code']

            # 生成文件名（安全的文件名）
            url_path = result['url'].replace('://', '_').replace('/', '_').replace('?', '_')[:50]
            filename_base = f"{timestamp}_{method}_{status}_{url_path}"

            # 保存请求
            if self.save_requests:
                request_file = self.debug_dir / f"{filename_base}_request.txt"
                with open(request_file, 'w', encoding='utf-8') as f:
                    f.write(result['raw_request'])
                logger.debug(f"保存请求到: {request_file}")

            # 保存响应
            if self.save_responses:
                response_file = self.debug_dir / f"{filename_base}_response.txt"
                with open(response_file, 'w', encoding='utf-8') as f:
                    f.write(result['raw_response'])
                logger.debug(f"保存响应到: {response_file}")

        except Exception as e:
            logger.error(f"保存调试信息失败: {e}")
    
    def _parse_response_body(self, text, headers):
        """解析响应体"""
        try:
            content_type = headers.get('Content-Type', '')
            if 'application/json' in content_type:
                return json.loads(text)
            else:
                return text
        except:
            return text
    
    def _build_raw_request(self, method, url, headers, params, body):
        """构造原始请求包 (用于展示)"""
        parsed_url = urlparse(url)
        
        # 构造请求行
        path = parsed_url.path
        if params:
            path += '?' + urlencode(params)
        
        lines = [f"{method} {path} HTTP/1.1"]
        lines.append(f"Host: {parsed_url.netloc}")
        
        # 添加请求头
        for key, value in headers.items():
            lines.append(f"{key}: {value}")
        
        # 添加请求体
        if body is not None:
            content_type = headers.get('Content-Type', '')
            
            if 'application/json' in content_type:
                body_str = json.dumps(body, ensure_ascii=False, indent=2)
            elif isinstance(body, dict):
                body_str = urlencode(body)
            else:
                body_str = str(body)
            
            lines.append(f"Content-Length: {len(body_str)}")
            lines.append("")
            lines.append(body_str)
        else:
            lines.append("")
        
        return "\n".join(lines)
    
    def _build_raw_response(self, status_code, headers, body_text):
        """构造原始响应包 (用于展示)"""
        # 简单的状态码原因映射
        reasons = {200: 'OK', 404: 'Not Found', 500: 'Internal Server Error'}
        reason = reasons.get(status_code, 'Unknown')
        
        lines = [f"HTTP/1.1 {status_code} {reason}"]
        
        # 添加响应头
        for key, value in headers.items():
            lines.append(f"{key}: {value}")
        
        lines.append("")
        
        # 添加响应体
        try:
            content_type = headers.get('Content-Type', '')
            if 'application/json' in content_type:
                body_str = json.dumps(json.loads(body_text), ensure_ascii=False, indent=2)
            else:
                body_str = body_text[:1000]  # 限制长度
        except:
            body_str = body_text[:1000]
        
        lines.append(body_str)
        
        return "\n".join(lines)

