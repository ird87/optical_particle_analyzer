window.HomeView = {
  template: `
    <div>
      <div class="d-flex justify-content-between align-items-center mb-3 mt-2">
        <h5 class="mb-0">Исследования</h5>
        <button class="btn btn-primary btn-sm" :disabled="$root.researchState?.working" @click="newResearch">+ Новое исследование</button>
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
              <button class="btn btn-sm btn-outline-primary me-1" :disabled="$root.researchState?.working" @click="loadResearch(r.id)">Открыть</button>
              <button class="btn btn-sm btn-outline-danger"       :disabled="$root.researchState?.working" @click="deleteResearch(r.id)">Удалить</button>
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
      const ok = await this.$root.newActiveResearch();
      if (ok) this.$root.currentTab = 'analyze';
      else this.errorMsg = this.$root.researchState?.error || '';
    },
    async loadResearch(id) {
      const ok = await this.$root.openActiveResearch(id);
      if (ok) this.$root.currentTab = this.$root.results.length ? 'results' : 'analyze';
      else this.errorMsg = this.$root.researchState?.error || '';
    },
    async deleteResearch(id) {
      const ok = await this.$root.deleteActiveResearch(id);
      if (ok) this.researches = this.researches.filter(r => r.id !== id);
      else this.errorMsg = this.$root.researchState?.error || '';
    },
  },
};
