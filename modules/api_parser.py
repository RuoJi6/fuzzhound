#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API 解析模块
解析 Swagger/OpenAPI JSON 文档
"""

import requests
import json
import urllib3
import re
import logging
import yaml
from urllib.parse import urljoin
from rich.console import Console

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

console = Console()
logger = logging.getLogger('fuzzhound.api_parser')


class APIParser:
    """API 解析器"""
    
    def __init__(self, config):
        self.config = config
        self.base_url = config['target']['base_url']
        self.api_path = config['target']['api_path']
        self.custom_prefix = config['target'].get('custom_prefix', '')
        self.timeout = config['target'].get('timeout', 10)
        self.verify_ssl = config['target'].get('verify_ssl', False)

        # 黑名单配置
        self.blacklist_enabled = config.get('blacklist', {}).get('enabled', False)
        self.blacklist_methods = [m.upper() for m in config.get('blacklist', {}).get('methods', [])]
        self.blacklist_paths = config.get('blacklist', {}).get('paths', [])
        self.blacklist_patterns = config.get('blacklist', {}).get('path_patterns', [])

        # 保存完整的 API 文档，用于解析 $ref 引用
        self.api_doc = {}

        # 智能解析 URL
        self._parse_url()

    def _is_blacklisted(self, method, path):
        """检查 API 是否在黑名单中"""
        if not self.blacklist_enabled:
            return False

        # 检查方法黑名单
        if method.upper() in self.blacklist_methods:
            logger.debug(f"🚫 API 被方法黑名单过滤: {method} {path}")
            return True

        # 检查路径黑名单（精确匹配）
        # 过滤掉空字符串，避免匹配所有路径
        valid_paths = [p for p in self.blacklist_paths if p and p.strip()]
        if path in valid_paths:
            logger.debug(f"🚫 API 被路径黑名单过滤: {method} {path}")
            return True

        # 检查路径正则表达式
        for pattern in self.blacklist_patterns:
            if not pattern or not pattern.strip():
                continue
            try:
                if re.search(pattern, path):
                    logger.debug(f"🚫 API 被正则黑名单过滤: {method} {path} (匹配: {pattern})")
                    return True
            except re.error:
                console.print(f"[yellow]⚠ 无效的正则表达式: {pattern}[/yellow]")
                continue

        return False

    def _parse_url(self):
        """智能解析 URL"""
        from urllib.parse import urlparse

        # 如果 base_url 包含了 API 文档路径，需要分离
        parsed = urlparse(self.base_url)
        path = parsed.path

        # 如果路径不为空，说明用户输入了完整的 URL
        if path and path != '/':
            # 检查是否包含常见的 API 文档路径关键字或文件扩展名
            api_doc_patterns = [
                'api-docs', 'swagger', 'openapi', 'docs/v', 'api/v', 'api_documentation'
            ]

            # 检查是否是 JSON/YAML 文件
            api_doc_extensions = ['.json', '.yaml', '.yml']

            # 检查路径中是否包含 API 文档关键字或文件扩展名
            path_lower = path.lower()
            is_api_doc = False

            # 检查关键字
            for pattern in api_doc_patterns:
                if pattern in path_lower:
                    is_api_doc = True
                    break

            # 检查文件扩展名
            if not is_api_doc:
                for ext in api_doc_extensions:
                    if path_lower.endswith(ext):
                        is_api_doc = True
                        break

            if is_api_doc:
                # 找到 API 文档路径，直接使用完整路径
                # 例如: https://www.scidb.cn/open-api/v2/api-docs
                # -> base_url = https://www.scidb.cn
                # -> api_path = /open-api/v2/api-docs

                self.api_path = path
                self.base_url = f"{parsed.scheme}://{parsed.netloc}"

                # 同时更新配置，确保其他模块（如 RequestBuilder）使用正确的 base_url
                self.config['target']['base_url'] = self.base_url
                self.config['target']['api_path'] = self.api_path

                console.print(f"[dim]🔍 自动检测到 API 文档路径: {path}[/dim]")
                return

            # 如果没有找到 API 文档关键字，但有路径，可能是自定义前缀
            # 保持原样，让用户通过 -p 参数指定 API 文档路径

    def parse(self):
        """解析 API 文档"""
        # 构造 API 文档 URL
        if self.custom_prefix:
            # 如果有自定义前缀，拼接 prefix + api_path
            api_doc_url = urljoin(self.base_url, self.custom_prefix.rstrip('/') + self.api_path)
        else:
            api_doc_url = urljoin(self.base_url, self.api_path)

        console.print(f"[cyan]📡 正在获取 API 文档: {api_doc_url}[/cyan]")

        # 尝试解析当前URL
        apis = self._try_parse_url(api_doc_url)

        # 如果解析成功，返回结果
        if apis:
            return apis

        # 如果解析失败，尝试其他常见路径
        console.print(f"[yellow]⚠ 当前路径解析失败，尝试其他常见的 API 文档路径...[/yellow]")

        # 常见的 API 文档路径（按优先级排序）
        common_paths = [
            '/v2/api-docs',           # Swagger 2.0 (SpringFox)
            '/v3/api-docs',           # OpenAPI 3.0 (Springdoc)
            '/api-docs',              # 通用
            '/swagger/v2/api-docs',   # 带 swagger 前缀
            '/swagger/v3/api-docs',
            '/doc.html',              # Knife4j
            '/swagger-ui.html',       # Swagger UI
        ]

        # 如果有自定义前缀，也尝试带前缀的路径
        if self.custom_prefix:
            prefix = self.custom_prefix.rstrip('/')
            prefixed_paths = [prefix + path for path in common_paths]
            common_paths = prefixed_paths + common_paths

        # 移除已经尝试过的路径
        current_path = self.api_path
        common_paths = [p for p in common_paths if p != current_path]

        # 逐个尝试
        for path in common_paths:
            try_url = urljoin(self.base_url, path)
            console.print(f"[dim]🔍 尝试: {try_url}[/dim]")

            apis = self._try_parse_url(try_url)
            if apis:
                console.print(f"[green]✓ 成功找到 API 文档: {try_url}[/green]")
                # 更新实例变量和配置中的路径，以便后续使用
                self.api_path = path
                self.config['target']['api_path'] = path
                return apis

        # 所有路径都失败
        console.print(f"[red]✗ 尝试了所有常见路径，均未找到有效的 API 文档[/red]")
        return []

    def _try_parse_url(self, api_doc_url):
        """尝试解析指定的 URL

        Args:
            api_doc_url: API 文档 URL

        Returns:
            解析成功返回 API 列表，失败返回空列表
        """

        # 构造更真实的请求头
        # Referer 设置为完整的 API 文档 URL，这样可以绕过一些 WAF 的 Referer 检查
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': api_doc_url,  # 使用完整的 API 文档 URL 作为 Referer
        }

        # 添加认证信息
        auth_config = self.config.get('auth', {})
        if auth_config.get('enabled', False):
            auth_type = auth_config.get('type', 'bearer')

            if auth_type == 'bearer' and auth_config.get('token'):
                headers['Authorization'] = f"Bearer {auth_config['token']}"
            elif auth_type == 'api_key' and auth_config.get('token'):
                header_name = auth_config.get('header_name', 'Authorization')
                headers[header_name] = auth_config['token']
            elif auth_type == 'cookie' and auth_config.get('cookie'):
                headers['Cookie'] = auth_config['cookie']

        # 如果配置中有自定义请求头，合并进来
        custom_headers = self.config.get('request', {}).get('headers', {})
        if custom_headers:
            headers.update(custom_headers)

        # 配置代理
        proxies = None
        proxy_config = self.config.get('proxy', {})
        if proxy_config.get('enabled', False):
            proxies = {}
            if proxy_config.get('http'):
                proxies['http'] = proxy_config['http']
            if proxy_config.get('https'):
                proxies['https'] = proxy_config['https']

            if proxies:
                # 只在第一次尝试时显示代理信息
                if api_doc_url == urljoin(self.base_url, self.api_path):
                    console.print(f"[dim]🔌 使用代理: {proxies.get('http') or proxies.get('https')}[/dim]")

        try:
            # 获取 API 文档
            response = requests.get(
                api_doc_url,
                timeout=self.timeout,
                verify=self.verify_ssl,
                headers=headers,
                proxies=proxies,
                allow_redirects=True
            )
            response.raise_for_status()

            # 根据URL后缀或Content-Type判断文档格式
            content_type = response.headers.get('Content-Type', '').lower()
            is_yaml = (
                api_doc_url.endswith('.yaml') or
                api_doc_url.endswith('.yml') or
                'yaml' in content_type or
                'yml' in content_type
            )

            # 解析文档（支持JSON和YAML）
            try:
                if is_yaml:
                    # 解析YAML格式
                    api_doc = yaml.safe_load(response.text)
                    console.print(f"[dim]📄 检测到 YAML 格式文档[/dim]")
                else:
                    # 解析JSON格式
                    api_doc = response.json()
                    console.print(f"[dim]📄 检测到 JSON 格式文档[/dim]")
            except (json.JSONDecodeError, yaml.YAMLError) as e:
                # 如果JSON解析失败，尝试YAML
                if not is_yaml:
                    try:
                        api_doc = yaml.safe_load(response.text)
                        console.print(f"[dim]📄 JSON解析失败，尝试YAML格式成功[/dim]")
                    except yaml.YAMLError:
                        logger.debug(f"文档解析失败: {e}")
                        return []
                else:
                    logger.debug(f"文档解析失败: {e}")
                    return []

            # 判断文档类型并解析
            apis = []
            if 'swagger' in api_doc and api_doc['swagger'] == '2.0':
                console.print(f"[dim]📋 检测到 Swagger 2.0 格式[/dim]")
                # 保存完整文档以便解析 $ref
                self.api_doc = api_doc
                apis = self._parse_swagger_v2(api_doc)
            elif 'openapi' in api_doc:
                version = api_doc['openapi']
                console.print(f"[dim]📋 检测到 OpenAPI {version} 格式[/dim]")
                # 保存完整文档以便解析 $ref
                self.api_doc = api_doc
                apis = self._parse_openapi_v3(api_doc)
            else:
                # 不支持的格式，静默返回空列表
                return []

            # 如果解析成功且有API，返回结果
            if apis:
                return apis
            else:
                return []

        except requests.exceptions.HTTPError as e:
            # 对于自动尝试的路径，不显示详细错误信息
            # 只有在第一次尝试时才显示详细提示
            if api_doc_url == urljoin(self.base_url, self.api_path):
                if e.response.status_code == 403:
                    console.print(f"[red]✗ 获取 API 文档失败: {e}[/red]")
                    console.print(f"[yellow]💡 提示: 目标网站返回 403 Forbidden，可能的原因：[/yellow]")
                    console.print(f"[yellow]   1. 网站有 WAF/防火墙保护，拦截了自动化请求[/yellow]")
                    console.print(f"[yellow]   2. 需要认证才能访问 API 文档[/yellow]")
                    console.print(f"[yellow]   3. API 文档路径不正确[/yellow]")
                    console.print(f"[yellow]   4. 需要特定的 Cookie 或 Token[/yellow]")
                elif e.response.status_code == 401:
                    console.print(f"[red]✗ 获取 API 文档失败: {e}[/red]")
                    console.print(f"[yellow]💡 提示: 需要认证才能访问，请在配置文件中添加认证信息[/yellow]")
                elif e.response.status_code == 404:
                    console.print(f"[red]✗ 获取 API 文档失败: {e}[/red]")
                    console.print(f"[yellow]💡 提示: API 文档路径不存在[/yellow]")
                else:
                    console.print(f"[red]✗ 获取 API 文档失败: {e}[/red]")
            return []
        except requests.exceptions.RequestException:
            # 网络错误，静默返回
            return []
        except json.JSONDecodeError:
            # JSON 解析错误，可能不是 JSON 格式的文档
            return []
        except Exception:
            # 其他错误，静默返回
            return []
    
    def _parse_swagger_v2(self, api_doc):
        """解析 Swagger 2.0 文档"""
        apis = []
        paths = api_doc.get('paths', {})
        base_path = api_doc.get('basePath', '')
        host = api_doc.get('host', '')

        # 处理 host 字段：如果包含路径，需要提取出来
        host_path = ''
        if host:
            # host 可能是 "www.scidb.cn/api/sdb-openapi-service" 这种格式
            # 需要分离域名和路径
            if '/' in host:
                parts = host.split('/', 1)
                # host 只保留域名部分（这里不使用，因为我们已经有 base_url）
                # 路径部分需要加到 base_path 前面
                host_path = '/' + parts[1]
                console.print(f"[dim]📍 检测到 host 包含路径: {host_path}[/dim]")

        # 处理 basePath：如果是完整URL，只取路径部分
        if base_path:
            from urllib.parse import urlparse
            # 如果 basePath 包含协议（http/https），说明是完整URL
            if base_path.startswith('http://') or base_path.startswith('https://'):
                parsed = urlparse(base_path)
                # 只使用路径部分
                base_path = parsed.path
                console.print(f"[dim]📍 检测到完整URL的basePath，提取路径: {base_path}[/dim]")
            else:
                console.print(f"[dim]📍 basePath: {base_path}[/dim]")

        # 合并 host_path 和 base_path
        # 最终路径 = host中的路径 + basePath
        if host_path:
            if base_path == '/' or not base_path:
                final_base_path = host_path
            else:
                final_base_path = host_path.rstrip('/') + '/' + base_path.lstrip('/')
            console.print(f"[dim]📍 合并后的 basePath: {final_base_path}[/dim]")
        else:
            final_base_path = base_path

        for path, methods in paths.items():
            for method, details in methods.items():
                if method.upper() not in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']:
                    continue

                # 获取标题：优先使用 summary，其次 operationId，最后为空
                summary = details.get('summary', '') or details.get('operationId', '')

                # 正确拼接 final_base_path 和 path，避免双斜杠
                # 如果 final_base_path 是 '/' 或空，则只使用 path
                if final_base_path == '/' or not final_base_path:
                    full_path = path
                else:
                    # 确保 final_base_path 不以 / 结尾，path 以 / 开头
                    full_path = final_base_path.rstrip('/') + ('/' + path.lstrip('/') if path else '')

                # 检查黑名单 - 标记但不跳过，让后续处理
                is_blacklisted = self._is_blacklisted(method.upper(), full_path)

                # 解析参数
                parameters = self._parse_parameters_v2(details.get('parameters', []))

                # 从路径中提取参数名称，补充缺失的路径参数定义
                parameters = self._ensure_path_parameters(full_path, parameters)

                api = {
                    'path': full_path,
                    'method': method.upper(),
                    'summary': summary,
                    'description': details.get('description', ''),
                    'operationId': details.get('operationId', ''),
                    'parameters': parameters,
                    'consumes': details.get('consumes', api_doc.get('consumes', [])),
                    'produces': details.get('produces', api_doc.get('produces', [])),
                    'tags': details.get('tags', []),
                    'is_blacklisted': is_blacklisted  # 标记是否在黑名单中
                }
                apis.append(api)

        return apis
    
    def _parse_openapi_v3(self, api_doc):
        """解析 OpenAPI 3.0 文档"""
        apis = []
        paths = api_doc.get('paths', {})
        servers = api_doc.get('servers', [])
        base_path = servers[0].get('url', '') if servers else ''

        # 处理 servers URL：如果是完整URL，只取路径部分
        if base_path:
            from urllib.parse import urlparse
            # 如果 URL 包含协议（http/https），说明是完整URL
            if base_path.startswith('http://') or base_path.startswith('https://'):
                parsed = urlparse(base_path)
                # 只使用路径部分
                base_path = parsed.path
                console.print(f"[dim]📍 检测到完整URL的server，提取路径: {base_path}[/dim]")
            else:
                console.print(f"[dim]📍 server URL: {base_path}[/dim]")

        for path, methods in paths.items():
            for method, details in methods.items():
                if method.upper() not in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']:
                    continue

                # 获取标题：优先使用 summary，其次 operationId，最后为空
                summary = details.get('summary', '') or details.get('operationId', '')

                # 正确拼接 base_path 和 path，避免双斜杠
                if base_path == '/' or not base_path:
                    full_path = path
                else:
                    full_path = base_path.rstrip('/') + ('/' + path.lstrip('/') if path else '')

                # 检查黑名单 - 标记但不跳过，让后续处理
                is_blacklisted = self._is_blacklisted(method.upper(), full_path)

                # 解析参数
                parameters = self._parse_parameters_v3(details)

                # 从路径中提取参数名称，补充缺失的路径参数定义
                parameters = self._ensure_path_parameters(full_path, parameters)

                api = {
                    'path': full_path,
                    'method': method.upper(),
                    'summary': summary,
                    'description': details.get('description', ''),
                    'operationId': details.get('operationId', ''),
                    'parameters': parameters,
                    'consumes': self._get_content_types_v3(details, 'requestBody'),
                    'produces': self._get_content_types_v3(details, 'responses'),
                    'tags': details.get('tags', []),
                    'is_blacklisted': is_blacklisted  # 标记是否在黑名单中
                }
                apis.append(api)

        return apis
    
    def _resolve_ref(self, ref_path):
        """解析 $ref 引用

        Args:
            ref_path: 引用路径，如 "#/components/parameters/entryGroupBy"

        Returns:
            解析后的对象，如果解析失败返回 None
        """
        if not ref_path or not ref_path.startswith('#/'):
            logger.debug(f"⚠️  无效的引用路径: {ref_path}")
            return None

        # 检查 api_doc 是否已初始化
        if not self.api_doc:
            logger.warning(f"⚠️  API文档未初始化，无法解析引用: {ref_path}")
            return None

        # 移除开头的 #/
        path_parts = ref_path[2:].split('/')
        logger.debug(f"🔍 解析引用: {ref_path}, 路径部分: {path_parts}")

        # 从文档根开始遍历
        current = self.api_doc
        for i, part in enumerate(path_parts):
            if isinstance(current, dict) and part in current:
                current = current[part]
                logger.debug(f"   ✓ 找到部分 [{i}]: {part}")
            else:
                if isinstance(current, dict):
                    available_keys = list(current.keys())[:5]  # 只显示前5个键
                    logger.warning(f"⚠️  无法解析引用 {ref_path} 在部分 '{part}'")
                    logger.warning(f"   当前层级可用的键: {available_keys}...")
                else:
                    logger.warning(f"⚠️  无法解析引用 {ref_path}，当前对象不是字典: {type(current)}")
                return None

        logger.debug(f"   ✓ 成功解析引用: {ref_path}")
        return current

    def _ensure_path_parameters(self, path, parameters):
        """确保路径中的所有参数都有定义

        从路径中提取 {paramName} 占位符，如果在 parameters['path'] 中没有定义，
        则创建一个默认定义

        Args:
            path: API 路径，如 /api/user/{userId}/post/{postId}
            parameters: 已解析的参数字典

        Returns:
            dict: 补充后的参数字典
        """
        import re

        # 从路径中提取所有参数名称
        path_param_names = re.findall(r'\{([^}]+)\}', path)

        # 获取已定义的路径参数名称（过滤掉空参数名）
        defined_param_names = {param['name'] for param in parameters.get('path', []) if param.get('name') and param.get('name').strip()}

        # 找出缺失的参数
        missing_params = set(path_param_names) - defined_param_names

        if missing_params:
            logger.warning(f"⚠️  路径 {path} 中发现未定义的参数: {missing_params}")

            # 为缺失的参数创建默认定义
            for param_name in missing_params:
                # 跳过空参数名
                if not param_name or not param_name.strip():
                    logger.warning(f"⚠️  跳过空参数名，路径: {path}")
                    continue

                param_info = {
                    'name': param_name,
                    'type': 'string',  # 默认为字符串类型
                    'required': True,  # 路径参数通常是必需的
                    'description': f'Path parameter {param_name}',
                    'default': None,
                    'schema': {}
                }
                parameters['path'].append(param_info)
                logger.debug(f"   ✓ 为参数 '{param_name}' 创建默认定义")

        return parameters

    def _parse_parameters_v2(self, parameters):
        """解析 Swagger 2.0 参数"""
        parsed_params = {
            'path': [],
            'query': [],
            'body': [],
            'header': [],
            'formData': []
        }

        for param in parameters:
            # 如果是 $ref 引用，先解析引用
            if '$ref' in param:
                ref_param = self._resolve_ref(param['$ref'])
                if ref_param:
                    param = ref_param
                else:
                    logger.warning(f"⚠️  无法解析参数引用: {param['$ref']}")
                    continue

            param_name = param.get('name', '')

            # 如果参数名为空，跳过（避免生成 {} 占位符）
            if not param_name or not param_name.strip():
                logger.warning(f"⚠️  跳过空参数名的参数: {param}")
                continue

            param_info = {
                'name': param_name,
                'type': param.get('type', 'string'),
                'required': param.get('required', False),
                'description': param.get('description', ''),
                'default': param.get('default'),
                'schema': param.get('schema', {})
            }

            param_in = param.get('in', 'query')
            if param_in in parsed_params:
                parsed_params[param_in].append(param_info)

        return parsed_params
    
    def _parse_parameters_v3(self, details):
        """解析 OpenAPI 3.0 参数"""
        parsed_params = {
            'path': [],
            'query': [],
            'body': [],
            'header': [],
            'formData': []
        }

        # 解析 parameters
        for param in details.get('parameters', []):
            # 如果是 $ref 引用，先解析引用
            if '$ref' in param:
                ref_param = self._resolve_ref(param['$ref'])
                if ref_param:
                    param = ref_param
                else:
                    logger.warning(f"⚠️  无法解析参数引用: {param['$ref']}")
                    continue

            param_name = param.get('name', '')

            # 如果参数名为空，跳过（避免生成 {} 占位符）
            if not param_name or not param_name.strip():
                logger.warning(f"⚠️  跳过空参数名的参数: {param}")
                continue

            # 获取 schema 并解析 $ref
            schema = param.get('schema', {})
            resolved_schema = self._resolve_schema(schema)

            param_info = {
                'name': param_name,
                'type': self._get_type_from_schema(schema),
                'required': param.get('required', False),
                'description': param.get('description', ''),
                'schema': resolved_schema  # 保存解析后的 schema
            }

            param_in = param.get('in', 'query')
            if param_in in parsed_params:
                parsed_params[param_in].append(param_info)
        
        # 解析 requestBody
        request_body = details.get('requestBody', {})
        if request_body:
            content = request_body.get('content', {})
            for content_type, content_details in content.items():
                schema = content_details.get('schema', {})
                parsed_params['body'].append({
                    'name': 'body',
                    'type': 'object',
                    'required': request_body.get('required', False),
                    'content_type': content_type,
                    'schema': schema
                })

        # 调试：打印解析后的参数
        logger.debug(f"   解析后的参数: path={len(parsed_params.get('path', []))}, query={len(parsed_params.get('query', []))}")
        if parsed_params.get('path'):
            logger.debug(f"   路径参数: {[p['name'] for p in parsed_params['path']]}")

        return parsed_params

    def _resolve_schema(self, schema):
        """解析 schema，如果包含 $ref 则解析引用

        Args:
            schema: schema 定义

        Returns:
            dict: 解析后的 schema
        """
        if '$ref' in schema:
            ref_schema = self._resolve_ref(schema['$ref'])
            if ref_schema:
                return ref_schema
        return schema

    def _get_type_from_schema(self, schema):
        """从 schema 中获取类型"""
        if 'type' in schema:
            return schema['type']
        elif '$ref' in schema:
            # 解析 $ref 引用，获取实际的类型
            ref_schema = self._resolve_ref(schema['$ref'])
            if ref_schema and 'type' in ref_schema:
                return ref_schema['type']
            # 如果无法解析或没有 type 字段，默认返回 object
            return 'object'
        return 'string'

    def _get_content_types_v3(self, details, key):
        """获取 OpenAPI 3.0 的 content types"""
        content_types = []

        if key == 'requestBody':
            request_body = details.get('requestBody', {})
            # 跳过 $ref 引用
            if isinstance(request_body, dict) and '$ref' not in request_body:
                content = request_body.get('content', {})
                content_types = list(content.keys())
        elif key == 'responses':
            responses = details.get('responses', {})
            # 如果 responses 本身是 $ref，跳过
            if isinstance(responses, dict) and '$ref' in responses:
                pass
            elif isinstance(responses, dict):
                for response in responses.values():
                    # 跳过 $ref 引用和非字典类型
                    if isinstance(response, dict) and '$ref' not in response:
                        content = response.get('content', {})
                        content_types.extend(content.keys())

        return list(set(content_types)) if content_types else ['application/json']

