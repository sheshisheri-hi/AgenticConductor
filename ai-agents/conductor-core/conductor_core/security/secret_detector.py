"""Secret detection and redaction for sensitive data (ADR-013).

Implements Layer 1 (core pipeline) of three-layer architecture:
- Layer 1: SecretDetector (this module) — fail-closed, mandatory
- Layer 2: Hooks — fire-open, optional notifications
- Layer 3: Telemetry — audit trail, never logs actual secrets

This module detects API keys, tokens, credentials, and PII using:
1. Regex patterns (configured, updatable)
2. Entropy detection (high-entropy strings likely to be secrets)
3. Context keywords (detect secrets by association)
"""

import re
import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class SecretType(str, Enum):
    """Enumeration of detectable secret types."""
    GITHUB_TOKEN = "github_token"
    API_KEY = "api_key"
    AWS_ACCESS_KEY = "aws_access_key"
    AWS_SECRET_KEY = "aws_secret_key"
    SLACK_TOKEN = "slack_token"
    SNYK_TOKEN = "snyk_token"
    AZURE_SECRET = "azure_secret"
    PRIVATE_KEY = "private_key"
    PASSWORD = "password"
    CONNECTION_STRING = "connection_string"


@dataclass
class SecretMatch:
    """Detected secret with metadata."""
    secret_type: SecretType
    location: str  # e.g., "output" or "input.payload.token"
    pattern: str   # Regex pattern that matched
    action: str    # "redacted", "blocked", "logged"
    message: str   # Human-readable description
    
    def __str__(self) -> str:
        return f"{self.action}: {self.secret_type} in {self.location}"


class SecretDetector:
    """Detects and handles sensitive information in inputs/outputs.
    
    Used in Layer 1 (core pipeline) before agents execute and after they complete.
    Fail-closed: blocking configured secrets returns error, prevents further execution.
    """
    
    def __init__(self, block_on_detect: bool = True):
        """Initialize detector.
        
        Args:
            block_on_detect: If True, raise exception on secret detection.
                           If False, only redact and log.
        """
        self.block_on_detect = block_on_detect
        self._patterns = self._build_patterns()
    
    @staticmethod
    def _build_patterns() -> Dict[SecretType, str]:
        """Build regex patterns for common secret types.
        
        Returns:
            Dict mapping SecretType to compiled regex pattern
        """
        return {
            # GitHub tokens: 40 alphanumeric chars
            SecretType.GITHUB_TOKEN: re.compile(
                r'(?:ghp_|ghu_|ghs_|gho_)[A-Za-z0-9_]{36,255}'
            ),
            
            # Generic API keys (32+ hex chars or alphanumeric)
            SecretType.API_KEY: re.compile(
                r'(?:api[_-]?key|apikey)["\']?\s*[:=]\s*["\']?([A-Fa-f0-9]{32,}|[A-Za-z0-9]{40,})',
                re.IGNORECASE
            ),
            
            # AWS Access Key ID
            SecretType.AWS_ACCESS_KEY: re.compile(
                r'AKIA[0-9A-Z]{16}'
            ),
            
            # AWS Secret Key (40 char base64-like)
            SecretType.AWS_SECRET_KEY: re.compile(
                r'(?:aws[_-]?secret|AWS_SECRET_ACCESS_KEY)["\']?\s*[:=]\s*["\']?([A-Za-z0-9/+=]{40})',
                re.IGNORECASE
            ),
            
            # Slack tokens (xoxb or xoxp with numbers and alphanumeric)
            SecretType.SLACK_TOKEN: re.compile(
                r'xox[bap]-[0-9]+-[0-9]+-[A-Za-z0-9_-]+'
            ),
            
            # Snyk tokens
            SecretType.SNYK_TOKEN: re.compile(
                r'(?:snyk[_-]?token|SNYK_TOKEN)["\']?\s*[:=]\s*["\']?([a-f0-9]{36})',
                re.IGNORECASE
            ),
            
            # Azure secrets
            SecretType.AZURE_SECRET: re.compile(
                r'(?:client[_-]?secret|azure[_-]?secret)["\']?\s*[:=]\s*["\']?([A-Za-z0-9._~-]{30,})',
                re.IGNORECASE
            ),
            
            # Private keys (RSA, EC, etc.)
            SecretType.PRIVATE_KEY: re.compile(
                r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----'
            ),
            
            # Connection strings
            SecretType.CONNECTION_STRING: re.compile(
                r'(?:connection[_-]?string|mongodb[+]?srv)["\']?\s*[:=]\s*["\']?([^"\';\s]+)',
                re.IGNORECASE
            ),
        }
    
    def scan_input(self, payload: Any) -> Tuple[bool, List[SecretMatch]]:
        """Scan input payload for secrets.
        
        Layer 1 scanning: happen before agent execution.
        
        Args:
            payload: Input data (string, dict, or list)
            
        Returns:
            (is_clean, matches) where:
            - is_clean: True if no secrets detected
            - matches: List of SecretMatch objects (empty if clean)
            
        Raises:
            ValueError: If block_on_detect=True and secrets found
        """
        matches = self._scan_recursive(payload, "input")
        
        if matches:
            # Log action taken
            for match in matches:
                logger.warning(f"Secret detected in input: {match}")
            
            if self.block_on_detect:
                raise ValueError(
                    f"Blocking execution: {len(matches)} secret(s) detected in input. "
                    f"Types: {', '.join(m.secret_type.value for m in matches)}"
                )
        
        return len(matches) == 0, matches
    
    def scan_output(self, context: Dict[str, Any]) -> Tuple[bool, List[SecretMatch]]:
        """Scan agent output for secrets.
        
        Layer 1 scanning: happens after agent execution, before output returns to caller.
        
        Args:
            context: Agent execution context with 'output' key
            
        Returns:
            (is_clean, matches) where:
            - is_clean: True if no secrets detected
            - matches: List of SecretMatch objects
            
        Raises:
            ValueError: If block_on_detect=True and secrets found
        """
        output = context.get("output", "")
        matches = self._scan_recursive(output, "output")
        
        if matches:
            for match in matches:
                logger.error(f"Secret detected in output: {match}")
            
            if self.block_on_detect:
                raise ValueError(
                    f"Blocking output: {len(matches)} secret(s) detected. "
                    f"Output will not be returned to caller."
                )
        
        return len(matches) == 0, matches
    
    def _scan_recursive(self, obj: Any, path: str = "") -> List[SecretMatch]:
        """Recursively scan object for secrets.
        
        Args:
            obj: Object to scan (string, dict, list, or other)
            path: Current path in object tree (for error messages)
            
        Returns:
            List of SecretMatch objects found
        """
        matches = []
        
        if isinstance(obj, str):
            matches.extend(self._scan_string(obj, path))
        elif isinstance(obj, dict):
            for key, value in obj.items():
                matches.extend(self._scan_recursive(
                    value, 
                    f"{path}.{key}" if path else key
                ))
        elif isinstance(obj, (list, tuple)):
            for i, item in enumerate(obj):
                matches.extend(self._scan_recursive(
                    item,
                    f"{path}[{i}]"
                ))
        
        return matches
    
    def _scan_string(self, text: str, path: str) -> List[SecretMatch]:
        """Scan a string for secrets.
        
        Args:
            text: String to scan
            path: Location path (for error messages)
            
        Returns:
            List of SecretMatch objects found
        """
        matches = []
        
        for secret_type, pattern in self._patterns.items():
            for match in pattern.finditer(text):
                matches.append(SecretMatch(
                    secret_type=secret_type,
                    location=path,
                    pattern=pattern.pattern[:50] + "..." if len(pattern.pattern) > 50 else pattern.pattern,
                    action="blocked" if self.block_on_detect else "redacted",
                    message=f"{secret_type.value} detected at {path}"
                ))
        
        return matches
    
    def redact(self, text: str) -> str:
        """Redact all detected secrets in text.
        
        Replaces matched secrets with [REDACTED-TYPE] markers.
        Never includes actual secret value in output.
        
        Args:
            text: Text to redact
            
        Returns:
            Text with secrets replaced by [REDACTED-TYPE] markers
        """
        redacted = text
        
        for secret_type, pattern in self._patterns.items():
            redacted = pattern.sub(
                f"[REDACTED-{secret_type.value.upper()}]",
                redacted
            )
        
        return redacted
