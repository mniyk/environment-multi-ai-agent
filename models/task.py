"""
Task related data models for multi-agent system
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

from .log import AgentExecutionLog


class AgentRole(Enum):
    PM = "pm"
    UI_DESIGNER = "ui_designer"
    PYTHON_DEVELOPER = "python_developer"
    TESTER = "tester"
    SECURITY_ENGINEER = "security_engineer"


@dataclass
class AgentTask:
    """エージェントが実行するタスクの定義"""
    role: AgentRole
    prompt: str
    task_id: str = ""
    dependencies: List[AgentRole] = field(default_factory=list)
    output_file: Optional[str] = None
    context_files: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Post initialization processing"""
        if not self.task_id:
            import time
            self.task_id = f"{self.role.value}_{int(time.time())}"


@dataclass
class AgentResult:
    """エージェントタスクの実行結果"""
    role: AgentRole
    success: bool
    output: str
    task_id: str = ""
    artifacts: List[str] = field(default_factory=list)
    errors: Optional[str] = None
    execution_log: Optional[AgentExecutionLog] = None
    retry_count: int = 0
    requires_retry: bool = False
    retry_reason: Optional[str] = None
    
    @property
    def execution_time(self) -> float:
        """実行時間を取得"""
        if self.execution_log:
            return self.execution_log.execution_time_seconds
        return 0.0
    
    @property
    def status_emoji(self) -> str:
        """ステータス絵文字"""
        return "✅" if self.success else "❌"
    
    def summary(self) -> str:
        """結果サマリー"""
        duration_text = f" ({self.execution_time:.1f}s)" if self.execution_time > 0 else ""
        artifacts_text = f", created {len(self.artifacts)} files" if self.artifacts else ""
        
        retry_text = f" (retry {self.retry_count})" if self.retry_count > 0 else ""
        return f"{self.status_emoji} {self.role.value}{duration_text}{artifacts_text}{retry_text}"
    
    def set_retry_required(self, reason: str) -> None:
        """Mark this result as requiring a retry"""
        self.requires_retry = True
        self.retry_reason = reason


@dataclass
class PhaseRetryTracker:
    """Cross-phase retry tracking for bug fixing workflow"""
    phase_name: str
    retry_count: int = 0
    max_retries: int = 3
    retry_history: List[Dict[str, Any]] = field(default_factory=list)
    triggered_by: Optional[str] = None  # Which phase triggered the retry
    retry_reason: Optional[str] = None
    
    def can_retry(self) -> bool:
        """Check if phase can be retried"""
        return self.retry_count < self.max_retries
    
    def add_retry_attempt(self, triggered_by: str, reason: str) -> None:
        """Record a retry attempt"""
        self.retry_count += 1
        self.triggered_by = triggered_by
        self.retry_reason = reason
        self.retry_history.append({
            "attempt": self.retry_count,
            "triggered_by": triggered_by,
            "reason": reason,
            "timestamp": __import__('time').time()
        })
    
    def get_retry_summary(self) -> str:
        """Get a summary of retry attempts"""
        if self.retry_count == 0:
            return "No retries"
        return f"Retried {self.retry_count}/{self.max_retries} times, last triggered by {self.triggered_by}: {self.retry_reason}"
