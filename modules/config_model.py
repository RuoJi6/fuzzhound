from typing import List, Dict, Optional, Union, Any
from pydantic import BaseModel, Field, HttpUrl

class TargetConfig(BaseModel):
    base_url: str = Field(..., description="Target Base URL")
    api_path: str = Field(..., description="API Documentation Path")
    custom_prefix: str = Field("", description="Custom API Prefix")
    ignore_basepath: bool = Field(False, description="Ignore Base Path")
    timeout: int = Field(10, description="Request Timeout")
    verify_ssl: bool = Field(False, description="Verify SSL Certificate")

class RequestConfig(BaseModel):
    threads: int = Field(5, description="Number of concurrent threads")
    delay: float = Field(0, description="Request delay in seconds")
    headers: Dict[str, str] = Field(default_factory=dict, description="Custom Headers")
    double_check: bool = Field(True, description="Double check requests")
    enum_test_limit: int = Field(0, description="Limit for enum testing (0 for all)")

class AuthConfig(BaseModel):
    enabled: bool = Field(False, description="Enable Authentication")
    type: str = Field("bearer", description="Auth Type: bearer, api_key, cookie")
    token: str = Field("", description="Auth Token")
    header_name: str = Field("Authorization", description="Header Name for API Key")
    cookie: str = Field("", description="Cookie String")

class ProxyConfig(BaseModel):
    enabled: bool = Field(False, description="Enable Proxy")
    http: str = Field("", description="HTTP Proxy")
    https: str = Field("", description="HTTPS Proxy")

class BlacklistConfig(BaseModel):
    enabled: bool = Field(False, description="Enable Blacklist")
    methods: List[str] = Field(default_factory=list, description="Blacklisted Methods")
    paths: List[str] = Field(default_factory=list, description="Blacklisted Paths")
    path_patterns: List[str] = Field(default_factory=list, description="Blacklisted Path Patterns")
    ignore_blacklist: bool = Field(False, description="Ignore Blacklist")

class FuzzConfig(BaseModel):
    enabled: bool = Field(False, description="Enable Fuzzing")
    keywords: List[str] = Field(default_factory=list, description="Keywords to match")
    count: int = Field(15, description="Number of fuzz payloads")
    mode: str = Field("keyword", description="Fuzz Mode: keyword, all")

class UsernameFuzzConfig(FuzzConfig):
    username_file: str = Field("config/usernames.txt", description="Username Dictionary File")

class PasswordFuzzConfig(FuzzConfig):
    password_file: str = Field("config/top100_password.txt", description="Password Dictionary File")

class NumberFuzzConfig(BaseModel):
    enabled: bool = Field(False, description="Enable Number Fuzzing")
    mode: str = Field("random", description="Mode: random, range")
    range_start: int = Field(1, description="Range Start")
    range_end: int = Field(100, description="Range End")
    count: int = Field(15, description="Random Count")
    default_range_start: int = Field(1, description="Default Range Start")
    default_range_end: int = Field(1000, description="Default Range End")

class SQLFuzzConfig(BaseModel):
    enabled: bool = Field(False, description="Enable SQL Fuzzing")
    mode: str = Field("smart", description="Mode: basic, smart, full")
    payload_file: str = Field("config/sql_payloads.txt", description="Payload File")
    keywords: List[str] = Field(default_factory=list, description="Keywords")
    max_payloads: int = Field(20, description="Max Payloads per param")
    detect_errors: bool = Field(True, description="Detect SQL Errors")
    error_file: str = Field("config/sql_errors.txt", description="Error Patterns File")
    detect_diff: bool = Field(True, description="Detect Response Diff")
    diff_threshold: int = Field(100, description="Length Diff Threshold")
    similarity_threshold: float = Field(0.7, description="Similarity Threshold")

class FuzzDetectionConfig(BaseModel):
    filter_status_codes: List[int] = Field(default_factory=list, description="Filter Result Status Codes")
    fuzz_filter_codes: List[int] = Field(default_factory=list, description="Filter Target API Status Codes")

class OutputConfig(BaseModel):
    output_dir: str = Field("output", description="Output Directory")
    html_report: str = Field("report.html", description="HTML Report Filename")

class LoggingConfig(BaseModel):
    log_dir: str = Field("logs", description="Log Directory")
    log_file: str = Field("fuzzhound.log", description="Log Filename")
    level: str = Field("INFO", description="Log Level")

class DebugConfig(BaseModel):
    enabled: bool = Field(False, description="Enable Debug Mode")

class DefaultValuesConfig(BaseModel):
    integer: int = Field(1, description="Default Integer")
    number: float = Field(1.0, description="Default Float")
    string: str = Field("test", description="Default String")
    boolean: bool = Field(True, description="Default Boolean")
    date: str = Field("2024-01-01", description="Default Date")
    datetime: str = Field("2024-01-01 00:00:00", description="Default DateTime")
    timestamp: int = Field(1704067200, description="Default Timestamp")

class AppConfig(BaseModel):
    target: TargetConfig
    request: RequestConfig = Field(default_factory=RequestConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)
    blacklist: BlacklistConfig = Field(default_factory=BlacklistConfig)
    fuzz_username: UsernameFuzzConfig = Field(default_factory=UsernameFuzzConfig)
    fuzz_password: PasswordFuzzConfig = Field(default_factory=PasswordFuzzConfig)
    fuzz_number: NumberFuzzConfig = Field(default_factory=NumberFuzzConfig)
    fuzz_sql: SQLFuzzConfig = Field(default_factory=SQLFuzzConfig)
    fuzz_detection: FuzzDetectionConfig = Field(default_factory=FuzzDetectionConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    debug: DebugConfig = Field(default_factory=DebugConfig)
    default_values: DefaultValuesConfig = Field(default_factory=DefaultValuesConfig)
