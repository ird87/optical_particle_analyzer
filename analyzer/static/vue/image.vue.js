const app = Vue.createApp({
    delimiters: ['[[', ']]'],
    data() {
        return {
            selectedFile: null, // Выбранный файл
            imageUrl: '',       // URL загруженного изображения
            results: []         // Результаты анализа
        };
    },
    methods: {
        // Обработчик выбора файла
        handleFileSelect(event) {
            this.selectedFile = event.target.files[0];
            if (this.selectedFile) {
                this.uploadImage();
            }
        },

        // Загрузка изображения
        async uploadImage() {
            if (!this.selectedFile) {
                alert('Пожалуйста, выберите файл.');
                return;
            }

            const formData = new FormData();
            formData.append('image', this.selectedFile);

            try {
                const response = await fetch('/upload_image/', {
                    method: 'POST',
                    body: formData
                });

                if (response.ok) {
                    const data = await response.json();
                    this.imageUrl = data.image_url;
                    this.results = []; // Сброс результатов при загрузке нового изображения
                } else {
                    alert('Ошибка загрузки изображения.');
                }
            } catch (error) {
                console.error('Ошибка загрузки:', error);
            }
        },

        // Обработка изображения
        async processImage(action) {
            const actionUrls = {
                contrast: '/process_contrast/',
                contour: '/process_contour/',
                analyze: '/process_analyze/'
            };

            try {
                const response = await fetch(actionUrls[action], {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        image_url: this.imageUrl
                    })
                });

                if (response.ok) {
                    const data = await response.json();
                    this.imageUrl = data.image_url;

                    // Обновляем результаты только для анализа
                    if (action === 'analyze' && data.results) {
                        console.log('Полученные результаты:', data.results); // Отладка
                        this.results = data.results;
                    }
                } else {
                    alert('Ошибка обработки изображения.');
                }
            } catch (error) {
                console.error('Ошибка обработки:', error);
            }
        }
    }
});

app.mount('#app');
