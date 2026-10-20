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
          <div class="row g-2 mb-2">
            <div class="col-md-6">
              <label class="form-label">Название:</label>
              <input type="text" v-model="calibName" class="form-control">
            </div>
            <div class="col-md-6">
              <label class="form-label">Микроскоп:</label>
              <select v-model="calibSelectedMicroscope" class="form-select">
                <option v-for="m in $root.microscopes" :key="m.name" :value="m">{{ m.name }}</option>
              </select>
            </div>
          </div>
          <div class="row g-2 mb-3">
            <div class="col-sm-6 col-md-5">
              <label class="form-label">Цена деления:</label>
              <select v-model="calibSelectedDivisionPrice" class="form-select">
                <option v-for="p in $root.divisionPrices" :key="p.name" :value="p">{{ p.name }}</option>
              </select>
              <div class="form-text">Укажите расстояние между соседними штрихами.</div>
            </div>
            <div class="col-sm-6 col-md-4">
              <label class="form-label text-primary">K (коэффициент):</label>
              <input type="number" step="0.0001" v-model="calibCoefficient" class="form-control border-primary"
                     placeholder="После калибровки">
            </div>
            <div class="col-md-3 d-flex align-items-end">
              <button class="btn btn-success w-100" @click="saveCalibration" :disabled="isSaveDisabled">Сохранить</button>
            </div>
          </div>
        </div>

        <!-- Рабочая область: камера и превью рядом -->
        <div class="border p-3">
          <div class="row g-3">
            <div class="col-md-6 calibration-column">
              <h6 class="mb-2">Получение изображения:</h6>

              <!-- Загрузка файла (только для ручного микроскопа) -->
              <div class="mb-3" v-if="isDefaultMicroscope">
                <input type="file" accept="image/*" @change="handleFileSelect" class="form-control">
              </div>

              <camera-panel v-if="!isDefaultMicroscope" :microscope="calibSelectedMicroscope" context="calibration"
                            :active="$root.currentTab === 'calibration'" :revision="$root.calibrationRevision"
                            :disabled="busy || sessionSyncing" @connected="refreshSession" @captured="onCaptured" @error="errorMsg = $event"></camera-panel>

              <button class="btn btn-primary w-100"
                      :disabled="!calibFileExists['sources.jpg'] || !calibSelectedDivisionPrice || busy"
                      @click="runCalibration">
                {{ busy ? 'Выполняется...' : 'Калибровка' }}
              </button>
              <div v-if="calibDetection" class="calibration-detection small text-muted mt-2" aria-live="polite">
                Распознано штрихов: {{ calibDetection.count }} ·
                {{ calibDetection.orientation === 'horizontal' ? 'горизонтальные' : 'вертикальные' }}
              </div>
            </div>

            <div class="col-md-6 calibration-column d-flex flex-column align-items-center">
              <h6 class="text-center mb-2">Превью изображения:</h6>

              <!-- Переключатели файлов -->
              <div class="calibration-file-states d-flex flex-wrap gap-1 w-100 mb-3">
                <button v-for="fname in calibFileStates" :key="fname"
                        class="btn btn-outline-primary"
                        :class="{ active: calibCurrentView === fname }"
                        :disabled="!calibFileExists[fname]"
                        @click="calibCurrentView = fname">
                  {{ calibFileNames[fname] }}
                </button>
              </div>

              <!-- Картинка -->
              <div class="calibration-preview img-thumbnail d-flex justify-content-center align-items-center"
                   @click="openModal">
                <img v-if="calibFileExists[calibCurrentView] && calibImages[calibCurrentView]"
                     :src="calibImages[calibCurrentView]"
                     style="max-width:100%;max-height:100%;object-fit:contain;">
                <div v-else-if="calibFileExists[calibCurrentView] && !calibImages[calibCurrentView]"
                     class="text-muted small">Загрузка...</div>
                <span v-else class="text-muted">Нет изображения</span>
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
      sessionSyncing: false,
      refreshGeneration: 0,
      calibId:                   0,
      calibName:                 '',
      calibCoefficient:          '',
      calibDetection:            null,
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
      return !Number.isFinite(n) || n <= 0 || !this.calibSelectedMicroscope || !this.calibSelectedDivisionPrice || !this.calibName.trim() || this.busy;
    },
    isDefaultMicroscope() {
      return !this.calibSelectedMicroscope || this.calibSelectedMicroscope.type === 'DEFAULT';
    },
  },

  watch: {
    '$root.microscopes'(items) {
      if (this.calibSelectedMicroscope) {
        this.calibSelectedMicroscope = items.find(item => item.name === this.calibSelectedMicroscope.name) || null;
      }
    },
    '$root.currentTab'(tab) { if (tab === 'calibration') this.refreshSession(); },
  },
  methods: {
    async refreshSession() {
      const generation = ++this.refreshGeneration;
      this.sessionSyncing = true;
      try {
        const result = await api.listImages('calibration');
        if (generation !== this.refreshGeneration) return;
        if (!result.ok) { this.errorMsg = result.error; return; }
        if (result.revision <= this.$root.calibrationRevision) return;
        this.$root.calibrationRevision = result.revision;
        this.calibCoefficient = '';
        this.calibDetection = null;
        for (const filename of this.calibFileStates) {
          this.calibFileExists[filename] = result.files.includes(filename);
          this.calibImages[filename] = '';
        }
        this.calibCurrentView = 'sources.jpg';
        if (this.calibFileExists['sources.jpg']) await this._loadImage('sources.jpg');
      } finally { if (generation === this.refreshGeneration) this.sessionSyncing = false; }
    },
    async onCaptured(result) {
      if (result.revision <= this.$root.calibrationRevision) return;
      this.$root.calibrationRevision = result.revision;
      this.calibCoefficient = '';
      this.calibDetection = null;
      this.calibFileExists = {'sources.jpg':true,'contrasted.jpg':false,'contours.jpg':false,'calibrated.jpg':false};
      this.calibImages = {'sources.jpg':'','contrasted.jpg':'','contours.jpg':'','calibrated.jpg':''};
      this.calibCurrentView = 'sources.jpg';
      await this._loadImage('sources.jpg');
    },
    // ------------------------------------------------------------------
    // Сессия
    // ------------------------------------------------------------------
    async createNewCalibration() {
      const result = await api.newCalibration();
      if (!result.ok) { this.errorMsg = result.error; return; }
      this.$root.calibrationRevision = result.revision;
      this.calibId                   = 0;
      this.calibName                 = '';
      this.calibCoefficient          = '';
      this.calibDetection            = null;
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
        await this.onCaptured(res);
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
      this.calibCoefficient = '';
      this.calibDetection = null;
      const res = await api.executeCalibration();
      this.busy = false;
      if (res.ok && res.revision === this.$root.calibrationRevision) {
        this.calibCoefficient = parseFloat(res.coefficient).toFixed(3);
        if (res.marks_count) this.calibDetection = {count:res.marks_count,orientation:res.orientation};
        for (const fname of ['contrasted.jpg', 'contours.jpg', 'calibrated.jpg']) {
          this.calibFileExists[fname] = true;
          await this._loadImage(fname);
        }
        this.calibCurrentView = 'calibrated.jpg';
      } else {
        this.errorMsg = res.error || 'Исходное изображение изменилось. Повторите калибровку.';
      }
    },

    // ------------------------------------------------------------------
    // Сохранение
    // ------------------------------------------------------------------
    async saveCalibration() {
      this.errorMsg = '';
      const res = await api.saveCalibration({
        revision:      this.$root.calibrationRevision,
        id:            this.calibId,
        name:          this.calibName,
        microscope:    this.calibSelectedMicroscope?.name || '',
        coefficient:   parseFloat(this.calibCoefficient),
        division_price: this.calibSelectedDivisionPrice?.name || '',
      });
      if (res.ok) {
        this.calibId = res.id;
      } else {
        this.errorMsg = res.error || 'Ошибка сохранения калибровки.';
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

      this.$root.calibrationRevision = res.revision;
      const c = res.calibration;
      this.calibId          = c.id;
      this.calibName        = c.name;
      this.calibCoefficient = c.coefficient;
      this.calibDetection = null;
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
        if (res.active && res.revision >= this.$root.calibrationRevision) {
          this.calibId = 0;
          this.$root.calibrationRevision = res.revision;
        }
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
      const revision = this.$root.calibrationRevision;
      const res = await api.getImage(filename, '', 'calibration');
      if (revision !== this.$root.calibrationRevision) return;
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
