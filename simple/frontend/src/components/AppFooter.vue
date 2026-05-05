<template>
  <footer class="footer">
    <div class="footer__meta">
      <span class="footer__icon" aria-hidden="true">
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M3 12L12 4l9 8" />
          <path d="M5 10v10h14V10" />
        </svg>
      </span>
      <span class="footer__brand">РИЭЛТ</span>
      <span class="footer__sep" aria-hidden="true"></span>
      <span class="footer__caption">Управление недвижимостью</span>
    </div>

    <div v-if="auth.isStaff" class="footer__widget">
      <CurrentTaskWidget embedded />
    </div>
  </footer>
</template>

<script setup>
import { useAuthStore } from '../store/auth'
import CurrentTaskWidget from './CurrentTaskWidget.vue'

const auth = useAuthStore()
</script>

<style scoped>
.footer {
  position: relative;
  z-index: 1;
  width: min(var(--content-width), calc(100% - 32px));
  margin: 28px auto 18px;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 20px;
  min-height: 64px;
  border-radius: var(--r-pill);
  border: 1px solid var(--c-border);
  background: linear-gradient(180deg, #124346 0%, #073434 100%);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  box-shadow: var(--shadow-1);
  color: var(--c-text);
  font-size: 13px;
  letter-spacing: 0.02em;
}

.footer__meta {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 14px;
}

.footer__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--grad-control);
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.16);
  box-shadow: 0 8px 20px rgba(4, 24, 22, 0.22);
}

.footer__brand {
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.footer__sep {
  flex: 0 0 auto;
  width: 1px;
  height: 18px;
  background: rgba(120, 216, 206, 0.34);
}

.footer__caption {
  min-width: 0;
  color: var(--c-ink-soft);
  line-height: 1.45;
}

.footer__widget {
  position: relative;
  flex: 0 0 238px;
  width: 238px;
  height: 42px;
  min-width: 238px;
  margin-left: auto;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  overflow: visible;
}

@media (max-width: 960px) {
  .footer {
    align-items: flex-start;
    flex-direction: column;
  }

  .footer__meta,
  .footer__widget {
    width: 100%;
  }

  .footer__widget {
    flex-basis: auto;
    height: 42px;
    min-width: 0;
  }
}

@media (max-width: 720px) {
  .footer {
    width: calc(100% - 18px);
    margin-top: 20px;
    padding: 12px 18px;
    gap: 12px;
    font-size: 12px;
  }

  .footer__meta {
    flex-wrap: wrap;
    gap: 10px;
  }

  .footer__icon {
    width: 32px;
    height: 32px;
  }

  .footer__sep {
    display: none;
  }
}
</style>
