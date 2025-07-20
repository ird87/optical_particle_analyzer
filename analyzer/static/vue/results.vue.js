window.resultsMixin = {
  delimiters: ['[[', ']]'],
  data() {
    return {
      params: [
        { key: 'perimeter', label: 'Периметр' },
        { key: 'area', label: 'Площадь' },
        { key: 'width', label: 'Ширина' },
        { key: 'length', label: 'Длина' },
        { key: 'dek', label: 'ДЭК' }
      ],
      visible: {
        perimeter: true, area: false, width: false, length: false, dek: false
      }
    };
  },
  computed: {
    selectedResearch() { return this.$root.selectedResearch; },
    averages() { return this.$root.averages || {}; },
    results() { return this.$root.results || []; }
  },
  methods: {
    formatDate(date) {
      if (!date) return '-';
      const d = new Date(date);
      return d.toLocaleString('ru-RU');
    },
    toggle(key) {
      this.visible[key] = !this.visible[key];
      if (this.visible[key]) this.$nextTick(() => this.renderHistogram(key));
    },
    renderHistogram(param) {
      if (!window.Chart) return;
      const data = this.results.map(r => r[param]);
      const ctx = document.getElementById('hist-' + param).getContext('2d');
      if (ctx._chart) ctx._chart.destroy();
      ctx._chart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: data.map((_, i) => String(i + 1)),
          datasets: [{ label: param, data, backgroundColor: '#5e9efb' }]
        },
        options: {
          plugins: { legend: { display: false } },
          scales: { y: { beginAtZero: true } },
          responsive: true,
          maintainAspectRatio: false
        }
      });
    }
  },
  mounted() {
    this.$nextTick(() => this.renderHistogram('perimeter'));
  },
  watch: {
    results() {
      for (const param of this.params)
        if (this.visible[param.key]) this.renderHistogram(param.key);
    }
  }
};
