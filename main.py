import sys
from pathlib import Path

import webview

from backend.api import Api
from backend.database import init_db
from backend.logger import logger, ROOT_DIR
from backend.storage import clear_session

# При запуске из PyInstaller-бандла статика лежит в sys._MEIPASS
if getattr(sys, 'frozen', False):
    GUI_DIR = Path(sys._MEIPASS) / 'gui'
else:
    GUI_DIR = ROOT_DIR / 'gui'

INDEX_HTML = GUI_DIR / 'index.html'


def main():
    logger.info('Запуск приложения')
    logger.info(f'Python {sys.version}')
    logger.info(f'Данные: {ROOT_DIR / "data"}')

    init_db()
    clear_session()

    api = Api()

    window = webview.create_window(
        title='Оптический анализатор частиц',
        url=str(INDEX_HTML),
        js_api=api,
        width=1280,
        height=800,
        min_size=(900, 600),
        text_select=False,
    )

    logger.info(f'Открытие окна: {INDEX_HTML}')
    webview.start(debug=True)
    logger.info('Приложение закрыто')


if __name__ == '__main__':
    main()
