"""
アプリケーション設定モジュール
環境変数と設定値を管理
"""

import os
from datetime import timedelta
from dotenv import load_dotenv

# .envファイルを読み込み
load_dotenv()


class Config:
    """基本設定クラス"""
    
    # Flask基本設定
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # データベース設定
    DATABASE_PATH = os.environ.get('DATABASE_PATH') or 'todo_app.db'
    
    # デバッグモード
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() in ['true', '1', 'yes']
    
    # ホスト・ポート設定
    HOST = os.environ.get('FLASK_HOST', '0.0.0.0')
    PORT = int(os.environ.get('FLASK_PORT', 5000))
    
    # セッション設定
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    
    # ページネーション
    TODOS_PER_PAGE = int(os.environ.get('TODOS_PER_PAGE', 20))
    
    # API設定
    API_RATE_LIMIT = os.environ.get('API_RATE_LIMIT', '100/hour')
    
    # ログ設定
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'todo_app.log')
    
    # セキュリティ設定
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1時間
    
    # JSONレスポンス設定
    JSON_SORT_KEYS = False
    JSONIFY_PRETTYPRINT_REGULAR = DEBUG


class DevelopmentConfig(Config):
    """開発環境設定"""
    DEBUG = True
    DATABASE_PATH = 'todo_app_dev.db'
    LOG_LEVEL = 'DEBUG'


class TestingConfig(Config):
    """テスト環境設定"""
    TESTING = True
    DATABASE_PATH = ':memory:'  # インメモリデータベース
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'test-secret-key'


class ProductionConfig(Config):
    """本番環境設定"""
    DEBUG = False
    DATABASE_PATH = os.environ.get('DATABASE_PATH') or '/app/data/todo_app.db'
    
    # 本番環境では必須の設定チェック
    if not os.environ.get('SECRET_KEY'):
        raise ValueError("SECRET_KEY environment variable must be set in production")


# 環境設定マッピング
config_mapping = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config(config_name: str = None) -> Config:
    """設定クラスを取得"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')
    
    return config_mapping.get(config_name, DevelopmentConfig)