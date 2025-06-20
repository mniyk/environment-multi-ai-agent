#!/usr/bin/env python3
"""
Claude Conversation Replayer
Claudeとの会話ログを再現・表示するモジュール
"""

import json
import os
import glob
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import argparse


class ConversationReplayer:
    """Claude会話ログの再現・表示クラス"""
    
    def __init__(self, project_dir: str):
        """
        初期化
        
        Args:
            project_dir: プロジェクトディレクトリのパス
        """
        self.project_dir = Path(project_dir)
        self.logs_dir = self.project_dir / "logs"
    
    def find_latest_session_log(self) -> Optional[Path]:
        """
        最新のセッションのclaude_conversations.jsonlファイルを検索
        
        Returns:
            最新のログファイルのパス、見つからない場合はNone
        """
        if not self.logs_dir.exists():
            print(f"❌ ログディレクトリが見つかりません: {self.logs_dir}")
            return None
        
        # session_*パターンのディレクトリを検索
        session_pattern = str(self.logs_dir / "session_*")
        session_dirs = glob.glob(session_pattern)
        
        if not session_dirs:
            print(f"❌ セッションディレクトリが見つかりません: {session_pattern}")
            return None
        
        # 最新のセッションディレクトリを取得（名前順でソート）
        latest_session_dir = Path(max(session_dirs))
        
        # claude_conversations.jsonlファイルのパス
        conversation_log_file = latest_session_dir / "claude_conversations.jsonl"
        
        if not conversation_log_file.exists():
            print(f"❌ 会話ログファイルが見つかりません: {conversation_log_file}")
            return None
        
        return conversation_log_file
    
    def load_conversations(self, log_file: Path) -> List[Dict]:
        """
        会話ログをJSONLファイルから読み込み
        
        Args:
            log_file: ログファイルのパス
            
        Returns:
            会話データのリスト
        """
        conversations = []
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            conversations.append(data)
                        except json.JSONDecodeError as e:
                            print(f"⚠️  行 {line_num} のJSONパースエラー: {e}")
                            continue
        except Exception as e:
            print(f"❌ ファイル読み込みエラー: {e}")
            return []
        
        return conversations
    
    def format_conversation(self, conversation: Dict, conversation_num: int) -> str:
        """
        会話データを整形して表示用文字列に変換
        
        Args:
            conversation: 会話データ
            conversation_num: 会話番号
            
        Returns:
            整形された会話文字列
        """
        output = []
        
        # ヘッダー
        output.append("=" * 80)
        output.append(f"🎭 会話 {conversation_num}")
        output.append("=" * 80)
        
        # 基本情報
        timestamp = conversation.get('timestamp', 'N/A')
        agent_role = conversation.get('agent_role', 'N/A')
        task_id = conversation.get('task_id', 'N/A')
        prompt_length = conversation.get('prompt_length', 0)
        response_length = conversation.get('response_length', 0)
        
        output.append(f"🕒 タイムスタンプ: {timestamp}")
        output.append(f"👤 エージェント: {agent_role}")
        output.append(f"📋 タスクID: {task_id}")
        output.append(f"📏 プロンプト長: {prompt_length:,} 文字")
        output.append(f"📏 レスポンス長: {response_length:,} 文字")
        output.append("")
        
        # プロンプト表示
        output.append("📝 プロンプト:")
        output.append("-" * 40)
        prompt = conversation.get('prompt', 'N/A')
        if len(prompt) > 1000:
            output.append(prompt[:1000] + f"\n... (残り {len(prompt) - 1000:,} 文字)")
        else:
            output.append(prompt)
        output.append("")
        
        # Claude レスポンス解析
        claude_response_raw = conversation.get('claude_response', {})
        stdout_raw = claude_response_raw.get('stdout', '')
        stderr = claude_response_raw.get('stderr', '')
        return_code = claude_response_raw.get('return_code', -1)
        
        output.append("💬 Claude Code レスポンス:")
        output.append("-" * 40)
        
        if stdout_raw:
            try:
                claude_response = json.loads(stdout_raw)
                
                # メタデータ表示
                output.append(f"🔄 実行結果タイプ: {claude_response.get('type', 'N/A')}")
                output.append(f"✅ 成功/失敗: {claude_response.get('subtype', 'N/A')}")
                output.append(f"⏱️  実行時間: {claude_response.get('duration_ms', 0) / 1000:.1f}秒")
                output.append(f"🔄 ターン数: {claude_response.get('num_turns', 'N/A')}")
                output.append(f"💰 コスト: ${claude_response.get('total_cost_usd', 0):.4f}")
                
                if claude_response.get('usage'):
                    usage = claude_response['usage']
                    output.append(f"📊 使用量:")
                    output.append(f"   - 入力トークン: {usage.get('input_tokens', 0):,}")
                    output.append(f"   - 出力トークン: {usage.get('output_tokens', 0):,}")
                    if usage.get('cache_read_input_tokens'):
                        output.append(f"   - キャッシュ読み込み: {usage.get('cache_read_input_tokens', 0):,}")
                
                output.append("")
                
                # 実行結果表示
                result = claude_response.get('result', 'N/A')
                output.append("📋 実行結果:")
                if len(result) > 800:
                    output.append(result[:800] + f"\n... (残り {len(result) - 800:,} 文字)")
                else:
                    output.append(result)
                    
            except json.JSONDecodeError:
                output.append(f"⚠️  レスポンスJSONパースエラー")
                output.append(f"Raw stdout: {stdout_raw[:200]}...")
        else:
            output.append("❌ レスポンスデータなし")
        
        if stderr:
            output.append(f"\n⚠️  stderr: {stderr}")
        
        output.append(f"\n🔧 リターンコード: {return_code}")
        output.append("")
        
        return "\n".join(output)
    
    def replay_conversations(self, limit: Optional[int] = None, conversation_id: Optional[int] = None):
        """
        会話ログを再現表示
        
        Args:
            limit: 表示する会話数の制限
            conversation_id: 特定の会話IDのみ表示
        """
        # 最新のログファイルを検索
        log_file = self.find_latest_session_log()
        if not log_file:
            return
        
        print(f"📁 ログファイル: {log_file}")
        print(f"📅 セッション: {log_file.parent.name}")
        print()
        
        # 会話データを読み込み
        conversations = self.load_conversations(log_file)
        
        if not conversations:
            print("❌ 会話データが見つかりませんでした")
            return
        
        print(f"📊 総会話数: {len(conversations)}件")
        print()
        
        # 表示対象の決定
        if conversation_id is not None:
            if 1 <= conversation_id <= len(conversations):
                conversations_to_show = [conversations[conversation_id - 1]]
                start_num = conversation_id
            else:
                print(f"❌ 会話ID {conversation_id} は範囲外です (1-{len(conversations)})")
                return
        else:
            conversations_to_show = conversations[:limit] if limit else conversations
            start_num = 1
        
        # 会話を表示
        for i, conversation in enumerate(conversations_to_show):
            conversation_num = start_num + i
            formatted_conversation = self.format_conversation(conversation, conversation_num)
            print(formatted_conversation)
            
            # 複数会話表示時は区切りを入れる
            if len(conversations_to_show) > 1 and i < len(conversations_to_show) - 1:
                input("\n⏸️  続行するには Enter を押してください...")
                print()
    
    def list_available_sessions(self):
        """利用可能なセッション一覧を表示"""
        if not self.logs_dir.exists():
            print(f"❌ ログディレクトリが見つかりません: {self.logs_dir}")
            return
        
        session_pattern = str(self.logs_dir / "session_*")
        session_dirs = glob.glob(session_pattern)
        
        if not session_dirs:
            print("❌ セッションディレクトリが見つかりません")
            return
        
        print("📋 利用可能なセッション:")
        print("-" * 50)
        
        for session_dir in sorted(session_dirs, reverse=True):
            session_path = Path(session_dir)
            session_name = session_path.name
            
            # 会話ログファイルの存在確認
            conversation_log = session_path / "claude_conversations.jsonl"
            if conversation_log.exists():
                try:
                    with open(conversation_log, 'r') as f:
                        conversation_count = sum(1 for line in f if line.strip())
                    status = f"✅ {conversation_count}件の会話"
                except:
                    status = "⚠️  読み込みエラー"
            else:
                status = "❌ 会話ログなし"
            
            # タイムスタンプ解析
            try:
                # session_20250618_060224 形式からタイムスタンプを抽出
                timestamp_str = session_name.replace('session_', '')
                timestamp = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                readable_time = timestamp.strftime('%Y-%m-%d %H:%M:%S')
            except:
                readable_time = "タイムスタンプ不明"
            
            print(f"  {session_name}")
            print(f"    🕒 {readable_time}")
            print(f"    📊 {status}")
            print()


def main():
    """メイン関数（スタンドアロン実行用）"""
    parser = argparse.ArgumentParser(
        description="Claude会話ログ再現ツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python conversation_replayer.py ./todo_project_output              # 最新セッションの全会話を表示
  python conversation_replayer.py ./todo_project_output --limit 3   # 最新3件の会話を表示
  python conversation_replayer.py ./todo_project_output --id 2      # 2番目の会話のみ表示
  python conversation_replayer.py ./todo_project_output --list      # セッション一覧表示
        """
    )
    
    parser.add_argument(
        "project_dir",
        help="プロジェクトディレクトリのパス"
    )
    
    parser.add_argument(
        "--limit", "-l",
        type=int,
        help="表示する会話数の制限"
    )
    
    parser.add_argument(
        "--id", "-i",
        type=int,
        help="特定の会話IDのみ表示"
    )
    
    parser.add_argument(
        "--list",
        action="store_true",
        help="利用可能なセッション一覧を表示"
    )
    
    args = parser.parse_args()
    
    replayer = ConversationReplayer(args.project_dir)
    
    if args.list:
        replayer.list_available_sessions()
    else:
        replayer.replay_conversations(limit=args.limit, conversation_id=args.id)


if __name__ == "__main__":
    main()