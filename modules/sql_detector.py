#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQL注入检测模块
"""

import re
import os
import logging
import difflib
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger('fuzzhound.sql_detector')


class SQLDetector:
    """SQL注入检测器"""
    
    def __init__(self, config: dict):
        """初始化SQL注入检测器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.sql_config = config.get('fuzz_sql', {})
        
        # 加载SQL错误特征
        self.error_patterns = self._load_error_patterns()

        # 编译正则表达式（提高性能）
        # 对于不是正则表达式的模式，需要转义特殊字符
        self.compiled_patterns = []
        for pattern in self.error_patterns:
            try:
                # 尝试直接编译（如果是正则表达式）
                compiled = re.compile(pattern, re.IGNORECASE)
                self.compiled_patterns.append(compiled)
            except re.error:
                # 如果编译失败，转义特殊字符后再编译（作为普通字符串匹配）
                escaped_pattern = re.escape(pattern)
                compiled = re.compile(escaped_pattern, re.IGNORECASE)
                self.compiled_patterns.append(compiled)
        
        logger.info(f"✅ SQL注入检测器初始化完成，加载了 {len(self.error_patterns)} 个错误特征")
    
    def _load_error_patterns(self) -> List[str]:
        """加载SQL错误特征
        
        Returns:
            错误特征列表
        """
        error_file = self.sql_config.get('error_file', 'config/sql_errors.txt')
        patterns = []
        
        if not os.path.exists(error_file):
            logger.warning(f"⚠️  SQL错误特征文件不存在: {error_file}，使用内置特征")
            return self._get_builtin_error_patterns()
        
        try:
            with open(error_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # 跳过空行和注释
                    if line and not line.startswith('#'):
                        patterns.append(line)
            
            logger.debug(f"📖 从文件加载了 {len(patterns)} 个SQL错误特征")
            return patterns
        except Exception as e:
            logger.error(f"❌ 加载SQL错误特征文件失败: {e}")
            return self._get_builtin_error_patterns()
    
    def _get_builtin_error_patterns(self) -> List[str]:
        """获取内置SQL错误特征
        
        Returns:
            内置错误特征列表
        """
        return [
            "You have an error in your SQL syntax",
            "MySQL server version for the right syntax to use",
            "Unclosed quotation mark",
            "Incorrect syntax near",
            "Syntax error",
            "SQL syntax",
            "database error",
            "SQL Error",
            "ORA-\\d+",
            "SQLSTATE",
            "pg_query",
            "mysql_fetch",
            "SQLException",
            "数据库出错",
            "SQL错误",
            "语法错误",
        ]
    
    def detect_sql_error(self, response_body: str) -> Tuple[bool, List[str]]:
        """检测响应中是否包含SQL错误信息

        Args:
            response_body: 响应体内容

        Returns:
            (是否检测到SQL错误, 匹配到的错误特征列表)
        """
        if not self.sql_config.get('detect_errors', True):
            return False, []

        matched_errors = []
        seen_patterns = set()  # 避免重复匹配

        for i, pattern in enumerate(self.compiled_patterns):
            match = pattern.search(response_body)
            if match:
                # 获取原始模式字符串
                original_pattern = self.error_patterns[i]
                # 避免重复添加
                if original_pattern not in seen_patterns:
                    matched_errors.append(original_pattern)
                    seen_patterns.add(original_pattern)

        return len(matched_errors) > 0, matched_errors
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """计算两个文本的相似度 (0.0 - 1.0)"""
        if not text1 and not text2:
            return 1.0
        if not text1 or not text2:
            return 0.0
        return difflib.SequenceMatcher(None, text1, text2).ratio()

    def analyze_response_diff(self, baseline_response: dict, fuzz_response: dict) -> Dict:
        """分析响应差异
        
        Args:
            baseline_response: 基线响应
            fuzz_response: Fuzz响应
        
        Returns:
            差异分析结果
        """
        if not self.sql_config.get('detect_diff', True):
            return {'has_diff': False}
        
        result = {
            'has_diff': False,
            'status_code_diff': False,
            'length_diff': 0,
            'content_diff': False,
            'significant_diff': False,
            'similarity': 1.0
        }
        
        # 状态码差异
        baseline_status = baseline_response.get('status_code', 0)
        fuzz_status = fuzz_response.get('status_code', 0)
        if baseline_status != fuzz_status:
            result['status_code_diff'] = True
            result['has_diff'] = True
        
        # 响应长度差异
        baseline_body = str(baseline_response.get('body', ''))
        fuzz_body = str(fuzz_response.get('body', ''))
        baseline_length = len(baseline_body)
        fuzz_length = len(fuzz_body)
        length_diff = abs(baseline_length - fuzz_length)
        result['length_diff'] = length_diff
        
        # 计算相似度
        similarity = self.calculate_similarity(baseline_body, fuzz_body)
        result['similarity'] = similarity
        
        # 判断是否为显著差异
        # 1. 长度差异超过阈值
        diff_threshold = self.sql_config.get('diff_threshold', 100)
        if length_diff > diff_threshold:
            result['significant_diff'] = True
            result['has_diff'] = True
            
        # 2. 相似度低于阈值 (例如 0.7)
        similarity_threshold = self.sql_config.get('similarity_threshold', 0.7)
        if similarity < similarity_threshold:
            result['significant_diff'] = True
            result['has_diff'] = True
        
        # 内容差异（简单比较）
        if baseline_body != fuzz_body:
            result['content_diff'] = True
            result['has_diff'] = True
        
        return result
    
    def calculate_risk_score(self, detection_result: dict) -> int:
        """计算风险评分
        
        Args:
            detection_result: 检测结果
        
        Returns:
            风险评分 (0-100)
        """
        score = 0
        
        # SQL错误检测到 +50分
        if detection_result.get('has_sql_error', False):
            score += 50
            # 多个错误特征 +10分
            error_count = len(detection_result.get('matched_errors', []))
            score += min(error_count * 5, 20)
        
        # 显著响应差异 +30分
        diff_result = detection_result.get('diff_result', {})
        if diff_result.get('significant_diff', False):
            score += 30
            
            # 如果相似度非常低 (< 0.5)，额外加分
            similarity = diff_result.get('similarity', 1.0)
            if similarity < 0.5:
                score += 20
        
        # 状态码变化 +10分
        if diff_result.get('status_code_diff', False):
            score += 10
        
        # 响应长度差异 +10分
        if diff_result.get('length_diff', 0) > 0:
            score += 10
        
        return min(score, 100)

