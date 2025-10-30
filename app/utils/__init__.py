"""
Utils package for SaaS Monitoring Platform
"""
"""Utilities module for the SaaS Monitoring Platform."""

from utils.cache import CacheManager, cache_result, invalidate_cache
from utils.helpers import (
    format_file_size,
    format_timestamp,
    validate_file_type,
    calculate_percentage,
    truncate_string,
    safe_divide,
    format_log_level,
    format_status_code,
    sanitize_filename,
    parse_date_range,
    get_file_extension,
    format_duration
)

__all__ = [
    # Cache utilities
    'CacheManager',
    'cache_result',
    'invalidate_cache',
    
    # Helper utilities
    'format_file_size',
    'format_timestamp',
    'validate_file_type',
    'calculate_percentage',
    'truncate_string',
    'safe_divide',
    'format_log_level',
    'format_status_code',
    'sanitize_filename',
    'parse_date_range',
    'get_file_extension',
    'format_duration'
]

__all__ = ['CacheManager', 'cache_result', 'invalidate_cache']
