window.HomeView = {
  template: `
    <div>
      <div class="d-flex justify-content-between align-items-center mb-3 mt-2">
        <h5 class="mb-0">Исследования</h5>
        <button class="btn btn-primary btn-sm" @click="newResearch">+ Новое исследование</button>
      </div>

      <div v-if="loading" class="text-muted">Загрузка...</div>

      <div v-else-if="researches.length === 0" class="text-muted fst-italic">
        Нет сохранённых исследований.
      </div>

      <table v-else class="table table-hover table-sm align-middle">
        <thead class="table-light">
          <tr>
            <th>#</th>
            <th>Название</th>
            <th>Сотрудник</th>
            <th>Микроскоп</th>
            <th>Дата</th>
            <th class="text-end">Ср. ДЭК</th>
            <th class="text-end">Ср. периметр</th>
            <th class="text-end">Ср. площадь</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in researches" :key="r.id">
            <td class="text-muted">{{ r.id }}</td>
            <td>{{ r.name }}</td>
            <td>{{ r.employee }}</td>
            <td>{{ r.microscope }}</td>
            <td>{{ $root.formatDate(r.date) }}</td>
            <td class="text-end">{{ r.average_dek }}</td>
            <td class="text-end">{{ r.average_perimeter }}</td>
            <td class="text-end">{{ r.average_area }}</td>
            <td class="text-end text-nowrap">
              <button class="btn btn-sm btn-outline-primary me-1" @click="loadResearch(r.id)">Открыть</button>
              <button class="btn btn-sm btn-outline-danger"       @click="deleteResearch(r.id)">Удалить</button>
            </td>
          </tr>
        </tbody>
      </table>

      <div v-if="errorMsg" class="alert alert-danger mt-2">{{ errorMsg }}</div>
    </div>
  `,

  data() {
    return {
      researches: [],
      loading:    true,
      errorMsg:   '',
    };
  },

  mounted() {
    this.fetchResearches();
  },

  watch: {
    '$root.currentTab'(tab) {
      if (tab === 'home') this.fetchResearches();
    },
  },

  methods: {
    async fetchResearches() {
      this.loading  = true;
      this.errorMsg = '';
      const res = await api.getResearches();
      if (res.ok) {
        this.researches = res.researches;
      } else {
        this.errorMsg = 'Не удалось загрузить список исследований.';
      }
      this.loading = false;
    },

    async newResearch() {
      const res = await api.newResearch();
      if (!res.ok) { this.errorMsg = 'Ошибка создания нового исследования.'; return; }

      // Сбрасываем общее состояние
      this.$root.selectedResearch           = null;
      this.$root.analyzeSelectedCalibration = null;
      this.$root.results                    = [];
      this.$root.averages                   = {};
      this.$root.analyzeResetKey++;

      this.$root.currentTab = 'analyze';
    },

    async loadResearch(id) {
      const res = await api.loadResearch(id);
      if (!res.ok) { this.errorMsg = 'Не удалось загрузить исследование.'; return; }

      const r = res.research;

      this.$root.selectedResearch = r;
      this.$root.results          = r.contours || [];
      this.$root.averages         = {
        perimeter: r.average_perimeter,
        area:      r.average_area,
        width:     r.average_width,
        length:    r.average_length,
        dek:       r.average_dek,
      };
      this.$root.analyzeSelectedCalibration = r.calibration_id
        ? { id: r.calibration_id }
        : null;

      // Результаты есть — сразу открываем вкладку результатов
      this.$root.currentTab = (r.contours && r.contours.length > 0) ? 'results' : 'analyze';
    },

    async deleteResearch(id) {
      if (!confirm('Удалить исследование? Это действие необратимо.')) return;
      const res = await api.deleteResearch(id);
      if (res.ok) {
        this.researches = this.researches.filter(r => r.id !== id);
      } else {
        this.errorMsg = 'Не удалось удалить исследование.';
      }
    },
  },
};
