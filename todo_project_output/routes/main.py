"""
メインページルート定義
Webページのルーティングを管理
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from models import Todo, Category
from datetime import datetime

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """メインページ"""
    try:
        # 最新のTodoを取得
        todos = Todo.get_all()
        categories = Category.get_all()
        stats = Todo.get_statistics()
        
        # 最近のTodo（上位10件）
        recent_todos = todos[:10]
        
        # 期限切れのTodo
        overdue_todos = [todo for todo in todos if todo.is_overdue]
        
        # 今日期限のTodo
        due_today_todos = [todo for todo in todos if todo.is_due_today]
        
        return render_template('index.html',
                             recent_todos=recent_todos,
                             overdue_todos=overdue_todos,
                             due_today_todos=due_today_todos,
                             categories=categories,
                             stats=stats)
                             
    except Exception as e:
        current_app.logger.error(f"Error in index route: {str(e)}")
        flash('データの取得中にエラーが発生しました', 'error')
        return render_template('index.html',
                             recent_todos=[],
                             overdue_todos=[],
                             due_today_todos=[],
                             categories=[],
                             stats={})


@main_bp.route('/todos')
def todos():
    """Todo一覧ページ"""
    try:
        # フィルタリングパラメータ
        status = request.args.get('status')
        category_id = request.args.get('category_id', type=int)
        priority = request.args.get('priority')
        search_query = request.args.get('q', '').strip()
        
        # 並び順パラメータ
        sort_by = request.args.get('sort', 'created_at')  # created_at, due_date, priority, title
        sort_order = request.args.get('order', 'desc')  # asc, desc
        
        # Todo取得
        todos = Todo.get_all(status=status, category_id=category_id, priority=priority)
        
        # 検索フィルタ
        if search_query:
            todos = [
                todo for todo in todos
                if search_query.lower() in todo.title.lower() or
                (todo.description and search_query.lower() in todo.description.lower())
            ]
        
        # ソート処理
        todos = sort_todos(todos, sort_by, sort_order)
        
        # カテゴリ一覧
        categories = Category.get_all()
        
        return render_template('todo_list.html',
                             todos=todos,
                             categories=categories,
                             current_status=status,
                             current_category=category_id,
                             current_priority=priority,
                             search_query=search_query,
                             sort_by=sort_by,
                             sort_order=sort_order)
                             
    except Exception as e:
        current_app.logger.error(f"Error in todos route: {str(e)}")
        flash('Todo一覧の取得中にエラーが発生しました', 'error')
        return render_template('todo_list.html',
                             todos=[],
                             categories=[],
                             current_status=status,
                             current_category=category_id,
                             current_priority=priority)


@main_bp.route('/todos/create', methods=['GET', 'POST'])
def create_todo():
    """Todo作成ページ"""
    if request.method == 'GET':
        try:
            categories = Category.get_all()
            return render_template('todo_form.html',
                                 categories=categories,
                                 todo=None,
                                 action='create')
        except Exception as e:
            current_app.logger.error(f"Error in create_todo GET: {str(e)}")
            flash('ページの読み込み中にエラーが発生しました', 'error')
            return redirect(url_for('main.todos'))
    
    # POST処理
    try:
        # フォームデータ取得
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category_id = request.form.get('category_id', type=int)
        priority = request.form.get('priority', 'medium')
        due_date_str = request.form.get('due_date', '').strip()
        
        # バリデーション
        errors = []
        if not title:
            errors.append('タイトルは必須です')
        if len(title) > 200:
            errors.append('タイトルは200文字以内で入力してください')
        if priority not in ['low', 'medium', 'high']:
            errors.append('無効な優先度が指定されました')
        
        # 日付変換
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            except ValueError:
                errors.append('日付形式が正しくありません')
        
        # カテゴリ存在チェック
        if category_id:
            category = Category.get_by_id(category_id)
            if not category:
                errors.append('指定されたカテゴリが存在しません')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            categories = Category.get_all()
            return render_template('todo_form.html',
                                 categories=categories,
                                 todo=None,
                                 action='create',
                                 form_data=request.form)
        
        # Todo作成
        todo = Todo(
            title=title,
            description=description,
            category_id=category_id,
            priority=priority,
            due_date=due_date
        )
        
        todo.save()
        flash('Todoが作成されました', 'success')
        return redirect(url_for('main.todos'))
        
    except Exception as e:
        current_app.logger.error(f"Error in create_todo POST: {str(e)}")
        flash('Todoの作成中にエラーが発生しました', 'error')
        return redirect(url_for('main.todos'))


@main_bp.route('/todos/<int:todo_id>/edit', methods=['GET', 'POST'])
def edit_todo(todo_id: int):
    """Todo編集ページ"""
    try:
        todo = Todo.get_by_id(todo_id)
        if not todo:
            flash('Todoが見つかりません', 'error')
            return redirect(url_for('main.todos'))
        
        if request.method == 'GET':
            categories = Category.get_all()
            return render_template('todo_form.html',
                                 categories=categories,
                                 todo=todo,
                                 action='edit')
        
        # POST処理
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category_id = request.form.get('category_id', type=int)
        priority = request.form.get('priority', 'medium')
        status = request.form.get('status', 'pending')
        due_date_str = request.form.get('due_date', '').strip()
        
        # バリデーション
        errors = []
        if not title:
            errors.append('タイトルは必須です')
        if len(title) > 200:
            errors.append('タイトルは200文字以内で入力してください')
        if priority not in ['low', 'medium', 'high']:
            errors.append('無効な優先度が指定されました')
        if status not in ['pending', 'in_progress', 'completed']:
            errors.append('無効なステータスが指定されました')
        
        # 日付変換
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            except ValueError:
                errors.append('日付形式が正しくありません')
        
        # カテゴリ存在チェック
        if category_id:
            category = Category.get_by_id(category_id)
            if not category:
                errors.append('指定されたカテゴリが存在しません')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            categories = Category.get_all()
            return render_template('todo_form.html',
                                 categories=categories,
                                 todo=todo,
                                 action='edit',
                                 form_data=request.form)
        
        # Todo更新
        todo.title = title
        todo.description = description
        todo.category_id = category_id
        todo.priority = priority
        todo.status = status
        todo.due_date = due_date
        
        todo.save()
        flash('Todoが更新されました', 'success')
        return redirect(url_for('main.todos'))
        
    except Exception as e:
        current_app.logger.error(f"Error in edit_todo: {str(e)}")
        flash('Todoの編集中にエラーが発生しました', 'error')
        return redirect(url_for('main.todos'))


@main_bp.route('/todos/<int:todo_id>/delete', methods=['POST'])
def delete_todo(todo_id: int):
    """Todo削除"""
    try:
        todo = Todo.get_by_id(todo_id)
        if not todo:
            flash('Todoが見つかりません', 'error')
            return redirect(url_for('main.todos'))
        
        todo.delete()
        flash('Todoが削除されました', 'success')
        
    except Exception as e:
        current_app.logger.error(f"Error in delete_todo: {str(e)}")
        flash('Todoの削除中にエラーが発生しました', 'error')
    
    return redirect(url_for('main.todos'))


@main_bp.route('/todos/<int:todo_id>/toggle', methods=['POST'])
def toggle_todo(todo_id: int):
    """Todo完了状態切り替え"""
    try:
        todo = Todo.get_by_id(todo_id)
        if not todo:
            flash('Todoが見つかりません', 'error')
            return redirect(url_for('main.todos'))
        
        if todo.status == 'completed':
            todo.mark_pending()
            flash('Todoを未完了にしました', 'info')
        else:
            todo.mark_completed()
            flash('Todoを完了にしました', 'success')
        
    except Exception as e:
        current_app.logger.error(f"Error in toggle_todo: {str(e)}")
        flash('Todo状態の変更中にエラーが発生しました', 'error')
    
    return redirect(url_for('main.todos'))


@main_bp.route('/categories')
def categories():
    """カテゴリ一覧ページ"""
    try:
        categories = Category.get_all()
        
        # 各カテゴリのTodo数を取得
        category_stats = {}
        for category in categories:
            todos = Todo.get_all(category_id=category.id)
            category_stats[category.id] = {
                'total': len(todos),
                'completed': len([t for t in todos if t.status == 'completed']),
                'pending': len([t for t in todos if t.status != 'completed'])
            }
            
        return render_template('categories.html',
                             categories=categories,
                             category_stats=category_stats)
                             
    except Exception as e:
        current_app.logger.error(f"Error in categories route: {str(e)}")
        flash('カテゴリ一覧の取得中にエラーが発生しました', 'error')
        return render_template('categories.html',
                             categories=[],
                             category_stats={})


def sort_todos(todos: list, sort_by: str, sort_order: str) -> list:
    """Todo一覧のソート処理"""
    reverse = sort_order == 'desc'
    
    if sort_by == 'title':
        return sorted(todos, key=lambda x: x.title.lower(), reverse=reverse)
    elif sort_by == 'priority':
        priority_order = {'high': 3, 'medium': 2, 'low': 1}
        return sorted(todos, key=lambda x: priority_order.get(x.priority, 0), reverse=reverse)
    elif sort_by == 'due_date':
        return sorted(todos, key=lambda x: x.due_date or datetime.max.date(), reverse=reverse)
    elif sort_by == 'status':
        status_order = {'pending': 1, 'in_progress': 2, 'completed': 3}
        return sorted(todos, key=lambda x: status_order.get(x.status, 0), reverse=reverse)
    else:  # created_at (default)
        return sorted(todos, key=lambda x: x.created_at or datetime.min, reverse=reverse)