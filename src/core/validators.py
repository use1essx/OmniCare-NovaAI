"""
Healthcare AI V2 - Comprehensive Input Validation and Sanitization
Advanced validation for healthcare data with XSS/injection prevention
"""

import re
import html
import json
import base64
try:
    import bleach
    BLEACH_AVAILABLE = True
except ImportError:
    BLEACH_AVAILABLE = False
    class bleach:
        @staticmethod
        def clean(text, tags=None, attributes=None, protocols=None, strip=False):
            import html
            return html.escape(text)
from typing import Dict, List, Any, Tuple
from urllib.parse import urlparse, unquote
import email_validator
from pydantic import validator
try:
    import magic  # python-magic for file type detection
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False
    class magic:
        @staticmethod
        def from_buffer(content, mime=True):
            return 'application/octet-stream'

from src.core.logging import get_logger
from src.core.exceptions import ValidationError


class ValidationResult:
    """Validation result with detailed information"""
    
    def __init__(self, is_valid: bool = True, errors: List[str] = None, 
                 sanitized_value: Any = None, warnings: List[str] = None):
        self.is_valid = is_valid
        self.errors = errors or []
        self.warnings = warnings or []
        self.sanitized_value = sanitized_value
    
    def add_error(self, error: str) -> None:
        """Add validation error"""
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str) -> None:
        """Add validation warning"""
        self.warnings.append(warning)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "sanitized_value": self.sanitized_value
        }


class HealthcareDataValidator:
    """Healthcare-specific data validation"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        
        # Healthcare-specific patterns
        self.hkid_pattern = re.compile(r'^[A-Z]{1,2}\d{6}\(\d\)$')
        self.medical_record_pattern = re.compile(r'^MR\d{8,12}$')
        self.prescription_pattern = re.compile(r'^RX\d{10,15}$')
        self.phone_hk_pattern = re.compile(r'^[2-9]\d{7}$|^[6-9]\d{7}$')
        
        # Medical terminology validation
        self.medical_terms = {
            'symptoms', 'diagnosis', 'treatment', 'medication', 'dosage',
            'allergy', 'condition', 'procedure', 'surgery', 'therapy'
        }
        
        # Dangerous medical terms that need special handling
        self.sensitive_terms = {
            'suicide', 'self-harm', 'overdose', 'abuse', 'emergency',
            'critical', 'severe', 'life-threatening', 'acute'
        }
    
    def validate_hk_id(self, hkid: str) -> ValidationResult:
        """Validate Hong Kong ID card number"""
        result = ValidationResult()
        
        if not hkid:
            result.add_error("HKID cannot be empty")
            return result
        
        # Remove spaces and convert to uppercase
        clean_hkid = hkid.replace(" ", "").upper()
        
        if not self.hkid_pattern.match(clean_hkid):
            result.add_error("Invalid HKID format")
            return result
        
        # Validate check digit
        if not self._validate_hkid_checksum(clean_hkid):
            result.add_error("Invalid HKID check digit")
            return result
        
        # Mask for privacy
        result.sanitized_value = clean_hkid[:2] + "****" + clean_hkid[-2:]
        return result
    
    def validate_medical_record_number(self, mrn: str) -> ValidationResult:
        """Validate medical record number"""
        result = ValidationResult()
        
        if not mrn:
            result.add_error("Medical record number cannot be empty")
            return result
        
        clean_mrn = mrn.strip().upper()
        
        if not self.medical_record_pattern.match(clean_mrn):
            result.add_error("Invalid medical record number format")
            return result
        
        result.sanitized_value = clean_mrn
        return result
    
    def validate_hk_phone(self, phone: str) -> ValidationResult:
        """Validate Hong Kong phone number"""
        result = ValidationResult()
        
        if not phone:
            result.add_error("Phone number cannot be empty")
            return result
        
        # Remove spaces, dashes, and plus signs
        clean_phone = re.sub(r'[\s\-\+\(\)]', '', phone)
        
        # Remove country code if present
        if clean_phone.startswith('852'):
            clean_phone = clean_phone[3:]
        
        if not self.phone_hk_pattern.match(clean_phone):
            result.add_error("Invalid Hong Kong phone number format")
            return result
        
        result.sanitized_value = clean_phone
        return result
    
    def validate_medical_text(self, text: str, allow_sensitive: bool = False) -> ValidationResult:
        """Validate medical text content"""
        result = ValidationResult()
        
        if not text:
            result.add_error("Medical text cannot be empty")
            return result
        
        # Basic length validation
        if len(text) > 10000:
            result.add_error("Medical text too long (max 10,000 characters)")
            return result
        
        # Check for sensitive terms
        text_lower = text.lower()
        found_sensitive = [term for term in self.sensitive_terms if term in text_lower]
        
        if found_sensitive and not allow_sensitive:
            result.add_warning(f"Contains sensitive medical terms: {', '.join(found_sensitive)}")
        
        # Sanitize HTML and remove dangerous content
        sanitized = self._sanitize_medical_text(text)
        result.sanitized_value = sanitized
        
        return result
    
    def validate_dosage(self, dosage: str) -> ValidationResult:
        """Validate medication dosage"""
        result = ValidationResult()
        
        if not dosage:
            result.add_error("Dosage cannot be empty")
            return result
        
        # Common dosage patterns
        dosage_patterns = [
            r'^\d+(\.\d+)?\s*(mg|g|ml|mcg|units?)\s*(daily|bid|tid|qid|prn)?$',
            r'^\d+\s*tablets?\s*(daily|bid|tid|qid|prn)?$',
            r'^\d+\s*drops?\s*(daily|bid|tid|qid|prn)?$'
        ]
        
        clean_dosage = dosage.strip().lower()
        
        if not any(re.match(pattern, clean_dosage, re.IGNORECASE) for pattern in dosage_patterns):
            result.add_error("Invalid dosage format")
            return result
        
        result.sanitized_value = clean_dosage
        return result
    
    def _validate_hkid_checksum(self, hkid: str) -> bool:
        """Validate HKID check digit using Hong Kong algorithm"""
        try:
            # Extract letters and digits
            letters = hkid[:2] if len(hkid) > 8 else hkid[0]
            digits = hkid[len(letters):-2]  # Exclude check digit in parentheses
            check_digit = int(hkid[-2])
            
            # Convert letters to numbers
            letter_values = {'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6, 'G': 7, 'H': 8,
                           'I': 9, 'J': 10, 'K': 11, 'L': 12, 'M': 13, 'N': 14, 'O': 15, 'P': 16,
                           'Q': 17, 'R': 18, 'S': 19, 'T': 20, 'U': 21, 'V': 22, 'W': 23, 'X': 24,
                           'Y': 25, 'Z': 26}
            
            # Calculate checksum
            total = 0
            
            # Add letter values
            if len(letters) == 2:
                total += letter_values[letters[0]] * 9
                total += letter_values[letters[1]] * 8
            else:
                total += letter_values[letters[0]] * 8
            
            # Add digit values
            for i, digit in enumerate(digits):
                total += int(digit) * (7 - i)
            
            # Calculate check digit
            remainder = total % 11
            calculated_check = 0 if remainder == 0 else 11 - remainder
            
            return calculated_check == check_digit
            
        except (KeyError, ValueError, IndexError):
            return False
    
    def _sanitize_medical_text(self, text: str) -> str:
        """Sanitize medical text while preserving medical terminology"""
        # Allow specific medical HTML tags
        allowed_tags = ['p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li']
        allowed_attributes = {}
        
        # Use bleach to sanitize
        sanitized = bleach.clean(
            text,
            tags=allowed_tags,
            attributes=allowed_attributes,
            strip=True
        )
        
        return sanitized.strip()


class SecurityValidator:
    """Security-focused input validation and sanitization"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        
        # XSS patterns
        self.xss_patterns = [
            re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL),
            re.compile(r'javascript:', re.IGNORECASE),
            re.compile(r'vbscript:', re.IGNORECASE),
            re.compile(r'on\w+\s*=', re.IGNORECASE),
            re.compile(r'expression\s*\(', re.IGNORECASE),
            re.compile(r'url\s*\(', re.IGNORECASE),
            re.compile(r'@import', re.IGNORECASE),
        ]
        
        # SQL injection patterns
        self.sql_patterns = [
            re.compile(r'(\bunion\b.*\bselect\b)', re.IGNORECASE),
            re.compile(r'(\bselect\b.*\bfrom\b)', re.IGNORECASE),
            re.compile(r'(\binsert\b.*\binto\b)', re.IGNORECASE),
            re.compile(r'(\bupdate\b.*\bset\b)', re.IGNORECASE),
            re.compile(r'(\bdelete\b.*\bfrom\b)', re.IGNORECASE),
            re.compile(r'(\bdrop\b.*\btable\b)', re.IGNORECASE),
            re.compile(r'(--|\#|/\*|\*/)', re.IGNORECASE),
        ]
        
        # Command injection patterns
        self.cmd_patterns = [
            re.compile(r';\s*(rm|del|format|fdisk)', re.IGNORECASE),
            re.compile(r';\s*(cat|type|more|less)', re.IGNORECASE),
            re.compile(r';\s*(ps|netstat|whoami|id)', re.IGNORECASE),
            re.compile(r'\|\s*(rm|del|format)', re.IGNORECASE),
            re.compile(r'&&\s*(rm|del|format)', re.IGNORECASE),
            re.compile(r'`.*`'),
            re.compile(r'\$\(.*\)'),
        ]
        
        # Path traversal patterns
        self.path_patterns = [
            re.compile(r'\.\./', re.IGNORECASE),
            re.compile(r'\.\.\\', re.IGNORECASE),
            re.compile(r'%2e%2e%2f', re.IGNORECASE),
            re.compile(r'%2e%2e%5c', re.IGNORECASE),
        ]
    
    def validate_string(self, value: str, max_length: int = 1000, 
                       allow_html: bool = False) -> ValidationResult:
        """Validate and sanitize string input"""
        result = ValidationResult()
        
        if not isinstance(value, str):
            result.add_error("Value must be a string")
            return result
        
        if len(value) > max_length:
            result.add_error(f"String too long (max {max_length} characters)")
            return result
        
        # Check for malicious patterns
        if self._contains_xss(value):
            result.add_error("Contains potential XSS content")
            return result
        
        if self._contains_sql_injection(value):
            result.add_error("Contains potential SQL injection")
            return result
        
        if self._contains_command_injection(value):
            result.add_error("Contains potential command injection")
            return result
        
        if self._contains_path_traversal(value):
            result.add_error("Contains potential path traversal")
            return result
        
        # Sanitize
        if allow_html:
            sanitized = self._sanitize_html(value)
        else:
            sanitized = html.escape(value)
        
        result.sanitized_value = sanitized.strip()
        return result
    
    def validate_email(self, email: str) -> ValidationResult:
        """Validate email address"""
        result = ValidationResult()
        
        if not email:
            result.add_error("Email cannot be empty")
            return result
        
        try:
            # Use email-validator library
            valid_email = email_validator.validate_email(email)
            result.sanitized_value = valid_email.email.lower()
        except email_validator.EmailNotValidError as e:
            result.add_error(f"Invalid email address: {str(e)}")
        
        return result
    
    def validate_url(self, url: str, allowed_schemes: List[str] = None) -> ValidationResult:
        """Validate URL"""
        result = ValidationResult()
        
        if not url:
            result.add_error("URL cannot be empty")
            return result
        
        if allowed_schemes is None:
            allowed_schemes = ['http', 'https']
        
        try:
            parsed = urlparse(url)
            
            if parsed.scheme not in allowed_schemes:
                result.add_error(f"URL scheme must be one of: {', '.join(allowed_schemes)}")
                return result
            
            if not parsed.netloc:
                result.add_error("URL must have a valid domain")
                return result
            
            # Check for suspicious patterns
            if self._contains_xss(url):
                result.add_error("URL contains potential XSS content")
                return result
            
            result.sanitized_value = url
            
        except Exception as e:
            result.add_error(f"Invalid URL format: {str(e)}")
        
        return result
    
    def validate_json(self, json_str: str, max_depth: int = 10) -> ValidationResult:
        """Validate JSON string"""
        result = ValidationResult()
        
        if not json_str:
            result.add_error("JSON cannot be empty")
            return result
        
        try:
            # Parse JSON
            data = json.loads(json_str)
            
            # Check depth
            if self._get_json_depth(data) > max_depth:
                result.add_error(f"JSON nesting too deep (max {max_depth} levels)")
                return result
            
            # Validate content
            if self._json_contains_malicious_content(data):
                result.add_error("JSON contains potentially malicious content")
                return result
            
            result.sanitized_value = data
            
        except json.JSONDecodeError as e:
            result.add_error(f"Invalid JSON format: {str(e)}")
        
        return result
    
    def validate_filename(self, filename: str) -> ValidationResult:
        """Validate uploaded filename"""
        result = ValidationResult()
        
        if not filename:
            result.add_error("Filename cannot be empty")
            return result
        
        # Check for path traversal
        if self._contains_path_traversal(filename):
            result.add_error("Filename contains path traversal characters")
            return result
        
        # Check for dangerous characters
        dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '\x00']
        if any(char in filename for char in dangerous_chars):
            result.add_error("Filename contains invalid characters")
            return result
        
        # Check for reserved names (Windows)
        reserved_names = ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 
                         'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 
                         'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9']
        
        name_without_ext = filename.split('.')[0].upper()
        if name_without_ext in reserved_names:
            result.add_error("Filename uses reserved system name")
            return result
        
        # Sanitize filename
        sanitized = re.sub(r'[^\w\-_\.]', '_', filename)
        result.sanitized_value = sanitized[:255]  # Limit length
        
        return result
    
    def validate_base64(self, b64_str: str, max_size: int = 10 * 1024 * 1024) -> ValidationResult:
        """Validate base64 encoded data"""
        result = ValidationResult()
        
        if not b64_str:
            result.add_error("Base64 string cannot be empty")
            return result
        
        try:
            # Decode base64
            decoded = base64.b64decode(b64_str, validate=True)
            
            if len(decoded) > max_size:
                result.add_error(f"Decoded data too large (max {max_size} bytes)")
                return result
            
            result.sanitized_value = b64_str
            
        except Exception as e:
            result.add_error(f"Invalid base64 encoding: {str(e)}")
        
        return result
    
    def _contains_xss(self, value: str) -> bool:
        """Check for XSS patterns"""
        return any(pattern.search(value) for pattern in self.xss_patterns)
    
    def _contains_sql_injection(self, value: str) -> bool:
        """Check for SQL injection patterns"""
        return any(pattern.search(value) for pattern in self.sql_patterns)
    
    def _contains_command_injection(self, value: str) -> bool:
        """Check for command injection patterns"""
        return any(pattern.search(value) for pattern in self.cmd_patterns)
    
    def _contains_path_traversal(self, value: str) -> bool:
        """Check for path traversal patterns"""
        decoded_value = unquote(value)
        return any(pattern.search(decoded_value) for pattern in self.path_patterns)
    
    def _sanitize_html(self, html_content: str) -> str:
        """Sanitize HTML content"""
        allowed_tags = ['p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li', 'h1', 'h2', 'h3']
        allowed_attributes = {
            'a': ['href', 'title'],
            'img': ['src', 'alt', 'width', 'height']
        }
        
        return bleach.clean(
            html_content,
            tags=allowed_tags,
            attributes=allowed_attributes,
            protocols=['http', 'https', 'mailto'],
            strip=True
        )
    
    def _get_json_depth(self, obj: Any, depth: int = 0) -> int:
        """Calculate JSON nesting depth"""
        if depth > 20:  # Prevent infinite recursion
            return depth
        
        if isinstance(obj, dict):
            return max([self._get_json_depth(v, depth + 1) for v in obj.values()] + [depth])
        elif isinstance(obj, list):
            return max([self._get_json_depth(item, depth + 1) for item in obj] + [depth])
        else:
            return depth
    
    def _json_contains_malicious_content(self, obj: Any) -> bool:
        """Check JSON for malicious content"""
        if isinstance(obj, str):
            return (self._contains_xss(obj) or 
                   self._contains_sql_injection(obj) or 
                   self._contains_command_injection(obj))
        elif isinstance(obj, dict):
            return any(self._json_contains_malicious_content(v) for v in obj.values())
        elif isinstance(obj, list):
            return any(self._json_contains_malicious_content(item) for item in obj)
        
        return False


class FileValidator:
    """File upload validation"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        
        # Allowed MIME types
        self.allowed_mime_types = {
            'application/pdf',
            'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp',
            'text/plain', 'text/csv',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/json',
            'application/zip'
        }
        
        # Dangerous file signatures
        self.dangerous_signatures = {
            b'MZ': 'PE executable',
            b'\x7fELF': 'ELF executable',
            b'\xca\xfe\xba\xbe': 'Java class file',
            b'PK\x03\x04': 'ZIP archive (check contents)',
            b'\x1f\x8b': 'GZIP compressed data'
        }
        
        # File size limits by type
        self.size_limits = {
            'image': 10 * 1024 * 1024,     # 10MB
            'document': 50 * 1024 * 1024,  # 50MB
            'archive': 100 * 1024 * 1024,  # 100MB
            'default': 10 * 1024 * 1024    # 10MB
        }
    
    def validate_file(self, file_content: bytes, filename: str, 
                     declared_mime_type: str = None) -> ValidationResult:
        """Comprehensive file validation"""
        result = ValidationResult()
        
        if not file_content:
            result.add_error("File content cannot be empty")
            return result
        
        # Validate filename
        filename_result = SecurityValidator().validate_filename(filename)
        if not filename_result.is_valid:
            result.errors.extend(filename_result.errors)
            return result
        
        # Detect actual MIME type
        try:
            actual_mime_type = magic.from_buffer(file_content, mime=True)
        except Exception:
            actual_mime_type = 'application/octet-stream'
        
        # Check if MIME type is allowed
        if actual_mime_type not in self.allowed_mime_types:
            result.add_error(f"File type not allowed: {actual_mime_type}")
            return result
        
        # Verify MIME type matches declaration
        if declared_mime_type and declared_mime_type != actual_mime_type:
            result.add_warning(f"Declared MIME type ({declared_mime_type}) doesn't match actual type ({actual_mime_type})")
        
        # Check file signature for dangerous content
        signature_check = self._check_file_signature(file_content)
        if not signature_check:
            result.add_error("File contains dangerous signature")
            return result
        
        # Check file size
        file_category = self._get_file_category(actual_mime_type)
        size_limit = self.size_limits.get(file_category, self.size_limits['default'])
        
        if len(file_content) > size_limit:
            result.add_error(f"File too large (max {size_limit} bytes for {file_category})")
            return result
        
        # Additional validation based on file type
        if actual_mime_type.startswith('image/'):
            if not self._validate_image_content(file_content):
                result.add_error("Invalid or corrupted image file")
                return result
        
        elif actual_mime_type == 'application/pdf':
            if not self._validate_pdf_content(file_content):
                result.add_error("Invalid or potentially malicious PDF file")
                return result
        
        result.sanitized_value = {
            'content': file_content,
            'filename': filename_result.sanitized_value,
            'mime_type': actual_mime_type,
            'size': len(file_content)
        }
        
        return result
    
    def _check_file_signature(self, content: bytes) -> bool:
        """Check file signature for dangerous content"""
        # Check first few bytes for dangerous signatures
        for signature, description in self.dangerous_signatures.items():
            if content.startswith(signature):
                if description == 'ZIP archive (check contents)':
                    # ZIP files need additional validation
                    return self._validate_zip_content(content)
                else:
                    # Other dangerous signatures
                    return False
        
        return True
    
    def _validate_image_content(self, content: bytes) -> bool:
        """Validate image file content"""
        try:
            # Check for embedded executables or scripts
            # This is a simplified check - in production, use a proper image library
            dangerous_patterns = [
                b'<script', b'javascript:', b'vbscript:', b'<?php'
            ]
            
            content_lower = content.lower()
            return not any(pattern in content_lower for pattern in dangerous_patterns)
            
        except Exception:
            return False
    
    def _validate_pdf_content(self, content: bytes) -> bool:
        """Validate PDF file content"""
        try:
            # Check PDF header
            if not content.startswith(b'%PDF-'):
                return False
            
            # Check for dangerous patterns in PDF
            dangerous_patterns = [
                b'/JavaScript', b'/JS', b'/OpenAction', b'/Launch',
                b'/EmbeddedFile', b'/XFA'
            ]
            
            return not any(pattern in content for pattern in dangerous_patterns)
            
        except Exception:
            return False
    
    def _validate_zip_content(self, content: bytes) -> bool:
        """Validate ZIP archive content"""
        try:
            import zipfile
            import io
            
            with zipfile.ZipFile(io.BytesIO(content), 'r') as zip_file:
                # Check for zip bombs (too many files)
                if len(zip_file.namelist()) > 100:
                    return False
                
                # Check for path traversal in filenames
                for filename in zip_file.namelist():
                    if '../' in filename or '..\\' in filename:
                        return False
                
                # Check total uncompressed size
                total_size = sum(file.file_size for file in zip_file.filelist)
                if total_size > 500 * 1024 * 1024:  # 500MB
                    return False
                
                return True
                
        except Exception:
            return False
    
    def _get_file_category(self, mime_type: str) -> str:
        """Get file category for size limits"""
        if mime_type.startswith('image/'):
            return 'image'
        elif mime_type in ['application/pdf', 'application/msword', 
                          'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
            return 'document'
        elif mime_type in ['application/zip', 'application/x-zip-compressed']:
            return 'archive'
        else:
            return 'default'


class CompositeValidator:
    """Main validator that combines all validation types"""
    
    def __init__(self):
        self.security_validator = SecurityValidator()
        self.healthcare_validator = HealthcareDataValidator()
        self.file_validator = FileValidator()
        self.logger = get_logger(__name__)
    
    def validate_user_input(self, data: Dict[str, Any], 
                           validation_rules: Dict[str, Dict] = None) -> Dict[str, ValidationResult]:
        """Validate user input data with custom rules"""
        results = {}
        
        for field, value in data.items():
            rules = validation_rules.get(field, {}) if validation_rules else {}
            
            if isinstance(value, str):
                results[field] = self.security_validator.validate_string(
                    value,
                    max_length=rules.get('max_length', 1000),
                    allow_html=rules.get('allow_html', False)
                )
            elif field == 'email':
                results[field] = self.security_validator.validate_email(value)
            elif field in ['hkid', 'hong_kong_id']:
                results[field] = self.healthcare_validator.validate_hk_id(value)
            elif field in ['medical_record_number', 'mrn']:
                results[field] = self.healthcare_validator.validate_medical_record_number(value)
            elif field in ['phone', 'phone_number']:
                results[field] = self.healthcare_validator.validate_hk_phone(value)
            elif field in ['medical_text', 'symptoms', 'diagnosis']:
                results[field] = self.healthcare_validator.validate_medical_text(
                    value, 
                    allow_sensitive=rules.get('allow_sensitive', False)
                )
            elif field == 'dosage':
                results[field] = self.healthcare_validator.validate_dosage(value)
            else:
                # Default string validation
                if isinstance(value, str):
                    results[field] = self.security_validator.validate_string(value)
                else:
                    results[field] = ValidationResult(sanitized_value=value)
        
        return results
    
    def validate_and_sanitize(self, data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], List[str]]:
        """Validate and return sanitized data"""
        validation_results = self.validate_user_input(data)
        
        all_valid = all(result.is_valid for result in validation_results.values())
        sanitized_data = {}
        all_errors = []
        
        for field, result in validation_results.items():
            if result.is_valid:
                sanitized_data[field] = result.sanitized_value
            else:
                all_errors.extend([f"{field}: {error}" for error in result.errors])
        
        return all_valid, sanitized_data, all_errors


# Global validator instance
composite_validator = CompositeValidator()


# Convenience functions for FastAPI dependencies

def validate_string_input(value: str, max_length: int = 1000) -> str:
    """Validate and sanitize string input"""
    result = composite_validator.security_validator.validate_string(value, max_length)
    if not result.is_valid:
        raise ValidationError(f"Invalid input: {', '.join(result.errors)}")
    return result.sanitized_value


def validate_email_input(email: str) -> str:
    """Validate and sanitize email input"""
    result = validator.security_validator.validate_email(email)
    if not result.is_valid:
        raise ValidationError(f"Invalid email: {', '.join(result.errors)}")
    return result.sanitized_value


def validate_hk_id_input(hkid: str) -> str:
    """Validate Hong Kong ID"""
    result = validator.healthcare_validator.validate_hk_id(hkid)
    if not result.is_valid:
        raise ValidationError(f"Invalid HKID: {', '.join(result.errors)}")
    return result.sanitized_value
