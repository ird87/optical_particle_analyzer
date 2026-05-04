window.AnalyzeView = {
  template: `
    <div>

      <!-- Кнопки Новое / Загрузить -->
      <div v-if="!isResearchLoadVisible" class="col-md-4 d-flex justify-content-between mt-2 mb-2">
        <button class="btn flex-fill btn-primary me-1" @click="createNewResearch">Новое</button>
        <button class="btn flex-fill btn-secondary ms-1" @click="toggleResearchLoadBlock">Загрузить</button>
      </div>

      <!-- Блок загрузки исследования -->
      <div v-if="isResearchLoadVisible" class="border p-3 mb-3">
        <h6>Загрузка исследования</h6>
        <table class="table table-bordered table-sm table-hover" style="cursor:pointer;">
          <thead>
            <tr>
              <th>#</th><th>Название</th><th>Сотрудник</th><th>Микроскоп</th><th>Дата</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in loadResearches" :key="r.id"
                :class="{ 'table-active': selectedResearchRow && selectedResearchRow.id === r.id }"
                @click="selectedResearchRow = r"
                @dblclick="doLoadResearch(r)">
              <td>{{ r.id }}</td>
              <td>{{ r.name }}</td>
              <td>{{ r.employee }}</td>
              <td>{{ r.microscope }}</td>
              <td>{{ $root.formatDate(r.date) }}</td>
            </tr>
          </tbody>
        </table>
        <div class="d-flex col-md-6 justify-content-end mt-2 ms-auto">
          <button class="btn flex-fill btn-danger me-1"
                  :disabled="!selectedResearchRow" @click="deleteLoadResearch">Удалить</button>
          <button class="btn flex-fill btn-primary me-1"
                  :disabled="!selectedResearchRow" @click="doLoadResearch(selectedResearchRow)">Загрузить</button>
          <button class="btn flex-fill btn-secondary" @click="toggleResearchLoadBlock">Отменить</button>
        </div>
      </div>

      <!-- Форма исследования -->
      <div v-if="!isResearchLoadVisible" class="border p-2 pb-0 mb-2">
        <div class="row mb-2">
          <div class="col-md-9">
            <label class="form-label">Название:</label>
            <input type="text" v-model="name" class="form-control">
          </div>
          <div class="col-md-3">
            <label class="form-label">Сотрудник:</label>
            <input type="text" v-model="employee" class="form-control">
          </div>
        </div>
        <div class="row mb-3">
          <div class="col-md-6">
            <label class="form-label">Микроскоп:</label>
            <select v-model="selectedMicroscope" class="form-select">
              <option :value="null" disabled>Выберите микроскоп</option>
              <option v-for="m in $root.microscopes" :key="m.name" :value="m">{{ m.name }}</option>
            </select>
          </div>
          <div class="col-md-6">
            <label class="form-label">Калибровка:</label>
            <select v-model="$root.analyzeSelectedCalibration" class="form-select"
                    :disabled="isCalibrationSelectDisabled">
              <option :value="null" disabled>{{ calibrationPlaceholder }}</option>
              <option v-for="c in availableCalibrations" :key="c.id" :value="c">
                {{ c.name }} (k={{ c.coefficient }})
              </option>
            </select>
          </div>
        </div>
      </div>

      <!-- Рабочая область -->
      <div v-if="!isResearchLoadVisible" class="border p-3 pb-0">
        <div class="row">

          <!-- Список файлов -->
          <div class="col-md-3">
            <h6>Список файлов:</h6>
            <ul class="list-group text-center mb-3">
              <li v-for="file in files" :key="file.name"
                  class="list-group-item"
                  :class="{ active: file === currentFile }"
                  style="cursor:pointer;user-select:none;"
                  @click="selectFile(file)">
                {{ file.name.split('.')[0] }}
              </li>
            </ul>
            <div class="d-flex mb-3">
              <button class="btn flex-fill btn-danger me-1"
                      :disabled="!currentFile" @click="deleteCurrentFile">Удалить</button>
              <button class="btn flex-fill btn-success ms-1"
                      :disabled="isAnalyzeButtonDisabled" @click="analyzeAllFiles">
                {{ busy ? 'Анализ...' : 'Анализировать' }}
              </button>
            </div>
          </div>

          <!-- Превью -->
          <div class="col-md-4 d-flex flex-column align-items-center">
            <h6 class="text-center">Превью изображения:</h6>

            <!-- Переключатели папок -->
            <div class="btn-group mb-3" style="width:400px;">
              <button v-for="folder in folders" :key="folder"
                      class="btn btn-outline-primary"
                      :class="{ active: folder === selectedFolder }"
                      :disabled="!folderButtonStates[folder]"
                      @click="changeFolder(folder)">
                {{ folderNames[folder] }}
              </button>
            </div>

            <!-- Картинка -->
            <div class="img-thumbnail d-flex justify-content-center align-items-center mb-3"
                 style="width:400px;height:386px;background:#f8f9fa;cursor:pointer;"
                 @click="openModal">
              <img v-if="currentImage" :src="currentImage"
                   style="max-width:100%;max-height:100%;object-fit:contain;">
              <div v-else-if="imageLoading" class="text-muted small">Загрузка...</div>
              <span v-else class="text-muted">Нет изображения</span>
            </div>

            <!-- Загрузка файлов с диска -->
            <div class="mb-3" style="width:400px;" v-if="isDefaultMicroscope">
              <input type="file" accept="image/*" multiple @change="handleFileSelect" class="form-control">
            </div>
            <!-- Кнопки для подключённого микроскопа -->
            <div class="d-flex mb-3" style="width:400px;" v-if="!isDefaultMicroscope">
              <button class="btn btn-info flex-fill me-1" v-if="canShowCamera">Камера</button>
              <button class="btn btn-success flex-fill mx-1" v-if="isAutomaticMicroscope">Старт</button>
              <button class="btn btn-primary flex-fill ms-1" v-if="isManualMicroscope">Снимок</button>
            </div>
          </div>

          <!-- Результаты -->
          <div class="col-md-5">
            <h6>Результаты анализа:</h6>
            <div v-if="$root.results.length > 0">
              <div style="max-height:265px;overflow-y:auto;">
                <table class="table table-sm table-bordered">
                  <thead class="table-light">
                    <tr>
                      <th>№</th><th>Периметр</th><th>Площадь</th>
                      <th>Ширина</th><th>Длина</th><th>ДЭК</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="r in $root.results" :key="r.contour_number">
                      <td>{{ r.contour_number }}</td>
                      <td>{{ r.perimeter.toFixed(2) }}</td>
                      <td>{{ r.area.toFixed(2) }}</td>
                      <td>{{ r.width.toFixed(2) }}</td>
                      <td>{{ r.length.toFixed(2) }}</td>
                      <td>{{ r.dek.toFixed(2) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <table class="table table-sm table-bordered mt-2">
                <tbody>
                  <tr><td>Средний периметр</td><td>{{ $root.averages.perimeter?.toFixed(2) }}</td></tr>
                  <tr><td>Средняя площадь</td><td>{{ $root.averages.area?.toFixed(2) }}</td></tr>
                  <tr><td>Средняя ширина</td><td>{{ $root.averages.width?.toFixed(2) }}</td></tr>
                  <tr><td>Средняя длина</td><td>{{ $root.averages.length?.toFixed(2) }}</td></tr>
                  <tr><td>Средний ДЭК</td><td>{{ $root.averages.dek?.toFixed(2) }}</td></tr>
                </tbody>
              </table>
            </div>
            <p v-else class="text-muted">Результаты пока отсутствуют.</p>
            <button class="btn btn-primary mb-3" :disabled="isSaveButtonDisabled" @click="saveResearch">
              Сохранить
            </button>
          </div>

        </div>
      </div>

      <div v-if="errorMsg" class="alert alert-danger mt-2">{{ errorMsg }}</div>

      <!-- Полноэкранный просмотр -->
      <teleport to="body">
        <div class="modal fade" id="analyzeImageModal" tabindex="-1" aria-hidden="true">
          <div class="modal-dialog modal-fullscreen">
            <div class="modal-content bg-dark">
              <div class="modal-body d-flex justify-content-center align-items-center"
                   @click="closeModal" style="cursor:pointer;">
                <img v-if="currentImage" :src="currentImage"
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
      researchId:        0,
      name:              '',
      employee:          '',
      selectedMicroscope: null,
      calibrations:      [],

      isResearchLoadVisible: false,
      loadResearches:        [],
      selectedResearchRow:   null,

      files:             [],
      currentFile:       null,
      lastUsedIndex:     0,

      folders:    ['sources', 'contrasted', 'contours', 'analyzed'],
      folderNames: { sources: 'Исходные', contrasted: 'Контраст', contours: 'Контуры', analyzed: 'Результат' },
      selectedFolder: 'sources',

      currentImage:  '',
      imageLoading:  false,
      imageCache:    {},  // { 'filename': { 'folder': 'data:image/jpeg;base64,...' } }

      busy:     false,
      errorMsg: '',
    };
  },

  computed: {
    availableCalibrations() {
      if (!this.selectedMicroscope) return [];
      return this.calibrations.filter(c => c.microscope === this.selectedMicroscope.name);
    },
    isCalibrationSelectDisabled() {
      return !this.selectedMicroscope;
    },
    calibrationPlaceholder() {
      if (!this.selectedMicroscope) return 'Сначала выберите микроскоп';
      if (this.availableCalibrations.length === 0) return 'Нет калибровок для этого микроскопа';
      return 'Выберите калибровку';
    },
    isAnalyzeButtonDisabled() {
      return this.files.length === 0 || !this.$root.analyzeSelectedCalibration || !this.selectedMicroscope || this.busy;
    },
    isSaveButtonDisabled() {
      return this.$root.results.length === 0;
    },
    folderButtonStates() {
      const hasFiles   = this.files.length > 0;
      const hasResults = this.$root.results.length > 0;
      return {
        sources:    hasFiles,
        contrasted: hasResults,
        contours:   hasResults,
        analyzed:   hasResults,
      };
    },
    isDefaultMicroscope() {
      return !this.selectedMicroscope || this.selectedMicroscope.type === 'DEFAULT';
    },
    isManualMicroscope() {
      return this.selectedMicroscope?.type === 'MANUAL';
    },
    isAutomaticMicroscope() {
      return this.selectedMicroscope?.type === 'AUTOMATIC';
    },
    canShowCamera() {
      return this.isManualMicroscope || this.isAutomaticMicroscope;
    },
  },

  watch: {
    // Когда загружается существующее исследование — синхронизируем форму
    '$root.selectedResearch': {
      immediate: true,
      handler(research) {
        if (research) this.syncFromRoot(research);
      },
    },
    // Сигнал «новое исследование» — очищаем форму (даже если selectedResearch уже был null)
    '$root.analyzeResetKey'() {
      this.syncFromRoot(null);
    },
    // Обновляем список калибровок при каждом открытии вкладки Анализ
    '$root.currentTab'(tab) {
      if (tab === 'analyze') this.fetchCalibrations();
    },
    // При смене микроскопа сбрасываем калибровку
    selectedMicroscope(newVal, oldVal) {
      if (newVal !== oldVal) this.$root.analyzeSelectedCalibration = null;
    },
  },

  async mounted() {
    await this.fetchCalibrations();
    this.syncFromRoot(this.$root.selectedResearch);
  },

  methods: {
    // ------------------------------------------------------------------
    // Загрузка исследования
    // ------------------------------------------------------------------
    async createNewResearch() {
      const res = await api.newResearch();
      if (!res.ok) { this.errorMsg = 'Ошибка создания нового исследования.'; return; }
      this.$root.selectedResearch           = null;
      this.$root.analyzeSelectedCalibration = null;
      this.$root.results                    = [];
      this.$root.averages                   = {};
      this.$root.analyzeResetKey++;
    },

    toggleResearchLoadBlock() {
      if (!this.isResearchLoadVisible) this.fetchLoadResearches();
      this.isResearchLoadVisible = !this.isResearchLoadVisible;
      this.selectedResearchRow   = null;
    },

    async fetchLoadResearches() {
      const res = await api.getResearches();
      if (res.ok) this.loadResearches = res.researches;
    },

    async doLoadResearch(r) {
      const res = await api.loadResearch(r.id);
      if (!res.ok) { this.errorMsg = 'Не удалось загрузить исследование.'; return; }
      const research = res.research;
      this.$root.selectedResearch = research;
      this.$root.results          = research.contours || [];
      this.$root.averages         = {
        perimeter: research.average_perimeter,
        area:      research.average_area,
        width:     research.average_width,
        length:    research.average_length,
        dek:       research.average_dek,
      };
      this.$root.analyzeSelectedCalibration = research.calibration_id
        ? { id: research.calibration_id }
        : null;
      this.isResearchLoadVisible = false;
      this.selectedResearchRow   = null;
    },

    async deleteLoadResearch() {
      if (!this.selectedResearchRow) return;
      if (!confirm('Удалить исследование? Это действие необратимо.')) return;
      const res = await api.deleteResearch(this.selectedResearchRow.id);
      if (res.ok) {
        this.loadResearches    = this.loadResearches.filter(r => r.id !== this.selectedResearchRow.id);
        this.selectedResearchRow = null;
      } else {
        this.errorMsg = 'Не удалось удалить исследование.';
      }
    },

    // ------------------------------------------------------------------
    // Инициализация из корневого состояния
    // ------------------------------------------------------------------
    async syncFromRoot(research) {
      if (research) {
        this.researchId = research.id || 0;
        this.name       = research.name || '';
        this.employee   = research.employee || '';
        this.selectedMicroscope = this.$root.microscopes.find(m => m.name === research.microscope) || null;
        // Восстановить calibration после загрузки calibrations
        await this.$nextTick();
        if (research.calibration_id) {
          this.$root.analyzeSelectedCalibration =
            this.calibrations.find(c => c.id === research.calibration_id) || null;
        }
      } else {
        this.researchId = 0;
        this.name = '';
        this.employee = '';
        this.selectedMicroscope = null;
      }

      // Загружаем файлы текущей сессии
      this.imageCache   = {};
      this.currentImage = '';
      this.files        = [];
      this.currentFile  = null;
      this.lastUsedIndex = 0;

      const listRes = await api.listImages('research');
      if (listRes.ok && listRes.files.length > 0) {
        this.files = listRes.files.map(n => ({ name: n }));
        this.lastUsedIndex = Math.max(...this.files.map(f => parseInt(f.name) || 0));
        const hasResults = this.$root.results.length > 0;
        this.selectedFolder = hasResults ? 'analyzed' : 'sources';
        await this.selectFile(this.files[0]);
      }
    },

    // ------------------------------------------------------------------
    // Калибровки
    // ------------------------------------------------------------------
    async fetchCalibrations() {
      const res = await api.getCalibrations();
      if (res.ok) this.calibrations = res.calibrations;
    },

    // ------------------------------------------------------------------
    // Файлы
    // ------------------------------------------------------------------
    async handleFileSelect(event) {
      const newFiles = Array.from(event.target.files);
      for (const file of newFiles) {
        this.lastUsedIndex++;
        const name = `${this.lastUsedIndex}.jpg`;
        const b64  = await this._readAsBase64(file);
        const res  = await api.uploadImage(name, b64, 'research');
        if (res.ok) {
          this.files.push({ name });
        }
      }
      if (!this.currentFile && this.files.length > 0) {
        await this.selectFile(this.files[0]);
      }
      event.target.value = '';
    },

    async selectFile(file) {
      this.currentFile = file;
      await this.loadImage(file.name, this.selectedFolder);
    },

    async changeFolder(folder) {
      if (!this.folderButtonStates[folder]) return;
      this.selectedFolder = folder;
      if (this.currentFile) await this.loadImage(this.currentFile.name, folder);
    },

    async deleteCurrentFile() {
      if (!this.currentFile) return;
      const res = await api.deleteImage(this.currentFile.name, 'research');
      if (res.ok) {
        const idx = this.files.indexOf(this.currentFile);
        this.files.splice(idx, 1);
        delete this.imageCache[this.currentFile.name];
        if (this.files.length > 0) {
          await this.selectFile(this.files[Math.min(idx, this.files.length - 1)]);
        } else {
          this.currentFile  = null;
          this.currentImage = '';
        }
      } else {
        this.errorMsg = 'Ошибка удаления файла.';
      }
    },

    // ------------------------------------------------------------------
    // Изображения
    // ------------------------------------------------------------------
    async loadImage(filename, folder) {
      if (!filename) return;
      // Из кеша
      if (this.imageCache[filename]?.[folder]) {
        this.currentImage = this.imageCache[filename][folder];
        return;
      }
      this.imageLoading = true;
      this.currentImage = '';
      const res = await api.getImage(filename, folder, 'research');
      this.imageLoading = false;
      if (res.ok && res.data) {
        if (!this.imageCache[filename]) this.imageCache[filename] = {};
        this.imageCache[filename][folder] = res.data;
        this.currentImage = res.data;
      }
    },

    _readAsBase64(file) {
      return new Promise(resolve => {
        const reader = new FileReader();
        reader.onload = e => resolve(e.target.result);
        reader.readAsDataURL(file);
      });
    },

    // ------------------------------------------------------------------
    // Анализ
    // ------------------------------------------------------------------
    async analyzeAllFiles() {
      this.busy     = true;
      this.errorMsg = '';
      const res = await api.executeResearch(this.$root.analyzeSelectedCalibration?.id || 0);
      this.busy = false;
      if (res.ok) {
        this.$root.results  = res.contours;
        this.$root.averages = res.averages;
        this.$root.selectedResearch = {
          id:             this.researchId,
          name:           this.name,
          employee:       this.employee,
          microscope:     this.selectedMicroscope?.name || '',
          calibration_id: this.$root.analyzeSelectedCalibration?.id || 0,
          date:           new Date().toISOString(),
        };
        // Очищаем кеш analyzed-папки и показываем результат
        for (const f of this.files) {
          if (this.imageCache[f.name]) delete this.imageCache[f.name]['analyzed'];
        }
        this.selectedFolder = 'analyzed';
        if (this.currentFile) await this.loadImage(this.currentFile.name, 'analyzed');
      } else {
        this.errorMsg = 'Ошибка выполнения анализа.';
      }
    },

    // ------------------------------------------------------------------
    // Сохранение
    // ------------------------------------------------------------------
    async saveResearch() {
      this.errorMsg = '';
      const res = await api.saveResearch({
        id:               this.researchId,
        name:             this.name,
        employee:         this.employee,
        microscope:       this.selectedMicroscope?.name || '',
        calibration_id:   this.$root.analyzeSelectedCalibration?.id || 0,
        average_perimeter: this.$root.averages.perimeter,
        average_area:      this.$root.averages.area,
        average_width:     this.$root.averages.width,
        average_length:    this.$root.averages.length,
        average_dek:       this.$root.averages.dek,
        contours:          this.$root.results,
      });
      if (res.ok) {
        this.researchId = res.id;
        if (this.$root.selectedResearch) this.$root.selectedResearch.id = res.id;
      } else {
        this.errorMsg = 'Ошибка сохранения исследования.';
      }
    },

    // ------------------------------------------------------------------
    // Модальное окно
    // ------------------------------------------------------------------
    openModal() {
      if (!this.currentImage) return;
      new bootstrap.Modal(document.getElementById('analyzeImageModal')).show();
    },
    closeModal() {
      bootstrap.Modal.getInstance(document.getElementById('analyzeImageModal'))?.hide();
    },
  },
};
