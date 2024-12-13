const app = Vue.createApp({
    delimiters: ['[[', ']]'],
    data() {
        return {
            description: '',
            performedBy: '',
            files: [],
            currentFile: null,
            imageUrl: '',
            results: [],
            averages: {},
            lastUsedIndex: 0,
            folders: ['sources', 'contrasted', 'contours', 'analyzed'],
            selectedFolder: 'sources',
            folderNames: {
                sources: 'Исходные',
                contrasted: 'Контраст',
                contours: 'Контуры',
                analyzed: 'Результат',
            },
        };
    },
    computed: {
        // Кнопка "Сохранить" доступна только если есть результаты
        isSaveButtonDisabled() {
            return this.results.length === 0;
        },
        // Доступность переключателей
        folderButtonStates() {
            if (this.files.length === 0) {
                return { sources: false, contrasted: false, contours: false, analyzed: false };
            } else if (this.results.length === 0) {
                return { sources: true, contrasted: false, contours: false, analyzed: false };
            } else {
                return { sources: true, contrasted: true, contours: true, analyzed: true };
            }
        },
    },
    methods: {
        // Получить URL для изображения
        getImageUrl(fileName, folder) {
            return `/media/in_work/${folder}/${fileName}`;
        },
        // Сменить папку для отображения
        changeFolder(folder) {
            if (this.folderButtonStates[folder]) {
                this.selectedFolder = folder;
                if (this.currentFile) {
                    this.imageUrl = this.getImageUrl(this.currentFile.name, folder);
                }
            }
        },
        // Обработка выбора файлов
        async handleFileSelect(event) {
            const newFiles = Array.from(event.target.files);
            const formData = new FormData();

            newFiles.forEach(file => {
                this.lastUsedIndex += 1;
                const numberedName = `${this.lastUsedIndex}.jpg`;
                formData.append('images[]', file, numberedName);
            });

            await this.uploadImages(formData);

            // Устанавливаем первый файл, если его еще нет
            if (!this.currentFile && this.files.length > 0) {
                this.selectFile(this.files[0]);
            }
        },
        // Установить выбранный файл
        selectFile(file) {
            this.currentFile = file;
            this.imageUrl = this.getImageUrl(file.name, this.selectedFolder);
        },
        // Загрузка изображений на сервер
        async uploadImages(formData) {
            try {
                const response = await fetch('/upload_image/', {
                    method: 'POST',
                    body: formData,
                });

                if (response.ok) {
                    const data = await response.json();
                    data.files.forEach((fileName) => {
                        this.files.push({
                            file: null, // Файл уже на сервере
                            name: fileName,
                        });
                    });
                } else {
                    console.error('Ошибка загрузки файлов.');
                }
            } catch (error) {
                console.error('Ошибка при загрузке файлов:', error);
            }
        },
        // Анализ всех файлов
        async analyzeAllFiles() {
    try {
        const response = await fetch('/process_images/analyze_all/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                description: this.description,
                performedBy: this.performedBy,
            }),
        });

        if (response.ok) {
            const data = await response.json();
            this.results = data.results.contours;
            this.averages = data.results.averages;

            // Автоматически переключаем папку отображения на "Результат"
            if (this.currentFile) {
                this.selectedFolder = 'analyzed';
                this.imageUrl = this.getImageUrl(this.currentFile.name, 'analyzed');
            }
        } else {
            console.error('Ошибка анализа.');
        }
    } catch (error) {
        console.error('Ошибка анализа:', error);
    }
},
        // Удаление текущего файла
        async deleteCurrentFile() {
            if (!this.currentFile) {
                console.error('Файл не выбран.');
                return;
            }

            try {
                const response = await fetch('/delete_image/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ file_name: this.currentFile.name }),
                });

                if (response.ok) {
                    const index = this.files.indexOf(this.currentFile);
                    this.files.splice(index, 1);

                    // Устанавливаем следующий или предыдущий файл
                    if (this.files.length > 0) {
                        const nextIndex = Math.min(index, this.files.length - 1);
                        this.selectFile(this.files[nextIndex]);
                    } else {
                        this.currentFile = null;
                        this.imageUrl = '';
                    }
                } else {
                    console.error('Ошибка удаления файла.');
                }
            } catch (error) {
                console.error('Ошибка при удалении файла:', error);
            }
        },
    },
    mounted() {
        // Инициализация при загрузке страницы
        this.lastUsedIndex = 0;
    },
});

app.mount('#app');
