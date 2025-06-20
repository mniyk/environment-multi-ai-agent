"""
Flask ToDo アプリケーション メインファイル
アプリケーションの初期化、設定、ルーティングを管理
"""

import logging
import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from werkzeug.exceptions import HTTPException
from config import get_config
from database import init_database
from models import Todo, Category


def create_app(config_name: str = None) -> Flask:
    """Flaskアプリケーションファクトリー"""
    app = Flask(__name__)
    
    # 設定読み込み
    config = get_config(config_name)
    app.config.from_object(config)
    
    # ログ設定
    setup_logging(app)
    
    # データベース初期化
    init_database(app.config['DATABASE_PATH'])
    
    # ルート登録
    register_routes(app)
    
    # エラーハンドラー登録
    register_error_handlers(app)
    
    # テンプレートフィルター登録
    register_template_filters(app)
    
    return app


def setup_logging(app: Flask):
    """ログ設定"""
    if not app.debug:
        logging.basicConfig(
            level=getattr(logging, app.config['LOG_LEVEL']),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(app.config['LOG_FILE']),
                logging.StreamHandler()
            ]
        )


def register_routes(app: Flask):
    """ルート登録"""
    
    @app.route('/')
    def index():
        """メインページ"""
        try:
            todos = Todo.get_all()
            categories = Category.get_all()
            stats = Todo.get_statistics()
            
            return render_template('index.html', 
                                 todos=todos, 
                                 categories=categories, 
                                 stats=stats)
        except Exception as e:
            app.logger.error(f"Error in index route: {str(e)}")
            flash('データの取得中にエラーが発生しました', 'error')
            return render_template('index.html', todos=[], categories=[], stats={})
    
    @app.route('/todos')
    def todos():
        """Todo一覧ページ"""
        try:
            # フィルタリングパラメータ
            status = request.args.get('status')
            category_id = request.args.get('category_id', type=int)
            priority = request.args.get('priority')
            
            todos = Todo.get_all(status=status, category_id=category_id, priority=priority)
            categories = Category.get_all()
            
            return render_template('todo_list.html', 
                                 todos=todos, 
                                 categories=categories,
                                 current_status=status,
                                 current_category=category_id,
                                 current_priority=priority)
        except Exception as e:
            app.logger.error(f"Error in todos route: {str(e)}")
            flash('Todo一覧の取得中にエラーが発生しました', 'error')
            return render_template('todo_list.html', todos=[], categories=[])
    
    # API Routes
    @app.route('/api/todos', methods=['GET'])
    def api_get_todos():
        """Todo一覧取得API"""
        try:
            status = request.args.get('status')
            category_id = request.args.get('category_id', type=int)
            priority = request.args.get('priority')
            
            todos = Todo.get_all(status=status, category_id=category_id, priority=priority)
            
            return jsonify({
                'success': True,
                'data': [todo.to_dict(include_category=True) for todo in todos],
                'count': len(todos)
            })
        except Exception as e:
            app.logger.error(f"Error in API get todos: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/todos', methods=['POST'])
    def api_create_todo():
        """Todo作成API"""
        try:
            data = request.get_json()
            
            # バリデーション
            if not data or not data.get('title'):
                return jsonify({'success': False, 'error': 'タイトルは必須です'}), 400
            
            # Todo作成
            todo = Todo(
                title=data['title'],
                description=data.get('description', ''),
                category_id=data.get('category_id'),
                priority=data.get('priority', 'medium'),
                status=data.get('status', 'pending'),
                due_date=data.get('due_date')
            )
            
            todo_id = todo.save()
            todo = Todo.get_by_id(todo_id)
            
            return jsonify({
                'success': True,
                'data': todo.to_dict(include_category=True),
                'message': 'Todoが作成されました'
            }), 201
            
        except Exception as e:
            app.logger.error(f"Error in API create todo: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/todos/<int:todo_id>', methods=['GET'])
    def api_get_todo(todo_id: int):
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
            app.logger.error(f"Error in API get todo: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/todos/<int:todo_id>', methods=['PUT'])
    def api_update_todo(todo_id: int):
        """Todo更新API"""
        try:
            todo = Todo.get_by_id(todo_id)
            if not todo:
                return jsonify({'success': False, 'error': 'Todoが見つかりません'}), 404
            
            data = request.get_json()
            
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
                todo.due_date = data['due_date']
            
            todo.save()
            
            return jsonify({
                'success': True,
                'data': todo.to_dict(include_category=True),
                'message': 'Todoが更新されました'
            })
            
        except Exception as e:
            app.logger.error(f"Error in API update todo: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/todos/<int:todo_id>', methods=['DELETE'])
    def api_delete_todo(todo_id: int):
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
            app.logger.error(f"Error in API delete todo: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/todos/<int:todo_id>/toggle', methods=['POST'])
    def api_toggle_todo(todo_id: int):
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
            app.logger.error(f"Error in API toggle todo: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/categories', methods=['GET'])
    def api_get_categories():
        """カテゴリ一覧取得API"""
        try:
            categories = Category.get_all()
            return jsonify({
                'success': True,
                'data': [category.to_dict() for category in categories]
            })
        except Exception as e:
            app.logger.error(f"Error in API get categories: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/statistics', methods=['GET'])
    def api_get_statistics():
        """統計情報取得API"""
        try:
            stats = Todo.get_statistics()
            return jsonify({
                'success': True,
                'data': stats
            })
        except Exception as e:
            app.logger.error(f"Error in API get statistics: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500


def register_error_handlers(app: Flask):
    """エラーハンドラー登録"""
    
    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'リソースが見つかりません'}), 404
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'サーバーエラーが発生しました'}), 500
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(Exception)
    def handle_exception(e):
        if isinstance(e, HTTPException):
            return e
        
        app.logger.error(f"Unhandled exception: {str(e)}")
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'サーバーエラーが発生しました'}), 500
        return render_template('errors/500.html'), 500


def register_template_filters(app: Flask):
    """テンプレートフィルター登録"""
    
    @app.template_filter('priority_label')
    def priority_label(priority):
        """優先度ラベル"""
        labels = {
            'low': '低',
            'medium': '中',
            'high': '高'
        }
        return labels.get(priority, priority)
    
    @app.template_filter('status_label')
    def status_label(status):
        """ステータスラベル"""
        labels = {
            'pending': '未完了',
            'in_progress': '進行中',
            'completed': '完了'
        }
        return labels.get(status, status)
    
    @app.template_filter('priority_class')
    def priority_class(priority):
        """優先度CSSクラス"""
        classes = {
            'low': 'text-success',
            'medium': 'text-warning',
            'high': 'text-danger'
        }
        return classes.get(priority, '')


if __name__ == '__main__':
    # アプリケーション作成
    app = create_app()
    
    # 開発サーバー起動
    app.run(
        host=app.config['HOST'],
        port=app.config['PORT'],
        debug=app.config['DEBUG']
    )