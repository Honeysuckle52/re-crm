<template>
  <section class="stack">
    <div class="hero" style="padding: 24px 28px">
      <div class="hero__eyebrow">{{ isEdit ? 'РЕДАКТИРОВАНИЕ' : 'НОВЫЙ ОБЪЕКТ' }}</div>
      <h1 class="h2" style="color: #fff; margin-top: 8px">
        {{ isEdit ? 'Изменить объект' : 'Создать объект' }}
      </h1>
    </div>

    <form class="panel panel--light stack" @submit.prevent="submit">
      <div class="grid grid--2">
        <div class="field">
          <label>Заголовок</label>
          <input class="input" v-model="form.title" required />
        </div>
        <div class="field">
          <label>Тип операции</label>
          <select class="select" v-model.number="form.operation_type" required>
            <option v-for="o in dict.operations" :key="o.id" :value="o.id">
              {{ o.name }}
            </option>
          </select>
        </div>

        <div class="field">
          <label>Цена, ₽</label>
          <input class="input" type="number" step="0.01" v-model.number="form.price" required />
        </div>
        <div class="field">
          <label>Цена за м²</label>
          <input class="input" type="number" step="0.01" v-model.number="form.price_per_sqm" />
        </div>

        <div class="field">
          <label>Комнат</label>
          <input class="input" type="number" v-model.number="form.rooms_count" />
        </div>
        <div class="field">
          <label>Этаж / всего</label>
          <div class="row">
            <input class="input" type="number" v-model.number="form.floor_number" />
            <input class="input" type="number" v-model.number="form.total_floors" />
          </div>
        </div>

        <div class="field">
          <label>Общая площадь, м²</label>
          <input class="input" type="number" step="0.01" v-model.number="form.area_total" />
        </div>
        <div class="field">
          <label>Жилая, м²</label>
          <input class="input" type="number" step="0.01" v-model.number="form.area_living" />
        </div>
      </div>

      <!-- Адрес: сначала выбираем город/улицу/дом, затем квартиру -->
      <div class="grid grid--3">
        <div class="field">
          <label>Город</label>
          <select class="select" v-model.number="addr.city" @change="loadStreets">
            <option value="">—</option>
            <option v-for="c in addr.cities" :key="c.id" :value="c.id">
              {{ c.name }}
            </option>
          </select>
        </div>
        <div class="field">
          <label>Улица</label>
          <select class="select" v-model.number="addr.street"
                  @change="loadHouses" :disabled="!addr.city">
            <option value="">—</option>
            <option v-for="s in addr.streets" :key="s.id" :value="s.id">
              {{ s.street_type }} {{ s.name }}
            </option>
          </select>
        </div>
        <div class="field">
          <label>Дом</label>
          <select class="select" v-model.number="addr.house"
                  @change="loadAddresses" :disabled="!addr.street">
            <option value="">—</option>
            <option v-for="h in addr.houses" :key="h.id" :value="h.id">
              д. {{ h.house_number }}
            </option>
          </select>
        </div>
      </div>

      <div class="grid grid--2">
        <div class="field">
          <label>Адрес (квартира/офис)</label>
          <select class="select" v-model.number="form.address" required
                  :disabled="!addr.house">
            <option value="">—</option>
            <option v-for="a in addr.addresses" :key="a.id" :value="a.id">
              {{ a.full_address }}
            </option>
          </select>
        </div>
        <AddressAutocomplete v-model="addr.fiasQuery"
                             label="Поиск по ФИАС"
                             placeholder="Москва, Ленина 1…" />
      </div>

      <div class="field">
        <label>Описание</label>
        <textarea class="textarea" v-model="form.description" rows="5"></textarea>
      </div>

      <div v-if="error" class="error">{{ error }}</div>
      <div class="row" style="justify-content: flex-end; gap: 8px">
        <button class="btn" type="button" @click="$router.back()">Отмена</button>
        <button class="btn btn--accent" :disabled="loading" type="submit">
          {{ loading ? 'Сохранение…' : (isEdit ? 'Сохранить' : 'Создать') }}
        </button>
      </div>
    </form>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import AddressAutocomplete from '../components/AddressAutocomplete.vue'

const route = useRoute(); const router = useRouter()
const isEdit = computed(() => !!route.params.id)

const form = reactive({
  title: '', operation_type: 1, status: 1, address: '',
  price: null, price_per_sqm: null,
  area_total: null, area_living: null, area_kitchen: null,
  rooms_count: null, floor_number: null, total_floors: null,
  description: '',
})
const addr = reactive({
  cities: [], streets: [], houses: [], addresses: [],
  city: '', street: '', house: '', fiasQuery: '',
})
const dict = reactive({ operations: [] })
const loading = ref(false); const error = ref('')

async function loadStreets() {
  addr.streets = []; addr.houses = []; addr.addresses = []
  addr.street = ''; addr.house = ''; form.address = ''
  if (!addr.city) return
  const { data } = await api.get('/streets/', { params: { city: addr.city } })
  addr.streets = data.results || data
}
async function loadHouses() {
  addr.houses = []; addr.addresses = []
  addr.house = ''; form.address = ''
  if (!addr.street) return
  const { data } = await api.get('/houses/', { params: { street: addr.street } })
  addr.houses = data.results || data
}
async function loadAddresses() {
  addr.addresses = []; form.address = ''
  if (!addr.house) return
  const { data } = await api.get('/addresses/', { params: { house: addr.house } })
  addr.addresses = (data.results || data).filter(a => a.house === addr.house)
}

async function submit() {
  loading.value = true; error.value = ''
  try {
    const payload = { ...form }
    const url = isEdit.value
      ? `/properties/${route.params.id}/` : '/properties/'
    const method = isEdit.value ? 'put' : 'post'
    const { data } = await api[method](url, payload)
    router.push(`/properties/${data.id}`)
  } catch (e) {
    error.value = JSON.stringify(e.response?.data || e.message)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  const [o, c] = await Promise.all([
    api.get('/operation-types/'),
    api.get('/cities/'),
  ])
  dict.operations = o.data.results || o.data
  addr.cities = c.data.results || c.data

  if (isEdit.value) {
    const { data } = await api.get(`/properties/${route.params.id}/`)
    Object.assign(form, data)
  }
})
</script>
