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
// Общий форматтер денег вынесен в utils/formatters; fallback '0' сохраняет
// прежнее поведение «нет суммы → 0».
import { formatMoney as fmtMoney } from '@/utils/formatters'

defineProps({ property: { type: Object, required: true } })

function formatMoney (v) { return fmtMoney(v, '0') }
</script>

<style scoped>
.card--link { text-decoration: none; color: inherit; transition: transform .15s, box-shadow .15s; }
.card--link:hover { transform: translateY(-2px); box-shadow: var(--shadow-2); }
.card__thumb {
  position: relative; aspect-ratio: 16/10;
  background: linear-gradient(135deg, #0e3a38, #1fa39a);
  border-radius: var(--r-sm); overflow: hidden;
  display: grid; place-items: center; color: rgba(255,255,255,.8);
}
.card__thumb img { width: 100%; height: 100%; object-fit: cover; }
.card__tag { position: absolute; top: 10px; left: 10px; }
</style>
