import os

class Settings:
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "postgres")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", 5432))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "tork_bot_db")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "tork_admin")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "tork_db_pass_2026")

    JWT_SECRET: str = os.getenv("JWT_SECRET", "tork-b2b-dashboard-secret-jwt-key-2026")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_HOURS: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", 12))

settings = Settings()
