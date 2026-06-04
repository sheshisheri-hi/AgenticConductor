"""mTLS certificate management for A2A server security.

ADR-011 Tier 3: Mutual TLS authentication between agents.
Provides certificate generation, loading, and validation.
"""

import logging
import json
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CertificateInfo:
    """Information about a certificate."""
    subject: str
    issuer: str
    valid_from: str
    valid_until: str
    fingerprint: str
    common_name: str


class CertificateManager:
    """Manage mTLS certificates for A2A agents.
    
    Handles:
    - Certificate generation
    - Certificate loading and validation
    - Certificate expiration tracking
    """
    
    def __init__(self, cert_dir: Path):
        """Initialize certificate manager.
        
        Args:
            cert_dir: Directory to store certificates
        """
        self.cert_dir = Path(cert_dir)
        self.cert_dir.mkdir(parents=True, exist_ok=True)
        
        self.ca_cert_path = self.cert_dir / "ca-cert.pem"
        self.ca_key_path = self.cert_dir / "ca-key.pem"
    
    def generate_ca_certificate(self, common_name: str = "Conductor-CA") -> bool:
        """Generate a self-signed CA certificate.
        
        Args:
            common_name: Common name for the CA
        
        Returns:
            True if successful
        """
        try:
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
            from datetime import datetime, timedelta
            
            # Generate private key
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend(),
            )
            
            # Create certificate
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, common_name),
            ])
            
            cert = x509.CertificateBuilder().subject_name(
                subject
            ).issuer_name(
                issuer
            ).public_key(
                private_key.public_key()
            ).serial_number(
                x509.random_serial_number()
            ).not_valid_before(
                datetime.utcnow()
            ).not_valid_after(
                datetime.utcnow() + timedelta(days=365)
            ).add_extension(
                x509.BasicConstraints(ca=True, path_length=0),
                critical=True,
            ).sign(private_key, hashes.SHA256(), default_backend())
            
            # Save certificate
            with open(self.ca_cert_path, "wb") as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))
            
            # Save private key
            with open(self.ca_key_path, "wb") as f:
                f.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                ))
            
            logger.info(f"Generated CA certificate: {self.ca_cert_path}")
            return True
        
        except ImportError:
            logger.error("cryptography library not installed")
            return False
        except Exception as e:
            logger.error(f"Failed to generate CA certificate: {e}")
            return False
    
    def generate_agent_certificate(
        self,
        agent_id: str,
        common_name: Optional[str] = None,
    ) -> Tuple[Optional[Path], Optional[Path]]:
        """Generate a certificate for an agent, signed by the CA.
        
        Args:
            agent_id: Unique agent identifier
            common_name: Common name (default: agent_id)
        
        Returns:
            (cert_path, key_path) or (None, None) on failure
        """
        try:
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
            from datetime import datetime, timedelta
            
            # Check CA exists
            if not self.ca_cert_path.exists() or not self.ca_key_path.exists():
                logger.error("CA certificate not found")
                return None, None
            
            common_name = common_name or agent_id
            
            # Generate agent private key
            agent_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend(),
            )
            
            # Load CA certificate and key
            with open(self.ca_cert_path, "rb") as f:
                ca_cert_data = f.read()
            
            from cryptography.hazmat.primitives.serialization import load_pem_x509_certificate
            ca_cert = load_pem_x509_certificate(ca_cert_data, default_backend())
            
            with open(self.ca_key_path, "rb") as f:
                ca_key_data = f.read()
            
            from cryptography.hazmat.primitives.serialization import load_pem_private_key
            ca_key = load_pem_private_key(ca_key_data, password=None, backend=default_backend())
            
            # Create agent certificate
            subject = x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, common_name),
            ])
            
            agent_cert = x509.CertificateBuilder().subject_name(
                subject
            ).issuer_name(
                ca_cert.subject
            ).public_key(
                agent_key.public_key()
            ).serial_number(
                x509.random_serial_number()
            ).not_valid_before(
                datetime.utcnow()
            ).not_valid_after(
                datetime.utcnow() + timedelta(days=365)
            ).add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            ).add_extension(
                x509.ExtendedKeyUsage([
                    x509.ExtendedKeyUsageOID.SERVER_AUTH,
                    x509.ExtendedKeyUsageOID.CLIENT_AUTH,
                ]),
                critical=False,
            ).sign(ca_key, hashes.SHA256(), default_backend())
            
            # Save agent certificate
            cert_path = self.cert_dir / f"{agent_id}-cert.pem"
            with open(cert_path, "wb") as f:
                f.write(agent_cert.public_bytes(serialization.Encoding.PEM))
            
            # Save agent key
            key_path = self.cert_dir / f"{agent_id}-key.pem"
            with open(key_path, "wb") as f:
                f.write(agent_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                ))
            
            logger.info(f"Generated agent certificate for {agent_id}")
            return cert_path, key_path
        
        except ImportError:
            logger.error("cryptography library not installed")
            return None, None
        except Exception as e:
            logger.error(f"Failed to generate agent certificate: {e}")
            return None, None
    
    def get_certificate_info(self, cert_path: Path) -> Optional[CertificateInfo]:
        """Get information about a certificate.
        
        Args:
            cert_path: Path to certificate file
        
        Returns:
            CertificateInfo or None
        """
        try:
            from cryptography.hazmat.primitives.serialization import load_pem_x509_certificate
            from cryptography.hazmat.backends import default_backend
            from cryptography.x509.oid import NameOID
            
            with open(cert_path, "rb") as f:
                cert_data = f.read()
            
            cert = load_pem_x509_certificate(cert_data, default_backend())
            
            # Extract common name
            common_name = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
            
            return CertificateInfo(
                subject=cert.subject.rfc4514_string(),
                issuer=cert.issuer.rfc4514_string(),
                valid_from=cert.not_valid_before.isoformat(),
                valid_until=cert.not_valid_after.isoformat(),
                fingerprint=cert.fingerprint(hashes.SHA256()).hex(),
                common_name=common_name,
            )
        
        except Exception as e:
            logger.error(f"Failed to read certificate: {e}")
            return None


def setup_mtls_for_environment(conductor_root: Path) -> Tuple[bool, Optional[Path]]:
    """Set up mTLS for a Conductor environment.
    
    Creates CA and initial certificates.
    
    Args:
        conductor_root: Root directory for Conductor project
    
    Returns:
        (success, cert_dir)
    """
    cert_dir = conductor_root / ".conductor" / "certs"
    manager = CertificateManager(cert_dir)
    
    # Generate CA if not exists
    if not manager.ca_cert_path.exists():
        if not manager.generate_ca_certificate():
            return False, None
    
    logger.info(f"mTLS environment ready at {cert_dir}")
    return True, cert_dir
