import logging
import sys
import json
from datetime import datetime, timezone
from typing import Any

class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that outputs log records as single-line JSON.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Include exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            
        # Add extra fields if passed via extra={}
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict): # type: ignore
            log_data.update(record.extra_fields)
            
        return json.dumps(log_data)

def setup_logging(level: str = "INFO") -> None:
    """
    Configure the root logger to output structured JSON logs to standard output.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(StructuredFormatter())
    root_logger.addHandler(console_handler)

    # Disable excessive logs from third-party libraries unless debug
    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("uvicorn.access").propagate = True
    logging.getLogger("motor").setLevel(logging.WARNING)
    
    logging.info("Structured logging initialized")
