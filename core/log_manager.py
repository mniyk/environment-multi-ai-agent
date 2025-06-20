"""
Log management system for multi-agent orchestrator
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict

from models.log import AgentExecutionLog, InteractionLog, SystemLog, SessionSummary


class LogManager:
    """包括的なログ管理システム"""
    
    def __init__(self, log_dir: str = "./logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.execution_logs: List[AgentExecutionLog] = []
        self.interaction_logs: List[InteractionLog] = []
        self.system_logs: List[SystemLog] = []
        
        # ロガーを先に初期化
        self.logger = logging.getLogger(__name__)
        
        # ログファイル設定
        self.setup_log_files()
        
    def setup_log_files(self):
        """ログファイルの初期化"""
        session_dir = self.log_dir / f"session_{self.session_id}"
        session_dir.mkdir(exist_ok=True)
        
        self.execution_log_file = session_dir / "agent_execution.jsonl"
        self.interaction_log_file = session_dir / "agent_interactions.jsonl"
        self.claude_conversation_file = session_dir / "claude_conversations.jsonl"
        self.system_log_file = session_dir / "system.log"
        self.summary_file = session_dir / "session_summary.json"
        
        # システムログファイルハンドラー設定
        file_handler = logging.FileHandler(self.system_log_file)
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        
        # ルートロガーにファイルハンドラー追加
        logging.getLogger().addHandler(file_handler)
        
        self.logger.info(f"Log session started: {self.session_id}")
    
    def log_agent_start(self, agent_role: str, task_id: str, prompt: str, context_files: List[str] = None) -> AgentExecutionLog:
        """エージェント実行開始ログ"""
        execution_log = AgentExecutionLog(
            agent_role=agent_role,
            task_id=task_id,
            start_time=datetime.now(),
            prompt_length=len(prompt),
            context_files_count=len(context_files or [])
        )
        
        self.execution_logs.append(execution_log)
        
        # リアルタイムログ出力
        print(f"🚀 [{datetime.now().strftime('%H:%M:%S')}] {agent_role} started task: {task_id}")
        
        # ファイルに保存
        self._write_execution_log(execution_log)
        
        return execution_log
    
    def log_agent_end(self, execution_log: AgentExecutionLog, success: bool, 
                     output: str = "", artifacts: List[str] = None, error: str = None):
        """エージェント実行終了ログ"""
        execution_log.end_time = datetime.now()
        execution_log.status = "completed" if success else "failed"
        execution_log.output_length = len(output)
        execution_log.artifacts_created = artifacts or []
        execution_log.error_message = error
        execution_log.execution_time_seconds = (execution_log.end_time - execution_log.start_time).total_seconds()
        
        # リアルタイムログ出力
        status_emoji = "✅" if success else "❌"
        duration = execution_log.execution_time_seconds
        print(f"{status_emoji} [{datetime.now().strftime('%H:%M:%S')}] {execution_log.agent_role} completed in {duration:.1f}s")
        
        if artifacts:
            print(f"   📁 Created: {', '.join(artifacts)}")
        
        if error:
            print(f"   💥 Error: {error}")
        
        # ファイルに保存
        self._write_execution_log(execution_log)
    
    def log_claude_code_command(self, agent_role: str, task_id: str, command: str):
        """Claude Codeコマンド実行ログ"""
        # 該当する実行ログを見つけて更新
        for log in self.execution_logs:
            if log.agent_role == agent_role and log.task_id == task_id:
                log.claude_code_commands.append(command)
                break
        
        print(f"   🔧 [{agent_role}] Executed: {command[:50]}...")
    
    def log_interaction(self, from_agent: str, to_agent: str, interaction_type: str, 
                       files_shared: List[str] = None, message: str = ""):
        """エージェント間相互作用ログ"""
        interaction_log = InteractionLog(
            timestamp=datetime.now(),
            from_agent=from_agent,
            to_agent=to_agent,
            interaction_type=interaction_type,
            files_shared=files_shared or [],
            message=message
        )
        
        self.interaction_logs.append(interaction_log)
        
        print(f"🔄 [{datetime.now().strftime('%H:%M:%S')}] {from_agent} → {to_agent}: {interaction_type}")
        if files_shared:
            print(f"   📤 Shared: {', '.join(files_shared)}")
        
        # ファイルに保存
        self._write_interaction_log(interaction_log)
    
    def log_system_event(self, level: str, component: str, message: str, details: Dict = None):
        """システムイベントログ"""
        system_log = SystemLog(
            timestamp=datetime.now(),
            level=level,
            component=component,
            message=message,
            details=details or {}
        )
        
        self.system_logs.append(system_log)
        
        # 標準ログにも出力
        if level == "error":
            self.logger.error(f"[{component}] {message}")
        elif level == "warning":
            self.logger.warning(f"[{component}] {message}")
        else:
            self.logger.info(f"[{component}] {message}")
    
    def _write_execution_log(self, log: AgentExecutionLog):
        """実行ログをファイルに書き込み"""
        with open(self.execution_log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log.to_dict(), ensure_ascii=False) + '\n')
    
    def _write_interaction_log(self, log: InteractionLog):
        """相互作用ログをファイルに書き込み"""
        with open(self.interaction_log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log.to_dict(), ensure_ascii=False) + '\n')
    
    def log_claude_conversation(self, agent_role: str, task_id: str, prompt: str, 
                              stdout: str, stderr: str, return_code: int):
        """Claude Codeとの詳細な会話ログを保存"""
        conversation_log = {
            "timestamp": datetime.now().isoformat(),
            "agent_role": agent_role,
            "task_id": task_id,
            "prompt": prompt,
            "claude_response": {
                "stdout": stdout,
                "stderr": stderr,
                "return_code": return_code
            },
            "prompt_length": len(prompt),
            "response_length": len(stdout)
        }
        
        # Claude会話ログファイルに書き込み
        with open(self.claude_conversation_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(conversation_log, ensure_ascii=False) + '\n')
        
        # システムログにも記録
        self.log_system_event(
            "info", f"claude_conversation_{agent_role}",
            f"Claude conversation logged for task {task_id}",
            {
                "prompt_length": len(prompt),
                "response_length": len(stdout),
                "return_code": return_code
            }
        )
    
    def generate_session_summary(self) -> SessionSummary:
        """セッション全体のサマリー生成"""
        if not self.execution_logs:
            # デフォルト値でサマリーを作成
            start_time = end_time = datetime.now()
            total_execution_time = 0
            successful_tasks = failed_tasks = 0
            agents_involved = []
            total_artifacts = 0
            claude_code_commands_count = 0
        else:
            start_time = min(log.start_time for log in self.execution_logs)
            end_time = max((log.end_time for log in self.execution_logs if log.end_time), default=datetime.now())
            total_execution_time = sum(log.execution_time_seconds for log in self.execution_logs)
            successful_tasks = len([log for log in self.execution_logs if log.status == "completed"])
            failed_tasks = len([log for log in self.execution_logs if log.status == "failed"])
            agents_involved = list(set(log.agent_role for log in self.execution_logs))
            total_artifacts = sum(len(log.artifacts_created) for log in self.execution_logs)
            claude_code_commands_count = sum(len(log.claude_code_commands) for log in self.execution_logs)
        
        summary = SessionSummary(
            session_id=self.session_id,
            start_time=start_time,
            end_time=end_time,
            total_execution_time_seconds=total_execution_time,
            total_tasks=len(self.execution_logs),
            successful_tasks=successful_tasks,
            failed_tasks=failed_tasks,
            agents_involved=agents_involved,
            total_artifacts_created=total_artifacts,
            total_interactions=len(self.interaction_logs),
            error_count=len([log for log in self.system_logs if log.level == "error"]),
            claude_code_commands_count=claude_code_commands_count
        )
        
        # ファイルに保存
        with open(self.summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary.to_dict(), f, indent=2, ensure_ascii=False)
        
        return summary
    
    def print_session_summary(self):
        """セッションサマリーの表示"""
        summary = self.generate_session_summary()
        
        print("\n" + "="*60)
        print("📊 SESSION SUMMARY")
        print("="*60)
        print(f"Session ID: {summary.session_id}")
        print(f"Duration: {summary.total_execution_time_seconds:.1f} seconds")
        print(f"Tasks: {summary.successful_tasks}/{summary.total_tasks} successful")
        print(f"Success Rate: {summary.success_rate:.1%}")
        print(f"Agents: {', '.join(summary.agents_involved)}")
        print(f"Artifacts: {summary.total_artifacts_created} files created")
        print(f"Interactions: {summary.total_interactions}")
        print(f"Commands: {summary.claude_code_commands_count} Claude Code executions")
        
        if summary.failed_tasks > 0:
            print(f"⚠️  Failed tasks: {summary.failed_tasks}")
        
        if summary.error_count > 0:
            print(f"🚨 System errors: {summary.error_count}")
        
        print(f"📁 Logs saved in: {self.log_dir}/session_{self.session_id}/")
    
    def get_logs_summary_dict(self) -> Dict:
        """ログの要約情報を辞書で取得"""
        summary = self.generate_session_summary()
        return {
            "session_id": summary.session_id,
            "execution_log_file": str(self.execution_log_file),
            "interaction_log_file": str(self.interaction_log_file),
            "system_log_file": str(self.system_log_file),
            "summary_file": str(self.summary_file),
            "summary": summary.to_dict()
        }
