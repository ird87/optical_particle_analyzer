const app = Vue.createApp({
    delimiters: ['[[', ']]'],
    data() {
        return {
            currentTab: 'analyze', // Вкладка по умолчанию
            microscopes: null, // Передача данных из context_processors
        };
    },
    methods: {
        switchTab(tab) {
            this.currentTab = tab;
        },
    },
    mounted() {
        const microscopesData = document.getElementById('app').getAttribute('data-microscopes');
        console.log(microscopesData);
        this.microscopes = JSON.parse(microscopesData);
    },
});

app.mixin(window.analyzeMixin);
app.mixin(window.calibrationMixin);
app.mount('#app');
