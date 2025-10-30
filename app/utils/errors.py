"""
Custom exception classes and error handling utilities for the SaaS Monitoring Platform.

This module provides:
- Custom exception classes for different error types
- Error formatting utilities
- HTTP status code mappings
"""

from typing import Dict, Any, Optional, Tuple
from flask import jsonify, Response
import traceback


# ============================================================================
# Custom Exception Classes
# ============================================================================

class AppError(Exception):
    """Base exception class for application errors."""
    
    def __init__(self, message: str, status_code: int = 500, details: Optional[Dict[str, Any]] = None):
        """
        Initialize AppError.
        
        Args:
            message: Human-readable error message
            status_code: HTTP status code (default: 500)
            details: Additional error details (optional)
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON response."""
        error_dict = {
            'success': False,
            'error': self.message,
            'code': self.status_code,
            'type': self.__class__.__name__
        }
        
        if self.details:
            error_dict['details'] = self.details
        
        return error_dict
    
    def to_response(self) -> Tuple[Response, int]:
        """Convert exception to Flask response."""
        return jsonify(self.to_dict()), self.status_code


class ValidationError(AppError):
    """Exception raised for validation errors."""
    
    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        Initialize ValidationError.
        
        Args:
            message: Validation error message
            field: Name of the field that failed validation (optional)
            details: Additional validation details (optional)
        """
        if field and details is None:
            details = {'field': field}
        elif field and details:
            details['field'] = field
        
        super().__init__(message, status_code=400, details=details)


class DatabaseError(AppError):
    """Exception raised for database operation errors."""
    
    def __init__(self, message: str, operation: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        Initialize DatabaseError.
        
        Args:
            message: Database error message
            operation: Database operation that failed (e.g., 'insert', 'update', 'delete')
            details: Additional error details (optional)
        """
        if operation and details is None:
            details = {'operation': operation}
        elif operation and details:
            details['operation'] = operation
        
        super().__init__(message, status_code=500, details=details)


class CacheError(AppError):
    """Exception raised for cache operation errors."""
    
    def __init__(self, message: str, operation: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        Initialize CacheError.
        
        Args:
            message: Cache error message
            operation: Cache operation that failed (e.g., 'get', 'set', 'delete')
            details: Additional error details (optional)
        """
        if operation and details is None:
            details = {'operation': operation}
        elif operation and details:
            details['operation'] = operation
        
        super().__init__(message, status_code=500, details=details)


class ElasticsearchError(AppError):
    """Exception raised for Elasticsearch operation errors."""
    
    def __init__(self, message: str, operation: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        Initialize ElasticsearchError.
        
        Args:
            message: Elasticsearch error message
            operation: Elasticsearch operation that failed (e.g., 'search', 'index')
            details: Additional error details (optional)
        """
        if operation and details is None:
            details = {'operation': operation}
        elif operation and details:
            details['operation'] = operation
        
        super().__init__(message, status_code=500, details=details)


class FileProcessingError(AppError):
    """Exception raised for file processing errors."""
    
    def __init__(self, message: str, filename: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        Initialize FileProcessingError.
        
        Args:
            message: File processing error message
            filename: Name of the file that caused the error (optional)
            details: Additional error details (optional)
        """
        if filename and details is None:
            details = {'filename': filename}
        elif filename and details:
            details['filename'] = filename
        
        super().__init__(message, status_code=400, details=details)


class NotFoundError(AppError):
    """Exception raised when a requested resource is not found."""
    
    def __init__(self, message: str = "Resource not found", resource_type: Optional[str] = None, 
                 resource_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        Initialize NotFoundError.
        
        Args:
            message: Error message
            resource_type: Type of resource not found (e.g., 'file', 'search')
            resource_id: ID of the resource not found (optional)
            details: Additional error details (optional)
        """
        if not details:
            details = {}
        
        if resource_type:
            details['resource_type'] = resource_type
        if resource_id:
            details['resource_id'] = resource_id
        
        super().__init__(message, status_code=404, details=details)


class UnauthorizedError(AppError):
    """Exception raised for unauthorized access attempts."""
    
    def __init__(self, message: str = "Unauthorized access", details: Optional[Dict[str, Any]] = None):
        """
        Initialize UnauthorizedError.
        
        Args:
            message: Error message
            details: Additional error details (optional)
        """
        super().__init__(message, status_code=401, details=details)


# ============================================================================
# Error Handler Functions
# ============================================================================

def format_error_response(message: str, code: int = 500, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Format a standardized error response.
    
    Args:
        message: Error message
        code: HTTP status code
        details: Additional error details (optional)
    
    Returns:
        Dictionary with standardized error format
    """
    response = {
        'success': False,
        'error': message,
        'code': code
    }
    
    if details:
        response['details'] = details
    
    return response


def handle_validation_error(error: ValidationError) -> Tuple[Response, int]:
    """
    Handle ValidationError and return formatted response.
    
    Args:
        error: ValidationError instance
    
    Returns:
        Tuple of (JSON response, status code)
    """
    return error.to_response()


def handle_database_error(error: DatabaseError) -> Tuple[Response, int]:
    """
    Handle DatabaseError and return formatted response.
    
    Args:
        error: DatabaseError instance
    
    Returns:
        Tuple of (JSON response, status code)
    """
    return error.to_response()


def handle_cache_error(error: CacheError) -> Tuple[Response, int]:
    """
    Handle CacheError and return formatted response.
    
    Args:
        error: CacheError instance
    
    Returns:
        Tuple of (JSON response, status code)
    """
    return error.to_response()


def handle_generic_exception(error: Exception, include_traceback: bool = False) -> Dict[str, Any]:
    """
    Handle generic exceptions and return formatted error response.
    
    Args:
        error: Exception instance
        include_traceback: Whether to include traceback in response (default: False)
    
    Returns:
        Dictionary with error information
    """
    error_response = {
        'success': False,
        'error': str(error) or 'An unexpected error occurred',
        'code': 500,
        'type': type(error).__name__
    }
    
    if include_traceback:
        error_response['traceback'] = traceback.format_exc()
    
    return error_response


def create_success_response(data: Any = None, message: Optional[str] = None, 
                           code: int = 200) -> Dict[str, Any]:
    """
    Create a standardized success response.
    
    Args:
        data: Response data (optional)
        message: Success message (optional)
        code: HTTP status code (default: 200)
    
    Returns:
        Dictionary with standardized success format
    """
    response = {
        'success': True,
        'code': code
    }
    
    if message:
        response['message'] = message
    
    if data is not None:
        response['data'] = data
    
    return response


# ============================================================================
# Validation Helpers
# ============================================================================

def validate_required_fields(data: Dict[str, Any], required_fields: list) -> None:
    """
    Validate that all required fields are present in data.
    
    Args:
        data: Dictionary to validate
        required_fields: List of required field names
    
    Raises:
        ValidationError: If any required field is missing
    """
    missing_fields = [field for field in required_fields if field not in data or data[field] is None]
    
    if missing_fields:
        raise ValidationError(
            f"Missing required fields: {', '.join(missing_fields)}",
            details={'missing_fields': missing_fields}
        )


def validate_file_extension(filename: str, allowed_extensions: list) -> None:
    """
    Validate that file has an allowed extension.
    
    Args:
        filename: Name of the file
        allowed_extensions: List of allowed extensions (e.g., ['json', 'csv'])
    
    Raises:
        ValidationError: If file extension is not allowed
    """
    if '.' not in filename:
        raise ValidationError(
            f"File must have an extension. Allowed: {', '.join(allowed_extensions)}",
            field='filename',
            details={'allowed_extensions': allowed_extensions}
        )
    
    extension = filename.rsplit('.', 1)[1].lower()
    
    if extension not in allowed_extensions:
        raise ValidationError(
            f"Invalid file extension '.{extension}'. Allowed: {', '.join(allowed_extensions)}",
            field='filename',
            details={'extension': extension, 'allowed_extensions': allowed_extensions}
        )


def validate_file_size(file_size: int, max_size_mb: int = 10) -> None:
    """
    Validate that file size is within limits.
    
    Args:
        file_size: Size of the file in bytes
        max_size_mb: Maximum allowed size in MB (default: 10)
    
    Raises:
        ValidationError: If file size exceeds limit
    """
    max_size_bytes = max_size_mb * 1024 * 1024
    
    if file_size > max_size_bytes:
        raise ValidationError(
            f"File size ({file_size / 1024 / 1024:.2f} MB) exceeds maximum allowed size ({max_size_mb} MB)",
            field='file_size',
            details={'file_size_mb': file_size / 1024 / 1024, 'max_size_mb': max_size_mb}
        )


def validate_pagination(page: Any, per_page: Any, max_per_page: int = 1000) -> Tuple[int, int]:
    """
    Validate and normalize pagination parameters.
    
    Args:
        page: Page number (can be string or int)
        per_page: Items per page (can be string or int)
        max_per_page: Maximum items per page (default: 1000)
    
    Returns:
        Tuple of (validated_page, validated_per_page)
    
    Raises:
        ValidationError: If pagination parameters are invalid
    """
    try:
        page = int(page) if page else 1
        per_page = int(per_page) if per_page else 20
    except (ValueError, TypeError):
        raise ValidationError(
            "Invalid pagination parameters. Page and per_page must be integers.",
            details={'page': page, 'per_page': per_page}
        )
    
    if page < 1:
        raise ValidationError("Page number must be greater than 0", field='page')
    
    if per_page < 1:
        raise ValidationError("Items per page must be greater than 0", field='per_page')
    
    if per_page > max_per_page:
        raise ValidationError(
            f"Items per page cannot exceed {max_per_page}",
            field='per_page',
            details={'per_page': per_page, 'max_per_page': max_per_page}
        )
    
    return page, per_page
