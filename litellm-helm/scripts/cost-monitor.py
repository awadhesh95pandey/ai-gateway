#!/usr/bin/env python3
"""
Vertex AI Cost Monitoring and Guardrails Script
This script provides comprehensive cost tracking and guardrails for Vertex AI usage.
"""

import os
import json
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class CostEntry:
    """Represents a single cost entry"""
    timestamp: datetime
    model: str
    user_id: str
    input_tokens: int
    output_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float
    request_id: str
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

class CostTracker:
    """In-memory cost tracking system"""
    
    def __init__(self):
        self.costs: List[CostEntry] = []
        self.daily_costs: Dict[str, float] = defaultdict(float)
        self.weekly_costs: Dict[str, float] = defaultdict(float)
        self.monthly_costs: Dict[str, float] = defaultdict(float)
        self.user_costs: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self.model_costs: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self.lock = threading.Lock()
        
        # Load configuration from environment
        self.daily_budget = float(os.getenv('DAILY_BUDGET', '100.0'))
        self.weekly_budget = float(os.getenv('WEEKLY_BUDGET', '500.0'))
        self.monthly_budget = float(os.getenv('MONTHLY_BUDGET', '2000.0'))
        
        self.warning_threshold = float(os.getenv('COST_ALERT_WARNING', '75')) / 100
        self.critical_threshold = float(os.getenv('COST_ALERT_CRITICAL', '90')) / 100
        self.emergency_threshold = float(os.getenv('COST_ALERT_EMERGENCY', '95')) / 100
        
        # Model cost configuration
        self.model_costs = {
            'vertex-gemini-pro': {
                'input': float(os.getenv('VERTEX_GEMINI_PRO_INPUT_COST', '0.000125')),
                'output': float(os.getenv('VERTEX_GEMINI_PRO_OUTPUT_COST', '0.000375'))
            },
            'vertex-gemini-flash': {
                'input': float(os.getenv('VERTEX_GEMINI_FLASH_INPUT_COST', '0.000075')),
                'output': float(os.getenv('VERTEX_GEMINI_FLASH_OUTPUT_COST', '0.0003'))
            }
        }
        
        logger.info(f"Cost tracker initialized with budgets: Daily=${self.daily_budget}, Weekly=${self.weekly_budget}, Monthly=${self.monthly_budget}")
    
    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> Tuple[float, float, float]:
        """Calculate cost for a request"""
        if model not in self.model_costs:
            logger.warning(f"Unknown model: {model}, using default costs")
            input_cost_per_1k = 0.001
            output_cost_per_1k = 0.002
        else:
            input_cost_per_1k = self.model_costs[model]['input']
            output_cost_per_1k = self.model_costs[model]['output']
        
        input_cost = (input_tokens / 1000) * input_cost_per_1k
        output_cost = (output_tokens / 1000) * output_cost_per_1k
        total_cost = input_cost + output_cost
        
        return input_cost, output_cost, total_cost
    
    def add_cost_entry(self, model: str, user_id: str, input_tokens: int, output_tokens: int, request_id: str) -> CostEntry:
        """Add a new cost entry"""
        input_cost, output_cost, total_cost = self.calculate_cost(model, input_tokens, output_tokens)
        
        entry = CostEntry(
            timestamp=datetime.utcnow(),
            model=model,
            user_id=user_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=total_cost,
            request_id=request_id
        )
        
        with self.lock:
            self.costs.append(entry)
            
            # Update aggregated costs
            today = entry.timestamp.strftime('%Y-%m-%d')
            week = entry.timestamp.strftime('%Y-W%U')
            month = entry.timestamp.strftime('%Y-%m')
            
            self.daily_costs[today] += total_cost
            self.weekly_costs[week] += total_cost
            self.monthly_costs[month] += total_cost
            
            self.user_costs[user_id][today] += total_cost
            self.model_costs[model][today] += total_cost
        
        logger.info(f"Cost entry added: {model} - ${total_cost:.6f} for user {user_id}")
        return entry
    
    def check_budget_limits(self) -> Dict[str, bool]:
        """Check if any budget limits are exceeded"""
        today = datetime.utcnow().strftime('%Y-%m-%d')
        week = datetime.utcnow().strftime('%Y-W%U')
        month = datetime.utcnow().strftime('%Y-%m')
        
        daily_spent = self.daily_costs.get(today, 0)
        weekly_spent = self.weekly_costs.get(week, 0)
        monthly_spent = self.monthly_costs.get(month, 0)
        
        return {
            'daily_warning': daily_spent >= (self.daily_budget * self.warning_threshold),
            'daily_critical': daily_spent >= (self.daily_budget * self.critical_threshold),
            'daily_emergency': daily_spent >= (self.daily_budget * self.emergency_threshold),
            'weekly_warning': weekly_spent >= (self.weekly_budget * self.warning_threshold),
            'weekly_critical': weekly_spent >= (self.weekly_budget * self.critical_threshold),
            'weekly_emergency': weekly_spent >= (self.weekly_budget * self.emergency_threshold),
            'monthly_warning': monthly_spent >= (self.monthly_budget * self.warning_threshold),
            'monthly_critical': monthly_spent >= (self.monthly_budget * self.critical_threshold),
            'monthly_emergency': monthly_spent >= (self.monthly_budget * self.emergency_threshold),
        }
    
    def get_current_costs(self) -> Dict:
        """Get current cost summary"""
        today = datetime.utcnow().strftime('%Y-%m-%d')
        week = datetime.utcnow().strftime('%Y-W%U')
        month = datetime.utcnow().strftime('%Y-%m')
        
        return {
            'daily': {
                'spent': self.daily_costs.get(today, 0),
                'budget': self.daily_budget,
                'percentage': (self.daily_costs.get(today, 0) / self.daily_budget) * 100
            },
            'weekly': {
                'spent': self.weekly_costs.get(week, 0),
                'budget': self.weekly_budget,
                'percentage': (self.weekly_costs.get(week, 0) / self.weekly_budget) * 100
            },
            'monthly': {
                'spent': self.monthly_costs.get(month, 0),
                'budget': self.monthly_budget,
                'percentage': (self.monthly_costs.get(month, 0) / self.monthly_budget) * 100
            }
        }
    
    def cleanup_old_entries(self, retention_days: int = 30):
        """Remove old cost entries"""
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        
        with self.lock:
            original_count = len(self.costs)
            self.costs = [entry for entry in self.costs if entry.timestamp > cutoff_date]
            removed_count = original_count - len(self.costs)
            
            if removed_count > 0:
                logger.info(f"Cleaned up {removed_count} old cost entries")

class ContentGuardrails:
    """Content filtering and validation guardrails"""
    
    def __init__(self):
        self.block_pii = os.getenv('BLOCK_PII', 'true').lower() == 'true'
        self.block_toxic = os.getenv('BLOCK_TOXIC', 'true').lower() == 'true'
        self.block_hate = os.getenv('BLOCK_HATE', 'true').lower() == 'true'
        self.block_violence = os.getenv('BLOCK_VIOLENCE', 'true').lower() == 'true'
        self.block_sexual = os.getenv('BLOCK_SEXUAL', 'true').lower() == 'true'
        
        self.max_input_tokens = int(os.getenv('MAX_INPUT_TOKENS', '8192'))
        self.max_output_tokens = int(os.getenv('MAX_OUTPUT_TOKENS', '8192'))
        self.max_request_size = int(os.getenv('MAX_REQUEST_SIZE', '1048576'))  # 1MB
        
        self.scan_for_secrets = os.getenv('SCAN_FOR_SECRETS', 'true').lower() == 'true'
        
        # PII patterns
        self.pii_patterns = [
            r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
            r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b',  # Credit card
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
            r'\b\d{3}[- ]?\d{3}[- ]?\d{4}\b',  # Phone number
        ]
        
        # Secret patterns
        self.secret_patterns = [
            r'sk-[a-zA-Z0-9]{48}',  # OpenAI API key
            r'AIza[0-9A-Za-z-_]{35}',  # Google API key
            r'AKIA[0-9A-Z]{16}',  # AWS access key
            r'ghp_[a-zA-Z0-9]{36}',  # GitHub personal access token
            r'xoxb-[0-9]{11}-[0-9]{11}-[a-zA-Z0-9]{24}',  # Slack bot token
        ]
        
        logger.info("Content guardrails initialized")
    
    def validate_input(self, content: str, content_type: str = 'text/plain') -> Tuple[bool, List[str]]:
        """Validate input content"""
        violations = []
        
        # Check content size
        if len(content.encode('utf-8')) > self.max_request_size:
            violations.append(f"Request size exceeds limit: {len(content.encode('utf-8'))} > {self.max_request_size}")
        
        # Estimate token count (rough approximation)
        estimated_tokens = len(content.split()) * 1.3  # Rough estimate
        if estimated_tokens > self.max_input_tokens:
            violations.append(f"Estimated input tokens exceed limit: {estimated_tokens} > {self.max_input_tokens}")
        
        # Check for PII
        if self.block_pii:
            for pattern in self.pii_patterns:
                if re.search(pattern, content):
                    violations.append("Potential PII detected in input")
                    break
        
        # Check for secrets
        if self.scan_for_secrets:
            for pattern in self.secret_patterns:
                if re.search(pattern, content):
                    violations.append("Potential secret/API key detected in input")
                    break
        
        # Basic toxic content detection (simple keyword-based)
        if self.block_toxic or self.block_hate or self.block_violence or self.block_sexual:
            toxic_keywords = ['hate', 'kill', 'violence', 'explicit', 'toxic']  # Simplified
            content_lower = content.lower()
            for keyword in toxic_keywords:
                if keyword in content_lower:
                    violations.append(f"Potentially harmful content detected: {keyword}")
                    break
        
        return len(violations) == 0, violations
    
    def validate_output(self, content: str) -> Tuple[bool, List[str]]:
        """Validate output content"""
        violations = []
        
        # Estimate token count
        estimated_tokens = len(content.split()) * 1.3
        if estimated_tokens > self.max_output_tokens:
            violations.append(f"Output tokens exceed limit: {estimated_tokens} > {self.max_output_tokens}")
        
        # Check for secrets in output
        if self.scan_for_secrets:
            for pattern in self.secret_patterns:
                if re.search(pattern, content):
                    violations.append("Potential secret/API key detected in output")
                    break
        
        return len(violations) == 0, violations

class GuardrailsManager:
    """Main guardrails and cost monitoring manager"""
    
    def __init__(self):
        self.cost_tracker = CostTracker()
        self.content_guardrails = ContentGuardrails()
        self.enabled = os.getenv('GUARDRAILS_ENABLED', 'true').lower() == 'true'
        
        if self.enabled:
            logger.info("Guardrails manager initialized and enabled")
            # Start cleanup thread
            cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
            cleanup_thread.start()
        else:
            logger.info("Guardrails manager initialized but disabled")
    
    def _cleanup_worker(self):
        """Background worker for cleanup tasks"""
        while True:
            try:
                time.sleep(3600)  # Run every hour
                retention_days = int(os.getenv('COST_RETENTION_DAYS', '30'))
                self.cost_tracker.cleanup_old_entries(retention_days)
            except Exception as e:
                logger.error(f"Error in cleanup worker: {e}")
    
    def pre_request_check(self, content: str, model: str, user_id: str) -> Tuple[bool, List[str]]:
        """Check request before processing"""
        if not self.enabled:
            return True, []
        
        violations = []
        
        # Check budget limits
        budget_status = self.cost_tracker.check_budget_limits()
        if budget_status.get('daily_emergency') or budget_status.get('monthly_emergency'):
            violations.append("Budget limit exceeded - request blocked")
        
        # Validate content
        content_valid, content_violations = self.content_guardrails.validate_input(content)
        if not content_valid:
            violations.extend(content_violations)
        
        return len(violations) == 0, violations
    
    def post_request_processing(self, model: str, user_id: str, input_tokens: int, output_tokens: int, 
                              output_content: str, request_id: str) -> Tuple[bool, List[str]]:
        """Process request after completion"""
        if not self.enabled:
            return True, []
        
        violations = []
        
        # Add cost entry
        cost_entry = self.cost_tracker.add_cost_entry(model, user_id, input_tokens, output_tokens, request_id)
        
        # Validate output
        output_valid, output_violations = self.content_guardrails.validate_output(output_content)
        if not output_valid:
            violations.extend(output_violations)
        
        # Check for budget alerts
        budget_status = self.cost_tracker.check_budget_limits()
        for alert_type, triggered in budget_status.items():
            if triggered:
                logger.warning(f"Budget alert triggered: {alert_type}")
        
        return len(violations) == 0, violations
    
    def get_status(self) -> Dict:
        """Get current status and metrics"""
        if not self.enabled:
            return {'enabled': False}
        
        return {
            'enabled': True,
            'costs': self.cost_tracker.get_current_costs(),
            'budget_status': self.cost_tracker.check_budget_limits(),
            'total_entries': len(self.cost_tracker.costs),
            'guardrails_config': {
                'block_pii': self.content_guardrails.block_pii,
                'block_toxic': self.content_guardrails.block_toxic,
                'scan_for_secrets': self.content_guardrails.scan_for_secrets,
                'max_input_tokens': self.content_guardrails.max_input_tokens,
                'max_output_tokens': self.content_guardrails.max_output_tokens,
            }
        }

# Global instance
guardrails_manager = GuardrailsManager()

def main():
    """Main function for standalone execution"""
    logger.info("Starting Vertex AI Cost Monitor and Guardrails")
    
    # Example usage
    while True:
        try:
            status = guardrails_manager.get_status()
            logger.info(f"Current status: {json.dumps(status, indent=2)}")
            time.sleep(60)  # Log status every minute
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
