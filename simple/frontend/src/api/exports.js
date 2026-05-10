import api from './index'
import { downloadBlobResponse } from '@/utils/downloads'

async function downloadExport({
  endpoint,
  params = {},
  format = 'csv',
  formatParam = 'export_format',
  fallbackName,
}) {
  const response = await api.get(endpoint, {
    params: {
      ...params,
      [formatParam]: format,
    },
    responseType: 'blob',
  })
  downloadBlobResponse(response, fallbackName)
}

export function exportEntityData(endpoint, format, params = {}, fallbackName = `export.${format}`) {
  return downloadExport({
    endpoint,
    params,
    format,
    formatParam: 'export_format',
    fallbackName,
  })
}

export function exportReportData(endpoint, format, params = {}, fallbackName = `report.${format}`) {
  return downloadExport({
    endpoint,
    params,
    format,
    formatParam: 'export',
    fallbackName,
  })
}
