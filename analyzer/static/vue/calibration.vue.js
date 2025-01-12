window.calibrationMixin = {
    delimiters: ['[[', ']]'],
    data() {
        return {
            calibName: '',
            calibCoefficient: '',
            calibSelectedMicroscope: null,
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
            const response = await fetch('/api/calibrations/execute/', { method: 'POST' });
            if (response.ok) {
                const { coefficient } = await response.json();
                this.calibCoefficient = parseFloat(coefficient).toFixed(3);
                this.calibFileExistStates['contrasted.jpg'] = true;
                this.calibFileExistStates['contours.jpg'] = true;
                this.calibFileExistStates['calibrated.jpg'] = true;
                this.calibCurrentView = 'calibrated.jpg'; // Переходим к результату
            }
        },
    },
};
