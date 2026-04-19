/**
 * Мини-стор тост-уведомлений.
 *
 * Используется вместо штатного ``alert()`` по всему приложению:
 * ошибки API, сообщения об автозакрытии задачи, успех отправки письма
 * и прочие неблокирующие события. Виджет ToastHost (в App.vue)
 * рендерит список и автоматически скрывает тосты по таймеру.
 */
import { defineStore } from 'pinia'

let uid = 0

export const useToastsStore = defineStore('toasts', {
  state: () => ({
    items: [],
  }),
  actions: {
    push ({ type = 'info', text, title = '', timeout = 4000 }) {
      const id = ++uid
      const toast = { id, type, text, title, timeout }
      this.items.push(toast)
      if (timeout > 0) {
        setTimeout(() => this.dismiss(id), timeout)
      }
      return id
    },
    info (text, title = '')    { return this.push({ type: 'info',    text, title }) },
    success (text, title = '') { return this.push({ type: 'success', text, title }) },
    warn (text, title = '')    { return this.push({ type: 'warn',    text, title, timeout: 5500 }) },
    error (text, title = '')   { return this.push({ type: 'error',   text, title, timeout: 7000 }) },
    dismiss (id) {
      this.items = this.items.filter((t) => t.id !== id)
    },
    clear () { this.items = [] },
  },
})

/** Универсальный экстрактор текста ошибки из ответа axios. */
export function extractError (err, fallback = 'Что-то пошло не так') {
  const data = err?.response?.data
  if (!data) return err?.message || fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  // DRF-валидация: { field: ['msg', ...] }
  const first = Object.values(data)[0]
  if (Array.isArray(first) && first.length) return String(first[0])
  if (typeof first === 'string') return first
  return fallback
}
