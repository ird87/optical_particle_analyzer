window.CameraPanel = {
  props: {
    microscope: Object, context: String, active: Boolean, revision: Number,
    disabled: {type:Boolean, default:false},
    cameraIndex: {type:Number, default:null},
  },
  emits: ['captured', 'capturing', 'connected', 'error'],
  template: `
    <div class="camera-panel border rounded p-2 mb-2" :class="{'camera-test-panel':context === 'settings'}">
      <div class="camera-toolbar d-flex flex-wrap gap-2 align-items-center mb-2">
        <button class="btn btn-sm btn-outline-primary" @click="connect"
                :disabled="busy || !active || disabled || deviceIndex == null || !!connectionId">
          {{ busy ? 'Подключение…' : 'Включить видео' }}
        </button>
        <button class="btn btn-sm btn-outline-secondary" @click="stop" :disabled="!connectionId && !busy">Остановить</button>
        <button class="btn btn-sm btn-primary" @click="capture" :disabled="!connectionId || capturing || disabled || !active">
          {{ capturing ? 'Съёмка…' : (context === 'calibration' ? 'Снять шкалу' : 'Снимок') }}
        </button>
        <span class="small ms-auto" :class="connectionId ? 'text-success' : 'text-muted'" role="status">
          {{ connectionId ? 'Подключено' : (deviceIndex == null ? 'Камера не выбрана' : 'Видео выключено') }}
        </span>
      </div>
      <div v-if="microscope && deviceIndex == null" class="small text-muted mb-2">Выберите камеру для этого микроскопа в настройках или загрузите готовый снимок.</div>
      <div v-if="cameraError" class="alert alert-danger small py-1 mb-2" role="alert">{{ cameraError }}</div>
      <div class="camera-images" :class="{'row g-2':context === 'settings'}">
        <div :class="{'col-6':context === 'settings'}">
          <div class="small text-muted mb-1">Видео камеры</div>
          <div class="camera-image-frame bg-light d-flex align-items-center justify-content-center">
            <img v-if="connectionId && preview" :src="preview" alt="Видеопредпросмотр камеры" class="workspace-image">
            <span v-else class="small text-muted text-center p-2">{{ connectionId ? 'Получение кадра…' : 'Включите видео, чтобы проверить резкость и освещение' }}</span>
          </div>
        </div>
        <div v-if="context === 'settings'" class="col-6">
          <div class="small text-muted mb-1">{{ testSnapshot ? 'Тестовый снимок · ' + snapshotWidth + ' × ' + snapshotHeight : 'Тестовый снимок' }}</div>
          <div class="camera-image-frame bg-light d-flex align-items-center justify-content-center">
            <img v-if="testSnapshot" :src="testSnapshot" alt="Тестовый снимок" class="workspace-image">
            <span v-else class="small text-muted text-center p-2">Нажмите «Снимок», чтобы проверить отдельный кадр</span>
          </div>
        </div>
      </div>
    </div>
  `,
  data() {
    return {connectionId:'',preview:'',testSnapshot:'',snapshotWidth:0,snapshotHeight:0,
            busy:false,capturing:false,cameraError:'',
            generation:0,pollTimer:null,reading:false};
  },
  computed: {
    deviceIndex() {
      return this.context === 'settings' && this.cameraIndex != null
        ? this.cameraIndex : this.microscope?.camera_index;
    },
  },
  watch: {
    active(value) { if (!value) this.stop(); },
    microscope() { this.testSnapshot=''; return this.stop(); },
    cameraIndex() { this.testSnapshot=''; return this.stop(); },
    context() { this.testSnapshot=''; return this.stop(); },
  },
  beforeUnmount() { this.stop(); },
  methods: {
    async connect() {
      if (!this.active || this.disabled || this.busy || this.connectionId || this.deviceIndex == null) return;
      this.busy = true;
      this.cameraError = '';
      const generation = ++this.generation;
      try {
        const result = this.context === 'settings' && this.cameraIndex != null
          ? await api.connectCamera(this.cameraIndex)
          : await api.connectMicroscope(this.microscope.name, this.context);
        if (generation !== this.generation || !this.active) {
          if (result.ok) await api.disconnectCamera(result.connection_id);
          return;
        }
        if (!result.ok) throw new Error(result.error || 'Не удалось подключить камеру');
        this.connectionId = result.connection_id;
        this.$emit('connected', result);
        this.poll(generation);
      } catch (error) {
        if (generation === this.generation) this.fail(error);
      } finally { this.busy = false; }
    },
    async stop() {
      ++this.generation;
      clearTimeout(this.pollTimer);
      this.pollTimer = null;
      const token = this.connectionId;
      this.connectionId = '';
      this.preview = '';
      if (token) {
        try { await api.disconnectCamera(token); }
        catch (error) { this.fail(error); }
      }
    },
    fail(error) {
      this.cameraError = error.message || String(error);
      this.$emit('error', this.cameraError);
    },
    async poll(generation) {
      if (generation !== this.generation || !this.active || !this.connectionId) return;
      if (this.reading) {
        clearTimeout(this.pollTimer);
        this.pollTimer = setTimeout(() => this.poll(generation), 50);
        return;
      }
      this.reading = true;
      try {
        const result = await api.getCameraFrame(this.connectionId);
        if (generation !== this.generation || !this.active) return;
        if (!result.ok) throw new Error(result.error || 'Кадр не получен');
        this.preview = result.data;
      } catch (error) {
        if (generation === this.generation) { this.fail(error); await this.stop(); }
      } finally {
        this.reading = false;
        if (generation === this.generation && this.active && this.connectionId) {
          clearTimeout(this.pollTimer);
          this.pollTimer = setTimeout(() => this.poll(generation), 50);
        }
      }
    },
    async capture() {
      if (!this.connectionId || !this.active || this.disabled || this.capturing) return;
      const generation = this.generation;
      const microscope = this.microscope?.name || '';
      this.capturing = true;
      this.$emit('capturing', true);
      this.cameraError = '';
      try {
        const settings = this.context === 'settings';
        const result = settings
          ? await api.captureTestFrame(this.connectionId)
          : await api.captureImage(this.connectionId, this.context, this.revision);
        if (settings) {
          if (generation !== this.generation || !this.active) return;
          if (!result.ok) throw new Error(result.error || 'Не удалось получить снимок');
          this.testSnapshot = result.data;
          this.snapshotWidth = result.width;
          this.snapshotHeight = result.height;
          return;
        }
        // Successful saves are committed session mutations, even after closing the preview.
        if (!result.ok) {
          if (generation !== this.generation || !this.active) return;
          throw new Error(result.error || 'Не удалось сохранить снимок');
        }
        this.$emit('captured', {...result, microscope});
      } catch (error) { if (generation === this.generation) this.fail(error); }
      finally { this.capturing = false;this.$emit('capturing', false); }
    },
  },
};
