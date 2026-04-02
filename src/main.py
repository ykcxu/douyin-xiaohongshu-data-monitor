from pathlib import Path


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    print("抖音小红书数据监测项目已初始化。")
    print(f"项目路径: {project_root}")


if __name__ == "__main__":
    main()
