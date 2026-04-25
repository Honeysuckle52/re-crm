/**
 * Общие форматтеры для всего фронтенда.
 *
 * Зачем отдельный модуль:
 *   До рефакторинга функции formatMoney/formatDate/formatDateShort
 *   были скопированы в десяток .vue-файлов с микро-различиями
 *   (где-то возвращали '—', где-то '0', где-то полный formatLocale).
 *   Любая правка форматирования (например, переход на другую валюту
 *   или формат даты) требовала пройти все view-шки. Теперь все
 *   импортируют отсюда и логика правится в одном месте.
 *
 *   Поведение каждой функции сохранено идентичным её прежним
 *   локальным копиям — менять логику в рамках задачи нельзя.
 */

/**
 * Форматирует число в денежный формат локали ru-RU.
 *
 * @param {number|string|null|undefined} value
 * @param {string} [empty='—'] - что вернуть для falsy-значения (0, null, undefined, '').
 *   В Dashboard.vue/PropertyDetail.vue/Deals.vue/PropertyCard.vue
 *   раньше возвращали '0' — для совместимости передавайте `'0'`.
 * @returns {string}
 */
export function formatMoney(value, empty = '—') {
  if (!value) return empty
  return new Intl.NumberFormat('ru-RU').format(value)
}

/**
 * Краткая дата-время: «DD.MM HH:MM» в локали ru-RU.
 * Используется в Tasks.vue, TaskWorkflow.vue, CurrentTaskWidget.vue.
 *
 * @param {string|number|Date|null|undefined} value
 * @returns {string}
 */
export function formatDateShort(value) {
  if (!value) return ''
  return new Date(value).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * Полная локализованная дата-время ru-RU (как `toLocaleString` без опций).
 * Используется в RequestDetail.vue.
 *
 * @param {string|number|Date|null|undefined} value
 * @returns {string}
 */
export function formatDate(value) {
  if (!value) return ''
  return new Date(value).toLocaleString('ru-RU')
}
