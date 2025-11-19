#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
报告生成模块
生成 HTML 报告和终端输出
"""

from pathlib import Path
from rich.console import Console
from rich.table import Table
from modules.utils import format_size, format_time
import json
from datetime import datetime


console = Console()


class Reporter:
    """报告生成器"""
    
    def __init__(self, config):
        self.config = config

        # 生成唯一的输出目录：output/域名_时间戳/
        base_output_dir = Path(config['output']['output_dir'])

        # 从 base_url 提取域名
        from urllib.parse import urlparse
        target_url = config['target']['base_url']
        parsed = urlparse(target_url)
        domain = parsed.netloc.replace(':', '_')  # 替换冒号避免文件名问题

        # 生成时间戳
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # 创建唯一目录
        self.output_dir = base_output_dir / f"{domain}_{timestamp}"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.save_requests = config['output'].get('save_requests', True)
        self.save_responses = config['output'].get('save_responses', True)
        self.verbose = config['output'].get('verbose', False)
        self.use_color = config['output'].get('color', True)

        # 调试模式配置
        self.debug_config = config.get('debug', {})
        self.debug_enabled = self.debug_config.get('enabled', False)
    
    def format_result(self, result):
        """格式化单个结果为字符串"""
        status_code = result['status_code']
        response_length = result['response_length']
        response_time = result['response_time']
        method = result['method']
        url = result['url']

        # 获取描述和参数信息
        request_data = result['request']
        api = request_data.get('api', {})
        description = request_data.get('description', api.get('summary', api.get('description', '')))
        param_info = request_data.get('param_info', '')
        is_original = request_data.get('is_original', None)

        # 根据状态码选择颜色 - 移除 [ERR]，统一显示状态码
        if status_code == 0:
            status_color = 'red'
            status_text = f'[{status_code}]'
        elif status_code < 300:
            status_color = 'green'
            status_text = f'[{status_code}]'
        elif status_code < 400:
            status_color = 'yellow'
            status_text = f'[{status_code}]'
        elif status_code < 500:
            status_color = 'yellow'
            status_text = f'[{status_code}]'
        else:
            status_color = 'red'
            status_text = f'[{status_code}]'

        # Fuzz 类型标记
        fuzz_type = request_data.get('fuzz_type', 'normal')
        fuzz_mark = ''
        if fuzz_type == 'parameter_fuzz':
            fuzz_mark = '[cyan][PARAM][/cyan] '
        elif fuzz_type == 'attack_fuzz':
            fuzz_mark = '[red][ATTACK][/red] '
        elif fuzz_type == 'username_fuzz':
            fuzz_mark = '[magenta][USER-FUZZ][/magenta] '
        elif fuzz_type == 'password_fuzz':
            fuzz_mark = '[magenta][PASS-FUZZ][/magenta] '
        elif fuzz_type == 'number_fuzz':
            fuzz_mark = '[cyan][NUM-FUZZ][/cyan] '
        elif fuzz_type == 'sql_fuzz':
            fuzz_mark = '[red][SQL-FUZZ][/red] '

        # 双重检查标记
        if is_original is True:
            fuzz_mark += '[magenta][原始][/magenta] '
        elif is_original is False and fuzz_type == 'normal':
            fuzz_mark += '[yellow][+参数][/yellow] '

        # 基础输出
        output = (
            f"{fuzz_mark}[{status_color}]{status_text:8}[/{status_color}] "
            f"{format_size(response_length):>10} "
            f"{format_time(response_time):>8} "
            f"[cyan]{method:7}[/cyan] "
            f"[blue]{url}[/blue] "
            f"[dim]{description}[/dim]"
        )

        # 如果有参数拼接信息，在下一行显示
        if param_info:
            output += f"\n         {'':8} {'':10} {'':8} {'':7} [yellow]└─ {param_info}[/yellow]"

        # 调试模式：显示详细的请求和响应信息
        if self.debug_enabled and self.debug_config.get('verbose', False):
            output += self._format_debug_info(result)

        return output

    def _format_debug_info(self, result):
        """格式化调试信息"""
        import json
        debug_output = []

        # 请求详情
        request_data = result['request']
        debug_output.append(f"\n         {'':8} {'':10} {'':8} {'':7} [dim cyan]┌─ 🔍 调试信息[/dim cyan]")

        # 显示请求参数
        if request_data.get('params'):
            params_str = ', '.join([f"{k}={v}" for k, v in request_data['params'].items()])
            debug_output.append(f"         {'':8} {'':10} {'':8} {'':7} [dim cyan]│  📋 查询参数: {params_str}[/dim cyan]")

        # 显示请求体
        if request_data.get('body'):
            body = request_data['body']
            if isinstance(body, dict):
                body_str = json.dumps(body, ensure_ascii=False, indent=2)
                # 限制显示长度
                if len(body_str) > 200:
                    body_str = body_str[:200] + '...'
                body_str = body_str.replace('\n', '\n         ' + ' '*8 + ' '*10 + ' '*8 + ' '*7 + '│    ')
                debug_output.append(f"         {'':8} {'':10} {'':8} {'':7} [dim cyan]│  📦 请求体:[/dim cyan]")
                debug_output.append(f"         {'':8} {'':10} {'':8} {'':7} [dim cyan]│    {body_str}[/dim cyan]")
            else:
                body_str = str(body)[:200]
                debug_output.append(f"         {'':8} {'':10} {'':8} {'':7} [dim cyan]│  📦 请求体: {body_str}[/dim cyan]")

        # 显示响应体（部分）
        response_body = result.get('response_body', '')
        if response_body:
            if isinstance(response_body, dict):
                body_str = json.dumps(response_body, ensure_ascii=False, indent=2)
            else:
                body_str = str(response_body)

            # 限制显示长度
            if len(body_str) > 300:
                body_str = body_str[:300] + '...'

            # 处理多行显示
            body_lines = body_str.split('\n')
            debug_output.append(f"         {'':8} {'':10} {'':8} {'':7} [dim cyan]│  📥 响应体:[/dim cyan]")
            for line in body_lines[:5]:  # 最多显示5行
                debug_output.append(f"         {'':8} {'':10} {'':8} {'':7} [dim cyan]│    {line}[/dim cyan]")
            if len(body_lines) > 5:
                debug_output.append(f"         {'':8} {'':10} {'':8} {'':7} [dim cyan]│    ...[/dim cyan]")

        # 显示响应头（关键信息）
        response_headers = result.get('response_headers', {})
        if response_headers:
            key_headers = ['Content-Type', 'Set-Cookie', 'Location', 'Server']
            shown_headers = {k: v for k, v in response_headers.items() if k in key_headers}
            if shown_headers:
                debug_output.append(f"         {'':8} {'':10} {'':8} {'':7} [dim cyan]│  📋 关键响应头:[/dim cyan]")
                for k, v in shown_headers.items():
                    v_str = str(v)[:100]
                    debug_output.append(f"         {'':8} {'':10} {'':8} {'':7} [dim cyan]│    {k}: {v_str}[/dim cyan]")

        debug_output.append(f"         {'':8} {'':10} {'':8} {'':7} [dim cyan]└─────────────────[/dim cyan]")

        return '\n'.join(debug_output)

    def print_result(self, result):
        """打印单个结果"""
        console.print(self.format_result(result))
    
    def print_summary(self, results):
        """打印统计摘要"""
        total = len(results)
        success = sum(1 for r in results if r['success'])
        failed = total - success
        
        # 统计状态码
        status_codes = {}
        for result in results:
            code = result['status_code']
            status_codes[code] = status_codes.get(code, 0) + 1
        
        # 统计 Fuzz 类型
        fuzz_types = {}
        for result in results:
            fuzz_type = result['request'].get('fuzz_type', 'normal')
            fuzz_types[fuzz_type] = fuzz_types.get(fuzz_type, 0) + 1
        
        console.print("\n" + "="*80)
        console.print("[bold cyan]📊 测试统计[/bold cyan]\n")
        
        console.print(f"[green]✓ 总请求数:[/green] {total}")
        console.print(f"[green]✓ 成功:[/green] {success}")
        console.print(f"[red]✗ 失败:[/red] {failed}")
        
        console.print(f"\n[cyan]状态码分布:[/cyan]")
        for code, count in sorted(status_codes.items()):
            console.print(f"  [{code}]: {count}")
        
        console.print(f"\n[cyan]测试类型分布:[/cyan]")
        for fuzz_type, count in fuzz_types.items():
            type_name = {
                'normal': '正常请求',
                'parameter_fuzz': '参数Fuzz',
                'attack_fuzz': '攻击Fuzz',
                'username_fuzz': '用户名Fuzz',
                'password_fuzz': '密码Fuzz',
                'number_fuzz': '数字Fuzz',
                'sql_fuzz': 'SQL注入Fuzz'
            }.get(fuzz_type, fuzz_type)
            console.print(f"  {type_name}: {count}")

        # 统计 Fuzz 分析结果
        fuzz_analysis_results = {
            'likely': 0,
            'possible': 0,
            'unlikely': 0
        }
        fuzz_findings = []

        for result in results:
            if result.get('fuzz_analysis'):
                analysis = result['fuzz_analysis']
                level = analysis.get('level', 'unlikely')
                fuzz_analysis_results[level] = fuzz_analysis_results.get(level, 0) + 1

                # 收集高价值发现
                if level in ['likely', 'possible']:
                    request_data = result['request']
                    fuzz_findings.append({
                        'level': level,
                        'label': analysis['label'],
                        'icon': analysis['icon'],
                        'fuzz_target': analysis.get('fuzz_target', request_data.get('fuzz_target', 'unknown')),
                        'fuzz_value': analysis.get('fuzz_value', request_data.get('fuzz_value', 'unknown')),
                        'score': analysis.get('score', 0),
                        'url': result['url'],
                        'status_code': result['status_code'],
                        'fuzz_type': request_data.get('fuzz_type', 'unknown'),
                        'reasons': analysis.get('reasons', [])
                    })

        # 如果有 Fuzz 分析结果，显示统计
        if any(fuzz_analysis_results.values()):
            console.print(f"\n[cyan]Fuzz 检测结果:[/cyan]")
            console.print(f"  🎯 高度可疑: {fuzz_analysis_results['likely']}")
            console.print(f"  ⚠️  可能有效: {fuzz_analysis_results['possible']}")
            console.print(f"  ❌ 可能无效: {fuzz_analysis_results['unlikely']}")

            # 显示高价值发现
            if fuzz_findings:
                console.print(f"\n[yellow bold]🔍 高价值发现:[/yellow bold]")
                for finding in fuzz_findings[:10]:  # 最多显示10个
                    fuzz_type_name = {
                        'username_fuzz': '用户名',
                        'password_fuzz': '密码',
                        'number_fuzz': '数字',
                        'sql_fuzz': 'SQL注入'
                    }.get(finding['fuzz_type'], finding['fuzz_type'])

                    reasons_str = ', '.join(finding['reasons']) if finding['reasons'] else ''
                    console.print(
                        f"  {finding['icon']} [{finding['status_code']}] "
                        f"[{fuzz_type_name}] {finding['fuzz_target']}={finding['fuzz_value']} "
                        f"(评分: {finding['score']})"
                    )
                    if reasons_str:
                        console.print(f"      原因: {reasons_str}")
                    console.print(f"      URL: {finding['url']}")
                if len(fuzz_findings) > 10:
                    console.print(f"  ... 还有 {len(fuzz_findings) - 10} 个发现，详见报告")

        console.print("="*80 + "\n")
    
    def generate_html_report(self, results, apis):
        """生成 HTML 报告"""
        html_file = self.output_dir / self.config['output']['html_report']

        # 生成 HTML
        html_content = self._generate_html(results, apis)

        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

        # 保存请求/响应包
        if self.save_requests or self.save_responses:
            self._save_raw_data(results)

        # 生成 CSV 和 JSON 报告
        self._generate_csv_report(results)
        self._generate_json_report(results)
    
    def _generate_html(self, results, apis):
        """生成 HTML 内容"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>API Fuzz 测试报告</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }}

        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}

        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}

        .header p {{
            font-size: 1.1em;
            opacity: 0.9;
        }}

        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 30px;
            background: #f8f9fa;
        }}

        .summary-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            text-align: center;
        }}

        .summary-card h3 {{
            color: #666;
            font-size: 0.9em;
            margin-bottom: 10px;
            text-transform: uppercase;
        }}

        .summary-card .value {{
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }}

        .content {{
            padding: 30px;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}

        th {{
            background: #667eea;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}

        td {{
            padding: 12px;
            border-bottom: 1px solid #eee;
        }}

        tr:hover {{
            background: #f8f9fa;
        }}

        .status-200 {{ color: #28a745; font-weight: bold; }}
        .status-300 {{ color: #ffc107; font-weight: bold; }}
        .status-400 {{ color: #fd7e14; font-weight: bold; }}
        .status-500 {{ color: #dc3545; font-weight: bold; }}
        .status-error {{ color: #6c757d; font-weight: bold; }}

        .method {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.85em;
            font-weight: bold;
        }}

        .method-GET {{ background: #d1ecf1; color: #0c5460; }}
        .method-POST {{ background: #d4edda; color: #155724; }}
        .method-PUT {{ background: #fff3cd; color: #856404; }}
        .method-DELETE {{ background: #f8d7da; color: #721c24; }}

        .fuzz-badge {{
            display: inline-block;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 0.75em;
            margin-left: 5px;
        }}

        .fuzz-param {{ background: #17a2b8; color: white; }}
        .fuzz-attack {{ background: #dc3545; color: white; }}
        .fuzz-username {{ background: #e83e8c; color: white; }}
        .badge-original {{ background: #6f42c1; color: white; }}
        .badge-with-params {{ background: #fd7e14; color: white; }}

        .param-info {{
            display: block;
            margin-top: 5px;
            padding: 8px;
            background: #fff3cd;
            border-left: 3px solid #ffc107;
            font-size: 0.85em;
            color: #856404;
            border-radius: 3px;
        }}

        .param-info strong {{
            color: #664d03;
        }}

        /* 详情面板 - 侧边滑出式 */
        .details-panel {{
            position: fixed;
            top: 0;
            right: -60%;
            width: 60%;
            height: 100vh;
            background: white;
            box-shadow: -5px 0 20px rgba(0,0,0,0.3);
            z-index: 1000;
            transition: right 0.3s ease;
            overflow-y: auto;
        }}

        .details-panel.show {{
            right: 0;
        }}

        .details-panel-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100vh;
            background: rgba(0,0,0,0.5);
            z-index: 999;
            display: none;
        }}

        .details-panel-overlay.show {{
            display: block;
        }}

        .details-panel-header {{
            position: sticky;
            top: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            z-index: 10;
        }}

        .details-panel-header h3 {{
            margin: 0;
            font-size: 1.3em;
        }}

        .details-panel-close {{
            background: rgba(255,255,255,0.2);
            border: none;
            color: white;
            font-size: 24px;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            cursor: pointer;
            transition: all 0.3s;
        }}

        .details-panel-close:hover {{
            background: rgba(255,255,255,0.3);
            transform: rotate(90deg);
        }}

        .details-panel-content {{
            padding: 30px;
        }}

        .details-section {{
            margin-bottom: 30px;
        }}

        .details-section h4 {{
            color: #667eea;
            font-size: 1.2em;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }}

        .details-section pre {{
            background: #2d2d2d;
            color: #f8f8f2;
            padding: 20px;
            border-radius: 8px;
            overflow: auto;
            max-height: 400px;
            white-space: pre;
            font-family: 'Courier New', Courier, monospace;
            font-size: 0.9em;
            border: 2px solid #444;
            line-height: 1.5;
        }}

        /* 滚动条样式 */
        .details-section pre::-webkit-scrollbar,
        .details-panel::-webkit-scrollbar {{
            width: 12px;
            height: 12px;
        }}

        .details-section pre::-webkit-scrollbar-track,
        .details-panel::-webkit-scrollbar-track {{
            background: #1a1a1a;
            border-radius: 5px;
        }}

        .details-section pre::-webkit-scrollbar-thumb,
        .details-panel::-webkit-scrollbar-thumb {{
            background: #667eea;
            border-radius: 5px;
            border: 2px solid #1a1a1a;
        }}

        .details-section pre::-webkit-scrollbar-thumb:hover,
        .details-panel::-webkit-scrollbar-thumb:hover {{
            background: #5568d3;
        }}

        .toggle-btn {{
            background: #667eea;
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.85em;
        }}

        .toggle-btn:hover {{
            background: #5568d3;
        }}

        .search-box {{
            margin: 20px 0;
            display: flex;
            gap: 10px;
            align-items: center;
        }}

        .search-box input {{
            flex: 1;
            padding: 10px;
            border: 2px solid #ddd;
            border-radius: 5px;
            font-size: 1em;
        }}

        .search-box input:focus {{
            outline: none;
            border-color: #667eea;
        }}

        .search-box button {{
            padding: 10px 20px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 1em;
        }}

        .search-box button:hover {{
            background: #5568d3;
        }}

        .pagination {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 10px;
            margin: 20px 0;
            padding: 20px;
        }}

        .pagination button {{
            padding: 8px 16px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
        }}

        .pagination button:hover {{
            background: #5568d3;
        }}

        .pagination button:disabled {{
            background: #ccc;
            cursor: not-allowed;
        }}

        .pagination span {{
            font-size: 1em;
            color: #666;
        }}

        .export-buttons {{
            display: flex;
            gap: 10px;
            margin: 20px 0;
        }}

        .export-btn {{
            padding: 8px 16px;
            background: #28a745;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 0.9em;
        }}

        .export-btn:hover {{
            background: #218838;
        }}

        tr.hidden {{
            display: none !important;
        }}

        tr.details-row.hidden {{
            display: none !important;
        }}

        tr.details-row:not(.hidden) {{
            display: table-row;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 API Fuzz 测试报告</h1>
            <p>生成时间: {timestamp}</p>
        </div>

        <div class="summary">
            <div class="summary-card">
                <h3>总请求数</h3>
                <div class="value">{len(results)}</div>
            </div>
            <div class="summary-card">
                <h3>成功</h3>
                <div class="value" style="color: #28a745;">{sum(1 for r in results if r['success'])}</div>
            </div>
            <div class="summary-card">
                <h3>失败</h3>
                <div class="value" style="color: #dc3545;">{sum(1 for r in results if not r['success'])}</div>
            </div>
            <div class="summary-card">
                <h3>API 接口数</h3>
                <div class="value">{len(apis)}</div>
            </div>
        </div>

        <div class="content">
            <h2>📋 测试结果详情</h2>

            <div class="export-buttons">
                <button class="export-btn" onclick="exportToCSV()">📥 导出 CSV</button>
                <button class="export-btn" onclick="exportToJSON()">📥 导出 JSON</button>
            </div>

            <div class="search-box">
                <input type="text" id="searchInput" placeholder="搜索 URL、状态码、描述..." onkeyup="searchTable()">
                <button onclick="searchTable()">🔍 搜索</button>
                <button onclick="clearSearch()">✖ 清除</button>
            </div>

            <div class="pagination">
                <button onclick="previousPage()" id="prevBtn">← 上一页</button>
                <span id="pageInfo">第 1 页</span>
                <button onclick="nextPage()" id="nextBtn">下一页 →</button>
                <select id="pageSizeSelect" onchange="changePageSize()">
                    <option value="10">每页 10 条</option>
                    <option value="20" selected>每页 20 条</option>
                    <option value="50">每页 50 条</option>
                    <option value="100">每页 100 条</option>
                    <option value="-1">显示全部</option>
                </select>
            </div>

            <table id="resultsTable">
                <thead>
                    <tr>
                        <th>状态码</th>
                        <th>响应长度</th>
                        <th>响应时间</th>
                        <th>方法</th>
                        <th>URL</th>
                        <th>描述</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody id="tableBody">
"""

        # 添加表格行
        for idx, result in enumerate(results):
            status_code = result['status_code']

            # 状态码样式
            if status_code == 0:
                status_class = 'status-error'
            elif status_code < 300:
                status_class = 'status-200'
            elif status_code < 400:
                status_class = 'status-300'
            elif status_code < 500:
                status_class = 'status-400'
            else:
                status_class = 'status-500'

            method = result['method']
            url = result['url']
            response_length = format_size(result['response_length'])
            response_time = format_time(result['response_time'])

            request_data = result['request']
            api = request_data.get('api', {})
            description = request_data.get('description', api.get('summary', api.get('description', '')))

            # 获取参数信息
            param_info = request_data.get('param_info', '')
            is_original = request_data.get('is_original', None)

            fuzz_type = request_data.get('fuzz_type', 'normal')
            fuzz_badge = ''
            if fuzz_type == 'parameter_fuzz':
                fuzz_badge = '<span class="fuzz-badge fuzz-param">PARAM</span>'
            elif fuzz_type == 'attack_fuzz':
                fuzz_badge = '<span class="fuzz-badge fuzz-attack">ATTACK</span>'
            elif fuzz_type == 'username_fuzz':
                fuzz_badge = '<span class="fuzz-badge fuzz-username">USER-FUZZ</span>'

            # 双重检查标记
            if is_original is True:
                fuzz_badge += '<span class="fuzz-badge badge-original">原始</span>'
            elif is_original is False and fuzz_type != 'username_fuzz':
                fuzz_badge += '<span class="fuzz-badge badge-with-params">+参数</span>'

            # 构建描述（包含参数信息）
            description_html = self._escape_html(description)
            if param_info:
                description_html += f'<div class="param-info"><strong>📝 参数详情:</strong> {self._escape_html(param_info)}</div>'

            # 转义详情数据用于 data 属性
            details_data = {
                'request': result['raw_request'],
                'headers': self._format_headers(result.get('response_headers', {})),
                'response': result['raw_response'],
                'url': url,
                'method': method,
                'status': status_code
            }

            import json
            details_json = json.dumps(details_data).replace("'", "&#39;").replace('"', '&quot;')

            html += f"""
                    <tr data-details='{details_json}'>
                        <td class="{status_class}">[{status_code if status_code > 0 else 'ERR'}]</td>
                        <td>{response_length}</td>
                        <td>{response_time}</td>
                        <td><span class="method method-{method}">{method}</span>{fuzz_badge}</td>
                        <td style="word-break: break-all;">{self._escape_html(url)}</td>
                        <td>{description_html}</td>
                        <td><button class="toggle-btn" onclick="showDetails(this)">查看详情</button></td>
                    </tr>
"""

        html += """
                </tbody>
            </table>
        </div>
    </div>

    <!-- 详情面板 -->
    <div class="details-panel-overlay" id="detailsOverlay" onclick="closeDetailsPanel()"></div>
    <div class="details-panel" id="detailsPanel">
        <div class="details-panel-header">
            <h3 id="detailsTitle">请求详情</h3>
            <button class="details-panel-close" onclick="closeDetailsPanel()">×</button>
        </div>
        <div class="details-panel-content">
            <div class="details-section">
                <h4>📤 请求包</h4>
                <pre id="detailsRequest"></pre>
            </div>
            <div class="details-section">
                <h4>📊 响应头</h4>
                <pre id="detailsHeaders"></pre>
            </div>
            <div class="details-section">
                <h4>📥 响应包 (完整)</h4>
                <pre id="detailsResponse"></pre>
            </div>
        </div>
    </div>

    <script>
        let currentPage = 1;
        let pageSize = 20;
        let allRows = [];
        let filteredRows = [];

        // 初始化
        document.addEventListener('DOMContentLoaded', function() {
            const tbody = document.getElementById('tableBody');
            allRows = Array.from(tbody.querySelectorAll('tr'));
            filteredRows = [...allRows];
            updatePagination();
        });

        // 显示详情面板
        function showDetails(btn) {
            const row = btn.closest('tr');
            const detailsData = JSON.parse(row.getAttribute('data-details'));

            // 更新面板内容
            document.getElementById('detailsTitle').textContent = `${detailsData.method} - [${detailsData.status}]`;
            document.getElementById('detailsRequest').textContent = detailsData.request;
            document.getElementById('detailsHeaders').textContent = detailsData.headers;
            document.getElementById('detailsResponse').textContent = detailsData.response;

            // 显示面板
            document.getElementById('detailsPanel').classList.add('show');
            document.getElementById('detailsOverlay').classList.add('show');
            document.body.style.overflow = 'hidden'; // 禁止背景滚动
        }

        // 关闭详情面板
        function closeDetailsPanel() {
            document.getElementById('detailsPanel').classList.remove('show');
            document.getElementById('detailsOverlay').classList.remove('show');
            document.body.style.overflow = ''; // 恢复滚动
        }

        // ESC 键关闭面板
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                closeDetailsPanel();
            }
        });

        function searchTable() {
            const input = document.getElementById('searchInput').value.toLowerCase();

            filteredRows = [];

            allRows.forEach(row => {
                const text = row.textContent.toLowerCase();

                if (text.includes(input)) {
                    filteredRows.push(row);
                }
            });

            currentPage = 1;
            updatePagination();
        }

        function clearSearch() {
            document.getElementById('searchInput').value = '';
            filteredRows = [...allRows];
            currentPage = 1;
            updatePagination();
        }

        function updatePagination() {
            const tbody = document.getElementById('tableBody');
            const allTableRows = Array.from(tbody.getElementsByTagName('tr'));

            // 隐藏所有行
            allTableRows.forEach(row => row.classList.add('hidden'));

            // 计算分页
            const totalPages = pageSize === -1 ? 1 : Math.ceil(filteredRows.length / pageSize);
            const start = pageSize === -1 ? 0 : (currentPage - 1) * pageSize;
            const end = pageSize === -1 ? filteredRows.length : start + pageSize;

            // 显示当前页的行
            for (let i = start; i < end && i < filteredRows.length; i++) {
                filteredRows[i].classList.remove('hidden');
            }

            // 更新分页信息
            document.getElementById('pageInfo').textContent =
                pageSize === -1 ? `显示全部 (${filteredRows.length} 条)` :
                `第 ${currentPage} / ${totalPages} 页 (共 ${filteredRows.length} 条)`;

            // 更新按钮状态
            document.getElementById('prevBtn').disabled = currentPage === 1;
            document.getElementById('nextBtn').disabled = currentPage >= totalPages || pageSize === -1;
        }

        function previousPage() {
            if (currentPage > 1) {
                currentPage--;
                updatePagination();
            }
        }

        function nextPage() {
            const totalPages = Math.ceil(filteredRows.length / pageSize);
            if (currentPage < totalPages) {
                currentPage++;
                updatePagination();
            }
        }

        function changePageSize() {
            pageSize = parseInt(document.getElementById('pageSizeSelect').value);
            currentPage = 1;
            updatePagination();
        }

        function exportToCSV() {
            const rows = [['状态码', '响应长度', '响应时间', '方法', 'URL', '描述']];

            filteredRows.forEach(row => {
                const cells = row.getElementsByTagName('td');
                const rowData = [
                    cells[0].textContent.trim(),
                    cells[1].textContent.trim(),
                    cells[2].textContent.trim(),
                    cells[3].textContent.trim().split('\\n')[0],
                    cells[4].textContent.trim(),
                    cells[5].textContent.trim().replace(/\\n/g, ' ')
                ];
                rows.push(rowData);
            });

            const csv = rows.map(row => row.map(cell => `"${cell}"`).join(',')).join('\\n');
            const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = 'api_fuzz_report.csv';
            link.click();
        }

        function exportToJSON() {
            const data = [];

            filteredRows.forEach(row => {
                const cells = row.getElementsByTagName('td');
                data.push({
                    status_code: cells[0].textContent.trim(),
                    response_length: cells[1].textContent.trim(),
                    response_time: cells[2].textContent.trim(),
                    method: cells[3].textContent.trim().split('\\n')[0],
                    url: cells[4].textContent.trim(),
                    description: cells[5].textContent.trim()
                });
            });

            const json = JSON.stringify(data, null, 2);
            const blob = new Blob([json], { type: 'application/json' });
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = 'api_fuzz_report.json';
            link.click();
        }
    </script>
</body>
</html>
"""

        return html

    def _escape_html(self, text):
        """转义 HTML 特殊字符"""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#39;'))

    def _format_headers(self, headers):
        """格式化响应头"""
        if not headers:
            return ''
        return '\n'.join([f'{k}: {v}' for k, v in headers.items()])
    
    def _save_raw_data(self, results):
        """保存原始请求/响应数据"""
        raw_dir = self.output_dir / 'raw'
        raw_dir.mkdir(exist_ok=True)

        for idx, result in enumerate(results):
            if self.save_requests:
                req_file = raw_dir / f'request_{idx+1}.txt'
                with open(req_file, 'w', encoding='utf-8') as f:
                    f.write(result['raw_request'])

            if self.save_responses:
                resp_file = raw_dir / f'response_{idx+1}.txt'
                with open(resp_file, 'w', encoding='utf-8') as f:
                    f.write(result['raw_response'])

    def _generate_csv_report(self, results):
        """生成 CSV 报告"""
        import csv

        csv_file = self.output_dir / 'report.csv'

        with open(csv_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)

            # 写入表头
            writer.writerow([
                '状态码', '响应长度', '响应时间(ms)', '方法', 'URL',
                '描述', '是否成功', '参数信息', 'Fuzz类型', '请求包', '响应包'
            ])

            # 写入数据
            for result in results:
                request_data = result['request']
                api = request_data.get('api', {})
                description = request_data.get('description', api.get('summary', ''))
                param_info = request_data.get('param_info', '')
                fuzz_type = request_data.get('fuzz_type', 'normal')

                writer.writerow([
                    result['status_code'],
                    result['response_length'],
                    int(result['response_time'] * 1000),
                    result['method'],
                    result['url'],
                    description,
                    '是' if result['success'] else '否',
                    param_info,
                    fuzz_type,
                    result['raw_request'],
                    result['raw_response']
                ])

    def _generate_json_report(self, results):
        """生成 JSON 报告"""
        import json

        json_file = self.output_dir / 'report.json'

        # 构造 JSON 数据
        data = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total': len(results),
            'success': sum(1 for r in results if r['success']),
            'failed': sum(1 for r in results if not r['success']),
            'results': []
        }

        for result in results:
            request_data = result['request']
            api = request_data.get('api', {})

            data['results'].append({
                'status_code': result['status_code'],
                'response_length': result['response_length'],
                'response_time': result['response_time'],
                'method': result['method'],
                'url': result['url'],
                'description': request_data.get('description', api.get('summary', '')),
                'param_info': request_data.get('param_info', ''),
                'is_original': request_data.get('is_original'),
                'fuzz_type': request_data.get('fuzz_type', 'normal'),
                'success': result['success'],
                'error': result.get('error', ''),
                'raw_request': result['raw_request'],
                'raw_response': result['raw_response'],
                'response_headers': result.get('response_headers', {}),
                'response_body': result.get('response_body', '')
            })

        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

