<template>
  <div class="field remote-lookup">
    <label>{{ label }}</label>
    <div class="remote-lookup__control">
      <input
        class="input remote-lookup__input"
        :disabled="disabled"
        :placeholder="placeholder"
        :value="query"
        autocomplete="off"
        @input="onInput"
        @focus="handleFocus"
        @blur="handleBlur"
        @keydown.esc="open = false"
      />
      <button
        v-if="clearable && modelValue != null && !disabled"
        class="remote-lookup__clear"
        type="button"
        aria-label="Очистить выбор"
        @mousedown.prevent
        @click="clear"
      >
        ×
      </button>
    </div>

    <div v-if="open" class="remote-lookup__menu">
      <div v-if="loading" class="remote-lookup__state">
        Поиск…
      </div>
      <template v-else-if="options.length">
        <button
          v-for="option in options"
          :key="option.id"
          class="remote-lookup__option"
          type="button"
          @mousedown.prevent="pick(option)"
        >
          <span class="remote-lookup__value">{{ option.label }}</span>
          <span v-if="option.hint" class="remote-lookup__hint">{{ option.hint }}</span>
        </button>
      </template>
      <div v-else class="remote-lookup__state">
        {{ query.length >= minChars || !minChars ? noResultsText : minCharsText }}
      </div>
    </div>

    <small v-if="selectedHint" class="muted remote-lookup__selected-hint">
      {{ selectedHint }}
    </small>
    <small v-if="error" class="error">{{ error }}</small>
  </div>
</template>

<script setup>
import { computed, ref, toRefs, watch } from 'vue'
import api from '../api'
import { unpackPaginated } from '@/utils/paginated'

const props = defineProps({
  modelValue: { type: [Number, String], default: null },
  label: { type: String, required: true },
  endpoint: { type: String, required: true },
  mapOption: { type: Function, required: true },
  params: { type: Object, default: () => ({}) },
  placeholder: { type: String, default: 'Начните вводить…' },
  queryParam: { type: String, default: 'search' },
  pageSize: { type: Number, default: 8 },
  minChars: { type: Number, default: 0 },
  clearable: { type: Boolean, default: true },
  disabled: { type: Boolean, default: false },
  noResultsText: { type: String, default: 'Ничего не найдено.' },
})

const emit = defineEmits(['update:modelValue', 'select'])
const {
  modelValue,
  label,
  placeholder,
  minChars,
  clearable,
  disabled,
  noResultsText,
} = toRefs(props)

const open = ref(false)
const loading = ref(false)
const error = ref('')
const query = ref('')
const options = ref([])
const selectedOption = ref(null)

let timer = null
let requestSeq = 0

const minCharsText = computed(() => {
  if (!props.minChars) return props.noResultsText
  return `Введите минимум ${props.minChars} символа(ов).`
})

const selectedHint = computed(() => {
  if (props.modelValue == null) return ''
  return selectedOption.value?.hint || ''
})

watch(
  () => props.modelValue,
  (value) => {
    if (value == null) {
      query.value = ''
      selectedOption.value = null
      return
    }

    const fromOptions = options.value.find((item) => item.id === value)
    if (fromOptions) {
      selectedOption.value = fromOptions
      query.value = fromOptions.label
      return
    }

    if (selectedOption.value?.id === value) {
      query.value = selectedOption.value.label
    }
  },
  { immediate: true },
)

watch(options, (nextOptions) => {
  if (props.modelValue == null) return
  const matched = nextOptions.find((item) => item.id === props.modelValue)
  if (!matched) return
  selectedOption.value = matched
  query.value = matched.label
})

function buildParams(search = '') {
  const params = {
    page: 1,
    page_size: props.pageSize,
    ...props.params,
  }
  if (search) {
    params[props.queryParam] = search
  }
  return params
}

async function fetchOptions(search = '') {
  if (props.disabled) return
  if (search.length < props.minChars && !(search === '' && props.minChars === 0)) {
    options.value = []
    loading.value = false
    error.value = ''
    return
  }

  const seq = ++requestSeq
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get(props.endpoint, {
      params: buildParams(search),
    })
    if (seq !== requestSeq) return
    options.value = unpackPaginated(data).items.map(props.mapOption)
  } catch (err) {
    if (seq !== requestSeq) return
    options.value = []
    error.value = err?.response?.data?.detail || 'Не удалось загрузить список.'
  } finally {
    if (seq === requestSeq) {
      loading.value = false
    }
  }
}

function onInput(event) {
  const nextValue = event.target.value
  query.value = nextValue
  open.value = true
  error.value = ''

  if (props.modelValue != null) {
    emit('update:modelValue', null)
  }
  selectedOption.value = null

  clearTimeout(timer)
  timer = setTimeout(() => {
    fetchOptions(nextValue.trim())
  }, 250)
}

function handleFocus() {
  if (props.disabled) return
  open.value = true
  fetchOptions(query.value.trim())
}

function handleBlur() {
  setTimeout(() => {
    open.value = false
    if (props.modelValue == null) {
      query.value = ''
    } else if (selectedOption.value) {
      query.value = selectedOption.value.label
    }
  }, 160)
}

function pick(option) {
  selectedOption.value = option
  query.value = option.label
  open.value = false
  emit('update:modelValue', option.id)
  emit('select', option)
}

function clear() {
  clearTimeout(timer)
  query.value = ''
  open.value = false
  options.value = []
  error.value = ''
  selectedOption.value = null
  emit('update:modelValue', null)
}
</script>

<style scoped>
.remote-lookup {
  position: relative;
}

.remote-lookup__control {
  position: relative;
}

.remote-lookup__input {
  padding-right: 44px;
}

.remote-lookup__clear {
  position: absolute;
  top: 50%;
  right: 12px;
  transform: translateY(-50%);
  width: 28px;
  height: 28px;
  border-radius: 999px;
  border: 0;
  background: rgba(14, 35, 40, 0.08);
  color: rgba(18, 54, 58, 0.82);
  font-size: 18px;
  line-height: 1;
  transition: background 0.2s ease, color 0.2s ease;
}

.remote-lookup__clear:hover {
  background: rgba(14, 35, 40, 0.14);
  color: rgba(18, 54, 58, 0.96);
}

.remote-lookup__menu {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  right: 0;
  z-index: 30;
  max-height: 320px;
  overflow: auto;
  border-radius: 20px;
  border: 1px solid rgba(19, 78, 84, 0.12);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(245, 250, 251, 0.98));
  box-shadow: 0 22px 40px rgba(9, 31, 39, 0.12);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
}

.remote-lookup__option {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border: 0;
  border-bottom: 1px solid rgba(19, 78, 84, 0.08);
  background: transparent;
  text-align: left;
  transition: background 0.2s ease;
}

.remote-lookup__option:last-child {
  border-bottom: 0;
}

.remote-lookup__option:hover {
  background: rgba(213, 232, 235, 0.52);
}

.remote-lookup__value {
  flex: 1;
  color: var(--c-text);
  font-size: 14px;
  font-weight: 600;
}

.remote-lookup__hint {
  color: var(--c-text-muted);
  font-size: 12px;
  text-align: right;
}

.remote-lookup__state,
.remote-lookup__selected-hint {
  display: block;
  padding-top: 8px;
}

.remote-lookup__state {
  padding: 14px;
  color: var(--c-text-muted);
  font-size: 13px;
}
</style>
