window.ResultsView = {
  template: `
    <div class="research-results">
      <div class="workspace-heading">
        <div><h6 class="mb-1">{{ $root.researchState?.name || $root.selectedResearch?.name || 'Результаты исследования' }}</h6><span class="small" :class="$root.researchState?.saved ? 'text-success' : 'text-muted'">{{ $root.researchState?.saved ? 'Сохранено' : 'Есть несохранённые изменения' }}</span></div>
        <div class="d-flex gap-2">
          <button class="btn btn-sm btn-outline-primary" @click="$root.currentTab = 'analyze'">Вернуться к снимкам</button>
          <button class="btn btn-sm btn-success" :disabled="$root.researchState?.saveDisabled || $root.researchState?.working" @click="$root.saveActiveResearch()">Сохранить исследование</button>
        </div>
      </div>
      <div v-if="$root.researchState?.error" class="alert alert-danger py-2" role="alert">{{ $root.researchState.error }}</div>
      <div v-if="!$root.results.length" class="workspace-empty border rounded p-3">Результаты отсутствуют или снимки изменились. Вернитесь к снимкам и выполните анализ.</div>
      <div v-else>
        <div class="results-context border rounded p-2 mb-2">
          <strong>Вся серия: {{ fileCount }} снимков · {{ $root.results.length }} частиц</strong>
          <div class="d-flex flex-wrap gap-3 small text-muted mt-1">
            <span>Сотрудник: {{ $root.researchState?.employee || $root.selectedResearch?.employee || '—' }}</span>
            <span>Микроскоп: {{ $root.researchContext?.microscope || $root.selectedResearch?.microscope || '—' }}</span>
            <span>Калибровка: {{ calibrationLabel }}</span>
            <span>{{ $root.formatDate($root.selectedResearch?.date) }}</span>
          </div>
          <div class="small text-muted mt-1">{{ segmentationLabel }}</div>
          <div v-if="$root.researchState?.status" class="small text-muted mt-1" role="status">{{ $root.researchState.status }}</div>
        </div>
        <div class="results-summary mb-3">
          <div v-for="param in params" :key="param.key" class="border rounded p-2">
            <div class="small text-muted">Среднее · {{ param.label }}</div>
            <strong>{{ formatNumber($root.averages[param.key]) }} <span class="small fw-normal">{{ param.unit }}</span></strong>
          </div>
        </div>
        <div class="d-flex align-items-center flex-wrap gap-2 mb-2">
          <button class="btn btn-sm" :class="view === 'table' ? 'btn-primary' : 'btn-outline-primary'" :aria-pressed="view === 'table'" @click="view = 'table'">Таблица частиц</button>
          <button class="btn btn-sm" :class="view === 'histogram' ? 'btn-primary' : 'btn-outline-primary'" :aria-pressed="view === 'histogram'" @click="view = 'histogram'">Распределение</button>
        </div>
        <div v-if="view === 'table'">
          <div class="results-table-wrap table-responsive border rounded">
            <table class="table table-sm table-bordered mb-0 results-particles">
              <thead class="table-light"><tr><th>№ частицы</th><th v-for="param in params" :key="param.key">{{ param.short || param.label }}, {{ param.unit }}</th></tr></thead>
              <tbody><tr v-for="row in visibleRows" :key="row.contour_number"><td>{{ row.contour_number }}</td><td v-for="param in params" :key="param.key">{{ formatNumber(row[param.key]) }}</td></tr></tbody>
            </table>
          </div>
          <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mt-2 small">
            <span class="text-muted">{{ (safePage - 1) * pageSize + 1 }}–{{ Math.min(safePage * pageSize,$root.results.length) }} из {{ $root.results.length }} частиц всей серии</span>
            <div class="d-flex align-items-center gap-2"><button class="btn btn-sm btn-outline-secondary" :disabled="safePage <= 1" @click="page = safePage - 1">Назад</button><span>{{ safePage }} / {{ pageCount }}</span><button class="btn btn-sm btn-outline-secondary" :disabled="safePage >= pageCount" @click="page = safePage + 1">Далее</button></div>
          </div>
        </div>
        <div v-show="view === 'histogram'" class="border rounded p-2">
          <div class="d-flex flex-wrap gap-2 align-items-end mb-2">
            <div class="results-parameter"><label for="histogram-parameter" class="form-label">Параметр</label><select id="histogram-parameter" v-model="activeParameter" class="form-select form-select-sm"><option v-for="param in params" :key="param.key" :value="param.key">{{ param.label }}, {{ param.unit }}</option></select></div>
            <div><label for="histogram-bins" class="form-label">Диапазоны</label><input id="histogram-bins" type="number" min="2" max="100" step="1" v-model.number="histogramBins" class="form-control form-control-sm histogram-bins" :aria-invalid="!!binsError" aria-describedby="histogram-error"></div>
            <button class="btn btn-sm btn-outline-primary" @click="redrawAll">Построить</button>
          </div>
          <div v-if="binsError" id="histogram-error" class="small text-danger mb-2" role="alert">{{ binsError }}</div>
          <div class="research-histogram"><canvas id="research-histogram" :aria-label="'Распределение: ' + currentParameter.label + ', ' + currentParameter.unit" role="img"></canvas></div>
        </div>
      </div>
    </div>
  `,
  data() {
    return {params:[{key:'perimeter',label:'Периметр',unit:'мкм'},{key:'area',label:'Площадь',unit:'мкм²'},
      {key:'width',label:'Ширина',unit:'мкм'},{key:'length',label:'Длина',unit:'мкм'},
      {key:'dek',label:'Диаметр эквивалентного круга',short:'ДЭК',unit:'мкм'}],
      view:'table',activeParameter:'dek',histogramBins:20,appliedBins:20,binsError:'',page:1,pageSize:50};
  },
  computed: {
    segmentationLabel() {
      const options = this.$root.researchContext?.analysisOptions;
      if (!options) return 'Настройки исходного выделения частиц не сохранены';
      const mode = {auto:'Автоматически',dark:'Тёмные частицы',light:'Светлые частицы',color:'Цветной фон'}[options.mode] || options.mode;
      return 'Выделение: ' + mode + ' · площадь > ' + options.min_area_px + ' пикс² · разделение ' + (options.split_touching ? 'включено' : 'выключено');
    },
    fileCount() { return this.$root.researchState?.fileCount ?? this.$root.researchContext?.fileCount ?? 0; },
    calibrationLabel() {
      const c = this.$root.researchContext?.calibration;
      if (c?.name) return c.name;
      const id = this.$root.selectedResearch?.calibration_id;
      return id ? 'Недоступна · №' + id : '—';
    },
    currentParameter() { return this.params.find(p => p.key === this.activeParameter) || this.params[4]; },
    pageCount() { return Math.max(1,Math.ceil(this.$root.results.length / this.pageSize)); },
    safePage() { return Math.min(Math.max(this.page,1),this.pageCount); },
    visibleRows() { return this.$root.results.slice((this.safePage - 1) * this.pageSize,this.safePage * this.pageSize); },
  },
  watch: {
    '$root.results'() { this.page = 1;this.destroyChart();this.requestChart(); },
    '$root.currentTab'(tab) { if (tab === 'results') this.requestChart(); },
    view() { this.requestChart(); },
    activeParameter() { this.requestChart(); },
  },
  beforeUnmount() { this.destroyChart(); },
  methods: {
    formatNumber(value) {
      if (!Number.isFinite(value)) return '—';
      return value !== 0 && Math.abs(value) < .000001 ? value.toExponential(3) : value.toLocaleString('ru-RU',{maximumFractionDigits:6});
    },
    requestChart() { this.$nextTick(() => { if (this.$root.currentTab === 'results' && this.view === 'histogram') this.renderHistogram(this.activeParameter); }); },
    redrawAll() {
      const value = this.histogramBins;
      if (!Number.isInteger(value) || value < 2 || value > 100) { this.binsError = 'Укажите целое число диапазонов от 2 до 100';return; }
      this.binsError = '';this.appliedBins = value;this.requestChart();
    },
    createBins(minVal,maxVal,numBins) {
      if (!Number.isInteger(numBins) || numBins < 2 || numBins > 100) throw new Error('Число диапазонов должно быть целым от 2 до 100');
      if (!Number.isFinite(minVal) || !Number.isFinite(maxVal) || minVal > maxVal) throw new Error('Некорректные границы распределения');
      if (minVal === maxVal) return [{start:minVal,end:maxVal,label:this.formatNumber(minVal)}];
      const step = (maxVal - minVal) / numBins;
      return Array.from({length:numBins},(_,i) => { const start = minVal + i * step,end = i === numBins - 1 ? maxVal : minVal + (i + 1) * step;return {start,end,label:this.formatNumber(start) + ' – ' + this.formatNumber(end)}; });
    },
    distributeToBins(data,bins) {
      const counts = new Array(bins.length).fill(0);
      for (const value of data) for (let i = 0;i < bins.length;i++) {
        if (value >= bins[i].start && (i === bins.length - 1 ? value <= bins[i].end : value < bins[i].end)) { counts[i]++;break; }
      }
      return counts;
    },
    destroyChart() { if (this._histogramChart) { this._histogramChart.destroy();this._histogramChart = null; } },
    renderHistogram(key) {
      if (!window.Chart || !this.$root.results.length) return;
      const data = this.$root.results.map(row => row[key]).filter(Number.isFinite);
      if (!data.length) { this.destroyChart();return; }
      const min = data.reduce((a,b) => Math.min(a,b),Infinity),max = data.reduce((a,b) => Math.max(a,b),-Infinity);
      const bins = this.createBins(min,max,this.appliedBins),counts = this.distributeToBins(data,bins);
      const canvas = document.getElementById('research-histogram');if (!canvas) return;
      this.destroyChart();
      const param = this.params.find(p => p.key === key);
      this._histogramChart = new window.Chart(canvas.getContext('2d'),{type:'bar',data:{labels:bins.map(b => b.label),datasets:[{label:'Число частиц',data:counts,backgroundColor:'#323b88'}]},
        options:{responsive:true,maintainAspectRatio:false,animation:false,plugins:{legend:{display:false}},scales:{
          x:{title:{display:true,text:param.label + ', ' + param.unit},ticks:{maxTicksLimit:10}},
          y:{beginAtZero:true,ticks:{precision:0},title:{display:true,text:'Число частиц'}},
        }}});
    },
  },
};
