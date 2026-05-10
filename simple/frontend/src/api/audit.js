import api from './index'
import { unpackPaginated } from '@/utils/paginated'

export async function listAuditLogs (params = {}) {
  const { data } = await api.get('/audit-log/', { params })
  return unpackPaginated(data)
}
