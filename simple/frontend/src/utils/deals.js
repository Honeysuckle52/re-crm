export function dealContractQueueActive(deal) {
  return ['pending', 'processing'].includes(deal?.contract_status)
}

export function dealContractStatusLabel(deal) {
  if (!deal) return 'Без PDF'
  if (deal.contract_status === 'pending') return 'В очереди'
  if (deal.contract_status === 'processing') return 'Формируется'
  if (deal.contract_status === 'failed') return 'Ошибка PDF'
  if (deal.contract_url || deal.contract_status === 'ready') return 'Готов'
  return 'Без PDF'
}

export function dealContractStatusHint(deal) {
  if (!deal) return ''
  if (deal.contract_status === 'pending') {
    return 'Договор уже поставлен в очередь на генерацию.'
  }
  if (deal.contract_status === 'processing') {
    return 'Договор формируется в фоновом процессе.'
  }
  if (deal.contract_status === 'failed') {
    return deal.contract_error_message || 'Предыдущая генерация договора завершилась ошибкой.'
  }
  if (deal.contract_url || deal.contract_status === 'ready') {
    return 'PDF-договор уже готов к скачиванию.'
  }
  return 'PDF ещё не поставлен в очередь на генерацию.'
}

export function dealStatusClass(name) {
  const normalized = (name || '').toLowerCase()
  if (normalized.includes('заверш')) return 'tag--accent'
  if (normalized.includes('отмен')) return 'deal-status--cancelled'
  return ''
}
