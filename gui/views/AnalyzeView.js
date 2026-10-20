window.AnalyzeView = {
  template: `
    <div class="analysis-editor">
      <div class="workspace-heading">
        <h6 class="mb-0">Анализ серии снимков</h6>
        <div class="d-flex gap-2">
          <button class="btn btn-sm btn-outline-primary" :disabled="working" @click="createNewResearch">Новое исследование</button>
          <button class="btn btn-sm btn-outline-secondary" :disabled="working" @click="toggleResearchLoadBlock">Открыть сохранённое</button>
        </div>
      </div>
      <div v-if="isResearchLoadVisible" class="border rounded p-3 mb-2">
        <h6>Сохранённые исследования</h6>
        <div class="table-responsive">
          <table class="table table-sm table-hover">
            <thead><tr><th>Название</th><th>Сотрудник</th><th>Микроскоп</th><th>Дата</th></tr></thead>
            <tbody>
              <tr v-for="r in loadResearches" :key="r.id" :class="{'table-active':selectedResearchRow?.id === r.id}">
                <td><button class="btn btn-sm btn-link p-0" :disabled="working" @click="selectedResearchRow = r" @dblclick="doLoadResearch(r)">{{ r.name || 'Без названия' }}</button></td>
                <td>{{ r.employee }}</td><td>{{ r.microscope }}</td><td>{{ $root.formatDate(r.date) }}</td>
              </tr>
              <tr v-if="!loadResearches.length"><td colspan="4" class="text-muted">Сохранённых исследований пока нет</td></tr>
            </tbody>
          </table>
        </div>
        <div class="d-flex justify-content-end gap-2">
          <button class="btn btn-sm btn-outline-danger" :disabled="working || !selectedResearchRow" @click="deleteLoadResearch">Удалить</button>
          <button class="btn btn-sm btn-primary" :disabled="working || !selectedResearchRow" @click="doLoadResearch(selectedResearchRow)">Открыть</button>
          <button class="btn btn-sm btn-outline-secondary" :disabled="working" @click="toggleResearchLoadBlock">Вернуться</button>
        </div>
      </div>
      <div v-else>
        <div class="row g-2 mb-2">
          <div class="col-md-3"><label for="research-name" class="form-label">Название</label><input id="research-name" v-model="name" class="form-control" :disabled="working" placeholder="Название исследования"></div>
          <div class="col-md-2"><label for="research-employee" class="form-label">Сотрудник</label><input id="research-employee" v-model="employee" class="form-control" :disabled="working"></div>
          <div class="col-md-3">
            <label for="research-microscope" class="form-label">Микроскоп</label>
            <select id="research-microscope" v-model="selectedMicroscope" class="form-select" @change="onMicroscopeChange" :disabled="working">
              <option :value="null" disabled>Выберите прибор</option>
              <option v-for="m in $root.microscopes" :key="m.name" :value="m">{{ m.type === 'DEFAULT' ? 'Изображения с диска' : m.name }}</option>
            </select>
          </div>
          <div class="col-md-4">
            <label for="research-calibration" class="form-label">Калибровка</label>
            <select id="research-calibration" v-model="$root.analyzeSelectedCalibration" class="form-select" :disabled="isCalibrationSelectDisabled" @change="onCalibrationChange">
              <option :value="null" disabled>{{ calibrationPlaceholder }}</option>
              <option v-for="c in availableCalibrations" :key="c.id" :value="c">{{ c.name }}</option>
            </select>
          </div>
        </div>
        <div class="border rounded p-2 mb-2">
          <div class="d-flex flex-wrap align-items-center gap-2">
            <button class="btn btn-primary" :disabled="isAnalyzeButtonDisabled" @click="analyzeAllFiles">{{ analyzing ? 'Анализ…' : 'Анализировать серию' }}</button>
            <div class="small me-auto"><strong>Вся серия: {{ files.length }} снимков · {{ $root.results.length }} частиц</strong><div class="text-muted">{{ calibrationScale }}</div></div>
            <button class="btn btn-outline-primary" :disabled="!$root.results.length || working" @click="$root.currentTab = 'results'">Проверить результаты</button>
            <button class="btn btn-success" :disabled="isSaveButtonDisabled" @click="saveResearch">{{ saving ? 'Сохранение…' : 'Сохранить' }}</button>
          </div>
          <div class="small mt-1" :class="successMsg && !hasUnsavedChanges ? 'text-success' : 'text-muted'" role="status">{{ statusText }}</div>
        </div>
        <details class="analysis-settings mb-2">
          <summary class="small">Выделение частиц · {{ analysisModeLabel }}</summary>
          <div class="row g-2 mt-1">
            <div class="col-md-4">
              <label for="particle-mode" class="form-label">Частицы и фон</label>
              <select id="particle-mode" v-model="analysisOptions.mode" @change="onAnalysisOptionsChange" class="form-select form-select-sm" :disabled="working">
                <option value="auto">Автоматически</option><option value="light">Светлые частицы</option><option value="dark">Тёмные частицы</option><option value="color">Цветной фон</option>
              </select>
            </div>
            <div class="col-md-4">
              <label for="particle-min-area" class="form-label">Минимальная площадь, пикс²</label>
              <input id="particle-min-area" type="number" min="1" step="1" v-model.number="analysisOptions.min_area_px" @change="onAnalysisOptionsChange" class="form-control form-control-sm" :disabled="working">
              <div class="small text-muted">{{ minimumParticleHint }}</div>
            </div>
            <div class="col-md-4">
              <label class="form-check mt-md-4"><input type="checkbox" class="form-check-input" v-model="analysisOptions.split_touching" @change="onAnalysisOptionsChange" :disabled="working"> Разделять узкие соединения</label>
              <div class="small text-muted">Эвристика для соприкасающихся частиц. Сравните обводку до и после.</div>
            </div>
          </div>
          <div v-if="optionsError" class="small text-danger mt-1" role="alert">{{ optionsError }}</div>
          <div v-if="$root.results.length && !resultOptionsKnown" class="small text-muted mt-1">Настройки исходного анализа неизвестны. Выбранные настройки применятся при новом расчёте.</div>
        </details>
        <div class="row g-3 analysis-workspace">
          <div class="col-md-6 workspace-column">
            <div class="workspace-heading">
              <h6 class="mb-0">Получение снимков</h6>
              <select aria-label="Источник снимков" v-model="sourceMode" class="form-select form-select-sm workspace-view-select" :disabled="working || !selectedMicroscope">
                <option value="camera" :disabled="isDefaultMicroscope">Камера</option><option value="file">Загрузить файлы</option>
              </select>
            </div>
            <div v-if="sourceMode === 'file' || isDefaultMicroscope" class="mb-2">
              <input aria-label="Снимки для анализа" type="file" accept="image/*" multiple @change="handleFileSelect" class="form-control" :disabled="working || !selectedMicroscope">
              <div class="analysis-file-list border rounded p-2 mt-2">
                <div class="small text-muted mb-2">Добавляйте снимки с одинаковым увеличением. Выберите кадр для проверки справа.</div>
                <div class="analysis-file-grid"><button v-for="file in files" :key="file.name" class="btn btn-sm" :class="currentFile?.name === file.name ? 'btn-primary' : 'btn-outline-primary'" :disabled="working" @click="selectFile(file)">Кадр {{ file.name.split('.')[0] }}</button></div>
              </div>
            </div>
            <camera-panel v-else :microscope="selectedMicroscope" context="research"
                          :active="$root.currentTab === 'analyze' && !isResearchLoadVisible" :revision="$root.researchRevision"
                          :disabled="working" @capturing="capturePending = $event" @connected="refreshSession" @captured="onCaptured"></camera-panel>
            <p v-if="isAutomaticMicroscope" class="small text-muted mb-0">Снимки по кнопке доступны. Автоматическое перемещение образца ещё не подключено.</p>
            <div class="small text-muted">После изменения снимков повторите анализ всей серии.</div>
          </div>
          <div class="col-md-6 workspace-column">
            <div class="workspace-heading">
              <h6 class="mb-0">Проверка снимка</h6>
              <select aria-label="Кадр серии" v-model="currentFile" @change="selectFile(currentFile)" class="form-select form-select-sm workspace-view-select" :disabled="!files.length || working">
                <option v-if="!files.length" :value="null">Нет снимков</option>
                <option v-for="file in files" :key="file.name" :value="file">Кадр {{ file.name.split('.')[0] }}</option>
              </select>
            </div>
            <div class="d-flex align-items-center gap-2 mb-2">
              <select aria-label="Обработка снимка" v-model="selectedFolder" @change="changeFolder(selectedFolder)" class="form-select form-select-sm" :disabled="!currentFile || working">
                <option v-for="folder in folders" :key="folder" :value="folder" :disabled="!folderButtonStates[folder]">{{ folderNames[folder] }}</option>
              </select>
              <button class="btn btn-sm btn-outline-danger text-nowrap" :disabled="!currentFile || working" @click="deleteCurrentFile">Удалить кадр</button>
            </div>
            <button class="analysis-preview img-thumbnail d-flex align-items-center justify-content-center" :disabled="!currentImage" @click="openModal" aria-label="Открыть снимок крупно">
              <img v-if="currentImage" :src="currentImage" alt="Выбранный снимок серии" class="workspace-image">
              <span v-else class="small text-muted">{{ imageLoading ? 'Загрузка…' : 'Снимите кадр или загрузите файл' }}</span>
            </button>
            <div v-if="selectedDiagnostic" class="small text-muted mt-1" role="status">
              {{ methodLabel(selectedDiagnostic.method) }} · найдено: {{ selectedDiagnostic.count }} · на краю: {{ selectedDiagnostic.excluded_border }} · ниже порога: {{ selectedDiagnostic.excluded_small }}<span v-if="selectedDiagnostic.split_count"> · разделений: {{ selectedDiagnostic.split_count }}</span>
            </div>
          </div>
        </div>
      </div>
      <div v-if="errorMsg" class="alert alert-danger py-2 mt-2" role="alert">{{ errorMsg }} <button v-if="calibrationError" class="btn btn-sm btn-outline-danger ms-2" :disabled="working" @click="fetchCalibrations">Повторить загрузку калибровок</button></div>
      <teleport to="body"><div class="modal fade" id="analyzeImageModal" tabindex="-1" aria-hidden="true"><div class="modal-dialog modal-fullscreen"><div class="modal-content bg-dark"><div class="modal-body d-flex align-items-center justify-content-center" @click="closeModal"><img v-if="currentImage" :src="currentImage" class="workspace-image" alt="Снимок серии крупно"></div></div></div></div></teleport>
    </div>
  `,
  data() {
    return {sessionSyncing:false,refreshGeneration:0,syncGeneration:0,imageRequest:0,
      analysisOptions:{mode:'auto',min_area_px:100,split_touching:false},appliedOptions:null,analysisDiagnostics:[],resultOptionsKnown:false,
      analysisVersion:0,calibrationRequest:0,calibrationsLoading:false,calibrationError:false,researchId:0,name:'',employee:'',selectedMicroscope:null,calibrations:[],
      activeMicroscopeName:'',sourceMicroscopeName:'',sourceMode:'camera',capturePending:false,
      isResearchLoadVisible:false,loadResearches:[],selectedResearchRow:null,
      files:[],currentFile:null,lastUsedIndex:0,
      folders:['sources','contrasted','contours','analyzed'],
      folderNames:{sources:'Исходный снимок',contrasted:'Контраст',contours:'Контуры',analyzed:'Результат распознавания'},
      selectedFolder:'sources',currentImage:'',imageLoading:false,imageCache:{},
      busy:false,analyzing:false,saving:false,uploading:false,errorMsg:'',successMsg:'',savedFingerprint:'',needsAnalysis:false};
  },
  computed: {
    working() { return this.busy || this.calibrationsLoading || this.saving || this.uploading || this.capturePending || this.sessionSyncing || !!this.$root.researchPending; },
    analysisModeLabel() { return {auto:'Автоматически',light:'Светлые частицы',dark:'Тёмные частицы',color:'Цветной фон'}[this.analysisOptions.mode] || 'Выберите режим'; },
    optionsError() {
      const options = this.analysisOptions;
      if (!['auto','light','dark','color'].includes(options.mode)) return 'Выберите режим выделения частиц';
      if (!Number.isFinite(options.min_area_px) || options.min_area_px < 1) return 'Минимальная площадь должна быть не меньше 1 пикселя²';
      if (typeof options.split_touching !== 'boolean') return 'Проверьте настройку разделения частиц';
      return '';
    },
    minimumParticleHint() {
      const c = this.$root.analyzeSelectedCalibration;
      const division = (this.$root.divisionPrices || []).find(p => p.name === c?.division_price);
      if (!division || !(c.coefficient > 0) || this.optionsError) return 'Мелкие области ниже этого порога исключаются';
      const diameter = Math.sqrt(4 * this.analysisOptions.min_area_px / Math.PI) * division.value / c.coefficient;
      return 'Эквивалентный диаметр порога ≈ ' + diameter.toLocaleString('ru-RU',{maximumFractionDigits:2}) + ' мкм';
    },
    selectedDiagnostic() { return this.analysisDiagnostics.find(d => d.filename === this.currentFile?.name) || null; },
    availableCalibrations() { return this.selectedMicroscope ? this.calibrations.filter(c => c.microscope === this.selectedMicroscope.name) : []; },
    isCalibrationSelectDisabled() { return !this.selectedMicroscope || this.working; },
    calibrationPlaceholder() { return !this.selectedMicroscope ? 'Сначала выберите прибор' : (!this.availableCalibrations.length ? 'Нет калибровок для прибора' : 'Выберите калибровку'); },
    analysisDisabledReason() {
      if (this.working) return 'Дождитесь завершения операции';
      if (this.optionsError) return this.optionsError;
      if (this.calibrationError) return 'Не удалось обновить калибровки. Повторите загрузку';
      if (!this.selectedMicroscope) return 'Выберите микроскоп';
      if (!this.files.length) return 'Добавьте снимки в серию';
      if (this.sourceMicroscopeName !== this.selectedMicroscope.name) return 'Снимки относятся к другому прибору. Начните новую серию';
      const c = this.$root.analyzeSelectedCalibration;
      if (!c || c.microscope !== this.selectedMicroscope.name) return 'Выберите калибровку для этого микроскопа';
      return '';
    },
    isAnalyzeButtonDisabled() { return !!this.analysisDisabledReason; },
    saveDisabledReason() {
      if (this.working) return 'Дождитесь завершения операции';
      if (this.optionsError) return this.optionsError;
      if (this.calibrationError) return 'Не удалось обновить калибровки. Повторите загрузку';
      if (this.appliedOptions && !this.sameOptions(this.analysisOptions,this.appliedOptions)) return 'Настройки изменились. Повторите анализ';
      if (!this.$root.results.length || this.needsAnalysis) return 'Выполните анализ серии';
      if (!this.name.trim()) return 'Введите название исследования';
      if (!this.selectedMicroscope || this.sourceMicroscopeName !== this.selectedMicroscope.name) return 'Проверьте выбранный микроскоп';
      if (!this.$root.analyzeSelectedCalibration) return 'Выберите калибровку';
      return '';
    },
    isSaveButtonDisabled() { return !!this.saveDisabledReason; },
    calibrationScale() {
      if (this.$root.results.length && !this.$root.researchContext?.calibration?.coefficient) return 'Измерения из сохранённого исследования';
      const c = this.$root.results.length ? this.$root.researchContext.calibration : this.$root.analyzeSelectedCalibration;
      const division = (this.$root.divisionPrices || []).find(p => p.name === c?.division_price);
      return division && c.coefficient > 0 ? (division.value / c.coefficient).toLocaleString('ru-RU',{maximumFractionDigits:6}) + ' мкм/пикс' : 'Укажите калибровку с тем же увеличением, что и снимки';
    },
    fingerprint() { const c = this.$root.analyzeSelectedCalibration;return JSON.stringify([this.name,this.employee,this.selectedMicroscope?.name,c?.id,c?.coefficient,c?.division_price,this.$root.researchRevision,this.analysisVersion,this.analysisOptions,this.files.map(f => f.name)]); },
    hasUnsavedChanges() { return this.savedFingerprint ? this.fingerprint !== this.savedFingerprint : !!(this.name.trim() || this.employee.trim() || this.files.length || this.$root.results.length); },
    statusText() { return this.successMsg && !this.hasUnsavedChanges ? this.successMsg : (this.analysisDisabledReason || (this.needsAnalysis ? 'Снимки или калибровка изменились. Нужен повторный анализ' : (this.saveDisabledReason || (this.hasUnsavedChanges ? 'Есть несохранённые изменения' : '')))); },
    editorStatus() { return {working:this.working,unsaved:this.hasUnsavedChanges,saved:!!this.savedFingerprint && !this.hasUnsavedChanges,fileCount:this.files.length,name:this.name,employee:this.employee,saveDisabled:this.isSaveButtonDisabled,saveReason:this.saveDisabledReason,error:this.errorMsg,status:this.statusText}; },
    folderButtonStates() { const ready = this.$root.results.length > 0 && !this.needsAnalysis;return {sources:this.files.length > 0,contrasted:ready,contours:ready,analyzed:ready}; },
    isDefaultMicroscope() { return !this.selectedMicroscope || this.selectedMicroscope.type === 'DEFAULT'; },
    isManualMicroscope() { return this.selectedMicroscope?.type === 'MANUAL'; },
    isAutomaticMicroscope() { return this.selectedMicroscope?.type === 'AUTOMATIC'; },
    canShowCamera() { return !this.isDefaultMicroscope; },
  },
  watch: {
    editorStatus: {handler(value) { this.$root.researchState = value; },immediate:true},
    '$root.analyzeResetKey'() { this.syncFromRoot(this.$root.selectedResearch); },
    async '$root.currentTab'(tab) { if (tab === 'analyze') { await this.fetchCalibrations();await this.refreshSession(); } },
    '$root.microscopes'(items) { if (this.selectedMicroscope) this.selectedMicroscope = items.find(m => m.name === this.selectedMicroscope.name) || null; },
  },
  async mounted() { this.sessionSyncing = true;try { await this.fetchCalibrations();await this.syncFromRoot(this.$root.selectedResearch); } finally { this.sessionSyncing = false; } },
  methods: {
    confirmDiscard() { return !this.hasUnsavedChanges || confirm('Есть несохранённые изменения исследования. Продолжить без сохранения?'); },
    clearResults() { this.$root.results = [];this.$root.averages = {};this.$root.researchContext = null;this.imageCache = {};this.successMsg = '';this.analysisDiagnostics = [];this.appliedOptions = null;this.resultOptionsKnown = false;this.needsAnalysis = this.files.length > 0; },
    clearFrames() { ++this.imageRequest;this.files = [];this.currentFile = null;this.currentImage = '';this.imageLoading = false;this.lastUsedIndex = 0;this.sourceMicroscopeName = '';this.selectedFolder = 'sources';this.clearResults(); },
    async refreshSession() {
      const generation = ++this.refreshGeneration;this.sessionSyncing = true;
      try {
        const result = await api.listImages('research');
        if (generation !== this.refreshGeneration || (result.ok && result.revision < this.$root.researchRevision)) return;
        if (!result.ok) { this.errorMsg = result.error;return; }
        const changed = result.revision > this.$root.researchRevision;
        this.$root.researchRevision = result.revision;
        if (changed) { this.clearResults();this.selectedFolder = 'sources';this.currentImage = ''; }
        const currentName = this.currentFile?.name;
        this.files = result.files.map(name => ({name}));this.lastUsedIndex = Math.max(0,...this.files.map(f => parseInt(f.name) || 0));
        this.currentFile = this.files.find(f => f.name === currentName) || this.files[0] || null;
        if (this.currentFile) await this.loadImage(this.currentFile.name,this.selectedFolder);
        else this.currentImage = '';
      } finally { if (generation === this.refreshGeneration) this.sessionSyncing = false; }
    },
    async onMicroscopeChange() {
      const next = this.selectedMicroscope;
      const previous = this.activeMicroscopeName || this.sourceMicroscopeName;
      if (previous && previous !== next?.name) {
        if ((this.files.length || this.$root.results.length) && !confirm('Смена микроскопа очистит снимки и результаты серии. Продолжить?')) {
          this.selectedMicroscope = this.$root.microscopes.find(m => m.name === previous) || null;return;
        }
        this.busy = true;
        try {
          const result = await api.newResearch();
          if (!result.ok) { this.selectedMicroscope = this.$root.microscopes.find(m => m.name === previous) || null;this.errorMsg = result.error;return; }
          this.$root.researchRevision = result.revision;this.researchId = 0;this.$root.selectedResearch = null;
          this.savedFingerprint = '';this.clearFrames();
        } finally { this.busy = false; }
      }
      this.activeMicroscopeName = next?.name || '';this.$root.analyzeSelectedCalibration = null;
      this.sourceMode = this.isDefaultMicroscope ? 'file' : 'camera';this.errorMsg = '';
    },
    async onAnalysisOptionsChange() { await this.onCalibrationChange(); },
    methodLabel(method) { return {lab_background:'По цвету фона',gray_light:'Светлые частицы',gray_dark:'Тёмные частицы',gray_corrected:'С коррекцией освещения'}[method] || 'Пороговое выделение'; },
    sameOptions(a,b) { return !!a && !!b && ['mode','min_area_px','split_touching'].every(key => a[key] === b[key]); },
    async onCalibrationChange() {
      this.clearResults();this.selectedFolder = 'sources';this.currentImage = '';this.imageLoading = false;++this.imageRequest;
      await this.$root.invalidateResearch();
      if (this.currentFile) await this.loadImage(this.currentFile.name,'sources');
    },
    async onCaptured(result) {
      if (result.revision <= this.$root.researchRevision) return;
      this.$root.researchRevision = result.revision;this.clearResults();
      const microscope = result.microscope || this.selectedMicroscope?.name || '';
      this.sourceMicroscopeName = this.sourceMicroscopeName && this.sourceMicroscopeName !== microscope ? '__mixed__' : microscope;
      this.activeMicroscopeName = this.selectedMicroscope?.name || '';
      const file = this.files.find(f => f.name === result.filename) || {name:result.filename};
      if (!this.files.includes(file)) this.files.push(file);
      this.lastUsedIndex = Math.max(this.lastUsedIndex,parseInt(file.name) || 0);this.needsAnalysis = true;
      this.selectedFolder = 'sources';this.currentFile = file;await this.loadImage(file.name,'sources');
    },
    async createNewResearch() {
      if (this.working || !this.confirmDiscard()) return false;
      this.busy = true;this.errorMsg = '';
      try {
        const result = await api.newResearch();
        if (!result.ok) { this.errorMsg = result.error || 'Ошибка создания исследования';return false; }
        this.$root.resetResearch(result);this.researchId = 0;this.name = '';this.employee = '';this.selectedMicroscope = null;
        this.activeMicroscopeName = '';this.savedFingerprint = '';this.clearFrames();this.isResearchLoadVisible = false;return true;
      } finally { this.busy = false; }
    },
    async toggleResearchLoadBlock() {
      if (this.working) return;
      if (!this.isResearchLoadVisible) await this.fetchLoadResearches();
      this.isResearchLoadVisible = !this.isResearchLoadVisible;this.selectedResearchRow = null;
    },
    async fetchLoadResearches() { const result = await api.getResearches();if (result.ok) this.loadResearches = result.researches;else this.errorMsg = result.error; },
    async doLoadResearch(research) {
      if (!research || this.working || !this.confirmDiscard()) return false;
      this.busy = true;this.errorMsg = '';
      try {
        const result = await api.loadResearch(research.id);
        if (!result.ok) { this.errorMsg = result.error || 'Не удалось открыть исследование';return false; }
        if (result.revision < this.$root.researchRevision) { this.errorMsg = 'Исследование изменилось. Откройте его повторно';return false; }
        this.$root.researchRevision = result.revision;this.$root.selectedResearch = result.research;
        this.$root.results = result.research.contours || [];
        this.$root.averages = Object.fromEntries(['perimeter','area','width','length','dek'].map(key => [key,result.research['average_' + key]]));
        this.$root.analyzeSelectedCalibration = null;
        await this.fetchCalibrations();await this.syncFromRoot(result.research);
        this.isResearchLoadVisible = false;this.selectedResearchRow = null;return true;
      } finally { this.busy = false; }
    },
    async deleteResearch(identifier) {
      if (this.working || !confirm('Удалить исследование? Это действие необратимо.')) return false;
      this.busy = true;
      try {
        const result = await api.deleteResearch(identifier);
        if (!result.ok) { this.errorMsg = result.error || 'Не удалось удалить исследование';return false; }
        this.$root.onResearchDeleted(identifier,result);
        this.loadResearches = this.loadResearches.filter(r => r.id !== identifier);
        if (this.selectedResearchRow?.id === identifier) this.selectedResearchRow = null;
        if (result.active) { this.researchId = 0;this.savedFingerprint = '';this.successMsg = ''; }
        return true;
      } finally { this.busy = false; }
    },
    async deleteLoadResearch() { if (this.selectedResearchRow) return this.deleteResearch(this.selectedResearchRow.id);return false; },
    async syncFromRoot(research) {
      const generation = ++this.syncGeneration;this.sessionSyncing = true;
      try {
        if (research) {
          this.researchId = research.id || 0;this.name = research.name || '';this.employee = research.employee || '';
          this.selectedMicroscope = this.$root.microscopes.find(m => m.name === research.microscope) || null;
          this.activeMicroscopeName = research.microscope;this.sourceMicroscopeName = research.microscope;
          this.analysisOptions = research.analysis_options ? {...research.analysis_options} : {mode:'auto',min_area_px:100,split_touching:false};
          this.appliedOptions = {...this.analysisOptions};this.resultOptionsKnown = !!research.analysis_options;
          this.analysisDiagnostics = Array.isArray(research.analysis_diagnostics) ? research.analysis_diagnostics : [];
          this.$root.analyzeSelectedCalibration = this.calibrations.find(c => c.id === research.calibration_id) || null;
        } else { this.researchId = 0;this.name = '';this.employee = '';this.selectedMicroscope = null;this.activeMicroscopeName = '';this.sourceMicroscopeName = ''; }
        this.sourceMode = this.isDefaultMicroscope ? 'file' : 'camera';this.imageCache = {};this.currentImage = '';this.files = [];this.currentFile = null;++this.imageRequest;
        const result = await api.listImages('research');
        if (generation !== this.syncGeneration || (result.ok && result.revision < this.$root.researchRevision)) return;
        if (!result.ok) { this.errorMsg = result.error;return; }
        this.$root.researchRevision = result.revision;this.files = result.files.map(name => ({name}));
        this.lastUsedIndex = Math.max(0,...this.files.map(f => parseInt(f.name) || 0));
        this.needsAnalysis = !this.$root.results.length && this.files.length > 0;this.selectedFolder = this.$root.results.length ? 'analyzed' : 'sources';
        this.currentFile = this.files[0] || null;
        if (this.currentFile) await this.loadImage(this.currentFile.name,this.selectedFolder);
        if (generation !== this.syncGeneration) return;
        if (research) {
          const c = this.$root.analyzeSelectedCalibration;
          this.$root.researchContext = {microscope:research.microscope,calibration:c ? {id:c.id,name:c.name} : null,fileCount:this.files.length,analysisOptions:research.analysis_options || null,diagnostics:this.analysisDiagnostics};
          this.savedFingerprint = research.id ? this.fingerprint : '';this.successMsg = research.id ? 'Сохранённое исследование открыто' : '';
        } else { this.savedFingerprint = '';this.successMsg = '';this.$root.researchContext = null; }
      } finally { if (generation === this.syncGeneration) this.sessionSyncing = false; }
    },
    async fetchCalibrations() {
      const request = ++this.calibrationRequest;this.calibrationsLoading = true;
      try {
        const result = await api.getCalibrations();
        if (request !== this.calibrationRequest) return;
        if (!result.ok) { this.errorMsg = result.error || 'Калибровки недоступны';this.calibrationError = true;return; }
        this.calibrationError = false;this.errorMsg = '';this.calibrations = result.calibrations;
        const previous = this.$root.analyzeSelectedCalibration;
        if (previous) {
          const current = this.calibrations.find(c => c.id === previous.id) || null;
          const changed = !current || current.coefficient !== previous.coefficient || current.division_price !== previous.division_price || current.microscope !== previous.microscope;
          this.$root.analyzeSelectedCalibration = current;
          if (changed && this.$root.results.length) await this.onCalibrationChange();
        }
      } finally { if (request === this.calibrationRequest) this.calibrationsLoading = false; }
    },
    async handleFileSelect(event) {
      const selected = Array.from(event.target.files || []);
      if (!selected.length || this.working || !this.selectedMicroscope) return;
      const microscope = this.selectedMicroscope.name;this.uploading = true;this.errorMsg = '';
      try {
        for (const file of selected) {
          const data = await this._readAsBase64(file);
          const result = await api.uploadImage(String(++this.lastUsedIndex) + '.jpg',data,'research');
          if (result.ok) await this.onCaptured({...result,microscope});
          else { this.errorMsg = result.error || 'Ошибка загрузки снимка';break; }
        }
      } catch (error) { this.errorMsg = error.message || 'Не удалось прочитать снимок'; }
      finally { this.uploading = false;event.target.value = ''; }
    },
    async selectFile(file) { if (!file) return;this.currentFile = file;await this.loadImage(file.name,this.selectedFolder); },
    async changeFolder(folder) { if (!this.folderButtonStates[folder]) return;this.selectedFolder = folder;if (this.currentFile) await this.loadImage(this.currentFile.name,folder); },
    async deleteCurrentFile() {
      if (!this.currentFile || this.working) return;
      const filename = this.currentFile.name;this.busy = true;this.errorMsg = '';
      try {
        const result = await api.deleteImage(filename,'research');
        if (!result.ok) { this.errorMsg = result.error || 'Не удалось удалить кадр';return; }
        this.$root.researchRevision = result.revision;this.clearResults();this.selectedFolder = 'sources';
        const index = this.files.findIndex(f => f.name === filename);this.files = this.files.filter(f => f.name !== filename);
        this.currentFile = this.files.find(f => f.name === this.currentFile?.name) || this.files[Math.min(Math.max(index,0),this.files.length-1)] || null;
        ++this.imageRequest;this.currentImage = '';if (this.currentFile) await this.loadImage(this.currentFile.name,'sources');
        this.needsAnalysis = this.files.length > 0;
      } finally { this.busy = false; }
    },
    async loadImage(filename,folder) {
      const request = ++this.imageRequest;if (!filename) return;
      if (this.imageCache[filename]?.[folder]) { this.currentImage = this.imageCache[filename][folder];this.imageLoading = false;return; }
      this.imageLoading = true;this.currentImage = '';const revision = this.$root.researchRevision;
      const result = await api.getImage(filename,folder,'research');
      if (request !== this.imageRequest || revision !== this.$root.researchRevision) return;
      this.imageLoading = false;
      if (this.currentFile?.name !== filename || this.selectedFolder !== folder) return;
      if (result.ok && result.data) { if (!this.imageCache[filename]) this.imageCache[filename] = {};this.imageCache[filename][folder] = result.data;this.currentImage = result.data; }
    },
    _readAsBase64(file) { return new Promise((resolve,reject) => { const reader = new FileReader();reader.onload = e => resolve(e.target.result);reader.onerror = () => reject(new Error('Не удалось прочитать файл'));reader.readAsDataURL(file); }); },
    sameCalibration(a,b) { return !!a && !!b && ['id','microscope','coefficient','division_price'].every(key => a[key] === b[key]); },
    async analyzeAllFiles() {
      if (this.isAnalyzeButtonDisabled) { this.errorMsg = this.analysisDisabledReason;return; }
      const revision = this.$root.researchRevision,calibration = {...this.$root.analyzeSelectedCalibration},microscope = this.selectedMicroscope.name;
      const options = {...this.analysisOptions};
      this.busy = true;this.analyzing = true;this.errorMsg = '';this.clearResults();
      this.selectedFolder = 'sources';this.currentImage = '';this.imageLoading = false;++this.imageRequest;
      try {
        const result = await api.executeResearch(calibration.id,options);
        if (!result.ok || result.revision !== revision || revision !== this.$root.researchRevision || microscope !== this.selectedMicroscope?.name || !this.sameCalibration(calibration,this.$root.analyzeSelectedCalibration) || !this.sameOptions(options,this.analysisOptions)) { this.errorMsg = result.error || 'Снимки или настройки изменились. Повторите анализ';if (this.currentFile) await this.loadImage(this.currentFile.name,'sources');return; }
        this.$root.results = result.contours;this.$root.averages = result.averages;this.needsAnalysis = false;this.analysisVersion++;
        this.$root.selectedResearch = {id:this.researchId,name:this.name,employee:this.employee,microscope,calibration_id:calibration.id,date:new Date().toISOString()};
        this.appliedOptions = {...(result.analysis_options || options)};this.resultOptionsKnown = true;
        this.analysisDiagnostics = Array.isArray(result.diagnostics) ? result.diagnostics : [];
        this.$root.researchContext = {microscope,calibration,fileCount:this.files.length,revision,analysisOptions:this.appliedOptions,diagnostics:this.analysisDiagnostics};
        this.imageCache = {};this.selectedFolder = 'analyzed';if (this.currentFile) await this.loadImage(this.currentFile.name,'analyzed');
      } finally { this.busy = false;this.analyzing = false; }
    },
    async saveResearch() {
      if (this.isSaveButtonDisabled) return false;
      const revision = this.$root.researchRevision;this.saving = true;this.errorMsg = '';this.successMsg = '';
      try {
        const metadata = {name:this.name.trim(),employee:this.employee.trim(),microscope:this.selectedMicroscope.name,calibration_id:this.$root.analyzeSelectedCalibration.id};
        const result = await api.saveResearch({revision,id:this.researchId,...metadata});
        if (!result.ok) { this.errorMsg = result.error || 'Не удалось сохранить исследование';return false; }
        this.researchId = result.id;
        if (revision === this.$root.researchRevision) {
          this.name = metadata.name;this.employee = metadata.employee;
          this.$root.selectedResearch = {...this.$root.selectedResearch,...metadata,id:result.id};
          this.savedFingerprint = this.fingerprint;this.successMsg = 'Исследование сохранено';
        }
        return true;
      } finally { this.saving = false; }
    },
    openModal() { if (this.currentImage) new bootstrap.Modal(document.getElementById('analyzeImageModal')).show(); },
    closeModal() { bootstrap.Modal.getInstance(document.getElementById('analyzeImageModal'))?.hide(); },
  },
};
