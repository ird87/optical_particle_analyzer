window.calibrationMixin = {
    delimiters: ['[[', ']]'],
    data() {
        return {
            calibId: 0,
            calibName: '',
            calibCoefficient: '',
            calibDivisionPrices: '',
            calibSelectedMicroscope: null,
            calibSelectedDivisionPrice: null,
            calibFileStates: ['sources.jpg', 'contrasted.jpg', 'contours.jpg', 'calibrated.jpg'],
            calibFileExistStates: { 'sources.jpg': false, 'contrasted.jpg': false, 'contours.jpg': false, 'calibrated.jpg': false },
            calibFileNames: {
                'sources.jpg': 'Исходный',
                'contrasted.jpg': 'Контраст',
                'contours.jpg': 'Контуры',
                'calibrated.jpg': 'Результат',
            },
            calibCurrentView: 'sources.jpg', // Активный файл для превью
            isCalibLoadVisible: false,
            calibrations: [],

            selectedCalibrationRow: null,
        };
    },
    computed: {
        // Проверяем, есть ли текущий файл для отображения
        isCalibCurrentFileAvailable() {
            return this.calibFileExistStates[this.calibCurrentView];
        },
        isSaveDisabled() {
            const num = parseFloat(this.calibCoefficient);
            return isNaN(num) || num <= 0;
        },
    },
    methods: {
        isDefaultCalibrationMicroscope() {
            return this.calibSelectedMicroscope?.type === 'DEFAULT';
        },
        toggleCalibLoadBlock() {
            this.isCalibLoadVisible = !this.isCalibLoadVisible;
            if (this.isCalibLoadVisible) {
                this.fetchCalibrations(); // Загружаем список при открытии
            }
        },
         handleCalibrationDblClick(calib) {
            // Здесь всё, что надо для загрузки: можно emit, либо напрямую
            this.loadCalibration(calib);
          },
        getCalibImageUrl(file) {
            const timestamp = new Date().getTime(); // Текущая метка времени
            return `/media/calibration/in_work/${file}?t=${timestamp}`;
        },
        changeCalibFile(view) {
            this.calibCurrentView = view;
        },
        async handleCalibFileSelect(event) {
            const file = event.target.files[0];
            if (!file) return;

            const formData = new FormData();
            formData.append('images[]', file, 'sources.jpg'); // Передаём файл с фиксированным именем
            formData.append('context', 'calibration');

            const response = await fetch('/upload_image/', { method: 'POST', body: formData });

            if (response.ok) {
                this.calibFileExistStates['sources.jpg'] = true; // Помечаем, что файл загружен
                this.calibFileExistStates['contrasted.jpg'] = false;
                this.calibFileExistStates['contours.jpg'] = false;
                this.calibFileExistStates['calibrated.jpg'] = false;
                this.calibCurrentView = 'sources.jpg'; // Активируем вкладку "Исходный"
            } else {
                console.error('Ошибка загрузки файла');
            }
        },
        async runCalibration() {
            const response = await fetch('/api/calibrations/execute/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({}), // Отправляем пустой объект, если других данных нет
            });
            if (response.ok) {
                const { coefficient } = await response.json();
                this.calibCoefficient = parseFloat(coefficient).toFixed(3);
                this.calibFileExistStates['contrasted.jpg'] = true;
                this.calibFileExistStates['contours.jpg'] = true;
                this.calibFileExistStates['calibrated.jpg'] = true;
                this.calibCurrentView = 'calibrated.jpg';
            } else {
                console.error('Ошибка выполнения калибровки');
            }
        },
        async saveCalibration() {
            try {
                const response = await fetch('/api/calibrations/save/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        id: this.calibId || 0, // Добавьте calibId в data()
                        name: this.calibName,
                        microscope: this.calibSelectedMicroscope?.name,
                        coefficient: parseFloat(this.calibCoefficient),
                        division_price: this.calibSelectedDivisionPrice?.name,
                    }),
                });

                if (response.ok) {
                    const data = await response.json();
                    this.calibId = data.id;
                    console.log('Сохранена калибровка с ID:', data.id);
                } else {
                    console.error('Ошибка сохранения калибровки.');
                }
            } catch (error) {
                console.error('Ошибка сохранения калибровки:', error);
            }
        },

        async fetchCalibrations() {
            try {
                const response = await fetch('/api/calibrations/');
                if (response.ok) {
                    this.calibrations = await response.json();
                } else {
                    console.error('Ошибка загрузки калибровок.');
                }
            } catch (error) {
                console.error('Ошибка загрузки калибровок:', error);
            }
        },

        async loadCalibration(calibration) {
            try {
                const response = await fetch(`/api/calibrations/${calibration.id}/load/`);
                if (response.ok) {
                    const data = await response.json();
                    const calib = data.calibration;

                    // Установка данных калибровки
                    this.calibId = calib.id;
                    this.calibName = calib.name;
                    this.calibCoefficient = calib.coefficient;

                    // Установка микроскопа
                    this.calibSelectedMicroscope = this.microscopes.find(
                        (microscope) => microscope.name === calib.microscope
                    );

                    // Установка цены деления
                    this.calibSelectedDivisionPrice = this.divisionPrices.find(
                        (price) => price.name === calib.division_price
                    );

                    // Установка состояний файлов
                    if (data.existing_files) {
                        this.calibFileExistStates = {
                            'sources.jpg': false,
                            'contrasted.jpg': false,
                            'contours.jpg': false,
                            'calibrated.jpg': false
                        };

                        data.existing_files.forEach(fileName => {
                            this.calibFileExistStates[fileName] = true;
                        });

                        // Установка активного вида
                        if (data.existing_files.includes('calibrated.jpg')) {
                            this.calibCurrentView = 'calibrated.jpg';
                        } else if (data.existing_files.includes('sources.jpg')) {
                            this.calibCurrentView = 'sources.jpg';
                        }
                    }

                    // Скрытие блока загрузки
                    this.toggleCalibLoadBlock();

                    console.log('Данные калибровки загружены:', data);
                } else {
                    console.error('Ошибка загрузки калибровки.');
                }
            } catch (error) {
                console.error('Ошибка загрузки калибровки:', error);
            }
        },

        selectCalibration(calibration) {
            this.selectedCalibrationRow = calibration;
        },

        async deleteCalibration(calibration) {
            if (!calibration) return;

            try {
                const response = await fetch(`/api/calibrations/${calibration.id}/delete/`, {
                    method: 'DELETE',
                });
                if (response.ok) {
                    this.calibrations = this.calibrations.filter(c => c.id !== calibration.id);
                    this.selectedCalibrationRow = null;
                } else {
                    console.error('Ошибка удаления калибровки.');
                }
            } catch (error) {
                console.error('Ошибка удаления калибровки:', error);
            }
        },

        createNewCalibration() {
            // Очистка всех полей
            this.calibId = 0;
            this.calibName = '';
            this.calibCoefficient = '';
            this.calibSelectedMicroscope = null;
            this.calibSelectedDivisionPrice = null;

            // Сброс состояний файлов
            this.calibFileExistStates = {
                'sources.jpg': false,
                'contrasted.jpg': false,
                'contours.jpg': false,
                'calibrated.jpg': false
            };
            this.calibCurrentView = 'sources.jpg';

            // Скрытие блока загрузки если он открыт
            if (this.isCalibLoadVisible) {
                this.toggleCalibLoadBlock();
            }
        },
        openCalibImageModal() {
            if (this.isCalibCurrentFileAvailable) {
                console.log("tyt")
                const modal = new bootstrap.Modal(document.getElementById('calibImageModal'));
                modal.show();
            }
        },
        closeCalibImageModal() {
            const modal = bootstrap.Modal.getInstance(document.getElementById('calibImageModal'));
            if (modal) {
                modal.hide();
            }
        },
        formatDate(dateString) {
            if (!dateString) return '-';

            const date = new Date(dateString);
            const options = {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            };

            return date.toLocaleDateString('ru-RU', options);
        },
    },
};
