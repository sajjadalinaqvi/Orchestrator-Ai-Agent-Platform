import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class FilterResult(Enum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    MODIFIED = "modified"


@dataclass
class GuardrailResult:
    result: FilterResult
    content: str
    violations: List[str]
    confidence: float
    metadata: Dict[str, Any]


class PIIRedactor:
    """Redact personally identifiable information from text"""

    def __init__(self):
        # Common PII patterns
        self.patterns = {
            'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            'phone': re.compile(r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b'),
            'ssn': re.compile(r'\b\d{3}-?\d{2}-?\d{4}\b'),
            'credit_card': re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
            'ip_address': re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'),
            'url': re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'),
        }

        # Replacement patterns
        self.replacements = {
            'email': '[EMAIL_REDACTED]',
            'phone': '[PHONE_REDACTED]',
            'ssn': '[SSN_REDACTED]',
            'credit_card': '[CREDIT_CARD_REDACTED]',
            'ip_address': '[IP_REDACTED]',
            'url': '[URL_REDACTED]',
        }

    def redact_pii(self, text: str) -> Tuple[str, List[str]]:
        """Redact PII from text and return redacted text and list of violations"""
        violations = []
        redacted_text = text

        for pii_type, pattern in self.patterns.items():
            matches = pattern.findall(text)
            if matches:
                violations.extend([f"{pii_type}: {match}" for match in matches])
                redacted_text = pattern.sub(self.replacements[pii_type], redacted_text)

        return redacted_text, violations


class ToxicityFilter:
    """Simple toxicity filter using keyword matching"""

    def __init__(self):
        # Basic toxic keywords (in a real system, use a proper ML model)
        self.toxic_keywords = {
            'hate_speech': ['hate', 'nazi', 'terrorist'],
            'profanity': ['damn', 'hell'],  # Very basic list
            'harassment': ['stupid', 'idiot', 'moron'],
            'violence': ['kill', 'murder', 'bomb', 'attack']
        }

        # Severity levels
        self.severity_weights = {
            'hate_speech': 1.0,
            'violence': 0.9,
            'harassment': 0.6,
            'profanity': 0.3
        }

    def check_toxicity(self, text: str, threshold: float = 0.7) -> Tuple[bool, float, List[str]]:
        """Check if text contains toxic content"""
        text_lower = text.lower()
        violations = []
        max_severity = 0.0

        for category, keywords in self.toxic_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    violations.append(f"{category}: {keyword}")
                    max_severity = max(max_severity, self.severity_weights[category])

        is_toxic = max_severity >= threshold
        return is_toxic, max_severity, violations


class ContentGuardrails:
    """Main guardrails system that combines multiple filters"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {
            'pii_redaction': True,
            'toxicity_filter': True,
            'toxicity_threshold': 0.7,
            'allowed_domains': [],  # Empty means all domains allowed
            'blocked_keywords': []
        }

        self.pii_redactor = PIIRedactor()
        self.toxicity_filter = ToxicityFilter()

    def process_input(self, text: str, tenant_id: str = "default") -> GuardrailResult:
        """Process input text through all guardrails"""
        violations = []
        processed_text = text
        result = FilterResult.ALLOWED
        confidence = 1.0

        # PII Redaction
        if self.config.get('pii_redaction', True):
            redacted_text, pii_violations = self.pii_redactor.redact_pii(processed_text)
            if pii_violations:
                violations.extend(pii_violations)
                processed_text = redacted_text
                result = FilterResult.MODIFIED
                logger.info(f"PII redacted for tenant {tenant_id}: {len(pii_violations)} violations")

        # Toxicity Filter
        if self.config.get('toxicity_filter', True):
            is_toxic, toxicity_score, toxic_violations = self.toxicity_filter.check_toxicity(
                processed_text,
                self.config.get('toxicity_threshold', 0.7)
            )

            if is_toxic:
                violations.extend(toxic_violations)
                result = FilterResult.BLOCKED
                confidence = toxicity_score
                logger.warning(f"Toxic content blocked for tenant {tenant_id}: score={toxicity_score}")

        # Keyword Filter
        blocked_keywords = self.config.get('blocked_keywords', [])
        for keyword in blocked_keywords:
            if keyword.lower() in processed_text.lower():
                violations.append(f"blocked_keyword: {keyword}")
                result = FilterResult.BLOCKED
                logger.warning(f"Blocked keyword '{keyword}' found for tenant {tenant_id}")

        return GuardrailResult(
            result=result,
            content=processed_text if result != FilterResult.BLOCKED else "",
            violations=violations,
            confidence=confidence,
            metadata={
                "original_length": len(text),
                "processed_length": len(processed_text),
                "tenant_id": tenant_id
            }
        )

    def process_output(self, text: str, tenant_id: str = "default") -> GuardrailResult:
        """Process output text through guardrails (lighter filtering)"""
        violations = []
        processed_text = text
        result = FilterResult.ALLOWED
        confidence = 1.0

        # Only apply PII redaction to outputs, not toxicity filtering
        if self.config.get('pii_redaction', True):
            redacted_text, pii_violations = self.pii_redactor.redact_pii(processed_text)
            if pii_violations:
                violations.extend(pii_violations)
                processed_text = redacted_text
                result = FilterResult.MODIFIED
                logger.info(f"PII redacted in output for tenant {tenant_id}: {len(pii_violations)} violations")

        return GuardrailResult(
            result=result,
            content=processed_text,
            violations=violations,
            confidence=confidence,
            metadata={
                "original_length": len(text),
                "processed_length": len(processed_text),
                "tenant_id": tenant_id
            }
        )

    def check_tool_access(self, tool_name: str, tenant_id: str = "default") -> bool:
        """Check if a tenant is allowed to use a specific tool"""
        # This would typically check against tenant configuration
        # For now, return True for all tools
        allowed_tools = self.config.get('allowed_tools', [])

        if not allowed_tools:  # Empty list means all tools allowed
            return True

        return tool_name in allowed_tools

    def update_config(self, config: Dict[str, Any]):
        """Update guardrails configuration"""
        self.config.update(config)
        logger.info(f"Guardrails configuration updated: {config}")

    def get_stats(self) -> Dict[str, Any]:
        """Get guardrails statistics"""
        return {
            "config": self.config,
            "filters_enabled": {
                "pii_redaction": self.config.get('pii_redaction', True),
                "toxicity_filter": self.config.get('toxicity_filter', True)
            }
        }
