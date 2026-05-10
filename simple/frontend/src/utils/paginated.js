export const DEFAULT_PAGE_SIZE = 20
export const LOOKUP_PAGE_SIZE = 200
export const PAGE_SIZE_OPTIONS = [10, 20, 50, 100]

export function unpackPaginated(data) {
  if (Array.isArray(data)) {
    return {
      items: data,
      count: data.length,
      next: null,
      previous: null,
    }
  }

  const items = data?.results || []
  return {
    items,
    count: Number(data?.count ?? items.length ?? 0),
    next: data?.next || null,
    previous: data?.previous || null,
  }
}
