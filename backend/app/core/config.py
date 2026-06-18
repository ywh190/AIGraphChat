from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 数据库配置
    DATABASE_URL: str = "mysql+pymysql://root:123456@localhost:3306/medicine_db"
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "root"
    NEO4J_DATABASE: str = "medicine"

    # Redis 缓存配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""  # 可选，如果没有密码留空
    REDIS_ENABLED: bool = True  # 是否启用Redis缓存
    CACHE_DEFAULT_TTL: int = 3600  # 默认缓存时间（秒）
    CACHE_KEY_PREFIX: str = "tcm:"  # 缓存键前缀

    # JWT认证配置
    SECRET_KEY: str = "your-secret-key-change-this-in-production-environment"  # 生产环境请修改
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # 访问令牌过期时间（分钟）

    # AI 配置
    EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    OPENAI_API_KEY: str = ""  # OpenAI API密钥
    OPENAI_API_BASE: str = ""  # OpenAI API基础URL

    # 应用配置
    DEBUG: bool = True

    class Config:
        env_file = ".env"

settings = Settings()