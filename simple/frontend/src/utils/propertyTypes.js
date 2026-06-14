const PROPERTY_TYPE_OPTIONS = [
  { value: 'apartment', label: 'Квартира' },
  { value: 'house', label: 'Дом' },
  { value: 'commercial', label: 'Коммерческая недвижимость' },
  { value: 'land', label: 'Земельный участок' },
  { value: 'garage', label: 'Гараж' },
  { value: 'room', label: 'Комната' },
]

const PROPERTY_TYPE_LABELS = PROPERTY_TYPE_OPTIONS.reduce((acc, item) => {
  acc[item.value] = item.label
  return acc
}, {
  office: 'Коммерческая недвижимость',
  warehouse: 'Коммерческая недвижимость',
})

const PROPERTY_TYPES_WITH_ROOMS = new Set(['apartment', 'house', 'room'])
const PROPERTY_TYPES_WITH_FLOOR = new Set(['apartment', 'room'])
const PROPERTY_TYPES_WITH_TOTAL_FLOORS = new Set(['apartment', 'house', 'room'])
const PROPERTY_TYPES_WITH_AREA_RANGE = new Set(['commercial', 'land', 'garage'])

export const PROPERTY_TYPE_VALUES = PROPERTY_TYPE_OPTIONS.map((item) => item.value)
export { PROPERTY_TYPE_OPTIONS }

export function normalizePropertyType(value) {
  const code = (value || '').toString().trim()
  if (!code) return ''
  if (code === 'office' || code === 'warehouse') return 'commercial'
  return code
}

export function propertyTypeLabel(value) {
  const code = normalizePropertyType(value)
  return PROPERTY_TYPE_LABELS[code] || PROPERTY_TYPE_LABELS[value] || '—'
}

export function propertyTypeUsesRooms(value) {
  return PROPERTY_TYPES_WITH_ROOMS.has(normalizePropertyType(value))
}

export function propertyTypeUsesFloor(value) {
  return PROPERTY_TYPES_WITH_FLOOR.has(normalizePropertyType(value))
}

export function propertyTypeUsesTotalFloors(value) {
  return PROPERTY_TYPES_WITH_TOTAL_FLOORS.has(normalizePropertyType(value))
}

export function propertyTypeUsesAreaRange(value) {
  return PROPERTY_TYPES_WITH_AREA_RANGE.has(normalizePropertyType(value))
}

export function formatRoomsValue(propertyType, roomsCount) {
  if (!propertyTypeUsesRooms(propertyType)) return '—'
  if (roomsCount === null || roomsCount === undefined || roomsCount === '') return '—'
  return `${roomsCount}-комн.`
}
