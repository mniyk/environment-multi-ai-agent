"""
Multi-Agent Development System

A flexible, template-based multi-agent system for software development
using Claude Code SDK.
"""

__version__ = "1.0.0"
__author__ = "Multi-Agent Development Team"
__description__ = "Template-based multi-agent system for software development"

from core import MultiAgentOrchestrator, TemplateLoader
from models import AgentRole, AgentTask, AgentResult
from config import Config, TemplateConfig

__all__ = [
    'MultiAgentOrchestrator',
    'TemplateLoader', 
    'AgentRole',
    'AgentTask',
    'AgentResult',
    'Config',
    'TemplateConfig'
]
