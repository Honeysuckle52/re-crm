import { defineStore } from 'pinia'

let uid = 0

const FIELD_LABELS = {
  title: 'Заголовок',
  description: 'Описание',
  assignee: 'Исполнитель',
  client: 'Клиент',
  client_profile: 'Клиент',
  property: 'Объект',
  request: 'Заявка',
  task_type: 'Тип задачи',
  priority: 'Приоритет',
  due_date: 'Срок',
  status: 'Статус',
  result: 'Результат',
  viewing_date: 'Дата и время показа',
  note: 'Комментарий',
}

function isHtmlErrorResponse(value) {
  if (typeof value !== 'string') return false
  const normalized = value.trim().toLowerCase()
  return normalized.startsWith('<!doctype html') || normalized.startsWith('<html')
}

function prettifyFieldName(field) {
  if (!field) return ''
  if (FIELD_LABELS[field]) return FIELD_LABELS[field]
  const normalized = String(field)
    .replace(/\[\d+\]/g, '')
    .replace(/\./g, ' ')
    .replace(/_/g, ' ')
    .trim()
  if (!normalized) return ''
  return normalized.charAt(0).toUpperCase() + normalized.slice(1)
}

function collectErrorEntries(payload, field = '') {
  if (payload === null || payload === undefined) return []
  if (typeof payload === 'string') {
    const message = payload.trim()
    return message ? [{ field, message }] : []
  }
  if (Array.isArray(payload)) {
    return payload.flatMap(item => collectErrorEntries(item, field))
  }
  if (typeof payload === 'object') {
    return Object.entries(payload).flatMap(([key, value]) => {
      if (key === 'detail' || key === 'non_field_errors') {
        return collectErrorEntries(value, '')
      }
      return collectErrorEntries(value, key)
    })
  }
  return [{ field, message: String(payload) }]
}

function formatErrorEntries(entries) {
  const seen = new Set()
  const messages = []
  entries.forEach(({ field, message }) => {
    const normalizedMessage = String(message || '').trim()
    if (!normalizedMessage) return
    const label = prettifyFieldName(field)
    const text = label ? `${label}: ${normalizedMessage}` : normalizedMessage
    if (seen.has(text)) return
    seen.add(text)
    messages.push(text)
  })
  return messages.join(' • ')
}

function htmlErrorMessage(status, fallback) {
  if (status === 400) {
    return 'Сервер отклонил запрос до обработки формы. Проверьте адрес CRM, обновите страницу и попробуйте ещё раз.'
  }
  if (status && status >= 500) {
    return 'Сервер временно недоступен или вернул внутреннюю ошибку. Попробуйте ещё раз.'
  }
  return fallback
}

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

export function extractError (err, fallback = 'Что-то пошло не так') {
  const data = err?.response?.data
  const status = err?.response?.status
  if (!data) {
    if (err?.code === 'ERR_NETWORK' || err?.message === 'Network Error') {
      if (typeof navigator !== 'undefined' && navigator.onLine === false) {
        return 'Нет подключения к интернету. Проверьте сеть и попробуйте ещё раз.'
      }
      return 'Сервер недоступен или соединение было прервано. Повторите попытку.'
    }
    if (isHtmlErrorResponse(err?.message)) {
      return htmlErrorMessage(status, fallback)
    }
    return err?.message || fallback
  }
  if (typeof data === 'string') {
    return isHtmlErrorResponse(data) ? htmlErrorMessage(status, fallback) : data
  }
  if (data.detail) return data.detail
  const formatted = formatErrorEntries(collectErrorEntries(data))
  if (formatted) return formatted
  const first = Object.values(data)[0]
  if (Array.isArray(first) && first.length) return String(first[0])
  if (typeof first === 'string') return first
  return fallback
}
