import os

# Корневая папка
BASE_DIR = r'D:\Git\optical_particle_analyzer\analyzer'
OUTPUT_FILE = os.path.join(BASE_DIR, 'merged_files.txt')

def collect_files():
    files = []

    # 1. HTML из templates и вложенных
    templates_dir = os.path.join(BASE_DIR, 'templates')
    for dirpath, _, filenames in os.walk(templates_dir):
        for f in filenames:
            if f.lower().endswith('.html'):
                files.append(os.path.join(dirpath, f))

    # 2. JS из static\vue и вложенных (кроме vue.global.prod.js)
    vue_dir = os.path.join(BASE_DIR, 'static', 'vue')
    for dirpath, _, filenames in os.walk(vue_dir):
        for f in filenames:
            if f.lower().endswith('.js') and f != 'vue.global.prod.js':
                files.append(os.path.join(dirpath, f))

    # 3. PY кроме __init__.py в BASE_DIR
    for f in os.listdir(BASE_DIR):
        if f.lower().endswith('.py') and f != '__init__.py':
            path = os.path.join(BASE_DIR, f)
            if os.path.isfile(path):
                files.append(path)

    return files

def relative_path(path):
    # Путь без корня
    return path.replace(BASE_DIR, '').replace('\\', '/').lstrip('/')

def main():
    files = collect_files()

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as out:
        for filepath in files:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            out.write('\n-----------------------\n')
            out.write(f'{relative_path(filepath)}\n')
            out.write('\n')
            out.write(content)
            out.write('\n-----------------------\n\n')

    print('Файлы успешно объединены в', OUTPUT_FILE)

if __name__ == '__main__':
    main()
