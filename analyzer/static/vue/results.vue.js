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
        perimeter: false,
        area: false,
        width: false,
        length: false,
        dek: false
      },
      toggleAllVisible: false
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
    toggleAll() {
      const next = !this.toggleAllVisible;
      for (const param of this.params) {
        this.visible[param.key] = next;
      }
      this.toggleAllVisible = next;
      // отрисовать графики если открываем
      if (next) {
        this.$nextTick(() => {
          for (const param of this.params) {
            if (this.visible[param.key]) this.renderHistogram(param.key);
          }
        });
      }
    },
    renderHistogram(param) {
      if (!window.Chart) return;
      let dataArray = this.results.map(r => r[param])
        .filter(v => typeof v === "number" && !isNaN(v));
      dataArray.sort((a, b) => a - b); // 1. сортировка по возрастанию

      // 2. группировка, если данных больше 100
      let labels = [];
      let data = [];
      const maxBars = 100;
      if (dataArray.length > maxBars) {
        const groupSize = Math.floor(dataArray.length / maxBars);
        let idx = 0;
        for (let i = 0; i < maxBars; i++) {
          let start = idx;
          let end = (i === maxBars - 1) ? dataArray.length : idx + groupSize;
          let group = dataArray.slice(start, end);
          let mean = group.reduce((sum, v) => sum + v, 0) / group.length;
          data.push(mean);
          labels.push(
            group.length === 1
              ? group[0].toFixed(2)
              : `${group[0].toFixed(2)}–${group[group.length - 1].toFixed(2)}`
          );
          idx = end;
        }
      } else {
        data = dataArray;
        labels = dataArray.map(v => v.toFixed(2));
      }

      // Далее стандартный Chart.js
      const elem = document.getElementById('hist-' + param);
      if (!elem) return;
      const ctx = elem.getContext('2d');
      // Удаление старого чарта:
      if (ctx._chart) ctx._chart.destroy();

      ctx._chart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels,
          datasets: [{
            label: param,
            data,
            backgroundColor: '#5a99fa'
          }]
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
