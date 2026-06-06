"""Tests for SecretDetector (ADR-013 Layer 1)."""

import pytest
from conductor_core.security import SecretDetector, SecretType


class TestSecretDetector:
    """Tests for secret detection and redaction."""
    
    @pytest.fixture
    def detector(self):
        """Create detector in non-blocking mode for testing."""
        return SecretDetector(block_on_detect=False)
    
    @pytest.fixture
    def blocking_detector(self):
        """Create detector in blocking mode."""
        return SecretDetector(block_on_detect=True)
    
    def test_github_token_detection(self, detector):
        """Test detection of GitHub tokens."""
        payload = {"token": "ghp_abcdefghijklmnopqrstuvwxyz1234567890"}
        is_clean, matches = detector.scan_input(payload)
        
        assert not is_clean
        assert len(matches) == 1
        assert matches[0].secret_type == SecretType.GITHUB_TOKEN
    
    def test_api_key_detection(self, detector):
        """Test detection of generic API keys."""
        payload = 'api_key = "0123456789abcdef0123456789abcdef0123456789abcdef"'
        is_clean, matches = detector.scan_input(payload)
        
        assert not is_clean
        assert any(m.secret_type == SecretType.API_KEY for m in matches)
    
    def test_aws_access_key_detection(self, detector):
        """Test detection of AWS access keys."""
        payload = "AKIA1234567890ABCDEF"
        is_clean, matches = detector.scan_input(payload)
        
        assert not is_clean
        assert matches[0].secret_type == SecretType.AWS_ACCESS_KEY
    
    def test_slack_token_detection(self, detector):
        """Test detection of Slack tokens."""
        payload = "xoxb-1234567890-1234567890-abcdefghijklmnop"
        is_clean, matches = detector.scan_input(payload)
        
        assert not is_clean
        assert matches[0].secret_type == SecretType.SLACK_TOKEN
    
    def test_private_key_detection(self, detector):
        """Test detection of private keys."""
        payload = "-----BEGIN PRIVATE KEY-----\nMIIEvAIBA..."
        is_clean, matches = detector.scan_input(payload)
        
        assert not is_clean
        assert matches[0].secret_type == SecretType.PRIVATE_KEY
    
    def test_clean_payload(self, detector):
        """Test that clean payloads are not flagged."""
        payload = {"name": "John", "age": 30, "email": "john@example.com"}
        is_clean, matches = detector.scan_input(payload)
        
        assert is_clean
        assert len(matches) == 0
    
    def test_nested_secret_detection(self, detector):
        """Test detection of secrets in nested structures."""
        payload = {
            "user": {
                "name": "John",
                "credentials": {
                    "api_key": "0123456789abcdef0123456789abcdef0123456789abcdef",
                    "token": "ghp_abcdefghijklmnopqrstuvwxyz1234567890"
                }
            }
        }
        is_clean, matches = detector.scan_input(payload)
        
        assert not is_clean
        assert len(matches) >= 1  # At least GitHub token
        assert any(m.secret_type == SecretType.GITHUB_TOKEN for m in matches)
    
    def test_secret_in_list(self, detector):
        """Test detection of secrets in lists."""
        payload = [
            "normal text",
            "ghp_abcdefghijklmnopqrstuvwxyz1234567890",
            "more text"
        ]
        is_clean, matches = detector.scan_input(payload)
        
        assert not is_clean
        assert matches[0].secret_type == SecretType.GITHUB_TOKEN
    
    def test_output_scanning(self, detector):
        """Test scanning of agent output."""
        context = {
            "output": "Secret token: ghp_abcdefghijklmnopqrstuvwxyz1234567890"
        }
        is_clean, matches = detector.scan_output(context)
        
        assert not is_clean
        assert matches[0].secret_type == SecretType.GITHUB_TOKEN
        assert matches[0].location == "output"
    
    def test_blocking_mode_raises_on_input(self, blocking_detector):
        """Test that blocking mode raises on secret detection in input."""
        payload = "ghp_abcdefghijklmnopqrstuvwxyz1234567890"
        
        with pytest.raises(ValueError, match="Blocking execution"):
            blocking_detector.scan_input(payload)
    
    def test_blocking_mode_raises_on_output(self, blocking_detector):
        """Test that blocking mode raises on secret detection in output."""
        context = {"output": "ghp_abcdefghijklmnopqrstuvwxyz1234567890"}
        
        with pytest.raises(ValueError, match="Blocking output"):
            blocking_detector.scan_output(context)
    
    def test_redaction(self, detector):
        """Test that secrets are properly redacted."""
        text = "My token is ghp_abcdefghijklmnopqrstuvwxyz1234567890 and api_key = 0123456789abcdef0123456789abcdef0123456789abcdef"
        redacted = detector.redact(text)
        
        assert "ghp_" not in redacted
        assert "[REDACTED-GITHUB_TOKEN]" in redacted
    
    def test_multiple_secrets_in_text(self, detector):
        """Test detection of multiple different secret types."""
        payload = {
            "github": "ghp_abcdefghijklmnopqrstuvwxyz1234567890",
            "aws": "AKIA1234567890ABCDEF",
            "slack": "xoxb-1234567890-1234567890-abcdefghijklmnop"
        }
        is_clean, matches = detector.scan_input(payload)
        
        assert not is_clean
        assert len(matches) >= 2  # At least GitHub and AWS
        assert {m.secret_type for m in matches} >= {
            SecretType.GITHUB_TOKEN,
            SecretType.AWS_ACCESS_KEY,
        }
    
    def test_secret_match_str(self, detector):
        """Test SecretMatch string representation."""
        payload = "ghp_abcdefghijklmnopqrstuvwxyz1234567890"
        is_clean, matches = detector.scan_input(payload)
        
        match_str = str(matches[0])
        assert "redacted" in match_str.lower()
        assert "input" in match_str
    
    def test_empty_payload(self, detector):
        """Test handling of empty payloads."""
        is_clean, matches = detector.scan_input("")
        assert is_clean
        assert len(matches) == 0
    
    def test_none_payload(self, detector):
        """Test handling of None payloads."""
        is_clean, matches = detector.scan_input(None)
        assert is_clean
        assert len(matches) == 0
    
    def test_integer_payload(self, detector):
        """Test handling of non-string/dict/list payloads."""
        is_clean, matches = detector.scan_input(12345)
        assert is_clean
        assert len(matches) == 0
    
    def test_path_tracking(self, detector):
        """Test that secret location paths are tracked correctly."""
        payload = {
            "user": {
                "creds": {
                    "token": "ghp_abcdefghijklmnopqrstuvwxyz1234567890"
                }
            }
        }
        is_clean, matches = detector.scan_input(payload)
        
        assert "user.creds.token" in matches[0].location
