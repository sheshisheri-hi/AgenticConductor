"""Token scrubber — Remove API keys, passwords, and sensitive data from logs and outputs.

ADR-013 Tier 2: Sensitive Information Disclosure defense.
Scrubs tokens before writing to logs, audit trails, or external systems.
"""

import re
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ScrubPattern:
    """A pattern to match and scrub sensitive data."""
    name: str
    pattern: str  # Regex pattern
    replacement: str = "[REDACTED]"
    case_insensitive: bool = True


class TokenScrubber:
    """Removes sensitive data (API keys, passwords, tokens) from text and dicts."""
    
    # Default patterns for common secret types
    DEFAULT_PATTERNS = [
        # API Keys (GitHub, Azure, AWS, etc.)
        ScrubPattern(
            name="github_token",
            pattern=r"gh_[A-Za-z0-9_]{30,}",
            replacement="[REDACTED_GITHUB_TOKEN]"
        ),
        ScrubPattern(
            name="aws_access_key",
            pattern=r"AKIA[0-9A-Z]{16}",
            replacement="[REDACTED_AWS_KEY]"
        ),
        ScrubPattern(
            name="aws_secret_key",
            pattern=r"aws_secret_access_key['\"]?\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{40}",
            replacement="aws_secret_access_key = [REDACTED_AWS_SECRET]"
        ),
        # Azure patterns
        ScrubPattern(
            name="azure_connection_string",
            pattern=r"DefaultEndpointsProtocol=https;AccountName=[^;]+;AccountKey=[^;]+",
            replacement="[REDACTED_AZURE_CONNECTION_STRING]"
        ),
        # Passwords and credentials
        ScrubPattern(
            name="password_field",
            pattern=r'(?:password|passwd|pwd)["\']?\s*[:=]\s*["\']?[^"\'}\s,]+["\']?',
            replacement="password = [REDACTED]",
            case_insensitive=True
        ),
        ScrubPattern(
            name="bearer_token",
            pattern=r"Bearer\s+[A-Za-z0-9\-_.~+/]+=*",
            replacement="Bearer [REDACTED_TOKEN]",
            case_insensitive=True
        ),
        # Database connection strings
        ScrubPattern(
            name="db_password",
            pattern=r"postgresql://[^:]+:([^@]+)@",
            replacement="postgresql://[user]:[REDACTED]@",
        ),
        ScrubPattern(
            name="mongodb_connection",
            pattern=r"mongodb\+srv://[^:]+:([^@]+)@",
            replacement="mongodb+srv://[user]:[REDACTED]@",
        ),
        # JWT tokens
        ScrubPattern(
            name="jwt_token",
            pattern=r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
            replacement="[REDACTED_JWT]"
        ),
        # API keys in common formats
        ScrubPattern(
            name="api_key_generic",
            pattern=r'["\']?(?:api[_-]?key|apikey)["\']?\s*[:=]\s*["\']?[A-Za-z0-9\-_.~+/=]{20,}["\']?',
            replacement="api_key = [REDACTED]",
            case_insensitive=True
        ),
        # Authorization headers
        ScrubPattern(
            name="auth_header",
            pattern=r"Authorization['\"]?\s*:\s*['\"]?[^\s'\"]+['\"]?",
            replacement="Authorization: [REDACTED]",
            case_insensitive=True
        ),
    ]
    
    def __init__(self, patterns: Optional[List[ScrubPattern]] = None):
        """Initialize scrubber.
        
        Args:
            patterns: Custom patterns to use. If None, uses DEFAULT_PATTERNS.
        """
        self.patterns = patterns or self.DEFAULT_PATTERNS
        self._compiled_patterns = []
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Pre-compile regex patterns for performance."""
        self._compiled_patterns = []
        for pattern in self.patterns:
            flags = re.IGNORECASE if pattern.case_insensitive else 0
            try:
                compiled = re.compile(pattern.pattern, flags)
                self._compiled_patterns.append((compiled, pattern))
            except re.error as e:
                logger.warning(f"Failed to compile scrub pattern '{pattern.name}': {e}")
    
    def scrub_text(self, text: str) -> str:
        """Remove sensitive data from text.
        
        Args:
            text: Text to scrub
            
        Returns:
            Scrubbed text with sensitive data replaced
        """
        if not isinstance(text, str):
            return text
        
        result = text
        for compiled_pattern, pattern_def in self._compiled_patterns:
            result = compiled_pattern.sub(pattern_def.replacement, result)
        
        return result
    
    def scrub_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively remove sensitive data from a dictionary.
        
        Args:
            data: Dictionary to scrub
            
        Returns:
            New dictionary with sensitive values replaced
        """
        if not isinstance(data, dict):
            return data
        
        result = {}
        for key, value in data.items():
            # Skip if key looks sensitive
            if self._is_sensitive_key(key):
                result[key] = "[REDACTED]"
                continue
            
            if isinstance(value, str):
                result[key] = self.scrub_text(value)
            elif isinstance(value, dict):
                result[key] = self.scrub_dict(value)
            elif isinstance(value, (list, tuple)):
                result[key] = [
                    self.scrub_text(v) if isinstance(v, str) else self.scrub_dict(v) if isinstance(v, dict) else v
                    for v in value
                ]
            else:
                result[key] = value
        
        return result
    
    @staticmethod
    def _is_sensitive_key(key: str) -> bool:
        """Check if a key name suggests sensitive data.
        
        Args:
            key: Dictionary key
            
        Returns:
            True if key looks like it contains sensitive data
        """
        sensitive_keywords = {
            "password", "passwd", "pwd",
            "secret", "token", "api_key", "apikey",
            "authorization", "auth",
            "credential", "credentials",
            "private_key", "private", "key",
            "access_key", "secret_key",
            "connection_string", "connectionstring",
            "db_password", "database_password",
        }
        
        key_lower = key.lower()
        return any(keyword in key_lower for keyword in sensitive_keywords)
    
    def scrub_log_record(self, record: logging.LogRecord) -> logging.LogRecord:
        """Scrub a logging.LogRecord before it's written.
        
        Can be used as a logging filter.
        
        Args:
            record: LogRecord to scrub
            
        Returns:
            Modified LogRecord with sensitive data removed
        """
        if hasattr(record, "msg") and isinstance(record.msg, str):
            record.msg = self.scrub_text(record.msg)
        
        if hasattr(record, "args") and isinstance(record.args, tuple):
            record.args = tuple(
                self.scrub_text(arg) if isinstance(arg, str) else arg
                for arg in record.args
            )
        
        if hasattr(record, "exc_text") and isinstance(record.exc_text, str):
            record.exc_text = self.scrub_text(record.exc_text)
        
        return record


class ScrubFilter(logging.Filter):
    """Logging filter that applies TokenScrubber to all log records."""
    
    def __init__(self, scrubber: Optional[TokenScrubber] = None):
        """Initialize filter.
        
        Args:
            scrubber: TokenScrubber instance. If None, creates a new one.
        """
        super().__init__()
        self.scrubber = scrubber or TokenScrubber()
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Apply scrubbing to log record.
        
        Args:
            record: LogRecord to filter
            
        Returns:
            True (always passes through after scrubbing)
        """
        self.scrubber.scrub_log_record(record)
        return True


def install_scrubber(scrubber: Optional[TokenScrubber] = None):
    """Install a TokenScrubber as a logging filter globally.
    
    Args:
        scrubber: TokenScrubber instance. If None, creates a new one.
    """
    scrubber = scrubber or TokenScrubber()
    filter_instance = ScrubFilter(scrubber)
    
    # Add to root logger
    root_logger = logging.getLogger()
    root_logger.addFilter(filter_instance)
    
    # Also add to all existing handlers
    for handler in root_logger.handlers:
        handler.addFilter(filter_instance)
    
    logger.info("TokenScrubber installed as logging filter")
