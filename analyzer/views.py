import os
import cv2
import json
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.conf import settings
import urllib.parse

# Главная страница
def home(request):
    return render(request, 'home.html')

@csrf_exempt
def upload_image(request):
    if request.method == 'POST' and request.FILES.get('image'):
        image = request.FILES['image']

        ext = os.path.splitext(image.name)[1]
        ascii_name = f"image{ext}"

        save_path = os.path.join('uploaded_images', ascii_name)
        saved_path = default_storage.save(save_path, image)
        saved_url = default_storage.url(saved_path)

        return JsonResponse({'image_url': saved_url})
    else:
        return JsonResponse({'error': 'Изображение не передано'}, status=400)

# Обработчик для контраста
@csrf_exempt
def process_contrast(request):
    return process_image_action(request, increase_contrast, expect_results=False)

# Обработчик для контуров
@csrf_exempt
def process_contour(request):
    return process_image_action(request, find_and_draw_contours, expect_results=False)

# Обработчик для анализа
@csrf_exempt
def process_analyze(request):
    return process_image_action(request, analyze_contours, expect_results=True)

def process_image_action(request, action_function, expect_results=False):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)

            image_url = data.get('image_url')
            if not image_url:
                return JsonResponse({'error': 'URL изображения не указан'}, status=400)

            decoded_image_url = urllib.parse.unquote(image_url.replace(settings.MEDIA_URL, "").lstrip('/'))
            image_path = os.path.normpath(os.path.join(settings.MEDIA_ROOT, decoded_image_url))

            if not os.path.exists(image_path):
                return JsonResponse({'error': 'Файл не найден'}, status=404)

            image = cv2.imread(image_path)
            if image is None:
                return JsonResponse({'error': 'Ошибка загрузки изображения'}, status=400)

            if expect_results:
                processed_image, results = action_function(image)
            else:
                processed_image = action_function(image)

            processed_image_name = f"processed_{os.path.basename(image_path)}"
            processed_image_path = os.path.normpath(
                os.path.join(settings.MEDIA_ROOT, 'processed_images', processed_image_name)
            )
            os.makedirs(os.path.dirname(processed_image_path), exist_ok=True)

            cv2.imwrite(processed_image_path, processed_image)

            response = {'image_url': f"/media/processed_images/{processed_image_name}"}
            if expect_results:
                response['results'] = results
                print("Analysis Results:", results)  # Отладка: передача данных анализа

            return JsonResponse(response)

        except Exception as e:
            return JsonResponse({'error': f'Ошибка обработки изображения: {str(e)}'}, status=500)
    else:
        return JsonResponse({'error': 'Неподдерживаемый метод'}, status=405)

# Вспомогательные функции для обработки изображения
def increase_contrast(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrasted = clahe.apply(gray)
    blurred = cv2.GaussianBlur(contrasted, (5, 5), 0)
    contrasted_colored = cv2.cvtColor(blurred, cv2.COLOR_GRAY2BGR)
    return contrasted_colored

def find_and_draw_contours(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    img_height, img_width = image.shape[:2]

    min_area = 100
    filtered_contours = [
        cnt for cnt in contours
        if cv2.contourArea(cnt) >= min_area and
        not (cv2.boundingRect(cnt)[0] <= 0 or
             cv2.boundingRect(cnt)[1] <= 0 or
             (cv2.boundingRect(cnt)[0] + cv2.boundingRect(cnt)[2]) >= img_width or
             (cv2.boundingRect(cnt)[1] + cv2.boundingRect(cnt)[3]) >= img_height)
    ]

    cv2.drawContours(image, filtered_contours, -1, (0, 0, 255), 2)
    return image

def analyze_contours(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    img_height, img_width = image.shape[:2]

    min_area = 100
    filtered_contours = []
    results = []
    for i, cnt in enumerate(contours):
        area = cv2.contourArea(cnt)
        x, y, w, h = cv2.boundingRect(cnt)

        if area < min_area or x <= 0 or y <= 0 or (x + w) >= img_width or (y + h) >= img_height:
            continue

        perimeter = cv2.arcLength(cnt, True)
        results.append({
            'number': len(filtered_contours) + 1,
            'length': round(perimeter, 2),
            'area': round(area, 2),
        })

        filtered_contours.append(cnt)

    cv2.drawContours(image, filtered_contours, -1, (0, 0, 255), 2)
    for i, cnt in enumerate(filtered_contours):
        M = cv2.moments(cnt)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            cv2.putText(image, str(i + 1), (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 6)
            cv2.putText(image, str(i + 1), (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

    return image, results
