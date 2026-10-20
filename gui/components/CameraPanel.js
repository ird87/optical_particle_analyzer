window.CameraPanel = {
  props: {
    microscope: Object, context: String, active: Boolean, revision: Number,
    disabled: {type:Boolean, default:false},
    cameraIndex: {type:Number, default:null},
  },
  emits: ['captured', 'connected', 'error'],
  template: `
    <div class="border rounded p-2 mb-2">
      <div class="d-flex flex-wrap gap-2 align-items-center mb-2">
        <button class="btn btn-sm btn-outline-primary" @click="connect"
                :disabled="busy || !active || disabled || deviceIndex == null || !!connectionId">
          {{ busy ? 'Подключение…' : (context === 'settings' ? 'Начать видеопросмотр' : 'Подключить камеру') }}
        </button>
        <button class="btn btn-sm btn-outline-secondary" @click="stop" :disabled="!connectionId && !busy">
          {{ context === 'settings' ? 'Остановить просмотр' : 'Отключить' }}
        </button>
        <span class="small" :class="connectionId ? 'text-success' : 'text-muted'">
          {{ connectionId ? 'Подключено' : 'Не подключено' }}
        </span>
      </div>
      <div v-if="microscope && deviceIndex == null" class="small text-muted mb-2">Выберите камеру для этого микроскопа в настройках.</div>
      <div v-if="connectionId" class="text-center bg-light p-1 mb-2">
        <div class="small text-muted">Живое изображение камеры</div>
        <img v-if="preview" :src="preview" alt="Видеопредпросмотр камеры" style="max-width:100%;max-height:300px;object-fit:contain;">
        <span v-else class="small text-muted">Получение кадра…</span>
      </div>
      <button class="btn btn-sm btn-primary" @click="capture"
              :disabled="!connectionId || capturing || disabled || !active">
        {{ capturing ? 'Съёмка…' : (context === 'calibration' ? 'Снять шкалу' : 'Снимок') }}
      </button>
      <div v-if="context === 'settings' && testSnapshot" class="text-center bg-light p-1 mt-2">
        <div class="small text-muted">Тестовый снимок · {{ snapshotWidth }} × {{ snapshotHeight }}</div>
        <img :src="testSnapshot" alt="Тестовый снимок" style="max-width:100%;max-height:300px;object-fit:contain;">
      </div>
      <div v-if="cameraError" class="alert alert-danger small py-1 mt-2 mb-0">{{ cameraError }}</div>
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
      this.capturing = true;
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
        this.$emit('captured', result);
      } catch (error) { if (generation === this.generation) this.fail(error); }
      finally { this.capturing = false; }
    },
  },
};
