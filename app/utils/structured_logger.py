"""
Structured JSON logging with trace ID propagation.
Provides consistent log format for observability and log analysis.
"""
import logging
import json
import uuid
import threading
from datetime import datetime
from typing import Optional, Dict, Any

# Thread-local storage for trace context
_trace_context = threading.local()


def get_trace_id() -> str:
    """Get current trace ID or generate a new one."""
    if not hasattr(_trace_context, 'trace_id') or _trace_context.trace_id is None:
        _trace_context.trace_id = str(uuid.uuid4()).replace('-', '')[:16]
    return _trace_context.trace_id


def set_trace_id(trace_id: str):
    """Set the current trace ID."""
    _trace_context.trace_id = trace_id


def clear_trace_id():
    """Clear the current trace ID."""
    _trace_context.trace_id = None


class StructuredJsonFormatter(logging.Formatter):
    """
    JSON log formatter with structured fields.
    
    Output format:
    {
        "timestamp": "2024-01-15T10:30:00.000Z",
        "level": "ERROR",
        "logger": "webapp.api",
        "message": "Failed to query Elasticsearch",
        "context": {...},
        "trace_id": "abc123def456"
    }
    """
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            'timestamp': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'trace_id': get_trace_id()
        }
        
        # Add context if present
        if hasattr(record, 'context') and record.context:
            log_entry['context'] = record.context
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None
            }
        
        # Add source location
        log_entry['source'] = {
            'file': record.filename,
            'line': record.lineno,
            'function': record.funcName
        }
        
        return json.dumps(log_entry, default=str)


class ContextLogger(logging.LoggerAdapter):
    """Logger adapter that adds context to log messages."""
    
    def process(self, msg: str, kwargs: Dict[str, Any]):
        # Add context to the record
        extra = kwargs.get('extra', {})
        if 'context' not in extra:
            extra['context'] = {}
        
        # Merge with adapter's extra context
        if self.extra:
            extra['context'].update(self.extra)
        
        kwargs['extra'] = extra
        return msg, kwargs


def get_structured_logger(name: str, context: Optional[Dict[str, Any]] = None) -> ContextLogger:
    """
    Get a structured logger with optional context.
    
    Args:
        name: Logger name
        context: Optional context dict to include in all logs
        
    Returns:
        ContextLogger with JSON formatting
    """
    logger = logging.getLogger(name)
    return ContextLogger(logger, context or {})


def setup_structured_logging(app_logger: logging.Logger, level: int = logging.INFO):
    """
    Configure structured JSON logging for the application.
    
    Args:
        app_logger: The application logger to configure
        level: Logging level
    """
    # Create JSON handler for stdout
    json_handler = logging.StreamHandler()
    json_handler.setFormatter(StructuredJsonFormatter())
    json_handler.setLevel(level)
    
    # Add handler if not already present
    if not any(isinstance(h, logging.StreamHandler) and 
               isinstance(h.formatter, StructuredJsonFormatter) 
               for h in app_logger.handlers):
        app_logger.addHandler(json_handler)
    
    app_logger.setLevel(level)


def log_with_context(logger: logging.Logger, level: int, message: str, 
                     context: Optional[Dict[str, Any]] = None, **kwargs):
    """
    Log a message with context.
    
    Args:
        logger: Logger instance
        level: Log level
        message: Log message
        context: Context dictionary
        **kwargs: Additional logging kwargs
    """
    extra = kwargs.pop('extra', {})
    extra['context'] = context or {}
    logger.log(level, message, extra=extra, **kwargs)
