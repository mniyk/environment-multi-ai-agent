"""
Configuration settings for multi-agent system
"""

import os
from pathlib import Path
from typing import Dict, List


class Config:
    """設定クラス"""
    
    # プロジェクト設定
    DEFAULT_PROJECT_DIR = "./todo_project_output"
    DEFAULT_LOG_DIR = "./logs"
    
    # Claude Code SDK設定（Anthropic API経由）
    ANTHROPIC_MODEL = "claude-3-5-sonnet-20241022"
    ANTHROPIC_MAX_TOKENS = 8192
    CLAUDE_TIMEOUT_SECONDS = 1800  # 30分
    
    # ログ設定
    LOG_LEVEL = "INFO"
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # エージェント設定
    MAX_PROMPT_LENGTH = 100000  # プロンプト長制限を拡張
    MAX_CONTEXT_FILES = 10
    
    # ファイル検出設定
    ARTIFACT_EXTENSIONS = ['.md', '.py', '.json', '.yaml', '.yml', '.txt', '.js', '.css', '.html', '.tsx', '.ts']
    IGNORE_PATTERNS = ['.git', '__pycache__', '.vscode', '.idea', 'node_modules', '.env']
    
    @classmethod
    def validate(cls) -> List[str]:
        """設定の検証"""
        errors = []
        
        # Claude Code SDK の存在確認は実行時に行う
        # Note: Claude Pro users don't need API key for Claude Code SDK
        
        return errors
    
    @classmethod
    def get_project_dir(cls, custom_dir: str = None) -> Path:
        """プロジェクトディレクトリの取得"""
        project_dir = custom_dir or cls.DEFAULT_PROJECT_DIR
        return Path(project_dir).resolve()
    
    @classmethod
    def get_log_dir(cls, project_dir: Path) -> Path:
        """ログディレクトリの取得"""
        return project_dir / "logs"




class TemplateConfig:
    """テンプレート関連の設定"""
    
    # テンプレート設定
    DEFAULT_TEMPLATES_DIR = "./templates"
    DEFAULT_AGENTS_DIR = "./agents"
    DEFAULT_TEMPLATE = "simple_todo"  # デフォルトテンプレート
    
    # 利用可能なテンプレート（自動発見もサポート）
    KNOWN_TEMPLATES = {
        "simple_todo": "シンプルToDoアプリ開発テンプレート（Python Flask + SQLite + Bootstrap）"
    }
    
    @classmethod
    def get_templates_directory(cls, custom_dir: str = None) -> Path:
        """テンプレートディレクトリの取得"""
        from pathlib import Path
        templates_dir = custom_dir or cls.DEFAULT_TEMPLATES_DIR
        return Path(templates_dir).resolve()
    
    @classmethod
    def get_agents_directory(cls, custom_dir: str = None) -> Path:
        """エージェントディレクトリの取得"""
        from pathlib import Path
        agents_dir = custom_dir or cls.DEFAULT_AGENTS_DIR
        return Path(agents_dir).resolve()
    
    @classmethod
    def is_valid_template(cls, template_name: str) -> bool:
        """テンプレート名の有効性チェック"""
        return template_name in cls.KNOWN_TEMPLATES
