const app = Vue.createApp({
    delimiters: ['[[', ']]'],
    data() {
        return {
            currentTab: 'analyze', // Вкладка по умолчанию
        };
    },
    methods: {
        switchTab(tab) {
            this.currentTab = tab;
        },
    },
    mounted() {

    },
});

app.mixin(window.analyzeMixin);
app.mount('#app');
