const app = Vue.createApp({
    delimiters: ['[[', ']]'],
    data() {
        return {
            files: [],           // Список файлов
            currentFile: null,   // Выбранное изображение
            imageUrl: '',        // URL текущего изображения
            results: [],         // Результаты анализа
            lastUsedIndex: 0     // Последний использованный номер файла
        };
    },
    methods: {
        // Обработчик выбора новых файлов
        handleFileSelect(event) {
            const newFiles = Array.from(event.target.files);

            const formData = new FormData(); // Создаем FormData для отправки файлов

            newFiles.forEach(file => {
                this.lastUsedIndex += 1; // Увеличиваем номер для нового файла
                const numberedName = `${this.lastUsedIndex}.jpg`; // Присваиваем новый номер
                this.files.push({ file: file, name: numberedName });

                // Добавляем файл в FormData с новым именем
                formData.append('images[]', file, numberedName);
            });

            // Отправляем новые файлы на сервер
            if (newFiles.length > 0) {
                this.uploadImages(formData);
            }

            // Если нет выбранного файла, выбираем первый из новых
            if (!this.currentFile && this.files.length > 0) {
                this.selectFile(this.files[0]);
            }
        },

        // Выбор текущего файла
        selectFile(file) {
            this.currentFile = file;
            this.imageUrl = URL.createObjectURL(file.file);
            this.results = []; // Очищаем результаты
        },

        // Удаление текущего файла
        deleteCurrentFile() {
            if (!this.currentFile) {
                alert('Файл не выбран.');
                return;
            }

            const index = this.files.indexOf(this.currentFile);

            if (index !== -1) {
                const fileNameToDelete = this.currentFile.name;

                // Отправляем запрос на сервер для удаления файла
                this.deleteFileFromServer(fileNameToDelete).then(() => {
                    this.files.splice(index, 1);

                    if (this.files.length > 0) {
                        // Если удаленный файл не последний, выбираем следующий
                        if (index < this.files.length) {
                            this.selectFile(this.files[index]);
                        } else {
                            // Если удаленный файл был последним, выбираем предыдущий
                            this.selectFile(this.files[index - 1]);
                        }
                    } else {
                        // Если файлов больше нет, сбрасываем выделение
                        this.currentFile = null;
                        this.imageUrl = '';
                        this.results = [];
                    }
                }).catch(error => {
                    console.error('Ошибка удаления файла на сервере:', error);
                    alert('Не удалось удалить файл на сервере.');
                });
            }
        },

        async uploadImages(formData) {
            try {
                const response = await fetch('/upload_image/', {
                    method: 'POST',
                    body: formData
                });

                if (response.ok) {
                    const data = await response.json();
                    console.log("Файлы успешно загружены:", data); // Отладка
                } else {
                    console.error("Ошибка загрузки файлов.");
                }
            } catch (error) {
                console.error("Ошибка при отправке файлов:", error);
            }
        },
         // Обработка всех файлов
        async processAllFiles(action) {
            if (this.files.length === 0) {
                alert('Нет изображений для обработки.');
                return;
            }

            try {
                const formData = new FormData();
                this.files.forEach(file => {
                    formData.append('images[]', file.file);
                });

                const response = await fetch(`/process_images/${action}/`, {
                    method: 'POST',
                    body: formData
                });

                if (response.ok) {
                    const data = await response.json();
                    if (action === 'analyze') {
                        this.results = data.results;
                    }
                    alert('Файлы успешно обработаны.');
                } else {
                    alert('Ошибка обработки файлов.');
                }
            } catch (error) {
                console.error('Ошибка обработки файлов:', error);
            }
        },

        async deleteFileFromServer(fileName) {
            try {
                const response = await fetch('/delete_image/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ file_name: fileName })
                });

                if (!response.ok) {
                    throw new Error('Ошибка удаления файла на сервере.');
                }

                console.log(`Файл "${fileName}" успешно удален с сервера.`);
            } catch (error) {
                console.error('Ошибка при удалении файла на сервере:', error);
                throw error;
            }
        }
    },
    mounted() {
        // При загрузке страницы инициализируем lastUsedIndex
        this.lastUsedIndex = 0;
    }
});

app.mount('#app');
