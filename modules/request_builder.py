#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
请求构造模块
根据 API 定义构造 HTTP 请求
"""

import json
import random
import os
import logging
from urllib.parse import urljoin
from typing import List, Dict, Any, Optional, Union, Tuple
from modules.utils import generate_test_value, create_test_file

logger = logging.getLogger('fuzzhound.request_builder')


class RequestBuilder:
    """请求构造器"""

    def __init__(self, config):
        self.config = config
        self.base_url = config['target']['base_url']
        self.custom_prefix = config['target'].get('custom_prefix', '')
        self.user_agents = self._load_user_agents()

        # 用户名 Fuzz 配置
        self.fuzz_username_enabled = config.get('fuzz_username', {}).get('enabled', False)
        self.username_keywords = [kw.lower() for kw in config.get('fuzz_username', {}).get('keywords', [])]
        self.usernames = self._load_usernames() if self.fuzz_username_enabled else []

        # 密码 Fuzz 配置
        self.fuzz_password_enabled = config.get('fuzz_password', {}).get('enabled', False)
        self.password_keywords = [kw.lower() for kw in config.get('fuzz_password', {}).get('keywords', [])]
        self.passwords = self._load_passwords() if self.fuzz_password_enabled else []

        # 数字型 Fuzz 配置
        self.fuzz_number_enabled = config.get('fuzz_number', {}).get('enabled', False)
        self.fuzz_number_config = config.get('fuzz_number', {})
        self.number_values = self._generate_number_values() if self.fuzz_number_enabled else []

        # SQL注入 Fuzz 配置
        self.fuzz_sql_enabled = config.get('fuzz_sql', {}).get('enabled', False)
        self.sql_keywords = [kw.lower() for kw in config.get('fuzz_sql', {}).get('keywords', [])]
        self.sql_payloads = self._load_sql_payloads() if self.fuzz_sql_enabled else []

    def _load_usernames(self):
        """加载用户名字典"""
        username_file = self.config.get('fuzz_username', {}).get('username_file', 'config/usernames.txt')
        count = self.config.get('fuzz_username', {}).get('count', 15)  # 默认15个
        usernames = []

        if os.path.exists(username_file):
            try:
                with open(username_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        # 跳过空行和注释
                        if line and not line.startswith('#'):
                            usernames.append(line)

                total_count = len(usernames)

                # 如果配置了数量限制且不为0（0表示全部）
                if count > 0 and count < total_count:
                    # 随机挑选指定数量
                    usernames = random.sample(usernames, count)
                    logger.info(f"✅ 加载用户名字典成功: 从 {total_count} 个中随机挑选 {len(usernames)} 个")
                else:
                    logger.info(f"✅ 加载用户名字典成功: {len(usernames)} 个用户名（全部）")
            except Exception as e:
                logger.error(f"❌ 加载用户名字典失败: {e}")
        else:
            logger.warning(f"⚠ 用户名字典文件不存在: {username_file}")

        return usernames

    def _load_passwords(self):
        """加载密码字典"""
        password_file = self.config.get('fuzz_password', {}).get('password_file', 'config/top100_password.txt')
        count = self.config.get('fuzz_password', {}).get('count', 15)  # 默认15个
        passwords = []

        if os.path.exists(password_file):
            try:
                with open(password_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        # 跳过空行和注释
                        if line and not line.startswith('#'):
                            passwords.append(line)

                total_count = len(passwords)

                # 如果配置了数量限制且不为0（0表示全部）
                if count > 0 and count < total_count:
                    # 随机挑选指定数量
                    passwords = random.sample(passwords, count)
                    logger.info(f"✅ 加载密码字典成功: 从 {total_count} 个中随机挑选 {len(passwords)} 个")
                else:
                    logger.info(f"✅ 加载密码字典成功: {len(passwords)} 个密码（全部）")
            except Exception as e:
                logger.error(f"❌ 加载密码字典失败: {e}")
        else:
            logger.warning(f"⚠ 密码字典文件不存在: {password_file}")

        return passwords

    def _generate_number_values(self):
        """生成数字型 Fuzz 值"""
        mode = self.fuzz_number_config.get('mode', 'random')

        if mode == 'range':
            # 范围遍历模式
            start = self.fuzz_number_config.get('range_start', 1)
            end = self.fuzz_number_config.get('range_end', 100)
            values = list(range(start, end + 1))
            logger.info(f"✅ 生成数字型 Fuzz 值: 范围遍历 {start}-{end}，共 {len(values)} 个")
        else:
            # 随机挑选模式
            count = self.fuzz_number_config.get('count', 15)
            start = self.fuzz_number_config.get('default_range_start', 1)
            end = self.fuzz_number_config.get('default_range_end', 1000)

            # 如果范围小于等于数量，直接返回所有值
            if end - start + 1 <= count:
                values = list(range(start, end + 1))
            else:
                # 随机挑选
                values = random.sample(range(start, end + 1), count)
                values.sort()  # 排序便于查看

            logger.info(f"✅ 生成数字型 Fuzz 值: 从 {start}-{end} 随机挑选 {len(values)} 个")

        return values

    def _load_user_agents(self):
        """加载 User-Agent 列表"""
        ua_file = 'config/user_agents.txt'
        user_agents = []

        if os.path.exists(ua_file):
            try:
                with open(ua_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        # 跳过空行和注释
                        if line and not line.startswith('#'):
                            user_agents.append(line)
            except Exception as e:
                print(f"⚠ 加载 User-Agent 文件失败: {e}")

        # 如果没有加载到 UA，使用默认列表
        if not user_agents:
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
            ]

        return user_agents

    def _load_sql_payloads(self):
        """加载SQL注入payload列表"""
        payload_file = self.config.get('fuzz_sql', {}).get('payload_file', 'config/sql_payloads.txt')
        payloads = []

        if not os.path.exists(payload_file):
            logger.warning(f"⚠️  SQL payload文件不存在: {payload_file}，使用内置payload")
            return self._get_builtin_sql_payloads()

        try:
            with open(payload_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # 跳过空行和注释
                    if line and not line.startswith('#'):
                        payloads.append(line)

            logger.info(f"📖 从文件加载了 {len(payloads)} 个SQL注入payload")

            # 根据模式过滤payload
            mode = self.config.get('fuzz_sql', {}).get('mode', 'smart')
            max_payloads = self.config.get('fuzz_sql', {}).get('max_payloads', 20)  # 默认值改为20

            if mode == 'basic':
                # 基础模式：只使用前10个最常见、最有效的payload
                # 这些是最基础的SQL注入测试，适合快速检测
                payloads = payloads[:10]
                logger.info(f"   使用 basic 模式，限制为 {len(payloads)} 个payload（最常见的基础测试）")
            elif mode == 'smart':
                # 智能模式：根据配置限制payload数量
                # 这个模式会在后续根据参数类型智能选择payload
                payloads = payloads[:max_payloads]
                logger.info(f"   使用 smart 模式，限制为 {len(payloads)} 个payload (配置: max_payloads={max_payloads})")
            elif mode == 'full':
                # 全量模式：使用所有payload，不做任何过滤
                # 这个模式最全面，但测试时间最长
                logger.info(f"   使用 full 模式，使用所有 {len(payloads)} 个payload（全面检测）")
            else:
                # 未知模式，使用所有payload
                logger.warning(f"   ⚠️  未知模式 '{mode}'，使用所有 {len(payloads)} 个payload")

            # 保存原始payload列表，供智能选择使用
            self.all_sql_payloads = payloads.copy()

            return payloads
        except Exception as e:
            logger.error(f"❌ 加载SQL payload文件失败: {e}")
            return self._get_builtin_sql_payloads()

    def _get_builtin_sql_payloads(self):
        """获取内置SQL注入payload"""
        return [
            "'",
            "\"",
            "' OR '1'='1",
            "\" OR \"1\"=\"1",
            "' OR 1=1--",
            "\" OR 1=1--",
            "'--",
            "\"--",
            "'''",
            "\"\"\"",
            "' UNION SELECT NULL--",
            "\" UNION SELECT NULL--",
            "-1",
            "1 OR 1=1",
            "admin' OR '1'='1",
        ]

    def _get_random_user_agent(self):
        """获取随机 User-Agent"""
        return random.choice(self.user_agents)

    def _should_fuzz_username(self, param_name, param_type=''):
        """判断参数是否应该进行用户名 Fuzz

        Args:
            param_name: 参数名称
            param_type: 参数类型（可选）

        Returns:
            bool: 是否应该 Fuzz
        """
        if not self.fuzz_username_enabled:
            return False

        # 检查参数类型：用户名Fuzz只适用于字符串型参数
        if param_type:
            param_type_lower = param_type.lower()
            is_string = param_type_lower in ['string', 'str', 'text', '']
            if not is_string:
                return False

        # 如果关键字列表为空或包含 'all'，测试所有字符串型参数
        if not self.username_keywords or 'all' in self.username_keywords:
            logger.debug(f"🎯 参数 '{param_name}' 将进行用户名 Fuzz（all模式）")
            return True

        param_name_lower = param_name.lower()

        # 检查参数名是否包含任一关键字
        for keyword in self.username_keywords:
            if keyword in param_name_lower:
                logger.debug(f"🎯 参数 '{param_name}' 匹配关键字 '{keyword}'，将进行用户名 Fuzz")
                return True

        return False

    def _should_fuzz_password(self, param_name, param_type=''):
        """判断参数是否应该进行密码 Fuzz

        Args:
            param_name: 参数名称
            param_type: 参数类型（可选）

        Returns:
            bool: 是否应该 Fuzz
        """
        if not self.fuzz_password_enabled:
            return False

        # 检查参数类型：密码Fuzz只适用于字符串型参数
        if param_type:
            param_type_lower = param_type.lower()
            is_string = param_type_lower in ['string', 'str', 'text', '']
            if not is_string:
                return False

        # 如果关键字列表为空或包含 'all'，测试所有字符串型参数
        if not self.password_keywords or 'all' in self.password_keywords:
            logger.debug(f"🎯 参数 '{param_name}' 将进行密码 Fuzz（all模式）")
            return True

        param_name_lower = param_name.lower()

        # 检查参数名是否包含任一关键字
        for keyword in self.password_keywords:
            if keyword in param_name_lower:
                logger.debug(f"🎯 参数 '{param_name}' 匹配关键字 '{keyword}'，将进行密码 Fuzz")
                return True

        return False

    def _should_fuzz_sql(self, param_name, param_type=''):
        """判断参数是否应该进行SQL注入 Fuzz

        Args:
            param_name: 参数名称
            param_type: 参数类型

        Returns:
            bool: 是否应该 Fuzz
        """
        if not self.fuzz_sql_enabled:
            return False

        # 检查参数类型
        test_numeric = self.config.get('fuzz_sql', {}).get('test_numeric', True)
        test_string = self.config.get('fuzz_sql', {}).get('test_string', True)

        param_type_lower = param_type.lower() if param_type else ''
        is_numeric = param_type_lower in ['integer', 'int', 'number', 'long', 'float', 'double']
        is_string = param_type_lower in ['string', 'str', 'text', '']

        # 如果类型不匹配配置，跳过
        if is_numeric and not test_numeric:
            return False
        if is_string and not test_string:
            return False

        # 如果没有配置关键字或包含 'all'，测试所有符合类型的参数
        if not self.sql_keywords or 'all' in self.sql_keywords:
            logger.debug(f"🎯 参数 '{param_name}' 将进行SQL注入 Fuzz（all模式）")
            return True

        param_name_lower = param_name.lower()

        # 检查参数名是否包含任一关键字
        for keyword in self.sql_keywords:
            if keyword in param_name_lower:
                logger.debug(f"🎯 参数 '{param_name}' 匹配关键字 '{keyword}'，将进行SQL注入 Fuzz")
                return True

        return False

    def _get_enum_params(self, api):
        """获取所有包含枚举值的参数

        Args:
            api: API 定义

        Returns:
            dict: {param_name: [enum_values]}
        """
        enum_params = {}
        parameters = api.get('parameters', {})

        # 检查路径参数
        for param in parameters.get('path', []):
            param_name = param.get('name', '')
            param_schema = param.get('schema', {})
            if param_schema.get('enum'):
                enum_params[param_name] = param_schema['enum']

        # 检查查询参数
        for param in parameters.get('query', []):
            param_name = param.get('name', '')
            param_schema = param.get('schema', {})
            if param_schema.get('enum'):
                enum_params[param_name] = param_schema['enum']

        return enum_params

    def _generate_enum_combinations(self, enum_params, limit=0):
        """生成所有枚举值的组合

        Args:
            enum_params: {param_name: [enum_values]}
            limit: 每个枚举参数测试的值数量，0=测试所有值

        Returns:
            list: [{param_name: value}, ...]
        """
        if not enum_params:
            return [{}]

        import itertools

        # 获取参数名和对应的枚举值列表
        param_names = list(enum_params.keys())
        enum_value_lists = []

        for name in param_names:
            values = enum_params[name]
            # 如果设置了限制，只取前 N 个值
            if limit > 0 and len(values) > limit:
                values = values[:limit]
                logger.debug(f"   枚举参数 '{name}' 限制为前 {limit} 个值: {values}")
            enum_value_lists.append(values)

        # 生成所有组合
        combinations = []
        for values in itertools.product(*enum_value_lists):
            combination = dict(zip(param_names, values))
            combinations.append(combination)

        return combinations

    def build(self, api, double_check=True):
        """构造普通请求（不包含Fuzz）

        Args:
            api: API 定义
            double_check: 是否进行双重检查（先访问原始URL，再访问添加参数后的URL）
        """
        logger.debug(f"🔨 构建普通请求: {api['method']} {api['path']}")
        requests = []

        # 获取枚举参数测试限制（0=测试所有值，默认）
        enum_test_limit = self.config.get('request', {}).get('enum_test_limit', 0)

        # 获取所有枚举参数
        enum_params = self._get_enum_params(api)

        # 生成枚举值组合
        if enum_params:
            enum_combinations = self._generate_enum_combinations(enum_params, enum_test_limit)
            if enum_test_limit > 0:
                logger.debug(f"   枚举参数测试：限制每个参数前 {enum_test_limit} 个值，生成 {len(enum_combinations)} 个组合")
            else:
                logger.debug(f"   枚举参数测试：测试所有枚举值，生成 {len(enum_combinations)} 个组合")
        else:
            # 没有枚举参数，使用默认值（None 表示使用 generate_test_value 的默认逻辑）
            enum_combinations = [None]

        # 为每个枚举组合生成请求
        for enum_values in enum_combinations:
            if double_check:
                # 检查是否有查询参数
                has_query_params = len(api['parameters'].get('query', [])) > 0
                logger.debug(f"   查询参数数量: {len(api['parameters'].get('query', []))}")

                # 1. 先构造不带参数的原始请求（仅路径参数）
                original_request = self._build_basic_request(api, include_query_params=False, enum_values=enum_values)
                original_request['is_original'] = True

                # 如果有枚举值，添加到描述中
                if enum_values:
                    enum_desc = ', '.join([f'{k}={v}' for k, v in enum_values.items()])
                    original_request['description'] = f"{api.get('summary', '')} [原始URL, 枚举: {enum_desc}]"
                else:
                    original_request['description'] = f"{api.get('summary', '')} [原始URL]"

                requests.append(original_request)
                logger.debug(f"   ✓ 构建原始请求: {original_request['url']}")

                # 2. 只有当有查询参数时，才构造带参数的请求
                if has_query_params:
                    full_request = self._build_basic_request(api, include_query_params=True, enum_values=enum_values)
                    full_request['is_original'] = False

                    # 如果有枚举值，添加到描述中
                    if enum_values:
                        enum_desc = ', '.join([f'{k}={v}' for k, v in enum_values.items()])
                        full_request['description'] = f"{api.get('summary', '')} [添加参数, 枚举: {enum_desc}]"
                    else:
                        full_request['description'] = f"{api.get('summary', '')} [添加参数]"

                    # 显示拼接信息
                    if full_request.get('params'):
                        full_request['param_info'] = f"添加参数: {', '.join([f'{k}={v}' for k, v in full_request['params'].items()])}"

                    requests.append(full_request)
                    logger.debug(f"   ✓ 构建带参数请求: {full_request['url']}")
            else:
                # 构造基础请求（带所有参数）
                request = self._build_basic_request(api, include_query_params=True, enum_values=enum_values)

                # 如果有枚举值，添加到描述中
                if enum_values:
                    enum_desc = ', '.join([f'{k}={v}' for k, v in enum_values.items()])
                    request['description'] = f"{api.get('summary', '')} [枚举: {enum_desc}]"

                requests.append(request)
                logger.debug(f"   ✓ 构建请求: {request['url']}")

        return requests

    def build_fuzz_requests(self, api):
        """构造Fuzz请求（在普通请求完成后调用）

        Args:
            api: API 定义

        Returns:
            list: Fuzz 请求列表
        """
        logger.debug(f"🔨 构建Fuzz请求: {api['method']} {api['path']}")
        fuzz_requests = []

        # 1. 用户名 Fuzz（如果启用）
        if self.fuzz_username_enabled and self.usernames:
            requests = self._build_username_fuzz_requests(api)
            if requests:
                fuzz_requests.extend(requests)
                logger.debug(f"   ✓ 构建用户名 Fuzz 请求: {len(requests)} 个")

        # 2. 密码 Fuzz（如果启用）
        if self.fuzz_password_enabled and self.passwords:
            requests = self._build_password_fuzz_requests(api)
            if requests:
                fuzz_requests.extend(requests)
                logger.debug(f"   ✓ 构建密码 Fuzz 请求: {len(requests)} 个")

        # 3. 数字型 Fuzz（如果启用）
        if self.fuzz_number_enabled and self.number_values:
            requests = self._build_number_fuzz_requests(api)
            if requests:
                fuzz_requests.extend(requests)
                logger.debug(f"   ✓ 构建数字型 Fuzz 请求: {len(requests)} 个")

        # 4. SQL注入 Fuzz（如果启用）
        if self.fuzz_sql_enabled and self.sql_payloads:
            requests = self._build_sql_fuzz_requests(api)
            if requests:
                fuzz_requests.extend(requests)
                logger.debug(f"   ✓ 构建SQL注入 Fuzz 请求: {len(requests)} 个")

        return fuzz_requests
    
    def _build_basic_request(self, api, include_query_params=True, enum_values=None):
        """构造基础请求

        Args:
            api: API 定义
            include_query_params: 是否包含查询参数
            enum_values: 指定要使用的枚举值字典 {param_name: value}，如果为 None 则使用默认值
        """
        method = api['method']
        path = api['path']
        parameters = api['parameters']

        # 处理路径参数
        path_params = {}
        for param in parameters.get('path', []):
            param_name = param.get('name', '')
            param_type = param.get('type', 'string')
            param_schema = param.get('schema', {})
            if not param_name or not param_name.strip():
                logger.warning(f"⚠️  跳过空参数名的路径参数: {param}")
                continue
            logger.debug(f"   处理路径参数: {param_name}, 类型: {param_type}, schema: {param_schema}")

            # 如果指定了枚举值，使用指定的值；否则使用默认值
            if enum_values and param_name in enum_values:
                value = enum_values[param_name]
                logger.debug(f"   使用指定的枚举值: {value}")
            else:
                value = generate_test_value(param_type, param_name, self.config, param_schema)
                logger.debug(f"   生成的值: {value}")

            path_params[param_name] = value
            path = path.replace('{' + param_name + '}', str(value))

        # 处理查询参数
        query_params = {}
        if include_query_params:
            for param in parameters.get('query', []):
                param_name = param.get('name', '')
                param_schema = param.get('schema', {})

                # 如果指定了枚举值，使用指定的值；否则使用默认值
                if enum_values and param_name in enum_values:
                    value = enum_values[param_name]
                else:
                    value = generate_test_value(param['type'], param_name, self.config, param_schema)

                query_params[param_name] = value
        
        # 处理请求头
        headers = {}

        # 1. 添加自定义请求头（从配置文件）
        custom_headers = self.config['request'].get('headers', {})
        if custom_headers:
            headers.update(custom_headers)

        # 2. 设置随机 User-Agent（如果配置启用且配置文件中没有指定）
        use_random_ua = self.config['request'].get('random_ua', True)
        if use_random_ua and 'User-Agent' not in headers:
            headers['User-Agent'] = self._get_random_user_agent()

        # 3. 根据请求方法和 API 定义设置 Accept 头（如果配置文件中没有指定）
        if 'Accept' not in headers:
            # 只有 POST/PUT/PATCH 请求才需要 Accept 头
            if method.upper() in ['POST', 'PUT', 'PATCH']:
                # 从 API 定义中获取 consumes（Swagger 2.0）或 requestBody content types（OpenAPI 3.0）
                accept_types = api.get('consumes', [])

                # 如果 API 定义了 consumes，使用第一个
                if accept_types:
                    headers['Accept'] = accept_types[0]
                else:
                    # 默认使用 application/json
                    headers['Accept'] = 'application/json'

        # 4. 添加更真实的浏览器请求头
        if 'Accept-Language' not in headers:
            headers['Accept-Language'] = 'zh-CN,zh;q=0.9,en;q=0.8'
        if 'Accept-Encoding' not in headers:
            headers['Accept-Encoding'] = 'gzip, deflate, br'
        if 'Connection' not in headers:
            headers['Connection'] = 'keep-alive'

        # 5. 添加 Referer（使用 base_url + api_path 作为 Referer，绕过 WAF 检查）
        if 'Referer' not in headers:
            # 构造 Referer URL（通常是 API 文档的 URL）
            api_doc_path = self.config['target'].get('api_path', '/api-docs')
            referer_url = self.base_url.rstrip('/') + api_doc_path
            headers['Referer'] = referer_url

        # 6. 添加 API 定义的 header 参数
        for param in parameters.get('header', []):
            value = generate_test_value(param['type'], param['name'], self.config)
            headers[param['name']] = str(value)
        
        # 处理认证
        if self.config.get('auth', {}).get('enabled', False):
            auth_config = self.config['auth']
            auth_type = auth_config.get('type', 'bearer')
            
            if auth_type == 'bearer':
                token = auth_config.get('token', '')
                headers['Authorization'] = f'Bearer {token}'
            elif auth_type == 'api_key':
                header_name = auth_config.get('header_name', 'X-API-Key')
                headers[header_name] = auth_config.get('token', '')
        
        # 处理请求体
        body = None
        content_type = None
        
        if parameters.get('body'):
            body_param = parameters['body'][0]
            content_type = body_param.get('content_type', 'application/json')
            schema = body_param.get('schema', {})
            
            if 'application/json' in content_type:
                # 使用 set 跟踪已访问的引用，防止循环递归
                body = self._generate_body_from_schema(schema, depth=0, max_depth=5)
                headers['Content-Type'] = 'application/json'
            elif 'application/x-www-form-urlencoded' in content_type:
                body = {}
                for param in parameters.get('formData', []):
                    value = generate_test_value(param['type'], param['name'], self.config)
                    body[param['name']] = value
                headers['Content-Type'] = 'application/x-www-form-urlencoded'
            elif 'multipart/form-data' in content_type:
                # 处理文件上传
                body = {}
                files = {}

                for param in parameters.get('formData', []):
                    param_name = param['name']
                    param_type = param.get('type', 'string')

                    # 如果是文件类型，创建测试文件
                    if param_type == 'file':
                        filename, file_obj, file_content_type = create_test_file(param_name)
                        files[param_name] = (filename, file_obj, file_content_type)
                        logger.debug(f"为参数 {param_name} 创建测试文件: {filename} ({file_content_type})")
                    else:
                        # 普通字段
                        value = generate_test_value(param_type, param_name, self.config)
                        body[param_name] = value

                # 如果有文件，将普通字段也放入 files 参数（requests 会正确处理）
                if files:
                    for key, value in body.items():
                        files[key] = (None, str(value))
                    body = files

                # multipart/form-data 的 Content-Type 会由 requests 自动设置
                if 'Content-Type' in headers:
                    del headers['Content-Type']
        
        # 构造完整 URL
        if self.custom_prefix:
            full_path = self.custom_prefix.rstrip('/') + path
        else:
            full_path = path

        url = urljoin(self.base_url, full_path)
        
        return {
            'method': method,
            'url': url,
            'path': path,
            'headers': headers,
            'params': query_params,
            'body': body,
            'api': api,
            'fuzz_type': 'normal'
        }
    
    def _generate_body_from_schema(self, schema: Dict[str, Any], depth: int = 0, max_depth: int = 5) -> Any:
        """从 schema 生成请求体
        
        Args:
            schema: Schema 定义
            depth: 当前递归深度
            max_depth: 最大递归深度，防止无限递归
            
        Returns:
            生成的数据
        """
        if not schema:
            return {}

        # 防止递归过深
        if depth > max_depth:
            logger.debug(f"⚠️  达到最大递归深度 ({max_depth})，停止展开")
            return {}

        schema_type = schema.get('type', 'object')

        if schema_type == 'object':
            body = {}
            properties = schema.get('properties', {})
            required = schema.get('required', [])

            for prop_name, prop_schema in properties.items():
                prop_type = prop_schema.get('type', 'string')

                # 只生成必需字段或简单字段
                if prop_name in required or prop_type in ['string', 'integer', 'number', 'boolean']:
                    # 对于对象或数组类型的属性，递归生成
                    if prop_type in ['object', 'array']:
                        body[prop_name] = self._generate_body_from_schema(prop_schema, depth + 1, max_depth)
                    else:
                        body[prop_name] = generate_test_value(prop_type, prop_name, self.config)

            return body
        elif schema_type == 'array':
            items_schema = schema.get('items', {})
            # 生成一个包含单个元素的数组
            return [self._generate_body_from_schema(items_schema, depth + 1, max_depth)]
        else:
            return generate_test_value(schema_type, '', self.config)

    def _build_username_fuzz_requests(self, api):
        """构造用户名 Fuzz 请求

        Args:
            api: API 定义

        Returns:
            list: Fuzz 请求列表
        """
        fuzz_requests = []
        parameters = api['parameters']

        # 查找需要 Fuzz 的参数
        fuzz_targets = []

        # 检查查询参数
        for param in parameters.get('query', []):
            param_type = param.get('type', 'string')
            if self._should_fuzz_username(param['name'], param_type):
                fuzz_targets.append({
                    'name': param['name'],
                    'location': 'query',
                    'type': param_type
                })

        # 检查路径参数
        for param in parameters.get('path', []):
            param_type = param.get('type', 'string')
            if self._should_fuzz_username(param['name'], param_type):
                fuzz_targets.append({
                    'name': param['name'],
                    'location': 'path',
                    'type': param_type
                })

        # 检查请求体参数（JSON）
        for body_param in parameters.get('body', []):
            schema = body_param.get('schema', {})
            properties = schema.get('properties', {})
            for prop_name, prop_schema in properties.items():
                prop_type = prop_schema.get('type', 'string')
                if self._should_fuzz_username(prop_name, prop_type):
                    fuzz_targets.append({
                        'name': prop_name,
                        'location': 'body',
                        'type': prop_type
                    })

        # 如果没有找到需要 Fuzz 的参数，直接返回
        if not fuzz_targets:
            return fuzz_requests

        # 为每个目标参数生成 Fuzz 请求
        for target in fuzz_targets:
            param_name = target['name']
            location = target['location']

            # 为每个用户名生成一个请求
            for username in self.usernames:
                # 构造基础请求
                base_request = self._build_basic_request(api, include_query_params=True)

                # 修改目标参数的值
                if location == 'query':
                    if 'params' not in base_request:
                        base_request['params'] = {}
                    base_request['params'][param_name] = username

                elif location == 'path':
                    # 替换路径参数
                    path = base_request['path']
                    path = path.replace('{' + param_name + '}', str(username))
                    base_request['path'] = path
                    # 重新构造 URL
                    if self.custom_prefix:
                        full_path = self.custom_prefix.rstrip('/') + path
                    else:
                        full_path = path
                    base_request['url'] = urljoin(self.base_url, full_path)

                elif location == 'body':
                    if base_request.get('body') and isinstance(base_request['body'], dict):
                        base_request['body'][param_name] = username

                # 标记为用户名 Fuzz 请求
                base_request['fuzz_type'] = 'username_fuzz'
                base_request['is_original'] = False
                base_request['description'] = f"{api.get('summary', '')} [用户名Fuzz: {param_name}={username}]"
                base_request['param_info'] = f"用户名Fuzz: {param_name}={username}"
                base_request['fuzz_target'] = param_name
                base_request['fuzz_value'] = username

                fuzz_requests.append(base_request)

        return fuzz_requests

    def _build_password_fuzz_requests(self, api):
        """构造密码 Fuzz 请求

        Args:
            api: API 定义

        Returns:
            list: Fuzz 请求列表
        """
        fuzz_requests = []
        parameters = api['parameters']

        # 查找需要 Fuzz 的参数
        fuzz_targets = []

        # 检查查询参数
        for param in parameters.get('query', []):
            param_type = param.get('type', 'string')
            if self._should_fuzz_password(param['name'], param_type):
                fuzz_targets.append({
                    'name': param['name'],
                    'location': 'query',
                    'type': param_type
                })

        # 检查路径参数
        for param in parameters.get('path', []):
            param_type = param.get('type', 'string')
            if self._should_fuzz_password(param['name'], param_type):
                fuzz_targets.append({
                    'name': param['name'],
                    'location': 'path',
                    'type': param_type
                })

        # 检查请求体参数（JSON）
        for body_param in parameters.get('body', []):
            schema = body_param.get('schema', {})
            properties = schema.get('properties', {})
            for prop_name, prop_schema in properties.items():
                prop_type = prop_schema.get('type', 'string')
                if self._should_fuzz_password(prop_name, prop_type):
                    fuzz_targets.append({
                        'name': prop_name,
                        'location': 'body',
                        'type': prop_type
                    })

        # 如果没有找到需要 Fuzz 的参数，直接返回
        if not fuzz_targets:
            return fuzz_requests

        # 为每个目标参数生成 Fuzz 请求
        for target in fuzz_targets:
            param_name = target['name']
            location = target['location']

            # 为每个密码生成一个请求
            for password in self.passwords:
                # 构造基础请求
                base_request = self._build_basic_request(api, include_query_params=True)

                # 修改目标参数的值
                if location == 'query':
                    if 'params' not in base_request:
                        base_request['params'] = {}
                    base_request['params'][param_name] = password

                elif location == 'path':
                    # 替换路径参数
                    path = base_request['path']
                    path = path.replace('{' + param_name + '}', str(password))
                    base_request['path'] = path
                    # 重新构造 URL
                    if self.custom_prefix:
                        full_path = self.custom_prefix.rstrip('/') + path
                    else:
                        full_path = path
                    base_request['url'] = urljoin(self.base_url, full_path)

                elif location == 'body':
                    if base_request.get('body') and isinstance(base_request['body'], dict):
                        base_request['body'][param_name] = password

                # 标记为密码 Fuzz 请求
                base_request['fuzz_type'] = 'password_fuzz'
                base_request['is_original'] = False
                base_request['description'] = f"{api.get('summary', '')} [密码Fuzz: {param_name}={password}]"
                base_request['param_info'] = f"密码Fuzz: {param_name}={password}"
                base_request['fuzz_target'] = param_name
                base_request['fuzz_value'] = password

                fuzz_requests.append(base_request)

        return fuzz_requests

    def _build_number_fuzz_requests(self, api):
        """构造数字型 Fuzz 请求

        Args:
            api: API 定义

        Returns:
            list: Fuzz 请求列表
        """
        fuzz_requests = []
        parameters = api['parameters']

        # 查找数字型参数
        fuzz_targets = []

        # 检查查询参数
        for param in parameters.get('query', []):
            param_type = param.get('type', 'string')
            # 检查是否为数字类型
            if param_type in ['integer', 'number', 'int', 'long', 'float', 'double']:
                fuzz_targets.append({
                    'name': param['name'],
                    'location': 'query',
                    'type': param_type
                })

        # 检查路径参数
        for param in parameters.get('path', []):
            param_type = param.get('type', 'string')
            if param_type in ['integer', 'number', 'int', 'long', 'float', 'double']:
                fuzz_targets.append({
                    'name': param['name'],
                    'location': 'path',
                    'type': param_type
                })

        # 检查请求体参数（JSON）
        for body_param in parameters.get('body', []):
            schema = body_param.get('schema', {})
            properties = schema.get('properties', {})
            for prop_name, prop_schema in properties.items():
                prop_type = prop_schema.get('type', 'string')
                if prop_type in ['integer', 'number', 'int', 'long', 'float', 'double']:
                    fuzz_targets.append({
                        'name': prop_name,
                        'location': 'body',
                        'type': prop_type
                    })

        # 如果没有找到数字型参数，直接返回
        if not fuzz_targets:
            return fuzz_requests

        # 为每个目标参数生成 Fuzz 请求
        for target in fuzz_targets:
            param_name = target['name']
            location = target['location']

            # 为每个数字值生成一个请求
            for number in self.number_values:
                # 构造基础请求
                base_request = self._build_basic_request(api, include_query_params=True)

                # 修改目标参数的值
                if location == 'query':
                    if 'params' not in base_request:
                        base_request['params'] = {}
                    base_request['params'][param_name] = number

                elif location == 'path':
                    # 替换路径参数
                    path = base_request['path']
                    path = path.replace('{' + param_name + '}', str(number))
                    base_request['path'] = path
                    # 重新构造 URL
                    if self.custom_prefix:
                        full_path = self.custom_prefix.rstrip('/') + path
                    else:
                        full_path = path
                    base_request['url'] = urljoin(self.base_url, full_path)

                elif location == 'body':
                    if base_request.get('body') and isinstance(base_request['body'], dict):
                        base_request['body'][param_name] = number

                # 标记为数字型 Fuzz 请求
                base_request['fuzz_type'] = 'number_fuzz'
                base_request['is_original'] = False
                base_request['description'] = f"{api.get('summary', '')} [数字Fuzz: {param_name}={number}]"
                base_request['param_info'] = f"数字Fuzz: {param_name}={number}"
                base_request['fuzz_target'] = param_name
                base_request['fuzz_value'] = number

                fuzz_requests.append(base_request)

        return fuzz_requests

    def build_fuzz_request(self, base_request, fuzz_data, fuzz_type):
        """构造 Fuzz 请求"""
        request = base_request.copy()
        request['fuzz_type'] = fuzz_type
        request['fuzz_data'] = fuzz_data
        
        # 根据 fuzz 类型修改请求
        if fuzz_type == 'parameter_fuzz':
            # 添加额外参数
            if 'params' not in request:
                request['params'] = {}
            request['params'].update(fuzz_data)
        
        elif fuzz_type == 'attack_fuzz':
            # 注入攻击 payload
            target_param = fuzz_data.get('target_param')
            payload = fuzz_data.get('payload')
            location = fuzz_data.get('location')  # query, body, path
            
            if location == 'query' and 'params' in request:
                if target_param in request['params']:
                    request['params'][target_param] = payload
            elif location == 'body' and request.get('body'):
                if isinstance(request['body'], dict) and target_param in request['body']:
                    request['body'][target_param] = payload
        
        return request

    def _select_payloads_for_param(self, param_type):
        """根据参数类型智能选择 payload

        Args:
            param_type: 参数类型（string, integer, number等）

        Returns:
            list: 选择的 payload 列表
        """
        mode = self.config.get('fuzz_sql', {}).get('mode', 'smart')

        # basic 和 full 模式：直接返回所有 payload
        if mode in ['basic', 'full']:
            return self.sql_payloads

        # smart 模式：根据参数类型智能选择
        if mode == 'smart':
            # 对于数字型参数，优先选择数字型 payload
            if param_type in ['integer', 'number', 'int', 'long', 'float', 'double']:
                # 数字型参数更容易受到数字型注入攻击
                # 优先使用不带引号的 payload
                numeric_payloads = []
                string_payloads = []

                for payload in self.sql_payloads:
                    # 判断 payload 是否包含引号
                    if "'" in payload or '"' in payload:
                        string_payloads.append(payload)
                    else:
                        numeric_payloads.append(payload)

                # 数字型参数：70% 数字型 payload + 30% 字符串型 payload
                max_payloads = len(self.sql_payloads)
                numeric_count = int(max_payloads * 0.7)
                string_count = max_payloads - numeric_count

                selected = numeric_payloads[:numeric_count] + string_payloads[:string_count]
                return selected[:max_payloads]

            # 对于字符串型参数，使用所有 payload
            else:
                return self.sql_payloads

        # 默认返回所有 payload
        return self.sql_payloads

    def _build_sql_fuzz_requests(self, api):
        """构造SQL注入 Fuzz 请求

        Args:
            api: API 定义

        Returns:
            list: Fuzz 请求列表
        """
        fuzz_requests = []
        parameters = api['parameters']

        # 查找需要进行SQL注入测试的参数
        fuzz_targets = []

        # 检查查询参数
        for param in parameters.get('query', []):
            param_name = param['name']
            param_type = param.get('type', 'string')
            if self._should_fuzz_sql(param_name, param_type):
                fuzz_targets.append({
                    'name': param_name,
                    'location': 'query',
                    'type': param_type
                })

        # 检查路径参数
        for param in parameters.get('path', []):
            param_name = param['name']
            param_type = param.get('type', 'string')
            if self._should_fuzz_sql(param_name, param_type):
                fuzz_targets.append({
                    'name': param_name,
                    'location': 'path',
                    'type': param_type
                })

        # 检查表单参数
        for param in parameters.get('formData', []):
            param_name = param['name']
            param_type = param.get('type', 'string')
            if self._should_fuzz_sql(param_name, param_type):
                fuzz_targets.append({
                    'name': param_name,
                    'location': 'formData',
                    'type': param_type
                })

        # 检查请求体参数（JSON）
        for body_param in parameters.get('body', []):
            schema = body_param.get('schema', {})
            properties = schema.get('properties', {})
            for prop_name, prop_schema in properties.items():
                prop_type = prop_schema.get('type', 'string')
                if self._should_fuzz_sql(prop_name, prop_type):
                    fuzz_targets.append({
                        'name': prop_name,
                        'location': 'body',
                        'type': prop_type
                    })

        # 如果没有找到目标参数，直接返回
        if not fuzz_targets:
            return fuzz_requests

        logger.info(f"🎯 API {api.get('path', 'unknown')}: 找到 {len(fuzz_targets)} 个SQL注入测试目标参数")
        for target in fuzz_targets:
            logger.debug(f"   - {target['name']} ({target['location']}, {target['type']})")

        # 为每个目标参数生成 Fuzz 请求
        for target in fuzz_targets:
            param_name = target['name']
            location = target['location']
            param_type = target['type']

            # 根据参数类型和模式选择 payload
            payloads_to_use = self._select_payloads_for_param(param_type)

            logger.debug(f"   为参数 '{param_name}' ({param_type}) 生成 {len(payloads_to_use)} 个payload请求")

            # 为每个payload生成一个请求
            for payload in payloads_to_use:
                # 构造基础请求
                base_request = self._build_basic_request(api, include_query_params=True)

                # 修改目标参数的值
                if location == 'query':
                    if 'params' not in base_request:
                        base_request['params'] = {}
                    base_request['params'][param_name] = payload

                elif location == 'path':
                    # 替换路径参数
                    path = base_request['path']
                    # URL编码payload
                    from urllib.parse import quote
                    encoded_payload = quote(payload, safe='')
                    path = path.replace('{' + param_name + '}', encoded_payload)
                    base_request['path'] = path
                    # 重新构造 URL
                    if self.custom_prefix:
                        full_path = self.custom_prefix.rstrip('/') + path
                    else:
                        full_path = path
                    base_request['url'] = urljoin(self.base_url, full_path)

                elif location == 'formData':
                    if 'data' not in base_request:
                        base_request['data'] = {}
                    base_request['data'][param_name] = payload

                elif location == 'body':
                    if base_request.get('body') and isinstance(base_request['body'], dict):
                        base_request['body'][param_name] = payload

                # 标记为SQL注入 Fuzz 请求
                base_request['fuzz_type'] = 'sql_fuzz'
                base_request['is_original'] = False
                base_request['description'] = f"{api.get('summary', '')} [SQL注入Fuzz: {param_name}]"
                base_request['param_info'] = f"SQL注入Fuzz: {param_name}={payload[:50]}"  # 限制显示长度
                base_request['fuzz_target'] = param_name
                base_request['fuzz_value'] = payload

                fuzz_requests.append(base_request)

        logger.info(f"✅ 生成了 {len(fuzz_requests)} 个SQL注入 Fuzz 请求")
        return fuzz_requests

