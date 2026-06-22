const DASH = '—'
const COMMERCIAL_ALIAS_CODES = new Set(['office', 'warehouse'])

const PROPERTY_TYPE_OPTIONS = [
  { value: 'apartment', label: 'Квартира' },
  { value: 'house', label: 'Дом' },
  { value: 'commercial', label: 'Коммерческая недвижимость' },
  { value: 'land', label: 'Земельный участок' },
  { value: 'garage', label: 'Гараж' },
  { value: 'room', label: 'Комната' },
]

const PROPERTY_TYPE_SCHEMAS = {
  apartment: {
    label: 'Квартира',
    showBuildingDetails: true,
    showRooms: true,
    showFloor: true,
    showResidentialArea: true,
    showBalcony: true,
    showBathroom: true,
    showRenovation: true,
    showBedrooms: true,
    showPrivateHouseFloors: false,
    showLandArea: false,
    showCommercialDetails: false,
    showResidentialDetails: true,
    showGarageRenovationOnly: false,
    showBuildingMaterialFilter: true,
    showYearBuiltFilter: true,
    showTotalFloorsFilter: false,
    showBathroomFilter: true,
    showRenovationFilter: true,
    showCommercialFilters: false,
    showLandFilters: false,
  },
  house: {
    label: 'Дом',
    showBuildingDetails: true,
    showRooms: true,
    showFloor: false,
    showResidentialArea: true,
    showBalcony: true,
    showBathroom: true,
    showRenovation: true,
    showBedrooms: true,
    showPrivateHouseFloors: true,
    showLandArea: true,
    showCommercialDetails: false,
    showResidentialDetails: true,
    showGarageRenovationOnly: false,
    showBuildingMaterialFilter: true,
    showYearBuiltFilter: true,
    showTotalFloorsFilter: true,
    showBathroomFilter: true,
    showRenovationFilter: true,
    showCommercialFilters: false,
    showLandFilters: true,
  },
  room: {
    label: 'Комната',
    showBuildingDetails: true,
    showRooms: true,
    showFloor: true,
    showResidentialArea: true,
    showBalcony: false,
    showBathroom: true,
    showRenovation: true,
    showBedrooms: true,
    showPrivateHouseFloors: false,
    showLandArea: false,
    showCommercialDetails: false,
    showResidentialDetails: true,
    showGarageRenovationOnly: false,
    showBuildingMaterialFilter: true,
    showYearBuiltFilter: true,
    showTotalFloorsFilter: false,
    showBathroomFilter: true,
    showRenovationFilter: true,
    showCommercialFilters: false,
    showLandFilters: false,
  },
  land: {
    label: 'Земельный участок',
    showBuildingDetails: false,
    showRooms: false,
    showFloor: false,
    showResidentialArea: false,
    showBalcony: false,
    showBathroom: false,
    showRenovation: false,
    showBedrooms: false,
    showPrivateHouseFloors: false,
    showLandArea: true,
    showCommercialDetails: false,
    showResidentialDetails: false,
    showGarageRenovationOnly: false,
    showBuildingMaterialFilter: false,
    showYearBuiltFilter: false,
    showTotalFloorsFilter: false,
    showBathroomFilter: false,
    showRenovationFilter: false,
    showCommercialFilters: false,
    showLandFilters: true,
  },
  garage: {
    label: 'Гараж',
    showBuildingDetails: false,
    showRooms: false,
    showFloor: false,
    showResidentialArea: false,
    showBalcony: false,
    showBathroom: false,
    showRenovation: true,
    showBedrooms: false,
    showPrivateHouseFloors: false,
    showLandArea: false,
    showCommercialDetails: false,
    showResidentialDetails: false,
    showGarageRenovationOnly: true,
    showBuildingMaterialFilter: false,
    showYearBuiltFilter: false,
    showTotalFloorsFilter: false,
    showBathroomFilter: false,
    showRenovationFilter: true,
    showCommercialFilters: false,
    showLandFilters: false,
  },
  commercial: {
    label: 'Коммерческая недвижимость',
    showBuildingDetails: false,
    showRooms: false,
    showFloor: false,
    showResidentialArea: false,
    showBalcony: false,
    showBathroom: false,
    showRenovation: false,
    showBedrooms: false,
    showPrivateHouseFloors: false,
    showLandArea: false,
    showCommercialDetails: true,
    showResidentialDetails: false,
    showGarageRenovationOnly: false,
    showBuildingMaterialFilter: false,
    showYearBuiltFilter: false,
    showTotalFloorsFilter: false,
    showBathroomFilter: false,
    showRenovationFilter: false,
    showCommercialFilters: true,
    showLandFilters: false,
  },
}

const DEFAULT_SCHEMA = {
  label: 'Недвижимость',
  showBuildingDetails: true,
  showRooms: false,
  showFloor: false,
  showResidentialArea: false,
  showBalcony: false,
  showBathroom: false,
  showRenovation: false,
  showBedrooms: false,
  showPrivateHouseFloors: false,
  showLandArea: false,
  showCommercialDetails: false,
  showResidentialDetails: false,
  showGarageRenovationOnly: false,
  showBuildingMaterialFilter: false,
  showYearBuiltFilter: false,
  showTotalFloorsFilter: false,
  showBathroomFilter: false,
  showRenovationFilter: false,
  showCommercialFilters: false,
  showLandFilters: false,
}

const PROPERTY_TYPE_LABELS = {
  ...Object.fromEntries(PROPERTY_TYPE_OPTIONS.map((item) => [item.value, item.label])),
  office: 'Коммерческая недвижимость',
  warehouse: 'Коммерческая недвижимость',
}

export const PROPERTY_TYPE_VALUES = PROPERTY_TYPE_OPTIONS.map((item) => item.value)
export { PROPERTY_TYPE_OPTIONS, PROPERTY_TYPE_SCHEMAS }

export function normalizePropertyType(value) {
  const code = (value || '').toString().trim()
  if (!code) return ''
  if (COMMERCIAL_ALIAS_CODES.has(code)) return 'commercial'
  return code
}

export function getPropertyTypeSchema(value) {
  const code = normalizePropertyType(value)
  if (!code) return DEFAULT_SCHEMA
  return PROPERTY_TYPE_SCHEMAS[code] || {
    ...DEFAULT_SCHEMA,
    label: PROPERTY_TYPE_LABELS[code] || code,
  }
}

export function propertyTypeLabel(value) {
  const code = normalizePropertyType(value)
  return PROPERTY_TYPE_LABELS[code] || PROPERTY_TYPE_LABELS[value] || DASH
}

export function propertyTypeUsesRooms(value) {
  return getPropertyTypeSchema(value).showRooms
}

export function propertyTypeUsesFloor(value) {
  return getPropertyTypeSchema(value).showFloor
}

export function propertyTypeIsCommercial(value) {
  return normalizePropertyType(value) === 'commercial'
}

export function propertyTypeHasLand(value) {
  return getPropertyTypeSchema(value).showLandArea
}

export function propertyTypeHasFloor(value) {
  return getPropertyTypeSchema(value).showPrivateHouseFloors
}

export function formatRoomsValue(propertyType, roomsCount) {
  if (!propertyTypeUsesRooms(propertyType)) return DASH
  if (roomsCount === null || roomsCount === undefined || roomsCount === '') return DASH
  return `${roomsCount}-комн.`
}
