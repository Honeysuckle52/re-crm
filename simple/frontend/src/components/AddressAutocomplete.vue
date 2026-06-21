<template>
  <div class="field" style="position: relative;">
    <label>{{ label }}</label>
    <input
      class="input"
      :value="modelValue"
      @input="onInput"
      @focus="open = true"
      @blur="handleBlur"
      :placeholder="placeholder"
      autocomplete="off"
    />
    <div v-if="open && results.length" class="autocomplete">
      <button
        v-for="(r, i) in results"
        :key="r.address_external_id || r.value + i"
        class="autocomplete__item"
        @mousedown.prevent="pick(r)"
        type="button"
      >
        <span class="autocomplete__value">{{ r.value }}</span>
        <span v-if="r.postal_code" class="autocomplete__hint">
          {{ r.postal_code }}
        </span>
      </button>
    </div>
    <small v-if="loading" class="muted">Поиск адреса…</small>
    <small v-if="error" class="error">{{ error }}</small>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import api from '../api'

const props = defineProps({
  modelValue: { type: String, default: '' },
  label: { type: String, default: 'Адрес' },
  placeholder: { type: String, default: 'Начните вводить адрес…' },
})
const emit = defineEmits(['update:modelValue', 'pick'])

const results = ref([])
const open = ref(false)
const loading = ref(false)
const error = ref('')
let timer = null

function onInput(e) {
  const v = e.target.value
  emit('update:modelValue', v)
  clearTimeout(timer)
  error.value = ''
  if (v.length < 2) {
    results.value = []
    open.value = false
    return
  }
  timer = setTimeout(async () => {
    loading.value = true
    try {
      const { data } = await api.get('/dadata/suggest-address/',
        { params: { q: v } })
      results.value = data.results || []
      open.value = results.value.length > 0
    } catch (e) {
      const detail = e?.response?.data?.detail
      error.value = detail || 'Сервис подсказок адресов недоступен. '
        + 'Адрес можно ввести вручную.'
    } finally {
      loading.value = false
    }
  }, 300)
}

function pick(r) {
  emit('update:modelValue', r.value)
  emit('pick', r)
  open.value = false
  results.value = []
}

function handleBlur() {
  setTimeout(() => { open.value = false }, 150)
}
</script>

<style scoped>
.autocomplete {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  right: 0;
  z-index: 200;
  max-height: 320px;
  overflow: auto;
  border-radius: 22px;
  border: 1px solid var(--c-border);
  background: linear-gradient(180deg, #124346 0%, #073434 100%);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  box-shadow: var(--shadow-glow);
}

.autocomplete__item {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  text-align: left;
  font-size: 14px;
  color: var(--c-text);
  border-bottom: 1px solid rgba(120, 216, 206, 0.12);
  transition: background 0.3s ease, color 0.3s ease;
}

.autocomplete__item:last-child {
  border-bottom: 0;
}

.autocomplete__item:hover {
  background: linear-gradient(135deg, rgba(27, 77, 62, 0.98), rgba(46, 139, 87, 0.82));
  color: #efffff;
}

.autocomplete__value {
  flex: 1;
}

.autocomplete__hint {
  font-size: 12px;
  color: var(--c-text-muted);
}
</style>
