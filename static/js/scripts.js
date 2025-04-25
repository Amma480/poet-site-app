// Показать/скрыть кнопку "Наверх"
window.onscroll = function() {
    let scrollTopButton = document.getElementById('scroll-top');
    if (document.body.scrollTop > 200 || document.documentElement.scrollTop > 200) {
        scrollTopButton.style.display = 'block';
    } else {
        scrollTopButton.style.display = 'none';
    }
};

// Прокрутка наверх
function scrollToTop() {
    window.scrollTo({ top: 0, behavior: 'smooth' });
}