#!/usr/bin/env python3
"""
Multi-Agent TODO App Development System
Main execution entry point
"""

import asyncio
import argparse
import logging
import sys
import subprocess
from pathlib import Path

from config import Config, TemplateConfig
from core.orchestrator import MultiAgentOrchestrator
from core.conversation_replayer import ConversationReplayer


def setup_logging():
    """ログ設定の初期化"""
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL),
        format=Config.LOG_FORMAT
    )


def validate_environment():
    """環境の事前チェック"""
    errors = Config.validate()
    
    # Claude Code SDK の存在確認
    try:
        import claude_code_sdk
        print("✅ Claude Code SDK available")
    except ImportError:
        print("⚠️ Claude Code SDK not available - using fallback mode")
        # SDKがなくてもモック実装で動作するため、エラーにはしない
    
    if errors:
        print("❌ Environment validation failed:")
        for error in errors:
            print(f"   • {error}")
        print("\n💡 Setup instructions:")
        print("   1. Install Claude Code SDK: pip install claude-code-sdk")
        print("   2. Or continue with fallback mode (mock responses)")
        return False
    
    print("✅ Environment validation passed")
    return True


async def run_development_workflow(project_dir: str = None, template_name: str = None, 
                                  templates_dir: str = None, agents_dir: str = None, dry_run: bool = False, timeout: int = 1800, max_retries: int = 3):
    """開発ワークフローの実行"""
    
    if dry_run:
        print("🔍 DRY RUN MODE - No actual tasks will be executed")
        
        # テンプレートとエージェントの検証のみ実行
        try:
            from core.template_loader import TemplateLoader
            from core.agent_loader import AgentLoader
            
            # エージェント定義の検証
            agent_loader = AgentLoader(agents_dir)
            print(f"\n👥 Validating agent definitions in: {agents_dir or TemplateConfig.DEFAULT_AGENTS_DIR}")
            agents = agent_loader.get_agents_summary()
            
            print(f"   Found {len(agents)} agent definitions:")
            for agent in agents:
                print(f"   ✅ {agent['role']}: {agent['display_name']}")
            
            # テンプレートの検証
            loader = TemplateLoader(templates_dir, agents_dir)
            
            if template_name:
                print(f"\n📋 Validating template: {template_name}")
                template = loader.load_template(template_name)
                
                # エージェント互換性チェック
                agent_req_summary = loader.get_agent_requirements_summary(template_name)
                compatibility = agent_req_summary["compatibility"]
                
                print(f"✅ Template validation passed")
                print(f"   Project: {template.name}")
                print(f"   Tasks: {len(template.tasks)}")
                print(f"   Agents: {', '.join(template.agent_roles)}")
                print(f"   Agent Compatibility: {compatibility['coverage_percentage']:.1f}%")
                
                if not compatibility['compatible']:
                    print(f"   ⚠️  Missing agents: {', '.join(compatibility['missing_agents'])}")
                
            else:
                print("\n📋 Available templates:")
                templates = loader.list_templates_summary()
                for template_info in templates:
                    if 'error' in template_info:
                        print(f"   ❌ {template_info['name']}: {template_info['error']}")
                    else:
                        print(f"   ✅ {template_info['name']}: {template_info['description']}")
                        
        except Exception as e:
            print(f"❌ Validation failed: {e}")
        
        return True
    
    # テンプレート選択
    if not template_name:
        template_name = select_template(templates_dir, agents_dir)
        if not template_name:
            print("❌ No template selected. Exiting.")
            return False
    
    print("🚀 Starting Multi-Agent Development System")
    print("="*60)
    
    # オーケストレーター初期化
    try:
        orchestrator = MultiAgentOrchestrator(project_dir, template_name, templates_dir, agents_dir, max_retries)
        orchestrator.default_timeout = timeout  # タイムアウトを設定
        print(f"⏱️  Timeout setting: {timeout}s ({timeout//60}min {timeout%60}s)")
        print(f"🔄 Max retries per task: {max_retries}")
    except Exception as e:
        print(f"❌ Failed to initialize orchestrator: {e}")
        return False
    
    # プロジェクト情報表示
    project_info = orchestrator.get_project_info()
    print(f"📋 Project: {project_info['project_name']}")
    print(f"🔧 Technology: {', '.join(project_info['technology_stack'][:3])}{'...' if len(project_info['technology_stack']) > 3 else ''}")
    print(f"👥 Agents: {', '.join(project_info['agents'])}")
    print(f"🔄 Phases: {len(project_info['phases'])}")
    print(f"📁 Agent Definitions: {project_info['agents_dir']}")
    print()
    
    try:
        # ワークフロー実行
        results = await orchestrator.execute_workflow()
        
        # 結果レポート
        orchestrator.print_workflow_summary()
        
        # 成功判定
        failed_count = len([r for r in results.values() if not r.success])
        if failed_count == 0:
            print("\n🎉 All phases completed successfully!")
            return True
        else:
            print(f"\n⚠️  {failed_count} phase(s) failed. Check logs for details.")
            return False
            
    except KeyboardInterrupt:
        print("\n⚠️  Development workflow interrupted by user")
        orchestrator.log_manager.log_system_event(
            "warning", "main", "Workflow interrupted by user"
        )
        return False
        
    except Exception as e:
        print(f"\n💥 Workflow execution failed: {str(e)}")
        orchestrator.log_manager.log_system_event(
            "error", "main", f"Workflow execution failed: {str(e)}"
        )
        orchestrator.log_manager.print_session_summary()
        raise


def select_template(templates_dir: str = None, agents_dir: str = None) -> str:
    """対話式テンプレート選択"""
    from core.template_loader import TemplateLoader
    
    try:
        loader = TemplateLoader(templates_dir, agents_dir)
        templates = loader.list_templates_summary()
        
        if not templates:
            print("❌ No templates found in templates directory")
            return None
        
        print("\n📋 Available Project Templates:")
        print("-" * 50)
        
        valid_templates = []
        for i, template_info in enumerate(templates, 1):
            if 'error' in template_info:
                print(f"   {i}. ❌ {template_info['name']}: {template_info['error']}")
            else:
                # エージェント互換性表示
                compatibility = template_info.get('agent_compatibility', {})
                compat_icon = "✅" if compatibility.get('compatible', True) else "⚠️"
                
                print(f"   {i}. {compat_icon} {template_info['name']}")
                print(f"      {template_info['description']}")
                print(f"      📊 {template_info['phases_count']} phases, {template_info['agents_count']} agents")
                
                if not compatibility.get('compatible', True):
                    missing = compatibility.get('missing_agents', [])
                    print(f"      ⚠️  Missing agents: {', '.join(missing)}")
                
                if template_info.get('technology_stack'):
                    tech_stack = ', '.join(template_info['technology_stack'][:3])
                    if len(template_info['technology_stack']) > 3:
                        tech_stack += '...'
                    print(f"      🔧 {tech_stack}")
                print()
                valid_templates.append((i, template_info['name']))
        
        if not valid_templates:
            print("❌ No valid templates available")
            return None
        
        # ユーザー選択
        while True:
            try:
                choice = input(f"Select template (1-{len(templates)}) or 'q' to quit: ").strip()
                if choice.lower() == 'q':
                    return None
                
                choice_num = int(choice)
                for num, template_name in valid_templates:
                    if num == choice_num:
                        return template_name
                
                print(f"❌ Invalid choice. Please select 1-{len(templates)}")
                
            except ValueError:
                print("❌ Please enter a number or 'q'")
            except KeyboardInterrupt:
                print("\n👋 Selection cancelled")
                return None
                
    except Exception as e:
        print(f"❌ Failed to load templates: {e}")
        return None


def list_templates(templates_dir: str = None, agents_dir: str = None):
    """利用可能なテンプレートの一覧表示"""
    from core.template_loader import TemplateLoader
    
    try:
        loader = TemplateLoader(templates_dir, agents_dir)
        templates = loader.list_templates_summary()
        
        print("📋 Available Project Templates")
        print("=" * 60)
        
        if not templates:
            print("❌ No templates found")
            return
        
        for template_info in templates:
            if 'error' in template_info:
                print(f"\n❌ {template_info['name']}")
                print(f"   Error: {template_info['error']}")
            else:
                compatibility = template_info.get('agent_compatibility', {})
                compat_status = "✅ Compatible" if compatibility.get('compatible', True) else "⚠️  Partial"
                
                print(f"\n{compat_status} {template_info['name']}")
                print(f"   Description: {template_info['description']}")
                print(f"   Phases: {template_info['phases_count']}")
                print(f"   Agents: {template_info['agents_count']}")
                
                if not compatibility.get('compatible', True):
                    missing = compatibility.get('missing_agents', [])
                    print(f"   Missing Agents: {', '.join(missing)}")
                
                if template_info.get('technology_stack'):
                    print(f"   Technology: {', '.join(template_info['technology_stack'])}")
                print(f"   Phases: {', '.join(template_info.get('phases', []))}")
                
    except Exception as e:
        print(f"❌ Failed to list templates: {e}")


def list_agents(agents_dir: str = None):
    """利用可能なエージェント定義の一覧表示"""
    from core.agent_loader import AgentLoader
    
    try:
        loader = AgentLoader(agents_dir)
        agents = loader.get_agents_summary()
        
        print("👥 Available Agent Definitions")
        print("=" * 60)
        
        if not agents:
            print("❌ No agent definitions found")
            return
        
        for agent in agents:
            print(f"\n✅ {agent['role']}")
            print(f"   Display Name: {agent['display_name']}")
            print(f"   Description: {agent['description']}")
            print(f"   Expertise: {agent['expertise_count']} areas")
            print(f"   Summary: {agent['expertise_summary']}")
            if agent['specializations_count'] > 0:
                print(f"   Specializations: {agent['specializations_count']}")
            print(f"   Context Keywords: {agent['context_keywords_count']}")
                
    except Exception as e:
        print(f"❌ Failed to list agents: {e}")


def validate_template(template_name: str, templates_dir: str = None, agents_dir: str = None):
    """テンプレートの詳細検証"""
    from core.template_loader import TemplateLoader, TemplateValidator
    
    try:
        loader = TemplateLoader(templates_dir, agents_dir)
        template = loader.load_template(template_name)
        validator = TemplateValidator()
        
        print(f"🔍 Validating template: {template_name}")
        print("=" * 50)
        
        # 基本情報
        print(f"✅ Template loaded successfully")
        print(f"   Project: {template.name}")
        print(f"   Tasks: {len(template.tasks)}")
        print(f"   Agents: {len(template.agents)}")
        
        # エージェント互換性チェック
        agent_req_summary = loader.get_agent_requirements_summary(template_name)
        compatibility = agent_req_summary["compatibility"]
        
        if compatibility['compatible']:
            print(f"\n✅ All required agent definitions are available")
        else:
            print(f"\n❌ Missing agent definitions:")
            for agent in agent_req_summary["agent_details"]:
                if not agent["available"]:
                    print(f"   • {agent['role']}: {agent['description']}")
        
        print(f"\n📊 Agent Compatibility: {compatibility['coverage_percentage']:.1f}%")
        
        # 依存関係検証
        dependency_errors = validator.validate_workflow_dependencies(template)
        if dependency_errors:
            print(f"\n❌ Dependency errors found:")
            for error in dependency_errors:
                print(f"   • {error}")
        else:
            print(f"\n✅ Workflow dependencies are valid")
        
        # 専門性検証
        expertise_warnings = validator.validate_agent_expertise_coverage(template)
        if expertise_warnings:
            print(f"\n⚠️  Expertise coverage warnings:")
            for warning in expertise_warnings:
                print(f"   • {warning}")
        else:
            print(f"\n✅ Agent expertise coverage looks good")
        
        overall_valid = len(dependency_errors) == 0 and compatibility['compatible']
        print(f"\n{'✅ Template is valid and ready to use' if overall_valid else '❌ Template has issues that need attention'}")
        
    except Exception as e:
        print(f"❌ Template validation failed: {e}")


def validate_agents(agents_dir: str = None):
    """エージェント定義の詳細検証"""
    from core.agent_loader import AgentLoader
    
    try:
        loader = AgentLoader(agents_dir)
        agents = loader.load_all_agents()
        
        print(f"🔍 Validating agent definitions in: {agents_dir or TemplateConfig.DEFAULT_AGENTS_DIR}")
        print("=" * 60)
        
        if not agents:
            print("❌ No agent definitions found")
            return
        
        print(f"✅ Found {len(agents)} agent definitions:")
        
        for agent_def in agents.values():
            print(f"\n👤 {agent_def.role} ({agent_def.display_name})")
            print(f"   Description: {agent_def.description}")
            print(f"   Expertise: {len(agent_def.expertise)} areas")
            print(f"   Instructions: {len(agent_def.instructions)} characters")
            print(f"   Context Keywords: {len(agent_def.context_keywords)}")
            print(f"   Specializations: {len(agent_def.specializations)}")
            print(f"   Collaboration: {len(agent_def.collaboration)}")
        
        print(f"\n✅ All agent definitions are valid")
        
    except Exception as e:
        print(f"❌ Agent validation failed: {e}")


def replay_conversations(project_dir: str, limit: int = None, conversation_id: int = None, list_sessions: bool = False):
    """
    Claude会話ログの再現表示
    
    Args:
        project_dir: プロジェクトディレクトリのパス
        limit: 表示する会話数の制限
        conversation_id: 特定の会話IDのみ表示
        list_sessions: セッション一覧表示フラグ
    """
    try:
        replayer = ConversationReplayer(project_dir)
        
        if list_sessions:
            replayer.list_available_sessions()
        else:
            replayer.replay_conversations(limit=limit, conversation_id=conversation_id)
            
    except Exception as e:
        print(f"❌ 会話再現に失敗しました: {e}")


def create_project_structure(project_dir: str):
    """プロジェクト構造の事前作成（最小限）"""
    project_path = Path(project_dir)
    
    # 最小限のディレクトリ構造（ログ用のみ）
    directories = [
        "logs"  # ログ保存用ディレクトリのみ
    ]
    
    for dir_name in directories:
        (project_path / dir_name).mkdir(parents=True, exist_ok=True)
    
    print(f"📁 Project directory created: {project_path.resolve()}")
    print(f"   - logs/ (for session logs)")
    print("   - Other directories will be created by agents as needed")


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="Multi-Agent Development System with Template and Agent Support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                                    # Interactive template selection
  python main.py --template simple_todo           # Use specific template
  python main.py --template simple_todo --project-dir ./my_todo_app
  python main.py --list-templates                  # List available templates
  python main.py --list-agents                     # List available agent definitions
  python main.py --validate-template simple_todo  # Validate template
  python main.py --validate-agents                 # Validate agent definitions
  python main.py --agents-dir ./custom_agents     # Use custom agent definitions
  python main.py --dry-run                         # Validate setup only
  python main.py --setup-only                      # Create project structure only
  python main.py --timeout 300                     # Set timeout to 5 minutes for quick test
  python main.py --template simple_todo --timeout 3600  # Set timeout to 60 minutes for complex template
  python main.py --template simple_todo --max-retries 3  # Set max block retries to 3
  python main.py --replay-conversations            # Replay latest conversations
  python main.py --replay-conversations --replay-limit 3  # Replay last 3 conversations
  python main.py --replay-conversations --replay-id 2     # Replay specific conversation
  python main.py --list-sessions                   # List available session logs
  python main.py --replay-conversations --project-dir ./my_project  # Replay from specific project
  python main.py --list-sessions --project-dir ./my_project         # List sessions from specific project

Use --list-templates to see available project templates.
Use --list-agents to see available agent definitions.
        """
    )
    
    parser.add_argument(
        "--project-dir", 
        default=Config.DEFAULT_PROJECT_DIR,
        help=f"Project directory (default: {Config.DEFAULT_PROJECT_DIR})"
    )
    
    parser.add_argument(
        "--template", "-t",
        help="Project template name (interactive selection if not specified)"
    )
    
    parser.add_argument(
        "--templates-dir",
        help=f"Templates directory (default: {TemplateConfig.DEFAULT_TEMPLATES_DIR})"
    )
    
    parser.add_argument(
        "--agents-dir",
        help=f"Agent definitions directory (default: {TemplateConfig.DEFAULT_AGENTS_DIR})"
    )
    
    parser.add_argument(
        "--list-templates", "-l",
        action="store_true",
        help="List available templates and exit"
    )
    
    parser.add_argument(
        "--list-agents", "-a",
        action="store_true",
        help="List available agent definitions and exit"
    )
    
    parser.add_argument(
        "--validate-template",
        metavar="TEMPLATE",
        help="Validate specific template and exit"
    )
    
    parser.add_argument(
        "--validate-agents",
        action="store_true",
        help="Validate agent definitions and exit"
    )
    
    parser.add_argument(
        "--dry-run", 
        action="store_true",
        help="Validate environment, templates, and agents without executing tasks"
    )
    
    parser.add_argument(
        "--setup-only", 
        action="store_true",
        help="Only create project structure and exit"
    )
    
    parser.add_argument(
        "--verbose", "-v", 
        action="store_true",
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        "--replay-conversations", "-r",
        action="store_true",
        help="Replay Claude conversations from latest session logs"
    )
    
    parser.add_argument(
        "--replay-limit",
        type=int,
        metavar="N",
        help="Limit number of conversations to replay"
    )
    
    parser.add_argument(
        "--replay-id",
        type=int,
        metavar="ID",
        help="Replay specific conversation by ID"
    )
    
    parser.add_argument(
        "--list-sessions",
        action="store_true", 
        help="List available conversation sessions"
    )
    
    parser.add_argument(
        "--timeout",
        type=int,
        default=1800,
        metavar="SECONDS",
        help="Timeout for agent execution in seconds (default: 1800 = 30 minutes)"
    )
    
    parser.add_argument(
        "--max-retries",
        type=int,
        default=5,
        metavar="COUNT",
        help="Maximum retry attempts per workflow block (default: 5)"
    )
    
    args = parser.parse_args()
    
    # ログレベル調整
    if args.verbose:
        Config.LOG_LEVEL = "DEBUG"
    
    # ログ設定
    setup_logging()
    
    print("🤖 Multi-Agent Development System")
    print("=" * 60)
    
    # テンプレート一覧表示
    if args.list_templates:
        list_templates(args.templates_dir, args.agents_dir)
        return
    
    # エージェント一覧表示
    if args.list_agents:
        list_agents(args.agents_dir)
        return
    
    # テンプレート検証
    if args.validate_template:
        validate_template(args.validate_template, args.templates_dir, args.agents_dir)
        return
    
    # エージェント検証
    if args.validate_agents:
        validate_agents(args.agents_dir)
        return
    
    # 会話再現・セッション管理
    if args.replay_conversations or args.list_sessions:
        replay_conversations(
            args.project_dir, 
            limit=args.replay_limit,
            conversation_id=args.replay_id,
            list_sessions=args.list_sessions
        )
        return
    
    # 環境チェック（dry-runの場合はClaude CLIチェックをスキップ）
    if not args.dry_run and not validate_environment():
        sys.exit(1)
    
    # プロジェクト構造作成
    if not args.dry_run:
        create_project_structure(args.project_dir)
    
    if args.setup_only:
        print("✅ Project structure setup completed")
        return
    
    # 開発ワークフロー実行
    try:
        success = asyncio.run(run_development_workflow(
            args.project_dir, 
            args.template,
            args.templates_dir,
            args.agents_dir,
            args.dry_run,
            args.timeout,
            args.max_retries
        ))
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(130)  # Standard exit code for Ctrl+C
        
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
