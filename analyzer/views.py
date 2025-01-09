import os
import cv2
import json
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import shutil
import math
from django.db import transaction
from django.views.decorators.http import require_http_methods
from .models import Research, ContourData, Calibration

# Пути для рабочих директорий
research_dir = os.path.join(settings.MEDIA_ROOT, 'research')
calibration_dir = os.path.join(settings.MEDIA_ROOT, 'calibration')
research_in_work_dir = os.path.join(research_dir, 'in_work')
calibration_in_work_dir = os.path.join(calibration_dir, 'in_work')


def get_files_in_directory(directory):
    if os.path.exists(directory):
        return [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
    return []

# Методы для калибровки
def clear_calibration_in_work():
    """
    Полностью удаляет папку calibration/in_work и создаёт её заново.
    """
    if os.path.exists(calibration_in_work_dir):
        shutil.rmtree(calibration_in_work_dir)
    os.makedirs(calibration_in_work_dir, exist_ok=True)



@require_http_methods(["GET"])
def calibration_list(request):
    """
    Возвращает список всех калибровок.
    """
    calibrations = Calibration.objects.all().values('id', 'name', 'microscope', 'coefficient')
    return JsonResponse(list(calibrations), safe=False)


@require_http_methods(["GET"])
def get_calibration(request, pk):
    """
    Возвращает данные калибровки по ID.
    """
    try:
        calibration = Calibration.objects.get(pk=pk)
        calibration_data = {
            'id': calibration.id,
            'name': calibration.name,
            'microscope': calibration.microscope,
            'coefficient': calibration.coefficient,
        }
        return JsonResponse(calibration_data)
    except Calibration.DoesNotExist:
        return JsonResponse({'error': 'Calibration not found'}, status=404)


@csrf_exempt
@require_http_methods(["POST"])
def save_calibration(request):
    """
    Сохранение калибровки + копирование files (если нужно).
    """
    try:
        data = json.loads(request.body)
        # Сохраняем/обновляем модель
        calibration, _ = Calibration.objects.update_or_create(
            id=data.get('id'),
            defaults={
                'name': data['name'],
                'microscope': data['microscope'],
                'coefficient': data['coefficient'],
            }
        )
        # Теперь копируем 4 файла (если существуют) из in_work в calibration/<id>
        dest_dir = os.path.join(calibration_dir, str(calibration.id))
        os.makedirs(dest_dir, exist_ok=True)

        for fname in ['sources.jpg', 'contrasted.jpg', 'contours.jpg', 'calibrate.jpg']:
            src_path = os.path.join(calibration_in_work_dir, fname)
            dst_path = os.path.join(dest_dir, fname)
            if os.path.exists(src_path):
                shutil.copy2(src_path, dst_path)

        return JsonResponse({'status': 'success', 'id': calibration.id})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)



@csrf_exempt
@require_http_methods(["GET"])
def load_calibration(request, pk):
    """
    Загрузка калибровки (без под-папок: files = sources.jpg, contrasted.jpg, contours.jpg, calibrate.jpg)
    """
    try:
        calibration = Calibration.objects.get(pk=pk)
        calibration_data = {
            'id': calibration.id,
            'name': calibration.name,
            'microscope': calibration.microscope,
            'coefficient': calibration.coefficient,
        }
        clear_calibration_in_work()

        # Копируем потенциальные файлы: sources.jpg, contrasted.jpg, contours.jpg, calibrate.jpg
        src_dir = os.path.join(calibration_dir, str(calibration.id))
        dst_dir = calibration_in_work_dir
        os.makedirs(dst_dir, exist_ok=True)

        for fname in ['sources.jpg', 'contrasted.jpg', 'contours.jpg', 'calibrate.jpg']:
            src_path = os.path.join(src_dir, fname)
            dst_path = os.path.join(dst_dir, fname)
            if os.path.exists(src_path):
                shutil.copy2(src_path, dst_path)

        # Собираем инфу, какие файлы реально существуют
        existing_files = []
        for fname in ['sources.jpg', 'contrasted.jpg', 'contours.jpg', 'calibrate.jpg']:
            if os.path.exists(os.path.join(dst_dir, fname)):
                existing_files.append(fname)

        return JsonResponse({
            'status': 'success',
            'calibration': calibration_data,
            'existing_files': existing_files,  # Например: ["sources.jpg", "contours.jpg"]
        })
    except Calibration.DoesNotExist:
        return JsonResponse({'error': 'Calibration not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_calibration(request, pk):
    """
    Удаляет калибровку из БД и соответствующую папку (calibration/<id>).
    """
    try:
        calibration = Calibration.objects.get(pk=pk)

        # Удаляем папку calibration/<id>
        folder_path = os.path.join(calibration_dir, str(calibration.id))
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)

        # Удаляем запись из БД
        calibration.delete()

        return JsonResponse({'status': 'success'})
    except Calibration.DoesNotExist:
        return JsonResponse({'error': 'Calibration not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def execute_calibration(request):
    """
    Пример эндпоинта, обрабатывающего sources.jpg, создающего
    contrasted.jpg, contours.jpg и calibrate.jpg.
    Находит вертикальные чёрные полосы и рассчитывает среднее расстояние.
    """
    try:
        source_path = os.path.join(calibration_in_work_dir, 'sources.jpg')
        if not os.path.exists(source_path):
            return JsonResponse({'error': 'sources.jpg not found'}, status=404)

        # 1) Читаем sources.jpg
        src = cv2.imread(source_path, cv2.IMREAD_COLOR)
        if src is None:
            return JsonResponse({'error': 'Cannot read sources.jpg'}, status=500)

        # 2) Контраст -> contrasted.jpg (например, через CLAHE)
        contrasted = increase_contrast(src)
        contrasted_path = os.path.join(calibration_in_work_dir, 'contrasted.jpg')
        cv2.imwrite(contrasted_path, contrasted)

        # 3) Поиск вертикальных полос -> contours.jpg
        #    На самом деле можно говорить именно о поиске "чёрных вертикальных" линий.
        #    Для простоты: делаем бинаризацию, ищем чёрные области, а потом определяем
        #    левый край каждой чёрной области. Сохраним промежуточную картинку.
        binary = find_vertical_lines(contrasted)
        contours_img = src.copy()
        # Чтобы отрисовать найденные края, например, небольшими красными линиями
        # (ниже в find_vertical_lines() у нас возвращается список X-координат).
        xs = detect_black_strips_left_edges(binary, contours_img)
        contours_path = os.path.join(calibration_in_work_dir, 'contours.jpg')
        cv2.imwrite(contours_path, contours_img)

        # 4) Вычисляем среднее расстояние между соседними X-координатами
        #    (x2 - x1), (x3 - x2), ...
        if len(xs) < 2:
            # Недостаточно полос для вычисления
            return JsonResponse({'status': 'success', 'coefficient': 0.0})

        distances = []
        for i in range(1, len(xs)):
            distances.append(xs[i] - xs[i-1])
        avg_distance = sum(distances) / len(distances)

        # 5) Итоговое изображение calibrate.jpg
        #    Рисуем синюю линию от x1 до xN по горизонтали, на некоторой Y
        #    Рисуем красную линию, соответствующую "среднему отрезку" (или "центральному").
        final_img = src.copy()
        h, w = final_img.shape[:2]

        # Считаем y для синей линии: "посередине со смещением вниз на 10%"
        # Например: y_blue = int(h * 0.5 + 0.1 * h) = int(0.6 * h)
        y_blue = int(0.5 * h + 0.1 * h)
        x_left = xs[0]
        x_right = xs[-1]
        cv2.line(final_img, (x_left, y_blue), (x_right, y_blue), (255, 0, 0), 2)

        # Выберем "средний отрезок"
        # Допустим, distances = [d1, d2, d3, ...], их на 1 меньше, чем полос
        # Средний индекс:
        mid_index = len(distances) // 2  # если четное количество, floor
        # Допустим, он d_mid = distances[mid_index]
        d_mid = distances[mid_index]
        # Чтобы нарисовать красную линию, нужно знать x_s и x_e для него
        # x_s = xs[mid_index]
        # x_e = xs[mid_index+1]
        x_s = xs[mid_index]
        x_e = xs[mid_index + 1]

        # y для красной линии (посередине со смещением вверх на 10%)
        y_red = int(0.5 * h - 0.1 * h)
        cv2.line(final_img, (x_s, y_red), (x_e, y_red), (0, 0, 255), 2)

        # Подписываем над красной линией значение d_mid (до 3 знаков)
        # Сдвинемся чуть выше линии, пусть на 10px
        text_pos = ( (x_s + x_e) // 2, y_red - 10 )
        cv2.putText(final_img, f"{d_mid:.3f}", text_pos,
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 4)
        cv2.putText(final_img, f"{d_mid:.3f}", text_pos,
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,0), 2)

        # Сохраняем final_img
        calibrate_path = os.path.join(calibration_in_work_dir, 'calibrated.jpg')
        cv2.imwrite(calibrate_path, final_img)

        return JsonResponse({
            'status': 'success',
            'coefficient': round(avg_distance, 3)  # Можно вернуть округлённое
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def increase_contrast(src):
    """Простейший пример поднятия контраста через CLAHE."""
    gray = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrasted = clahe.apply(gray)
    # Вернём обратно BGR-картинку, если хотим
    return cv2.cvtColor(contrasted, cv2.COLOR_GRAY2BGR)

def find_vertical_lines(img_bgr):
    """
    Возвращает ч/б (binary) изображение, где чёрные полосы могут быть выделены.
    Это упрощённый пример, можно менять логику.
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    # Для наглядности предполагаем, что чёрные полосы < 50
    _, binary = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY_INV)
    return binary

def detect_black_strips_left_edges(binary, draw_img):
    """
    Ищем отдельные вертикальные чёрные области,
    возвращаем список X-координат (левых краёв).
    Для наглядности рисуем красный маркер в draw_img.
    """
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    xs = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        # Считаем, что это вертикальная полоса, если w < 50% ширины всего изображения,
        # h достаточно большой, и т.п. Здесь можно добавить логику фильтрации.
        # В простом случае — считаем всё чёрное вертикальной полосой.
        xs.append(x)

        # Нарисуем небольшой маркер
        cv2.circle(draw_img, (x, y), 5, (0, 0, 255), -1)

    # Сортируем по возрастанию X (слева направо)
    xs.sort()
    return xs


def clear_research_directory(path):
    """
    Очищает все папки внутри указанной директории.
    Если директория не существует, она будет создана.
    """
    for folder in ['sources', 'contrasted', 'contours', 'analyzed']:
        folder_path = os.path.join(path, folder)
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)
        os.makedirs(folder_path, exist_ok=True)


def clear_research_directory_except_sources(path):
    """
    Очищает все папки внутри указанной директории, кроме sources.
    Если директория не существует, она будет создана.
    """
    for folder in ['contrasted', 'contours', 'analyzed']:
        folder_path = os.path.join(path, folder)
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)
        os.makedirs(folder_path, exist_ok=True)

def clear_research_in_work():
    """Очищает все папки внутри research/in_work."""
    clear_research_directory(research_in_work_dir)


def clear_research_in_work_except_sources():
    """Очищает все папки внутри research/in_work, кроме sources."""
    clear_research_directory_except_sources(research_in_work_dir)

def home(request):
    # Очищаем research/in_work
    clear_research_in_work()
    clear_calibration_in_work()
    return render(request, 'home.html')


@require_http_methods(["GET"])
def research_list(request):
    """
    Возвращает список исследований.
    """
    researches = Research.objects.all().values('id', 'name', 'employee', 'microscope', 'date')
    return JsonResponse(list(researches), safe=False)


@require_http_methods(["GET"])
def get_research(request, pk):
    """
    Возвращает данные исследования.
    """
    try:
        research = Research.objects.get(pk=pk)
        contours = list(ContourData.objects.filter(research=research).values(
            'contour_number', 'perimeter', 'area', 'width', 'length', 'dek'
        ))
        calibration = None
        if research.calibration:
            calibration = {
                'id': research.calibration.id,
                'name': research.calibration.name,
                'microscope': research.calibration.microscope,
                'coefficient': research.calibration.coefficient,
            }
        research_data = {
            'id': research.id,
            'name': research.name,
            'employee': research.employee,
            'microscope': research.microscope,
            'date': research.date,
            'average_perimeter': research.average_perimeter,
            'average_area': research.average_area,
            'average_width': research.average_width,
            'average_length': research.average_length,
            'average_dek': research.average_dek,
            'calibration': calibration,
            'contours': contours,
        }
        return JsonResponse(research_data)
    except Research.DoesNotExist:
        return JsonResponse({'error': 'Research not found'}, status=404)

@csrf_exempt
@require_http_methods(["POST"])
def save_research(request):
    """
    Сохраняет исследование.
    """
    try:
        data = json.loads(request.body)

        # Подготовка общих данных для исследования
        research_data = {
            'name': data['name'],
            'employee': data['employee'],
            'microscope': data['microscope'],
            'average_perimeter': data['average_perimeter'],
            'average_area': data['average_area'],
            'average_width': data['average_width'],
            'average_length': data['average_length'],
            'average_dek': data['average_dek'],
        }

        # Если id == 0, создаём новое исследование
        if data.get('id', 0) == 0:
            research = Research.objects.create(**research_data)
        else:
            # Обновляем существующее или создаём, если объект не найден
            research, _ = Research.objects.update_or_create(
                id=data['id'], defaults=research_data
            )

        # Установка калибровки
        calibration_id = data.get('calibration_id', 0)
        research.calibration_id = calibration_id if calibration_id > 0 else None
        research.save()

        # Работа с контурами
        contours = data.get('contours', [])
        with transaction.atomic():
            ContourData.objects.filter(research=research).delete()
            new_contours = [
                ContourData(
                    research=research,
                    contour_number=contour['number'],
                    perimeter=contour['perimeter'],
                    area=contour['area'],
                    width=contour['width'],
                    length=contour['length'],
                    dek=contour['dek'],
                )
                for contour in contours
            ]
            ContourData.objects.bulk_create(new_contours)

        # Обработка директорий
        cur_research_dir = os.path.join(research_dir, str(research.id))
        clear_research_directory(cur_research_dir)
        for folder in ['sources', 'contrasted', 'contours', 'analyzed']:
            src = os.path.join(research_in_work_dir, folder)
            dst = os.path.join(cur_research_dir, folder)
            if os.path.exists(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)

        return JsonResponse({'status': 'success', 'id': research.id})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def load_research(request, pk):
    """
    Загружает исследование по указанному ID, включая контуры и калибровку.
    Очищает research_in_work_dir и копирует данные из папки исследования.
    """
    try:
        # Получение исследования
        research = Research.objects.get(pk=pk)

        # Очищаем research_in_work_dir
        clear_research_in_work()

        # Путь к папке исследования
        cur_research_dir = os.path.join(research_dir, str(research.id))

        # Копируем папки из исследования в рабочую директорию
        for folder in ['sources', 'contrasted', 'contours', 'analyzed']:
            src = os.path.join(cur_research_dir, folder)
            dst = os.path.join(research_in_work_dir, folder)
            if os.path.exists(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)

        # Формирование данных калибровки
        calibration = None
        if research.calibration:
            calibration = {
                'id': research.calibration.id,
                'name': research.calibration.name,
                'microscope': research.calibration.microscope,
                'coefficient': research.calibration.coefficient,
            }

        # Формирование данных контуров
        contours = list(ContourData.objects.filter(research=research).values(
            'contour_number', 'perimeter', 'area', 'width', 'length', 'dek'
        ))

        # Формирование полного ответа
        research_data = {
            'id': research.id,
            'name': research.name,
            'employee': research.employee,
            'microscope': research.microscope,
            'date': research.date,
            'average_perimeter': research.average_perimeter,
            'average_area': research.average_area,
            'average_width': research.average_width,
            'average_length': research.average_length,
            'average_dek': research.average_dek,
            'calibration': calibration,  # Данные калибровки
            'contours': contours,       # Данные контуров
        }

        files_in_sources = get_files_in_directory(os.path.join(research_in_work_dir, 'sources'))

        return JsonResponse({'status': 'success', 'research': research_data, 'files':files_in_sources })
    except Research.DoesNotExist:
        return JsonResponse({'error': 'Research not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_research(request, pk):
    """
    Удаляет исследование.
    """
    try:
        research = Research.objects.get(pk=pk)
        cur_research_dir = os.path.join(research_dir, str(research.id))
        if os.path.exists(cur_research_dir):
            shutil.rmtree(cur_research_dir)
        research.delete()
        return JsonResponse({'status': 'success'})
    except Research.DoesNotExist:
        return JsonResponse({'error': 'Research not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def execute_research(request):
    """
    Выполняет обработку изображений (анализ) для исследований.
    """
    if request.method == 'POST':
        # Очищаем все, кроме sources
        clear_research_in_work_except_sources()

        source_dir = os.path.join(research_in_work_dir, 'sources')
        contrasted_dir = os.path.join(research_in_work_dir, 'contrasted')
        contours_dir = os.path.join(research_in_work_dir, 'contours')
        analyzed_dir = os.path.join(research_in_work_dir, 'analyzed')

        all_contours = []
        averages = {'perimeter': 0, 'area': 0, 'length': 0, 'width': 0, 'dek': 0}
        contour_number = 1  # Счётчик для сквозной нумерации

        for file_name in os.listdir(source_dir):
            source_path = os.path.join(source_dir, file_name)

            # Читаем изображение
            image = cv2.imread(source_path)

            # Этап 1: Контраст
            contrasted = increase_contrast(image)
            cv2.imwrite(os.path.join(contrasted_dir, file_name), contrasted)

            # Этап 2: Контуры
            contoured = find_and_draw_contours(contrasted)
            cv2.imwrite(os.path.join(contours_dir, file_name), contoured)

            # Этап 3: Анализ
            analyzed_image, contours, contour_number = analyze_contours(contrasted, contour_number)
            cv2.imwrite(os.path.join(analyzed_dir, file_name), analyzed_image)

            # Сохраняем результаты анализа
            all_contours.extend(contours)

        # Вычисляем средние значения
        if all_contours:
            for key in averages.keys():
                averages[key] = sum(item[key] for item in all_contours) / len(all_contours)

        return JsonResponse({'results': {'contours': all_contours, 'averages': averages}})
    return JsonResponse({'error': 'Метод не поддерживается'}, status=405)

# Обработки
def increase_contrast(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrasted = clahe.apply(gray)
    blurred = cv2.GaussianBlur(contrasted, (5, 5), 0)
    return cv2.cvtColor(blurred, cv2.COLOR_GRAY2BGR)


def find_and_draw_contours(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    height, width = image.shape[:2]

    # Проверяем, чтобы контур не пересекал границы изображения
    def is_within_bounds(contour):
        for point in contour:
            x, y = point[0]
            if x <= 0 or y <= 0 or x >= width - 1 or y >= height - 1:
                return False
        return True

    filtered_contours = [cnt for cnt in contours if cv2.contourArea(cnt) > 100 and is_within_bounds(cnt)]
    cv2.drawContours(image, filtered_contours, -1, (0, 0, 255), 2)
    return image


def analyze_contours(image, start_number=1):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    results = []
    height, width = image.shape[:2]

    # Проверяем, чтобы контур не пересекал границы изображения
    def is_within_bounds(contour):
        for point in contour:
            x, y = point[0]
            if x <= 0 or y <= 0 or x >= width - 1 or y >= height - 1:
                return False
        return True

    filtered_contours = [cnt for cnt in contours if cv2.contourArea(cnt) > 100 and is_within_bounds(cnt)]

    for cnt in filtered_contours:
        M = cv2.moments(cnt)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])

        # Периметр
        perimeter = cv2.arcLength(cnt, True)

        # Площадь
        area = cv2.contourArea(cnt)

        # Минимальный ограничивающий прямоугольник
        rect = cv2.minAreaRect(cnt)
        box = cv2.boxPoints(rect)

        # Длина и ширина прямоугольника
        width = min(rect[1])
        length = max(rect[1])

        # Диаметр эквивалентного круга
        equivalent_diameter = math.sqrt((4 * area) / math.pi)

        # Добавляем результат
        results.append({
            'contour_number': start_number,
            'perimeter': round(perimeter, 2),
            'area': round(area, 2),
            'length': round(length, 2),
            'width': round(width, 2),
            'dek': round(equivalent_diameter, 2),
            'cx': cx,
            'cy': cy,
        })

        # Рисуем номер контура на изображении
        cv2.putText(image, str(start_number), (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 6)
        cv2.putText(image, str(start_number), (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)

        start_number += 1

    return image, results, start_number

@csrf_exempt
def upload_image(request):
    """
    При контексте 'calibration' сохраняем файл под именем 'sources.jpg'
    """
    if request.method == 'POST' and 'images[]' in request.FILES:
        context = request.POST.get('context', 'research')
        images = request.FILES.getlist('images[]')

        if context == 'calibration':
            save_path = os.path.join(calibration_in_work_dir, 'sources.jpg')
            os.makedirs(calibration_in_work_dir, exist_ok=True)  # Убедимся, что директория существует
            with open(save_path, 'wb') as f:
                for chunk in images[0].chunks():
                    f.write(chunk)
            return JsonResponse({'status': 'success'})

        elif context == 'research':
            # Выбираем рабочую директорию
            in_work_dir = research_in_work_dir if context == 'research' else calibration_in_work_dir

            images = request.FILES.getlist('images[]')
            saved_files = []

            for image in images:
                # Формируем путь для сохранения
                save_path = os.path.join(in_work_dir, 'sources', image.name)
                os.makedirs(os.path.dirname(save_path), exist_ok=True)

                # Сохраняем файл
                with open(save_path, 'wb') as f:
                    for chunk in image.chunks():
                        f.write(chunk)

                saved_files.append(image.name)

            return JsonResponse({'status': 'success', 'files': saved_files})
        else:
            return JsonResponse({'error': 'Invalid context'}, status=400)

    return JsonResponse({'error': 'No images provided'}, status=400)

@csrf_exempt
def delete_image(request):
    """
    Удаляет изображения в зависимости от контекста (исследование или калибровка).
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        context = data.get('context', 'research')  # Контекст: research или calibration
        file_name = data.get('file_name')

        if not file_name or context not in ['research', 'calibration']:
            return JsonResponse({'error': 'Неверные параметры'}, status=400)

        # Выбираем рабочую директорию
        in_work_dir = research_in_work_dir if context == 'research' else calibration_in_work_dir

        folders = ['sources', 'contrasted', 'contours', 'analyzed']
        for folder in folders:
            file_path = os.path.join(in_work_dir, folder, file_name)
            if os.path.exists(file_path):
                os.remove(file_path)

        return JsonResponse({'status': 'success'})
    else:
        return JsonResponse({'error': 'Неподдерживаемый метод'}, status=405)


@csrf_exempt
def list_images(request):
    """
    Возвращает список изображений в зависимости от контекста (исследование или калибровка).
    """
    context = request.GET.get('context', 'research')  # Контекст: research или calibration
    if context not in ['research', 'calibration']:
        return JsonResponse({'error': 'Invalid context specified'}, status=400)

    # Выбираем рабочую директорию
    in_work_dir = research_in_work_dir if context == 'research' else calibration_in_work_dir
    sources_dir = os.path.join(in_work_dir, 'sources')

    if not os.path.exists(sources_dir):
        return JsonResponse({'files': []})

    files = os.listdir(sources_dir)
    files_data = [{'index': i + 1, 'name': f} for i, f in enumerate(files)]
    return JsonResponse({'files': files_data})








