"""
Template loader and validator for multi-agent system
"""

import yaml
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from models.task import AgentRole, AgentTask
from .agent_loader import AgentLoader


@dataclass
class ProjectTemplate:
    """プロジェクトテンプレートのデータクラス"""
    name: str
    description: str
    technology_stack: List[str]
    workflow: Dict[str, Any]
    agents: Dict[str, Any]
    tasks: Dict[str, Any]
    
    @property
    def agent_roles(self) -> List[str]:
        """利用可能なエージェントロールのリスト"""
        return list(self.agents.keys())
    
    @property
    def task_names(self) -> List[str]:
        """タスク名のリスト"""
        return list(self.tasks.keys())
    
    def get_task_dependencies(self, task_name: str) -> List[str]:
        """指定されたタスクの依存関係を取得"""
        task = self.tasks.get(task_name)
        if task and 'context_files' in task:
            return task['context_files']
        return []
    
    def calculate_complexity_score(self) -> int:
        """テンプレートの複雑度スコアを計算"""
        score = 0
        
        # 技術スタック数による複雑度
        score += len(self.technology_stack) * 10
        
        # フェーズ数による複雑度
        phases = self.workflow.get('phases', [])
        score += len(phases) * 20
        
        # 出力ファイル数による複雑度
        for task in self.tasks.values():
            output_files = task.get('output_files', [])
            score += len(output_files) * 5
        
        # 依存関係による複雑度
        for task in self.tasks.values():
            context_files = task.get('context_files', [])
            score += len(context_files) * 3
        
        # 特定技術の複雑度ボーナス
        complex_techs = ['docker', 'kubernetes', 'sqlalchemy', 'redis', 'celery', 'postgresql']
        for tech in self.technology_stack:
            if any(ct in tech.lower() for ct in complex_techs):
                score += 30
        
        return score
    
    def calculate_timeout(self, base_timeout: int = 600) -> int:
        """複雑度に基づいて動的タイムアウトを計算（秒）"""
        complexity = self.calculate_complexity_score()
        
        # 複雑度レベルの判定
        if complexity <= 50:
            # 簡単 (hello_world等)
            return base_timeout  # 10分
        elif complexity <= 100:
            # 中程度 (simple_calculator等)
            return base_timeout * 2  # 20分
        elif complexity <= 200:
            # 複雑 (simple_blog等)
            return base_timeout * 3  # 30分
        else:
            # 非常に複雑 (ecommerce, 複数DB等)
            return base_timeout * 6  # 60分


class TemplateLoader:
    """テンプレートローダーとバリデーター"""
    
    def __init__(self, templates_dir: str = "./templates", agents_dir: str = "./agents"):
        self.templates_dir = Path(templates_dir or "./templates")
        self.agent_loader = AgentLoader(agents_dir)
        self.logger = logging.getLogger(__name__)
        self.loaded_templates: Dict[str, ProjectTemplate] = {}
        
    def discover_templates(self) -> List[str]:
        """利用可能なテンプレートファイルを発見"""
        if not self.templates_dir.exists():
            self.logger.warning(f"Templates directory not found: {self.templates_dir}")
            return []
        
        template_files = []
        for file_path in self.templates_dir.glob("*.yaml"):
            template_files.append(file_path.stem)
        
        for file_path in self.templates_dir.glob("*.yml"):
            template_files.append(file_path.stem)
            
        self.logger.info(f"Discovered {len(template_files)} templates: {template_files}")
        return sorted(template_files)
    
    def load_template(self, template_name: str) -> ProjectTemplate:
        """指定されたテンプレートを読み込み"""
        if template_name in self.loaded_templates:
            return self.loaded_templates[template_name]
        
        # YAML ファイルを探索
        yaml_file = self.templates_dir / f"{template_name}.yaml"
        yml_file = self.templates_dir / f"{template_name}.yml"
        
        template_file = None
        if yaml_file.exists():
            template_file = yaml_file
        elif yml_file.exists():
            template_file = yml_file
        else:
            raise FileNotFoundError(f"Template file not found: {template_name}")
        
        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                template_data = yaml.safe_load(f)
            
            # テンプレートデータの検証
            self._validate_template_structure(template_data, template_name)
            
            # ProjectTemplate オブジェクトを作成
            project_info = template_data['project']
            template = ProjectTemplate(
                name=project_info['name'],
                description=project_info['description'],
                technology_stack=project_info.get('technology_stack', []),
                workflow=template_data['workflow'],
                agents=template_data['agents'],
                tasks=template_data['tasks']
            )
            
            # エージェント定義との互換性チェック
            compatibility = self.agent_loader.validate_agent_compatibility(template.agent_roles)
            if not compatibility['compatible']:
                self.logger.warning(
                    f"Template {template_name} has missing agent definitions: {compatibility['missing_agents']}"
                )
            
            # キャッシュに保存
            self.loaded_templates[template_name] = template
            
            self.logger.info(f"Successfully loaded template: {template_name}")
            return template
            
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in template {template_name}: {e}")
        except KeyError as e:
            raise ValueError(f"Missing required field in template {template_name}: {e}")
    
    def _validate_template_structure(self, template_data: Dict, template_name: str):
        """テンプレート構造の検証"""
        required_sections = ['project', 'workflow', 'agents', 'tasks']
        
        for section in required_sections:
            if section not in template_data:
                raise ValueError(f"Missing required section '{section}' in template {template_name}")
        
        # project セクションの検証
        project = template_data['project']
        required_project_fields = ['name', 'description']
        for field in required_project_fields:
            if field not in project:
                raise ValueError(f"Missing required field '{field}' in project section")
        
        # workflow セクションの検証
        workflow = template_data['workflow']
        if 'phases' not in workflow:
            raise ValueError("Missing 'phases' in workflow section")
        
        # 各フェーズの検証
        for phase in workflow['phases']:
            required_phase_fields = ['phase', 'agent', 'dependencies', 'parallel']
            for field in required_phase_fields:
                if field not in phase:
                    raise ValueError(f"Missing required field '{field}' in phase: {phase.get('phase', 'unknown')}")
        
        # agents セクションの検証
        agents = template_data['agents']
        for agent_name, agent_info in agents.items():
            if 'role' not in agent_info:
                raise ValueError(f"Missing 'role' in agent: {agent_name}")
            if 'expertise' not in agent_info:
                raise ValueError(f"Missing 'expertise' in agent: {agent_name}")
        
        # tasks セクションの検証
        tasks = template_data['tasks']
        for task_name, task_info in tasks.items():
            required_task_fields = ['agent', 'title', 'prompt', 'output_files', 'context_files']
            for field in required_task_fields:
                if field not in task_info:
                    raise ValueError(f"Missing required field '{field}' in task: {task_name}")
        
        self.logger.debug(f"Template structure validation passed for: {template_name}")
    
    def validate_agent_roles(self, template: ProjectTemplate) -> List[str]:
        """テンプレートのエージェントロールが有効かチェック"""
        # エージェントローダーから利用可能なロールを取得
        available_roles = self.agent_loader.get_available_roles()
        invalid_roles = []
        
        for agent_name in template.agent_roles:
            if agent_name not in available_roles:
                invalid_roles.append(agent_name)
        
        if invalid_roles:
            self.logger.warning(f"Invalid agent roles found: {invalid_roles}")
            self.logger.info(f"Available roles are: {available_roles}")
        
        return invalid_roles
    
    def create_agent_tasks(self, template: ProjectTemplate) -> List[AgentTask]:
        """テンプレートからAgentTaskのリストを生成"""
        tasks = []
        
        # 利用可能なエージェントロールを取得
        available_roles = self.agent_loader.get_available_roles()
        
        # ワークフローの順序に従ってタスクを作成
        for phase_info in template.workflow['phases']:
            phase_name = phase_info['phase']
            agent_name = phase_info['agent']
            dependencies = phase_info.get('dependencies', [])
            
            # 対応するタスク情報を取得
            task_info = template.tasks.get(phase_name)
            if not task_info:
                self.logger.warning(f"Task info not found for phase: {phase_name}")
                continue
            
            # エージェントロールの検証と取得
            if agent_name not in available_roles:
                self.logger.error(f"Agent role not available: {agent_name}")
                continue
            
            try:
                agent_role = AgentRole(agent_name)
            except ValueError:
                self.logger.error(f"Invalid agent role: {agent_name}")
                continue
            
            # AgentTaskを作成
            task = AgentTask(
                role=agent_role,
                prompt=task_info['prompt'],
                task_id=f"{agent_name}_{phase_name}",
                dependencies=[AgentRole(dep) for dep in dependencies if dep in available_roles],
                output_file=task_info['output_files'][0] if task_info['output_files'] else None,
                context_files=task_info.get('context_files', [])
            )
            
            tasks.append(task)
        
        self.logger.info(f"Created {len(tasks)} tasks from template")
        return tasks
    
    def get_template_summary(self, template_name: str) -> Dict[str, Any]:
        """テンプレートのサマリー情報を取得"""
        try:
            template = self.load_template(template_name)
            
            # エージェント互換性チェック
            compatibility = self.agent_loader.validate_agent_compatibility(template.agent_roles)
            
            return {
                "name": template.name,
                "description": template.description,
                "technology_stack": template.technology_stack,
                "phases_count": len(template.workflow['phases']),
                "agents_count": len(template.agents),
                "tasks_count": len(template.tasks),
                "agents": list(template.agents.keys()),
                "phases": [phase['phase'] for phase in template.workflow['phases']],
                "agent_compatibility": compatibility
            }
        except Exception as e:
            return {
                "name": template_name,
                "error": str(e)
            }
    
    def list_templates_summary(self) -> List[Dict[str, Any]]:
        """全テンプレートのサマリーリストを取得"""
        template_names = self.discover_templates()
        summaries = []
        
        for template_name in template_names:
            summary = self.get_template_summary(template_name)
            summaries.append(summary)
        
        return summaries
    
    def export_template_as_json(self, template_name: str, output_path: str):
        """テンプレートをJSON形式でエクスポート"""
        template = self.load_template(template_name)
        
        export_data = {
            "project": {
                "name": template.name,
                "description": template.description,
                "technology_stack": template.technology_stack
            },
            "workflow": template.workflow,
            "agents": template.agents,
            "tasks": template.tasks
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Template exported to: {output_path}")
    
    def get_agent_requirements_summary(self, template_name: str) -> Dict[str, Any]:
        """テンプレートのエージェント要件サマリー"""
        template = self.load_template(template_name)
        compatibility = self.agent_loader.validate_agent_compatibility(template.agent_roles)
        
        agent_details = []
        for agent_name in template.agent_roles:
            agent_def = self.agent_loader.get_agent_by_role(agent_name)
            if agent_def:
                agent_details.append({
                    "role": agent_name,
                    "display_name": agent_def.display_name,
                    "description": agent_def.description,
                    "expertise_summary": agent_def.get_expertise_summary(),
                    "available": True
                })
            else:
                agent_details.append({
                    "role": agent_name,
                    "display_name": agent_name.replace('_', ' ').title(),
                    "description": f"Required for {template.name}",
                    "expertise_summary": "Not defined",
                    "available": False
                })
        
        return {
            "template": template_name,
            "compatibility": compatibility,
            "agent_details": agent_details
        }


class TemplateValidator:
    """テンプレート専用のバリデーター"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def validate_workflow_dependencies(self, template: ProjectTemplate) -> List[str]:
        """ワークフローの依存関係の整合性をチェック"""
        errors = []
        
        # フェーズ名とタスク名のマッピングを作成
        phase_names = {phase['phase'] for phase in template.workflow['phases']}
        task_names = set(template.tasks.keys())
        
        # フェーズとタスクの対応チェック
        for phase in template.workflow['phases']:
            phase_name = phase['phase']
            if phase_name not in task_names:
                errors.append(f"Phase '{phase_name}' has no corresponding task definition")
        
        # 依存関係の循環チェック
        dependency_graph = {}
        for phase in template.workflow['phases']:
            phase_name = phase['phase']
            dependencies = phase.get('dependencies', [])
            dependency_graph[phase_name] = dependencies
        
        # 簡単な循環検出
        for phase_name in dependency_graph:
            if self._has_circular_dependency(dependency_graph, phase_name, set()):
                errors.append(f"Circular dependency detected involving phase: {phase_name}")
        
        return errors
    
    def _has_circular_dependency(self, graph: Dict[str, List[str]], node: str, visited: set) -> bool:
        """循環依存の検出（深さ優先探索）"""
        if node in visited:
            return True
        
        visited.add(node)
        
        for dependency in graph.get(node, []):
            if dependency in graph and self._has_circular_dependency(graph, dependency, visited.copy()):
                return True
        
        return False
    
    def validate_agent_expertise_coverage(self, template: ProjectTemplate) -> List[str]:
        """エージェントの専門性がタスクをカバーしているかチェック"""
        warnings = []
        
        # 簡単なキーワードマッチングによる検証
        for task_name, task_info in template.tasks.items():
            agent_name = task_info['agent']
            agent_info = template.agents.get(agent_name, {})
            agent_expertise = agent_info.get('expertise', [])
            
            # タスクのプロンプトに含まれるキーワードをチェック
            prompt_lower = task_info['prompt'].lower()
            
            # 専門性のキーワードがプロンプトに含まれているかざっくりチェック
            expertise_coverage = any(
                expertise.lower() in prompt_lower 
                for expertise in agent_expertise
            )
            
            if not expertise_coverage:
                warnings.append(
                    f"Task '{task_name}' may not align with agent '{agent_name}' expertise"
                )
        
        return warnings
    
    def validate_retry_workflow(self, template: ProjectTemplate) -> Dict[str, Any]:
        """Validate that the template supports cross-phase retry functionality"""
        validation_result = {
            "supports_retry": False,
            "retry_pairs": [],
            "warnings": [],
            "recommendations": []
        }
        
        phases = [phase['phase'] for phase in template.workflow['phases']]
        
        # Check for common retry patterns
        retry_patterns = [
            (['development', 'testing'], 'development -> testing cycle'),
            (['testing', 'bug_fixing'], 'testing -> bug fixing cycle'),
            (['bug_fixing', 'retesting'], 'bug fixing -> retesting cycle'),
            (['development', 'testing', 'bug_fixing'], 'full development cycle'),
            (['qa', 'development'], 'qa -> development cycle')
        ]
        
        found_patterns = []
        for pattern_phases, description in retry_patterns:
            if all(phase in phases for phase in pattern_phases):
                found_patterns.append(description)
                validation_result["retry_pairs"].append(pattern_phases)
        
        if found_patterns:
            validation_result["supports_retry"] = True
            validation_result["detected_patterns"] = found_patterns
        else:
            validation_result["warnings"].append(
                "No common retry patterns detected. Consider adding testing and bug_fixing phases."
            )
        
        # Check for testing phases that can trigger retries
        testing_phases = [p for p in phases if any(keyword in p.lower() for keyword in ['test', 'qa', 'verification'])]
        if not testing_phases:
            validation_result["warnings"].append(
                "No testing phases found. Cross-phase retry works best with testing phases that can detect bugs."
            )
        
        # Check for development phases that can be retried
        dev_phases = [p for p in phases if any(keyword in p.lower() for keyword in ['develop', 'implementation', 'coding'])]
        if not dev_phases:
            validation_result["warnings"].append(
                "No development phases found. Cross-phase retry needs development phases to fix bugs."
            )
        
        # Recommendations
        if 'testing' in phases and 'development' in phases:
            validation_result["recommendations"].append(
                "Consider adding a 'bug_fixing' phase between testing and retesting for better retry workflow."
            )
        
        if len(testing_phases) == 1:
            validation_result["recommendations"].append(
                "Consider adding a 'retesting' phase to verify bug fixes."
            )
        
        return validation_result
