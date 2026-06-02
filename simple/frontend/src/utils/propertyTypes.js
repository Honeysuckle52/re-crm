export const PROPERTY_TYPES_WITHOUT_ROOMS = ['office', 'warehouse']
export const PROPERTY_TYPES_WITHOUT_FLOOR = ['house', 'warehouse']
export const PROPERTY_TYPES_WITHOUT_TOTAL_FLOORS = ['warehouse']

export function propertyTypeUsesRooms(type) {
  return !PROPERTY_TYPES_WITHOUT_ROOMS.includes(type)
}

export function propertyTypeUsesFloor(type) {
  return !PROPERTY_TYPES_WITHOUT_FLOOR.includes(type)
}

export function propertyTypeUsesTotalFloors(type) {
  return !PROPERTY_TYPES_WITHOUT_TOTAL_FLOORS.includes(type)
}

export function formatRoomsValue(type, roomsCount) {
  return propertyTypeUsesRooms(type) ? (roomsCount || '—') : 'Не применяется'
}
