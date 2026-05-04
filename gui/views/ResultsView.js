window.ResultsView = {
  template: `
    <div>
      <!-- Заголовок -->
      <h5 class="mt-2">
        Результат: <span class="fw-normal">{{ $root.selectedResearch?.name || '-' }}</span>
      </h5>

      <!-- Информационная строка -->
      <div class="border px-3 py-1 mb-2 bg-light">
        <div class="row gy-2 align-items-end">
          <div class="col-md-3">
            <div class="small text-muted">Сотрудник</div>
            <div class="fw-semibold fs-5">{{ $root.selectedResearch?.employee || '-' }}</div>
          </div>
          <div class="col-md-3">
            <div class="small text-muted">Микроскоп</div>
            <div class="fs-5">{{ $root.selectedResearch?.microscope || '-' }}</div>
          </div>
          <div class="col-md-3">
            <div class="small text-muted">Калибровка</div>
            <div class="fs-5">{{ calibrationLabel }}</div>
          </div>
          <div class="col-md-3">
            <div class="small text-muted">Дата</div>
            <div class="fs-5">{{ $root.formatDate($root.selectedResearch?.date) }}</div>
          </div>
        </div>
      </div>

      <!-- Параметры с гистограммами -->
      <div class="results-scroll p-3 pt-0">

        <h6 class="mt-3 mb-3 d-flex align-items-center justify-content-between">
          <span>Распределение параметров</span>
          <span style="font-size:1.6rem;line-height:1;padding:.2rem .6rem .1rem;cursor:pointer;"
                @click="toggleAll">
            {{ toggleAllVisible ? '▲' : '▼' }}
          </span>
        </h6>

        <!-- Количество диапазонов -->
        <div class="d-flex align-items-center mb-3 gap-2" style="max-width:260px;">
          <label class="form-label mb-0 text-nowrap small">Диапазонов:</label>
          <input type="number" min="2" max="100" v-model.number="histogramBins"
                 class="form-control form-control-sm" style="width:80px;">
          <button class="btn btn-sm btn-outline-secondary" @click="redrawAll">Обновить</button>
        </div>

        <div v-for="param in params" :key="param.key" class="border mb-3 bg-white">
          <!-- Заголовок секции -->
          <div class="d-flex justify-content-between align-items-center px-3 py-2"
               style="cursor:pointer;user-select:none;"
               @click="toggle(param.key)">
            <span class="fw-semibold" style="font-size:1.1rem;">
              {{ param.label }}
              <span class="small text-muted ms-3">
                Среднее: <b>{{ ($root.averages[param.key] ?? 0).toFixed(2) }}</b>
              </span>
            </span>
            <span style="font-size:1.4rem;">{{ visible[param.key] ? '▲' : '▼' }}</span>
          </div>

          <!-- Гистограмма -->
          <div v-show="visible[param.key]" class="px-3 pb-2">
            <canvas :id="'hist-' + param.key" class="w-100"
                    style="min-height:200px;max-height:280px;"></canvas>
          </div>
        </div>
      </div>
    </div>
  `,

  data() {
    return {
      params: [
        { key: 'perimeter', label: 'Периметр' },
        { key: 'area',      label: 'Площадь' },
        { key: 'width',     label: 'Ширина' },
        { key: 'length',    label: 'Длина' },
        { key: 'dek',       label: 'Диаметр эквивалентного круга' },
      ],
      visible: { perimeter: false, area: false, width: false, length: false, dek: false },
      toggleAllVisible: false,
      histogramBins:    20,
    };
  },

  computed: {
    calibrationLabel() {
      const c = this.$root.analyzeSelectedCalibration;
      if (!c) return '-';
      return c.name + (c.coefficient != null ? ` (k=${Number(c.coefficient).toFixed(3)})` : '');
    },
  },

  watch: {
    '$root.results'() {
      this.$nextTick(() => this.redrawAll());
    },
  },

  methods: {
    toggle(key) {
      this.visible[key] = !this.visible[key];
      if (this.visible[key]) this.$nextTick(() => this.renderHistogram(key));
    },

    toggleAll() {
      const next = !this.toggleAllVisible;
      this.toggleAllVisible = next;
      for (const p of this.params) this.visible[p.key] = next;
      if (next) this.$nextTick(() => { for (const p of this.params) this.renderHistogram(p.key); });
    },

    redrawAll() {
      this.$nextTick(() => {
        for (const p of this.params) {
          if (this.visible[p.key]) this.renderHistogram(p.key);
        }
      });
    },

    // ------------------------------------------------------------------
    // Гистограмма
    // ------------------------------------------------------------------
    createBins(minVal, maxVal, numBins) {
      if (minVal === maxVal) return [{ start: minVal, end: maxVal, label: minVal.toFixed(2) }];
      const step = (maxVal - minVal) / numBins;
      return Array.from({ length: numBins }, (_, i) => {
        const start = minVal + i * step;
        const end   = minVal + (i + 1) * step;
        return { start, end, label: `${start.toFixed(2)} – ${end.toFixed(2)}` };
      });
    },

    distributeToBins(data, bins) {
      const counts = new Array(bins.length).fill(0);
      for (const v of data) {
        for (let i = 0; i < bins.length; i++) {
          const { start, end } = bins[i];
          const inBin = i < bins.length - 1 ? (v >= start && v < end) : (v >= start && v <= end);
          if (inBin) { counts[i]++; break; }
        }
      }
      return counts;
    },

    renderHistogram(param) {
      if (!window.Chart) return;
      const dataArray = (this.$root.results || [])
        .map(r => r[param])
        .filter(v => typeof v === 'number' && !isNaN(v));
      if (dataArray.length === 0) return;

      const minVal = Math.min(...dataArray);
      const maxVal = Math.max(...dataArray);
      const bins   = this.createBins(minVal, maxVal, this.histogramBins);
      const counts = this.distributeToBins(dataArray, bins);
      const maxCount = Math.max(...counts);

      const elem = document.getElementById('hist-' + param);
      if (!elem) return;
      const ctx = elem.getContext('2d');
      if (ctx._chart) ctx._chart.destroy();

      ctx._chart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: bins.map(b => b.label),
          datasets: [{
            label:           'Количество значений',
            data:            counts,
            backgroundColor: '#5a99fa',
            borderColor:     '#4285f4',
            borderWidth:     1,
          }],
        },
        plugins: [{
          id: 'datalabels',
          afterDatasetsDraw(chart) {
            const ctx = chart.ctx;
            ctx.save();
            ctx.font          = 'bold 12px Arial';
            ctx.fillStyle     = '#000';
            ctx.textAlign     = 'center';
            ctx.textBaseline  = 'bottom';
            chart.data.datasets.forEach((dataset, i) => {
              chart.getDatasetMeta(i).data.forEach((bar, idx) => {
                if (dataset.data[idx] > 0) ctx.fillText(dataset.data[idx], bar.x, bar.y - 5);
              });
            });
            ctx.restore();
          },
        }],
        options: {
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                title: ctx => `Диапазон: ${ctx[0].label}`,
                label: ctx => `Количество: ${ctx.parsed.y}`,
              },
            },
          },
          scales: {
            y: {
              beginAtZero: true,
              suggestedMax: maxCount > 0 ? Math.ceil(maxCount * 1.15) : 10,
              ticks: { stepSize: 1 },
              title: { display: true, text: 'Количество значений' },
            },
            x: { title: { display: true, text: 'Диапазоны значений' } },
          },
          responsive:          true,
          maintainAspectRatio: false,
        },
      });
    },
  },
};
