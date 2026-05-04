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
                  {{ m.custom ? 'USB #' + m.camera_index : '—' }}
                </td>
                <td class="text-center">
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
                <button class="btn btn-sm btn-outline-secondary"
                        :disabled="testing" @click="testCamera">
                  {{ testing ? 'Захват...' : 'Тест' }}
                </button>
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

          <!-- Правая колонка: тестовый кадр -->
          <div class="col-md-7">
            <div class="img-thumbnail d-flex justify-content-center align-items-center"
                 style="width:100%;height:320px;background:#1a1a1a;">
              <img v-if="testFrame" :src="testFrame"
                   style="max-width:100%;max-height:100%;object-fit:contain;">
              <span v-else class="text-secondary small">
                Выберите камеру и нажмите «Тест»
              </span>
            </div>
          </div>

        </div>
      </div>

    </div>
  `,

  data() {
    return {
      cameras:         [],
      scanned:         false,
      scanning:        false,
      selectedCamera:  null,

      newName: '',
      newType: 'MANUAL',

      testing:   false,
      testFrame: '',
      errorMsg:  '',
    };
  },

  methods: {
    async scanCameras() {
      this.scanning  = true;
      this.errorMsg  = '';
      this.cameras   = [];
      this.scanned   = false;
      this.selectedCamera = null;
      this.testFrame = '';

      const res = await api.scanCameras();
      this.scanning = false;
      this.scanned  = true;
      if (res.ok) {
        this.cameras = res.cameras;
      } else {
        this.errorMsg = 'Ошибка при поиске камер.';
      }
    },

    selectCamera(cam) {
      this.selectedCamera = cam;
      this.testFrame = '';
      this.newName   = cam.label;
      this.errorMsg  = '';
    },

    async testCamera() {
      if (!this.selectedCamera) return;
      this.testing   = true;
      this.testFrame = '';
      this.errorMsg  = '';

      const res = await api.getTestFrame(this.selectedCamera.index);
      this.testing = false;
      if (res.ok) {
        this.testFrame = res.data;
      } else {
        this.errorMsg = res.error || 'Не удалось получить кадр.';
      }
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
        this.selectedCamera = null;
        this.newName        = '';
        this.newType        = 'MANUAL';
        this.testFrame      = '';
      } else {
        this.errorMsg = 'Ошибка сохранения микроскопа.';
      }
    },

    async deleteMicroscope(m) {
      if (!confirm(`Удалить микроскоп «${m.name}»?`)) return;
      const res = await api.deleteCustomMicroscope(m.id);
      if (res.ok) {
        const mics = await api.getMicroscopes();
        if (mics.ok) this.$root.microscopes = mics.microscopes;
      } else {
        this.errorMsg = 'Ошибка удаления микроскопа.';
      }
    },
  },
};
