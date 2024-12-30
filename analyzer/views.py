import os
import cv2
import json
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.conf import settings
import glob
import shutil
import numpy as np
import math

def clear_in_work():
    """Очищает все папки внутри `in_work`."""
    in_work_dir = os.path.join(settings.MEDIA_ROOT, 'in_work')
    if os.path.exists(in_work_dir):
        for folder in ['sources', 'contrasted', 'contours', 'analyzed']:
            folder_path = os.path.join(in_work_dir, folder)
            if os.path.exists(folder_path):
                shutil.rmtree(folder_path)
            os.makedirs(folder_path)

def clear_in_work_except_sources():
    """Очищает все папки внутри `in_work`, кроме `sources`."""
    in_work_dir = os.path.join(settings.MEDIA_ROOT, 'in_work')
    if os.path.exists(in_work_dir):
        for folder in ['contrasted', 'contours', 'analyzed']:  # Исключаем `sources`
            folder_path = os.path.join(in_work_dir, folder)
            if os.path.exists(folder_path):
                shutil.rmtree(folder_path)
            os.makedirs(folder_path, exist_ok=True)


def home(request):
    # Очищаем папку in_work
    clear_in_work()
    return render(request, 'home.html')

@csrf_exempt
def upload_image(request):
    if request.method == 'POST' and 'images[]' in request.FILES:
        images = request.FILES.getlist('images[]')
        saved_files = []

        for image in images:
            # Формируем путь для сохранения
            save_path = os.path.join(settings.MEDIA_ROOT, 'in_work', 'sources', image.name)

            # Убедитесь, что директория существует
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
    if request.method == 'POST':
        data = json.loads(request.body)
        file_name = data.get('file_name')

        if not file_name:
            return JsonResponse({'error': 'Имя файла не указано'}, status=400)

        folders = ['sources', 'contrasted', 'contours', 'analyzed']
        for folder in folders:
            file_path = os.path.join(settings.MEDIA_ROOT, 'in_work', folder, file_name)
            if os.path.exists(file_path):
                os.remove(file_path)

        return JsonResponse({'status': 'success'})
    else:
        return JsonResponse({'error': 'Неподдерживаемый метод'}, status=405)



@csrf_exempt
def list_images(request):
    sources_dir = os.path.join(settings.MEDIA_ROOT, 'in_work/sources')
    if not os.path.exists(sources_dir):
        return JsonResponse({'files': []})

    files = os.listdir(sources_dir)
    files_data = [{'index': i + 1, 'name': f} for i, f in enumerate(files)]
    return JsonResponse({'files': files_data})



@csrf_exempt
def process_images_analyze_all(request):
    if request.method == 'POST':
        clear_in_work_except_sources()

        folders = ['contrasted', 'contours', 'analyzed']
        for folder in folders:
            os.makedirs(os.path.join(settings.MEDIA_ROOT, 'in_work', folder), exist_ok=True)

        source_dir = os.path.join(settings.MEDIA_ROOT, 'in_work/sources')
        contrasted_dir = os.path.join(settings.MEDIA_ROOT, 'in_work/contrasted')
        contours_dir = os.path.join(settings.MEDIA_ROOT, 'in_work/contours')
        analyzed_dir = os.path.join(settings.MEDIA_ROOT, 'in_work/analyzed')

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
            'number': start_number,
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



