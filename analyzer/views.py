import os
import cv2
import json
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import shutil
import math
import numpy as np
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
    calibrations = Calibration.objects.all().values('id', 'name', 'microscope', 'coefficient', 'division_price', 'date')
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
            'division_price': calibration.division_price,
            'date': calibration.date,
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

        # Подготавливаем данные для сохранения
        calibration_data = {
            'name': data['name'],
            'microscope': data['microscope'],
            'coefficient': data['coefficient'],
            'division_price': data['division_price'],
        }

        # Если id == 0, создаём новую калибровку
        if data.get('id', 0) == 0:
            calibration = Calibration.objects.create(**calibration_data)
        else:
            # Обновляем существующую или создаём, если объект не найден
            calibration, _ = Calibration.objects.update_or_create(
                id=data['id'],
                defaults=calibration_data
            )


        # Теперь копируем 4 файла (если существуют) из in_work в calibration/<id>
        dest_dir = os.path.join(calibration_dir, str(calibration.id))
        os.makedirs(dest_dir, exist_ok=True)

        for fname in ['sources.jpg', 'contrasted.jpg', 'contours.jpg', 'calibrated.jpg']:
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
    Загрузка калибровки (без под-папок: files = sources.jpg, contrasted.jpg, contours.jpg, calibrated.jpg)
    """
    try:
        calibration = Calibration.objects.get(pk=pk)
        calibration_data = {
            'id': calibration.id,
            'name': calibration.name,
            'microscope': calibration.microscope,
            'coefficient': calibration.coefficient,
            'division_price': calibration.division_price,
            'date': calibration.date,
        }
        clear_calibration_in_work()

        # Копируем потенциальные файлы: sources.jpg, contrasted.jpg, contours.jpg, calibrated.jpg
        src_dir = os.path.join(calibration_dir, str(calibration.id))
        dst_dir = calibration_in_work_dir
        os.makedirs(dst_dir, exist_ok=True)

        for fname in ['sources.jpg', 'contrasted.jpg', 'contours.jpg', 'calibrated.jpg']:
            src_path = os.path.join(src_dir, fname)
            dst_path = os.path.join(dst_dir, fname)
            if os.path.exists(src_path):
                shutil.copy2(src_path, dst_path)

        # Собираем инфу, какие файлы реально существуют
        existing_files = []
        for fname in ['sources.jpg', 'contrasted.jpg', 'contours.jpg', 'calibrated.jpg']:
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
    1) Читаем sources.jpg
    2) Контрастируем -> contrasted.jpg
    3) Ищем вертикальные полосы на контрастной картинке (binary),
       заливаем их красным -> contours.jpg,
       но x-координату берём как minX по реальному контуру
    4) Считаем среднее расстояние -> coefficient
    5) Рисуем calibrated.jpg, где короткая красная линия
       действительно совпадает с подсчитанным расстоянием
    """
    try:
        source_path = os.path.join(calibration_in_work_dir, 'sources.jpg')
        if not os.path.exists(source_path):
            return JsonResponse({'error': 'sources.jpg not found'}, status=404)

        # (1) Читаем исходник
        src = cv2.imread(source_path, cv2.IMREAD_COLOR)
        if src is None:
            return JsonResponse({'error': 'Cannot read sources.jpg'}, status=500)

        # (2) Повышаем контраст -> contrasted.jpg
        contrasted = increase_contrast(src)
        contrasted_path = os.path.join(calibration_in_work_dir, 'contrasted.jpg')
        cv2.imwrite(contrasted_path, contrasted)

        # (3) Бинаризуем и ищем вертикальные полосы -> contours.jpg
        #     Для отрисовки красным будем использовать копию контрастной картинки.
        binary = find_vertical_lines(contrasted)
        contours_img = contrasted.copy()

        # detect_black_strips_left_edges теперь ищет minX в контуре
        xs = detect_black_strips_left_edges(binary, contours_img)
        contours_path = os.path.join(calibration_in_work_dir, 'contours.jpg')
        cv2.imwrite(contours_path, contours_img)

        # Если не нашли хотя бы 2 полосы — 0.0
        if len(xs) < 2:
            calibrate_path = os.path.join(calibration_in_work_dir, 'calibrated.jpg')
            cv2.imwrite(calibrate_path, contrasted)
            return JsonResponse({'status': 'success', 'coefficient': 0.0})

        # Считаем расстояния между соседними x
        distances = [xs[i] - xs[i-1] for i in range(1, len(xs))]
        avg_distance = sum(distances) / len(distances)

        # (4) Рисуем финальное изображение (calibrated.jpg) на контрасте
        final_img = contrasted.copy()
        h, w = final_img.shape[:2]

        # Синяя горизонтальная линия (между самой левой и самой правой полосой)
        y_blue = int(h * 0.6)
        cv2.line(final_img, (xs[0], y_blue), (xs[-1], y_blue), (255, 0, 0), 2)

        # "Центральное" расстояние (для наглядности)
        mid_index = len(distances) // 2
        d_mid = distances[mid_index]
        x_s = xs[mid_index]
        x_e = xs[mid_index + 1]

        y_red = int(h * 0.5)
        cv2.line(final_img, (x_s, y_red), (x_e, y_red), (0, 0, 255), 2)

        # Подписываем именно d_mid (или avg_distance, если хотите)
        text_pos = ((x_s + x_e) // 2, y_red - 10)
        text_val = f"{avg_distance:.3f}"
        cv2.putText(final_img, text_val, text_pos, cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (255,255,255), 3)
        cv2.putText(final_img, text_val, text_pos, cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (0,0,0), 1)

        calibrate_path = os.path.join(calibration_in_work_dir, 'calibrated.jpg')
        cv2.imwrite(calibrate_path, final_img)

        return JsonResponse({
            'status': 'success',
            'coefficient': round(avg_distance, 3)
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def increase_contrast(src):
    """
    Простейший пример поднятия контраста через CLAHE
    Возвращаем BGR картинку
    """
    gray = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    c_gray = clahe.apply(gray)
    return cv2.cvtColor(c_gray, cv2.COLOR_GRAY2BGR)


def find_vertical_lines(img_bgr):
    """
    Возвращает бинарную маску, где изначально тёмные вертикальные полосы
    становятся белыми (255).
    Здесь пример на адаптивном пороге + инвертировании + морфологии.
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # Адаптивный порог (инвертированный)
    binary_inv = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        blockSize=31,  # Подбирайте
        C=10
    )
    # Морфология, чтобы слегка склеить вертикальные полосы
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 7))
    closed = cv2.morphologyEx(binary_inv, cv2.MORPH_CLOSE, kernel, iterations=1)

    return closed


def detect_black_strips_left_edges(binary, draw_img):
    """
    Ищем контуры (белые полосы) на бинарной маске.
    - Для каждого контура берём minX среди всех пикселей этого контура
    - Закрашиваем контур красным
    - Возвращаем список всех minX, отсортированный
    """
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    xs = []
    h, w = draw_img.shape[:2]

    for cnt in contours:
        pts = cnt.reshape(-1, 2)  # (N, 2) массив x,y
        x_min = np.min(pts[:, 0])
        y_min = np.min(pts[:, 1])
        cw = np.max(pts[:, 0]) - x_min
        ch = np.max(pts[:, 1]) - y_min

        # Фильтрация «неадекватных» пятен
        if cw > w*0.7:
            # Слишком широкое
            continue
        if ch < 5:
            # Слишком низкое
            continue

        # Можно добавить aspect_ratio, если хотите отсекать "слишком широкие"
        aspect_ratio = ch / (cw+1)
        if aspect_ratio < 6.0:
           continue

        # Заливка красным
        cv2.drawContours(draw_img, [cnt], -1, (0, 0, 255), cv2.FILLED)

        xs.append(x_min)

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
            'calibration_id': data.get('calibration_id', None),
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

        # Работа с контурами
        contours = data.get('contours', [])
        with transaction.atomic():
            ContourData.objects.filter(research=research).delete()
            new_contours = [
                ContourData(
                    research=research,
                    contour_number=contour['contour_number'],
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
        try:
            # Получаем данные калибровки из запроса
            data = json.loads(request.body) if request.body else {}
            calibration_id = data.get('calibration_id', 0)

            # Получаем данные калибровки
            calibration_coefficient = 1.0  # Значение по умолчанию
            division_price_value = 1.0  # Значение по умолчанию

            if calibration_id > 0:
                try:
                    calibration = Calibration.objects.get(id=calibration_id)
                    calibration_coefficient = calibration.coefficient

                    # Извлекаем числовое значение из строки division_price (например, "1 мкм" -> 1)
                    division_price_str = calibration.division_price
                    division_price_value = float(division_price_str.split()[0])
                except Calibration.DoesNotExist:
                    pass  # Используем значения по умолчанию

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

                # Этап 3: Анализ (передаем данные калибровки)
                analyzed_image, contours, contour_number = analyze_contours(
                    contrasted, contour_number, calibration_coefficient, division_price_value
                )
                cv2.imwrite(os.path.join(analyzed_dir, file_name), analyzed_image)

                # Сохраняем результаты анализа
                all_contours.extend(contours)

            # Вычисляем средние значения
            if all_contours:
                for key in averages.keys():
                    averages[key] = sum(item[key] for item in all_contours) / len(all_contours)

            return JsonResponse({'results': {'contours': all_contours, 'averages': averages}})

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

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


def analyze_contours(image, start_number=1, calibration_coefficient=1.0, division_price_value=1.0):
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

        # Периметр в пикселях
        perimeter_pixels = cv2.arcLength(cnt, True)

        # Площадь в пикселях
        area_pixels = cv2.contourArea(cnt)

        # Минимальный ограничивающий прямоугольник
        rect = cv2.minAreaRect(cnt)
        box = cv2.boxPoints(rect)

        # Длина и ширина прямоугольника в пикселях
        width_pixels = min(rect[1])
        length_pixels = max(rect[1])

        # Диаметр эквивалентного круга в пикселях
        equivalent_diameter_pixels = math.sqrt((4 * area_pixels) / math.pi)

        # Конвертируем в реальные единицы
        perimeter_real = pixels_to_real_units(perimeter_pixels, calibration_coefficient, division_price_value)
        area_real = pixels_to_real_units(area_pixels, calibration_coefficient**2, division_price_value**2)  # Площадь - квадрат единиц
        length_real = pixels_to_real_units(length_pixels, calibration_coefficient, division_price_value)
        width_real = pixels_to_real_units(width_pixels, calibration_coefficient, division_price_value)
        dek_real = pixels_to_real_units(equivalent_diameter_pixels, calibration_coefficient, division_price_value)

        # Добавляем результат с реальными единицами
        results.append({
            'contour_number': start_number,
            'perimeter': round(perimeter_real, 2),
            'area': round(area_real, 2),
            'length': round(length_real, 2),
            'width': round(width_real, 2),
            'dek': round(dek_real, 2),
            'cx': cx,  # Координаты для рисования остаются в пикселях
            'cy': cy,  # Координаты для рисования остаются в пикселях
        })

        # Рисуем номер контура на изображении (координаты в пикселях)
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


def pixels_to_real_units(pixel_value, calibration_coefficient, division_price_value):
    """
    Конвертирует значение в пикселях в реальные единицы.

    Args:
        pixel_value (float): Значение в пикселях
        calibration_coefficient (float): Коэффициент калибровки (пикселей на единицу деления)
        division_price_value (float): Цена деления в микрометрах

    Returns:
        float: Значение в микрометрах
    """
    if calibration_coefficient == 0:
        return pixel_value  # Возвращаем исходное значение если калибровка не проведена

    # Переводим пиксели в единицы деления, затем в микрометры
    real_value = (pixel_value / calibration_coefficient) * division_price_value
    return real_value







