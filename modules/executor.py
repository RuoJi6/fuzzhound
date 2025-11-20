#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试执行器模块
负责执行普通测试和 Fuzz 测试 (AsyncIO 版本)
"""

import sys
import time
import asyncio
import logging
import signal
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

# 全局中断标志 (使用 asyncio.Event 在异步中更好，但为了兼容信号处理，使用简单的变量或 threading.Event)
# 在 asyncio 中，通常捕获 CancelledError
interrupted = False


def display_config(config):
    """显示配置信息"""
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
    
    # 显示并发数
    threads = config['request'].get('threads', 5)
    console.print(f"[cyan]🔧 并发请求:[/cyan] {threads}")
    
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
    
    # 显示 Fuzz 配置 (简化显示，避免代码过长)
    if any_fuzz_enabled:
        console.print(f"[yellow]💥 Fuzz 测试:[/yellow] [red bold]已启用[/red bold]")


def calculate_total_requests(apis, config):
    """计算实际会生成的请求数量"""
    total_normal_requests = 0
    total_enum_requests = 0
    has_enum_params = False
    double_check = config['request'].get('double_check', True)
    
    # 获取黑名单配置
    blacklist_config = config.get('blacklist', {})
    ignore_blacklist = blacklist_config.get('ignore_blacklist', False)

    for api in apis:
        # 跳过黑名单 API（除非忽略黑名单）
        if api.get('is_blacklisted', False) and not ignore_blacklist:
            continue
            
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

            # 每个组合会生成 1 或 2 个请求
            has_query_params = len(parameters.get('query', [])) > 0
            if double_check and has_query_params:
                enum_requests = combinations_count * 2
                total_normal_requests += enum_requests
                total_enum_requests += enum_requests
            else:
                total_normal_requests += combinations_count
                total_enum_requests += combinations_count
        else:
            # 没有枚举参数
            has_query_params = len(parameters.get('query', [])) > 0
            if double_check and has_query_params:
                total_normal_requests += 2
            else:
                total_normal_requests += 1

    return total_normal_requests, total_enum_requests, has_enum_params


async def execute_fuzz_tests_async(config, apis, request_builder, request_sender, reporter,
                                   fuzz_detector, sql_detector, any_fuzz_enabled,
                                   concurrency, delay, api_status_map, print_lock, interrupted_event):
    """执行 Fuzz 测试 (异步)"""
    console.print(f"\n[cyan]📍 阶段 2/2: Fuzz 测试[/cyan]\n")

    fuzz_results = []
    fuzz_filter_codes = config.get('fuzz_detection', {}).get('fuzz_filter_codes', [])

    if fuzz_filter_codes:
        console.print(f"[yellow]🔍 Fuzz前置筛选：只对状态码为 {fuzz_filter_codes} 的API进行Fuzz测试[/yellow]")

    # 创建进度条
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
    filtered_apis_count = 0
    status_zero_filtered = 0  # 新增：记录状态码为0的API数量

    for api in apis:
        blacklist_config = config.get('blacklist', {})
        ignore_blacklist = blacklist_config.get('ignore_blacklist', False)

        if api.get('is_blacklisted', False) and not ignore_blacklist:
            continue

        api_key = f"{api.get('method', 'GET')}:{api.get('path', '')}"
        api_status = api_status_map.get(api_key, 0)
        
        # 自动排除状态码为0的API（连接失败/超时等）
        if api_status == 0:
            status_zero_filtered += 1
            continue
        
        if fuzz_filter_codes:
            if api_status not in fuzz_filter_codes:
                filtered_apis_count += 1
                continue

        fuzz_requests_list = request_builder.build_fuzz_requests(api)
        all_fuzz_requests.extend(fuzz_requests_list)

    if status_zero_filtered > 0:
        console.print(f"[dim cyan]📊 已自动排除 {status_zero_filtered} 个状态码为0的API（连接失败/不可达）[/dim cyan]")
    if filtered_apis_count > 0:
        console.print(f"[yellow]📊 已筛选掉 {filtered_apis_count} 个不符合状态码条件的API[/yellow]")

    if len(all_fuzz_requests) == 0:
        fuzz_progress.stop()
        if fuzz_filter_codes:
            console.print(f"[yellow]⚠️  没有符合条件的API需要进行Fuzz测试 (筛选条件: 状态码 {fuzz_filter_codes})[/yellow]")
        else:
            console.print(f"[yellow]⚠️  没有符合条件的API需要进行Fuzz测试 (原因: 没有参数匹配默认关键字)[/yellow]")
            console.print(f"[yellow]💡 提示: 尝试使用 '--fall all' 参数来对所有参数进行Fuzz测试[/yellow]")
        return fuzz_results

    fuzz_task = fuzz_progress.add_task("[yellow]Fuzz 测试进度", total=len(all_fuzz_requests))
    logger.info(f"📊 总共生成了 {len(all_fuzz_requests)} 个 Fuzz 请求")

    process_single_fuzz_request = create_fuzz_test_handler(
        config, request_sender, reporter, fuzz_detector,
        sql_detector, any_fuzz_enabled, delay, print_lock, interrupted_event
    )

    # 使用 Semaphore 限制并发
    sem = asyncio.Semaphore(concurrency)

    async def sem_task(req):
        async with sem:
            if interrupted_event.is_set():
                return None
            try:
                result = await process_single_fuzz_request(req, fuzz_progress)
                fuzz_progress.update(fuzz_task, advance=1)
                return result
            except Exception as e:
                logger.error(f"Fuzz task error: {e}")
                fuzz_progress.update(fuzz_task, advance=1)
                return None

    # 创建所有任务
    tasks = [asyncio.create_task(sem_task(req)) for req in all_fuzz_requests]

    try:
        # 等待所有任务完成
        for future in asyncio.as_completed(tasks):
            result = await future
            if result:
                fuzz_results.append(result)
                
                # 打印逻辑 (简化版，直接复用之前的逻辑)
                should_print = False
                fuzz_type = result.get('fuzz_type', 'normal')
                
                if config.get('debug', {}).get('enabled', False):
                    should_print = True
                elif fuzz_type == 'sql_fuzz':
                    if result.get('fuzz_analysis') and result['fuzz_analysis'].get('score', 0) > 0:
                        should_print = True
                elif fuzz_type in ['username_fuzz', 'password_fuzz', 'number_fuzz']:
                    if result.get('fuzz_analysis'):
                        analysis = result['fuzz_analysis']
                        if analysis.get('level') in ['possible', 'likely']:
                            should_print = True
                else:
                    should_print = True

                if should_print:
                    filter_status_codes = config.get('fuzz_detection', {}).get('filter_status_codes', [])
                    if filter_status_codes:
                        status_code = result.get('status_code', 0)
                        if status_code not in filter_status_codes:
                            should_print = False
                
                # 应用级别筛选
                if should_print and result.get('fuzz_analysis'):
                    level_filter = config.get('fuzz_detection', {}).get('level_filter', 'possible')
                    analysis_level = result['fuzz_analysis'].get('level', 'unlikely')
                    
                    if level_filter == 'likely':
                        # 只显示 likely
                        if analysis_level != 'likely':
                            should_print = False
                    elif level_filter == 'possible':
                        # 显示 possible 和 likely
                        if analysis_level not in ['possible', 'likely']:
                            should_print = False
                    # level_filter == 'all' 时显示所有

                if should_print:
                    # 使用 print_lock 保护打印
                    # 注意：在 async 中，如果 print_lock 是 threading.Lock，这里会阻塞 loop。
                    # 但为了简单起见和兼容 handlers.py，我们假设它没问题。
                    # 理想情况下应该用 asyncio.Lock，但 handlers.py 是共享的。
                    # 这里我们直接打印，因为 rich console 是线程安全的。
                    output = reporter.format_result(result)
                    fuzz_progress.console.print(output)

                    if result.get('fuzz_analysis'):
                        analysis = result['fuzz_analysis']
                        if analysis['level'] in ['likely', 'possible']:
                            detail = (
                                f"         {'':8} {'':10} {'':8} {'':7} "
                                f"[yellow]└─ {analysis['icon']} {analysis['label']} (评分: {analysis['score']}) "
                                f"原因: {', '.join(analysis['reasons'])}[/yellow]"
                            )
                            fuzz_progress.console.print(detail)

    except asyncio.CancelledError:
        console.print(f"\n[yellow]⚠️  Fuzz 测试被取消[/yellow]")
        raise
    finally:
        fuzz_progress.stop()

    return fuzz_results


async def execute_tests_async(config):
    """执行测试 (异步主函数)"""
    display_config(config)

    console.print(f"\n[yellow]⚙ 正在解析 API 文档...[/yellow]")
    api_parser = APIParser(config)
    apis = api_parser.parse()

    if not apis:
        console.print(f"[red]✗ 未找到任何 API 接口[/red]")
        sys.exit(1)

    console.print(f"[cyan]📄 API 文档路径:[/cyan] {config['target']['api_path']}")

    # 初始化模块
    request_builder = RequestBuilder(config)
    reporter = Reporter(config)
    fuzz_detector = FuzzDetector(config)
    
    fuzz_username_enabled = config.get('fuzz_username', {}).get('enabled', False)
    fuzz_password_enabled = config.get('fuzz_password', {}).get('enabled', False)
    fuzz_number_enabled = config.get('fuzz_number', {}).get('enabled', False)
    fuzz_sql_enabled = config.get('fuzz_sql', {}).get('enabled', False)
    
    sql_detector = SQLDetector(config) if fuzz_sql_enabled else None
    any_fuzz_enabled = fuzz_username_enabled or fuzz_password_enabled or fuzz_number_enabled or fuzz_sql_enabled

    total_normal_requests, total_enum_requests, has_enum_params = calculate_total_requests(apis, config)

    if has_enum_params:
        console.print(f"[green]✓ 成功解析 {len(apis)} 个 API 接口，enum参数生成 {total_enum_requests} 个请求，将生成 {total_normal_requests} 个测试请求[/green]")
    else:
        console.print(f"[green]✓ 成功解析 {len(apis)} 个 API 接口[/green]")

    console.print(f"\n[yellow]🚀 开始测试 API 接口 (AsyncIO 模式)...[/yellow]\n")

    results = []
    concurrency = config['request'].get('threads', 5) # 复用 threads 参数作为并发数
    delay = config['request'].get('delay', 0)
    api_status_map = {}
    
    # 打印锁 (虽然 rich 是线程安全的，但为了保持逻辑一致)
    # 在 asyncio 中，我们其实不需要 threading.Lock，但为了兼容 handlers.py 的接口
    import threading
    print_lock = threading.Lock()
    
    # 中断事件
    interrupted_event = asyncio.Event()

    # 进度条
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=False
    )
    progress.start()
    task = progress.add_task("[cyan]普通测试进度", total=total_normal_requests)

    # 初始化 RequestSender (使用 context manager)
    request_sender = RequestSender(config)
    
    try:
        async with request_sender:
            # 创建处理函数
            process_api_normal = create_normal_test_handler(
                config, request_builder, request_sender, reporter,
                fuzz_detector, any_fuzz_enabled, delay, progress, print_lock, api_status_map, interrupted_event
            )

            # ========== 第一阶段：普通测试 ==========
            console.print(f"[cyan]📍 阶段 1/2: 普通API测试[/cyan]\n")

            # 使用 Semaphore 限制并发
            sem = asyncio.Semaphore(concurrency)

            async def sem_task(api):
                async with sem:
                    if interrupted_event.is_set():
                        return []
                    try:
                        res = await process_api_normal(api)
                        progress.update(task, advance=len(res))
                        return res
                    except Exception as e:
                        logger.error(f"Task error: {e}")
                        progress.update(task, advance=1)
                        return []

            tasks = [asyncio.create_task(sem_task(api)) for api in apis]
            
            # 等待所有任务
            for future in asyncio.as_completed(tasks):
                api_results = await future
                results.extend(api_results)

            progress.stop()

            # ========== 第二阶段：Fuzz 测试 ==========
            if any_fuzz_enabled and not interrupted_event.is_set():
                fuzz_results = await execute_fuzz_tests_async(
                    config, apis, request_builder, request_sender, reporter,
                    fuzz_detector, sql_detector, any_fuzz_enabled,
                    concurrency, delay, api_status_map, print_lock, interrupted_event
                )
                results.extend(fuzz_results)

    except asyncio.CancelledError:
        console.print(f"\n[yellow]⚠️  任务被取消[/yellow]")
        interrupted_event.set()
    except Exception as e:
        console.print(f"[red]❌ 发生错误: {e}[/red]")
        import traceback
        traceback.print_exc()
    finally:
        progress.stop()
        # 确保 session 关闭 (context manager 会处理，但如果出错可能需要额外检查)
        await request_sender.close()

    # 生成报告
    if results:
        console.print(f"\n[yellow]📊 正在生成报告...[/yellow]")
        reporter.generate_html_report(results, apis)
        reporter.print_summary(results)
        
        console.print(f"\n[green]✓ 测试完成！报告已保存到: {reporter.output_dir / config['output']['html_report']}[/green]")
    else:
        console.print(f"\n[yellow]⚠️  没有收集到任何测试结果[/yellow]")


def execute_tests(config):
    """执行测试入口"""
    try:
        asyncio.run(execute_tests_async(config))
    except KeyboardInterrupt:
        console.print(f"\n[yellow]⚠️  用户中断测试[/yellow]")
        # 这里不需要做太多，因为 asyncio.run 会处理清理
    except Exception as e:
        console.print(f"[red]❌ 程序异常退出: {e}[/red]")
        sys.exit(1)
