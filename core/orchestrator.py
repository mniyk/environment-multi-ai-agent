"""
Multi-agent orchestrator for dynamic project development
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

from config import Config, TemplateConfig
from models.task import AgentRole, AgentTask, AgentResult, PhaseRetryTracker
from .agent import AgentFactory
from .log_manager import LogManager
from .template_loader import TemplateLoader, ProjectTemplate


class MultiAgentOrchestrator:
    """マルチエージェントオーケストレーター（テンプレートベース）"""
    
    def __init__(self, project_dir: str = None, template_name: str = None, 
                 templates_dir: str = None, agents_dir: str = None, max_retries: int = 3):
        self.project_dir = Config.get_project_dir(project_dir)
        self.log_manager = LogManager(Config.get_log_dir(self.project_dir))
        
        # エージェントディレクトリの設定
        self.agents_dir = agents_dir or TemplateConfig.DEFAULT_AGENTS_DIR
        
        # エージェント作成（エージェントディレクトリを渡す）
        self.agents = AgentFactory.create_all_agents(
            str(self.project_dir), self.log_manager, self.agents_dir
        )
        
        self.results: Dict[str, AgentResult] = {}  # 文字列キーに変更（phase名）
        self.retry_trackers: Dict[str, PhaseRetryTracker] = {}  # Phase retry tracking
        self.logger = logging.getLogger(__name__)
        
        # テンプレート関連の初期化
        self.template_loader = TemplateLoader(
            templates_dir or TemplateConfig.DEFAULT_TEMPLATES_DIR,
            self.agents_dir
        )
        self.template_name = template_name or TemplateConfig.DEFAULT_TEMPLATE
        self.project_template: Optional[ProjectTemplate] = None
        self.workflow_tasks: List[AgentTask] = []
        
        # テンプレートの読み込み
        self._load_project_template()
        
        # デフォルトタイムアウト（引数で上書き可能）
        self.default_timeout = 1800  # 30分
        
        # デフォルトリトライ回数
        self.max_retries = max_retries
        
        # 動的タイムアウトの計算
        self.calculated_timeout = None
        if self.project_template:
            self.calculated_timeout = self.project_template.calculate_timeout()
            complexity_score = self.project_template.calculate_complexity_score()
            print(f"🕒 Complexity Score: {complexity_score}, Auto Timeout: {self.calculated_timeout//60}min")
        
        # システム初期化ログ
        self.log_manager.log_system_event(
            "info", "orchestrator", "Multi-agent system initialized",
            {
                "project_dir": str(self.project_dir),
                "template": self.template_name,
                "agents_dir": self.agents_dir,
                "agents": [role.value for role in AgentRole],
                "log_dir": str(self.log_manager.log_dir)
            }
        )
    
    def _load_project_template(self):
        """プロジェクトテンプレートの読み込み"""
        try:
            self.project_template = self.template_loader.load_template(self.template_name)
            self.workflow_tasks = self.template_loader.create_agent_tasks(self.project_template)
            
            # エージェント互換性チェック
            compatibility = self.template_loader.get_agent_requirements_summary(self.template_name)
            
            self.log_manager.log_system_event(
                "info", "template_loader", f"Template loaded successfully: {self.template_name}",
                {
                    "project_name": self.project_template.name,
                    "tasks_count": len(self.workflow_tasks),
                    "technology_stack": self.project_template.technology_stack,
                    "agent_compatibility": compatibility["compatibility"]
                }
            )
            
            # エージェント定義の不足を警告
            if not compatibility["compatibility"]["compatible"]:
                missing_agents = compatibility["compatibility"]["missing_agents"]
                self.log_manager.log_system_event(
                    "warning", "template_loader", 
                    f"Missing agent definitions: {missing_agents}",
                    {"missing_count": len(missing_agents)}
                )
                
        except Exception as e:
            self.log_manager.log_system_event(
                "error", "template_loader", f"Failed to load template: {self.template_name}",
                {"error": str(e)}
            )
            raise
    
    async def execute_workflow(self) -> Dict[str, AgentResult]:
        """テンプレートベースのワークフロー実行 with cross-phase retry support"""
        
        if not self.project_template:
            raise Exception("No project template loaded")
        
        self.log_manager.log_system_event(
            "info", "orchestrator", 
            f"Starting workflow execution for project: {self.project_template.name}"
        )
        
        try:
            # Initialize retry trackers for all phases
            for phase_info in self.project_template.workflow['phases']:
                phase_name = phase_info['phase']
                self.retry_trackers[phase_name] = PhaseRetryTracker(
                    phase_name=phase_name,
                    max_retries=getattr(self, 'max_cross_phase_retries', 3)
                )
            
            # Execute workflow with retry support
            await self._execute_workflow_with_retries()
            
            self.log_manager.log_system_event(
                "info", "orchestrator", "Workflow execution completed successfully"
            )
            
        except Exception as e:
            self.log_manager.log_system_event(
                "error", "orchestrator", f"Workflow execution failed: {str(e)}"
            )
            raise
        
        return self.results
    
    def _check_dependencies(self, dependencies: List[str]) -> bool:
        """依存関係の充足確認"""
        for dependency in dependencies:
            if dependency not in self.results or not self.results[dependency].success:
                return False
        return True
    
    def _find_task_for_phase(self, phase_name: str) -> Optional[AgentTask]:
        """フェーズ名に対応するタスクを検索"""
        for task in self.workflow_tasks:
            if task.task_id.endswith(f"_{phase_name}"):
                return task
        return None
    
    async def _execute_phase(self, phase_name: str, task: AgentTask):
        """単一フェーズの実行"""
        self.logger.info(f"Executing phase: {phase_name}")
        
        # コンテキストファイルの更新
        context_files = self._get_available_context_files(task.context_files)
        task.context_files = context_files
        
        # 依存関係ログ
        if context_files:
            self.log_manager.log_interaction(
                "previous_phases", task.role.value, "dependency",
                context_files, f"{task.role.value} using previous phase outputs as input"
            )
        
        # タスク実行（個別エージェントリトライを無効化、フェーズレベルリトライを使用）
        result = await self.agents[task.role].execute_task(task, timeout=self.default_timeout, max_retries=1)
        self.results[phase_name] = result
        
        # 成果物の共有ログ
        if result.success and result.artifacts:
            self.log_manager.log_interaction(
                task.role.value, "team", "artifact_creation",
                result.artifacts, f"Created {len(result.artifacts)} artifacts in phase {phase_name}"
            )
        
        # Check if phase failed and determine if retry is needed
        if not result.success:
            self.logger.error(f"Phase {phase_name} failed: {result.errors}")
            # Mark failure but don't immediately fail - let retry logic handle it
            result.set_retry_required(f"Phase execution failed: {result.errors}")
        
        # Check for testing phase results that indicate bugs
        elif result.success and self._is_testing_phase(phase_name):
            bugs = self._analyze_test_results(result)
            if bugs:
                self.logger.warning(f"Testing phase {phase_name} found bugs: {bugs}")
                result.set_retry_required(f"Bugs found during testing: {', '.join(bugs)}")
                
        # Check for development phase that might have validation errors
        elif result.success and phase_name.lower() in ['development', 'bug_fixing']:
            # Check if the developed application actually works
            if not self._validate_development_result(result):
                self.logger.warning(f"Development phase {phase_name} produced non-working code")
                result.set_retry_required("Development validation failed - code has runtime errors")
    
    def _get_available_context_files(self, file_list: List[str]) -> List[str]:
        """利用可能なコンテキストファイルのリストを取得"""
        available_files = []
        for file_name in file_list:
            file_path = self.project_dir / file_name
            if file_path.exists():
                available_files.append(file_name)
        return available_files
    
    def get_project_info(self) -> Dict:
        """プロジェクト情報の取得"""
        if not self.project_template:
            return {"error": "No template loaded"}
        
        return {
            "template_name": self.template_name,
            "project_name": self.project_template.name,
            "description": self.project_template.description,
            "technology_stack": self.project_template.technology_stack,
            "phases": [phase['phase'] for phase in self.project_template.workflow['phases']],
            "agents": list(self.project_template.agents.keys()),
            "agents_dir": self.agents_dir
        }
    
    def get_agent_status(self) -> Dict:
        """エージェント定義の状態取得"""
        agent_summaries = {}
        
        for role, agent in self.agents.items():
            agent_def_summary = agent.get_agent_definition_summary()
            context_summary = agent.get_context_summary()
            
            agent_summaries[role.value] = {
                **agent_def_summary,
                **context_summary
            }
        
        return {
            "agents_dir": self.agents_dir,
            "agent_summaries": agent_summaries,
            "total_agents": len(self.agents)
        }
    
    def get_workflow_status(self) -> Dict:
        """ワークフローの状態を取得 with retry information"""
        if not self.project_template:
            return {"error": "No template loaded"}
        
        total_phases = len(self.project_template.workflow['phases'])
        completed_phases = len([r for r in self.results.values() if r.success])
        failed_phases = len([r for r in self.results.values() if not r.success])
        
        # Get retry status
        retry_status = self.get_retry_status()
        
        status = {
            "project_info": self.get_project_info(),
            "agent_status": self.get_agent_status(),
            "total_phases": total_phases,
            "completed_phases": completed_phases,
            "failed_phases": failed_phases,
            "retry_summary": retry_status,
            "phase_details": {}
        }
        
        for phase_name, result in self.results.items():
            phase_detail = {
                "success": result.success,
                "execution_time": result.execution_time,
                "artifacts_count": len(result.artifacts) if result.artifacts else 0,
                "error": result.errors if result.errors else None,
                "retry_count": result.retry_count,
                "requires_retry": result.requires_retry,
                "retry_reason": result.retry_reason
            }
            
            # Add retry tracker info if available
            if phase_name in self.retry_trackers:
                tracker = self.retry_trackers[phase_name]
                phase_detail["retry_tracker"] = {
                    "can_retry": tracker.can_retry(),
                    "retry_history": tracker.retry_history,
                    "triggered_by": tracker.triggered_by
                }
            
            status["phase_details"][phase_name] = phase_detail
        
        return status
    
    def print_workflow_summary(self):
        """ワークフローサマリーの表示"""
        print("\n" + "="*60)
        print(f"🎉 {self.project_template.name.upper()} DEVELOPMENT COMPLETED")
        print("="*60)
        
        print(f"📋 Project: {self.project_template.name}")
        print(f"🔧 Technology: {', '.join(self.project_template.technology_stack[:3])}{'...' if len(self.project_template.technology_stack) > 3 else ''}")
        print(f"👥 Agents Directory: {self.agents_dir}")
        print()
        
        for phase_name, result in self.results.items():
            print(result.summary())
        
        print(f"\n📁 Project files created in: {self.project_dir}/")
        
        # エージェント定義サマリー
        agent_status = self.get_agent_status()
        print(f"\n👥 Agent Definitions Summary:")
        for agent_role, agent_info in agent_status["agent_summaries"].items():
            status_icon = "✅" if agent_info.get("display_name") != agent_role.replace('_', ' ').title() else "⚠️"
            print(f"   {status_icon} {agent_role}: {agent_info.get('display_name', 'N/A')}")
        
        # セッションサマリーの表示
        self.log_manager.print_session_summary()
        
        # ログファイルの場所を表示
        log_info = self.log_manager.get_logs_summary_dict()
        print("\n🔍 DETAILED LOGS:")
        print(f"   📊 Agent execution: {log_info['execution_log_file']}")
        print(f"   🔄 Interactions: {log_info['interaction_log_file']}")
        print(f"   📋 System log: {log_info['system_log_file']}")
        print(f"   📈 Summary: {log_info['summary_file']}")
    
    def get_project_artifacts(self) -> List[str]:
        """プロジェクト全体のアーティファクトリストを取得"""
        all_artifacts = []
        for result in self.results.values():
            if result.artifacts:
                all_artifacts.extend(result.artifacts)
        return sorted(list(set(all_artifacts)))  # 重複除去してソート
    
    def switch_template(self, new_template_name: str):
        """実行時のテンプレート切り替え（リセット付き）"""
        self.template_name = new_template_name
        self.results.clear()
        self._load_project_template()
        
        self.log_manager.log_system_event(
            "info", "orchestrator", f"Template switched to: {new_template_name}"
        )
    
    def list_available_templates(self) -> List[Dict]:
        """利用可能なテンプレートのリスト"""
        return self.template_loader.list_templates_summary()
    
    def validate_current_template(self) -> Dict:
        """現在のテンプレートの検証"""
        if not self.project_template:
            return {"valid": False, "error": "No template loaded"}
        
        # テンプレートローダーのバリデーターを使用
        from .template_loader import TemplateValidator
        validator = TemplateValidator()
        
        # 依存関係の検証
        dependency_errors = validator.validate_workflow_dependencies(self.project_template)
        
        # エージェントロールの検証
        invalid_roles = self.template_loader.validate_agent_roles(self.project_template)
        
        # 専門性カバレッジの検証
        expertise_warnings = validator.validate_agent_expertise_coverage(self.project_template)
        
        # エージェント定義の互換性チェック
        agent_compatibility = self.template_loader.get_agent_requirements_summary(self.template_name)
        
        # Validate retry workflow compatibility
        retry_validation = validator.validate_retry_workflow(self.project_template)
        
        return {
            "valid": len(dependency_errors) == 0 and len(invalid_roles) == 0 and agent_compatibility["compatibility"]["compatible"],
            "dependency_errors": dependency_errors,
            "invalid_roles": invalid_roles,
            "expertise_warnings": expertise_warnings,
            "agent_compatibility": agent_compatibility["compatibility"],
            "agent_details": agent_compatibility["agent_details"],
            "retry_workflow": retry_validation
        }
    
    def get_available_agent_definitions(self) -> List[Dict]:
        """利用可能なエージェント定義のリスト"""
        return self.template_loader.agent_loader.get_agents_summary()
    
    async def _execute_workflow_with_retries(self):
        """Execute workflow with block-level retry support"""
        max_block_retries = 5  # Maximum retry attempts for each block
        
        # Define workflow blocks
        workflow_blocks = self._define_workflow_blocks()
        
        for block_name, block_phases in workflow_blocks.items():
            print(f"\n🎯 Starting workflow block: {block_name}")
            retry_count = 0
            
            # Check if this is a no-retry block
            is_no_retry_block = 'no_retry' in block_name
            effective_max_retries = 1 if is_no_retry_block else max_block_retries
            
            while retry_count < effective_max_retries:
                block_success = True
                failed_phase = None
                
                # Execute all phases in the block
                for phase_name in block_phases:
                    phase_info = self._get_phase_info(phase_name)
                    if not phase_info:
                        continue
                        
                    dependencies = phase_info.get('dependencies', [])
                    
                    # Check dependencies (should be satisfied within the block or from previous blocks)
                    if not self._check_dependencies(dependencies):
                        self.logger.warning(f"Skipping phase {phase_name} due to unmet dependencies")
                        continue
                    
                    # Find and execute task
                    task = self._find_task_for_phase(phase_name)
                    if task:
                        await self._execute_phase(phase_name, task)
                        result = self.results.get(phase_name)
                        
                        if not result or not result.success:
                            print(f"❌ Block {block_name} failed at phase {phase_name}")
                            block_success = False
                            failed_phase = phase_name
                            break
                    else:
                        self.logger.error(f"No task found for phase: {phase_name}")
                        block_success = False
                        failed_phase = phase_name
                        break
                
                if block_success:
                    print(f"✅ Block {block_name} completed successfully")
                    break
                else:
                    retry_count += 1
                    if is_no_retry_block:
                        print(f"💀 Block {block_name} failed - NO RETRY allowed for this block")
                        raise Exception(f"Block {block_name} failed at phase {failed_phase} - no retry allowed")
                    elif retry_count < effective_max_retries:
                        print(f"🔄 Retrying block {block_name} (attempt {retry_count + 1}/{effective_max_retries})")
                        print(f"   Failed phase: {failed_phase}")
                        
                        # Clear results for all phases in this block to retry from the beginning
                        for phase_name in block_phases:
                            if phase_name in self.results:
                                del self.results[phase_name]
                        
                        # Add some delay before retry
                        await asyncio.sleep(2)
                    else:
                        raise Exception(f"Block {block_name} failed after {effective_max_retries} attempts at phase {failed_phase}")
    
    def _define_workflow_blocks(self) -> Dict[str, List[str]]:
        """Define workflow blocks for block-level retry"""
        blocks = {}
        
        # Get all phases from the template
        all_phases = [phase_info['phase'] for phase_info in self.project_template.workflow['phases']]
        
        # Planning phases (PM) - NO RETRY for planning
        planning_phases = [p for p in all_phases if any(keyword in p.lower() for keyword in ['planning', 'concept'])]
        if planning_phases:
            blocks['planning_no_retry'] = planning_phases
        
        # UI Design and Schema block
        ui_phases = [p for p in all_phases if any(keyword in p.lower() for keyword in ['ui', 'design', 'wireframe', 'schema', 'database_design'])]
        if ui_phases:
            blocks['design'] = ui_phases
        
        # Development and Testing block (this is the key - they retry together)
        # Include bug_fixing and retesting as part of development cycle
        dev_test_phases = [p for p in all_phases if any(keyword in p.lower() for keyword in ['development', 'dev', 'test', 'testing', 'qa', 'bug_fixing', 'retesting'])]
        if dev_test_phases:
            blocks['development_testing'] = dev_test_phases
        
        # Security block
        security_phases = [p for p in all_phases if any(keyword in p.lower() for keyword in ['security', 'audit'])]
        if security_phases:
            blocks['security'] = security_phases
        
        # Ensure all phases are covered
        covered_phases = set()
        for block_phases in blocks.values():
            covered_phases.update(block_phases)
        
        uncovered_phases = set(all_phases) - covered_phases
        if uncovered_phases:
            blocks['misc'] = list(uncovered_phases)
        
        print(f"📋 Workflow blocks defined:")
        for block_name, phases in blocks.items():
            print(f"   {block_name}: {phases}")
        
        return blocks
    
    def _get_phase_info(self, phase_name: str) -> Dict:
        """Get phase info from template"""
        for phase_info in self.project_template.workflow['phases']:
            if phase_info['phase'] == phase_name:
                return phase_info
        return None
    
    def _is_testing_phase(self, phase_name: str) -> bool:
        """Check if a phase is a testing phase"""
        testing_keywords = ['test', 'testing', 'qa', 'verification']
        return any(keyword in phase_name.lower() for keyword in testing_keywords)
    
    def _analyze_test_results(self, result: AgentResult) -> List[str]:
        """Analyze test results to find bugs"""
        bugs = []
        output_lower = result.output.lower()
        
        # Look for common bug indicators in test output
        bug_indicators = [
            ('failed', 'test failures detected'),
            ('error', 'errors found in testing'),
            ('exception', 'exceptions during testing'),
            ('bug', 'bugs identified'),
            ('issue', 'issues found'),
            ('problem', 'problems detected'),
            ('fix', 'fixes needed')
        ]
        
        for indicator, description in bug_indicators:
            if indicator in output_lower:
                bugs.append(description)
        
        # Check test report files for more detailed analysis
        if result.artifacts:
            for artifact in result.artifacts:
                if 'test' in artifact.lower() and 'report' in artifact.lower():
                    try:
                        file_path = self.project_dir / artifact
                        if file_path.exists():
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read().lower()
                                if 'fail' in content or 'error' in content:
                                    bugs.append(f"Issues found in {artifact}")
                    except Exception as e:
                        self.logger.warning(f"Failed to analyze test report {artifact}: {e}")
        
        return bugs
    
    def _determine_retry_phase(self, current_phase: str, reason: str) -> Optional[str]:
        """Determine which phase should be retried based on current phase and reason"""
        # Define retry mappings
        retry_mappings = {
            'testing': 'development',
            'retesting': 'bug_fixing',
            'qa': 'development',
            'verification': 'development'
        }
        
        # Check direct mappings first
        for keyword, target_phase in retry_mappings.items():
            if keyword in current_phase.lower():
                return target_phase
        
        # Fallback: if testing found issues, retry development
        if 'test' in current_phase.lower():
            return 'development'
        
        return None
    
    def _validate_development_result(self, result: AgentResult) -> bool:
        """Validate that development phase produced working code"""
        try:
            # Check if app.py exists
            app_path = self.project_dir / "app.py"
            if not app_path.exists():
                return False
            
            # Try basic syntax validation
            import subprocess
            python_cmd = self._get_python_command()
            
            syntax_result = subprocess.run(
                [python_cmd, "-m", "py_compile", str(app_path)],
                cwd=str(self.project_dir),
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return syntax_result.returncode == 0
            
        except Exception as e:
            self.logger.warning(f"Development validation failed: {e}")
            return False
    
    def _get_python_command(self) -> str:
        """Get the appropriate Python command for the system"""
        import shutil
        
        for cmd in ["python3", "python", "py"]:
            if shutil.which(cmd):
                return cmd
        return "python3"
    
    def _can_retry_phase(self, phase_name: str) -> bool:
        """Check if a phase can be retried"""
        tracker = self.retry_trackers.get(phase_name)
        return tracker and tracker.can_retry()
    
    def _trigger_phase_retry(self, retry_phase: str, triggered_by: str, reason: str):
        """Trigger a phase retry"""
        tracker = self.retry_trackers[retry_phase]
        tracker.add_retry_attempt(triggered_by, reason)
        
        # Clear results from retry_phase onwards to re-execute
        phases_to_clear = self._get_phases_from(retry_phase)
        for phase in phases_to_clear:
            if phase in self.results:
                del self.results[phase]
        
        self.log_manager.log_system_event(
            "info", "orchestrator", 
            f"Triggering retry of phase '{retry_phase}' (attempt {tracker.retry_count}) due to {triggered_by}: {reason}"
        )
    
    def _get_phases_from(self, start_phase: str) -> List[str]:
        """Get list of phases starting from a given phase"""
        phases = []
        start_found = False
        
        for phase_info in self.project_template.workflow['phases']:
            phase_name = phase_info['phase']
            if phase_name == start_phase:
                start_found = True
            if start_found:
                phases.append(phase_name)
        
        return phases
    
    def get_retry_status(self) -> Dict[str, Any]:
        """Get the current retry status for all phases"""
        status = {
            "total_phases": len(self.retry_trackers),
            "phases_with_retries": 0,
            "total_retry_attempts": 0,
            "phase_details": {}
        }
        
        for phase_name, tracker in self.retry_trackers.items():
            if tracker.retry_count > 0:
                status["phases_with_retries"] += 1
                status["total_retry_attempts"] += tracker.retry_count
            
            status["phase_details"][phase_name] = {
                "retry_count": tracker.retry_count,
                "max_retries": tracker.max_retries,
                "can_retry": tracker.can_retry(),
                "last_triggered_by": tracker.triggered_by,
                "last_reason": tracker.retry_reason,
                "summary": tracker.get_retry_summary()
            }
        
        return status
    
    def switch_agents_directory(self, new_agents_dir: str):
        """エージェントディレクトリの切り替え"""
        self.agents_dir = new_agents_dir
        
        # エージェントを再作成
        self.agents = AgentFactory.create_all_agents(
            str(self.project_dir), self.log_manager, self.agents_dir
        )
        
        # テンプレートローダーも更新
        self.template_loader = TemplateLoader(
            self.template_loader.templates_dir, self.agents_dir
        )
        
        # 現在のテンプレートを再読み込み
        if self.project_template:
            self._load_project_template()
        
        self.log_manager.log_system_event(
            "info", "orchestrator", f"Agents directory switched to: {new_agents_dir}"
        )
