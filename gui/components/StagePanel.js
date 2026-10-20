window.StagePanel = {
  props:{microscope:Object,active:Boolean,mode:{type:String,default:'settings'},disabled:Boolean},
  emits:['scan-updated','profile-ready'],
  template:`
    <div class="stage-panel border rounded p-2 mb-2">
      <div class="d-flex align-items-center flex-wrap gap-2 mb-2">
        <strong>Стол XYZ · {{ (connected ? stage.board : settings.board) === 'nano' ? 'Arduino Nano' : (connected ? stage.board : settings.board) }}</strong>
        <span class="small" role="status">{{ statusLabel }}</span>
        <button class="btn btn-sm btn-outline-primary ms-auto" :disabled="locked || connected" @click="start('connect')">Подключить стол</button>
        <button class="btn btn-sm btn-outline-primary" :disabled="locked || !connected" @click="start('home')">Найти ноль Z → X → Y</button>
        <button class="btn btn-sm btn-danger" :disabled="!connected && !job.active" @click="stop">СТОП</button>
        <button v-if="mode === 'settings'" class="btn btn-sm btn-outline-secondary" :disabled="locked || !connected" @click="disconnect">Отключить</button>
      </div>
      <div v-if="simulated" class="alert alert-info small py-1 mb-2">Симулятор: движения и изображения синтетические. Эти измерения служат только для проверки программы.</div>
      <div v-if="error" class="alert alert-danger small py-1 mb-2" role="alert">{{ error }}</div>
      <div v-if="connected" class="small text-muted mb-2">Координаты X / Y / Z: {{ (stage.pos || []).join(' / ') }} шагов · Концевики: {{ (stage.limits || []).join(' / ') }} (1 — сработал)</div>
      <div v-if="mode === 'settings'" class="mb-2">
        <div class="row g-2">
          <div class="col-md-3"><label class="form-label">Режим</label><select class="form-select form-select-sm" v-model="settings.mode" :disabled="locked"><option value="serial">Реальный стол</option><option value="simulator">Симулятор без оборудования</option></select></div>
          <div class="col-md-3"><label class="form-label">Плата</label><select class="form-select form-select-sm" v-model="settings.board" :disabled="locked"><option value="nano">Nano (ATmega328P) · основная</option><option value="uno">Uno</option><option value="mega">Mega 2560</option></select></div>
          <div class="col-md-2"><label class="form-label">Драйвер</label><select class="form-select form-select-sm" v-model="settings.driver" :disabled="locked"><option value="a4988">A4988</option><option value="drv8825">DRV8825</option></select></div>
          <div class="col-md-4"><label class="form-label">COM-порт</label><div class="input-group input-group-sm"><input class="form-control" aria-label="COM-порт" v-model="settings.port" list="stage-ports" :disabled="locked || settings.mode === 'simulator'" placeholder="COM3"><button class="btn btn-outline-secondary" :disabled="locked" @click="findPorts">Найти</button></div><datalist id="stage-ports"><option v-for="p in ports" :key="p.port" :value="p.port">{{ p.label }}</option></datalist></div>
        </div>
        <details class="mt-2"><summary class="small">Параметры механики для инженера</summary>
          <p class="small text-muted mt-2">Значения ниже — заготовка. Они должны соответствовать прошивке, винтам и микрошагу. Ноль Z должен отводить объектив от образца. После изменения оптики создайте новый профиль Z.</p>
          <div class="row g-2"><div class="col-md-4" v-for="(axis,i) in ['X','Y','Z']" :key="axis"><label class="form-label">Ход {{ axis }}, шагов</label><input type="number" min="1" step="1" class="form-control form-control-sm" v-model.number="settings.travel_steps[i]" :disabled="locked"><label class="form-label mt-1">{{ axis }}: импульсов на мм</label><input type="number" min="0.001" step="0.001" class="form-control form-control-sm" v-model.number="settings.steps_per_mm[i]" :disabled="locked"></div></div>
          <div class="row g-2 mt-1"><div class="col-md-6"><label class="form-label">Пауза после движения, мс</label><input type="number" min="0" max="10000" class="form-control form-control-sm" v-model.number="settings.settle_ms" :disabled="locked"></div><div class="col-md-6"><label class="form-label">Таймаут движения, с</label><input type="number" min="1" max="600" class="form-control form-control-sm" v-model.number="settings.move_timeout_s" :disabled="locked"></div></div>
          <label class="form-check mt-2"><input type="checkbox" class="form-check-input" v-model="settings.mechanics_confirmed" :disabled="locked"> Инженер проверил направления, концевики, ход и настройки прошивки</label>
        </details>
        <button class="btn btn-sm btn-primary mt-2" :disabled="locked" @click="saveSettings">Сохранить настройки стола</button>
        <span class="small text-muted ms-2">Подключение использует сохранённые настройки.</span>
      </div>
      <details v-if="connected" class="mb-2"><summary class="small">Ручное перемещение · абсолютные координаты в шагах</summary>
        <div class="d-flex gap-2 mt-2"><label v-for="(axis,i) in ['X','Y','Z']" :key="axis" class="small flex-fill">{{ axis }}<input type="number" min="0" step="1" v-model.number="target[i]" class="form-control form-control-sm" :disabled="locked || !stage.homed"></label><button class="btn btn-sm btn-outline-primary align-self-end" :disabled="locked || !stage.homed" @click="start('move')">Перейти</button></div>
      </details>
      <div v-if="mode === 'profile'">
        <h6>Профиль масштаба по Z</h6>
        <p class="small text-muted">Закрепите шкалу с известным шагом и настройте оптику. Мастер переместит Z, дождётся остановки и снимет шкалу в каждой точке. Проверьте резкость по всему диапазону заранее. Между точками масштаб не интерполируется.</p>
        <div class="row g-2"><div class="col-md-4"><label class="form-label">Название профиля</label><input class="form-control form-control-sm" v-model="profileName" :disabled="locked"></div><div class="col-md-4"><label class="form-label">Положения Z, шагов через запятую</label><input class="form-control form-control-sm" v-model="positions" :disabled="locked" placeholder="0, 1000, 2000"></div><div class="col-md-4"><label class="form-label">Между штрихами</label><select class="form-select form-select-sm" v-model="divisionPrice" :disabled="locked"><option value="" disabled>Цена деления</option><option v-for="p in $root.divisionPrices" :key="p.name" :value="p.name">{{ p.name }}</option></select></div></div>
        <button class="btn btn-sm btn-primary mt-2" :disabled="locked || !stage.homed || !profileName.trim() || !positions.trim() || !divisionPrice" @click="start('profile')">Снять и рассчитать все положения Z</button>
      </div>
      <div v-if="mode !== 'settings'" class="mt-2">
        <div class="row g-2"><div class="col-md-8"><label class="form-label">Измеренный профиль Z</label><select class="form-select form-select-sm" v-model="profileId" @change="selectProfile" :disabled="locked"><option value="">{{ profiles.length ? 'Выберите профиль' : 'Сначала создайте профиль во вкладке «Калибровка»' }}</option><option v-for="p in profiles" :key="p.id" :value="p.id">{{ p.name }}{{ p.simulated ? ' · симулятор' : '' }}</option></select></div><div class="col-md-4"><label class="form-label">Калиброванное Z, шагов</label><select class="form-select form-select-sm" v-model="z" @change="loadScaleImage" :disabled="locked || !selectedProfile"><option v-for="p in (selectedProfile?.points || [])" :key="p.z" :value="p.z">{{ p.z }} · {{ (p.division_um / p.coefficient).toFixed(4) }} мкм/пикс</option></select></div></div>
        <div v-if="mode === 'scan'" class="mt-2">
          <p class="small text-muted mb-1">Одна серия снимается на одном Z. Поле кадра: {{ fieldOfView }}. Шаг XY: {{ gridPitch }}. Кадры считаются отдельно: перекрытие может повторно учитывать частицы. Выберите шаг сетки без перекрытия.</p>
          <div class="row g-2"><div class="col-4" v-for="item in gridFields" :key="item.key"><label class="form-label small">{{ item.label }}</label><input type="number" :min="item.min" step="1" v-model.number="grid[item.key]" class="form-control form-control-sm" :disabled="locked"></div></div>
          <button class="btn btn-sm btn-primary mt-2" :disabled="locked || !stage.homed || !selectedPoint" @click="start('scan')">Снять сетку · {{ grid.columns * grid.rows }} кадров</button>
        </div>
        <button v-if="selectedPoint && mode === 'profile'" class="btn btn-sm btn-outline-secondary mt-2" :disabled="locked" @click="loadScaleImage">Проверить снимок шкалы</button>
      </div>
      <div v-if="job.id" class="small mt-2" role="status">{{ jobLabel }} · {{ job.completed || 0 }} / {{ job.total || 0 }}<span v-if="job.error"> · {{ job.error }}</span></div>
      <img v-if="preview" :src="preview" alt="Последний кадр автоматической съёмки или шкала Z" class="stage-preview img-thumbnail mt-2">
    </div>
  `,
  data(){return {settings:{mode:'serial',port:'',board:'nano',driver:'a4988',travel_steps:[10000,10000,10000],steps_per_mm:[200,200,200],mechanics_confirmed:false,settle_ms:300,move_timeout_s:90},stage:{},profiles:[],job:{active:false},ports:[],connectedMicroscope:'',busy:false,error:'',preview:'',target:[0,0,0],profileName:'',positions:'',divisionPrice:'',profileId:'',z:null,grid:{x:0,y:0,columns:2,rows:2,dx:1000,dy:1000},timer:null,generation:0,reading:false,ownedJob:'',notifiedJob:'',settingsLoaded:false,disposed:false};},
  computed:{
    simulated(){return this.connected ? this.stage.mode==='simulator' : this.settings.mode==='simulator';},
    gridPitch(){return (this.grid.dx/this.settings.steps_per_mm[0]*1000).toFixed(1)+' × '+(this.grid.dy/this.settings.steps_per_mm[1]*1000).toFixed(1)+' мкм';},
    connected(){return !!this.stage.connected && this.connectedMicroscope===this.microscope?.name;},
    locked(){return this.busy || this.job.active || this.disabled || !this.active;},
    selectedProfile(){return this.profiles.find(p=>p.id===this.profileId)||null;},
    selectedPoint(){return this.selectedProfile?.points.find(p=>p.z===this.z)||null;},
    fieldOfView(){const p=this.selectedPoint;return p ? (p.width*p.division_um/p.coefficient).toFixed(1)+' × '+(p.height*p.division_um/p.coefficient).toFixed(1)+' мкм' : 'выберите профиль и Z';},
    gridFields(){return [{key:'x',label:'Начало X, шагов',min:0},{key:'y',label:'Начало Y, шагов',min:0},{key:'columns',label:'Столбцов',min:1},{key:'rows',label:'Строк',min:1},{key:'dx',label:'Шаг X, импульсов',min:1},{key:'dy',label:'Шаг Y, импульсов',min:1}];},
    statusLabel(){if(!this.connected)return 'Стол отключён';if(this.stage.configured===false)return 'Прошивка ожидает настройки инженером';return this.stage.homed ? 'Ноль найден' : 'Требуется поиск нуля';},
    jobLabel(){return {running:'Выполняется',stopping:'Остановка…',done:'Готово',cancelled:'Остановлено',error:'Ошибка',idle:'Ожидание'}[this.job.status]||this.job.status;},
  },
  watch:{
    active(value){if(value)this.refresh();else if(this.ownedJob && this.job.active)this.stop();},
    'microscope.name'(){++this.generation;this.settingsLoaded=false;this.profileId='';this.z=null;this.preview='';if(this.active)this.refresh();},
  },
  mounted(){if(this.active)this.refresh();},
  beforeUnmount(){this.disposed=true;++this.generation;clearTimeout(this.timer);if(this.ownedJob && this.job.active)api.stopStage();},
  methods:{
    async refresh(){
      clearTimeout(this.timer);
      if(this.disposed || this.reading || !this.microscope?.name)return;
      this.reading=true;const generation=this.generation;
      try{
        const res=await api.getStageState(this.microscope.name);
        if(generation!==this.generation)return;
        if(!res.ok){this.error=res.error;return;}
        if(!this.settingsLoaded){this.settings=res.settings;this.settingsLoaded=true;}
        this.stage=res.stage;this.profiles=res.profiles;this.connectedMicroscope=res.connected_microscope;this.job=res.job;
        this.$root.stageBusy=!!this.job.active;
        if(this.job.preview)this.preview=this.job.preview;
        if(this.job.id && !this.job.active && this.notifiedJob!==this.job.id){
          this.notifiedJob=this.job.id;
          if(this.job.kind==='scan')this.$emit('scan-updated',{...this.job,microscope:this.microscope.name});
          if(this.job.kind==='profile' && this.job.status==='done'){
            const p=this.job.result?.profile;if(p){this.profileId=p.id;this.selectProfile();this.$emit('profile-ready',p);}
          }
          this.ownedJob='';
        }
      }finally{
        this.reading=false;
        if(!this.disposed && (this.active || this.job.active))this.timer=setTimeout(()=>this.refresh(),400);
      }
    },
    async saveSettings(){if(this.locked)return;this.busy=true;this.error='';try{const r=await api.saveStageSettings(this.microscope.name,this.settings);if(!r.ok)this.error=r.error;else this.settings=r.settings;}finally{this.busy=false;await this.refresh();}},
    async findPorts(){this.error='';const r=await api.getStagePorts();if(r.ok)this.ports=r.ports;else this.error=r.error;},
    async disconnect(){if(this.locked)return;const r=await api.disconnectStage();if(!r.ok)this.error=r.error;else {this.job=r.job;this.$root.stageBusy=!!r.job.active;}await this.refresh();},
    async start(kind){
      if(this.locked)return;
      let params={};
      if(kind==='move')params={xyz:this.target.slice()};
      if(kind==='profile')params={name:this.profileName,positions:this.positions.split(',').map(v=>v.trim()==='' ? null : Number(v.trim())),division_price:this.divisionPrice};
      if(kind==='scan')params={...this.grid,profile_id:this.profileId,z:this.z};
      this.busy=true;this.error='';
      try{const r=await api.startStageJob(this.microscope.name,kind,params);if(!r.ok){this.error=r.error;return;}this.job=r.job;this.ownedJob=r.job.id;this.$root.stageBusy=!!r.job.active;}finally{this.busy=false;}
      await this.refresh();
    },
    async stop(){const r=await api.stopStage();if(!r.ok)this.error=r.error;await this.refresh();},
    selectProfile(){this.z=this.selectedProfile?.points[0]?.z ?? null;this.preview='';},
    async loadScaleImage(){if(!this.selectedPoint)return;const id=this.profileId,z=this.z;const r=await api.getStageProfileImage(id,z);if(id!==this.profileId || z!==this.z)return;if(r.ok)this.preview=r.data;else this.error=r.error;},
  },
};
