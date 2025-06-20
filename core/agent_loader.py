"""
Agent definition loader and validator for multi-agent system
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class AgentDefinition:
    """エージェント定義のデータクラス"""
    role: str
    display_name: str
    description: str
    expertise: List[str]
    instructions: str
    context_keywords: List[str] = field(default_factory=list)
    specializations: Dict[str, str] = field(default_factory=dict)
    output_guidelines: Dict[str, str] = field(default_factory=dict)
    collaboration: Dict[str, str] = field(default_factory=dict)
    
    def build_prompt(self, base_prompt: str, context: str, working_dir: str) -> str:
        """完全なプロンプトの構築"""
        return f"""
{self.instructions}

=== 作業コンテキスト ===
{context}

=== 指示 ===
{base_prompt}

作業ディレクトリ: {working_dir}
現在のロール: {self.role} ({self.display_name})

出力は明確で実用的なものにし、必要に応じてファイルを作成してください。
"""

    def get_expertise_summary(self) -> str:
        """専門分野のサマリー"""
        return ", ".join(self.expertise[:3]) + ("..." if len(self.expertise) > 3 else "")
    
    def matches_context(self, prompt: str) -> int:
        """プロンプトとの関連度を計算（0-100）"""
        prompt_lower = prompt.lower()
        matches = 0
        
        for keyword in self.context_keywords:
            if keyword.lower() in prompt_lower:
                matches += 1
        
        # 専門分野とのマッチングも考慮
        for expertise in self.expertise:
            if any(word in prompt_lower for word in expertise.lower().split()):
                matches += 0.5
        
        # 0-100の範囲にスケール
        max_possible = len(self.context_keywords) + len(self.expertise) * 0.5
        return int((matches / max_possible * 100)) if max_possible > 0 else 0


class AgentLoader:
    """エージェント定義ローダーとバリデーター"""
    
    def __init__(self, agents_dir: str = "./agents"):
        self.agents_dir = Path(agents_dir or "./agents")
        self.logger = logging.getLogger(__name__)
        self.loaded_agents: Dict[str, AgentDefinition] = {}
        
    def discover_agents(self) -> List[str]:
        """利用可能なエージェント定義ファイルを発見"""
        if not self.agents_dir.exists():
            self.logger.warning(f"Agents directory not found: {self.agents_dir}")
            return []
        
        agent_files = []
        for file_path in self.agents_dir.glob("*.yaml"):
            agent_files.append(file_path.stem)
        
        for file_path in self.agents_dir.glob("*.yml"):
            agent_files.append(file_path.stem)
            
        self.logger.info(f"Discovered {len(agent_files)} agent definitions: {agent_files}")
        return sorted(agent_files)
    
    def load_agent(self, agent_name: str) -> AgentDefinition:
        """指定されたエージェント定義を読み込み"""
        if agent_name in self.loaded_agents:
            return self.loaded_agents[agent_name]
        
        # YAML ファイルを探索
        yaml_file = self.agents_dir / f"{agent_name}.yaml"
        yml_file = self.agents_dir / f"{agent_name}.yml"
        
        agent_file = None
        if yaml_file.exists():
            agent_file = yaml_file
        elif yml_file.exists():
            agent_file = yml_file
        else:
            raise FileNotFoundError(f"Agent definition file not found: {agent_name}")
        
        try:
            with open(agent_file, 'r', encoding='utf-8') as f:
                agent_data = yaml.safe_load(f)
            
            # エージェント定義の検証
            self._validate_agent_structure(agent_data, agent_name)
            
            # AgentDefinition オブジェクトを作成
            agent = AgentDefinition(
                role=agent_data['role'],
                display_name=agent_data['display_name'],
                description=agent_data['description'],
                expertise=agent_data['expertise'],
                instructions=agent_data['instructions'],
                context_keywords=agent_data.get('context_keywords', []),
                specializations=agent_data.get('specializations', {}),
                output_guidelines=agent_data.get('output_guidelines', {}),
                collaboration=agent_data.get('collaboration', {})
            )
            
            # キャッシュに保存
            self.loaded_agents[agent_name] = agent
            
            self.logger.info(f"Successfully loaded agent definition: {agent_name}")
            return agent
            
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in agent definition {agent_name}: {e}")
        except KeyError as e:
            raise ValueError(f"Missing required field in agent definition {agent_name}: {e}")
    
    def _validate_agent_structure(self, agent_data: Dict, agent_name: str):
        """エージェント定義構造の検証"""
        required_fields = ['role', 'display_name', 'description', 'expertise', 'instructions']
        
        for field in required_fields:
            if field not in agent_data:
                raise ValueError(f"Missing required field '{field}' in agent definition {agent_name}")
        
        # データ型の検証
        if not isinstance(agent_data['expertise'], list):
            raise ValueError(f"'expertise' must be a list in agent definition {agent_name}")
        
        if not isinstance(agent_data['instructions'], str):
            raise ValueError(f"'instructions' must be a string in agent definition {agent_name}")
        
        # オプショナルフィールドの型検証
        optional_list_fields = ['context_keywords']
        for field in optional_list_fields:
            if field in agent_data and not isinstance(agent_data[field], list):
                raise ValueError(f"'{field}' must be a list in agent definition {agent_name}")
        
        optional_dict_fields = ['specializations', 'output_guidelines', 'collaboration']
        for field in optional_dict_fields:
            if field in agent_data and not isinstance(agent_data[field], dict):
                raise ValueError(f"'{field}' must be a dict in agent definition {agent_name}")
        
        self.logger.debug(f"Agent definition structure validation passed for: {agent_name}")
    
    def load_all_agents(self) -> Dict[str, AgentDefinition]:
        """全エージェント定義を読み込み"""
        agent_names = self.discover_agents()
        agents = {}
        
        for agent_name in agent_names:
            try:
                agent = self.load_agent(agent_name)
                agents[agent_name] = agent
            except Exception as e:
                self.logger.error(f"Failed to load agent {agent_name}: {e}")
        
        return agents
    
    def get_agent_by_role(self, role: str) -> Optional[AgentDefinition]:
        """ロール名でエージェント定義を取得"""
        for agent in self.loaded_agents.values():
            if agent.role == role:
                return agent
        
        # まだ読み込まれていない場合は探索
        agent_names = self.discover_agents()
        for agent_name in agent_names:
            if agent_name not in self.loaded_agents:
                try:
                    agent = self.load_agent(agent_name)
                    if agent.role == role:
                        return agent
                except Exception:
                    continue
        
        return None
    
    def find_best_agent_for_task(self, task_prompt: str) -> Optional[AgentDefinition]:
        """タスクプロンプトに最適なエージェントを検索"""
        all_agents = self.load_all_agents()
        
        best_agent = None
        best_score = 0
        
        for agent in all_agents.values():
            score = agent.matches_context(task_prompt)
            if score > best_score:
                best_score = score
                best_agent = agent
        
        self.logger.info(f"Best agent for task: {best_agent.role if best_agent else 'None'} (score: {best_score})")
        return best_agent
    
    def get_available_roles(self) -> List[str]:
        """利用可能なエージェントロールのリスト"""
        all_agents = self.load_all_agents()
        return [agent.role for agent in all_agents.values()]
    
    def get_agents_summary(self) -> List[Dict[str, Any]]:
        """全エージェントのサマリー情報を取得"""
        all_agents = self.load_all_agents()
        summaries = []
        
        for agent_name, agent in all_agents.items():
            summary = {
                "name": agent_name,
                "role": agent.role,
                "display_name": agent.display_name,
                "description": agent.description,
                "expertise_count": len(agent.expertise),
                "expertise_summary": agent.get_expertise_summary(),
                "specializations_count": len(agent.specializations),
                "context_keywords_count": len(agent.context_keywords)
            }
            summaries.append(summary)
        
        return summaries
    
    def validate_agent_compatibility(self, template_agents: List[str]) -> Dict[str, Any]:
        """テンプレートで要求されるエージェントとの互換性チェック"""
        available_roles = self.get_available_roles()
        
        missing_agents = []
        available_agents = []
        
        for required_agent in template_agents:
            if required_agent in available_roles:
                available_agents.append(required_agent)
            else:
                missing_agents.append(required_agent)
        
        return {
            "compatible": len(missing_agents) == 0,
            "available_agents": available_agents,
            "missing_agents": missing_agents,
            "coverage_percentage": len(available_agents) / len(template_agents) * 100 if template_agents else 100
        }
    
    def create_custom_agent(self, role: str, display_name: str, description: str, 
                          expertise: List[str], instructions: str, **kwargs) -> AgentDefinition:
        """カスタムエージェント定義を動的作成"""
        agent = AgentDefinition(
            role=role,
            display_name=display_name,
            description=description,
            expertise=expertise,
            instructions=instructions,
            context_keywords=kwargs.get('context_keywords', []),
            specializations=kwargs.get('specializations', {}),
            output_guidelines=kwargs.get('output_guidelines', {}),
            collaboration=kwargs.get('collaboration', {})
        )
        
        # メモリキャッシュに保存
        self.loaded_agents[role] = agent
        
        self.logger.info(f"Created custom agent: {role}")
        return agent
    
    def export_agent_definition(self, agent_name: str, output_path: str):
        """エージェント定義をYAML形式でエクスポート"""
        agent = self.load_agent(agent_name)
        
        export_data = {
            "role": agent.role,
            "display_name": agent.display_name,
            "description": agent.description,
            "expertise": agent.expertise,
            "instructions": agent.instructions,
            "context_keywords": agent.context_keywords,
            "specializations": agent.specializations,
            "output_guidelines": agent.output_guidelines,
            "collaboration": agent.collaboration
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(export_data, f, default_flow_style=False, ensure_ascii=False, sort_keys=False)
        
        self.logger.info(f"Agent definition exported to: {output_path}")


class AgentRegistry:
    """エージェント定義の統合管理"""
    
    def __init__(self, agents_dir: str = "./agents"):
        self.agent_loader = AgentLoader(agents_dir)
        self.logger = logging.getLogger(__name__)
    
    def get_instructions_for_role(self, role: str) -> str:
        """ロール用の指示を取得（config.pyのROLE_INSTRUCTIONSの代替）"""
        agent = self.agent_loader.get_agent_by_role(role)
        if agent:
            return agent.instructions
        
        # フォールバック: 基本的な指示
        self.logger.warning(f"No agent definition found for role: {role}")
        return f"""
あなたは{role}として行動してください。
明確で実用的な成果物を作成し、必要に応じてファイルを作成してください。
"""
    
    def build_prompt_for_role(self, role: str, base_prompt: str, context: str, working_dir: str) -> str:
        """ロール用の完全なプロンプトを構築"""
        agent = self.agent_loader.get_agent_by_role(role)
        if agent:
            return agent.build_prompt(base_prompt, context, working_dir)
        
        # フォールバック
        return f"""
{self.get_instructions_for_role(role)}

=== 作業コンテキスト ===
{context}

=== 指示 ===
{base_prompt}

作業ディレクトリ: {working_dir}
現在のロール: {role}

出力は明確で実用的なものにし、必要に応じてファイルを作成してください。
"""
