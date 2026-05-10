export function resolveDownloadName(contentDisposition, fallback) {
  const match = /filename=\"([^\"]+)\"/i.exec(contentDisposition || '')
  return match?.[1] || fallback
}

export function triggerBlobDownload(blob, filename) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

export function downloadBlobResponse(response, fallbackName) {
  const blob = new Blob([response.data], {
    type: response.headers['content-type'] || 'application/octet-stream',
  })
  triggerBlobDownload(
    blob,
    resolveDownloadName(response.headers['content-disposition'], fallbackName),
  )
}
