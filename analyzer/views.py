import os
import cv2
import json
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.conf import settings
import glob
import shutil

def clear_in_work():
    """Очищает все папки внутри `in work`."""
    in_work_dir = os.path.join(settings.MEDIA_ROOT, 'in work')
    if os.path.exists(in_work_dir):
        for folder in ['sources', 'contrasted', 'contours', 'analyzed']:
            folder_path = os.path.join(in_work_dir, folder)
            if os.path.exists(folder_path):
                shutil.rmtree(folder_path)
            os.makedirs(folder_path)

def home(request):
    # Очищаем папку in work
    clear_in_work()
    return render(request, 'home.html')


@csrf_exempt
def upload_image(request):
    if request.method == 'POST' and 'images[]' in request.FILES:
        images = request.FILES.getlist('images[]')  # Извлекаем список файлов
        print("Полученные файлы:", images)

        saved_urls = []
        for image in images:
            print(f"Сохраняем файл: {image.name}")
            # Сохраняем файл в папку sources
            save_path = os.path.join(settings.MEDIA_ROOT, 'in work', 'sources', image.name)
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            # Сохраняем файл поблочно
            with open(save_path, 'wb') as f:
                for chunk in image.chunks():
                    f.write(chunk)

            # Добавляем URL сохраненного файла в список
            saved_urls.append(os.path.join('/media', 'in work', 'sources', image.name))

        return JsonResponse({'status': 'success', 'image_urls': saved_urls})
    else:
        print("No 'images[]' in request.FILES")
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
            file_path = os.path.join(settings.MEDIA_ROOT, 'in work', folder, file_name)
            if os.path.exists(file_path):
                os.remove(file_path)

        return JsonResponse({'status': 'success'})
    else:
        return JsonResponse({'error': 'Неподдерживаемый метод'}, status=405)



@csrf_exempt
def list_images(request):
    sources_dir = os.path.join(settings.MEDIA_ROOT, 'in work/sources')
    if not os.path.exists(sources_dir):
        return JsonResponse({'files': []})

    files = os.listdir(sources_dir)
    files_data = [{'index': i + 1, 'name': f} for i, f in enumerate(files)]
    return JsonResponse({'files': files_data})



@csrf_exempt
def process_images(request, action):
    source_dir = os.path.join(settings.MEDIA_ROOT, 'in work/sources')
    target_dir = os.path.join(settings.MEDIA_ROOT, f'in work/{action}')
    os.makedirs(target_dir, exist_ok=True)

    if action == 'contrast':
        action_function = increase_contrast
    elif action == 'contours':
        action_function = find_and_draw_contours
    elif action == 'analyze':
        action_function = analyze_contours
    else:
        return JsonResponse({'error': 'Неизвестное действие'}, status=400)

    results = []
    for file_name in os.listdir(source_dir):
        source_path = os.path.join(source_dir, file_name)
        target_path = os.path.join(target_dir, file_name)
        image = cv2.imread(source_path)
        if image is None:
            continue

        if action == 'analyze':
            processed_image, analysis = action_function(image)
            results.append({'file_name': file_name, 'results': analysis})
        else:
            processed_image = action_function(image)

        cv2.imwrite(target_path, processed_image)

    if action == 'analyze':
        return JsonResponse({'results': results})
    return JsonResponse({'message': f'Файлы обработаны для {action}'})


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
    filtered_contours = [cnt for cnt in contours if cv2.contourArea(cnt) > 100]
    cv2.drawContours(image, filtered_contours, -1, (0, 0, 255), 2)
    return image


def analyze_contours(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    results = []
    filtered_contours = [cnt for cnt in contours if cv2.contourArea(cnt) > 100]
    for i, cnt in enumerate(filtered_contours):
        M = cv2.moments(cnt)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            perimeter = cv2.arcLength(cnt, True)
            area = cv2.contourArea(cnt)
            results.append({'number': i + 1, 'length': round(perimeter, 2), 'area': round(area, 2)})
            cv2.putText(image, str(i + 1), (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 6)
            cv2.putText(image, str(i + 1), (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
    return image, results
