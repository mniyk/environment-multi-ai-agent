-- ToDoアプリケーション データベース設計
-- SQLite用スキーマ定義

-- ======================
-- テーブル設計
-- ======================

-- タスクカテゴリテーブル
CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(50) NOT NULL UNIQUE,
    color VARCHAR(7) DEFAULT '#6c757d', -- Bootstrapカラーコード
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Todosメインテーブル
CREATE TABLE todos (
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
    
    -- 外部キー制約
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
);

-- ======================
-- インデックス設計
-- ======================

-- 検索・ソートパフォーマンス向上
CREATE INDEX idx_todos_status ON todos(status);
CREATE INDEX idx_todos_priority ON todos(priority);
CREATE INDEX idx_todos_due_date ON todos(due_date);
CREATE INDEX idx_todos_category ON todos(category_id);
CREATE INDEX idx_todos_display_order ON todos(display_order);
CREATE INDEX idx_todos_created_at ON todos(created_at);

-- 複合インデックス（よく使われる組み合わせ）
CREATE INDEX idx_todos_status_priority ON todos(status, priority);
CREATE INDEX idx_todos_category_status ON todos(category_id, status);
CREATE INDEX idx_todos_due_date_status ON todos(due_date, status);

-- ======================
-- トリガー設計
-- ======================

-- updated_at自動更新トリガー
CREATE TRIGGER update_todos_timestamp 
    AFTER UPDATE ON todos
    FOR EACH ROW
    WHEN OLD.updated_at = NEW.updated_at OR NEW.updated_at IS NULL
BEGIN
    UPDATE todos SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- カテゴリのupdated_at自動更新トリガー
CREATE TRIGGER update_categories_timestamp 
    AFTER UPDATE ON categories
    FOR EACH ROW
    WHEN OLD.updated_at = NEW.updated_at OR NEW.updated_at IS NULL
BEGIN
    UPDATE categories SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- 完了時のcompleted_at自動設定トリガー
CREATE TRIGGER set_completed_at 
    AFTER UPDATE ON todos
    FOR EACH ROW
    WHEN NEW.status = 'completed' AND OLD.status != 'completed'
BEGIN
    UPDATE todos SET completed_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- 未完了時のcompleted_atクリアトリガー
CREATE TRIGGER clear_completed_at 
    AFTER UPDATE ON todos
    FOR EACH ROW
    WHEN NEW.status != 'completed' AND OLD.status = 'completed'
BEGIN
    UPDATE todos SET completed_at = NULL WHERE id = NEW.id;
END;

-- ======================
-- 初期データ投入
-- ======================

-- デフォルトカテゴリの作成
INSERT INTO categories (name, color, description) VALUES 
    ('個人', '#007bff', '個人的なタスク'),
    ('仕事', '#28a745', '業務関連のタスク'),
    ('学習', '#ffc107', '学習・勉強関連'),
    ('買い物', '#17a2b8', '購入・買い物リスト'),
    ('健康', '#dc3545', '健康・運動関連');

-- サンプルタスクの作成（開発・テスト用）
INSERT INTO todos (title, description, category_id, priority, due_date) VALUES 
    ('プロジェクト企画書作成', 'Q4のプロジェクト企画書を作成する', 2, 'high', '2024-07-15'),
    ('SQLiteチュートリアル', 'データベース操作の基本を学習', 3, 'medium', '2024-07-10'),
    ('牛乳・パン・卵を購入', '冷蔵庫の在庫補充', 4, 'low', '2024-06-22'),
    ('ランニング30分', '健康維持のための運動', 5, 'medium', '2024-06-21'),
    ('ToDoアプリのUI設計', 'ワイヤーフレームとモックアップ作成', 2, 'high', '2024-06-23');

-- ======================
-- ビュー定義
-- ======================

-- タスク詳細ビュー（カテゴリ情報付き）
CREATE VIEW todo_details AS
SELECT 
    t.id,
    t.title,
    t.description,
    t.priority,
    t.status,
    t.due_date,
    t.completed_at,
    t.created_at,
    t.updated_at,
    t.display_order,
    c.name as category_name,
    c.color as category_color,
    -- 期限切れフラグ
    CASE 
        WHEN t.due_date IS NOT NULL AND t.due_date < DATE('now') AND t.status != 'completed' 
        THEN 1 ELSE 0 
    END as is_overdue,
    -- 今日期限フラグ
    CASE 
        WHEN t.due_date = DATE('now') AND t.status != 'completed' 
        THEN 1 ELSE 0 
    END as is_due_today
FROM todos t
LEFT JOIN categories c ON t.category_id = c.id;

-- 統計情報ビュー
CREATE VIEW todo_statistics AS
SELECT 
    COUNT(*) as total_tasks,
    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_tasks,
    COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_tasks,
    COUNT(CASE WHEN status = 'in_progress' THEN 1 END) as in_progress_tasks,
    COUNT(CASE WHEN due_date IS NOT NULL AND due_date < DATE('now') AND status != 'completed' THEN 1 END) as overdue_tasks,
    COUNT(CASE WHEN priority = 'high' AND status != 'completed' THEN 1 END) as high_priority_tasks,
    ROUND(
        CASE 
            WHEN COUNT(*) > 0 
            THEN (COUNT(CASE WHEN status = 'completed' THEN 1 END) * 100.0 / COUNT(*))
            ELSE 0 
        END, 1
    ) as completion_rate
FROM todos;

-- ======================
-- データ整合性チェック用クエリ
-- ======================

-- 孤立したカテゴリIDをチェック
-- SELECT * FROM todos WHERE category_id NOT IN (SELECT id FROM categories) AND category_id IS NOT NULL;

-- 重複するカテゴリ名をチェック  
-- SELECT name, COUNT(*) FROM categories GROUP BY name HAVING COUNT(*) > 1;

-- 無効な優先度・ステータスをチェック
-- SELECT * FROM todos WHERE priority NOT IN ('low', 'medium', 'high');
-- SELECT * FROM todos WHERE status NOT IN ('pending', 'in_progress', 'completed');

-- ======================
-- パフォーマンス最適化のためのクエリ例
-- ======================

-- よく使用されるクエリのパフォーマンステスト用
-- EXPLAIN QUERY PLAN SELECT * FROM todo_details WHERE status = 'pending' ORDER BY priority DESC, due_date ASC;
-- EXPLAIN QUERY PLAN SELECT * FROM todo_details WHERE category_name = '仕事' AND is_overdue = 1;

-- ======================
-- 備考
-- ======================
-- 1. SQLiteの制約: FOREIGN KEYは有効化が必要 (PRAGMA foreign_keys = ON;)
-- 2. 日付形式: ISO8601形式 (YYYY-MM-DD) を推奨
-- 3. カラー形式: Hex形式 (#RRGGBB) でBootstrapカラーを想定
-- 4. 文字エンコーディング: UTF-8
-- 5. タイムゾーン: ローカルタイム（個人利用想定）