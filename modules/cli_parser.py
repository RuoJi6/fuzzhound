#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
命令行参数解析模块
"""

import argparse


class ColoredHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """自定义帮助格式化器，添加颜色支持"""

    # ANSI 颜色代码
    COLORS = {
        'CYAN': '\033[96m',
        'GREEN': '\033[92m',
        'YELLOW': '\033[93m',
        'BLUE': '\033[94m',
        'MAGENTA': '\033[95m',
        'RED': '\033[91m',
        'BOLD': '\033[1m',
        'UNDERLINE': '\033[4m',
        'END': '\033[0m'
    }

    def _format_usage(self, usage, actions, groups, prefix):
        """格式化 usage 行"""
        if prefix is None:
            prefix = f"{self.COLORS['YELLOW']}usage:{self.COLORS['END']} "
        return super()._format_usage(usage, actions, groups, prefix)

    def _format_action(self, action):
        """格式化每个参数"""
        # 获取原始格式化结果
        result = super()._format_action(action)

        # 为参数选项添加颜色
        if action.option_strings:
            # 短选项和长选项
            for opt in action.option_strings:
                colored_opt = f"{self.COLORS['GREEN']}{opt}{self.COLORS['END']}"
                result = result.replace(opt, colored_opt, 1)

        return result

    def start_section(self, heading):
        """格式化分组标题"""
        if heading:
            # 为不同的分组添加不同的颜色
            if '🎯' in heading:
                colored_heading = f"{self.COLORS['CYAN']}{self.COLORS['BOLD']}{heading}{self.COLORS['END']}"
            elif '⚡' in heading:
                colored_heading = f"{self.COLORS['YELLOW']}{self.COLORS['BOLD']}{heading}{self.COLORS['END']}"
            elif '💥' in heading:
                colored_heading = f"{self.COLORS['RED']}{self.COLORS['BOLD']}{heading}{self.COLORS['END']}"
            elif '🔧' in heading:
                colored_heading = f"{self.COLORS['BLUE']}{self.COLORS['BOLD']}{heading}{self.COLORS['END']}"
            else:
                colored_heading = f"{self.COLORS['BOLD']}{heading}{self.COLORS['END']}"

            super().start_section(colored_heading)
        else:
            super().start_section(heading)


def create_argument_parser():
    """创建命令行参数解析器"""

    # ANSI 颜色代码
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    MAGENTA = '\033[95m'
    BOLD = '\033[1m'
    END = '\033[0m'
    WHITE = '\033[97m'
    BLUE = '\033[94m'
    DIM = '\033[2m'

    # 定义 banner 内容（纯文本，用于计算宽度）
    plain_lines = [
        "",
        "   🐕 FuzzHound - API 安全测试工具",
        "",
        "   Version: v1.0  |  Author: RuoJi",
        "",
        "   支持 Swagger/OpenAPI 自动化测试和智能 Fuzz",
        "",
        "   GitHub: https://github.com/RuoJi6/fuzzhound",
        "",
    ]

    # 定义带颜色的内容
    colored_lines = [
        "",
        f"   🐕 {YELLOW}FuzzHound{CYAN} - API 安全测试工具",
        "",
        f"   {WHITE}Version:{CYAN} {GREEN}v1.0{CYAN}  |  {WHITE}Author:{CYAN} {MAGENTA}RuoJi{CYAN}",
        "",
        f"   {DIM}支持 Swagger/OpenAPI 自动化测试和智能 Fuzz{END}{CYAN}",
        "",
        f"   {BLUE}GitHub:{CYAN} https://github.com/RuoJi6/fuzzhound",
        "",
    ]

    # 计算最大宽度（使用纯文本计算，emoji 算作2个字符宽度）
    def display_width(text):
        """计算字符串的显示宽度，emoji 算作2个字符"""
        width = 0
        for char in text:
            # emoji 和中文字符占2个宽度
            if ord(char) > 0x1F300 or '\u4e00' <= char <= '\u9fff':
                width += 2
            else:
                width += 1
        return width

    max_width = max(display_width(line) for line in plain_lines)

    # 构建自适应框
    top_border = f"╔{'═' * (max_width + 2)}╗"
    bottom_border = f"╚{'═' * (max_width + 2)}╝"

    banner_lines = [top_border]
    for i, line in enumerate(colored_lines):
        # 计算实际显示宽度
        visible_len = display_width(plain_lines[i])
        padding = max_width - visible_len
        banner_lines.append(f"║ {line}{' ' * padding} ║")
    banner_lines.append(bottom_border)

    # 自定义帮助信息
    description = f"""
{CYAN}{BOLD}{chr(10).join(banner_lines)}{END}

    """

    epilog = f"""
{YELLOW}{BOLD}使用示例:{END}
  {GREEN}# 基础测试{END}
  python3 fuzzhound.py -u http://example.com/api-docs

  {GREEN}# 启用所有 Fuzz 测试{END}
  python3 fuzzhound.py -u http://example.com/api-docs --fall

  {GREEN}# 用户名 Fuzz（所有参数 + 全部字典）{END}
  python3 fuzzhound.py -u http://example.com/api-docs --fuser all:all

  {GREEN}# SQL 注入检测（智能模式）{END}
  python3 fuzzhound.py -u http://example.com/api-docs --fpsql --sql-mode smart

  {GREEN}# 使用代理（Burp Suite/Charles等）{END}
  python3 fuzzhound.py -u http://example.com/api-docs --proxy http://127.0.0.1:8080

  {GREEN}# 指定输出目录{END}
  python3 fuzzhound.py -u http://example.com/api-docs -o ./my_output

  {GREEN}# 只对返回 200 的 API 进行 Fuzz{END}
  python3 fuzzhound.py -u http://example.com/api-docs --fall --fuzz-filter 200

  {GREEN}# 数字型 Fuzz（检测 IDOR 漏洞）{END}
  python3 fuzzhound.py -u http://example.com/api-docs --fnumber 1-10000

  {GREEN}# 只显示高度可疑的 Fuzz 结果{END}
  python3 fuzzhound.py -u http://example.com/api-docs --fall --fuzz-level likely

  {GREEN}# 使用 --prefix 和 --ignore-basepath{END}
  {GREEN}# API文档: http://example.com/base-service/;/v2/api-docs (basePath: /bs-service){END}
  {GREEN}# 实际API: http://example.com/base-service/api/user/list{END}
  python3 fuzzhound.py -u "http://example.com/base-service/;/v2/api-docs" --prefix /base-service/api --ignore-basepath

{MAGENTA}GitHub: https://github.com/RuoJi6/fuzzhound{END}
    """

    parser = argparse.ArgumentParser(
        description=description,
        epilog=epilog,
        formatter_class=ColoredHelpFormatter,
        add_help=True
    )
    
    # 基础参数组
    basic_group = parser.add_argument_group('🎯 基础参数')
    basic_group.add_argument('-u', '--url', metavar='URL', help='目标 URL (可以是完整的 API 文档 URL 或基础 URL)')
    basic_group.add_argument('-p', '--path', metavar='PATH', help='API 文档路径 (如果 -u 是基础 URL，则需要指定此参数)')
    basic_group.add_argument('-c', '--config', metavar='FILE', default='config/config.yaml', help='配置文件路径 (默认: config/config.yaml)')
    basic_group.add_argument('-o', '--output', metavar='DIR', help='输出目录 (覆盖配置文件)')
    basic_group.add_argument('--prefix', metavar='PREFIX', help='API请求路径前缀，仅作用于实际API请求，不影响获取API文档 (如: /api 会将 /user/list 转换为 /api/user/list)')
    basic_group.add_argument('--ignore-basepath', action='store_true', help='忽略 API 文档中的 basePath/server URL，只使用 API 路径本身。与 --prefix 配合使用时，只会添加 prefix 而不会叠加 basePath')
    basic_group.add_argument('--proxy', metavar='PROXY', help='代理地址 (如: http://127.0.0.1:8080)')

    # 性能参数组
    perf_group = parser.add_argument_group('⚡ 性能参数')
    perf_group.add_argument('-t', '--threads', metavar='N', type=int, help='并发线程数 (默认: 5)')
    perf_group.add_argument('-d', '--delay', metavar='SEC', type=float, help='请求延迟（秒）(默认: 1.5)')
    perf_group.add_argument('--enum-limit', metavar='N', type=int, help='限制每个枚举参数测试的值数量（默认: 0=测试所有枚举值）。例如：--enum-limit 3 只测试每个枚举参数的前3个值。适用于 API 文档中定义了 enum 的参数（如 sourceDB: [InterPro, pfam, smart, ...]）')

    # Fuzz 参数组
    fuzz_group = parser.add_argument_group('💥 Fuzz 选项')
    fuzz_group.add_argument('--fall', metavar='MODE', nargs='?', const='default', help='🔥 一键启用所有Fuzz测试。不带参数或"default"使用关键字匹配，"all"测试所有参数')
    fuzz_group.add_argument('--fuser', metavar='N|all|all:N|all:all', nargs='?', const='default',
                           help='启用用户名 Fuzz。格式：N=关键字+随机N个，all=所有参数+随机15个，all:N=所有参数+随机N个，all:all=所有参数+全部字典')
    fuzz_group.add_argument('--fpass', metavar='N|all|all:N|all:all', nargs='?', const='default',
                           help='启用密码 Fuzz。格式：N=关键字+随机N个，all=所有参数+随机15个，all:N=所有参数+随机N个，all:all=所有参数+全部字典')
    fuzz_group.add_argument('--fnumber', metavar='N|START-END|all', type=str, help='启用数字型 Fuzz（默认1-1000随机15个，可指定数量如"40"或范围如"1-100"）。使用 "all" 测试所有数字型参数')
    fuzz_group.add_argument('--fpsql', metavar='KEYWORDS', nargs='?', const='default', help='启用SQL注入 Fuzz（对参数进行SQL注入漏洞检测）。使用 "all" 测试所有参数（根据类型智能选择payload）')
    fuzz_group.add_argument('--sql-mode', metavar='MODE', choices=['basic', 'smart', 'full'], help='SQL注入Fuzz模式：basic(10个payload)、smart(20个payload，默认)、full(155个全部payload)')
    fuzz_group.add_argument('--sql-payloads', metavar='N', type=int, help='SQL注入每个参数测试的payload数量（仅在smart模式生效，覆盖默认的20个）')
    fuzz_group.add_argument('--fuzz-status', metavar='CODES', help='Fuzz结果状态码筛选，只显示指定状态码的结果（逗号分隔，如: 200,500,403）。默认: 200,500,403,401,302。使用 "all" 显示所有状态码')
    fuzz_group.add_argument('--fuzz-filter', metavar='CODES', help='Fuzz前置筛选，只对指定状态码的API进行Fuzz测试（逗号分隔，如: 200,403）。默认: all（所有API都进行Fuzz）')
    fuzz_group.add_argument('--fuzz-level', metavar='LEVEL', choices=['likely', 'possible', 'all'], default='possible', help='Fuzz检测级别筛选：likely(只显示高度可疑🚨/🎯)、possible(显示可能有效及以上⚠️+🚨，默认)、all(显示所有级别包括❌)')

    # 默认值参数组
    default_group = parser.add_argument_group('🎲 默认值选项')
    default_group.add_argument('--default-int', metavar='VALUE', type=int, help='设置整数型参数的默认值（默认: 1）')
    default_group.add_argument('--default-float', metavar='VALUE', type=float, help='设置浮点型参数的默认值（默认: 1.0）')
    default_group.add_argument('--default-string', metavar='VALUE', type=str, help='设置字符串型参数的默认值（默认: "test"）')
    default_group.add_argument('--default-bool', metavar='VALUE', type=str, choices=['true', 'false'], help='设置布尔型参数的默认值（默认: true）')
    default_group.add_argument('--default-date', metavar='VALUE', type=str, help='设置日期型参数的默认值（默认: "2024-01-01"）')
    default_group.add_argument('--default-datetime', metavar='VALUE', type=str, help='设置日期时间型参数的默认值（默认: "2024-01-01 00:00:00"）')
    default_group.add_argument('--default-timestamp', metavar='VALUE', type=int, help='设置时间戳型参数的默认值（默认: 1704067200）')

    # 其他参数组
    other_group = parser.add_argument_group('🔧 其他选项')
    other_group.add_argument('-v', '--verbose', action='store_true', help='显示详细信息')
    other_group.add_argument('--debug', action='store_true', help='启用调试模式（显示详细日志和调试信息）')
    other_group.add_argument('--ignore-blacklist', action='store_true', help='忽略黑名单，测试所有接口（包括危险操作）')

    return parser

