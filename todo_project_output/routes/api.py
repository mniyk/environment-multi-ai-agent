"""
API ルート定義
REST API エンドポイントを管理
"""

from flask import Blueprint, request, jsonify, current_app
from models import Todo, Category
from datetime import datetime

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/todos', methods=['GET'])
def get_todos():
    """Todo一覧取得API"""
    try:
        # クエリパラメータ取得
        status = request.args.get('status')
        category_id = request.args.get('category_id', type=int)
        priority = request.args.get('priority')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # バリデーション
        if per_page > 100:
            per_page = 100
        
        todos = Todo.get_all(status=status, category_id=category_id, priority=priority)
        
        # ページネーション（簡易実装）
        start = (page - 1) * per_page
        end = start + per_page
        paginated_todos = todos[start:end]
        
        return jsonify({
            'success': True,
            'data': [todo.to_dict(include_category=True) for todo in paginated_todos],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': len(todos),
                'pages': (len(todos) + per_page - 1) // per_page
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in get_todos API: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/todos', methods=['POST'])
def create_todo():
    """Todo作成API"""
    try:
        data = request.get_json()
        
        # バリデーション
        errors = validate_todo_data(data)
        if errors:
            return jsonify({'success': False, 'errors': errors}), 400
        
        # 日付変換
        due_date = None
        if data.get('due_date'):
            try:
                due_date = datetime.strptime(data['due_date'], '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'success': False, 'error': '日付形式が正しくありません（YYYY-MM-DD）'}), 400
        
        # Todo作成
        todo = Todo(
            title=data['title'],
            description=data.get('description', ''),
            category_id=data.get('category_id'),
            priority=data.get('priority', 'medium'),
            status=data.get('status', 'pending'),
            due_date=due_date,
            display_order=data.get('display_order', 0)
        )
        
        todo_id = todo.save()
        todo = Todo.get_by_id(todo_id)
        
        return jsonify({
            'success': True,
            'data': todo.to_dict(include_category=True),
            'message': 'Todoが作成されました'
        }), 201
        
    except Exception as e:
        current_app.logger.error(f"Error in create_todo API: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/todos/<int:todo_id>', methods=['GET'])
def get_todo(todo_id: int):
    """Todo詳細取得API"""
    try:
        todo = Todo.get_by_id(todo_id)
        if not todo:
            return jsonify({'success': False, 'error': 'Todoが見つかりません'}), 404
        
        return jsonify({
            'success': True,
            'data': todo.to_dict(include_category=True)
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in get_todo API: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/todos/<int:todo_id>', methods=['PUT'])
def update_todo(todo_id: int):
    """Todo更新API"""
    try:
        todo = Todo.get_by_id(todo_id)
        if not todo:
            return jsonify({'success': False, 'error': 'Todoが見つかりません'}), 404
        
        data = request.get_json()
        
        # バリデーション
        errors = validate_todo_data(data, is_update=True)
        if errors:
            return jsonify({'success': False, 'errors': errors}), 400
        
        # データ更新
        if 'title' in data:
            todo.title = data['title']
        if 'description' in data:
            todo.description = data['description']
        if 'category_id' in data:
            todo.category_id = data['category_id']
        if 'priority' in data:
            todo.priority = data['priority']
        if 'status' in data:
            todo.status = data['status']
        if 'due_date' in data:
            if data['due_date']:
                try:
                    todo.due_date = datetime.strptime(data['due_date'], '%Y-%m-%d').date()
                except ValueError:
                    return jsonify({'success': False, 'error': '日付形式が正しくありません（YYYY-MM-DD）'}), 400
            else:
                todo.due_date = None
        if 'display_order' in data:
            todo.display_order = data['display_order']
        
        todo.save()
        
        return jsonify({
            'success': True,
            'data': todo.to_dict(include_category=True),
            'message': 'Todoが更新されました'
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in update_todo API: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/todos/<int:todo_id>', methods=['DELETE'])
def delete_todo(todo_id: int):
    """Todo削除API"""
    try:
        todo = Todo.get_by_id(todo_id)
        if not todo:
            return jsonify({'success': False, 'error': 'Todoが見つかりません'}), 404
        
        todo.delete()
        
        return jsonify({
            'success': True,
            'message': 'Todoが削除されました'
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in delete_todo API: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/todos/<int:todo_id>/toggle', methods=['POST'])
def toggle_todo(todo_id: int):
    """Todo完了状態切り替えAPI"""
    try:
        todo = Todo.get_by_id(todo_id)
        if not todo:
            return jsonify({'success': False, 'error': 'Todoが見つかりません'}), 404
        
        if todo.status == 'completed':
            todo.mark_pending()
            message = 'Todoを未完了にしました'
        else:
            todo.mark_completed()
            message = 'Todoを完了にしました'
        
        return jsonify({
            'success': True,
            'data': todo.to_dict(include_category=True),
            'message': message
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in toggle_todo API: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/categories', methods=['GET'])
def get_categories():
    """カテゴリ一覧取得API"""
    try:
        categories = Category.get_all()
        return jsonify({
            'success': True,
            'data': [category.to_dict() for category in categories]
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in get_categories API: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/categories', methods=['POST'])
def create_category():
    """カテゴリ作成API"""
    try:
        data = request.get_json()
        
        # バリデーション
        if not data or not data.get('name'):
            return jsonify({'success': False, 'error': 'カテゴリ名は必須です'}), 400
        
        if len(data['name']) > 50:
            return jsonify({'success': False, 'error': 'カテゴリ名は50文字以内で入力してください'}), 400
        
        # カテゴリ作成
        category = Category(
            name=data['name'],
            color=data.get('color', '#6c757d'),
            description=data.get('description', '')
        )
        
        category_id = category.save()
        category = Category.get_by_id(category_id)
        
        return jsonify({
            'success': True,
            'data': category.to_dict(),
            'message': 'カテゴリが作成されました'
        }), 201
        
    except Exception as e:
        current_app.logger.error(f"Error in create_category API: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/statistics', methods=['GET'])
def get_statistics():
    """統計情報取得API"""
    try:
        stats = Todo.get_statistics()
        return jsonify({
            'success': True,
            'data': stats
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in get_statistics API: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/todos/bulk', methods=['POST'])
def bulk_update_todos():
    """Todo一括更新API"""
    try:
        data = request.get_json()
        
        if not data or 'todo_ids' not in data or 'action' not in data:
            return jsonify({'success': False, 'error': 'todo_idsとactionは必須です'}), 400
        
        todo_ids = data['todo_ids']
        action = data['action']
        
        if not isinstance(todo_ids, list) or not todo_ids:
            return jsonify({'success': False, 'error': 'todo_idsは空でないリストである必要があります'}), 400
        
        updated_todos = []
        
        for todo_id in todo_ids:
            todo = Todo.get_by_id(todo_id)
            if not todo:
                continue
            
            if action == 'complete':
                todo.mark_completed()
            elif action == 'pending':
                todo.mark_pending()
            elif action == 'delete':
                todo.delete()
                continue
            elif action == 'update_priority':
                priority = data.get('priority')
                if priority in ['low', 'medium', 'high']:
                    todo.priority = priority
                    todo.save()
            elif action == 'update_category':
                category_id = data.get('category_id')
                todo.category_id = category_id
                todo.save()
            
            updated_todos.append(todo.to_dict(include_category=True))
        
        return jsonify({
            'success': True,
            'data': updated_todos,
            'message': f'{len(updated_todos)}件のTodoを更新しました'
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in bulk_update_todos API: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


def validate_todo_data(data: dict, is_update: bool = False) -> list:
    """Todoデータバリデーション"""
    errors = []
    
    if not data:
        errors.append('データが必要です')
        return errors
    
    # タイトルバリデーション（新規作成時は必須）
    if not is_update and not data.get('title'):
        errors.append('タイトルは必須です')
    elif data.get('title') and len(data['title']) > 200:
        errors.append('タイトルは200文字以内で入力してください')
    
    # 優先度バリデーション
    if data.get('priority') and data['priority'] not in ['low', 'medium', 'high']:
        errors.append('優先度は low, medium, high のいずれかを指定してください')
    
    # ステータスバリデーション
    if data.get('status') and data['status'] not in ['pending', 'in_progress', 'completed']:
        errors.append('ステータスは pending, in_progress, completed のいずれかを指定してください')
    
    # カテゴリバリデーション
    if data.get('category_id'):
        category = Category.get_by_id(data['category_id'])
        if not category:
            errors.append('指定されたカテゴリが存在しません')
    
    return errors