window.CameraPanel = {
  props: {
    microscope: Object, context: String, active: Boolean, revision: Number,
    disabled: {type:Boolean, default:false},
  },
  emits: ['captured', 'connected', 'error'],
  template: `
    <div class="border rounded p-2 mb-2">
      <div class="d-flex gap-2 align-items-center mb-2">
        <button class="btn btn-sm btn-outline-primary" @click="connect"
                :disabled="busy || !active || disabled || !microscope || microscope.camera_index == null || !!connectionId">
          {{ busy ? 'Подключение…' : 'Подключить камеру' }}
        </button>
        <button class="btn btn-sm btn-outline-secondary" @click="stop" :disabled="!connectionId && !busy">Отключить</button>
        <span class="small" :class="connectionId ? 'text-success' : 'text-muted'">
          {{ connectionId ? 'Подключено' : 'Не подключено' }}
        </span>
      </div>
      <div v-if="microscope && microscope.camera_index == null" class="small text-muted mb-2">Выберите камеру для этого микроскопа в настройках.</div>
      <div v-if="connectionId" class="text-center bg-light p-1 mb-2">
        <div class="small text-muted">Живое изображение камеры</div>
        <img v-if="preview" :src="preview" style="max-width:100%;max-height:300px;object-fit:contain;">
        <span v-else class="small text-muted">Получение кадра…</span>
      </div>
      <button v-if="context !== 'settings'" class="btn btn-sm btn-primary" @click="capture"
              :disabled="!connectionId || capturing || disabled || !active">
        {{ capturing ? 'Сохранение…' : (context === 'calibration' ? 'Снять шкалу' : 'Снимок') }}
      </button>
      <div v-if="cameraError" class="alert alert-danger small py-1 mt-2 mb-0">{{ cameraError }}</div>
    </div>
  `,
  data() {
    return {connectionId:'',preview:'',busy:false,capturing:false,cameraError:'',
            generation:0,pollTimer:null,reading:false};
  },
  watch: {
    active(value) { if (!value) this.stop(); },
    microscope() { this.stop(); },
    context() { this.stop(); },
  },
  beforeUnmount() { this.stop(); },
  methods: {
    async connect() {
      if (!this.active || this.disabled || this.busy || this.connectionId || !this.microscope) return;
      this.busy = true;
      this.cameraError = '';
      const generation = ++this.generation;
      try {
        const result = await api.connectMicroscope(this.microscope.name, this.context);
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
        this.pollTimer = setTimeout(() => this.poll(generation), 200);
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
          this.pollTimer = setTimeout(() => this.poll(generation), 200);
        }
      }
    },
    async capture() {
      if (!this.connectionId || !this.active || this.disabled || this.capturing) return;
      const generation = this.generation;
      this.capturing = true;
      this.cameraError = '';
      try {
        const result = await api.captureImage(this.connectionId, this.context, this.revision);
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
