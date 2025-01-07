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
    """Очищает все папки внутри calibration/in_work."""
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
    Сохраняет данные калибровки.
    """
    try:
        data = json.loads(request.body)
        calibration, created = Calibration.objects.update_or_create(
            id=data.get('id'),
            defaults={
                'name': data['name'],
                'microscope': data['microscope'],
                'coefficient': data['coefficient'],
            },
        )
        return JsonResponse({'status': 'success', 'id': calibration.id})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def load_calibration(request, pk):
    """
    Загружает данные калибровки по ID и очищает calibration/in_work.
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
        return JsonResponse({'status': 'success', 'calibration': calibration_data})
    except Calibration.DoesNotExist:
        return JsonResponse({'error': 'Calibration not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_calibration(request, pk):
    """
    Удаляет данные калибровки.
    """
    try:
        calibration = Calibration.objects.get(pk=pk)
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
    Выполняет калибровку (заглушка).
    """
    clear_calibration_in_work()
    # Добавить здесь логику выполнения калибровки
    return JsonResponse({'status': 'success', 'message': 'Calibration executed (placeholder)'})


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
    Сохраняет изображения в зависимости от контекста (исследование или калибровка).
    """
    if request.method == 'POST' and 'images[]' in request.FILES:
        context = request.POST.get('context', 'research')  # Контекст: research или calibration
        if context not in ['research', 'calibration']:
            return JsonResponse({'error': 'Invalid context specified'}, status=400)

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
        return JsonResponse({'error': 'Изображения не переданы'}, status=400)


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








