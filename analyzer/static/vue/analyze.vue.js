window.analyzeMixin = {
    delimiters: ['[[', ']]'],
    data() {
        return {
            name: '',
            id: 0,
            employee: '',
            selectedMicroscope: null,
            selectedCalibration: null,
            microscopes: null, // Передача данных из context_processors
            files: [],
            currentFile: null,
            imageUrl: '',
            results: [],
            averages: {},
            lastUsedIndex: 0,
            isLoadBlockVisible: false, // Переключатель видимости блока загрузки
            researches: [], // Данные исследований
            selectedResearch: null, // Выбранное исследование
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
            return `/media/research/in_work/${folder}/${fileName}`;
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
                // Добавляем контекст исследования
                formData.append('context', 'research');

                const response = await fetch('/upload_image/', {
                    method: 'POST',
                    body: formData,
                });

                if (response.ok) {
                    const data = await response.json();

                    data.files.forEach((fileName) => {
                        this.files.push({
                            file: null,
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
                const response = await fetch('/api/researches/execute/', { // Новый URL
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                });

                if (response.ok) {
                    const data = await response.json();
                    this.results = data.results.contours;
                    this.averages = data.results.averages;

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
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        file_name: this.currentFile.name,
                        context: 'research', // Указываем контекст исследования
                    }),
                });

                if (response.ok) {
                    const index = this.files.indexOf(this.currentFile);
                    this.files.splice(index, 1);

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
       isDefaultMicroscope() {
            return this.selectedMicroscope?.type === 'DEFAULT';
        },
        isManualMicroscope() {
            return this.selectedMicroscope?.type === 'MANUAL';
        },
        isAutomaticMicroscope() {
            return this.selectedMicroscope?.type === 'AUTOMATIC';
        },
        createNewResearch() {
            location.reload(); // Обновляет страницу
        },
        toggleLoadBlock() {
            this.isLoadBlockVisible = !this.isLoadBlockVisible;
            if (this.isLoadBlockVisible) {
                this.fetchResearches();
            }
        },
        selectResearch(research) {
        // Устанавливаем текущую строку как выбранную
        this.selectedResearch = research;
    },
        async deleteResearch(research) {
            try {
                const response = await fetch(`/api/researches/${research.id}/delete/`, {
                    method: 'DELETE',
                });
                if (response.ok) {
                    this.researches = this.researches.filter(r => r.id !== research.id);
                    this.selectedResearch = null;
                } else {
                    console.error('Ошибка удаления исследования.');
                }
            } catch (error) {
                console.error('Ошибка удаления исследования:', error);
            }
        },
        async loadResearch(research) {
        try {
            const response = await fetch(`/api/researches/${research.id}/load/`);
            if (response.ok) {
                const data = await response.json();

                console.log(data)

                const research = data.research;

                // Установка основных данных
                this.id = research.id;
                this.name = research.name;
                this.employee = research.employee;
                this.selectedMicroscope = this.microscopes.find(
                    (microscope) => microscope.name === research.microscope
                );

                this.files = [];

                data.files.forEach((fileName) => {
                        this.files.push({
                            file: null,
                            name: fileName,
                        });
                    });

                 // Устанавливаем первый файл, если его еще нет
                if (!this.currentFile && this.files.length > 0) {
                    this.selectFile(this.files[0]);

                     if (this.currentFile) {
                        this.selectedFolder = 'analyzed';
                        this.imageUrl = this.getImageUrl(this.currentFile.name, 'analyzed');
                    }
                }

                // Установка контуров и средних значений
                this.results = research.contours;
                this.averages = {
                    perimeter: research.average_perimeter,
                    area: research.average_area,
                    width: research.average_width,
                    length: research.average_length,
                    dek: research.average_dek,
                };

                // Установка калибровки
                if (research.calibration) {
                    this.selectedCalibration = {
                        id: research.calibration.id,
                        name: research.calibration.name,
                        microscope: research.calibration.microscope,
                        coefficient: research.calibration.coefficient,
                    };
                } else {
                    this.selectedCalibration = null;
                }

                // Скрытие блока загрузки
                this.toggleLoadBlock();

                console.log('Данные исследования загружены:', data);
            } else {
                console.error('Ошибка загрузки исследования.');
            }
        } catch (error) {
            console.error('Ошибка загрузки исследования:', error);
        }
    },
    async saveResearch() {
        try {
            const response = await fetch('/api/researches/save/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    id: this.id,
                    name: this.name,
                    employee: this.employee,
                    microscope: this.selectedMicroscope?.name,
                    calibration_id: this.selectedCalibration?.id || 0, // ID калибровки или 0
                    average_perimeter: this.averages.perimeter,
                    average_area: this.averages.area,
                    average_width: this.averages.width,
                    average_length: this.averages.length,
                    average_dek: this.averages.dek,
                    contours: this.results,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                this.id = data.id;
                console.log('Сохранено исследование с ID:', data.id);
            } else {
                console.error('Ошибка сохранения исследования.');
            }
        } catch (error) {
            console.error('Ошибка сохранения исследования:', error);
        }
    },
    async fetchResearches() {
        try {
            const response = await fetch('/api/researches/');
            if (response.ok) {
                this.researches = await response.json();
            } else {
                console.error('Ошибка загрузки исследований.');
            }
        } catch (error) {
            console.error('Ошибка загрузки исследований:', error);
        }
    },

        canShowCamera() {
            return this.isManualMicroscope() || this.isAutomaticMicroscope();
        },
        openCamera() {
            console.log("Камера открыта");
        },
        startMicroscope() {
            console.log("Запуск микроскопа");
        },
        captureImage() {
            console.log("Снимок сделан");
        },
    },
    mounted() {
        // Инициализация при загрузке страницы
        this.lastUsedIndex = 0;
        const microscopesData = document.getElementById('app_analyze').getAttribute('data-microscopes');
        console.log(microscopesData);
        this.microscopes = JSON.parse(microscopesData);

        // Инициализация первого микроскопа
        this.selectedMicroscope = null;
        console.log(this.selectedMicroscope);
    },
};
