"""
Utility helper functions for the SaaS Monitoring Platform.

This module provides commonly used utility functions for:
- File size formatting
- Timestamp formatting
- File type validation
- Percentage calculations
- Data formatting and conversion
"""

from typing import Optional, Union
from datetime import datetime
import os


def format_file_size(size_bytes: int) -> str:
    """
    Convert file size in bytes to human-readable format.
    
    Converts bytes to the most appropriate unit (B, KB, MB, GB, TB)
    with two decimal places of precision.
    
    Args:
        size_bytes (int): File size in bytes
    
    Returns:
        str: Formatted file size (e.g., "2.50 MB", "1.23 GB")
    
    Examples:
        >>> format_file_size(1024)
        '1.00 KB'
        >>> format_file_size(1048576)
        '1.00 MB'
        >>> format_file_size(1536)
        '1.50 KB'
    """
    if size_bytes < 0:
        return "0 B"
    
    # Define units and their thresholds
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    unit_index = 0
    size = float(size_bytes)
    
    # Convert to appropriate unit
    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1
    
    # Format with 2 decimal places, remove trailing zeros
    if unit_index == 0:
        # Bytes should not have decimals
        return f"{int(size)} {units[unit_index]}"
    else:
        return f"{size:.2f} {units[unit_index]}"


def format_timestamp(
    timestamp: Union[str, datetime], 
    format_type: str = 'short'
) -> str:
    """
    Format ISO timestamp or datetime object to human-readable string.
    
    Supports multiple output formats:
    - 'short': "Oct 30, 10:00 AM"
    - 'long': "October 30, 2025 at 10:00:00 AM"
    - 'date': "Oct 30, 2025"
    - 'time': "10:00 AM"
    - 'relative': "2 hours ago" (future implementation)
    
    Args:
        timestamp (Union[str, datetime]): ISO 8601 timestamp string or datetime object
        format_type (str): Output format type (default: 'short')
    
    Returns:
        str: Formatted timestamp string
    
    Raises:
        ValueError: If timestamp format is invalid
    
    Examples:
        >>> format_timestamp("2025-10-30T10:00:00Z")
        'Oct 30, 10:00 AM'
        >>> format_timestamp("2025-10-30T10:00:00Z", format_type='date')
        'Oct 30, 2025'
    """
    # Convert string to datetime if needed
    if isinstance(timestamp, str):
        try:
            # Handle various ISO 8601 formats
            if timestamp.endswith('Z'):
                timestamp = timestamp[:-1] + '+00:00'
            
            # Try parsing with timezone
            try:
                dt = datetime.fromisoformat(timestamp)
            except:
                # Fallback: parse without timezone
                dt = datetime.strptime(timestamp.split('.')[0], '%Y-%m-%dT%H:%M:%S')
        except Exception as e:
            raise ValueError(f"Invalid timestamp format: {timestamp}") from e
    else:
        dt = timestamp
    
    # Format based on type
    if format_type == 'short':
        return dt.strftime('%b %d, %I:%M %p')
    elif format_type == 'long':
        return dt.strftime('%B %d, %Y at %I:%M:%S %p')
    elif format_type == 'date':
        return dt.strftime('%b %d, %Y')
    elif format_type == 'time':
        return dt.strftime('%I:%M %p')
    elif format_type == 'iso':
        return dt.isoformat()
    else:
        # Default to short format
        return dt.strftime('%b %d, %I:%M %p')


def validate_file_type(
    filename: str, 
    allowed_extensions: Optional[list] = None
) -> bool:
    """
    Validate if a file has an allowed extension.
    
    Performs case-insensitive extension checking. If no allowed_extensions
    list is provided, defaults to ['csv', 'json'].
    
    Args:
        filename (str): Name of the file to validate
        allowed_extensions (Optional[list]): List of allowed extensions without dots
                                             (default: ['csv', 'json'])
    
    Returns:
        bool: True if file extension is allowed, False otherwise
    
    Examples:
        >>> validate_file_type('data.csv')
        True
        >>> validate_file_type('data.txt')
        False
        >>> validate_file_type('DATA.CSV')
        True
        >>> validate_file_type('config.yaml', ['yaml', 'yml'])
        True
    """
    if allowed_extensions is None:
        allowed_extensions = ['csv', 'json']
    
    # Check if filename has an extension
    if '.' not in filename:
        return False
    
    # Extract extension (case-insensitive)
    extension = filename.rsplit('.', 1)[1].lower()
    
    # Convert allowed extensions to lowercase for comparison
    allowed_extensions_lower = [ext.lower() for ext in allowed_extensions]
    
    return extension in allowed_extensions_lower


def calculate_percentage(part: Union[int, float], total: Union[int, float]) -> float:
    """
    Calculate percentage with safe division (handles zero total).
    
    Returns the percentage of part relative to total, rounded to 2 decimal places.
    If total is 0, returns 0.0 to avoid division by zero.
    
    Args:
        part (Union[int, float]): The part value (numerator)
        total (Union[int, float]): The total value (denominator)
    
    Returns:
        float: Percentage value (0.0 to 100.0), rounded to 2 decimal places
    
    Examples:
        >>> calculate_percentage(25, 100)
        25.0
        >>> calculate_percentage(1, 3)
        33.33
        >>> calculate_percentage(5, 0)
        0.0
        >>> calculate_percentage(150, 100)
        150.0
    """
    if total == 0:
        return 0.0
    
    percentage = (part / total) * 100
    return round(percentage, 2)


def truncate_string(text: str, max_length: int = 50, suffix: str = '...') -> str:
    """
    Truncate string to maximum length with optional suffix.
    
    If the string is longer than max_length, it will be truncated and
    the suffix will be appended. The suffix length is included in max_length.
    
    Args:
        text (str): Text to truncate
        max_length (int): Maximum length including suffix (default: 50)
        suffix (str): Suffix to append when truncated (default: '...')
    
    Returns:
        str: Truncated string with suffix if needed
    
    Examples:
        >>> truncate_string('This is a very long message', 15)
        'This is a ve...'
        >>> truncate_string('Short', 50)
        'Short'
    """
    if len(text) <= max_length:
        return text
    
    # Calculate truncation point (account for suffix length)
    truncate_at = max_length - len(suffix)
    
    if truncate_at <= 0:
        return suffix[:max_length]
    
    return text[:truncate_at] + suffix


def safe_divide(
    numerator: Union[int, float], 
    denominator: Union[int, float], 
    default: Union[int, float] = 0
) -> float:
    """
    Perform division with safe handling of zero denominator.
    
    Args:
        numerator (Union[int, float]): The numerator
        denominator (Union[int, float]): The denominator
        default (Union[int, float]): Value to return if denominator is 0 (default: 0)
    
    Returns:
        float: Result of division or default value
    
    Examples:
        >>> safe_divide(10, 2)
        5.0
        >>> safe_divide(10, 0)
        0
        >>> safe_divide(10, 0, default=None)
        None
    """
    if denominator == 0:
        return default
    
    return numerator / denominator


def format_log_level(level: str) -> dict:
    """
    Get display properties for log level (color, icon, badge class).
    
    Args:
        level (str): Log level (e.g., 'INFO', 'ERROR', 'DEBUG')
    
    Returns:
        dict: Dictionary with 'color', 'icon', and 'badge_class' keys
    
    Examples:
        >>> format_log_level('ERROR')
        {'color': 'danger', 'icon': 'exclamation-circle', 'badge_class': 'badge-danger'}
        >>> format_log_level('INFO')
        {'color': 'info', 'icon': 'info-circle', 'badge_class': 'badge-info'}
    """
    level_upper = level.upper()
    
    level_config = {
        'DEBUG': {
            'color': 'secondary',
            'icon': 'bug',
            'badge_class': 'badge-secondary'
        },
        'INFO': {
            'color': 'info',
            'icon': 'info-circle',
            'badge_class': 'badge-info'
        },
        'WARNING': {
            'color': 'warning',
            'icon': 'exclamation-triangle',
            'badge_class': 'badge-warning'
        },
        'ERROR': {
            'color': 'danger',
            'icon': 'exclamation-circle',
            'badge_class': 'badge-danger'
        },
        'CRITICAL': {
            'color': 'dark',
            'icon': 'times-circle',
            'badge_class': 'badge-dark'
        }
    }
    
    return level_config.get(level_upper, {
        'color': 'primary',
        'icon': 'circle',
        'badge_class': 'badge-primary'
    })


def format_status_code(code: int) -> dict:
    """
    Get display properties for HTTP status code.
    
    Args:
        code (int): HTTP status code (e.g., 200, 404, 500)
    
    Returns:
        dict: Dictionary with 'category', 'color', and 'description' keys
    
    Examples:
        >>> format_status_code(200)
        {'category': 'success', 'color': 'success', 'description': 'OK'}
        >>> format_status_code(404)
        {'category': 'client_error', 'color': 'warning', 'description': 'Not Found'}
    """
    # Determine category and color based on status code range
    if 200 <= code < 300:
        category = 'success'
        color = 'success'
    elif 300 <= code < 400:
        category = 'redirect'
        color = 'info'
    elif 400 <= code < 500:
        category = 'client_error'
        color = 'warning'
    elif 500 <= code < 600:
        category = 'server_error'
        color = 'danger'
    else:
        category = 'unknown'
        color = 'secondary'
    
    # Common status code descriptions
    descriptions = {
        200: 'OK',
        201: 'Created',
        204: 'No Content',
        301: 'Moved Permanently',
        302: 'Found',
        304: 'Not Modified',
        400: 'Bad Request',
        401: 'Unauthorized',
        403: 'Forbidden',
        404: 'Not Found',
        405: 'Method Not Allowed',
        429: 'Too Many Requests',
        500: 'Internal Server Error',
        502: 'Bad Gateway',
        503: 'Service Unavailable',
        504: 'Gateway Timeout'
    }
    
    description = descriptions.get(code, f'Status {code}')
    
    return {
        'category': category,
        'color': color,
        'description': description
    }


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing/replacing unsafe characters.
    
    Removes or replaces characters that are unsafe for filenames across
    different operating systems (Windows, Linux, macOS).
    
    Args:
        filename (str): Original filename
    
    Returns:
        str: Sanitized filename safe for filesystem
    
    Examples:
        >>> sanitize_filename('report*.txt')
        'report.txt'
        >>> sanitize_filename('data/file.csv')
        'data_file.csv'
    """
    # Characters to remove or replace
    unsafe_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    
    sanitized = filename
    for char in unsafe_chars:
        sanitized = sanitized.replace(char, '_')
    
    # Remove leading/trailing spaces and dots
    sanitized = sanitized.strip(' .')
    
    # Ensure filename is not empty
    if not sanitized:
        sanitized = 'unnamed_file'
    
    return sanitized


def parse_date_range(date_from: Optional[str], date_to: Optional[str]) -> dict:
    """
    Parse and validate date range parameters.
    
    Converts date strings to datetime objects and ensures date_from is before date_to.
    
    Args:
        date_from (Optional[str]): Start date (ISO format or None)
        date_to (Optional[str]): End date (ISO format or None)
    
    Returns:
        dict: Dictionary with 'valid', 'date_from', 'date_to', 'error' keys
    
    Examples:
        >>> parse_date_range('2025-10-01', '2025-10-31')
        {'valid': True, 'date_from': datetime(...), 'date_to': datetime(...), 'error': None}
        >>> parse_date_range('2025-10-31', '2025-10-01')
        {'valid': False, 'date_from': None, 'date_to': None, 'error': 'date_from must be before date_to'}
    """
    result = {
        'valid': True,
        'date_from': None,
        'date_to': None,
        'error': None
    }
    
    try:
        # Parse date_from
        if date_from:
            result['date_from'] = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
        
        # Parse date_to
        if date_to:
            result['date_to'] = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
        
        # Validate range
        if result['date_from'] and result['date_to']:
            if result['date_from'] > result['date_to']:
                result['valid'] = False
                result['error'] = 'date_from must be before date_to'
                result['date_from'] = None
                result['date_to'] = None
    
    except Exception as e:
        result['valid'] = False
        result['error'] = f'Invalid date format: {str(e)}'
        result['date_from'] = None
        result['date_to'] = None
    
    return result


def get_file_extension(filename: str) -> str:
    """
    Extract file extension from filename.
    
    Args:
        filename (str): Filename with or without path
    
    Returns:
        str: File extension in lowercase (without dot), or empty string if no extension
    
    Examples:
        >>> get_file_extension('data.csv')
        'csv'
        >>> get_file_extension('/path/to/file.JSON')
        'json'
        >>> get_file_extension('README')
        ''
    """
    if '.' not in filename:
        return ''
    
    return filename.rsplit('.', 1)[1].lower()


def format_duration(milliseconds: float) -> str:
    """
    Format duration in milliseconds to human-readable string.
    
    Args:
        milliseconds (float): Duration in milliseconds
    
    Returns:
        str: Formatted duration (e.g., "250ms", "1.5s", "2m 30s")
    
    Examples:
        >>> format_duration(500)
        '500ms'
        >>> format_duration(1500)
        '1.50s'
        >>> format_duration(65000)
        '1m 5s'
    """
    if milliseconds < 1000:
        return f"{int(milliseconds)}ms"
    
    seconds = milliseconds / 1000
    
    if seconds < 60:
        return f"{seconds:.2f}s"
    
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    
    if remaining_seconds > 0:
        return f"{minutes}m {remaining_seconds}s"
    else:
        return f"{minutes}m"
