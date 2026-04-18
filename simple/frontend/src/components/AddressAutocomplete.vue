<template>
  <div class="field" style="position: relative;">
    <label>{{ label }}</label>
    <input
      class="input"
      :value="modelValue"
      @input="onInput"
      @focus="open = true"
      @blur="setTimeout(() => open = false, 150)"
      :placeholder="placeholder"
    />
    <div v-if="open && results.length" class="autocomplete">
      <button
        v-for="r in results"
        :key="r.object_id || r.fias_id || r.full_name"
        class="autocomplete__item"
        @mousedown.prevent="pick(r)"
        type="button"
      >
        {{ r.full_name || r.name || r.address }}
      </button>
    </div>
    <small v-if="loading" class="muted">Поиск в ФИАС…</small>
    <small v-if="error" class="error">{{ error }}</small>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import api from '../api'

const props = defineProps({
  modelValue: String,
  label: { type: String, default: 'Адрес' },
  placeholder: { type: String, default: 'Начните вводить адрес…' },
})
const emit = defineEmits(['update:modelValue', 'pick'])

const results = ref([])
const open = ref(false)
const loading = ref(false)
const error = ref('')
let t = null

function onInput(e) {
  const v = e.target.value
  emit('update:modelValue', v)
  clearTimeout(t)
  if (v.length < 3) { results.value = []; return }
  t = setTimeout(async () => {
    loading.value = true; error.value = ''
    try {
      const { data } = await api.get('/fias/search/', { params: { q: v } })
      results.value = data.results || []
      open.value = true
    } catch (e) {
      error.value = 'ФИАС недоступен'
    } finally {
      loading.value = false
    }
  }, 300)
}

function pick(r) {
  emit('update:modelValue', r.full_name || r.name || r.address)
  emit('pick', r)
  open.value = false
}
</script>

<style scoped>
.autocomplete {
  position: absolute; top: 100%; left: 0; right: 0;
  background: var(--c-paper); border-radius: var(--r-sm);
  box-shadow: var(--shadow-2); margin-top: 4px; z-index: 20;
  max-height: 280px; overflow: auto;
}
.autocomplete__item {
  display: block; width: 100%; text-align: left;
  padding: 10px 14px; border-bottom: 1px solid rgba(0,0,0,.05);
  font-size: 14px;
}
.autocomplete__item:hover { background: var(--c-paper-2); }
</style>
