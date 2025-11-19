#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
请求发送模块
发送 HTTP 请求并记录响应
"""

import requests
import time
import json
import urllib3
import logging
from pathlib import Path
from datetime import datetime
from urllib.parse import urlencode

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger('fuzzhound.request_sender')


class RequestSender:
    """请求发送器"""
    
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
        self.proxies = None
        proxy_config = config.get('proxy', {})
        if proxy_config.get('enabled', False):
            self.proxies = {}
            if proxy_config.get('http'):
                self.proxies['http'] = proxy_config['http']
            if proxy_config.get('https'):
                self.proxies['https'] = proxy_config['https']

        # 创建 session
        self.session = requests.Session()
        if self.proxies:
            self.session.proxies.update(self.proxies)
        
    def send(self, request_data):
        """发送请求"""
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
            time.sleep(self.delay)

        # 准备请求数据
        kwargs = {
            'timeout': self.timeout,
            'verify': self.verify_ssl,
            'headers': headers,
            'params': params
        }
        
        # 处理请求体
        if body is not None:
            content_type = headers.get('Content-Type', '')
            
            if 'application/json' in content_type:
                kwargs['json'] = body
            elif 'application/x-www-form-urlencoded' in content_type:
                kwargs['data'] = body
            elif 'multipart/form-data' in content_type:
                kwargs['files'] = body
            else:
                kwargs['data'] = body
        
        # 发送请求
        response = None
        error = None
        start_time = time.time()

        for attempt in range(self.retry + 1):
            try:
                response = self.session.request(method, url, **kwargs)
                # 请求成功，即使状态码是 4xx 或 5xx 也不算异常
                break
            except requests.exceptions.RequestException as e:
                error = str(e)
                if attempt < self.retry:
                    time.sleep(1)
                    continue

        end_time = time.time()
        elapsed_time = end_time - start_time

        # 构造结果
        # 注意：只有在网络异常（response 为 None）时才显示状态码 0
        # 如果请求成功但返回 4xx/5xx，应该显示真实的状态码
        # 重要：必须使用 "is not None" 而不是 "if response"，因为 Response 对象的 __bool__
        # 方法在状态码为 4xx/5xx 时返回 False
        result = {
            'request': request_data,
            'method': method,
            'url': url,
            'status_code': response.status_code if response is not None else 0,
            'response_length': len(response.content) if response is not None else 0,
            'response_time': elapsed_time,
            'response_headers': dict(response.headers) if response is not None else {},
            'response_body': self._get_response_body(response) if response is not None else '',
            'error': error,
            'success': response is not None and response.status_code < 400,
            'raw_request': self._build_raw_request(method, url, headers, params, body),
            'raw_response': self._build_raw_response(response) if response is not None else ''
        }

        # 记录响应信息
        if response is not None:
            logger.debug(f"📥 收到响应: {response.status_code} ({len(response.content)} bytes, {elapsed_time:.2f}s)")
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
    
    def _get_response_body(self, response):
        """获取响应体"""
        try:
            content_type = response.headers.get('Content-Type', '')
            if 'application/json' in content_type:
                return response.json()
            else:
                return response.text
        except:
            return response.text
    
    def _build_raw_request(self, method, url, headers, params, body):
        """构造原始请求包"""
        from urllib.parse import urlparse, parse_qs
        
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
    
    def _build_raw_response(self, response):
        """构造原始响应包"""
        lines = [f"HTTP/1.1 {response.status_code} {response.reason}"]
        
        # 添加响应头
        for key, value in response.headers.items():
            lines.append(f"{key}: {value}")
        
        lines.append("")
        
        # 添加响应体
        try:
            content_type = response.headers.get('Content-Type', '')
            if 'application/json' in content_type:
                body_str = json.dumps(response.json(), ensure_ascii=False, indent=2)
            else:
                body_str = response.text[:1000]  # 限制长度
        except:
            body_str = response.text[:1000]
        
        lines.append(body_str)
        
        return "\n".join(lines)

