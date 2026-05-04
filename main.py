import sys
from pathlib import Path
from backend.logger import logger, ROOT_DIR

if __name__ == '__main__':
    logger.info('Запуск приложения')
    logger.info(f'Python {sys.version}')
    logger.info(f'Данные: {ROOT_DIR / "data"}')
    # Инициализация БД, сессии и pywebview — Шаг 8
