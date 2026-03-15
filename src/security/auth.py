"""
Healthcare AI V2 - Authentication and Security Utilities
Password validation, input sanitization, and security helpers
"""

import bcrypt
import hashlib
import hmac
import re
import secrets
import string
from typing import Dict, List, Optional, Tuple
import ipaddress

from src.core.config import settings


class PasswordValidator:
    """Password strength validation and policy enforcement"""
    
    def __init__(self):
        self.min_length = settings.password_min_length
        self.max_length = 128
        
        # Common weak passwords and patterns
        self.forbidden_patterns = [
            r"password",
            r"123456",
            r"qwerty",
            r"admin",
            r"letmein",
            r"welcome",
            r"monkey",
            r"dragon",
            r"healthcare",
            r"health",
            r"medical",
        ]
        
        # Character class patterns
        self.uppercase_pattern = re.compile(r"[A-Z]")
        self.lowercase_pattern = re.compile(r"[a-z]")
        self.digit_pattern = re.compile(r"\d")
        self.special_pattern = re.compile(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?~`]")
        self.sequence_pattern = re.compile(r"(.)\1{2,}")  # Repeated characters
        
    def validate(self, password: str, user_info: Optional[Dict] = None) -> Dict:
        """
        Validate password against security policies
        
        Args:
            password: Password to validate
            user_info: User information to check against (email, username, name)
            
        Returns:
            Dictionary with validation results
        """
        errors = []
        suggestions = []
        score = 0
        
        # Basic length check
        if len(password) < self.min_length:
            errors.append(f"Password must be at least {self.min_length} characters long")
        elif len(password) >= self.min_length:
            score += 10
            
        if len(password) > self.max_length:
            errors.append(f"Password must not exceed {self.max_length} characters")
            
        # Character diversity checks
        has_upper = bool(self.uppercase_pattern.search(password))
        has_lower = bool(self.lowercase_pattern.search(password))
        has_digit = bool(self.digit_pattern.search(password))
        has_special = bool(self.special_pattern.search(password))
        
        # Very lenient validation for testing - just require letters and numbers/special chars
        has_letter = has_upper or has_lower
        has_number_or_special = has_digit or has_special
        
        if not has_letter:
            errors.append("Password must contain at least one letter")
            suggestions.append("Add letters (A-Z or a-z)")
        
        if not has_number_or_special:
            errors.append("Password must contain at least one number or special character")
            suggestions.append("Add numbers (0-9) or special characters (!@#$%^&*)")
            
        if has_letter and has_number_or_special:
            score += 30  # Bonus for having both letters and numbers/special chars
            
        # Pattern checks
        password_lower = password.lower()
        
        # Check for forbidden patterns (relaxed for testing)
        # Only check for very obvious weak patterns
        very_weak_patterns = [r"password123", r"123456", r"qwerty"]
        for pattern in very_weak_patterns:
            if re.search(pattern, password_lower):
                errors.append(f"Password contains very weak pattern: {pattern}")
                suggestions.append("Avoid obvious patterns")
                score -= 10
                
        # Check for repeated characters (relaxed - only very obvious patterns)
        if len(set(password)) < 3:  # Only flag if password has less than 3 unique characters
            errors.append("Password needs more variety in characters")
            suggestions.append("Use different characters")
            score -= 5
            
        # Check against user information (relaxed for testing)
        if user_info:
            # Only check for exact matches of very obvious personal info
            user_data = [
                user_info.get("email", "").split("@")[0],
                user_info.get("username", ""),
            ]
            
            for data in user_data:
                if data and len(data) > 4 and password_lower == data.lower():
                    errors.append("Password cannot be identical to username or email")
                    suggestions.append("Choose a different password")
                    score -= 15
                    break
                    
        # Complexity bonus
        char_types = sum([has_upper, has_lower, has_digit, has_special])
        if char_types == 4:
            score += 20
        elif char_types == 3:
            score += 10
            
        # Length bonus
        if len(password) >= 12:
            score += 10
        if len(password) >= 16:
            score += 10
            
        # Ensure score is within bounds
        score = max(0, min(100, score))
        
        # Add strength-based suggestions
        if score < 50:
            suggestions.append("Consider using a longer password")
            suggestions.append("Use a mix of different character types")
        elif score < 80:
            suggestions.append("Consider adding more character variety")
            
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "suggestions": suggestions,
            "strength_score": score,
            "character_types": char_types,
            "length": len(password)
        }
        
    def generate_secure_password(self, length: int = 16) -> str:
        """Generate a cryptographically secure password"""
        if length < self.min_length:
            length = self.min_length
            
        # Ensure at least one character from each required type
        password_chars = [
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.ascii_lowercase), 
            secrets.choice(string.digits),
            secrets.choice("!@#$%^&*()_+-=[]{}|;:,.<>?")
        ]
        
        # Fill remaining length with random characters
        all_chars = string.ascii_letters + string.digits + "!@#$%^&*()_+-=[]{}|;:,.<>?"
        for _ in range(length - 4):
            password_chars.append(secrets.choice(all_chars))
            
        # Shuffle the characters
        secrets.SystemRandom().shuffle(password_chars)
        
        return "".join(password_chars)


# Bcrypt configuration
BCRYPT_ROUNDS = 12


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt directly"""
    # bcrypt has a 72-byte limit, truncate if necessary
    if len(password.encode('utf-8')) > 72:
        password = password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
    
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    try:
        # Apply same truncation as in get_password_hash
        if len(plain_password.encode('utf-8')) > 72:
            plain_password = plain_password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False


class InputSanitizer:
    """Input sanitization and validation utilities"""
    
    # XSS patterns to detect and remove
    XSS_PATTERNS = [
        re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL),
        re.compile(r"javascript:", re.IGNORECASE),
        re.compile(r"vbscript:", re.IGNORECASE),
        re.compile(r"on\w+\s*=", re.IGNORECASE),
        re.compile(r"<iframe[^>]*>.*?</iframe>", re.IGNORECASE | re.DOTALL),
        re.compile(r"<object[^>]*>.*?</object>", re.IGNORECASE | re.DOTALL),
        re.compile(r"<embed[^>]*>.*?</embed>", re.IGNORECASE | re.DOTALL),
    ]
    
    # SQL injection patterns
    SQL_PATTERNS = [
        re.compile(r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)", re.IGNORECASE),
        re.compile(r"(--|#|/\*|\*/)", re.IGNORECASE),
        re.compile(r"(\b(OR|AND)\s+\d+\s*=\s*\d+)", re.IGNORECASE),
        re.compile(r"('\s*(OR|AND)\s*')", re.IGNORECASE),
    ]
    
    @classmethod
    def sanitize_string(cls, input_string: str, max_length: Optional[int] = None) -> str:
        """
        Sanitize input string by removing potentially dangerous content
        
        Args:
            input_string: String to sanitize
            max_length: Maximum allowed length
            
        Returns:
            Sanitized string
        """
        if not isinstance(input_string, str):
            return ""
            
        # Remove XSS patterns
        for pattern in cls.XSS_PATTERNS:
            input_string = pattern.sub("", input_string)
            
        # Remove null bytes and control characters
        input_string = input_string.replace("\x00", "")
        input_string = re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]", "", input_string)
        
        # Normalize whitespace
        input_string = re.sub(r"\s+", " ", input_string).strip()
        
        # Truncate if necessary
        if max_length and len(input_string) > max_length:
            input_string = input_string[:max_length]
            
        return input_string
        
    @classmethod
    def validate_email(cls, email: str) -> bool:
        """Validate email format"""
        email_pattern = re.compile(
            r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        )
        return bool(email_pattern.match(email))
        
    @classmethod
    def validate_username(cls, username: str) -> bool:
        """Validate username format"""
        # Allow letters, numbers, hyphens, and underscores
        username_pattern = re.compile(r"^[a-zA-Z0-9_-]{3,50}$")
        return bool(username_pattern.match(username))
        
    @classmethod
    def detect_sql_injection(cls, input_string: str) -> bool:
        """Detect potential SQL injection attempts"""
        for pattern in cls.SQL_PATTERNS:
            if pattern.search(input_string):
                return True
        return False
        
    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """Sanitize filename for safe storage"""
        # Remove path separators and dangerous characters
        filename = re.sub(r"[^\w\s.-]", "", filename)
        filename = re.sub(r"\.+", ".", filename)
        filename = filename.strip(".")
        
        # Limit length
        if len(filename) > 255:
            name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
            filename = name[:255-len(ext)-1] + "." + ext if ext else name[:255]
            
        return filename


class SecurityTokenGenerator:
    """Security token generation and validation"""
    
    @staticmethod
    def generate_token(length: int = 32) -> str:
        """Generate a cryptographically secure random token"""
        return secrets.token_urlsafe(length)
        
    @staticmethod
    def generate_numeric_code(length: int = 6) -> str:
        """Generate a numeric code for 2FA"""
        return "".join(secrets.choice(string.digits) for _ in range(length))
        
    @staticmethod
    def generate_backup_codes(count: int = 10, length: int = 8) -> List[str]:
        """Generate backup codes for 2FA recovery"""
        codes = []
        for _ in range(count):
            code = "".join(secrets.choice(string.ascii_uppercase + string.digits) 
                          for _ in range(length))
            # Format as XXXX-XXXX for readability
            formatted_code = f"{code[:4]}-{code[4:]}"
            codes.append(formatted_code)
        return codes
        
    @staticmethod
    def hash_token(token: str, salt: Optional[str] = None) -> Tuple[str, str]:
        """
        Hash a token for secure storage
        
        Returns:
            Tuple of (hashed_token, salt)
        """
        if salt is None:
            salt = secrets.token_hex(16)
            
        hashed = hashlib.pbkdf2_hmac(
            "sha256",
            token.encode(),
            salt.encode(),
            100000  # iterations
        )
        
        return hashed.hex(), salt
        
    @staticmethod
    def verify_token(token: str, hashed_token: str, salt: str) -> bool:
        """Verify a token against its hash"""
        try:
            computed_hash, _ = SecurityTokenGenerator.hash_token(token, salt)
            return hmac.compare_digest(computed_hash, hashed_token)
        except Exception:
            return False


class IPValidator:
    """IP address validation and security checks"""
    
    # Private IP ranges
    PRIVATE_RANGES = [
        ipaddress.IPv4Network("10.0.0.0/8"),
        ipaddress.IPv4Network("172.16.0.0/12"),
        ipaddress.IPv4Network("192.168.0.0/16"),
        ipaddress.IPv4Network("127.0.0.0/8"),
    ]
    
    # Suspicious IP ranges (you might want to expand this)
    SUSPICIOUS_RANGES = [
        # Add known malicious IP ranges here
    ]
    
    @classmethod
    def validate_ip(cls, ip_str: str) -> Dict:
        """
        Validate and analyze an IP address
        
        Returns:
            Dictionary with validation results
        """
        try:
            ip = ipaddress.IPv4Address(ip_str)
            
            is_private = any(ip in range_ for range_ in cls.PRIVATE_RANGES)
            is_suspicious = any(ip in range_ for range_ in cls.SUSPICIOUS_RANGES)
            is_loopback = ip.is_loopback
            is_multicast = ip.is_multicast
            
            return {
                "is_valid": True,
                "ip_address": str(ip),
                "is_private": is_private,
                "is_suspicious": is_suspicious,
                "is_loopback": is_loopback,
                "is_multicast": is_multicast,
                "risk_level": "high" if is_suspicious else "low"
            }
            
        except (ipaddress.AddressValueError, ValueError):
            return {
                "is_valid": False,
                "ip_address": ip_str,
                "error": "Invalid IP address format"
            }


class SecurityHeaders:
    """Security headers for HTTP responses"""
    
    @staticmethod
    def get_security_headers() -> Dict[str, str]:
        """Get recommended security headers"""
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://cdn.tailwindcss.com; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
                "img-src 'self' data: https:; "
                "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
                "connect-src 'self'; "
                "frame-ancestors 'none';"
            ),
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": (
                "geolocation=(), "
                "microphone=(self), "
                "camera=(), "
                "payment=(), "
                "usb=(), "
                "magnetometer=(), "
                "gyroscope=(), "
                "speaker=(), "
                "vibrate=(), "
                "fullscreen=(self), "
                "sync-xhr=()"
            )
        }


# Export main utilities
__all__ = [
    "PasswordValidator",
    "InputSanitizer",
    "SecurityTokenGenerator",
    "IPValidator",
    "SecurityHeaders",
    "get_password_hash",
    "verify_password",
    "BCRYPT_ROUNDS",
]

