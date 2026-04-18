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
  // закрываем с задержкой, чтобы успел сработать mousedown на пункте
  setTimeout(() => { open.value = false }, 150)
}
</script>

<style scoped>
.autocomplete {
  position: absolute; top: 100%; left: 0; right: 0;
  background: var(--c-paper); border-radius: var(--r-sm);
  box-shadow: var(--shadow-2); margin-top: 4px; z-index: 20;
  max-height: 320px; overflow: auto;
}
.autocomplete__item {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  width: 100%; text-align: left;
  padding: 10px 14px; border-bottom: 1px solid rgba(0,0,0,.05);
  font-size: 14px; color: var(--c-ink);
}
.autocomplete__item:hover { background: var(--c-paper-2); }
.autocomplete__value { flex: 1; }
.autocomplete__hint { font-size: 12px; color: var(--c-ink-soft); }
</style>
