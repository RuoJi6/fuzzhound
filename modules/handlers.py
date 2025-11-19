#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试处理器模块
包含普通测试和 Fuzz 测试的处理函数
"""

import time
import logging

logger = logging.getLogger('fuzzhound')


def create_normal_test_handler(config, request_builder, request_sender, reporter,
                               fuzz_detector, any_fuzz_enabled, delay, progress, print_lock, api_status_map):
    """创建普通测试处理函数

    Args:
        config: 配置字典
        request_builder: 请求构建器
        request_sender: 请求发送器
        reporter: 报告器
        fuzz_detector: Fuzz 检测器
        any_fuzz_enabled: 是否启用了任何 Fuzz
        delay: 请求延迟
        progress: 进度条对象
        print_lock: 打印锁
        api_status_map: API 状态码映射字典

    Returns:
        function: 处理函数
    """
    def process_api_normal(api):
        """处理单个 API 的普通测试（线程安全）"""
        api_results = []
        double_check = config['request'].get('double_check', True)

        # 生成 API 的唯一标识
        api_key = f"{api.get('method', 'GET')}:{api.get('path', '')}"

        try:
            # 检查是否在黑名单中
            blacklist_config = config.get('blacklist', {})
            ignore_blacklist = blacklist_config.get('ignore_blacklist', False)

            if api.get('is_blacklisted', False) and not ignore_blacklist:
                # 黑名单 API 不发送请求，只显示提示
                with print_lock:
                    method = api.get('method', 'GET')
                    path = api.get('path', '')
                    summary = api.get('summary', '') or api.get('description', '')
                    full_url = config['target']['base_url'].rstrip('/') + path

                    # 格式化黑名单输出
                    blacklist_output = (
                        f"[red bold][!!!][/red bold] "
                        f"[black on yellow bold] 黑名单 [/black on yellow bold] "
                        f"[red]{method:7}[/red] "
                        f"[dim]{full_url}[/dim] "
                        f"[yellow]{summary}[/yellow]"
                    )
                    progress.console.print(blacklist_output)

                return api_results

            # 构造普通请求（不包含Fuzz）
            requests_list = request_builder.build(api, double_check=double_check)

            # 发送请求
            for idx, req in enumerate(requests_list):
                # 请求延迟
                if delay > 0:
                    time.sleep(delay)

                result = request_sender.send(req)
                api_results.append(result)

                # 设置基准响应（使用第一个正常请求作为基准，供后续Fuzz使用）
                if any_fuzz_enabled and idx == 0:
                    baseline_key = fuzz_detector.get_api_key(result)
                    fuzz_detector.set_baseline(baseline_key, result)

                # 记录第一个请求的状态码（用于 Fuzz 前置筛选）
                if idx == 0:
                    api_status_map[api_key] = result.get('status_code', 0)

                # 线程安全地打印结果
                with print_lock:
                    output = reporter.format_result(result)
                    progress.console.print(output)

        except Exception as e:
            logger.error(f"处理 API {api.get('path', 'unknown')} 时出错: {e}")

        return api_results
    
    return process_api_normal


def create_fuzz_test_handler(config, request_sender, reporter, fuzz_detector, 
                             sql_detector, any_fuzz_enabled, delay, print_lock):
    """创建 Fuzz 测试处理函数
    
    Args:
        config: 配置字典
        request_sender: 请求发送器
        reporter: 报告器
        fuzz_detector: Fuzz 检测器
        sql_detector: SQL 检测器
        any_fuzz_enabled: 是否启用了任何 Fuzz
        delay: 请求延迟
        print_lock: 打印锁
        
    Returns:
        function: 处理函数
    """
    def process_single_fuzz_request(req, fuzz_progress_obj):
        """处理单个 Fuzz 请求（线程安全）"""
        try:
            # 请求延迟
            if delay > 0:
                time.sleep(delay)

            result = request_sender.send(req)

            # 分析 Fuzz 结果（所有类型的Fuzz都使用相同的检测逻辑）
            fuzz_type = req.get('fuzz_type', 'normal')

            # SQL注入检测
            if fuzz_type == 'sql_fuzz' and sql_detector:
                # 获取基线响应
                api_key = fuzz_detector.get_api_key(result)
                baseline = fuzz_detector.get_baseline(api_key)

                # 检测SQL错误
                response_body = result.get('response_body', '')
                # 确保 response_body 是字符串
                if not isinstance(response_body, str):
                    response_body = str(response_body) if response_body is not None else ''
                has_sql_error, matched_errors = sql_detector.detect_sql_error(response_body)

                # 分析响应差异
                diff_result = {}
                if baseline:
                    diff_result = sql_detector.analyze_response_diff(baseline, result)

                # 计算风险评分
                detection_result = {
                    'has_sql_error': has_sql_error,
                    'matched_errors': matched_errors,
                    'diff_result': diff_result
                }
                risk_score = sql_detector.calculate_risk_score(detection_result)

                # 如果检测到SQL注入迹象，添加分析结果
                if risk_score > 0:
                    result['fuzz_analysis'] = {
                        'level': 'likely' if risk_score >= 50 else 'possible',
                        'icon': '🚨' if risk_score >= 50 else '⚠️',
                        'label': 'SQL注入漏洞' if risk_score >= 50 else '可能存在SQL注入',
                        'score': risk_score,
                        'reasons': []
                    }

                    # 添加检测原因
                    if has_sql_error:
                        result['fuzz_analysis']['reasons'].append(f'检测到SQL错误 ({len(matched_errors)}个特征)')
                    if diff_result.get('significant_diff'):
                        result['fuzz_analysis']['reasons'].append(f'响应长度差异 ({diff_result.get("length_diff", 0)}字节)')
                    if diff_result.get('status_code_diff'):
                        result['fuzz_analysis']['reasons'].append('状态码变化')

            # 其他类型的Fuzz检测
            elif any_fuzz_enabled and fuzz_type in ['username_fuzz', 'password_fuzz', 'number_fuzz']:
                analysis = fuzz_detector.analyze_fuzz_result(result)
                if analysis:
                    result['fuzz_analysis'] = analysis

            return result

        except Exception as e:
            logger.error(f"处理 Fuzz 请求时出错: {e}")
            return None
    
    return process_single_fuzz_request

