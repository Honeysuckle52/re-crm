export const requestCloseOutcomes = [
  {
    value: 'completed',
    label: 'Успешно завершена',
    description: 'Закрывает заявку как завершённую и создаёт сделку, если выбран объект или подтверждён вариант.',
  },
  {
    value: 'cancelled',
    label: 'Отменена клиентом',
    description: 'Клиент отказался от обращения или снял заявку самостоятельно.',
  },
  {
    value: 'rejected',
    label: 'Отклонена агентством',
    description: 'Заявка не подходит под условия работы или не берётся в обработку.',
  },
  {
    value: 'lost',
    label: 'Потеряна',
    description: 'Клиент перестал отвечать или ушёл в другой канал продаж.',
  },
]

export const activeRequestStatusCodes = ['open', 'processing']
export const terminalRequestStatusCodes = ['completed', 'cancelled', 'rejected', 'lost']

export function isTerminalRequestStatus (statusCode) {
  return terminalRequestStatusCodes.includes(statusCode)
}

export function canTakeRequest (request) {
  if (!request) return false
  return !request.agent && !isTerminalRequestStatus(request.status_code)
}

export function getRequestCloseSuccessMessage ({ outcome, data, requestId = null }) {
  const requestLabel = requestId ? ` #${requestId}` : ''
  if (outcome === 'completed' && data?.deal?.deal_number) {
    return `Заявка${requestLabel} завершена. Создана сделка ${data.deal.deal_number}, договор поставлен в очередь на генерацию.`
  }

  const messages = {
    completed: `Заявка${requestLabel} завершена`,
    cancelled: `Заявка${requestLabel} отменена`,
    rejected: `Заявка${requestLabel} отклонена`,
    lost: `Заявка${requestLabel} помечена как потерянная`,
  }
  return messages[outcome] || `Заявка${requestLabel} закрыта`
}
