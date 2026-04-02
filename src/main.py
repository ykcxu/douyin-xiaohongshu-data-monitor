from app.config.settings import get_settings
from app.services.bootstrap import init_db


def main() -> None:
    settings = get_settings()
    init_db()
    print("抖音小红书数据监测项目骨架已初始化。")
    print(f"应用名: {settings.app_name}")
    print(f"数据库: {settings.sqlalchemy_database_uri}")
    print(f"浏览器状态目录: {settings.browser_state_dir}")


if __name__ == "__main__":
    main()
