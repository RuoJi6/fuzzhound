#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fuzz 检测模块
用于判断用户名 Fuzz 是否成功
"""

import logging
import json

logger = logging.getLogger('fuzzhound.fuzz_detector')


class FuzzDetector:
    """Fuzz 检测器"""
    
    def __init__(self, config):
        self.config = config

        # 优先使用通用的 fuzz_detection 配置，如果没有则使用 fuzz_username 的配置（向后兼容）
        self.detection_config = config.get('fuzz_detection', config.get('fuzz_username', {}).get('detection', {}))
        self.enabled = self.detection_config.get('enabled', True)

        # 状态码配置
        self.success_status_codes = self.detection_config.get('success_status_codes', [200, 201, 202])
        self.auth_status_codes = self.detection_config.get('auth_status_codes', [401, 403])

        # 阈值配置
        self.length_diff_threshold = self.detection_config.get('length_diff_threshold', 20)
        self.time_diff_threshold = self.detection_config.get('time_diff_threshold', 2.0)

        # 关键字配置
        self.success_keywords = [kw.lower() for kw in self.detection_config.get('success_keywords', [])]
        self.failure_keywords = [kw.lower() for kw in self.detection_config.get('failure_keywords', [])]

        # 评分阈值
        self.score_threshold_possible = self.detection_config.get('score_threshold_possible', 50)
        self.score_threshold_likely = self.detection_config.get('score_threshold_likely', 70)

        # 存储基准响应
        self.baseline_responses = {}
    
    def set_baseline(self, api_key, result):
        """设置基准响应

        Args:
            api_key: API 标识（method + path）
            result: 基准请求的响应结果
        """
        self.baseline_responses[api_key] = {
            'status_code': result['status_code'],
            'response_length': result['response_length'],
            'response_time': result['response_time'],
            'response_body': result.get('response_body', '')
        }
        logger.debug(f"📊 设置基准响应: {api_key} - 状态码:{result['status_code']}, 长度:{result['response_length']}")

    def get_baseline(self, api_key):
        """获取基准响应

        Args:
            api_key: API 标识（method + path）

        Returns:
            dict: 基准响应数据，如果不存在则返回 None
        """
        return self.baseline_responses.get(api_key)

    def get_api_key(self, result):
        """生成 API 标识
        
        Args:
            result: 请求结果
            
        Returns:
            str: API 标识
        """
        request_data = result.get('request', {})
        api = request_data.get('api', {})
        method = api.get('method', result.get('method', 'GET'))
        path = api.get('path', '')
        return f"{method}:{path}"
    
    def analyze_fuzz_result(self, result):
        """分析 Fuzz 结果
        
        Args:
            result: Fuzz 请求的响应结果
            
        Returns:
            dict: 分析结果
        """
        if not self.enabled:
            return None
        
        # 获取 API 标识
        api_key = self.get_api_key(result)
        
        # 如果没有基准响应，无法判断
        if api_key not in self.baseline_responses:
            logger.debug(f"⚠️  没有找到基准响应: {api_key}")
            return None
        
        baseline = self.baseline_responses[api_key]
        
        # 开始评分
        score = 0
        reasons = []

        # 1. 状态码判断 (最高50分)
        status_code = result['status_code']
        baseline_status = baseline['status_code']

        # 检测是否两者都是认证错误（用于后续降低权重）
        both_auth_errors = (status_code in self.auth_status_codes and
                           baseline_status in self.auth_status_codes)

        if status_code in self.success_status_codes and baseline_status not in self.success_status_codes:
            # 从非成功码变为成功码（最有价值）
            score += 50
            reasons.append(f"状态码从{baseline_status}变为{status_code}")
        elif status_code in self.auth_status_codes and baseline_status not in self.auth_status_codes:
            # 从非认证码变为认证码（说明用户可能存在，但需要认证）
            # 注意：只有当基准状态码不是401/403时才加分，避免误报
            score += 40
            reasons.append(f"状态码从{baseline_status}变为{status_code}(需要认证)")
        elif status_code != baseline_status:
            # 其他状态码变化
            score += 20
            reasons.append(f"状态码变化: {baseline_status} → {status_code}")

        # 2. 响应长度判断 (最高30分)
        # 原则：响应包越长，价值越高（可能返回了更多数据）
        response_length = result['response_length']
        baseline_length = baseline['response_length']

        if baseline_length > 0:
            length_diff_percent = abs(response_length - baseline_length) / baseline_length * 100

            if length_diff_percent > self.length_diff_threshold:
                if response_length > baseline_length:
                    # 响应长度增加（高价值）
                    # 根据增加的幅度和绝对长度来评分
                    if response_length > 1000:
                        # 响应包很大（>1KB），可能返回了详细数据
                        length_score = 15 if both_auth_errors else 30
                    elif response_length > 500:
                        # 响应包中等（>500B）
                        length_score = 12 if both_auth_errors else 25
                    else:
                        # 响应包较小
                        length_score = 10 if both_auth_errors else 20
                    score += length_score
                    reasons.append(f"响应长度增加{length_diff_percent:.1f}% (从{baseline_length}到{response_length}字节)")
                else:
                    # 响应长度减少（低价值，可能只是错误消息变短）
                    length_score = 3 if both_auth_errors else 5
                    score += length_score
                    reasons.append(f"响应长度减少{length_diff_percent:.1f}% (从{baseline_length}到{response_length}字节)")

        # 3. 响应时间判断 (最高10分)
        response_time = result['response_time']
        baseline_time = baseline['response_time']

        if baseline_time > 0:
            time_ratio = response_time / baseline_time

            if time_ratio > self.time_diff_threshold:
                score += 10
                reasons.append(f"响应时间增加{time_ratio:.1f}倍")

        # 4. 响应内容关键字判断 (最高20分)
        response_body = result.get('response_body', '')
        response_text = self._extract_text(response_body).lower()

        success_keyword_found = False
        failure_keyword_found = False

        for keyword in self.success_keywords:
            if keyword in response_text:
                score += 20
                reasons.append(f"包含成功关键字'{keyword}'")
                success_keyword_found = True
                break

        for keyword in self.failure_keywords:
            if keyword in response_text:
                score -= 10
                reasons.append(f"包含失败关键字'{keyword}'")
                failure_keyword_found = True
                break

        # 5. 综合判断
        if score >= self.score_threshold_likely:
            level = 'likely'
            label = '高度可疑'
            icon = '🎯'
        elif score >= self.score_threshold_possible:
            level = 'possible'
            label = '可能有效'
            icon = '⚠️'
        else:
            level = 'unlikely'
            label = '可能无效'
            icon = '❌'

        # 获取 Fuzz 的用户名
        request_data = result.get('request', {})
        fuzz_value = request_data.get('fuzz_value', '')
        fuzz_target = request_data.get('fuzz_target', '')

        analysis = {
            'score': score,
            'level': level,
            'label': label,
            'icon': icon,
            'reasons': reasons,
            'fuzz_value': fuzz_value,
            'fuzz_target': fuzz_target,
            'status_code': status_code,
            'baseline_status': baseline_status,
            'response_length': response_length,
            'baseline_length': baseline_length
        }

        logger.debug(f"{icon} Fuzz分析: {fuzz_target}={fuzz_value} - 评分:{score}, 级别:{label}")

        return analysis

    def _extract_text(self, response_body):
        """从响应体中提取文本

        Args:
            response_body: 响应体（可能是字符串或字典）

        Returns:
            str: 提取的文本
        """
        if isinstance(response_body, str):
            return response_body
        elif isinstance(response_body, dict):
            return json.dumps(response_body)
        else:
            return str(response_body)

    def get_summary(self):
        """获取检测摘要

        Returns:
            dict: 摘要信息
        """
        return {
            'baseline_count': len(self.baseline_responses),
            'enabled': self.enabled
        }

