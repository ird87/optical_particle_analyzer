window.CalibrationView = {
  template: `
    <div>

      <!-- Кнопки Новая / Загрузить -->
      <div v-if="!isCalibLoadVisible" class="col-md-4 d-flex justify-content-between mt-2 mb-2">
        <button class="btn flex-fill btn-primary me-1" @click="createNewCalibration">Новая</button>
        <button class="btn flex-fill btn-secondary ms-1" @click="toggleCalibLoadBlock">Загрузить</button>
      </div>

      <!-- Форма калибровки -->
      <div v-if="!isCalibLoadVisible">
        <div class="border p-2 pb-0 mb-2">
          <div class="row mb-2">
            <div class="col-md-6">
              <label class="form-label">Название:</label>
              <input type="text" v-model="calibName" class="form-control">
            </div>
            <div class="col-md-6">
              <label class="form-label">Цена деления:</label>
              <select v-model="calibSelectedDivisionPrice" class="form-select">
                <option v-for="p in $root.divisionPrices" :key="p.name" :value="p">{{ p.name }}</option>
              </select>
            </div>
          </div>
          <div class="row mb-3">
            <div class="col-md-6">
              <label class="form-label">Микроскоп:</label>
              <select v-model="calibSelectedMicroscope" class="form-select">
                <option v-for="m in $root.microscopes" :key="m.name" :value="m">{{ m.name }}</option>
              </select>
            </div>
            <div class="col-md-3">
              <label class="form-label text-primary">K (коэффициент):</label>
              <input type="number" step="0.0001" v-model="calibCoefficient" class="form-control border-primary"
                     placeholder="Будет рассчитан при калибровке">
            </div>
            <div class="col-md-3 d-flex align-items-end justify-content-end">
              <button class="btn btn-success" @click="saveCalibration" :disabled="isSaveDisabled">Сохранить</button>
            </div>
          </div>
        </div>

        <!-- Превью -->
        <div class="border p-3">
          <div class="row">
            <div class="col-md-4 d-flex flex-column align-items-center">
              <h6 class="text-center mb-2">Превью изображения:</h6>

              <!-- Переключатели файлов -->
              <div class="btn-group mb-3" style="width:350px;">
                <button v-for="fname in calibFileStates" :key="fname"
                        class="btn btn-outline-primary"
                        :class="{ active: calibCurrentView === fname }"
                        :disabled="!calibFileExists[fname]"
                        @click="calibCurrentView = fname">
                  {{ calibFileNames[fname] }}
                </button>
              </div>

              <!-- Картинка -->
              <div class="img-thumbnail d-flex justify-content-center align-items-center mb-3"
                   style="width:350px;height:300px;background:#f8f9fa;cursor:pointer;"
                   @click="openModal">
                <img v-if="calibFileExists[calibCurrentView] && calibImages[calibCurrentView]"
                     :src="calibImages[calibCurrentView]"
                     style="max-width:100%;max-height:100%;object-fit:contain;">
                <div v-else-if="calibFileExists[calibCurrentView] && !calibImages[calibCurrentView]"
                     class="text-muted small">Загрузка...</div>
                <span v-else class="text-muted">Нет изображения</span>
              </div>

              <!-- Загрузка файла (только для ручного микроскопа) -->
              <div class="mb-3" style="width:350px;" v-if="isDefaultMicroscope">
                <input type="file" accept="image/*" @change="handleFileSelect" class="form-control">
              </div>

              <!-- Кнопка Калибровка -->
              <div class="d-flex mb-3" style="width:350px;">
                <button class="btn btn-primary flex-fill"
                        :disabled="!calibFileExists['sources.jpg'] || !calibSelectedDivisionPrice || busy"
                        @click="runCalibration">
                  {{ busy ? 'Выполняется...' : 'Калибровка' }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Блок загрузки калибровки -->
      <div v-if="isCalibLoadVisible" class="border p-3 mb-4">
        <h6>Загрузка калибровки</h6>
        <table class="table table-bordered table-sm table-hover" style="cursor:pointer;">
          <thead>
            <tr>
              <th>Название</th><th>Микроскоп</th><th>Коэффициент</th><th>Дата</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in calibrations" :key="c.id"
                :class="{ 'table-active': selectedRow && selectedRow.id === c.id }"
                @click="selectedRow = c"
                @dblclick="loadCalibration(c)">
              <td>{{ c.name }}</td>
              <td>{{ c.microscope }}</td>
              <td>{{ c.coefficient }}</td>
              <td>{{ $root.formatDate(c.date) }}</td>
            </tr>
          </tbody>
        </table>
        <div class="d-flex col-md-6 justify-content-end mt-2 ms-auto">
          <button class="btn flex-fill btn-danger me-1"
                  :disabled="!selectedRow" @click="deleteCalibration">Удалить</button>
          <button class="btn flex-fill btn-primary me-1"
                  :disabled="!selectedRow" @click="loadCalibration(selectedRow)">Загрузить</button>
          <button class="btn flex-fill btn-secondary" @click="toggleCalibLoadBlock">Отменить</button>
        </div>
      </div>

      <div v-if="errorMsg" class="alert alert-danger mt-2">{{ errorMsg }}</div>

      <!-- Модальное окно полного размера -->
      <teleport to="body">
        <div class="modal fade" id="calibImageModal" tabindex="-1" aria-hidden="true">
          <div class="modal-dialog modal-fullscreen">
            <div class="modal-content bg-dark">
              <div class="modal-body d-flex justify-content-center align-items-center"
                   @click="closeModal" style="cursor:pointer;">
                <img v-if="calibImages[calibCurrentView]"
                     :src="calibImages[calibCurrentView]"
                     style="max-width:100%;max-height:100%;object-fit:contain;">
              </div>
            </div>
          </div>
        </div>
      </teleport>

    </div>
  `,

  data() {
    return {
      calibId:                   0,
      calibName:                 '',
      calibCoefficient:          '',
      calibSelectedMicroscope:   null,
      calibSelectedDivisionPrice: null,

      calibFileStates: ['sources.jpg', 'contrasted.jpg', 'contours.jpg', 'calibrated.jpg'],
      calibFileNames: {
        'sources.jpg':    'Исходный',
        'contrasted.jpg': 'Контраст',
        'contours.jpg':   'Контуры',
        'calibrated.jpg': 'Результат',
      },
      calibFileExists: {
        'sources.jpg': false, 'contrasted.jpg': false,
        'contours.jpg': false, 'calibrated.jpg': false,
      },
      calibImages: {
        'sources.jpg': '', 'contrasted.jpg': '',
        'contours.jpg': '', 'calibrated.jpg': '',
      },
      calibCurrentView:    'sources.jpg',

      isCalibLoadVisible:  false,
      calibrations:        [],
      selectedRow:         null,
      busy:                false,
      errorMsg:            '',
    };
  },

  computed: {
    isSaveDisabled() {
      const n = parseFloat(this.calibCoefficient);
      return isNaN(n) || n <= 0;
    },
    isDefaultMicroscope() {
      return !this.calibSelectedMicroscope || this.calibSelectedMicroscope.type === 'DEFAULT';
    },
  },

  methods: {
    // ------------------------------------------------------------------
    // Сессия
    // ------------------------------------------------------------------
    async createNewCalibration() {
      await api.newCalibration();
      this.calibId                   = 0;
      this.calibName                 = '';
      this.calibCoefficient          = '';
      this.calibSelectedMicroscope   = null;
      this.calibSelectedDivisionPrice = null;
      this.calibFileExists = { 'sources.jpg': false, 'contrasted.jpg': false, 'contours.jpg': false, 'calibrated.jpg': false };
      this.calibImages     = { 'sources.jpg': '', 'contrasted.jpg': '', 'contours.jpg': '', 'calibrated.jpg': '' };
      this.calibCurrentView = 'sources.jpg';
      this.errorMsg = '';
      if (this.isCalibLoadVisible) this.toggleCalibLoadBlock();
    },

    // ------------------------------------------------------------------
    // Загрузка файла с диска
    // ------------------------------------------------------------------
    async handleFileSelect(event) {
      const file = event.target.files[0];
      if (!file) return;
      const b64 = await this._readAsBase64(file);
      const res = await api.uploadImage('sources.jpg', b64, 'calibration');
      if (res.ok) {
        this.calibFileExists = { 'sources.jpg': true, 'contrasted.jpg': false, 'contours.jpg': false, 'calibrated.jpg': false };
        this.calibImages     = { 'sources.jpg': '', 'contrasted.jpg': '', 'contours.jpg': '', 'calibrated.jpg': '' };
        this.calibCurrentView = 'sources.jpg';
        await this._loadImage('sources.jpg');
      } else {
        this.errorMsg = 'Ошибка загрузки файла.';
      }
    },

    _readAsBase64(file) {
      return new Promise((resolve) => {
        const reader = new FileReader();
        reader.onload = (e) => resolve(e.target.result); // data URI
        reader.readAsDataURL(file);
      });
    },

    // ------------------------------------------------------------------
    // Калибровка
    // ------------------------------------------------------------------
    async runCalibration() {
      this.busy = true;
      this.errorMsg = '';
      const res = await api.executeCalibration();
      this.busy = false;
      if (res.ok) {
        this.calibCoefficient = parseFloat(res.coefficient).toFixed(3);
        for (const fname of ['contrasted.jpg', 'contours.jpg', 'calibrated.jpg']) {
          this.calibFileExists[fname] = true;
          await this._loadImage(fname);
        }
        this.calibCurrentView = 'calibrated.jpg';
      } else {
        this.errorMsg = 'Ошибка выполнения калибровки.';
      }
    },

    // ------------------------------------------------------------------
    // Сохранение
    // ------------------------------------------------------------------
    async saveCalibration() {
      this.errorMsg = '';
      const res = await api.saveCalibration({
        id:            this.calibId,
        name:          this.calibName,
        microscope:    this.calibSelectedMicroscope?.name || '',
        coefficient:   parseFloat(this.calibCoefficient),
        division_price: this.calibSelectedDivisionPrice?.name || '',
      });
      if (res.ok) {
        this.calibId = res.id;
      } else {
        this.errorMsg = 'Ошибка сохранения калибровки.';
      }
    },

    // ------------------------------------------------------------------
    // Список калибровок
    // ------------------------------------------------------------------
    async toggleCalibLoadBlock() {
      this.isCalibLoadVisible = !this.isCalibLoadVisible;
      if (this.isCalibLoadVisible) {
        const res = await api.getCalibrations();
        if (res.ok) {
          this.calibrations = res.calibrations;
        } else {
          this.errorMsg = 'Не удалось загрузить список калибровок.';
        }
        this.selectedRow = null;
      }
    },

    async loadCalibration(calib) {
      if (!calib) return;
      const res = await api.loadCalibration(calib.id);
      if (!res.ok) { this.errorMsg = 'Ошибка загрузки калибровки.'; return; }

      const c = res.calibration;
      this.calibId          = c.id;
      this.calibName        = c.name;
      this.calibCoefficient = c.coefficient;
      this.calibSelectedMicroscope   = this.$root.microscopes.find(m => m.name === c.microscope) || null;
      this.calibSelectedDivisionPrice = this.$root.divisionPrices.find(p => p.name === c.division_price) || null;

      // Сбрасываем изображения и помечаем существующие файлы
      this.calibImages     = { 'sources.jpg': '', 'contrasted.jpg': '', 'contours.jpg': '', 'calibrated.jpg': '' };
      this.calibFileExists = { 'sources.jpg': false, 'contrasted.jpg': false, 'contours.jpg': false, 'calibrated.jpg': false };
      for (const fname of (res.files || [])) {
        if (fname in this.calibFileExists) {
          this.calibFileExists[fname] = true;
          this._loadImage(fname);
        }
      }

      // Активируем лучший доступный файл
      const preferred = ['calibrated.jpg', 'sources.jpg'];
      this.calibCurrentView = preferred.find(f => this.calibFileExists[f]) || 'sources.jpg';

      this.isCalibLoadVisible = false;
      this.selectedRow = null;
      this.errorMsg = '';
    },

    async deleteCalibration() {
      if (!this.selectedRow) return;
      if (!confirm('Удалить калибровку?')) return;
      const res = await api.deleteCalibration(this.selectedRow.id);
      if (res.ok) {
        this.calibrations = this.calibrations.filter(c => c.id !== this.selectedRow.id);
        this.selectedRow = null;
      } else {
        this.errorMsg = 'Ошибка удаления калибровки.';
      }
    },

    // ------------------------------------------------------------------
    // Изображения
    // ------------------------------------------------------------------
    async _loadImage(filename) {
      const res = await api.getImage(filename, '', 'calibration');
      if (res.ok && res.data) {
        this.calibImages[filename] = res.data;
      }
    },

    // ------------------------------------------------------------------
    // Модальное окно
    // ------------------------------------------------------------------
    openModal() {
      if (!this.calibFileExists[this.calibCurrentView]) return;
      const modal = new bootstrap.Modal(document.getElementById('calibImageModal'));
      modal.show();
    },
    closeModal() {
      const inst = bootstrap.Modal.getInstance(document.getElementById('calibImageModal'));
      if (inst) inst.hide();
    },
  },
};
