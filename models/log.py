"""
Logging related data models for multi-agent system
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict


@dataclass
class AgentExecutionLog:
    """エージェント実行ログ"""
    agent_role: str
    task_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = "running"  # running, completed, failed
    prompt_length: int = 0
    context_files_count: int = 0
    output_length: int = 0
    artifacts_created: List[str] = field(default_factory=list)
    claude_code_commands: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    execution_time_seconds: float = 0.0
    
    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return {
            "agent_role": self.agent_role,
            "task_id": self.task_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
            "prompt_length": self.prompt_length,
            "context_files_count": self.context_files_count,
            "output_length": self.output_length,
            "artifacts_created": self.artifacts_created,
            "claude_code_commands": self.claude_code_commands,
            "error_message": self.error_message,
            "execution_time_seconds": self.execution_time_seconds
        }


@dataclass
class InteractionLog:
    """エージェント間相互作用ログ"""
    timestamp: datetime
    from_agent: str
    to_agent: str
    interaction_type: str  # context_sharing, dependency, review, artifact_creation
    files_shared: List[str] = field(default_factory=list)
    message: str = ""
    
    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "interaction_type": self.interaction_type,
            "files_shared": self.files_shared,
            "message": self.message
        }


@dataclass
class SystemLog:
    """システム全体ログ"""
    timestamp: datetime
    level: str  # info, warning, error
    component: str
    message: str
    details: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level,
            "component": self.component,
            "message": self.message,
            "details": self.details
        }


@dataclass
class SessionSummary:
    """セッション全体のサマリー"""
    session_id: str
    start_time: datetime
    end_time: datetime
    total_execution_time_seconds: float
    total_tasks: int
    successful_tasks: int
    failed_tasks: int
    agents_involved: List[str]
    total_artifacts_created: int
    total_interactions: int
    error_count: int
    claude_code_commands_count: int
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_tasks == 0:
            return 0.0
        return self.successful_tasks / self.total_tasks
    
    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return {
            "session_id": self.session_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "total_execution_time_seconds": self.total_execution_time_seconds,
            "total_tasks": self.total_tasks,
            "successful_tasks": self.successful_tasks,
            "failed_tasks": self.failed_tasks,
            "success_rate": self.success_rate,
            "agents_involved": self.agents_involved,
            "total_artifacts_created": self.total_artifacts_created,
            "total_interactions": self.total_interactions,
            "error_count": self.error_count,
            "claude_code_commands_count": self.claude_code_commands_count
        }
