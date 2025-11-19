#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fuzz 配置处理模块
"""

import sys
from rich.console import Console

console = Console()


def _parse_fuzz_param(param_value, config, config_key, fuzz_name):
    """解析 Fuzz 参数

    Args:
        param_value: 参数值（如 "30", "all", "all:100", "all:all"）
        config: 配置字典
        config_key: 配置键名（如 'fuzz_username', 'fuzz_password'）
        fuzz_name: Fuzz 名称（用于错误提示，如 '用户名', '密码'）
    """
    if param_value == 'default':
        # 使用默认配置（关键字匹配 + 默认数量15）
        pass
    elif param_value == 'all':
        # all = 所有参数 + 默认数量15
        config[config_key]['mode'] = 'all'
        config[config_key]['count'] = 15
    elif ':' in param_value:
        # all:N 或 all:all 格式
        parts = param_value.split(':', 1)
        if len(parts) == 2 and parts[0] == 'all':
            config[config_key]['mode'] = 'all'
            if parts[1] == 'all':
                # all:all = 所有参数 + 全部字典
                config[config_key]['count'] = 0
            else:
                # all:N = 所有参数 + 随机N个
                try:
                    count = int(parts[1])
                    config[config_key]['count'] = count
                except ValueError:
                    console.print(f"[red]❌ 错误：{fuzz_name}Fuzz参数格式错误，all:后应为数字或'all'[/red]")
                    sys.exit(1)
        else:
            console.print(f"[red]❌ 错误：{fuzz_name}Fuzz参数格式错误，应为 'all:N' 或 'all:all'[/red]")
            sys.exit(1)
    else:
        # 纯数字 = 关键字匹配 + 随机N个
        try:
            count = int(param_value)
            config[config_key]['count'] = count
        except ValueError:
            console.print(f"[red]❌ 错误：{fuzz_name}Fuzz参数格式错误，应为数字、'all'、'all:N' 或 'all:all'[/red]")
            sys.exit(1)


def process_fuzz_args(config, args):
    """处理 Fuzz 相关的命令行参数
    
    Args:
        config: 配置字典
        args: 命令行参数对象
        
    Returns:
        dict: 更新后的配置
    """
    # 处理单独的 Fuzz 参数
    if hasattr(args, 'fuser') and args.fuser:
        if 'fuzz_username' not in config:
            config['fuzz_username'] = {}
        config['fuzz_username']['enabled'] = True

        # 解析用户名Fuzz参数
        # 格式：N | all | all:N | all:all
        _parse_fuzz_param(args.fuser, config, 'fuzz_username', '用户名')

    if hasattr(args, 'fpass') and args.fpass:
        if 'fuzz_password' not in config:
            config['fuzz_password'] = {}
        config['fuzz_password']['enabled'] = True

        # 解析密码Fuzz参数
        # 格式：N | all | all:N | all:all
        _parse_fuzz_param(args.fpass, config, 'fuzz_password', '密码')
    
    if hasattr(args, 'fnumber') and args.fnumber:
        if 'fuzz_number' not in config:
            config['fuzz_number'] = {}
        config['fuzz_number']['enabled'] = True
        
        # 解析数字Fuzz参数
        if args.fnumber == 'all':
            config['fuzz_number']['mode'] = 'all'
        elif '-' in args.fnumber:
            # 范围模式：1-100
            try:
                start, end = args.fnumber.split('-')
                config['fuzz_number']['mode'] = 'range'
                config['fuzz_number']['range_start'] = int(start)
                config['fuzz_number']['range_end'] = int(end)
            except ValueError:
                console.print(f"[red]❌ 错误：--fnumber 参数格式错误，应为数字、范围（如1-100）或'all'[/red]")
                sys.exit(1)
        else:
            # 数量模式：40
            try:
                count = int(args.fnumber)
                config['fuzz_number']['mode'] = 'random'
                config['fuzz_number']['count'] = count
            except ValueError:
                console.print(f"[red]❌ 错误：--fnumber 参数格式错误，应为数字、范围（如1-100）或'all'[/red]")
                sys.exit(1)
    
    if hasattr(args, 'fpsql') and args.fpsql:
        if 'fuzz_sql' not in config:
            config['fuzz_sql'] = {}
        config['fuzz_sql']['enabled'] = True
        if args.fpsql == 'all':
            config['fuzz_sql']['mode'] = 'all'
    
    # 处理 SQL 模式参数
    if hasattr(args, 'sql_mode') and args.sql_mode:
        if 'fuzz_sql' not in config:
            config['fuzz_sql'] = {}
        config['fuzz_sql']['mode'] = args.sql_mode
    
    # 处理 SQL payload 数量参数
    if hasattr(args, 'sql_payloads') and args.sql_payloads:
        if 'fuzz_sql' not in config:
            config['fuzz_sql'] = {}
        config['fuzz_sql']['max_payloads'] = args.sql_payloads
    
    # 处理枚举参数测试限制参数
    if hasattr(args, 'enum_limit') and args.enum_limit is not None:
        if 'request' not in config:
            config['request'] = {}
        config['request']['enum_test_limit'] = args.enum_limit
        if args.enum_limit == 0:
            console.print(f"[yellow]📢 枚举参数测试：测试所有枚举值（针对 API 文档中定义了 enum 的参数）[/yellow]")
        else:
            console.print(f"[yellow]📢 枚举参数测试：每个枚举参数只测试前 {args.enum_limit} 个值（针对 API 文档中定义了 enum 的参数）[/yellow]")
    
    # 处理 Fuzz 状态码筛选参数
    if hasattr(args, 'fuzz_status') and args.fuzz_status:
        if 'fuzz_detection' not in config:
            config['fuzz_detection'] = {}

        if args.fuzz_status.lower() == 'all':
            # 显示所有状态码
            config['fuzz_detection']['filter_status_codes'] = []
            console.print(f"[yellow]📢 Fuzz状态码筛选：显示所有状态码[/yellow]")
        else:
            # 解析状态码列表
            try:
                status_codes = [int(code.strip()) for code in args.fuzz_status.split(',')]
                config['fuzz_detection']['filter_status_codes'] = status_codes
                console.print(f"[yellow]📢 Fuzz状态码筛选：只显示状态码 {status_codes} 的结果[/yellow]")
            except ValueError:
                console.print(f"[red]❌ 错误：--fuzz-status 参数格式错误，应为逗号分隔的数字（如: 200,500,403）或 'all'[/red]")
                sys.exit(1)

    # 处理 Fuzz 前置筛选参数
    if hasattr(args, 'fuzz_filter') and args.fuzz_filter:
        if 'fuzz_detection' not in config:
            config['fuzz_detection'] = {}

        if args.fuzz_filter.lower() == 'all':
            # 对所有API进行Fuzz
            config['fuzz_detection']['fuzz_filter_codes'] = []
            console.print(f"[yellow]📢 Fuzz前置筛选：对所有API进行Fuzz测试[/yellow]")
        else:
            # 解析状态码列表
            try:
                status_codes = [int(code.strip()) for code in args.fuzz_filter.split(',')]
                config['fuzz_detection']['fuzz_filter_codes'] = status_codes
                console.print(f"[yellow]📢 Fuzz前置筛选：只对状态码为 {status_codes} 的API进行Fuzz测试[/yellow]")
            except ValueError:
                console.print(f"[red]❌ 错误：--fuzz-filter 参数格式错误，应为逗号分隔的数字（如: 200,403）或 'all'[/red]")
                sys.exit(1)

    return config

