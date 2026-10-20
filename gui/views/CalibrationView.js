window.CalibrationView = {
  template: `
    <div>

      <div v-if="!isCalibLoadVisible" class="calibration-editor">
        <div class="workspace-heading">
          <h6 class="mb-0">Калибровка масштаба</h6>
          <div class="d-flex gap-2">
            <button class="btn btn-sm btn-outline-primary" :disabled="working" @click="createNewCalibration">Новая</button>
            <button class="btn btn-sm btn-outline-secondary" :disabled="working" @click="toggleCalibLoadBlock">Открыть сохранённую</button>
          </div>
        </div>

        <div class="row g-2 mb-2 calibration-controls">
          <div class="col-md-5">
            <label for="calibration-microscope" class="form-label">Микроскоп</label>
            <select id="calibration-microscope" v-model="calibSelectedMicroscope" class="form-select" :disabled="working" @change="onMicroscopeChange">
              <option :value="null" disabled>Выберите микроскоп</option>
              <option v-for="m in $root.microscopes" :key="m.name" :value="m">{{ m.type === 'DEFAULT' ? 'Изображения с диска' : m.name }}</option>
            </select>
          </div>
          <div class="col-md-3">
            <label for="calibration-source" class="form-label">Источник снимка</label>
            <select id="calibration-source" v-model="sourceMode" class="form-select" :disabled="working || !calibSelectedMicroscope">
              <option value="camera" :disabled="isDefaultMicroscope">Камера</option>
              <option value="file">Загрузить файл</option>
            </select>
          </div>
          <div class="col-md-4">
            <label for="calibration-division" class="form-label">Между соседними штрихами</label>
            <select id="calibration-division" v-model="calibSelectedDivisionPrice" class="form-select" :disabled="working">
              <option :value="null" disabled>Выберите цену деления</option>
              <option v-for="p in $root.divisionPrices" :key="p.name" :value="p">{{ p.name }}</option>
            </select>
          </div>
        </div>

        <div class="calibration-resultbar border rounded p-2 mb-2">
          <div class="d-flex align-items-center gap-3 flex-wrap">
            <button class="btn btn-primary" :disabled="isCalculateDisabled" @click="runCalibration">{{ busy ? 'Расчёт…' : 'Рассчитать масштаб' }}</button>
            <div class="calibration-scale" aria-live="polite">
              <strong v-if="scaleValue">{{ scaleValue }} мкм/пикс</strong>
              <span v-else class="text-muted">Масштаб ещё не рассчитан</span>
              <div v-if="calibCoefficient" class="small text-muted">{{ calibCoefficient }} пикселей на деление</div>
              <div v-if="calibDetection" class="calibration-detection small text-muted">
                Штрихов: {{ calibDetection.count }} · {{ calibDetection.orientation === 'horizontal' ? 'горизонтальные' : 'вертикальные' }}
              </div>
            </div>
            <div class="calibration-save d-flex align-items-center gap-2 ms-auto">
              <input aria-label="Название калибровки" type="text" v-model="calibName" class="form-control" placeholder="Название калибровки" :disabled="working">
              <button class="btn btn-success text-nowrap" :disabled="isSaveDisabled" @click="saveCalibration">{{ saving ? 'Сохранение…' : 'Сохранить' }}</button>
            </div>
          </div>
          <div class="small mt-1" :class="successMsg && !hasUnsavedChanges ? 'text-success' : 'text-muted'" role="status">
            {{ successMsg && !hasUnsavedChanges ? successMsg : (saveDisabledReason || (hasUnsavedChanges ? 'Есть несохранённые изменения' : '')) }}
          </div>
        </div>
        <div v-if="errorMsg" class="alert alert-danger py-2 mb-2" role="alert">{{ errorMsg }}</div>

        <div class="row g-3 calibration-workspace">
          <div class="col-md-6 calibration-column">
            <h6 class="mb-2">1. Получите снимок шкалы</h6>
            <div v-if="sourceMode === 'file' || isDefaultMicroscope" class="mb-2">
              <input aria-label="Снимок шкалы" type="file" accept="image/*" @change="handleFileSelect" class="form-control" :disabled="working || !calibSelectedMicroscope">
            </div>
            <camera-panel v-else :microscope="calibSelectedMicroscope" context="calibration"
                          :active="$root.currentTab === 'calibration' && !isCalibLoadVisible" :revision="$root.calibrationRevision"
                          :disabled="working" @capturing="capturePending = $event" @connected="refreshSession" @captured="onCaptured"></camera-panel>
            <div class="small text-muted">В кадре нужны не менее четырёх чётких штрихов с одинаковым шагом. Расположите их горизонтально или вертикально.</div>
          </div>
          <div class="col-md-6 calibration-column">
            <div class="d-flex justify-content-between align-items-center gap-2 mb-2">
              <h6 class="mb-0">2. Проверьте результат</h6>
              <select aria-label="Вид изображения шкалы" v-model="calibCurrentView" class="form-select form-select-sm calibration-view-select">
                <option v-for="fname in calibFileStates" :key="fname" :value="fname" :disabled="!calibFileExists[fname]">{{ calibFileNames[fname] }}</option>
              </select>
            </div>
            <button type="button" class="calibration-preview img-thumbnail d-flex justify-content-center align-items-center" @click="openModal" :disabled="!calibFileExists[calibCurrentView]" aria-label="Открыть изображение шкалы крупно">
              <img v-if="calibFileExists[calibCurrentView] && calibImages[calibCurrentView]" :src="calibImages[calibCurrentView]" alt="Снимок шкалы" class="workspace-image">
              <span v-else class="text-muted small">{{ calibFileExists[calibCurrentView] ? 'Загрузка…' : 'Снимите шкалу или загрузите изображение' }}</span>
            </button>
          </div>
        </div>
        <details class="mt-2 calibration-advanced">
          <summary class="small text-muted">Ручная корректировка коэффициента</summary>
          <label class="form-check mt-2"><input type="checkbox" v-model="manualCoefficient" class="form-check-input" :disabled="working || !calibSelectedMicroscope"> Ввести коэффициент вручную</label>
          <label for="calibration-coefficient" class="form-label">Пикселей на одно деление</label>
          <input id="calibration-coefficient" type="number" min="0" step="0.001" v-model="calibCoefficient" @input="onManualCoefficient" class="form-control form-control-sm" :disabled="working || !manualCoefficient || !calibSelectedMicroscope">
        </details>
      </div>

      <!-- Блок загрузки калибровки -->
      <div v-if="isCalibLoadVisible" class="border p-3 mb-4">
        <h6>Загрузка калибровки</h6>
        <table class="table table-bordered table-sm table-hover" style="cursor:pointer;">
          <thead>
            <tr>
              <th>Название</th><th>Микроскоп</th><th>Пикс/деление</th><th>Дата</th>
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
                  :disabled="working || !selectedRow" @click="deleteCalibration">Удалить</button>
          <button class="btn flex-fill btn-primary me-1"
                  :disabled="working || !selectedRow" @click="loadCalibration(selectedRow)">Загрузить</button>
          <button class="btn flex-fill btn-secondary" :disabled="working" @click="toggleCalibLoadBlock">Отменить</button>
        </div>
      </div>

      <div v-if="isCalibLoadVisible && errorMsg" class="alert alert-danger mt-2" role="alert">{{ errorMsg }}</div>

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
      sourceMode: 'camera',
      activeMicroscopeName: '',
      capturePending: false,
      sourceMicroscopeName: '',
      coefficientMicroscopeName: '',
      manualCoefficient: false,
      saving: false,
      savedFingerprint: '',
      successMsg: '',
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
    working() { return this.busy || this.saving || this.sessionSyncing || this.capturePending; },
    sourceMatchesMicroscope() {
      return !!this.calibSelectedMicroscope && this.sourceMicroscopeName === this.calibSelectedMicroscope.name;
    },
    calculateDisabledReason() {
      if (this.working) return 'Дождитесь завершения операции';
      if (!this.calibSelectedMicroscope) return 'Выберите микроскоп';
      if (!this.calibFileExists['sources.jpg'] || !this.sourceMatchesMicroscope) return 'Получите снимок шкалы для выбранного микроскопа';
      if (!this.calibSelectedDivisionPrice) return 'Укажите расстояние между соседними штрихами';
      return '';
    },
    isCalculateDisabled() { return !!this.calculateDisabledReason; },
    saveDisabledReason() {
      if (this.working) return 'Дождитесь завершения операции';
      if (!this.calibSelectedMicroscope) return 'Выберите микроскоп';
      if (!this.calibSelectedDivisionPrice) return 'Укажите расстояние между соседними штрихами';
      const n = parseFloat(this.calibCoefficient);
      if (!Number.isFinite(n) || n <= 0 || this.coefficientMicroscopeName !== this.calibSelectedMicroscope.name) return 'Получите снимок и рассчитайте масштаб для выбранного микроскопа';
      if (!this.calibName.trim()) return 'Введите название калибровки для сохранения';
      return '';
    },
    isSaveDisabled() { return !!this.saveDisabledReason; },
    scaleValue() {
      const n = parseFloat(this.calibCoefficient);
      const division = this.calibSelectedDivisionPrice?.value;
      return n > 0 && Number.isFinite(n) && division > 0 && this.coefficientMicroscopeName === this.calibSelectedMicroscope?.name
        ? (division / n).toLocaleString('ru-RU', {maximumFractionDigits:6}) : '';
    },
    fingerprint() {
      return JSON.stringify([this.calibName, this.calibSelectedMicroscope?.name,
        this.calibSelectedDivisionPrice?.name, this.calibCoefficient, this.$root.calibrationRevision]);
    },
    hasUnsavedChanges() {
      return this.savedFingerprint ? this.fingerprint !== this.savedFingerprint
        : !!(this.calibName.trim() || this.calibCoefficient || this.calibFileExists['sources.jpg']);
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
        this.coefficientMicroscopeName = '';
        this.sourceMicroscopeName = this.calibSelectedMicroscope?.name || '';
        this.successMsg = '';
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
      this.coefficientMicroscopeName = '';
      this.sourceMicroscopeName = result.microscope || this.calibSelectedMicroscope?.name || '';
      this.activeMicroscopeName = this.calibSelectedMicroscope?.name || '';
      this.successMsg = '';
      this.calibFileExists = {'sources.jpg':true,'contrasted.jpg':false,'contours.jpg':false,'calibrated.jpg':false};
      this.calibImages = {'sources.jpg':'','contrasted.jpg':'','contours.jpg':'','calibrated.jpg':''};
      this.calibCurrentView = 'sources.jpg';
      await this._loadImage('sources.jpg');
    },
    // ------------------------------------------------------------------
    // Сессия
    // ------------------------------------------------------------------
    clearSource() {
      this.calibCoefficient = '';
      this.calibDetection = null;
      this.sourceMicroscopeName = '';
      this.coefficientMicroscopeName = '';
      this.manualCoefficient = false;
      this.calibFileExists = {'sources.jpg':false,'contrasted.jpg':false,'contours.jpg':false,'calibrated.jpg':false};
      this.calibImages = {'sources.jpg':'','contrasted.jpg':'','contours.jpg':'','calibrated.jpg':''};
      this.calibCurrentView = 'sources.jpg';
      this.successMsg = '';
    },
    confirmDiscard() {
      return !this.hasUnsavedChanges || confirm('Есть несохранённые изменения калибровки. Продолжить без сохранения?');
    },
    async onMicroscopeChange() {
      const next = this.calibSelectedMicroscope;
      const previous = this.activeMicroscopeName || this.sourceMicroscopeName || this.coefficientMicroscopeName;
      if (previous && next?.name !== previous) {
        if ((this.calibFileExists['sources.jpg'] || this.calibCoefficient) && !confirm('Снимок и масштаб относятся к другому микроскопу. Очистить их для выбранного прибора?')) {
          this.calibSelectedMicroscope = this.$root.microscopes.find(m => m.name === previous) || null;
          return;
        }
        this.busy = true;
        try {
          const result = await api.newCalibration();
          if (!result.ok) {
            this.calibSelectedMicroscope = this.$root.microscopes.find(m => m.name === previous) || null;
            this.errorMsg = result.error; return;
          }
          this.$root.calibrationRevision = result.revision;
          this.calibId = 0;
          this.savedFingerprint = '';
          this.clearSource();
        } finally { this.busy = false; }
      } else if (this.coefficientMicroscopeName !== next?.name) {
        this.calibCoefficient = '';this.coefficientMicroscopeName = '';
      }
      this.activeMicroscopeName = next?.name || '';
      this.sourceMode = this.isDefaultMicroscope ? 'file' : 'camera';
      this.errorMsg = '';
    },
    onManualCoefficient() {
      this.coefficientMicroscopeName = this.calibSelectedMicroscope?.name || '';
      this.calibDetection = null;
      this.successMsg = '';
    },
    async createNewCalibration() {
      if (this.working || !this.confirmDiscard()) return;
      this.busy = true;
      try {
        const result = await api.newCalibration();
        if (!result.ok) { this.errorMsg = result.error; return; }
        this.$root.calibrationRevision = result.revision;
        this.calibId = 0;this.calibName = '';
        this.calibSelectedMicroscope = null;this.calibSelectedDivisionPrice = null;this.activeMicroscopeName = '';
        this.savedFingerprint = '';this.clearSource();this.errorMsg = '';
        this.isCalibLoadVisible = false;
      } finally { this.busy = false; }
    },

    // ------------------------------------------------------------------
    // Загрузка файла с диска
    // ------------------------------------------------------------------
    async handleFileSelect(event) {
      const file = event.target.files[0];
      if (!file || this.working || !this.calibSelectedMicroscope) return;
      this.busy = true;this.errorMsg = '';
      try {
        const b64 = await this._readAsBase64(file);
        const res = await api.uploadImage('sources.jpg', b64, 'calibration');
        if (res.ok) await this.onCaptured(res);
        else this.errorMsg = res.error || 'Ошибка загрузки файла.';
      } catch (error) { this.errorMsg = error.message || 'Не удалось прочитать файл'; }
      finally { this.busy = false;event.target.value = ''; }
    },

    _readAsBase64(file) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => resolve(e.target.result); // data URI
        reader.onerror = () => reject(new Error('Не удалось прочитать файл'));
        reader.readAsDataURL(file);
      });
    },

    // ------------------------------------------------------------------
    // Калибровка
    // ------------------------------------------------------------------
    async runCalibration() {
      if (this.isCalculateDisabled) { this.errorMsg = this.calculateDisabledReason; return; }
      const microscope = this.calibSelectedMicroscope.name;
      const revision = this.$root.calibrationRevision;
      this.busy = true;this.errorMsg = '';this.successMsg = '';
      this.calibCoefficient = '';this.calibDetection = null;this.coefficientMicroscopeName = '';
      try {
        const res = await api.executeCalibration();
        if (res.ok && res.revision === revision && revision === this.$root.calibrationRevision && microscope === this.calibSelectedMicroscope?.name) {
          this.calibCoefficient = parseFloat(res.coefficient).toFixed(3);
          this.coefficientMicroscopeName = microscope;
          if (res.marks_count) this.calibDetection = {count:res.marks_count,orientation:res.orientation};
          for (const fname of ['contrasted.jpg', 'contours.jpg', 'calibrated.jpg']) {
            this.calibFileExists[fname] = true;
            await this._loadImage(fname);
          }
          this.calibCurrentView = 'calibrated.jpg';
        } else this.errorMsg = res.error || 'Исходное изображение изменилось. Повторите калибровку.';
      } finally { this.busy = false; }
    },

    async saveCalibration() {
      if (this.isSaveDisabled) return;
      const fingerprint = this.fingerprint;
      this.saving = true;this.errorMsg = '';this.successMsg = '';
      try {
        const res = await api.saveCalibration({
          revision:this.$root.calibrationRevision, id:this.calibId, name:this.calibName,
          microscope:this.calibSelectedMicroscope.name,
          coefficient:parseFloat(this.calibCoefficient),division_price:this.calibSelectedDivisionPrice.name,
        });
        if (res.ok) {
          this.calibId = res.id;this.savedFingerprint = fingerprint;
          this.successMsg = 'Калибровка сохранена';
        } else this.errorMsg = res.error || 'Ошибка сохранения калибровки.';
      } finally { this.saving = false; }
    },

    // ------------------------------------------------------------------
    // Список калибровок
    // ------------------------------------------------------------------
    async toggleCalibLoadBlock() {
      if (this.working) return;
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
      if (!calib || this.working || !this.confirmDiscard()) return;
      this.busy = true;
      try {
        const res = await api.loadCalibration(calib.id);
        if (!res.ok) { this.errorMsg = 'Ошибка загрузки калибровки.'; return; }

        if (res.revision < this.$root.calibrationRevision) {
          this.errorMsg = 'Сессия калибровки изменилась. Откройте калибровку повторно.';return;
        }
        this.$root.calibrationRevision = res.revision;
        const c = res.calibration;
        this.calibId          = c.id;
        this.calibName        = c.name;
        this.calibCoefficient = c.coefficient;
        this.calibDetection = null;
        this.activeMicroscopeName = c.microscope;
        this.sourceMicroscopeName = c.microscope;
        this.coefficientMicroscopeName = c.microscope;
        this.manualCoefficient = false;
        this.calibSelectedMicroscope   = this.$root.microscopes.find(m => m.name === c.microscope) || null;
        this.calibSelectedDivisionPrice = this.$root.divisionPrices.find(p => p.name === c.division_price) || null;

        // Сбрасываем изображения и помечаем существующие файлы
        this.calibImages     = { 'sources.jpg': '', 'contrasted.jpg': '', 'contours.jpg': '', 'calibrated.jpg': '' };
        this.calibFileExists = { 'sources.jpg': false, 'contrasted.jpg': false, 'contours.jpg': false, 'calibrated.jpg': false };
        for (const fname of (res.files || [])) {
          if (fname in this.calibFileExists) {
            this.calibFileExists[fname] = true;
            await this._loadImage(fname);
          }
        }

        // Активируем лучший доступный файл
        const preferred = ['calibrated.jpg', 'sources.jpg'];
        this.calibCurrentView = preferred.find(f => this.calibFileExists[f]) || 'sources.jpg';

        this.sourceMode = this.isDefaultMicroscope ? 'file' : 'camera';
        this.savedFingerprint = this.fingerprint;
        this.successMsg = 'Сохранённая калибровка загружена';
        this.isCalibLoadVisible = false;
        this.selectedRow = null;
        this.errorMsg = '';
      } finally { this.busy = false; }
    },

    async deleteCalibration() {
      if (this.working || !this.selectedRow) return;
      const identifier = this.selectedRow.id;
      if (!confirm('Удалить калибровку?')) return;
      this.busy = true;
      try {
        const res = await api.deleteCalibration(identifier);
        if (res.ok) {
          if (res.active && res.revision >= this.$root.calibrationRevision) {
            this.calibId = 0;
            this.savedFingerprint = '';this.successMsg = '';
            this.$root.calibrationRevision = res.revision;
          }
          this.calibrations = this.calibrations.filter(c => c.id !== identifier);
          if (this.selectedRow?.id === identifier) this.selectedRow = null;
        } else this.errorMsg = res.error || 'Ошибка удаления калибровки.';
      } finally { this.busy = false; }
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
