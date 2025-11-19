#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具函数模块
"""

import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler
from rich.console import Console

console = Console()


def setup_logger(config=None, verbose=False, debug=False):
    """设置日志

    Args:
        config: 配置字典
        verbose: 是否显示详细信息（命令行参数）
        debug: 是否启用调试模式（命令行参数）
    """
    # 获取日志配置
    if config:
        log_config = config.get('logging', {})
        debug_config = config.get('debug', {})
    else:
        log_config = {}
        debug_config = {}

    # 确定日志级别
    if debug or debug_config.get('enabled', False):
        level = logging.DEBUG
    elif verbose or debug_config.get('verbose', False):
        level = logging.INFO
    else:
        level_str = log_config.get('level', 'INFO')
        level = getattr(logging, level_str.upper(), logging.INFO)

    # 创建日志目录
    log_dir = log_config.get('log_dir', 'logs')
    log_file = log_config.get('log_file', 'fuzzhound.log')
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    log_path = os.path.join(log_dir, log_file)

    # 获取日志轮转配置
    max_bytes = log_config.get('max_bytes', 10485760)  # 默认 10MB
    backup_count = log_config.get('backup_count', 5)  # 默认保留 5 个文件

    # 创建日志处理器
    handlers = []

    # 文件处理器（带轮转）
    if log_config.get('enabled', True):
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        handlers.append(file_handler)

    # 调试模式下添加控制台处理器
    if debug or debug_config.get('enabled', False):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(
            logging.Formatter('[%(levelname)s] %(name)s: %(message)s')
        )
        handlers.append(console_handler)

    # 配置根日志记录器
    logging.basicConfig(
        level=level,
        handlers=handlers
    )

    # 禁用第三方库的 DEBUG 日志
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)

    logger = logging.getLogger('fuzzhound')

    # 记录日志配置信息
    if log_config.get('enabled', True):
        logger.info(f"日志文件: {log_path}")
        logger.info(f"日志级别: {logging.getLevelName(level)}")
        if debug or debug_config.get('enabled', False):
            logger.debug("调试模式已启用")

    return logger


def print_banner():
    """打印 Banner"""
    banner = """
[bold cyan]
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   🐕 FuzzHound - API 安全测试工具    by ruoji             ║
║                                                           ║
║   支持 Swagger/OpenAPI 自动化测试和智能 Fuzz              ║
║                                                           ║
║   GitHub: https://github.com/RuoJi6/fuzzhound             ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
[/bold cyan]
    """
    console.print(banner)


def load_dict_file(file_path):
    """加载字典文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        return lines
    except FileNotFoundError:
        console.print(f"[yellow]⚠ 字典文件不存在: {file_path}[/yellow]")
        return []
    except Exception as e:
        console.print(f"[red]✗ 加载字典文件失败: {e}[/red]")
        return []


def generate_test_value(param_type, param_name='', config=None, schema=None):
    """根据参数类型生成测试值

    Args:
        param_type: 参数类型
        param_name: 参数名称
        config: 配置字典（可选）
        schema: 参数的 schema 定义（可选，用于获取枚举值等）

    Returns:
        生成的测试值
    """
    # 如果 schema 中有枚举值，优先使用第一个枚举值
    if schema and 'enum' in schema and schema['enum']:
        return schema['enum'][0]

    # 获取默认值配置
    default_values = {}
    if config:
        default_values = config.get('default_values', {})

    # 默认类型映射（从配置文件读取，如果配置中没有指定，使用硬编码的默认值）
    type_mapping = {
        'string': default_values.get('string', 'test'),
        'integer': default_values.get('integer', 1),
        'int': default_values.get('integer', 1),
        'long': default_values.get('integer', 1),
        'number': default_values.get('number', 1.0),
        'float': default_values.get('number', 1.0),
        'double': default_values.get('number', 1.0),
        'boolean': default_values.get('boolean', True),
        'bool': default_values.get('boolean', True),
        # 日期时间类型
        'date': default_values.get('date', '2024-01-01'),
        'datetime': default_values.get('datetime', '2024-01-01 00:00:00'),
        'date-time': default_values.get('date-time', '2024-01-01T00:00:00Z'),  # OpenAPI 3.0 格式
        'timestamp': default_values.get('timestamp', 1704067200),
        # 复杂类型
        'array': default_values.get('array', []),
        'object': default_values.get('object', {}),
        'file': default_values.get('file', 'test_file')  # 文件类型返回特殊标记，由 request_builder 处理
    }

    # 获取基于名称的默认值配置
    name_based_defaults = default_values.get('name_based', {})

    # 根据参数名称推断（优先级最高）
    param_name_lower = param_name.lower()

    # 检查配置中的基于名称的默认值
    for key, value in name_based_defaults.items():
        if key.lower() in param_name_lower:
            return value

    # 如果配置中没有，使用内置的推断逻辑
    # 日期时间相关（优先级最高，因为可能包含其他关键字）
    if 'timestamp' in param_name_lower:
        return name_based_defaults.get('timestamp', 1704067200)
    elif 'datetime' in param_name_lower or 'date_time' in param_name_lower:
        return name_based_defaults.get('datetime', '2024-01-01 00:00:00')
    elif 'created' in param_name_lower or 'updated' in param_name_lower:
        return name_based_defaults.get('created', name_based_defaults.get('updated', '2024-01-01 00:00:00'))
    elif 'time' in param_name_lower:
        return name_based_defaults.get('time', '2024-01-01 00:00:00')
    elif 'date' in param_name_lower:
        return name_based_defaults.get('date', '2024-01-01')
    elif 'start' in param_name_lower:
        return name_based_defaults.get('start', '2024-01-01')
    elif 'end' in param_name_lower:
        return name_based_defaults.get('end', '2024-12-31')
    # 其他常见字段
    elif 'id' in param_name_lower:
        return name_based_defaults.get('id', 1)
    elif 'name' in param_name_lower:
        return name_based_defaults.get('name', 'test')
    elif 'email' in param_name_lower:
        return name_based_defaults.get('email', 'test@example.com')
    elif 'phone' in param_name_lower:
        return name_based_defaults.get('phone', '13800138000')
    elif 'url' in param_name_lower:
        return name_based_defaults.get('url', 'http://example.com')
    elif 'page' in param_name_lower:
        return name_based_defaults.get('page', 1)
    elif 'size' in param_name_lower or 'limit' in param_name_lower:
        return name_based_defaults.get('size', name_based_defaults.get('limit', 10))
    elif 'status' in param_name_lower:
        return name_based_defaults.get('status', 1)

    # 默认根据类型
    return type_mapping.get(param_type.lower() if param_type else 'string', default_values.get('string', 'test'))


def format_size(size):
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"


def format_time(seconds):
    """格式化时间"""
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    return f"{seconds:.2f}s"


def is_json_content_type(content_type):
    """判断是否为 JSON 内容类型"""
    if not content_type:
        return False
    return 'application/json' in content_type.lower()


def truncate_string(s, max_length=100):
    """截断字符串"""
    if len(s) <= max_length:
        return s
    return s[:max_length] + '...'


def create_test_file(param_name='file', file_type='txt'):
    """创建测试文件对象

    Args:
        param_name: 参数名称，用于推断文件类型
        file_type: 文件类型（txt, jpg, png, pdf等）

    Returns:
        tuple: (filename, file_content, content_type)
    """
    import io

    # 根据参数名推断文件类型
    param_name_lower = param_name.lower()

    if 'image' in param_name_lower or 'img' in param_name_lower or 'photo' in param_name_lower or 'avatar' in param_name_lower:
        # 图片文件 - 创建一个最小的 1x1 PNG
        filename = 'test_image.png'
        # 最小的 PNG 文件（1x1 透明像素）
        file_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        content_type = 'image/png'
    elif 'pdf' in param_name_lower or 'document' in param_name_lower or 'doc' in param_name_lower:
        # PDF 文件 - 创建一个最小的 PDF
        filename = 'test_document.pdf'
        file_content = b'%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000056 00000 n\n0000000115 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n206\n%%EOF'
        content_type = 'application/pdf'
    elif 'video' in param_name_lower:
        # 视频文件
        filename = 'test_video.mp4'
        file_content = b'test video content'
        content_type = 'video/mp4'
    elif 'audio' in param_name_lower:
        # 音频文件
        filename = 'test_audio.mp3'
        file_content = b'test audio content'
        content_type = 'audio/mpeg'
    elif 'csv' in param_name_lower:
        # CSV 文件
        filename = 'test_data.csv'
        file_content = b'id,name,value\n1,test,100\n'
        content_type = 'text/csv'
    elif 'json' in param_name_lower:
        # JSON 文件
        filename = 'test_data.json'
        file_content = b'{"test": "data"}'
        content_type = 'application/json'
    elif 'xml' in param_name_lower:
        # XML 文件
        filename = 'test_data.xml'
        file_content = b'<?xml version="1.0"?><root><test>data</test></root>'
        content_type = 'application/xml'
    else:
        # 默认文本文件
        filename = 'test_file.txt'
        file_content = b'This is a test file for API fuzzing.'
        content_type = 'text/plain'

    return (filename, io.BytesIO(file_content), content_type)
