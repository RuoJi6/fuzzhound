#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API Fuzz 测试工具
支持 Spring Boot Swagger/OpenAPI 接口测试和 Fuzz
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

