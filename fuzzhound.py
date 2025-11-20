#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FuzzHound - API 安全测试工具
Version: v1.0
Author: RuoJi
GitHub: https://github.com/RuoJi6/fuzzhound

支持 Swagger/OpenAPI 自动化测试和智能 Fuzz
包含字典攻击、SQL注入、IDOR、文件上传等多种测试模式
"""

import sys
from pathlib import Path

from modules.cli_parser import create_argument_parser
from modules.config_manager import load_config, validate_config, merge_cli_args
from modules.utils import setup_logger, print_banner
from modules.executor import execute_tests

from rich.console import Console

console = Console()


def main():
    """主函数"""

    # 创建参数解析器并解析参数
    parser = create_argument_parser()

    # 如果没有提供任何参数，显示帮助信息
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    # 打印 Banner
    print_banner()

    # 加载配置
    config = load_config(args.config)
    if not validate_config(config):
        sys.exit(1)

    # 合并命令行参数到配置
    config = merge_cli_args(config, args)
    
    # 设置日志
    global logger
    logger = setup_logger(config)
    
    # 执行测试
    try:
        execute_tests(config)
    except KeyboardInterrupt:
        console.print(f"\n[yellow]⚠ 用户中断测试[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]✗ 发生错误: {e}[/red]")
        if config.get('debug', {}).get('enabled', False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

