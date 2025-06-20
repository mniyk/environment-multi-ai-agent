"""
Claude Code Agent implementation for multi-agent system
"""

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

from config import Config, TemplateConfig
from models.task import AgentRole, AgentTask, AgentResult
from .log_manager import LogManager
from .agent_loader import AgentRegistry

try:
    import claude_code_sdk
    CLAUDE_CODE_SDK_AVAILABLE = True
except ImportError:
    CLAUDE_CODE_SDK_AVAILABLE = False


class ClaudeCodeAgent:
    """Individual Claude Code agent with specific role"""
    
    def __init__(self, role: AgentRole, working_dir: str, log_manager: LogManager = None, 
                 agents_dir: str = None):
        self.role = role
        self.working_dir = Path(working_dir)
        self.log_manager = log_manager
        self.logger = logging.getLogger(f"{__name__}.{role.value}")
        
        # Claude Code SDK初期化
        if CLAUDE_CODE_SDK_AVAILABLE:
            self.claude_sdk_available = True
        else:
            self.claude_sdk_available = False
            self.logger.warning("Claude Code SDK not available, using fallback implementation")
        
        # エージェント定義レジストリの初期化
        agents_directory = agents_dir or TemplateConfig.DEFAULT_AGENTS_DIR
        self.agent_registry = AgentRegistry(agents_directory)
        
        # 作業ディレクトリの作成
        self.working_dir.mkdir(parents=True, exist_ok=True)
        
    async def execute_task(self, task: AgentTask, timeout: Optional[int] = None, max_retries: int = 1) -> AgentResult:
        """Execute a task using Claude Code SDK - single attempt only, retries handled at workflow level"""
        if not task.task_id:
            task.task_id = f"{self.role.value}_{int(time.time())}"
        
        print(f"🚀 Starting task {task.task_id} for {self.role.value}")
        
        # 実行開始ログ
        execution_log = None
        if self.log_manager:
            execution_log = self.log_manager.log_agent_start(
                self.role.value, task.task_id, task.prompt, task.context_files
            )
        
        try:
            print(f"🔍 DEBUG: Starting task execution for {self.role.value}")
            
            # コンテキストファイルを読み込み
            print(f"🔍 DEBUG: Loading context files...")
            context_content, available_files = self._load_context_files(task.context_files)
            print(f"🔍 DEBUG: Loaded {len(available_files)} context files")
            
            # 相互作用ログ
            if self.log_manager and available_files:
                self.log_manager.log_interaction(
                    "file_system", self.role.value, "context_sharing",
                    available_files, f"Loaded {len(available_files)} context files"
                )
            
            # ロール固有のプロンプト構築
            print(f"🔍 DEBUG: Building role prompt...")
            role_prompt = self._build_role_prompt(task.prompt, context_content)
            print(f"🔍 DEBUG: Role prompt built, length: {len(role_prompt)}")
            
            # Claude Code SDK実行
            print(f"🔍 DEBUG: Starting Claude Code SDK execution...")
            result = await self._run_claude_code_sdk(role_prompt, task.output_file, task.task_id, timeout)
            print(f"🔍 DEBUG: Claude Code SDK execution completed")
            
            # 実行終了ログ（成功）
            if self.log_manager:
                self.log_manager.log_agent_end(
                    execution_log, True, result["output"], result.get("artifacts", [])
                )
            
            self.logger.info(f"Task {task.task_id} completed successfully")
            return AgentResult(
                role=self.role,
                success=True,
                output=result["output"],
                task_id=task.task_id,
                artifacts=result.get("artifacts", []),
                execution_log=execution_log
            )
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Task {task.task_id} failed: {error_msg}")
            
            # 実行終了ログ（失敗）
            if self.log_manager:
                self.log_manager.log_agent_end(execution_log, False, "", [], error_msg)
                self.log_manager.log_system_event(
                    "error", f"agent_{self.role.value}", f"Task execution failed: {error_msg}",
                    {"task_id": task.task_id, "exception_type": type(e).__name__}
                )
            
            self.logger.error(f"Task {task.task_id} failed: {error_msg}")
            return AgentResult(
                role=self.role,
                success=False,
                output="",
                task_id=task.task_id,
                errors=error_msg,
                execution_log=execution_log
            )
    
    def _load_context_files(self, context_files: List[str] = None) -> tuple[str, List[str]]:
        """コンテキストファイルの読み込み（サイズ制限付き）"""
        context_content = ""
        available_files = []
        max_file_size = 5000  # 1ファイル最大5000文字
        total_size = 0
        max_total_size = 20000  # 全体で最大20000文字
        
        if context_files:
            for file_path in context_files:
                if total_size >= max_total_size:
                    break
                    
                full_path = self.working_dir / file_path
                if full_path.exists():
                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            
                            # ファイルサイズ制限
                            if len(content) > max_file_size:
                                content = content[:max_file_size] + "\n... (truncated)"
                            
                            # 全体サイズ制限
                            remaining_size = max_total_size - total_size
                            if len(content) > remaining_size:
                                content = content[:remaining_size] + "\n... (truncated)"
                            
                            context_content += f"\n=== {file_path} ===\n{content}\n"
                            available_files.append(file_path)
                            total_size += len(content)
                            
                    except Exception as e:
                        self.logger.warning(f"Failed to read context file {file_path}: {e}")
                else:
                    self.logger.warning(f"Context file not found: {file_path}")
        
        return context_content, available_files
    
    def _build_role_prompt(self, base_prompt: str, context: str) -> str:
        """Build role-specific prompt using AgentRegistry"""
        # 作業ディレクトリの情報を明示的に追加
        enhanced_prompt = f"""
{base_prompt}

【重要】作業ディレクトリ: {self.working_dir}
現在のロール: {self.role.value}

ファイルを作成する際は、必ず上記の作業ディレクトリ内に保存してください。
相対パスを使用し、ディレクトリが存在しない場合は自動的に作成してください。
出力は明確で実用的なものにし、必要に応じてファイルを作成してください。
"""
        
        return self.agent_registry.build_prompt_for_role(
            self.role.value, enhanced_prompt, context, str(self.working_dir)
        )
    
    async def _run_claude_code_sdk(self, prompt: str, output_file: Optional[str] = None, task_id: str = "", timeout: Optional[int] = None) -> Dict:
        """Run Claude Code SDK with the given prompt"""
        # プロンプト長チェック
        if len(prompt) > Config.MAX_PROMPT_LENGTH:
            self.logger.warning(f"Prompt length {len(prompt)} exceeds maximum {Config.MAX_PROMPT_LENGTH}")
        
        # SDK実行ログ
        if self.log_manager:
            self.log_manager.log_claude_code_command(
                self.role.value, task_id, f"Claude Code SDK call with {len(prompt)} chars"
            )
        
        try:
            effective_timeout = timeout or Config.CLAUDE_TIMEOUT_SECONDS
            
            if self.claude_sdk_available:
                try:
                    # Claude Code SDK呼び出し
                    options = claude_code_sdk.ClaudeCodeOptions(
                        cwd=str(self.working_dir),
                        permission_mode='acceptEdits'  # ファイル編集を自動許可
                    )
                    
                    # 非同期ジェネレーターから結果を取得
                    response_parts = []
                    
                    async def collect_response():
                        try:
                            async for message in claude_code_sdk.query(options=options, prompt=prompt):
                                if hasattr(message, 'content'):
                                    response_parts.append(str(message.content))
                                else:
                                    response_parts.append(str(message))
                        except Exception as e:
                            self.logger.error(f"Error in Claude Code SDK query: {e}")
                            raise
                    
                    await asyncio.wait_for(collect_response(), timeout=effective_timeout)
                    response_text = "\n".join(response_parts) if response_parts else ""
                    
                except Exception as sdk_error:
                    # SDK エラーの場合はフォールバックを使用
                    self.logger.warning(f"Claude Code SDK failed: {sdk_error}, using fallback")
                    response_text = f"Fallback: Mock Claude Code response for {self.role.value} task: {task_id[:10]}..."
            else:
                # Fallback: Mock implementation for development
                response_text = f"Mock Claude Code response for {self.role.value} task: {task_id[:10]}..."
                self.logger.warning("Using mock Claude Code response - SDK not available")
            
        except asyncio.TimeoutError:
            error_msg = f"Claude Code SDK execution timed out after {effective_timeout}s"
            if self.log_manager:
                self.log_manager.log_system_event(
                    "error", f"claude_code_sdk_{self.role.value}", error_msg,
                    {"task_id": task_id, "timeout": effective_timeout}
                )
            print(f"⏰ TIMEOUT: {self.role.value} task timed out after {effective_timeout//60}min {effective_timeout%60}s")
            raise Exception(error_msg)
        
        except Exception as e:
            error_msg = str(e)
            if self.log_manager:
                self.log_manager.log_system_event(
                    "error", f"claude_code_sdk_{self.role.value}", 
                    f"Claude Code SDK execution failed: {error_msg}",
                    {"task_id": task_id}
                )
            raise Exception(f"Claude Code SDK failed: {error_msg}")
        
        # SDKの詳細な会話ログを保存
        if self.log_manager:
            self.log_manager.log_claude_conversation(
                self.role.value, task_id, prompt, response_text, "", 0
            )
        
        # 作成されたファイルを検出
        artifacts = self._detect_created_files()
        
        return {
            "output": response_text,
            "artifacts": artifacts
        }
    
    def _detect_created_files(self) -> List[str]:
        """作成されたファイルを検出"""
        artifacts = []
        
        try:
            for file_path in self.working_dir.rglob('*'):
                if file_path.is_file():
                    # 相対パスに変換
                    relative_path = file_path.relative_to(self.working_dir)
                    relative_path_str = str(relative_path)
                    
                    # 無視パターンをチェック
                    if any(pattern in relative_path_str for pattern in Config.IGNORE_PATTERNS):
                        continue
                    
                    # 拡張子チェック
                    if file_path.suffix in Config.ARTIFACT_EXTENSIONS:
                        artifacts.append(relative_path_str)
                    
        except Exception as e:
            self.logger.warning(f"Failed to detect created files: {e}")
        
        return sorted(artifacts)
    
    def get_context_summary(self) -> Dict:
        """エージェントの状態サマリー"""
        return {
            "role": self.role.value,
            "working_dir": str(self.working_dir),
            "artifacts_count": len(self._detect_created_files()),
            "artifacts": self._detect_created_files()[:5]  # 最初の5個だけ表示
        }
    
    async def _validate_solution(self) -> bool:
        """Validate solution based on agent role and expected outputs"""
        try:
            # For PM agent - check if project_plan.md exists
            if self.role.value == "pm":
                plan_path = self.working_dir / "project_plan.md"
                if plan_path.exists() and plan_path.stat().st_size > 100:  # At least 100 bytes
                    print("✅ PM solution validation passed - project plan created")
                    return True
                else:
                    print("❌ PM solution validation failed - project plan missing or too small")
                    return False
            
            # For UI Designer - check if design files exist
            elif self.role.value == "ui_designer":
                required_files = ["database_schema.sql", "ui_design.md", "wireframe.html"]
                missing_files = []
                for file_name in required_files:
                    file_path = self.working_dir / file_name
                    if not file_path.exists() or file_path.stat().st_size < 50:
                        missing_files.append(file_name)
                
                if not missing_files:
                    print("✅ UI Designer solution validation passed - all design files created")
                    return True
                else:
                    print(f"❌ UI Designer solution validation failed - missing: {', '.join(missing_files)}")
                    return False
            
            # For Python Developer - check Flask app
            elif self.role.value == "python_developer":
                app_path = self.working_dir / "app.py"
                if not app_path.exists():
                    print("❌ Python Developer solution validation failed - app.py not found")
                    return False
                
                # Try to run basic Flask app validation
                import subprocess
                
                # Basic syntax check
                python_cmd = self._get_python_command()
                result = subprocess.run(
                    [python_cmd, "-m", "py_compile", str(app_path)],
                    cwd=str(self.working_dir),
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode != 0:
                    print(f"❌ Python syntax validation failed: {result.stderr}")
                    return False
                
                # Try basic import test
                test_script = '''
import sys
import os
sys.path.insert(0, ".")
try:
    from app import app
    print("SUCCESS: Basic Flask app validation passed")
except ImportError as e:
    print(f"IMPORT_ERROR: {e}")
    sys.exit(1)
except Exception as e:
    print(f"FLASK_ERROR: {e}")
    sys.exit(1)
'''
                
                result = subprocess.run(
                    [python_cmd, "-c", test_script],
                    cwd=str(self.working_dir),
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode == 0 and "SUCCESS" in result.stdout:
                    print("✅ Python Developer solution validation passed")
                    return True
                else:
                    print(f"❌ Python Developer solution validation failed: {result.stdout} {result.stderr}")
                    return False
            
            # For Tester - check if test files exist
            elif self.role.value == "tester":
                test_files = ["test_app.py", "TEST_REPORT.md"]
                missing_files = []
                for file_name in test_files:
                    file_path = self.working_dir / file_name
                    if not file_path.exists() or file_path.stat().st_size < 50:
                        missing_files.append(file_name)
                
                if not missing_files:
                    print("✅ Tester solution validation passed - test files created")
                    return True
                else:
                    print(f"❌ Tester solution validation failed - missing: {', '.join(missing_files)}")
                    return False
            
            # For Security Engineer - check if security files exist
            elif self.role.value == "security_engineer":
                security_files = ["SECURITY_AUDIT.md"]
                missing_files = []
                for file_name in security_files:
                    file_path = self.working_dir / file_name
                    if not file_path.exists() or file_path.stat().st_size < 50:
                        missing_files.append(file_name)
                
                if not missing_files:
                    print("✅ Security Engineer solution validation passed - security files created")
                    return True
                else:
                    print(f"❌ Security Engineer solution validation failed - missing: {', '.join(missing_files)}")
                    return False
            
            # Default case - just check if any files were created
            else:
                artifacts = self._detect_created_files()
                if artifacts:
                    print(f"✅ Generic solution validation passed - {len(artifacts)} files created")
                    return True
                else:
                    print("❌ Generic solution validation failed - no files created")
                    return False
                
        except subprocess.TimeoutExpired:
            print("❌ Solution validation timed out")
            return False
        except Exception as e:
            print(f"❌ Solution validation error: {e}")
            return False
    
    def _get_python_command(self) -> str:
        """Get the appropriate Python command for the system"""
        import shutil
        
        # Try different Python commands in order of preference
        for cmd in ["python3", "python", "py"]:
            if shutil.which(cmd):
                return cmd
        
        # Fallback to python3 if nothing found
        return "python3"
    
    def get_agent_definition_summary(self) -> Dict:
        """エージェント定義のサマリー"""
        agent_def = self.agent_registry.agent_loader.get_agent_by_role(self.role.value)
        if agent_def:
            return {
                "role": agent_def.role,
                "display_name": agent_def.display_name,
                "description": agent_def.description,
                "expertise_summary": agent_def.get_expertise_summary(),
                "specializations": list(agent_def.specializations.keys())
            }
        else:
            return {
                "role": self.role.value,
                "display_name": self.role.value.replace('_', ' ').title(),
                "description": "Default agent configuration",
                "expertise_summary": "General purpose",
                "specializations": []
            }


class AgentFactory:
    """エージェント作成ファクトリ"""
    
    @staticmethod
    def create_agent(role: AgentRole, working_dir: str, log_manager: LogManager = None, 
                    agents_dir: str = None) -> ClaudeCodeAgent:
        """指定されたロールのエージェントを作成"""
        return ClaudeCodeAgent(role, working_dir, log_manager, agents_dir)
    
    @staticmethod
    def create_all_agents(working_dir: str, log_manager: LogManager = None, 
                         agents_dir: str = None) -> Dict[AgentRole, ClaudeCodeAgent]:
        """全種類のエージェントを作成"""
        return {
            role: AgentFactory.create_agent(role, working_dir, log_manager, agents_dir)
            for role in AgentRole
        }
