export function formatMoney(value, empty = '—') {
  if (!value) return empty
  return new Intl.NumberFormat('ru-RU').format(value)
}

export function formatDateShort(value) {
  if (!value) return ''
  return new Date(value).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatDate(value) {
  if (!value) return ''
  return new Date(value).toLocaleString('ru-RU')
}
