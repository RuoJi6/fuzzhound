#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试执行器模块
负责执行普通测试和 Fuzz 测试
"""

import sys
import time
import threading
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from modules.api_parser import APIParser
from modules.request_builder import RequestBuilder
from modules.request_sender import RequestSender
from modules.reporter import Reporter
from modules.fuzz_detector import FuzzDetector
from modules.sql_detector import SQLDetector
from modules.handlers import create_normal_test_handler, create_fuzz_test_handler

console = Console()
logger = logging.getLogger('fuzzhound')

# 线程锁，用于保护共享资源
results_lock = threading.Lock()
print_lock = threading.Lock()


def display_config(config):
    """显示配置信息
    
    Args:
        config: 配置字典
    """
    # 检查是否启用了任何Fuzz功能
    fuzz_username_config = config.get('fuzz_username', {})
    fuzz_password_config = config.get('fuzz_password', {})
    fuzz_number_config = config.get('fuzz_number', {})
    fuzz_sql_config = config.get('fuzz_sql', {})
    any_fuzz_enabled = (fuzz_username_config.get('enabled', False) or 
                       fuzz_password_config.get('enabled', False) or 
                       fuzz_number_config.get('enabled', False) or 
                       fuzz_sql_config.get('enabled', False))
    
    # 显示目标 URL
    console.print(f"[cyan]🎯 目标 URL:[/cyan] {config['target']['base_url']}")
    
    # 显示并发线程数
    threads = config['request'].get('threads', 5)
    console.print(f"[cyan]🔧 并发线程:[/cyan] {threads}")
    
    # 显示请求延迟
    delay = config['request'].get('delay', 0)
    console.print(f"[cyan]⏱️  请求延迟:[/cyan] {delay}s")
    
    # 显示黑名单状态
    blacklist_enabled = config.get('blacklist', {}).get('enabled', False)
    ignore_blacklist = config.get('blacklist', {}).get('ignore_blacklist', False)
    if blacklist_enabled and not ignore_blacklist:
        console.print(f"[cyan]🛡️  黑名单状态:[/cyan] 已启用")
    elif ignore_blacklist:
        console.print(f"[yellow]🛡️  黑名单状态:[/cyan] 已忽略[/yellow]")
    else:
        console.print(f"[cyan]🛡️  黑名单状态:[/cyan] 未启用")
    
    # 显示用户名 Fuzz 配置
    if fuzz_username_config.get('enabled', False):
        username_file = fuzz_username_config.get('username_file', 'config/usernames.txt')
        keywords = fuzz_username_config.get('keywords', [])
        count = fuzz_username_config.get('count', 15)
        mode = fuzz_username_config.get('mode', 'keyword')

        console.print(f"[yellow]💥 用户名 Fuzz:[/yellow] [red bold]已启用[/red bold]")
        console.print(f"[cyan]📖 字典文件:[/cyan] {username_file}")

        # 显示参数匹配模式
        if mode == 'all':
            console.print(f"[cyan]🎯 参数匹配:[/cyan] 所有字符串参数")
        else:
            console.print(f"[cyan]🎯 参数匹配:[/cyan] 关键字匹配 ({', '.join(keywords)})")

        # 显示字典数量
        if count > 0:
            console.print(f"[cyan]🔢 字典数量:[/cyan] 随机挑选 {count} 个")
        else:
            console.print(f"[cyan]🔢 字典数量:[/cyan] 全部")

    # 显示密码 Fuzz 配置
    if fuzz_password_config.get('enabled', False):
        password_file = fuzz_password_config.get('password_file', 'config/top100_password.txt')
        keywords = fuzz_password_config.get('keywords', [])
        count = fuzz_password_config.get('count', 15)
        mode = fuzz_password_config.get('mode', 'keyword')

        console.print(f"[yellow]💥 密码 Fuzz:[/yellow] [red bold]已启用[/red bold]")
        console.print(f"[cyan]📖 字典文件:[/cyan] {password_file}")

        # 显示参数匹配模式
        if mode == 'all':
            console.print(f"[cyan]🎯 参数匹配:[/cyan] 所有字符串参数")
        else:
            console.print(f"[cyan]🎯 参数匹配:[/cyan] 关键字匹配 ({', '.join(keywords)})")

        # 显示字典数量
        if count > 0:
            console.print(f"[cyan]🔢 字典数量:[/cyan] 随机挑选 {count} 个")
        else:
            console.print(f"[cyan]🔢 字典数量:[/cyan] 全部")

    # 显示数字型 Fuzz 配置
    if fuzz_number_config.get('enabled', False):
        mode = fuzz_number_config.get('mode', 'random')
        if mode == 'range':
            start = fuzz_number_config.get('range_start', 1)
            end = fuzz_number_config.get('range_end', 100)
            console.print(f"[yellow]💥 数字型 Fuzz:[/yellow] [red bold]已启用[/red bold]")
            console.print(f"[cyan]🔢 Fuzz 模式:[/cyan] 范围遍历 ({start}-{end})")
        else:
            count = fuzz_number_config.get('count', 15)
            start = fuzz_number_config.get('default_range_start', 1)
            end = fuzz_number_config.get('default_range_end', 1000)
            console.print(f"[yellow]💥 数字型 Fuzz:[/yellow] [red bold]已启用[/red bold]")
            console.print(f"[cyan]🔢 Fuzz 模式:[/cyan] 随机挑选 (从{start}-{end}中随机{count}个)")

    # 显示SQL注入 Fuzz 配置
    if fuzz_sql_config.get('enabled', False):
        mode = fuzz_sql_config.get('mode', 'smart')
        payload_file = fuzz_sql_config.get('payload_file', 'config/sql_payloads.txt')
        keywords = fuzz_sql_config.get('keywords', [])
        max_payloads = fuzz_sql_config.get('max_payloads', 20)
        console.print(f"[yellow]💥 SQL注入 Fuzz:[/yellow] [red bold]已启用[/red bold]")
        console.print(f"[cyan]🎯 Fuzz 模式:[/cyan] {mode}")
        console.print(f"[cyan]📖 Payload文件:[/cyan] {payload_file}")
        if keywords:
            console.print(f"[cyan]🔑 匹配关键字:[/cyan] {', '.join(keywords)}")
        else:
            console.print(f"[cyan]🔑 匹配关键字:[/cyan] 全部参数")
        if mode == 'smart' and max_payloads > 0:
            console.print(f"[cyan]📊 最大Payload数:[/cyan] {max_payloads}")

    # 显示 Fuzz 状态码筛选配置
    fuzz_detection_config = config.get('fuzz_detection', {})
    filter_status_codes = fuzz_detection_config.get('filter_status_codes', [])
    fuzz_filter_codes = fuzz_detection_config.get('fuzz_filter_codes', [])
    if any_fuzz_enabled:
        # Fuzz 前置筛选
        if fuzz_filter_codes:
            console.print(f"[cyan]🎯 Fuzz前置筛选:[/cyan] 只对状态码为 {fuzz_filter_codes} 的API进行Fuzz")
        else:
            console.print(f"[cyan]🎯 Fuzz前置筛选:[/cyan] 对所有API进行Fuzz")

        # Fuzz 结果筛选
        if filter_status_codes:
            console.print(f"[cyan]🔍 Fuzz结果筛选:[/cyan] 只显示状态码 {filter_status_codes} 的结果")
        else:
            console.print(f"[cyan]🔍 Fuzz结果筛选:[/cyan] 显示所有状态码")
    
    # 显示调试模式状态
    debug_config = config.get('debug', {})
    if debug_config.get('enabled', False):
        console.print(f"[yellow]🐛 调试模式:[/yellow] [red bold]已启用[/red bold]")
        log_config = config.get('logging', {})
        log_dir = log_config.get('log_dir', 'logs')
        log_file = log_config.get('log_file', 'api_fuzzer.log')
        console.print(f"[cyan]📝 日志文件:[/cyan] {log_dir}/{log_file}")
    
    # 显示默认参数值
    default_values = config.get('default_values', {})
    if default_values:
        console.print(f"[cyan]🎲 默认参数值:[/cyan]")
        if 'integer' in default_values:
            console.print(f"   整数型: {default_values['integer']}")
        if 'number' in default_values:
            console.print(f"   浮点型: {default_values['number']}")
        if 'string' in default_values:
            console.print(f"   字符串: {default_values['string']}")
        if 'boolean' in default_values:
            console.print(f"   布尔型: {default_values['boolean']}")
        if 'date' in default_values:
            console.print(f"   日期型: {default_values['date']}")
        if 'datetime' in default_values:
            console.print(f"   日期时间: {default_values['datetime']}")
        if 'timestamp' in default_values:
            console.print(f"   时间戳: {default_values['timestamp']}")


def calculate_total_requests(apis, config):
    """计算实际会生成的请求数量（考虑枚举值测试）

    Args:
        apis: API 列表
        config: 配置字典

    Returns:
        tuple: (total_normal_requests, total_enum_requests, has_enum_params)
    """
    total_normal_requests = 0
    total_enum_requests = 0
    has_enum_params = False
    double_check = config['request'].get('double_check', True)

    for api in apis:
        # 获取枚举参数测试限制
        enum_test_limit = config.get('request', {}).get('enum_test_limit', 0)

        # 获取所有枚举参数
        enum_params = {}
        parameters = api.get('parameters', {})

        # 检查路径参数
        for param in parameters.get('path', []):
            param_schema = param.get('schema', {})
            if param_schema.get('enum'):
                enum_params[param.get('name', '')] = param_schema['enum']

        # 检查查询参数
        for param in parameters.get('query', []):
            param_schema = param.get('schema', {})
            if param_schema.get('enum'):
                enum_params[param.get('name', '')] = param_schema['enum']

        # 计算枚举值组合数量
        if enum_params:
            has_enum_params = True
            import itertools

            # 获取参数名和对应的枚举值列表
            param_names = list(enum_params.keys())
            enum_value_lists = []

            for name in param_names:
                values = enum_params[name]
                # 如果设置了限制，只取前 N 个值
                if enum_test_limit > 0 and len(values) > enum_test_limit:
                    values = values[:enum_test_limit]
                enum_value_lists.append(values)

            # 计算组合数量
            combinations_count = 1
            for values in enum_value_lists:
                combinations_count *= len(values)

            # 每个组合会生成 1 或 2 个请求（取决于 double_check 和是否有查询参数）
            has_query_params = len(parameters.get('query', [])) > 0
            if double_check and has_query_params:
                enum_requests = combinations_count * 2  # 原始请求 + 带参数请求
                total_normal_requests += enum_requests
                total_enum_requests += enum_requests
            else:
                total_normal_requests += combinations_count
                total_enum_requests += combinations_count
        else:
            # 没有枚举参数，按正常逻辑计算
            has_query_params = len(parameters.get('query', [])) > 0
            if double_check and has_query_params:
                total_normal_requests += 2  # 原始请求 + 带参数请求
            else:
                total_normal_requests += 1

    return total_normal_requests, total_enum_requests, has_enum_params


def execute_fuzz_tests(config, apis, request_builder, request_sender, reporter,
                       fuzz_detector, sql_detector, any_fuzz_enabled,
                       fuzz_username_enabled, fuzz_password_enabled,
                       fuzz_number_enabled, fuzz_sql_enabled,
                       threads, delay, api_status_map):
    """执行 Fuzz 测试

    Args:
        config: 配置字典
        apis: API 列表
        request_builder: 请求构建器
        request_sender: 请求发送器
        reporter: 报告器
        fuzz_detector: Fuzz 检测器
        sql_detector: SQL 检测器
        any_fuzz_enabled: 是否启用了任何 Fuzz
        fuzz_username_enabled: 是否启用用户名 Fuzz
        fuzz_password_enabled: 是否启用密码 Fuzz
        fuzz_number_enabled: 是否启用数字 Fuzz
        fuzz_sql_enabled: 是否启用 SQL Fuzz
        threads: 线程数
        delay: 请求延迟
        api_status_map: API 状态码映射字典 {api_key: status_code}
    """
    console.print(f"\n[cyan]📍 阶段 2/2: Fuzz 测试[/cyan]\n")

    # 获取 Fuzz 前置筛选配置
    fuzz_filter_codes = config.get('fuzz_detection', {}).get('fuzz_filter_codes', [])

    # 如果配置了前置筛选，显示筛选信息
    if fuzz_filter_codes:
        console.print(f"[yellow]🔍 Fuzz前置筛选：只对状态码为 {fuzz_filter_codes} 的API进行Fuzz测试[/yellow]")

    # 创建新的进度条用于 Fuzz 测试
    fuzz_progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=False
    )

    fuzz_progress.start()

    # 收集所有 Fuzz 请求
    all_fuzz_requests = []
    filtered_apis_count = 0  # 被筛选掉的 API 数量

    for api in apis:
        # 检查是否在黑名单中
        blacklist_config = config.get('blacklist', {})
        ignore_blacklist = blacklist_config.get('ignore_blacklist', False)

        if api.get('is_blacklisted', False) and not ignore_blacklist:
            continue

        # 如果配置了 Fuzz 前置筛选，检查该 API 的状态码
        if fuzz_filter_codes:
            # 生成 API 的唯一标识
            api_key = f"{api.get('method', 'GET')}:{api.get('path', '')}"
            api_status = api_status_map.get(api_key, 0)

            # 如果状态码不在筛选列表中，跳过该 API
            if api_status not in fuzz_filter_codes:
                filtered_apis_count += 1
                continue

        # 构造 Fuzz 请求
        fuzz_requests_list = request_builder.build_fuzz_requests(api)
        all_fuzz_requests.extend(fuzz_requests_list)

    # 如果有 API 被筛选掉，显示统计信息
    if filtered_apis_count > 0:
        console.print(f"[yellow]📊 已筛选掉 {filtered_apis_count} 个不符合状态码条件的API[/yellow]")

    # 如果没有 Fuzz 请求，直接返回
    if len(all_fuzz_requests) == 0:
        fuzz_progress.stop()
        console.print(f"[yellow]⚠️  没有符合条件的API需要进行Fuzz测试[/yellow]")
        return

    fuzz_task = fuzz_progress.add_task("[yellow]Fuzz 测试进度", total=len(all_fuzz_requests))

    logger.info(f"📊 总共生成了 {len(all_fuzz_requests)} 个 Fuzz 请求")

    # 创建 Fuzz 处理函数
    process_single_fuzz_request = create_fuzz_test_handler(
        config, request_sender, reporter, fuzz_detector,
        sql_detector, any_fuzz_enabled, delay, print_lock
    )

    try:
        # 使用线程池并发处理所有 Fuzz 请求
        with ThreadPoolExecutor(max_workers=threads) as executor:
            # 提交所有 Fuzz 请求任务
            future_to_req = {
                executor.submit(process_single_fuzz_request, req, fuzz_progress): req
                for req in all_fuzz_requests
            }

            # 处理完成的任务
            for future in as_completed(future_to_req):
                try:
                    result = future.result()

                    # 线程安全地打印结果
                    if result:
                        with print_lock:
                            # 判断是否应该显示此结果
                            should_print = False
                            fuzz_type = result.get('fuzz_type', 'normal')

                            # 调试模式：显示所有结果
                            if config.get('debug', {}).get('enabled', False):
                                should_print = True
                            # SQL注入Fuzz：只显示检测到漏洞的结果
                            elif fuzz_type == 'sql_fuzz':
                                if result.get('fuzz_analysis') and result['fuzz_analysis'].get('score', 0) > 0:
                                    should_print = True
                            # 其他Fuzz类型：只显示有异常的结果（状态码异常、响应异常等）
                            elif fuzz_type in ['username_fuzz', 'password_fuzz', 'number_fuzz']:
                                # 如果有 Fuzz 分析结果，检查分数是否达到阈值
                                if result.get('fuzz_analysis'):
                                    analysis = result['fuzz_analysis']
                                    # 只显示 "可能有效" 或 "高度可疑" 的结果（score >= 50）
                                    if analysis.get('level') in ['possible', 'likely']:
                                        should_print = True
                            # 其他未知类型：显示所有结果
                            else:
                                should_print = True

                            # 应用状态码筛选（如果配置了）
                            if should_print:
                                filter_status_codes = config.get('fuzz_detection', {}).get('filter_status_codes', [])
                                # 如果配置了状态码筛选（非空列表），则只显示匹配的状态码
                                if filter_status_codes:
                                    status_code = result.get('status_code', 0)
                                    if status_code not in filter_status_codes:
                                        should_print = False

                            if should_print:
                                output = reporter.format_result(result)
                                fuzz_progress.console.print(output)

                                # 如果有 Fuzz 分析结果，打印详细信息
                                if result.get('fuzz_analysis'):
                                    analysis = result['fuzz_analysis']
                                    if analysis['level'] in ['likely', 'possible']:
                                        detail = (
                                            f"         {'':8} {'':10} {'':8} {'':7} "
                                            f"[yellow]└─ {analysis['icon']} {analysis['label']} (评分: {analysis['score']}) "
                                            f"原因: {', '.join(analysis['reasons'])}[/yellow]"
                                        )
                                        fuzz_progress.console.print(detail)

                except Exception as e:
                    logger.error(f"处理 Fuzz 请求时出错: {e}")
                finally:
                    # 更新进度条
                    fuzz_progress.update(fuzz_task, advance=1)
    finally:
        fuzz_progress.stop()


def execute_tests(config):
    """执行测试

    Args:
        config: 配置字典
    """
    # 显示配置信息
    display_config(config)

    # 解析 API 文档
    console.print(f"\n[yellow]⚙ 正在解析 API 文档...[/yellow]")
    api_parser = APIParser(config)
    apis = api_parser.parse()

    if not apis:
        console.print(f"[red]✗ 未找到任何 API 接口[/red]")
        sys.exit(1)

    # 显示实际使用的 API 文档路径（解析后可能已更新）
    console.print(f"[cyan]📄 API 文档路径:[/cyan] {config['target']['api_path']}")

    # 初始化模块
    request_builder = RequestBuilder(config)
    request_sender = RequestSender(config)
    reporter = Reporter(config)

    # 初始化 Fuzz 检测器
    fuzz_detector = FuzzDetector(config)
    fuzz_username_enabled = config.get('fuzz_username', {}).get('enabled', False)
    fuzz_password_enabled = config.get('fuzz_password', {}).get('enabled', False)
    fuzz_number_enabled = config.get('fuzz_number', {}).get('enabled', False)
    fuzz_sql_enabled = config.get('fuzz_sql', {}).get('enabled', False)

    # 初始化 SQL 检测器（如果启用了SQL注入Fuzz）
    sql_detector = SQLDetector(config) if fuzz_sql_enabled else None

    # 检查是否启用了任何Fuzz功能
    any_fuzz_enabled = fuzz_username_enabled or fuzz_password_enabled or fuzz_number_enabled or fuzz_sql_enabled

    # 计算实际会生成的请求数量（考虑枚举值测试）
    total_normal_requests, total_enum_requests, has_enum_params = calculate_total_requests(apis, config)

    # 显示解析结果
    if has_enum_params:
        console.print(f"[green]✓ 成功解析 {len(apis)} 个 API 接口，enum参数生成 {total_enum_requests} 个请求，将生成 {total_normal_requests} 个测试请求[/green]")
    else:
        console.print(f"[green]✓ 成功解析 {len(apis)} 个 API 接口[/green]")

    console.print(f"\n[yellow]🚀 开始测试 API 接口 (多线程模式)...[/yellow]\n")

    # 测试参数
    results = []
    threads = config['request'].get('threads', 5)
    double_check = config['request'].get('double_check', True)
    delay = config['request'].get('delay', 0)

    # 用于记录每个 API 的状态码（用于 Fuzz 前置筛选）
    api_status_map = {}  # {api_key: status_code}

    # 创建进度条
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=False  # 不自动清除
    )

    progress.start()
    # 使用实际的请求数量作为进度条总数
    task = progress.add_task("[cyan]普通测试进度", total=total_normal_requests)

    # 创建处理函数
    process_api_normal = create_normal_test_handler(
        config, request_builder, request_sender, reporter,
        fuzz_detector, any_fuzz_enabled, delay, progress, print_lock, api_status_map
    )

    try:
        # ========== 第一阶段：普通测试 ==========
        console.print(f"[cyan]📍 阶段 1/2: 普通API测试[/cyan]\n")

        # 使用线程池并发处理普通请求
        with ThreadPoolExecutor(max_workers=threads) as executor:
            # 提交所有普通测试任务
            future_to_api = {executor.submit(process_api_normal, api): api for api in apis}

            # 处理完成的任务
            for future in as_completed(future_to_api):
                api = future_to_api[future]
                try:
                    api_results = future.result()

                    # 线程安全地添加结果
                    with results_lock:
                        results.extend(api_results)

                    # 更新进度条（根据实际生成的请求数量）
                    progress.update(task, advance=len(api_results))

                except Exception as e:
                    logger.error(f"处理 API {api.get('path', 'unknown')} 时出错: {e}")
                    # 即使出错也要更新进度条，避免卡住
                    progress.update(task, advance=1)

        progress.stop()

        # ========== 第二阶段：Fuzz 测试 ==========
        if any_fuzz_enabled:
            execute_fuzz_tests(
                config, apis, request_builder, request_sender, reporter,
                fuzz_detector, sql_detector, any_fuzz_enabled,
                fuzz_username_enabled, fuzz_password_enabled,
                fuzz_number_enabled, fuzz_sql_enabled,
                threads, delay, api_status_map
            )

        # 生成测试报告
        console.print(f"\n[yellow]📊 正在生成报告...[/yellow]")
        reporter.generate_html_report(results, apis)

        # 打印统计信息
        reporter.print_summary(results)

        # 获取输出目录
        from pathlib import Path
        output_dir = Path(config['output']['output_dir'])
        console.print(f"\n[green]✓ 测试完成！报告已保存到: {output_dir / config['output']['html_report']}[/green]")

    except Exception as e:
        progress.stop()
        raise e

