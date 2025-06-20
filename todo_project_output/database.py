"""
データベース接続とセットアップ用モジュール
SQLiteデータベースの初期化、接続管理を行う
"""

import sqlite3
import os
from contextlib import contextmanager
from typing import Optional


class DatabaseManager:
    """データベース管理クラス"""
    
    def __init__(self, db_path: str = 'todo_app.db'):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """データベースの初期化"""
        if not os.path.exists(self.db_path):
            self._create_tables()
    
    def _create_tables(self):
        """テーブル作成とサンプルデータ投入"""
        with self.get_connection() as conn:
            # スキーマファイルを読み込んで実行
            schema_path = os.path.join(os.path.dirname(__file__), 'database_schema.sql')
            if os.path.exists(schema_path):
                with open(schema_path, 'r', encoding='utf-8') as f:
                    schema_sql = f.read()
                conn.executescript(schema_sql)
            else:
                # スキーマファイルがない場合のフォールバック
                self._create_tables_fallback(conn)
    
    def _create_tables_fallback(self, conn: sqlite3.Connection):
        """スキーマファイルがない場合のテーブル作成"""
        conn.executescript('''
            -- カテゴリテーブル
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(50) NOT NULL UNIQUE,
                color VARCHAR(7) DEFAULT '#6c757d',
                description TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            -- Todosテーブル
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title VARCHAR(200) NOT NULL,
                description TEXT,
                category_id INTEGER,
                priority VARCHAR(10) DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high')),
                status VARCHAR(15) DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed')),
                due_date DATE,
                completed_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                display_order INTEGER DEFAULT 0,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
            );

            -- インデックス
            CREATE INDEX IF NOT EXISTS idx_todos_status ON todos(status);
            CREATE INDEX IF NOT EXISTS idx_todos_priority ON todos(priority);
            CREATE INDEX IF NOT EXISTS idx_todos_due_date ON todos(due_date);
            CREATE INDEX IF NOT EXISTS idx_todos_category ON todos(category_id);

            -- トリガー
            CREATE TRIGGER IF NOT EXISTS update_todos_timestamp 
                AFTER UPDATE ON todos
                FOR EACH ROW
                WHEN OLD.updated_at = NEW.updated_at OR NEW.updated_at IS NULL
            BEGIN
                UPDATE todos SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END;

            CREATE TRIGGER IF NOT EXISTS set_completed_at 
                AFTER UPDATE ON todos
                FOR EACH ROW
                WHEN NEW.status = 'completed' AND OLD.status != 'completed'
            BEGIN
                UPDATE todos SET completed_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END;

            CREATE TRIGGER IF NOT EXISTS clear_completed_at 
                AFTER UPDATE ON todos
                FOR EACH ROW
                WHEN NEW.status != 'completed' AND OLD.status = 'completed'
            BEGIN
                UPDATE todos SET completed_at = NULL WHERE id = NEW.id;
            END;

            -- デフォルトカテゴリ
            INSERT OR IGNORE INTO categories (name, color, description) VALUES 
                ('個人', '#007bff', '個人的なタスク'),
                ('仕事', '#28a745', '業務関連のタスク'),
                ('学習', '#ffc107', '学習・勉強関連'),
                ('買い物', '#17a2b8', '購入・買い物リスト'),
                ('健康', '#dc3545', '健康・運動関連');
        ''')
    
    @contextmanager
    def get_connection(self):
        """データベース接続のコンテキストマネージャー"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 辞書形式でアクセス可能
        try:
            yield conn
        finally:
            conn.close()
    
    def execute_query(self, query: str, params: tuple = ()) -> list:
        """SELECT文実行"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()
    
    def execute_update(self, query: str, params: tuple = ()) -> int:
        """INSERT/UPDATE/DELETE文実行"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.lastrowid or cursor.rowcount


# グローバルデータベースマネージャーインスタンス
db_manager = DatabaseManager()


def get_db_connection():
    """データベース接続を取得"""
    return db_manager.get_connection()


def init_database(db_path: str = 'todo_app.db'):
    """データベースを初期化"""
    global db_manager
    db_manager = DatabaseManager(db_path)
    return db_manager