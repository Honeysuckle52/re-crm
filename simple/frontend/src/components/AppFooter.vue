<template>
  <!--
    Футер CRM. Раньше иконка «домика» была position: absolute и «всплывала»
    над пилюлей. На узких экранах и при частичном скрытии (transition fade,
    v-show, скрытие по роли и т. п.) абсолютный элемент «съезжал» в сторону
    и визуально отрывался от самой пилюли. Переводим её во flex-поток — она
    всегда едет вместе с текстом и никогда не перекрывает надпись «РИЭЛТ».
  -->
  <footer class="footer">
    <span class="footer__icon" aria-hidden="true">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
           stroke="currentColor" stroke-width="2"
           stroke-linecap="round" stroke-linejoin="round">
        <path d="M3 12L12 4l9 8" />
        <path d="M5 10v10h14V10" />
      </svg>
    </span>
    <span class="footer__brand">РИЭЛТ</span>
    <span class="footer__sep" aria-hidden="true"></span>
    <span class="footer__caption">Управление недвижимостью</span>
  </footer>
</template>

<style scoped>
/*
  Никаких position:absolute. Всё в одной flex-строке — значок не может
  «съехать» относительно пилюли ни при какой ширине или анимации.
*/
.footer {
  position: relative;
  margin: 48px 16px 16px;
  display: flex;
  align-items: center;
  gap: 14px;
  background: var(--c-panel);
  color: #fff;
  padding: 14px 24px;
  border-radius: var(--r-pill);
  box-shadow: var(--shadow-2);
  letter-spacing: .1em;
  text-transform: uppercase;
  font-size: 12px;
  min-height: 48px;
}

.footer__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--c-paper);
  color: var(--c-panel);
  box-shadow: var(--shadow-1);
}

.footer__brand {
  font-weight: 700;
  letter-spacing: .16em;
}

.footer__sep {
  flex: 0 0 auto;
  width: 1px;
  height: 18px;
  background: rgba(255, 255, 255, .25);
}

.footer__caption {
  flex: 1 1 auto;
  color: rgba(255, 255, 255, .85);
}

@media (max-width: 720px) {
  .footer {
    padding: 12px 18px;
    font-size: 11px;
    letter-spacing: .06em;
    gap: 10px;
  }
  .footer__icon { width: 32px; height: 32px; }
  .footer__sep { display: none; }
}
</style>
