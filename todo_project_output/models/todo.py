"""
Todoモデル定義
データベース操作とビジネスロジックを管理
"""

from datetime import datetime, date
from typing import List, Optional, Dict, Any
from database import db_manager


class Category:
    """カテゴリモデル"""
    
    def __init__(self, id: int = None, name: str = None, color: str = '#6c757d', 
                 description: str = None, created_at: datetime = None, 
                 updated_at: datetime = None):
        self.id = id
        self.name = name
        self.color = color
        self.description = description
        self.created_at = created_at
        self.updated_at = updated_at
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Category':
        """辞書からCategoryインスタンスを作成"""
        return cls(
            id=data.get('id'),
            name=data.get('name'),
            color=data.get('color', '#6c757d'),
            description=data.get('description'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            'id': self.id,
            'name': self.name,
            'color': self.color,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def save(self) -> int:
        """カテゴリを保存"""
        if self.id:
            # 更新
            query = '''
                UPDATE categories 
                SET name = ?, color = ?, description = ?
                WHERE id = ?
            '''
            db_manager.execute_update(query, (self.name, self.color, self.description, self.id))
            return self.id
        else:
            # 新規作成
            query = '''
                INSERT INTO categories (name, color, description)
                VALUES (?, ?, ?)
            '''
            self.id = db_manager.execute_update(query, (self.name, self.color, self.description))
            return self.id
    
    def delete(self) -> bool:
        """カテゴリを削除"""
        if self.id:
            query = 'DELETE FROM categories WHERE id = ?'
            result = db_manager.execute_update(query, (self.id,))
            return result > 0
        return False
    
    @staticmethod
    def get_all() -> List['Category']:
        """全カテゴリを取得"""
        query = '''
            SELECT id, name, color, description, created_at, updated_at
            FROM categories
            ORDER BY name
        '''
        rows = db_manager.execute_query(query)
        return [Category.from_dict(dict(row)) for row in rows]
    
    @staticmethod
    def get_by_id(category_id: int) -> Optional['Category']:
        """IDでカテゴリを取得"""
        query = '''
            SELECT id, name, color, description, created_at, updated_at
            FROM categories
            WHERE id = ?
        '''
        rows = db_manager.execute_query(query, (category_id,))
        return Category.from_dict(dict(rows[0])) if rows else None


class Todo:
    """Todoモデル"""
    
    def __init__(self, id: int = None, title: str = None, description: str = None,
                 category_id: int = None, priority: str = 'medium', status: str = 'pending',
                 due_date: date = None, completed_at: datetime = None,
                 created_at: datetime = None, updated_at: datetime = None,
                 display_order: int = 0):
        self.id = id
        self.title = title
        self.description = description
        self.category_id = category_id
        self.priority = priority
        self.status = status
        self.due_date = due_date
        self.completed_at = completed_at
        self.created_at = created_at
        self.updated_at = updated_at
        self.display_order = display_order
        self._category = None
    
    @property
    def category(self) -> Optional[Category]:
        """関連するカテゴリを取得"""
        if self._category is None and self.category_id:
            self._category = Category.get_by_id(self.category_id)
        return self._category
    
    @property
    def is_overdue(self) -> bool:
        """期限切れかどうか"""
        if self.due_date and self.status != 'completed':
            return self.due_date < date.today()
        return False
    
    @property
    def is_due_today(self) -> bool:
        """今日が期限かどうか"""
        if self.due_date and self.status != 'completed':
            return self.due_date == date.today()
        return False
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Todo':
        """辞書からTodoインスタンスを作成"""
        due_date = None
        if data.get('due_date'):
            if isinstance(data['due_date'], str):
                due_date = datetime.strptime(data['due_date'], '%Y-%m-%d').date()
            else:
                due_date = data['due_date']
        
        completed_at = None
        if data.get('completed_at'):
            if isinstance(data['completed_at'], str):
                completed_at = datetime.fromisoformat(data['completed_at'])
            else:
                completed_at = data['completed_at']
        
        return cls(
            id=data.get('id'),
            title=data.get('title'),
            description=data.get('description'),
            category_id=data.get('category_id'),
            priority=data.get('priority', 'medium'),
            status=data.get('status', 'pending'),
            due_date=due_date,
            completed_at=completed_at,
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at'),
            display_order=data.get('display_order', 0)
        )
    
    def to_dict(self, include_category: bool = False) -> Dict[str, Any]:
        """辞書形式に変換"""
        result = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'category_id': self.category_id,
            'priority': self.priority,
            'status': self.status,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'display_order': self.display_order,
            'is_overdue': self.is_overdue,
            'is_due_today': self.is_due_today
        }
        
        if include_category and self.category:
            result['category'] = self.category.to_dict()
        
        return result
    
    def save(self) -> int:
        """Todoを保存"""
        if self.id:
            # 更新
            query = '''
                UPDATE todos 
                SET title = ?, description = ?, category_id = ?, priority = ?, 
                    status = ?, due_date = ?, display_order = ?
                WHERE id = ?
            '''
            db_manager.execute_update(query, (
                self.title, self.description, self.category_id, self.priority,
                self.status, self.due_date, self.display_order, self.id
            ))
            return self.id
        else:
            # 新規作成
            query = '''
                INSERT INTO todos (title, description, category_id, priority, status, due_date, display_order)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            '''
            self.id = db_manager.execute_update(query, (
                self.title, self.description, self.category_id, self.priority,
                self.status, self.due_date, self.display_order
            ))
            return self.id
    
    def delete(self) -> bool:
        """Todoを削除"""
        if self.id:
            query = 'DELETE FROM todos WHERE id = ?'
            result = db_manager.execute_update(query, (self.id,))
            return result > 0
        return False
    
    def mark_completed(self) -> bool:
        """完了状態にマーク"""
        self.status = 'completed'
        self.completed_at = datetime.now()
        return self.save() > 0
    
    def mark_pending(self) -> bool:
        """未完了状態にマーク"""
        self.status = 'pending'
        self.completed_at = None
        return self.save() > 0
    
    @staticmethod
    def get_all(status: str = None, category_id: int = None, priority: str = None) -> List['Todo']:
        """Todo一覧を取得"""
        query = '''
            SELECT t.*, c.name as category_name, c.color as category_color
            FROM todos t
            LEFT JOIN categories c ON t.category_id = c.id
            WHERE 1=1
        '''
        params = []
        
        if status:
            query += ' AND t.status = ?'
            params.append(status)
        
        if category_id:
            query += ' AND t.category_id = ?'
            params.append(category_id)
        
        if priority:
            query += ' AND t.priority = ?'
            params.append(priority)
        
        query += ' ORDER BY t.display_order, t.created_at DESC'
        
        rows = db_manager.execute_query(query, tuple(params))
        todos = []
        for row in rows:
            todo = Todo.from_dict(dict(row))
            if row['category_name']:
                todo._category = Category(
                    id=row['category_id'],
                    name=row['category_name'],
                    color=row['category_color']
                )
            todos.append(todo)
        
        return todos
    
    @staticmethod
    def get_by_id(todo_id: int) -> Optional['Todo']:
        """IDでTodoを取得"""
        query = '''
            SELECT t.*, c.name as category_name, c.color as category_color
            FROM todos t
            LEFT JOIN categories c ON t.category_id = c.id
            WHERE t.id = ?
        '''
        rows = db_manager.execute_query(query, (todo_id,))
        if rows:
            row = rows[0]
            todo = Todo.from_dict(dict(row))
            if row['category_name']:
                todo._category = Category(
                    id=row['category_id'],
                    name=row['category_name'],
                    color=row['category_color']
                )
            return todo
        return None
    
    @staticmethod
    def get_statistics() -> Dict[str, Any]:
        """統計情報を取得"""
        query = '''
            SELECT 
                COUNT(*) as total_tasks,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_tasks,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_tasks,
                COUNT(CASE WHEN status = 'in_progress' THEN 1 END) as in_progress_tasks,
                COUNT(CASE WHEN due_date IS NOT NULL AND due_date < DATE('now') AND status != 'completed' THEN 1 END) as overdue_tasks,
                COUNT(CASE WHEN priority = 'high' AND status != 'completed' THEN 1 END) as high_priority_tasks
            FROM todos
        '''
        rows = db_manager.execute_query(query)
        if rows:
            stats = dict(rows[0])
            stats['completion_rate'] = (
                (stats['completed_tasks'] / stats['total_tasks'] * 100) 
                if stats['total_tasks'] > 0 else 0
            )
            return stats
        return {}