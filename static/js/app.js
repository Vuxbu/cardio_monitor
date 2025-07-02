const socket = io();

const elements = {
    hr: document.getElementById('hr-value'),
    speed: document.getElementById('speed-value')
};

socket.on('data_update', (data) => {
    const element = elements[data.type];
    if (element) {
        element.textContent = data.value || '--';
        element.classList.add('pulse');
        setTimeout(() => element.classList.remove('pulse'), 500);
    }
});