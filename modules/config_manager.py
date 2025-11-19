#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块
"""

import sys
import yaml
from rich.console import Console
from modules.fuzz_config import process_fuzz_args

console = Console()


def load_config(config_file):
    """加载配置文件"""
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        console.print(f"[red]✗ 加载配置文件失败: {e}[/red]")
        sys.exit(1)


def validate_config(config):
    """验证配置文件"""
    required_fields = ['target', 'output']
    for field in required_fields:
        if field not in config:
            console.print(f"[red]✗ 配置文件缺少必需字段: {field}[/red]")
            return False
    
    if 'base_url' not in config['target']:
        console.print(f"[red]✗ 配置文件缺少必需字段: target.base_url[/red]")
        return False
    
    return True


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

