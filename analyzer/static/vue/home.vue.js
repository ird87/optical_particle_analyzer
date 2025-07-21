const app = Vue.createApp({
    delimiters: ['[[', ']]'],
    data() {
        return {
            currentTab: 'analyze', // Вкладка по умолчанию
            microscopes: null, // Передача данных из context_processors
            divisionPrices: null, // Передача данных из context_processors
            results: [],
            averages: {},
            selectedResearch: null, // Выбранное исследование
            analyzeSelectedCalibration: null,
        };
    },
    computed: {
        resultsAvailable() {
            const hasResults = Array.isArray(this.results) && this.results.length > 0;
            const avg = this.averages || {};
            const hasAverages = ['perimeter','area','width','length','dek']
                .every(k => typeof avg[k] === 'number' && !isNaN(avg[k]));
            return hasResults && hasAverages;
        }
    },
    methods: {
        switchTab(tab) {
            if (tab === 'results' && !this.resultsAvailable) return;
            this.currentTab = tab;
        },
    },
    mounted() {
        const microscopesData = document.getElementById('app').getAttribute('data-microscopes');
        this.microscopes = JSON.parse(microscopesData);

        const selectedFields1 = this.microscopes.map(microscope => ({
            name: microscope.name,
            localizedType: microscope.type_localized
        }));
        console.log(selectedFields1);

        const divisionPricesData = document.getElementById('app').getAttribute('data-division-prices');
        this.divisionPrices = JSON.parse(divisionPricesData);

        // Выборка нескольких полей
         const selectedFields2 = this.divisionPrices.map(division_price => ({
        name: division_price.name,
        localizedType: division_price.value
    }));
    console.log(selectedFields2);
    },
});

app.mixin(window.analyzeMixin);
app.mixin(window.resultsMixin);
app.mixin(window.calibrationMixin);
const vm = app.mount('#app');
window.app = vm;
