<template>
  <section class="stack property-form-page">
    <div class="hero" style="padding: 24px 28px">
      <div class="row row--between" style="flex-wrap: wrap; gap: 12px">
        <div>
          <div class="hero__eyebrow">{{ isEdit ? 'РЕДАКТИРОВАНИЕ' : 'НОВЫЙ ОБЪЕКТ' }}</div>
          <h1 class="h2" style="color: #fff; margin-top: 8px">
            {{ isEdit ? 'Изменить объект' : 'Создать объект' }}
          </h1>
          <div style="color: rgba(255,255,255,.75); font-size: 14px; margin-top: 6px">
            Заполните карточку объекта, подготовьте адрес, медиа и описание для дальнейшей работы по заявкам.
          </div>
        </div>
        <button class="btn btn--ghost" type="button" @click="$router.back()">Назад</button>
      </div>
    </div>

    <div v-if="false" class="kpi-strip">
      <article class="kpi-card">
        <span class="kpi-card__label">Режим</span>
        <strong class="kpi-card__value">{{ formModeLabel }}</strong>
        <span class="kpi-card__meta">{{ isEdit ? 'Обновление существующей карточки' : 'Создание нового объекта в каталоге' }}</span>
      </article>
      <article class="kpi-card">
        <span class="kpi-card__label">Адрес</span>
        <strong class="kpi-card__value">{{ addressStateLabel }}</strong>
        <span class="kpi-card__meta">{{ addressPicked?.value || existingAddress || 'Выберите адрес из подсказок' }}</span>
      </article>
      <article class="kpi-card">
        <span class="kpi-card__label">Фотографии</span>
        <strong class="kpi-card__value">{{ photoCount }}</strong>
        <span class="kpi-card__meta">Обложка: {{ coverCount ? 'назначена' : 'не выбрана' }}</span>
      </article>
      <article class="kpi-card kpi-card--accent">
        <span class="kpi-card__label">Характеристики</span>
        <strong class="kpi-card__value">{{ selectedFeaturesCount }}</strong>
        <span class="kpi-card__meta">Отмечено параметров объекта</span>
      </article>
    </div>

    <form class="panel panel--light stack property-form" @submit.prevent="submit">
      <div class="surface-head property-form__section-head">
        <div>
          <div class="surface-head__meta">Карточка объекта</div>
          <h2 class="h3">Основные параметры</h2>
        </div>
        <div class="surface-head__caption">Базовые данные для каталога и дальнейшей работы по заявкам.</div>
      </div>
      <div class="grid grid--2 property-form__main-grid">
        <div class="field">
          <label>Заголовок</label>
          <input class="input" v-model="form.title" required
                 placeholder="Например: 2-комнатная на Ленина" />
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
          <input class="input" type="number" step="0.01"
                 v-model.number="form.price" required />
        </div>
        <div class="field">
          <label>Тип объекта</label>
          <select class="select" v-model="form.premises_type" required>
            <option v-for="item in dict.propertyTypes" :key="item.id" :value="item.code">
              {{ item.name }}
            </option>
          </select>
        </div>
        <div class="field">
          <label>Количество комнат</label>
          <input class="input" type="number" v-model.number="form.rooms_count"
                 :disabled="isRoomsDisabled" :placeholder="isRoomsDisabled ? 'Не применяется' : ''" />
        </div>
        <div class="field">
          <label>Этаж</label>
          <input class="input" type="number" v-model.number="form.floor_number"
                 :disabled="isFloorDisabled" :placeholder="isFloorDisabled ? 'Не применяется' : 'Этаж'" />
        </div>

        <div class="field">
          <label>Общая площадь, м²</label>
          <input class="input" type="number" step="0.01"
                 v-model.number="form.area_total" />
        </div>
        <div class="field">
          <label>Кадастровый номер</label>
          <input class="input" v-model="form.cadastral_number" />
        </div>
        <div class="field" v-if="auth.isStaff">
          <label>Статус</label>
          <select class="select" v-model.number="form.status" required>
            <option v-for="s in dict.statuses" :key="s.id" :value="s.id">
              {{ s.name }}
            </option>
          </select>
        </div>
        <div class="field" v-if="auth.isStaff">
          <label>Публикация</label>
          <label class="chip-check" style="width: fit-content">
            <input type="checkbox" v-model="form.is_published" />
            Опубликован
          </label>
        </div>
      </div>

      <div class="surface-head property-form__section-head">
        <div>
          <div class="surface-head__meta">Локация</div>
          <h2 class="h3">Адрес</h2>
        </div>
        <div class="surface-head__caption">Подсказки адресов подставляются через DaData.</div>
      </div>
      <p class="muted">
        Начните вводить адрес — подсказки подгружаются из сервиса DaData.
        Выберите нужную строку, и поля будут заполнены автоматически.
      </p>
      <AddressAutocomplete
        v-model="addressQuery"
        label="Поиск по адресу"
        placeholder="Город, улица, дом, квартира…"
        @pick="onAddressPick"
      />
      <div v-if="addressPicked" class="row" style="gap: 12px; flex-wrap: wrap">
        <span class="tag tag--accent">{{ addressPicked.value }}</span>
        <span v-if="addressPicked.postal_code" class="tag">
          Индекс: {{ addressPicked.postal_code }}
        </span>
        <span v-if="addressPicked.geo_lat && addressPicked.geo_lon" class="tag">
          {{ addressPicked.geo_lat.toFixed(4) }}, {{ addressPicked.geo_lon.toFixed(4) }}
        </span>
      </div>
      <div v-else-if="existingAddress" class="muted">
        Текущий адрес: {{ existingAddress }}
      </div>

      <div class="surface-head property-form__section-head">
        <div>
          <div class="surface-head__meta">Медиа</div>
          <h2 class="h3">Фотографии</h2>
        </div>
        <div class="surface-head__caption">Можно загружать файлы и добавлять внешние ссылки на изображения.</div>
      </div>
      <p class="muted">
        После создания объекта карты со спутниковыми снимками подгружаются
        автоматически из 2GIS по указанному адресу. Вы также можете загрузить
        собственные фотографии или добавить ссылки на изображения — они
        сохранятся вместе с картами из 2GIS.
      </p>
      <div class="grid grid--3" v-if="photos.length">
        <div v-for="(p, i) in photos" :key="p.id || ('new-' + i)"
             class="photo-tile">
          <img :src="p.image_url || p.preview || p.url" alt="Фото объекта" />
          <div class="photo-tile__overlay">
            <label class="tag tag--panel" style="cursor: pointer">
              <input type="checkbox" v-model="p.is_cover"
                     @change="setCover(p)" style="display: none" />
              {{ p.is_cover ? 'Обложка' : 'Сделать обложкой' }}
            </label>
            <button class="btn btn--danger btn--sm" type="button"
                    @click="removePhoto(p, i)">
              Удалить
            </button>
          </div>
        </div>
      </div>
      <div v-else class="empty property-form__photos-empty">
        Фотографии пока не добавлены.
      </div>
      <div class="row property-form__photos-actions" style="gap: 12px; flex-wrap: wrap">
        <label class="btn btn--sm" style="cursor: pointer">
          Загрузить файл
          <input type="file" accept="image/*" multiple
                 style="display: none" @change="onFilesSelected" />
        </label>
        <div class="row property-form__photo-url" style="gap: 8px; flex: 1; min-width: 240px">
          <input class="input" v-model="newPhotoUrl"
                 placeholder="или вставьте ссылку на изображение" />
          <button class="btn btn--sm" type="button" @click="addPhotoByUrl">
            Добавить ссылку
          </button>
        </div>
      </div>

      <div class="surface-head property-form__section-head">
        <div>
          <div class="surface-head__meta">Контент карточки</div>
          <h2 class="h3">Описание</h2>
        </div>
        <div class="surface-head__caption">Текст используется в карточке объекта и в работе агента с клиентом.</div>
      </div>
      <div class="field">
        <label>Описание объекта</label>
        <textarea class="textarea" v-model="form.description" rows="5"
                  placeholder="Расскажите об объекте: состояние, инфраструктура, транспорт…">
        </textarea>
      </div>

      <div class="surface-head property-form__section-head">
        <div>
          <div class="surface-head__meta">Данные БД</div>
          <h2 class="h3">Характеристики из связанных таблиц</h2>
        </div>
        <div class="surface-head__caption">
          Поля сохраняются в `building_details`, `property_details` и `commercial_property_details`.
        </div>
      </div>

      <div class="grid grid--2 property-form__details-grid">
        <div class="panel panel--light property-form__details-block">
          <h3 class="h4">Дом</h3>
          <div class="grid grid--2 property-form__details-fields">
            <div class="field">
              <label>Год постройки</label>
              <input class="input" type="number" v-model.number="form.building_details.year_built" />
            </div>
            <div class="field">
              <label>Этажей в доме</label>
              <input class="input" type="number" v-model.number="form.building_details.total_floors" />
            </div>
            <div class="field">
              <label>Материал стен</label>
              <select class="select" v-model="form.building_details.building_material">
                <option :value="null">Не указан</option>
                <option v-for="item in dict.buildingMaterials" :key="item.id" :value="item.id">
                  {{ item.name }}
                </option>
              </select>
            </div>
            <div class="field">
              <label>Лифты</label>
              <input class="input" type="number" min="0" v-model.number="form.building_details.elevators_count" />
            </div>
          </div>
        </div>

        <div class="panel panel--light property-form__details-block">
          <h3 class="h4">Жилая часть</h3>
          <div class="grid grid--2 property-form__details-fields">
            <div class="field">
              <label>Жилая площадь, м²</label>
              <input class="input" type="number" step="0.01" v-model.number="form.property_details.living_area" />
            </div>
            <div class="field">
              <label>Площадь кухни, м²</label>
              <input class="input" type="number" step="0.01" v-model.number="form.property_details.kitchen_area" />
            </div>
            <div class="field">
              <label>Высота потолков, м</label>
              <input class="input" type="number" step="0.01" v-model.number="form.property_details.ceiling_height" />
            </div>
            <div class="field">
              <label>Балконы</label>
              <input class="input" type="number" min="0" v-model.number="form.property_details.balcony_count" />
            </div>
            <div class="field">
              <label>Санузлы</label>
              <input class="input" type="number" min="0" v-model.number="form.property_details.bathroom_count" />
            </div>
            <div class="field">
              <label>Тип санузла</label>
              <select class="select" v-model="form.property_details.bathroom_type">
                <option :value="null">Не указан</option>
                <option v-for="item in dict.bathroomTypes" :key="item.id" :value="item.id">
                  {{ item.name }}
                </option>
              </select>
            </div>
            <div class="field">
              <label>Тип ремонта</label>
              <select class="select" v-model="form.property_details.renovation_type">
                <option :value="null">Не указан</option>
                <option v-for="item in dict.renovationTypes" :key="item.id" :value="item.id">
                  {{ item.name }}
                </option>
              </select>
            </div>
            <div class="field">
              <label>Спальни</label>
              <input class="input" type="number" min="0" v-model.number="form.property_details.bedrooms_count" />
            </div>
            <div class="field" v-if="propertyTypeHasFloor(normalizedPremisesType)">
              <label>Этажей в квартире / доме</label>
              <input class="input" type="number" min="1" v-model.number="form.property_details.floors_count" />
            </div>
            <div class="field" v-if="propertyTypeHasLand(normalizedPremisesType)">
              <label>Площадь участка, м²</label>
              <input class="input" type="number" step="0.01" v-model.number="form.property_details.land_area" />
            </div>
          </div>
        </div>

        <div class="panel panel--light property-form__details-block" v-if="isCommercialType">
          <h3 class="h4">Коммерческая недвижимость</h3>
          <div class="grid grid--2 property-form__details-fields">
            <div class="field">
              <label>Тип коммерческого объекта</label>
              <select class="select" v-model="form.commercial_property_details.commercial_type">
                <option :value="null">Не указан</option>
                <option v-for="item in dict.commercialTypes" :key="item.id" :value="item.id">
                  {{ item.name }}
                </option>
              </select>
            </div>
            <div class="field">
              <label>Полезная площадь, м²</label>
              <input class="input" type="number" step="0.01" v-model.number="form.commercial_property_details.usable_area" />
            </div>
            <div class="field">
              <label>Высота потолков, м</label>
              <input class="input" type="number" step="0.01" v-model.number="form.commercial_property_details.ceiling_height" />
            </div>
            <div class="field">
              <label>Нагрузка на пол, кг/м²</label>
              <input class="input" type="number" step="0.01" v-model.number="form.commercial_property_details.floor_load" />
            </div>
            <div class="field">
              <label>Электрическая мощность, кВт</label>
              <input class="input" type="number" step="0.01" v-model.number="form.commercial_property_details.electric_power_kw" />
            </div>
            <div class="field">
              <label>Парковочные места</label>
              <input class="input" type="number" min="0" v-model.number="form.commercial_property_details.parking_spaces" />
            </div>
            <label class="chip-check">
              <input type="checkbox" v-model="form.commercial_property_details.has_separate_entrance" />
              Отдельный вход
            </label>
            <label class="chip-check">
              <input type="checkbox" v-model="form.commercial_property_details.has_display_windows" />
              Витринные окна
            </label>
            <label class="chip-check">
              <input type="checkbox" v-model="form.commercial_property_details.is_first_line" />
              Первая линия
            </label>
          </div>
        </div>

        <div class="panel panel--light property-form__details-block">
          <h3 class="h4">Удобства</h3>
          <div class="property-form__amenities">
            <label v-for="item in dict.amenities" :key="item.id" class="chip-check">
              <input
                type="checkbox"
                :value="item.id"
                v-model="form.amenity_ids" />
              {{ item.name }}
            </label>
          </div>
        </div>

        <div class="panel panel--light property-form__details-block" v-if="auth.isStaff">
          <h3 class="h4">Документы объекта</h3>
          <div class="stack" style="gap: 10px">
            <div class="grid grid--2 property-form__doc-form">
              <div class="field">
                <label>Название документа</label>
                <input class="input" v-model="newDocument.document_name" />
              </div>
              <div class="field">
                <label>Ссылка на файл</label>
                <input class="input" v-model="newDocument.file_url" />
              </div>
              <label class="chip-check">
                <input type="checkbox" v-model="newDocument.is_verified" />
                Проверен
              </label>
              <button class="btn btn--sm btn--primary" type="button" @click="submitDocument">
                Добавить документ
              </button>
            </div>
            <div v-for="doc in documents" :key="doc.id" class="property-form__list-row">
              <div>
                <b>{{ doc.document_name }}</b>
                <div class="muted" style="font-size: 12px">
                  {{ doc.is_verified ? 'Проверен' : 'Не проверен' }}
                  <span v-if="doc.verified_by_username">· {{ doc.verified_by_username }}</span>
                </div>
              </div>
              <a :href="doc.file_url" target="_blank" rel="noreferrer">Открыть</a>
            </div>
            <div v-if="!documents.length" class="muted">Документы не загружены.</div>
          </div>
        </div>

        <div class="panel panel--light property-form__details-block" v-if="auth.isStaff && isEdit">
          <h3 class="h4">Просмотры</h3>
          <div class="stack" style="gap: 10px">
            <div v-for="viewing in viewings" :key="viewing.id" class="property-form__list-row">
              <div>
                <b>{{ formatViewingClient(viewing) }}</b>
                <div class="muted" style="font-size: 12px">
                  {{ formatDate(viewing.scheduled_date || viewing.viewing_date) }}
                  · {{ formatViewingAgent(viewing) }}
                  · {{ viewing.status_name || viewing.status?.name || '—' }}
                </div>
              </div>
            </div>
            <div v-if="!viewings.length" class="muted">Просмотры не запланированы.</div>
          </div>
        </div>

        <div class="panel panel--light property-form__details-block" v-if="auth.isStaff && isEdit">
          <h3 class="h4">История цен</h3>
          <div class="table-wrap property-form__table-wrap">
            <table class="table">
              <thead>
                <tr>
                  <th>Дата</th>
                  <th>Старая</th>
                  <th>Новая</th>
                  <th>Кто изменил</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in priceHistory" :key="item.id">
                  <td>{{ formatDate(item.changed_at) }}</td>
                  <td>{{ item.old_price ? `${item.old_price} ₽` : '—' }}</td>
                  <td>{{ item.new_price ? `${item.new_price} ₽` : '—' }}</td>
                  <td>{{ item.changed_by_username || '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="!priceHistory.length" class="muted">История цен отсутствует.</div>
        </div>

        <div class="panel panel--light property-form__details-block" v-if="propertyOwners.length">
          <h3 class="h4">Собственники</h3>
          <div class="stack" style="gap: 10px">
            <div v-for="(owner, index) in propertyOwners" :key="`${owner.property}-${owner.client_profile}`" class="property-form__list-row">
              <div>
                <b>{{ `Заказчик ${index + 1}` }}</b>
                <div class="muted" style="font-size: 12px">
                  {{ formatOwnerName(owner) }}
                  <span v-if="owner.ownership_share !== null && owner.ownership_share !== undefined">
                    · {{ owner.ownership_share }}%
                  </span>
                </div>
                <div class="muted" style="font-size: 12px">
                  {{ formatOwnerContacts(owner) }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="error" class="error">{{ error }}</div>
      <div class="row" style="justify-content: flex-end; gap: 8px">
        <button class="btn" type="button" @click="$router.back()">Отмена</button>
        <button class="btn btn--accent" :disabled="loading" type="submit">
          {{ loading ? 'Сохранение…' : (isEdit ? 'Сохранить' : 'Создать') }}
        </button>
      </div>
    </form>

    <Teleport to="body">
      <div v-if="viewingDialogOpen" class="modal-overlay" @click.self="closeViewingDialog">
        <div class="modal" style="max-width: 760px; width: calc(100vw - 32px)">
          <div class="surface-head">
            <div class="surface-head__meta">Просмотр объекта</div>
            <h3 class="h3">Запланировать просмотр</h3>
          </div>

          <div class="grid grid--2" style="gap: 14px; margin-top: 18px">
            <RemoteLookupField
              v-model="viewingForm.client_profile"
              label="Клиент"
              endpoint="/client-profiles/"
              placeholder="Поиск клиента"
              :map-option="mapClientProfileOption"
              no-results-text="Клиенты не найдены."
            />
            <RemoteLookupField
              v-model="viewingForm.employee_profile"
              label="Сотрудник"
              endpoint="/employee-profiles/"
              placeholder="Поиск сотрудника"
              :map-option="mapEmployeeProfileOption"
              no-results-text="Сотрудники не найдены."
            />
            <div class="field">
              <label>Дата и время</label>
              <input class="input" type="datetime-local" v-model="viewingForm.scheduled_date" />
            </div>
            <div class="field">
              <label>Статус</label>
              <select class="select" v-model.number="viewingForm.status">
                <option v-for="s in dict.viewingStatuses" :key="s.id" :value="s.id">
                  {{ s.name }}
                </option>
              </select>
            </div>
            <div class="field" style="grid-column: 1 / -1">
              <label>Комментарий</label>
              <textarea class="textarea" v-model="viewingForm.notes" rows="4"></textarea>
            </div>
          </div>

          <div class="row" style="justify-content: flex-end; gap: 8px; margin-top: 18px">
            <button class="btn" type="button" @click="closeViewingDialog">Отмена</button>
            <button class="btn btn--accent" type="button" :disabled="viewingSaving" @click="submitViewing">
              {{ viewingSaving ? 'Сохранение…' : 'Запланировать' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import AddressAutocomplete from '../components/AddressAutocomplete.vue'
import RemoteLookupField from '../components/RemoteLookupField.vue'
import { useDraftPersistence } from '../composables/useDraftPersistence'
import { useUnsavedChangesGuard } from '../composables/useUnsavedChangesGuard'
import { extractError, useToastsStore } from '../store/toasts'
import { useAuthStore } from '../store/auth'
import { LOOKUP_PAGE_SIZE, unpackPaginated } from '@/utils/paginated'
import { formatDate } from '@/utils/formatters'
import {
  normalizePropertyType,
  propertyTypeHasFloor,
  propertyTypeHasLand,
  propertyTypeIsCommercial,
  propertyTypeUsesFloor,
  propertyTypeUsesRooms,
} from '@/utils/propertyTypes'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const toasts = useToastsStore()
const isEdit = computed(() => !!route.params.id)

function createBuildingDetailsForm() {
  return {
    year_built: null,
    total_floors: null,
    building_material: null,
    elevators_count: 0,
  }
}

function createPropertyDetailsForm() {
  return {
    living_area: null,
    kitchen_area: null,
    ceiling_height: null,
    balcony_count: 0,
    bathroom_count: 1,
    bathroom_type: null,
    renovation_type: null,
    bedrooms_count: null,
    floors_count: null,
    land_area: null,
  }
}

function createCommercialPropertyDetailsForm() {
  return {
    commercial_type: null,
    usable_area: null,
    ceiling_height: null,
    floor_load: null,
    electric_power_kw: null,
    has_separate_entrance: false,
    has_display_windows: false,
    is_first_line: false,
    parking_spaces: null,
  }
}

function createAmenityIdsForm() {
  return []
}

function defaultForm() {
  return {
    title: '',
    operation_type: 1,
    status: 1,
    premises_type: 'apartment',
    address: null,
    price: null,
    area_total: null,
    rooms_count: null,
    floor_number: null,
    cadastral_number: '',
    is_published: true,
    description: '',
    building_details: createBuildingDetailsForm(),
    property_details: createPropertyDetailsForm(),
    commercial_property_details: createCommercialPropertyDetailsForm(),
    amenity_ids: createAmenityIdsForm(),
  }
}

function mergeFormState(source = {}) {
  const base = defaultForm()
  const rest = source || {}
  return {
    ...base,
    title: rest.title ?? base.title,
    operation_type: rest.operation_type ?? base.operation_type,
    status: rest.status ?? base.status,
    premises_type: rest.premises_type ?? base.premises_type,
    address: rest.address ?? base.address,
    price: rest.price ?? base.price,
    area_total: rest.area_total ?? base.area_total,
    rooms_count: rest.rooms_count ?? base.rooms_count,
    floor_number: rest.floor_number ?? base.floor_number,
    cadastral_number: rest.cadastral_number ?? base.cadastral_number,
    is_published: rest.is_published ?? base.is_published,
    description: rest.description ?? base.description,
    building_details: {
      ...base.building_details,
      ...(rest.building_details || {}),
    },
    property_details: {
      ...base.property_details,
      ...(rest.property_details || {}),
    },
    commercial_property_details: {
      ...base.commercial_property_details,
      ...(rest.commercial_property_details || {}),
    },
    amenity_ids: Array.isArray(rest.amenity_ids)
      ? [...rest.amenity_ids]
      : [...base.amenity_ids],
  }
}

const form = reactive(defaultForm())

const dict = reactive({
  operations: [],
  statuses: [],
  propertyTypes: [],
  buildingMaterials: [],
  bathroomTypes: [],
  renovationTypes: [],
  commercialTypes: [],
  viewingStatuses: [],
  amenities: [],
})
const addressQuery = ref('')
const addressPicked = ref(null)
const existingAddress = ref('')
const photos = ref([])
const pendingFiles = ref([])
const removedPhotoIds = ref([])
const newPhotoUrl = ref('')
const loading = ref(false)
const error = ref('')
const propertyBaseline = ref('')
const propertyDraftRestored = ref(false)
let initSeq = 0

const formModeLabel = computed(() => (
  isEdit.value ? 'Редактирование' : 'Создание'
))
const addressStateLabel = computed(() => {
  if (addressPicked.value) return 'Выбран'
  if (existingAddress.value) return 'Сохранён'
  return 'Не указан'
})
const normalizedPremisesType = computed(() => normalizePropertyType(form.premises_type))
const isCommercialType = computed(() => propertyTypeIsCommercial(normalizedPremisesType.value))
const selectedFeaturesCount = computed(() => form.amenity_ids.length)
const isRoomsDisabled = computed(() => !propertyTypeUsesRooms(normalizedPremisesType.value))
const isFloorDisabled = computed(() => !propertyTypeUsesFloor(normalizedPremisesType.value))
const propertyData = ref(null)
const propertyOwners = computed(() => propertyData.value?.owners || [])
const documents = ref([])
const viewings = ref([])
const priceHistory = ref([])
const newDocument = reactive({
  document_name: '',
  file_url: '',
  is_verified: false,
})
const viewingDialogOpen = ref(false)
const viewingSaving = ref(false)
const viewingForm = reactive({
  client_profile: null,
  employee_profile: null,
  scheduled_date: '',
  status: null,
  notes: '',
})
const photoCount = computed(() => photos.value.length)
const coverCount = computed(() => photos.value.filter((photo) => photo.is_cover).length)
const propertyDirtySnapshot = computed(() => JSON.stringify(buildPropertyDirtyState()))
const isPropertyDirty = computed(() => propertyDirtySnapshot.value !== propertyBaseline.value)

function onAddressPick(r) {
  addressPicked.value = r
}

function mapClientProfileOption(profile) {
  return {
    id: profile.id,
    label: [profile.last_name, profile.first_name, profile.middle_name].filter(Boolean).join(' ') || profile.username || `Клиент #${profile.id}`,
    hint: profile.username || profile.user?.username || profile.user?.email || '',
  }
}

function mapEmployeeProfileOption(profile) {
  return {
    id: profile.id,
    label: [profile.last_name, profile.first_name, profile.middle_name].filter(Boolean).join(' ') || profile.username || `Сотрудник #${profile.id}`,
    hint: profile.username || profile.user?.username || profile.user?.email || '',
  }
}

function formatViewingClient(viewing) {
  const first = viewing.client_first_name || viewing.client?.first_name || ''
  const last = viewing.client_last_name || viewing.client?.last_name || ''
  const middle = viewing.client_middle_name || viewing.client?.middle_name || ''
  return [last, first, middle].filter(Boolean).join(' ') || viewing.client_username || '—'
}

function formatViewingAgent(viewing) {
  const first = viewing.agent_first_name || viewing.agent?.first_name || ''
  const last = viewing.agent_last_name || viewing.agent?.last_name || ''
  const middle = viewing.agent_middle_name || viewing.agent?.middle_name || ''
  return [last, first, middle].filter(Boolean).join(' ') || viewing.agent_username || '—'
}

function formatOwnerName(owner) {
  const individualName = [owner.client_last_name, owner.client_first_name, owner.client_middle_name].filter(Boolean).join(' ')
  return individualName || owner.client_username || '—'
}

function formatOwnerContacts(owner) {
  return [owner.client_phone, owner.client_email].filter(Boolean).join(' · ') || '—'
}

function openViewingDialog() {
  viewingDialogOpen.value = true
}

function closeViewingDialog() {
  viewingDialogOpen.value = false
}

async function submitDocument() {
  if (!isEdit.value || !newDocument.document_name.trim() || !newDocument.file_url.trim()) return
  const payload = {
    property: route.params.id,
    document_name: newDocument.document_name.trim(),
    file_url: newDocument.file_url.trim(),
    is_verified: !!newDocument.is_verified,
  }
  await api.post('/property-documents/', payload)
  newDocument.document_name = ''
  newDocument.file_url = ''
  newDocument.is_verified = false
  const { data } = await api.get('/property-documents/', { params: { property: route.params.id } })
  documents.value = unpackPaginated(data).items
}

async function submitViewing() {
  if (!isEdit.value || !viewingForm.client_profile || !viewingForm.employee_profile || !viewingForm.scheduled_date) return
  viewingSaving.value = true
  try {
    await api.post('/property-viewings/', {
      property: route.params.id,
      client_profile: viewingForm.client_profile,
      employee_profile: viewingForm.employee_profile,
      scheduled_date: viewingForm.scheduled_date,
      status: viewingForm.status,
      notes: viewingForm.notes,
    })
    closeViewingDialog()
    viewingForm.client_profile = null
    viewingForm.employee_profile = null
    viewingForm.scheduled_date = ''
    viewingForm.status = dict.viewingStatuses[0]?.id || null
    viewingForm.notes = ''
    const { data } = await api.get('/property-viewings/', { params: { property: route.params.id } })
    viewings.value = unpackPaginated(data).items
  } finally {
    viewingSaving.value = false
  }
}

function onFilesSelected(e) {
  const files = Array.from(e.target.files || [])
  for (const file of files) {
    const preview = URL.createObjectURL(file)
    const photo = { file, preview, is_cover: false, _new: true }
    photos.value.push(photo)
    pendingFiles.value.push(photo)
  }
  e.target.value = ''
}

function addPhotoByUrl() {
  const u = newPhotoUrl.value.trim()
  if (!u) return
  photos.value.push({ url: u, image_url: u, is_cover: false, _new: true, _fromUrl: true })
  newPhotoUrl.value = ''
}

function setCover(target) {
  photos.value.forEach(p => { p.is_cover = (p === target) })
}

function revokePreview (photo) {
  if (photo?.preview?.startsWith('blob:')) {
    URL.revokeObjectURL(photo.preview)
  }
}

function removePhoto(p, index) {
  if (p.id) removedPhotoIds.value.push(p.id)
  pendingFiles.value = pendingFiles.value.filter((item) => item !== p)
  revokePreview(p)
  photos.value.splice(index, 1)
}

function buildPropertyDraftData() {
  return {
    form: mergeFormState(form),
    addressQuery: addressQuery.value,
    addressPicked: addressPicked.value,
    newPhotoUrl: newPhotoUrl.value,
    photoUrls: photos.value
      .filter((photo) => photo._new && photo._fromUrl && photo.url)
      .map((photo) => ({
        url: photo.url,
        is_cover: !!photo.is_cover,
      })),
    amenityIds: [...form.amenity_ids],
  }
}

function buildPropertyDirtyState() {
  return {
    ...buildPropertyDraftData(),
    photos: photos.value.map((photo) => ({
      id: photo.id ?? null,
      url: photo.url || photo.image_url || null,
      is_cover: !!photo.is_cover,
      is_new: !!photo._new,
      file_name: photo.file?.name || null,
      file_size: photo.file?.size || null,
    })),
    removedPhotoIds: [...removedPhotoIds.value],
  }
}

function isPropertyDraftEmpty(draft) {
  const formData = mergeFormState(draft?.form || {})
  const base = defaultForm()
  const hasFormValue = JSON.stringify({
    ...formData,
    operation_type: base.operation_type,
    status: base.status,
    address: null,
  }) !== JSON.stringify({
    ...base,
    address: null,
  })

  return !(
    hasFormValue
    || !!draft?.addressQuery
    || !!draft?.addressPicked
    || !!draft?.newPhotoUrl
    || (draft?.photoUrls || []).length
  )
}

function formatPropertyValidationError(data) {
  const labels = {
    title: 'Название',
    operation_type: 'Тип операции',
    status: 'Статус',
    premises_type: 'Тип помещения',
    price: 'Цена',
    area_total: 'Площадь',
    rooms_count: 'Количество комнат',
    floor_number: 'Этаж',
    address: 'Адрес',
  }

  if (!data || typeof data !== 'object') return ''
  const parts = []
  for (const [key, value] of Object.entries(data)) {
    const title = labels[key] || key
    const message = Array.isArray(value) ? value.filter(Boolean).join(' ') : String(value || '')
    if (message) parts.push(`${title}: ${message}`)
  }
  return parts.join(' ')
}

function applyPropertyDraft(draft) {
  Object.assign(form, mergeFormState(draft?.form || {}))
  addressQuery.value = draft?.addressQuery || ''
  addressPicked.value = draft?.addressPicked || null
  newPhotoUrl.value = draft?.newPhotoUrl || ''
  photos.value.forEach(revokePreview)
  photos.value = (draft?.photoUrls || []).map((photo) => ({
    url: photo.url,
    image_url: photo.url,
    is_cover: !!photo.is_cover,
    _new: true,
    _fromUrl: true,
  }))
  form.amenity_ids = Array.isArray(draft?.amenityIds) ? [...draft.amenityIds] : []
  pendingFiles.value = []
  removedPhotoIds.value = []
}

function syncPropertyBaseline() {
  propertyBaseline.value = propertyDirtySnapshot.value
}

function resetPropertyFormState () {
  Object.assign(form, defaultForm())
  addressQuery.value = ''
  addressPicked.value = null
  existingAddress.value = ''
  propertyData.value = null
  documents.value = []
  viewings.value = []
  priceHistory.value = []
  viewingDialogOpen.value = false
  viewingSaving.value = false
  viewingForm.client_profile = null
  viewingForm.employee_profile = null
  viewingForm.scheduled_date = ''
  viewingForm.status = null
  viewingForm.notes = ''
  newDocument.document_name = ''
  newDocument.file_url = ''
  newDocument.is_verified = false
  photos.value.forEach(revokePreview)
  photos.value = []
  pendingFiles.value = []
  removedPhotoIds.value = []
  newPhotoUrl.value = ''
  error.value = ''
  propertyDraftRestored.value = false
}

async function ensureOperationTypesLoaded () {
  if (dict.operations.length) return
  const { data } = await api.get('/operation-types/', {
    params: { page_size: LOOKUP_PAGE_SIZE },
  })
  dict.operations = unpackPaginated(data).items
}

async function ensureLookupLoaded(key, endpoint) {
  if (dict[key].length) return
  const { data } = await api.get(endpoint, {
    params: { page_size: LOOKUP_PAGE_SIZE },
  })
  dict[key] = unpackPaginated(data).items
}

async function initializeForm () {
  const seq = ++initSeq
  loading.value = true
  resetPropertyFormState()

  try {
    await Promise.all([
      ensureOperationTypesLoaded(),
      ensureLookupLoaded('statuses', '/property-statuses/'),
      ensureLookupLoaded('propertyTypes', '/property-types/'),
      ensureLookupLoaded('buildingMaterials', '/building-materials/'),
      ensureLookupLoaded('bathroomTypes', '/bathroom-types/'),
      ensureLookupLoaded('renovationTypes', '/renovation-types/'),
      ensureLookupLoaded('commercialTypes', '/commercial-property-types/'),
      ensureLookupLoaded('viewingStatuses', '/viewing-statuses/'),
      ensureLookupLoaded('amenities', '/amenities/'),
    ])
    if (seq !== initSeq) return

    if (isEdit.value) {
      const { data } = await api.get(`/properties/${route.params.id}/`)
      if (seq !== initSeq) return
      propertyData.value = data
      Object.assign(form, {
        title: data.title,
        operation_type: data.operation_type,
        status: data.status,
        premises_type: data.premises_type || 'apartment',
        address: data.address,
        price: data.price,
        area_total: data.area_total,
        rooms_count: data.rooms_count,
        floor_number: data.floor_number,
        cadastral_number: data.cadastral_number,
        is_published: data.is_published,
        description: data.description,
        building_details: {
          ...createBuildingDetailsForm(),
          ...(data.building_details || {}),
          building_material: data.building_details?.building_material
            ?? data.building_details?.building_material_data?.id
            ?? null,
        },
        property_details: {
          ...createPropertyDetailsForm(),
          ...(data.property_details || {}),
          bathroom_type: data.property_details?.bathroom_type
            ?? data.property_details?.bathroom_type_data?.id
            ?? null,
          renovation_type: data.property_details?.renovation_type
            ?? data.property_details?.renovation_type_data?.id
            ?? null,
        },
        commercial_property_details: {
          ...createCommercialPropertyDetailsForm(),
          ...(data.commercial_property_details || {}),
          commercial_type: data.commercial_property_details?.commercial_type
            ?? data.commercial_property_details?.commercial_type_data?.id
            ?? null,
        },
        amenity_ids: (data.amenities || []).map((item) => item.amenity),
      })
      existingAddress.value = data.full_address || ''
      photos.value = (data.photos || []).map((photo) => ({ ...photo }))
      documents.value = unpackPaginated(data.documents).items
      priceHistory.value = unpackPaginated(data.price_history).items
      if (isEdit.value) {
        const [docsResp, priceResp, viewingsResp] = await Promise.all([
          api.get('/property-documents/', { params: { property: route.params.id } }).catch(() => ({ data: [] })),
          api.get('/property-price-history/', { params: { property: route.params.id } }).catch(() => ({ data: [] })),
          auth.isStaff
            ? api.get('/property-viewings/', { params: { property: route.params.id } }).catch(() => ({ data: [] }))
            : Promise.resolve({ data: [] }),
        ])
        documents.value = unpackPaginated(docsResp.data).items
        priceHistory.value = unpackPaginated(priceResp.data).items
        viewings.value = unpackPaginated(viewingsResp.data).items
        viewingForm.status = dict.viewingStatuses[0]?.id || null
      }
      syncPropertyBaseline()
    } else {
      syncPropertyBaseline()
    }
  } catch (e) {
    if (seq !== initSeq) return
    error.value = extractError(e, 'Failed to initialize property form.')
  } finally {
    if (seq === initSeq) {
      loading.value = false
    }
  }
}

const { clearDraft: clearPropertyDraft } = useDraftPersistence({
  key: 'property-form:create',
  enabled: () => !isEdit.value,
  getData: buildPropertyDraftData,
  applyData: (draft) => {
    propertyDraftRestored.value = true
    applyPropertyDraft(draft)
    toasts.info('Черновик объекта восстановлен')
  },
  isEmpty: isPropertyDraftEmpty,
})

useUnsavedChangesGuard({
  enabled: () => isPropertyDirty.value,
  isDirty: () => isPropertyDirty.value,
  message: 'Есть несохранённые изменения в карточке объекта. Покинуть страницу?',
})

async function uploadPhotos(propertyId) {
  for (const p of pendingFiles.value) {
    const fd = new FormData()
    fd.append('property', propertyId)
    fd.append('image', p.file)
    fd.append('is_cover', p.is_cover ? 'true' : 'false')
    await api.post('/property-photos/', fd,
      { headers: { 'Content-Type': 'multipart/form-data' } })
  }
  pendingFiles.value = []

  for (const p of photos.value.filter(x => x._new && x._fromUrl)) {
    await api.post('/property-photos/', {
      property: propertyId,
      url: p.url,
      is_cover: p.is_cover,
    })
  }

  for (const id of removedPhotoIds.value) {
    await api.delete(`/property-photos/${id}/`)
  }
  removedPhotoIds.value = []

  const selectedExistingCover = photos.value.find((photo) => photo.is_cover && photo.id)
  if (selectedExistingCover) {
    await api.post(`/property-photos/${selectedExistingCover.id}/set_cover/`)
  }
}

async function submit() {
  loading.value = true; error.value = ''
  try {
    const payload = {
      title: form.title,
      operation_type: form.operation_type,
      status: form.status,
      premises_type: form.premises_type,
      price: form.price,
      area_total: form.area_total,
      rooms_count: isRoomsDisabled.value ? null : form.rooms_count,
      floor_number: isFloorDisabled.value ? null : form.floor_number,
      cadastral_number: form.cadastral_number || null,
      is_published: !!form.is_published,
      description: form.description,
      building_details_data: {
        ...form.building_details,
        building_material: form.building_details.building_material || null,
      },
      property_details_data: {
        ...form.property_details,
        bathroom_type: form.property_details.bathroom_type || null,
        renovation_type: form.property_details.renovation_type || null,
      },
      commercial_property_details_data: {
        ...form.commercial_property_details,
        commercial_type: form.commercial_property_details.commercial_type || null,
      },
      amenity_ids: [...form.amenity_ids],
    }
    if (addressPicked.value) {
      payload.address_data = addressPicked.value
    } else if (form.address) {
      payload.address = form.address
    } else if (!isEdit.value) {
      throw new Error('Выберите адрес из подсказок.')
    }

    const url = isEdit.value
      ? `/properties/${route.params.id}/` : '/properties/'
    const method = isEdit.value ? 'put' : 'post'
    const { data } = await api[method](url, payload)

    await uploadPhotos(data.id)
    clearPropertyDraft()
    syncPropertyBaseline()
    router.push(`/properties/${data.id}`)
  } catch (e) {
    error.value = extractError(e, 'Не удалось сохранить объект.')
    const data = e.response?.data
    if (typeof data === 'object' && data) {
      const formatted = formatPropertyValidationError(data)
      if (formatted) error.value = formatted
      else error.value = extractError(e, 'Не удалось сохранить объект.')
    } else {
      error.value = e.message || 'Не удалось сохранить объект.'
    }
  } finally {
    loading.value = false
  }
}

watch(() => `${route.name || ''}:${route.params.id || 'new'}`, () => {
  void initializeForm()
}, { immediate: true })
watch(() => form.premises_type, (value) => {
  if (!propertyTypeUsesRooms(value)) {
    form.rooms_count = null
  }
  if (!propertyTypeUsesFloor(value)) {
    form.floor_number = null
  }
  if (propertyTypeIsCommercial(value)) {
    form.property_details.floors_count = null
    form.property_details.land_area = null
    form.property_details.living_area = null
    form.property_details.kitchen_area = null
    form.property_details.bathroom_count = 0
    form.property_details.bathroom_type = null
    form.property_details.renovation_type = null
    form.property_details.bedrooms_count = null
  } else {
    form.commercial_property_details.commercial_type = null
    form.commercial_property_details.usable_area = null
    form.commercial_property_details.ceiling_height = null
    form.commercial_property_details.floor_load = null
    form.commercial_property_details.electric_power_kw = null
    form.commercial_property_details.parking_spaces = null
    form.commercial_property_details.has_separate_entrance = false
    form.commercial_property_details.has_display_windows = false
    form.commercial_property_details.is_first_line = false
  }
})

onBeforeUnmount(() => {
  photos.value.forEach(revokePreview)
})
</script>

<style scoped>
.property-form-page {
  min-height: 0;
}

.property-form__section-head {
  margin-bottom: 2px;
}

.property-form__main-grid {
  gap: 16px;
}
.property-form__main-grid > .field > .select {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(230, 238, 242, 0.95));
  color: var(--c-page-text);
  border-color: rgba(21, 56, 57, 0.16);
  color-scheme: light;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.84),
    0 10px 22px rgba(16, 55, 52, 0.08);
  background-image:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(230, 238, 242, 0.95)),
    linear-gradient(45deg, transparent 50%, rgba(21, 56, 57, 0.62) 50%),
    linear-gradient(135deg, rgba(21, 56, 57, 0.62) 50%, transparent 50%);
  background-position:
    0 0,
    calc(100% - 24px) calc(50% - 3px),
    calc(100% - 18px) calc(50% - 3px);
  background-size:
    100% 100%,
    6px 6px,
    6px 6px;
  background-repeat: no-repeat;
  padding-right: 42px;
}


.property-form__floor-row {
  gap: 10px;
}

.chip-check {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 38px;
  padding: 0 14px;
  border-radius: var(--r-pill);
  border: 1px solid var(--c-border);
  background: rgba(255, 255, 255, 0.06);
  color: var(--c-ink-soft);
  font-size: 13px;
  cursor: pointer;
  transition: transform 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease, background 0.3s ease, color 0.3s ease;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.chip-check:hover {
  transform: translateY(-2px);
  border-color: var(--c-border-strong);
  box-shadow: 0 10px 20px rgba(31, 163, 154, 0.08);
}

.chip-check input {
  accent-color: var(--c-accent);
}

.chip-check:has(input:checked) {
  background: linear-gradient(135deg, rgba(31, 163, 154, 0.18), rgba(99, 208, 197, 0.16));
  color: #effffd;
  border-color: rgba(99, 208, 197, 0.28);
  box-shadow: 0 0 18px rgba(99, 208, 197, 0.12);
}

.photo-tile {
  position: relative;
  aspect-ratio: 4 / 3;
  overflow: hidden;
  border-radius: 22px;
  border: 1px solid var(--c-border);
  background: rgba(255, 255, 255, 0.06);
  box-shadow: var(--shadow-1);
  transition: transform 0.3s ease, box-shadow 0.3s ease, background 0.3s ease;
}

.photo-tile:hover {
  transform: translateY(-5px);
  background: rgba(255, 255, 255, 0.08);
  box-shadow: var(--shadow-glow);
}

.photo-tile img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.photo-tile__overlay {
  position: absolute;
  inset: auto 0 0 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px;
  background: linear-gradient(to top, rgba(7, 19, 29, 0.86), transparent);
}

.property-form__photos-empty {
  min-height: 140px;
}

.property-form__photos-actions {
  align-items: stretch;
}

.property-form__photo-url {
  width: 100%;
}

@media (max-width: 720px) {
  .property-form__floor-row,
  .property-form__photos-actions,
  .property-form__photo-url {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
