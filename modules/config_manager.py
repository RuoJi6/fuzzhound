#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块
"""

import sys
import yaml
from rich.console import Console
from pydantic import ValidationError
from modules.fuzz_config import process_fuzz_args
from modules.config_model import AppConfig

console = Console()


def load_config(config_file):
    """加载配置文件"""
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            yaml_data = yaml.safe_load(f) or {}
            
        # 使用 Pydantic 验证并填充默认值
        # 注意：这里我们允许部分字段缺失，由 Pydantic 填充默认值
        # 但对于必需字段（如 target.base_url），如果 YAML 中没有且没有默认值，会在 validate_config 中检查
        # 或者我们可以先创建一个只有部分数据的 dict，后续合并命令行参数后再验证
        
        # 为了支持命令行参数覆盖，我们这里先不进行严格验证，只做基础结构填充
        # 但 AppConfig 定义了 target 是必需的，所以如果 YAML 空的话会报错
        # 我们先返回 yaml_data，在 merge_cli_args 之后再做最终验证
        
        # 不过，为了让 merge_cli_args 能安全地访问嵌套字典，我们需要确保结构存在
        # 我们可以用 AppConfig 来填充默认结构，但允许缺失必需字段（通过 construct 或 partial）
        # 但 Pydantic v2 没有 construct 了 (有 model_construct 但不验证)
        
        # 策略：先返回原始 dict，但在 merge_cli_args 中要小心 key error
        # 或者，我们可以定义一个 "PartialAppConfig" 所有字段可选？
        # 不，最好的办法是：
        # 1. 加载 YAML
        # 2. 确保顶层 key 存在
        
        config = yaml_data
        
        # 确保基本结构存在，避免 merge_cli_args 报错
        if 'target' not in config: config['target'] = {}
        if 'request' not in config: config['request'] = {}
        if 'auth' not in config: config['auth'] = {}
        if 'proxy' not in config: config['proxy'] = {}
        if 'blacklist' not in config: config['blacklist'] = {}
        if 'fuzz_username' not in config: config['fuzz_username'] = {}
        if 'fuzz_password' not in config: config['fuzz_password'] = {}
        if 'fuzz_number' not in config: config['fuzz_number'] = {}
        if 'fuzz_sql' not in config: config['fuzz_sql'] = {}
        if 'fuzz_detection' not in config: config['fuzz_detection'] = {}
        if 'output' not in config: config['output'] = {}
        if 'logging' not in config: config['logging'] = {}
        if 'debug' not in config: config['debug'] = {}
        if 'default_values' not in config: config['default_values'] = {}
        
        return config
    except Exception as e:
        console.print(f"[red]✗ 加载配置文件失败: {e}[/red]")
        sys.exit(1)


def validate_config(config):
    """验证配置文件"""
    """验证配置文件"""
    try:
        # 使用 Pydantic 进行最终验证
        # 这会检查类型、必需字段和默认值
        app_config = AppConfig(**config)
        
        # 将验证后的配置（包含默认值）转回 dict，更新原 config
        # 这样后续代码可以使用完整的配置（包含 Pydantic 填充的默认值）
        validated_dict = app_config.model_dump()
        config.update(validated_dict)
        
        return True
    except ValidationError as e:
        console.print(f"[red]✗ 配置文件验证失败:[/red]")
        for error in e.errors():
            loc = " -> ".join(str(x) for x in error['loc'])
            msg = error['msg']
            console.print(f"  - [yellow]{loc}[/yellow]: {msg}")
        return False
    except Exception as e:
        console.print(f"[red]✗ 验证配置时发生未知错误: {e}[/red]")
        return False


def merge_cli_args(config, args):
    """将命令行参数合并到配置中
    
    Args:
        config: 配置字典
        args: 命令行参数对象
        
    Returns:
        dict: 合并后的配置
    """
    # 命令行参数覆盖配置文件
    if args.url:
        config['target']['base_url'] = args.url
        # 如果没有指定 path，使用默认值
        if not args.path:
            config['target']['api_path'] = '/api-docs'
    if args.path:
        config['target']['api_path'] = args.path
    if args.prefix:
        config['target']['custom_prefix'] = args.prefix
    if hasattr(args, 'ignore_basepath') and args.ignore_basepath:
        config['target']['ignore_basepath'] = True
    if args.output:
        config['output']['output_dir'] = args.output
    if args.threads:
        config['request']['threads'] = args.threads
    if args.delay is not None:
        config['request']['delay'] = args.delay
    if args.verbose:
        config['output']['verbose'] = True
    if args.debug:
        # 启用调试模式
        if 'debug' not in config:
            config['debug'] = {}
        config['debug']['enabled'] = True
        config['debug']['verbose'] = True
        config['debug']['save_requests'] = True
        config['debug']['save_responses'] = True
        # 调试模式下自动启用详细输出
        config['output']['verbose'] = True
    
    # 处理代理参数
    if args.proxy:
        if 'request' not in config:
            config['request'] = {}
        config['request']['proxy'] = args.proxy
        console.print(f"[yellow]📢 使用代理: {args.proxy}[/yellow]")
    
    # 处理黑名单参数
    if args.ignore_blacklist:
        if 'blacklist' not in config:
            config['blacklist'] = {}
        config['blacklist']['ignore_blacklist'] = True
        console.print(f"[yellow]⚠️  已忽略黑名单，将测试所有接口（包括危险操作）[/yellow]")
    
    # 处理默认值参数
    if hasattr(args, 'default_int') and args.default_int is not None:
        if 'default_values' not in config:
            config['default_values'] = {}
        config['default_values']['integer'] = args.default_int
    if hasattr(args, 'default_float') and args.default_float is not None:
        if 'default_values' not in config:
            config['default_values'] = {}
        config['default_values']['number'] = args.default_float
    if hasattr(args, 'default_string') and args.default_string is not None:
        if 'default_values' not in config:
            config['default_values'] = {}
        config['default_values']['string'] = args.default_string
    if hasattr(args, 'default_bool') and args.default_bool is not None:
        if 'default_values' not in config:
            config['default_values'] = {}
        config['default_values']['boolean'] = args.default_bool.lower() == 'true'
    if hasattr(args, 'default_date') and args.default_date is not None:
        if 'default_values' not in config:
            config['default_values'] = {}
        config['default_values']['date'] = args.default_date
    if hasattr(args, 'default_datetime') and args.default_datetime is not None:
        if 'default_values' not in config:
            config['default_values'] = {}
        config['default_values']['datetime'] = args.default_datetime
    if hasattr(args, 'default_timestamp') and args.default_timestamp is not None:
        if 'default_values' not in config:
            config['default_values'] = {}
        config['default_values']['timestamp'] = args.default_timestamp

    # 处理 --fall 参数（一键启用所有Fuzz）
    if hasattr(args, 'fall') and args.fall:
        mode = args.fall
        if mode == 'all':
            # 全部参数模式
            console.print(f"[red bold]🔥 启用所有Fuzz测试 - 全部参数模式（测试所有参数）[/red bold]")
            console.print(f"[yellow]  ├─ 用户名Fuzz：全部参数[/yellow]")
            console.print(f"[yellow]  ├─ 密码Fuzz：全部参数[/yellow]")
            console.print(f"[yellow]  ├─ 数字Fuzz：全部参数[/yellow]")
            console.print(f"[yellow]  └─ SQL注入Fuzz：全部参数[/yellow]")

            # 启用所有Fuzz，使用 "all" 模式
            if 'fuzz_username' not in config:
                config['fuzz_username'] = {}
            config['fuzz_username']['enabled'] = True
            config['fuzz_username']['mode'] = 'all'
            config['fuzz_username']['count'] = 0  # 0 表示使用全部字典

            if 'fuzz_password' not in config:
                config['fuzz_password'] = {}
            config['fuzz_password']['enabled'] = True
            config['fuzz_password']['mode'] = 'all'
            config['fuzz_password']['count'] = 0  # 0 表示使用全部字典

            if 'fuzz_number' not in config:
                config['fuzz_number'] = {}
            config['fuzz_number']['enabled'] = True
            config['fuzz_number']['mode'] = 'all'

            if 'fuzz_sql' not in config:
                config['fuzz_sql'] = {}
            config['fuzz_sql']['enabled'] = True
            config['fuzz_sql']['mode'] = 'all'
        else:
            # 默认模式（关键字匹配）
            console.print(f"[red bold]🔥 启用所有Fuzz测试 - 默认模式（使用关键字匹配）[/red bold]")
            console.print(f"[yellow]  ├─ 用户名Fuzz：关键字模式[/yellow]")
            console.print(f"[yellow]  ├─ 密码Fuzz：关键字模式[/yellow]")
            console.print(f"[yellow]  ├─ 数字Fuzz：默认模式[/yellow]")
            console.print(f"[yellow]  └─ SQL注入Fuzz：关键字模式[/yellow]")

            # 启用所有Fuzz，使用关键字模式
            if 'fuzz_username' not in config:
                config['fuzz_username'] = {}
            config['fuzz_username']['enabled'] = True

            if 'fuzz_password' not in config:
                config['fuzz_password'] = {}
            config['fuzz_password']['enabled'] = True

            if 'fuzz_number' not in config:
                config['fuzz_number'] = {}
            config['fuzz_number']['enabled'] = True

            if 'fuzz_sql' not in config:
                config['fuzz_sql'] = {}
            config['fuzz_sql']['enabled'] = True

    # 处理其他 Fuzz 参数
    config = process_fuzz_args(config, args)

    return config

