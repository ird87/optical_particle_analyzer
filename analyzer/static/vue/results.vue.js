window.resultsMixin = {
  delimiters: ['[[', ']]'],
  data() {
    return {
      params: [
        { key: 'perimeter', label: 'Периметр' },
        { key: 'area', label: 'Площадь' },
        { key: 'width', label: 'Ширина' },
        { key: 'length', label: 'Длина' },
        { key: 'dek', label: 'Диаметр эквивалентного круга' }
      ],
      visible: {
        perimeter: false,
        area: false,
        width: false,
        length: false,
        dek: false
      },
      toggleAllVisible: false,
      histogramBins: 20 // КДГ - количество диапазонов гистограммы
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

    /**
     * Создает диапазоны для гистограммы
     * @param {number} minVal - минимальное значение
     * @param {number} maxVal - максимальное значение
     * @param {number} numBins - количество диапазонов
     * @returns {Array} массив диапазонов [{start, end, label}, ...]
     */
    createBins(minVal, maxVal, numBins) {
      if (minVal === maxVal) {
        // Если все значения одинаковые
        return [{
          start: minVal,
          end: maxVal,
          label: minVal.toFixed(2)
        }];
      }

      const step = (maxVal - minVal) / numBins;
      const bins = [];

      for (let i = 0; i < numBins; i++) {
        const start = minVal + i * step;
        const end = minVal + (i + 1) * step;

        bins.push({
          start: start,
          end: end,
          label: `${start.toFixed(2)} - ${end.toFixed(2)}`
        });
      }

      return bins;
    },

    /**
     * Распределяет данные по диапазонам
     * @param {Array} data - массив числовых значений
     * @param {Array} bins - массив диапазонов
     * @returns {Array} количество значений в каждом диапазоне
     */
    distributeToBins(data, bins) {
      const counts = new Array(bins.length).fill(0);

      for (const value of data) {
        for (let i = 0; i < bins.length; i++) {
          const bin = bins[i];

          // Стандартная практика: левая граница включается, правая исключается [a, b)
          // Исключение: последний диапазон включает правую границу [a, b]
          if (i < bins.length - 1) {
            if (value >= bin.start && value < bin.end) {
              counts[i]++;
              break;
            }
          } else {
            // Последний диапазон включает правую границу
            if (value >= bin.start && value <= bin.end) {
              counts[i]++;
              break;
            }
          }
        }
      }

      return counts;
    },

    renderHistogram(param) {
  if (!window.Chart) return;

  // Получаем данные для параметра
  let dataArray = this.results.map(r => r[param])
    .filter(v => typeof v === "number" && !isNaN(v));

  if (dataArray.length === 0) return;

  // Находим минимальное и максимальное значения
  const minVal = Math.min(...dataArray);
  const maxVal = Math.max(...dataArray);

  // Создаем диапазоны
  const bins = this.createBins(minVal, maxVal, this.histogramBins);

  // Распределяем данные по диапазонам
  const counts = this.distributeToBins(dataArray, bins);

  // Вычисляем максимальное значение с запасом для подписей
  const maxCount = Math.max(...counts);
  const suggestedMax = maxCount > 0 ? Math.ceil(maxCount * 1.15) : 10;

  // Подготавливаем данные для Chart.js
  const labels = bins.map(bin => bin.label);
  const data = counts;

  // Отрисовка графика
  const elem = document.getElementById('hist-' + param);
  if (!elem) return;
  const ctx = elem.getContext('2d');

  // Удаление старого чарта
  if (ctx._chart) ctx._chart.destroy();

  ctx._chart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Количество значений',
        data,
        backgroundColor: '#5a99fa',
        borderColor: '#4285f4',
        borderWidth: 1
      }]
    },
    plugins: [{
      // Создаем кастомный плагин для отрисовки подписей
      id: 'datalabels',
      afterDatasetsDraw: function(chart) {
        const ctx = chart.ctx;

        ctx.save();
        ctx.font = 'bold 12px Arial';
        ctx.fillStyle = '#000';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'bottom';

        chart.data.datasets.forEach(function(dataset, i) {
          const meta = chart.getDatasetMeta(i);
          meta.data.forEach(function(bar, index) {
            const data = dataset.data[index];
            if (data > 0) {
              ctx.fillText(data, bar.x, bar.y - 5);
            }
          });
        });

        ctx.restore();
      }
    }],
    options: {
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: function(context) {
              return `Диапазон: ${context[0].label}`;
            },
            label: function(context) {
              return `Количество: ${context.parsed.y}`;
            }
          }
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          suggestedMax: suggestedMax,
          ticks: {
            stepSize: 1
          },
          title: {
            display: true,
            text: 'Количество значений'
          }
        },
        x: {
          title: {
            display: true,
            text: 'Диапазоны значений'
          }
        }
      },
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
      for (const param of this.params) {
        if (this.visible[param.key]) this.renderHistogram(param.key);
      }
    }
  }
};
