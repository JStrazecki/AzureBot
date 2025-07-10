# sql-assistant/bot/token_limiter.py
"""
Token Usage Limiter for Azure OpenAI
Prevents excessive token usage and costs
"""

import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple
import tiktoken

logger = logging.getLogger(__name__)

class TokenLimiter:
    """
    Tracks and limits token usage to prevent excessive costs
    """
    
    def __init__(self, 
                 max_daily_tokens: int = 50000,  # ~$1-2 per day
                 max_hourly_tokens: int = 10000,  # ~$0.20-0.40 per hour
                 max_tokens_per_request: int = 2000,
                 cost_per_1k_tokens: float = 0.03):  # GPT-4 pricing
        
        self.max_daily_tokens = max_daily_tokens
        self.max_hourly_tokens = max_hourly_tokens
        self.max_tokens_per_request = max_tokens_per_request
        self.cost_per_1k_tokens = cost_per_1k_tokens
        
        # Usage tracking
        self.usage_file = Path(".token_usage.json")
        self.usage_data = self._load_usage()
        
        # Token counter
        try:
            self.encoding = tiktoken.encoding_for_model("gpt-4")
        except:
            # Fallback if tiktoken has issues
            self.encoding = tiktoken.get_encoding("cl100k_base")
    
    def _load_usage(self) -> Dict:
        """Load usage data from file"""
        if self.usage_file.exists():
            try:
                with open(self.usage_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        
        return {
            "daily": {},
            "hourly": {},
            "total_tokens": 0,
            "total_cost": 0.0,
            "last_reset": datetime.now().isoformat()
        }
    
    def _save_usage(self):
        """Save usage data to file"""
        try:
            with open(self.usage_file, 'w') as f:
                json.dump(self.usage_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save usage data: {e}")
    
    def check_limits(self, estimated_tokens: int) -> Tuple[bool, str]:
        """
        Check if request would exceed limits
        Returns (allowed, reason)
        """
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        current_hour = now.strftime("%Y-%m-%d-%H")
        
        # Check per-request limit
        if estimated_tokens > self.max_tokens_per_request:
            return False, f"Request too large: {estimated_tokens} tokens (max: {self.max_tokens_per_request})"
        
        # Get current usage
        daily_usage = self.usage_data["daily"].get(today, 0)
        hourly_usage = self.usage_data["hourly"].get(current_hour, 0)
        
        # Check daily limit
        if daily_usage + estimated_tokens > self.max_daily_tokens:
            remaining = self.max_daily_tokens - daily_usage
            cost = daily_usage * self.cost_per_1k_tokens / 1000
            return False, f"Daily token limit reached: {daily_usage}/{self.max_daily_tokens} tokens used (${cost:.2f}). Resets at midnight."
        
        # Check hourly limit
        if hourly_usage + estimated_tokens > self.max_hourly_tokens:
            remaining = self.max_hourly_tokens - hourly_usage
            return False, f"Hourly token limit reached: {hourly_usage}/{self.max_hourly_tokens} tokens used. Try again next hour."
        
        return True, "OK"
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text"""
        try:
            return len(self.encoding.encode(text))
        except:
            # Fallback: rough estimate of 4 characters per token
            return len(text) // 4
    
    def track_usage(self, prompt_tokens: int, completion_tokens: int):
        """Track token usage after a successful request"""
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        current_hour = now.strftime("%Y-%m-%d-%H")
        
        total_tokens = prompt_tokens + completion_tokens
        
        # Update daily usage
        if today not in self.usage_data["daily"]:
            self.usage_data["daily"] = {today: 0}  # Reset old days
        self.usage_data["daily"][today] = self.usage_data["daily"].get(today, 0) + total_tokens
        
        # Update hourly usage
        if current_hour not in self.usage_data["hourly"]:
            # Keep only last 24 hours
            self._cleanup_old_hourly()
        self.usage_data["hourly"][current_hour] = self.usage_data["hourly"].get(current_hour, 0) + total_tokens
        
        # Update totals
        self.usage_data["total_tokens"] += total_tokens
        self.usage_data["total_cost"] += total_tokens * self.cost_per_1k_tokens / 1000
        
        # Save
        self._save_usage()
        
        # Log usage
        daily_total = self.usage_data["daily"][today]
        daily_cost = daily_total * self.cost_per_1k_tokens / 1000
        logger.info(f"Token usage - This request: {total_tokens}, Today: {daily_total} (${daily_cost:.2f})")
    
    def _cleanup_old_hourly(self):
        """Remove hourly data older than 24 hours"""
        cutoff = datetime.now() - timedelta(hours=24)
        cutoff_str = cutoff.strftime("%Y-%m-%d-%H")
        
        self.usage_data["hourly"] = {
            k: v for k, v in self.usage_data["hourly"].items()
            if k >= cutoff_str
        }
    
    def get_usage_summary(self) -> Dict:
        """Get current usage summary"""
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        current_hour = now.strftime("%Y-%m-%d-%H")
        
        daily_usage = self.usage_data["daily"].get(today, 0)
        hourly_usage = self.usage_data["hourly"].get(current_hour, 0)
        
        daily_cost = daily_usage * self.cost_per_1k_tokens / 1000
        total_cost = self.usage_data["total_cost"]
        
        return {
            "daily": {
                "used": daily_usage,
                "limit": self.max_daily_tokens,
                "remaining": self.max_daily_tokens - daily_usage,
                "percentage": (daily_usage / self.max_daily_tokens * 100) if self.max_daily_tokens > 0 else 0,
                "cost": daily_cost
            },
            "hourly": {
                "used": hourly_usage,
                "limit": self.max_hourly_tokens,
                "remaining": self.max_hourly_tokens - hourly_usage,
                "percentage": (hourly_usage / self.max_hourly_tokens * 100) if self.max_hourly_tokens > 0 else 0
            },
            "total": {
                "tokens": self.usage_data["total_tokens"],
                "cost": total_cost
            },
            "limits": {
                "daily_limit": self.max_daily_tokens,
                "hourly_limit": self.max_hourly_tokens,
                "request_limit": self.max_tokens_per_request,
                "estimated_daily_cost": self.max_daily_tokens * self.cost_per_1k_tokens / 1000
            }
        }
    
    def reset_daily_usage(self):
        """Reset daily usage (for testing)"""
        today = datetime.now().strftime("%Y-%m-%d")
        if today in self.usage_data["daily"]:
            self.usage_data["daily"][today] = 0
            self._save_usage()