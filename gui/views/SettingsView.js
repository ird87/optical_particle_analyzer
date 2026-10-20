window.SettingsView = {
  template: `
    <div class="mt-2">
      <div class="row g-4">

        <!-- ===== Список микроскопов ===== -->
        <div class="col-md-7">
          <h6>Микроскопы</h6>
          <table class="table table-sm table-bordered align-middle">
            <thead class="table-light">
              <tr><th>Название</th><th>Тип</th><th>Камера</th><th></th></tr>
            </thead>
            <tbody>
              <tr v-for="m in $root.microscopes" :key="m.name + (m.id || '')">
                <td>{{ m.name }}</td>
                <td>{{ m.type_localized }}</td>
                <td class="text-muted small">
                  {{ m.camera_index != null ? 'Камера ' + m.camera_index : 'Не привязана' }}
                </td>
                <td class="text-center">
                  <button v-if="m.type !== 'DEFAULT'" class="btn btn-sm btn-outline-primary me-1" @click="configureMicroscope(m)">Настроить</button>
                  <span v-if="!m.custom" class="badge bg-secondary">встроен</span>
                  <button v-else class="btn btn-sm btn-outline-danger"
                          @click="deleteMicroscope(m)">✕</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- ===== Цены деления ===== -->
        <div class="col-md-5">
          <h6>Цены деления</h6>
          <table class="table table-sm table-bordered">
            <thead class="table-light">
              <tr><th>Название</th><th>Значение (мкм)</th></tr>
            </thead>
            <tbody>
              <tr v-for="d in $root.divisionPrices" :key="d.name">
                <td>{{ d.name }}</td>
                <td>{{ d.value }}</td>
              </tr>
            </tbody>
          </table>
        </div>

      </div>

      <div v-if="selectedMicroscope" class="border rounded p-3 mt-3">
        <h6>Подключение: {{ selectedMicroscope.name }}</h6>
        <div class="d-flex align-items-end gap-2 mb-2">
          <div><label class="form-label">Индекс камеры</label>
            <input type="number" min="0" step="1" class="form-control form-control-sm" v-model.number="bindingIndex" style="width:110px;">
          </div>
          <button class="btn btn-sm btn-primary" @click="bindCamera">Привязать камеру</button>
        </div>
        <div class="small text-muted mb-2">Индексы устройств показаны в результатах поиска ниже. После переподключения USB индекс может измениться.</div>
      </div>

      <!-- ===== Подключение USB-микроскопа ===== -->
      <div class="border rounded p-3 mt-3">
        <h6 class="mb-3">Подключение USB-микроскопа</h6>

        <div class="row g-3 align-items-start">

          <!-- Левая колонка: поиск и форма -->
          <div class="col-md-5">

            <!-- Поиск камер -->
            <button class="btn btn-outline-primary btn-sm mb-3"
                    :disabled="scanning" @click="scanCameras">
              {{ scanning ? 'Поиск...' : 'Найти камеры' }}
            </button>

            <div v-if="cameras.length === 0 && scanned" class="text-muted small mb-2">
              USB-камеры не найдены.
            </div>

            <!-- Список найденных камер -->
            <div v-if="cameras.length > 0" class="mb-3">
              <label class="form-label small">Выберите камеру:</label>
              <div class="list-group">
                <button v-for="cam in cameras" :key="cam.index"
                        class="list-group-item list-group-item-action py-1 small"
                        :class="{ active: selectedCamera && selectedCamera.index === cam.index }"
                        @click="selectCamera(cam)">
                  {{ cam.label }} (индекс {{ cam.index }})
                </button>
              </div>
            </div>

            <!-- Форма добавления -->
            <div v-if="selectedCamera" class="mt-2">
              <div class="mb-2">
                <label class="form-label small">Название:</label>
                <input type="text" v-model="newName" class="form-control form-control-sm"
                       placeholder="Например: Микроскоп USB 1">
              </div>
              <div class="mb-3">
                <label class="form-label small">Тип управления:</label>
                <select v-model="newType" class="form-select form-select-sm">
                  <option value="MANUAL">Ручной (снимок по кнопке)</option>
                  <option value="AUTOMATIC">Автоматический</option>
                </select>
              </div>
              <div class="d-flex gap-2">
                <button class="btn btn-sm btn-success"
                        :disabled="!newName.trim()" @click="addMicroscope">
                  Добавить
                </button>
              </div>
            </div>

            <div v-if="errorMsg" class="alert alert-danger alert-sm mt-2 py-1 small">
              {{ errorMsg }}
            </div>
          </div>

          <!-- Правая колонка: видео и отдельный тестовый снимок -->
          <div class="col-md-7">
            <div v-if="selectedCamera || selectedMicroscope">
              <h6>Проверка: {{ selectedCamera ? selectedCamera.label : selectedMicroscope.name }}</h6>
              <p class="small text-muted">Начните видеопросмотр. Кнопка «Снимок» оставляет отдельный кадр для проверки качества изображения.</p>
              <camera-panel ref="cameraPreview" :key="bindingVersion"
                            :microscope="selectedCamera ? null : selectedMicroscope"
                            :camera-index="selectedCamera ? selectedCamera.index : null"
                            context="settings" :active="$root.currentTab === 'settings'"
                            :revision="0" @error="errorMsg = $event"></camera-panel>
            </div>
            <div v-else class="text-muted small p-3 border rounded">
              Выберите найденную камеру или нажмите «Настроить» у микроскопа.
            </div>
          </div>

        </div>
      </div>

    </div>
  `,

  data() {
    return {
      selectedMicroscopeName: '',
      bindingIndex: 0,
      bindingVersion: 0,
      cameras:         [],
      scanned:         false,
      scanning:        false,
      selectedCamera:  null,

      newName: '',
      newType: 'MANUAL',

      errorMsg:  '',
    };
  },

  computed: {
    selectedMicroscope() {
      return this.$root.microscopes.find(m => m.name === this.selectedMicroscopeName) || null;
    },
  },
  methods: {
    async configureMicroscope(microscope) {
      if (this.$refs.cameraPreview) await this.$refs.cameraPreview.stop();
      this.selectedCamera = null;
      this.selectedMicroscopeName = microscope.name;
      this.bindingIndex = microscope.camera_index == null ? 0 : microscope.camera_index;
      this.bindingVersion++;
      this.errorMsg = '';
    },
    async bindCamera() {
      if (!this.selectedMicroscope) return;
      if (this.$refs.cameraPreview) await this.$refs.cameraPreview.stop();
      const result = await api.bindMicroscope(this.selectedMicroscope.name, this.bindingIndex);
      if (!result.ok) { this.errorMsg = result.error; return; }
      const mics = await api.getMicroscopes();
      if (mics.ok) this.$root.microscopes = mics.microscopes;
      this.bindingVersion++;
      this.errorMsg = '';
    },
    async scanCameras() {
      this.scanning  = true;
      if (this.$refs.cameraPreview) await this.$refs.cameraPreview.stop();
      this.errorMsg  = '';
      this.cameras   = [];
      this.scanned   = false;
      this.selectedCamera = null;
      this.selectedMicroscopeName = '';

      const res = await api.scanCameras();
      this.scanning = false;
      this.scanned  = true;
      if (res.ok) {
        this.cameras = res.cameras;
      } else {
        this.errorMsg = res.error || 'Ошибка при поиске камер.';
      }
    },

    async selectCamera(cam) {
      if (this.$refs.cameraPreview) await this.$refs.cameraPreview.stop();
      this.selectedCamera = cam;
      this.selectedMicroscopeName = '';
      this.bindingVersion++;
      this.newName   = cam.label;
      this.errorMsg  = '';
    },

    async addMicroscope() {
      if (!this.newName.trim() || !this.selectedCamera) return;
      this.errorMsg = '';

      const typeLabels = { MANUAL: 'Ручной', AUTOMATIC: 'Автоматический' };
      const res = await api.saveCustomMicroscope({
        name:           this.newName.trim(),
        type:           this.newType,
        type_localized: typeLabels[this.newType],
        camera_index:   this.selectedCamera.index,
      });

      if (res.ok) {
        // Обновляем глобальный список микроскопов
        const mics = await api.getMicroscopes();
        if (mics.ok) this.$root.microscopes = mics.microscopes;

        // Сбрасываем форму
        this.selectedMicroscopeName = this.newName.trim();
        this.bindingIndex = this.selectedCamera.index;
        this.bindingVersion++;
        this.selectedCamera = null;
        this.newName        = '';
        this.newType        = 'MANUAL';
      } else {
        this.errorMsg = res.error || 'Ошибка сохранения микроскопа.';
      }
    },

    async deleteMicroscope(m) {
      if (!confirm(`Удалить микроскоп «${m.name}»?`)) return;
      if (this.selectedMicroscopeName === m.name && this.$refs.cameraPreview) await this.$refs.cameraPreview.stop();
      const res = await api.deleteCustomMicroscope(m.id);
      if (res.ok) {
        const mics = await api.getMicroscopes();
        if (mics.ok) this.$root.microscopes = mics.microscopes;
      } else {
        this.errorMsg = res.error || 'Ошибка удаления микроскопа.';
      }
    },
  },
};
