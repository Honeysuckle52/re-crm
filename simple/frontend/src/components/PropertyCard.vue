<template>
  <router-link :to="`/properties/${property.id}`" class="card card--link">
    <div class="card__thumb">
      <img v-if="property.photos?.[0]?.image_url" :src="property.photos[0].image_url"
           :alt="property.title || 'Объект'" />
      <div v-else class="card__thumb-fallback" aria-hidden="true">
        <svg width="42" height="42" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="1.5" stroke-linecap="round"
             stroke-linejoin="round">
          <path d="M3 12l9-8 9 8"/><path d="M5 10v10h14V10"/>
        </svg>
      </div>
      <span class="card__tag tag tag--panel">
        {{ property.operation_type_name }}
      </span>
    </div>
    <div class="card__title">{{ property.title || 'Без названия' }}</div>
    <div class="card__price">{{ formatMoney(property.price) }} ₽</div>
    <div class="card__meta">
      <span v-if="property.rooms_count" class="tag">{{ property.rooms_count }}-комн.</span>
      <span v-if="property.area_total" class="tag">{{ property.area_total }} м²</span>
      <span v-if="property.floor_number" class="tag">
        {{ property.floor_number }}/{{ property.total_floors || '—' }} эт.
      </span>
      <span class="tag tag--accent">{{ property.status_name }}</span>
    </div>
    <div class="muted" style="font-size: 12px">{{ property.full_address }}</div>
  </router-link>
</template>

<script setup>
import { formatMoney as fmtMoney } from '@/utils/formatters'

defineProps({ property: { type: Object, required: true } })

function formatMoney (v) { return fmtMoney(v, '0') }
</script>

<style scoped>
.card--link {
  text-decoration: none;
  color: inherit;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
  display: flex;
  flex-direction: column;
}

.card--link:hover {
  transform: translateY(-5px);
  box-shadow: var(--shadow-glow-strong);
}

.card__thumb {
  position: relative;
  aspect-ratio: 16 / 10;
  overflow: hidden;
  display: grid;
  place-items: center;
  color: rgba(255, 255, 255, 0.88);
  border-radius: 20px;
  border: 1px solid rgba(120, 216, 206, 0.16);
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.2), rgba(46, 159, 152, 0.14)),
    radial-gradient(circle at top right, rgba(120, 216, 206, 0.18), transparent 42%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
}

.card__thumb::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, transparent 38%, rgba(34, 72, 69, 0.24));
  pointer-events: none;
}

.card__thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.45s ease;
}

.card--link:hover .card__thumb img {
  transform: scale(1.04);
}

.card__thumb-fallback {
  position: relative;
  z-index: 1;
}

.card__tag {
  position: absolute;
  top: 12px;
  left: 12px;
  z-index: 1;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}
</style>
