<template>
  <component
    :is="interactive ? 'router-link' : 'div'"
    :to="interactive ? `/properties/${property.id}` : undefined"
    class="card card--link property-card"
    :class="{ 'card--selectable': selectable, 'card--selected': selected }"
    @click="handleClick"
  >
    <div class="card__thumb property-card__thumb">
      <img
        v-if="property.photos?.[0]?.image_url"
        :src="property.photos[0].image_url"
        :alt="property.title || 'Объект'" />
      <div v-else class="card__thumb-fallback property-card__thumb-fallback" aria-hidden="true">
        <svg width="42" height="42" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="1.5" stroke-linecap="round"
             stroke-linejoin="round">
          <path d="M3 12l9-8 9 8"/>
          <path d="M5 10v10h14V10"/>
        </svg>
      </div>

      <div class="property-card__thumb-overlay">
        <div class="property-card__thumb-top">
          <span class="tag tag--accent property-card__operation">
            {{ property.operation_type_name || 'Сделка' }}
          </span>
          <span v-if="property.status_name" class="tag tag--panel property-card__status">
            {{ property.status_name }}
          </span>
        </div>
        <div class="property-card__thumb-bottom">
          <span v-if="pricePerSqm" class="tag tag--panel property-card__sqm">
            {{ pricePerSqm }}
          </span>
        </div>
      </div>
    </div>

    <div class="property-card__content">
      <div class="card__price property-card__price">
        {{ formatMoney(property.price) }} ₽
      </div>
      <div class="card__title property-card__title">
        {{ property.title || 'Без названия' }}
      </div>

      <div v-if="metaTags.length" class="card__meta property-card__meta">
        <span v-for="tag in metaTags" :key="tag" class="tag">
          {{ tag }}
        </span>
      </div>

      <div class="muted property-card__address">
        {{ property.full_address || property.address || 'Адрес не указан' }}
      </div>

      <div v-if="amenityPreview.length" class="property-card__amenities">
        <span v-for="amenity in amenityPreview" :key="amenity" class="tag tag--panel">
          {{ amenity }}
        </span>
      </div>
    </div>
  </component>
</template>

<script setup>
import { computed } from 'vue'
import { formatMoney as fmtMoney } from '@/utils/formatters'
import {
  formatRoomsValue,
  normalizePropertyType,
  propertyTypeLabel,
  propertyTypeUsesRooms,
} from '@/utils/propertyTypes'

const props = defineProps({
  property: { type: Object, required: true },
  interactive: { type: Boolean, default: true },
  selectable: { type: Boolean, default: false },
  selected: { type: Boolean, default: false },
})

const emit = defineEmits(['select'])

const normalizedType = computed(() => normalizePropertyType(props.property.premises_type))
const showRooms = computed(() => (
  propertyTypeUsesRooms(normalizedType.value) && props.property.rooms_count
))
const roomsLabel = computed(() => (
  formatRoomsValue(normalizedType.value, props.property.rooms_count)
))
const pricePerSqm = computed(() => {
  const price = Number(props.property.price)
  const area = Number(props.property.area_total)
  if (!price || !area) return ''
  return `${fmtMoney(Math.round(price / area), '0')} ₽/м²`
})
const metaTags = computed(() => {
  const tags = []
  if (showRooms.value && roomsLabel.value !== '—') {
    tags.push(roomsLabel.value)
  }
  if (props.property.area_total) {
    tags.push(`${props.property.area_total} м²`)
  }
  if (props.property.floor_number) {
    const totalFloors = props.property.total_floors || props.property.building_details?.total_floors || '—'
    tags.push(`${props.property.floor_number}/${totalFloors} эт.`)
  }
  const typeLabel = props.property.property_type_name || propertyTypeLabel(normalizedType.value)
  if (typeLabel && typeLabel !== '—') {
    tags.push(typeLabel)
  }
  return tags
})
const amenityPreview = computed(() => (
  Array.isArray(props.property.amenities)
    ? props.property.amenities
        .slice(0, 3)
        .map((item) => item?.amenity_data?.name || item?.amenity_name || item?.amenity || '')
        .filter(Boolean)
    : []
))

function handleClick(event) {
  if (!props.selectable) return
  event.preventDefault?.()
  emit('select', props.property)
}

function formatMoney(v) {
  return fmtMoney(v, '0')
}
</script>

<style scoped>
.property-card {
  gap: 14px;
  overflow: hidden;
  transition: transform 0.28s ease, box-shadow 0.28s ease, border-color 0.28s ease;
}

.card--link {
  text-decoration: none;
  color: inherit;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
  display: flex;
  flex-direction: column;
  padding: 12px 12px 16px;
}

.card--selectable {
  cursor: pointer;
}

.card--selected {
  outline: 2px solid rgba(120, 216, 206, 0.52);
  outline-offset: 2px;
}

.card--link:hover {
  transform: translateY(-8px);
  box-shadow: 0 24px 46px rgba(16, 55, 52, 0.2);
}

.property-card__thumb {
  position: relative;
  aspect-ratio: 16 / 10;
  overflow: hidden;
  display: grid;
  place-items: center;
  color: rgba(255, 255, 255, 0.88);
  border-radius: 20px;
  border: 1px solid rgba(120, 216, 206, 0.12);
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.14), rgba(46, 159, 152, 0.14)),
    radial-gradient(circle at top right, rgba(120, 216, 206, 0.18), transparent 42%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.property-card__thumb::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(3, 18, 18, 0.12), rgba(3, 18, 18, 0.78));
  pointer-events: none;
}

.property-card__thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.45s ease;
}

.card--link:hover .property-card__thumb img {
  transform: scale(1.04);
}

.property-card__thumb-fallback {
  position: relative;
  z-index: 1;
}

.property-card__thumb-overlay {
  position: absolute;
  inset: 0;
  z-index: 1;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 14px;
}

.property-card__thumb-top,
.property-card__thumb-bottom {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}

.property-card__operation {
  padding: 6px 12px;
  border-radius: 999px;
  color: #efffff;
  font-weight: 600;
  background: rgba(7, 19, 29, 0.82);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.property-card__status,
.property-card__sqm {
  padding: 6px 12px;
  color: #efffff;
  font-weight: 600;
  background: rgba(7, 19, 29, 0.82);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.property-card__status {
  border-radius: 999px;
}

.property-card__sqm {
  border-radius: 12px;
  font-size: 12px;
}

.property-card__content {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  gap: 12px;
  padding: 0 16px 0;
}

.property-card__price {
  font-size: clamp(26px, 2.2vw, 28px);
  font-weight: 800;
  line-height: 1.1;
  color: #ffffff;
}

.property-card__title {
  font-size: 19px;
  font-weight: 700;
  line-height: 1.35;
  min-height: 2.6em;
}

.property-card__meta {
  gap: 6px;
  flex-wrap: wrap;
}

.property-card__meta .tag,
.property-card__amenities .tag {
  padding: 5px 10px;
  font-weight: 500;
}

.property-card__address {
  font-size: 13px;
  font-weight: 400;
  line-height: 1.5;
  color: var(--c-text-muted);
}

.property-card__amenities {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: auto;
  padding-top: 2px;
}
</style>
