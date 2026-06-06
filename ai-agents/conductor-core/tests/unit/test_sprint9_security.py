"""Tests for Sprint 9 components: token scrubbing, dependencies, validation."""

import pytest
import logging
from pathlib import Path
from pydantic import BaseModel

from conductor_core.secrets import TokenScrubber, ScrubPattern, ScrubFilter
from conductor_core.supply_chain.dependencies import DependencyScanner, DependencyVerifier, DependencyManifest
from conductor_core.decorators import validated_agent, AgentOutputValidator
from conductor_core.validation import (
    register_schema, get_schema, SchemaCatalog, validate_against_schema
)


class TestTokenScrubber:
    """Test token scrubbing functionality."""
    
    def test_scrub_github_token(self):
        """Test GitHub token detection."""
        scrubber = TokenScrubber()
        text = "My token is gh_pou_1234567890abcdefghijklmnopqrst"
        scrubbed = scrubber.scrub_text(text)
        
        assert "gh_pou_" not in scrubbed
        assert "[REDACTED" in scrubbed
    
    def test_scrub_aws_access_key(self):
        """Test AWS access key detection."""
        scrubber = TokenScrubber()
        text = "Access key: AKIAIOSFODNN7EXAMPLE"
        scrubbed = scrubber.scrub_text(text)
        
        assert "AKIA" not in scrubbed
        assert "[REDACTED" in scrubbed
    
    def test_scrub_bearer_token(self):
        """Test Bearer token detection."""
        scrubber = TokenScrubber()
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        scrubbed = scrubber.scrub_text(text)
        
        assert "eyJhbGc" not in scrubbed
        assert "Bearer" in scrubbed
    
    def test_scrub_dict_values(self):
        """Test dictionary value scrubbing."""
        scrubber = TokenScrubber()
        data = {
            "username": "alice",
            "password": "secret123",
            "api_key": "sk_live_1234567890abcdef",
        }
        scrubbed = scrubber.scrub_dict(data)
        
        assert "[REDACTED" in str(scrubbed)
        assert "secret123" not in str(scrubbed)
        assert "sk_live_" not in str(scrubbed)
    
    def test_scrub_sensitive_keys(self):
        """Test that sensitive key names are scrubbed."""
        scrubber = TokenScrubber()
        data = {
            "password": "my_password",
            "secret": "my_secret",
            "api_key": "my_key",
        }
        scrubbed = scrubber.scrub_dict(data)
        
        assert scrubbed["password"] == "[REDACTED]"
        assert scrubbed["secret"] == "[REDACTED]"
    
    def test_logging_filter(self):
        """Test TokenScrubber as logging filter."""
        scrubber = TokenScrubber()
        filter_instance = ScrubFilter(scrubber)
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Token is gh_pou_1234567890abcdefghijklmnopqrst",
            args=(),
            exc_info=None,
        )
        
        result = filter_instance.filter(record)
        assert result is True
        assert "gh_pou_" not in record.msg


class TestDependencyManifest:
    """Test dependency manifest functionality."""
    
    def test_manifest_creation(self):
        """Test DependencyManifest dataclass."""
        manifest = DependencyManifest(
            created_at="2026-06-04T00:00:00Z",
            python_version="3.13.0",
            dependencies=[
                {
                    "name": "pydantic",
                    "version": "2.5.0",
                    "hash_sha256": "abc123",
                    "location": "/path/to/site-packages",
                }
            ]
        )
        
        assert manifest.python_version == "3.13.0"
        assert len(manifest.dependencies) == 1
        assert manifest.dependencies[0]["name"] == "pydantic"
    
    def test_manifest_to_json(self):
        """Test JSON serialization."""
        manifest = DependencyManifest(
            created_at="2026-06-04T00:00:00Z",
            python_version="3.13.0",
            dependencies=[]
        )
        
        json_str = manifest.to_json()
        assert "2026-06-04" in json_str
        assert "3.13.0" in json_str


class TestValidatedAgent:
    """Test @validated_agent decorator."""
    
    def test_valid_output(self):
        """Test decorator accepts valid output."""
        class TestOutput(BaseModel):
            code: str
            confidence: float
        
        @validated_agent(TestOutput)
        def my_agent():
            return {"code": "hello()", "confidence": 0.95}
        
        result = my_agent()
        assert isinstance(result, TestOutput)
        assert result.code == "hello()"
        assert result.confidence == 0.95
    
    def test_invalid_output_no_raise(self):
        """Test decorator rejects invalid output (no raise)."""
        class TestOutput(BaseModel):
            code: str
            confidence: float
        
        @validated_agent(TestOutput, raise_on_invalid=False)
        def my_agent():
            return {"code": 123, "confidence": "high"}  # Invalid!
        
        # Should return original dict, not raise
        result = my_agent()
        assert result == {"code": 123, "confidence": "high"}
    
    def test_invalid_output_raise(self):
        """Test decorator raises on invalid output."""
        class TestOutput(BaseModel):
            code: str
            confidence: float
        
        @validated_agent(TestOutput, raise_on_invalid=True)
        def my_agent():
            return {"code": 123}  # Missing confidence, invalid types
        
        with pytest.raises(ValueError):
            my_agent()


class TestAgentOutputValidator:
    """Test batch validation."""
    
    def test_batch_validate(self):
        """Test validating multiple outputs."""
        class Output1(BaseModel):
            text: str
        
        class Output2(BaseModel):
            number: int
        
        validator = AgentOutputValidator()
        
        # Validate multiple
        validator.validate("agent1", {"text": "hello"}, Output1)
        validator.validate("agent2", {"number": 42}, Output2)
        
        summary = validator.get_summary()
        assert summary.total_validated == 2
        assert summary.successful == 2
        assert summary.failed == 0
    
    def test_validation_with_failures(self):
        """Test validation tracking failures."""
        class Output(BaseModel):
            value: int
        
        validator = AgentOutputValidator()
        
        validator.validate("agent1", {"value": 42}, Output)
        validator.validate("agent2", {"value": "not_int"}, Output)
        
        summary = validator.get_summary()
        assert summary.successful == 1
        assert summary.failed == 1


class TestSchemaCatalog:
    """Test schema registry."""
    
    def test_register_schema(self):
        """Test schema registration."""
        catalog = SchemaCatalog()
        
        class MySchema(BaseModel):
            field: str
        
        catalog.register("my_agent", MySchema)
        
        retrieved = catalog.get("my_agent")
        assert retrieved == MySchema
    
    def test_list_schemas(self):
        """Test listing all schemas."""
        catalog = SchemaCatalog()
        
        class Schema1(BaseModel):
            a: str
        
        class Schema2(BaseModel):
            b: int
        
        catalog.register("agent1", Schema1)
        catalog.register("agent2", Schema2)
        
        schemas = catalog.list_schemas()
        assert "agent1" in schemas
        assert "agent2" in schemas
        assert schemas["agent1"] == "Schema1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
