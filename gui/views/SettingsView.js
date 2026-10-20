window.SettingsView = {
  template: `
    <div class="settings-workspace">
      <div class="row g-3">
        <div class="col-md-4 col-xl-3">
          <div class="workspace-heading">
            <h6 class="mb-0">Микроскопы</h6>
            <button class="btn btn-sm btn-outline-primary" :disabled="working" @click="beginAddMicroscope">Добавить</button>
          </div>
          <div class="list-group microscope-list">
            <button v-for="m in $root.microscopes" :key="m.name" class="list-group-item list-group-item-action"
                    :class="{active:selectedMicroscopeName === m.name}" :disabled="working" @click="configureMicroscope(m)">
              <strong>{{ m.type === 'DEFAULT' ? 'Изображения с диска' : m.name }}</strong>
              <span class="d-block small">{{ m.type === 'DEFAULT' ? 'Камера не требуется' : m.type_localized + ' · ' + (m.camera_index != null ? 'Камера ' + m.camera_index : 'Камера не выбрана') }}</span>
            </button>
          </div>
          <details class="mt-3 division-reference">
            <summary class="small">Справка: цены деления шкалы</summary>
            <p class="small text-muted mt-2 mb-1">Расстояние между соседними штрихами выбирается при калибровке. 1 мм = 1000 мкм.</p>
            <div class="small" v-for="d in $root.divisionPrices" :key="d.name">{{ d.name }}</div>
          </details>
        </div>

        <div class="col-md-8 col-xl-9">
          <div v-if="selectedMicroscope || adding" class="border rounded p-3 microscope-card">
            <div class="workspace-heading">
              <h6 class="mb-0">{{ adding ? 'Новый микроскоп' : (selectedMicroscope.type === 'DEFAULT' ? 'Работа с файлами' : selectedMicroscope.name) }}</h6>
              <button v-if="selectedMicroscope && selectedMicroscope.custom" class="btn btn-sm btn-outline-danger" :disabled="working" @click="deleteMicroscope(selectedMicroscope)">Удалить микроскоп</button>
              <button v-if="adding" class="btn btn-sm btn-outline-secondary" :disabled="working" @click="cancelAdd">Отмена</button>
            </div>
            <div v-if="errorMsg" class="alert alert-danger py-2" role="alert">{{ errorMsg }}</div>
            <div v-if="successMsg" class="alert alert-success py-2" role="status">{{ successMsg }}</div>
            <div v-if="selectedMicroscope && selectedMicroscope.type === 'DEFAULT'" class="text-muted">
              Загружайте готовые изображения во вкладках «Калибровка» и «Анализ». Подключать камеру для этого режима не нужно.
            </div>
            <div v-else>
              <div v-if="adding" class="row g-2 mb-2">
                <div class="col-lg-6">
                  <label for="microscope-name" class="form-label">Название микроскопа</label>
                  <input id="microscope-name" v-model="newName" class="form-control" placeholder="Например: Микроскоп USB 1" :disabled="working">
                </div>
                <div class="col-lg-6">
                  <label for="microscope-type" class="form-label">Перемещение образца</label>
                  <select id="microscope-type" v-model="newType" class="form-select" :disabled="working">
                    <option value="MANUAL">Вручную, снимок по кнопке</option>
                    <option value="AUTOMATIC">Автоматически · стол Arduino XYZ</option>
                  </select>
                </div>
              </div>
              <p v-if="(adding ? newType : selectedMicroscope.type) === 'AUTOMATIC'" class="small text-muted mb-2">Автоматическая съёмка использует стол Arduino XYZ и измеренный профиль масштаба Z.</p>
              <div class="d-flex flex-wrap align-items-end gap-2 mb-2">
                <div class="camera-device-field">
                  <label for="microscope-camera" class="form-label">Камера</label>
                  <select id="microscope-camera" v-model="bindingIndex" @change="onDeviceChange" class="form-select" :disabled="working">
                    <option :value="null">Выберите найденную камеру</option>
                    <option v-for="cam in cameraOptions" :key="cam.index" :value="cam.index">{{ cam.label }}</option>
                  </select>
                </div>
                <button class="btn btn-outline-primary" :disabled="working" @click="scanCameras">{{ scanning ? 'Поиск…' : 'Найти камеры' }}</button>
                <button v-if="adding" class="btn btn-success" :disabled="working || !newName.trim() || bindingIndex == null" @click="addMicroscope">Добавить микроскоп</button>
                <button v-else class="btn btn-primary" :disabled="working || bindingIndex == null || bindingIndex === selectedMicroscope.camera_index" @click="bindCamera">Сохранить привязку</button>
              </div>
              <p class="small text-muted mb-2" role="status">{{ deviceHint }}</p>
              <details class="mb-2">
                <summary class="small text-muted">Указать индекс камеры вручную</summary>
                <input aria-label="Индекс камеры вручную" type="number" min="0" step="1" v-model.number="bindingIndex" @change="onDeviceChange" class="form-control form-control-sm mt-2 camera-index-field" :disabled="working">
                <span class="small text-muted">После переподключения USB индекс может измениться — найдите и проверьте камеру повторно.</span>
              </details>
              <stage-panel v-if="selectedMicroscope?.type === 'AUTOMATIC' && !adding" :key="selectedMicroscope.name"
                           :microscope="selectedMicroscope" mode="settings" :active="$root.currentTab === 'settings'" :disabled="working"></stage-panel>
              <camera-panel ref="cameraPreview" :key="bindingVersion"
                            :microscope="selectedMicroscope" :camera-index="bindingIndex"
                            context="settings" :active="$root.currentTab === 'settings'"
                            :disabled="working || bindingIndex == null" :revision="0"></camera-panel>
            </div>
          </div>
          <div v-else class="workspace-empty border rounded p-4">
            <h6>Выберите микроскоп слева</h6>
            <p class="text-muted mb-3">Здесь можно выбрать камеру, проверить видео и сделать тестовый снимок.</p>
            <button class="btn btn-primary" @click="beginAddMicroscope">Добавить микроскоп</button>
          </div>
        </div>
      </div>
    </div>
  `,
  data() {
    return {selectedMicroscopeName:'',bindingIndex:null,bindingVersion:0,
      cameras:[],scanned:false,scanning:false,selectedCamera:null,
      newName:'',newType:'MANUAL',adding:false,saving:false,errorMsg:'',successMsg:''};
  },
  computed: {
    selectedMicroscope() { return this.$root.microscopes.find(m => m.name === this.selectedMicroscopeName) || null; },
    working() { return this.scanning || this.saving || !!this.$root.stageBusy; },
    cameraOptions() {
      const options = this.cameras.map(cam => ({...cam,label:cam.label + ' · индекс ' + cam.index}));
      if (this.bindingIndex != null && !options.some(cam => cam.index === this.bindingIndex)) {
        options.push({index:this.bindingIndex,label:'Камера ' + this.bindingIndex + ' · ' + (this.scanned ? 'не найдена при поиске' : 'указанный индекс')});
      }
      return options;
    },
    deviceHint() {
      if (this.scanning) return 'Идёт поиск подключённых камер…';
      if (this.scanned && !this.cameras.length) return 'Камеры не найдены. Проверьте USB-подключение и повторите поиск.';
      if (this.bindingIndex == null) return 'Нажмите «Найти камеры», затем выберите устройство.';
      if (this.selectedMicroscope && this.bindingIndex !== this.selectedMicroscope.camera_index) return 'Выбрана другая камера. Проверьте изображение и сохраните привязку.';
      return 'Включите видео и сделайте тестовый снимок. Тестовые снимки не попадают в исследование.';
    },
  },
  methods: {
    async stopPreview() { if (this.$refs.cameraPreview) await this.$refs.cameraPreview.stop(); },
    async configureMicroscope(microscope) {
      if (this.working) return;
      await this.stopPreview();
      this.adding = false;this.selectedCamera = null;
      this.selectedMicroscopeName = microscope.name;this.bindingIndex = microscope.camera_index ?? null;
      this.bindingVersion++;this.errorMsg = '';this.successMsg = '';
    },
    async beginAddMicroscope() {
      if (this.working) return;
      await this.stopPreview();
      this.adding = true;this.selectedMicroscopeName = '';this.selectedCamera = null;
      this.bindingIndex = null;this.newName = '';this.newType = 'MANUAL';
      this.bindingVersion++;this.errorMsg = '';this.successMsg = '';
    },
    async cancelAdd() {
      await this.stopPreview();this.adding = false;this.selectedCamera = null;this.bindingIndex = null;
      this.errorMsg = '';this.successMsg = '';
    },
    async onDeviceChange() {
      await this.stopPreview();this.bindingVersion++;this.errorMsg = '';this.successMsg = '';
      if (this.adding) {
        this.selectedCamera = this.bindingIndex == null ? null : this.cameras.find(c => c.index === this.bindingIndex) || {index:this.bindingIndex,label:'Камера ' + this.bindingIndex};
        if (!this.newName && this.selectedCamera) this.newName = this.selectedCamera.label;
      }
    },
    async bindCamera() {
      if (!this.selectedMicroscope || this.bindingIndex == null || this.working) return;
      this.saving = true;this.errorMsg = '';this.successMsg = '';
      try {
        await this.stopPreview();
        const result = await api.bindMicroscope(this.selectedMicroscope.name,this.bindingIndex);
        if (!result.ok) { this.errorMsg = result.error;return; }
        const mics = await api.getMicroscopes();
        if (!mics.ok) { this.errorMsg = mics.error;return; }
        this.$root.microscopes = mics.microscopes;this.bindingVersion++;
        this.successMsg = 'Привязка камеры сохранена';
      } finally { this.saving = false; }
    },
    async scanCameras() {
      if (this.working) return;
      this.scanning = true;this.errorMsg = '';this.successMsg = '';this.scanned = false;
      try {
        await this.stopPreview();
        const res = await api.scanCameras();this.scanned = true;
        if (res.ok) this.cameras = res.cameras;
        else this.errorMsg = res.error || 'Ошибка при поиске камер.';
      } finally { this.scanning = false; }
    },
    async selectCamera(cam) {
      if (!this.adding && !this.selectedMicroscope) this.adding = true;
      this.bindingIndex = cam.index;await this.onDeviceChange();
    },
    async addMicroscope() {
      if (!this.newName.trim() || this.bindingIndex == null || this.working) return;
      this.saving = true;this.errorMsg = '';this.successMsg = '';
      try {
        await this.stopPreview();
        const name = this.newName.trim();
        const res = await api.saveCustomMicroscope({name,type:this.newType,
          type_localized:this.newType === 'AUTOMATIC' ? 'Автоматический' : 'Ручной',camera_index:this.bindingIndex});
        if (!res.ok) { this.errorMsg = res.error || 'Ошибка сохранения микроскопа.';return; }
        const mics = await api.getMicroscopes();
        if (!mics.ok) { this.errorMsg = mics.error;return; }
        this.$root.microscopes = mics.microscopes;
        this.selectedMicroscopeName = name;this.selectedCamera = null;this.adding = false;
        this.newName = '';this.newType = 'MANUAL';this.bindingVersion++;
        this.successMsg = 'Микроскоп добавлен. Можно перейти к калибровке.';
      } finally { this.saving = false; }
    },
    async deleteMicroscope(m) {
      if (this.working || !confirm('Удалить микроскоп «' + m.name + '»?')) return;
      this.saving = true;this.errorMsg = '';
      try {
        await this.stopPreview();
        const res = await api.deleteCustomMicroscope(m.id);
        if (!res.ok) { this.errorMsg = res.error || 'Ошибка удаления микроскопа.';return; }
        const mics = await api.getMicroscopes();
        if (mics.ok) this.$root.microscopes = mics.microscopes;
        this.selectedMicroscopeName = '';this.bindingIndex = null;this.bindingVersion++;
      } finally { this.saving = false; }
    },
  },
};
