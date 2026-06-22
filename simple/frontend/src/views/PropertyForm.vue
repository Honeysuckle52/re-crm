<template>
  <section class="stack property-form-page">
    <div class="hero property-form__hero">
      <div class="row row--between property-form__hero-top">
        <div class="stack property-form__hero-copy">
          <div class="hero__eyebrow">{{ isEdit ? 'Редактирование' : 'Новый объект' }}</div>
          <h1 class="h2 property-form__hero-title">
            {{ isEdit ? 'Изменить объект' : 'Создать объект' }}
          </h1>
          <div class="property-form__hero-text">
            Заполните карточку по шагам: тип, адрес, параметры, медиа и описание.
          </div>
        </div>
        <button class="btn btn--ghost" type="button" @click="$router.back()">Назад</button>
      </div>

      <div class="property-form__stepper">
        <button
          v-for="step in steps"
          :key="step.id"
          type="button"
          class="property-form__step"
          :class="{
            'is-active': currentStep === step.id,
            'is-complete': isStepComplete(step.id),
            'is-locked': !isStepAccessible(step.id),
          }"
          :disabled="!isStepAccessible(step.id)"
          @click="openStep(step.id)"
        >
          <span class="property-form__step-index">{{ step.id }}</span>
          <span class="property-form__step-copy">
            <span class="property-form__step-title">{{ step.title }}</span>
            <span class="property-form__step-caption">{{ step.caption }}</span>
          </span>
        </button>
      </div>
    </div>

    <form class="panel panel--light property-form" novalidate @submit.prevent="handleSubmit">
      <div class="surface-head property-form__surface-head">
        <div class="surface-head__meta">
          <div class="surface-head__meta">Шаг {{ currentStep }} из {{ steps.length }}</div>
          <h2 class="h3">{{ currentStepMeta.title }}</h2>
        </div>
        <div class="surface-head__caption">{{ currentStepMeta.caption }}</div>
      </div>

      <div v-if="currentStepErrors.length" class="property-form__step-errors">
        <div v-for="message in currentStepErrors" :key="message" class="property-form__step-error">
          {{ message }}
        </div>
      </div>

      <section v-show="currentStep === 1" class="stack property-form__step-panel">
        <div class="panel panel--light property-form__subpanel">
          <div class="surface-head">
            <div class="surface-head__meta">
              <h3 class="h4">Тип и операция</h3>
            </div>
            <div class="surface-head__caption">
              Выберите сценарий сделки и тип объекта. От этого зависит весь набор полей дальше.
            </div>
          </div>

          <div class="grid grid--2 property-form__grid">
            <div class="field">
              <label>Тип операции <span class="property-form__required">*</span></label>
              <select ref="operationTypeFieldRef" class="select" v-model.number="form.operation_type">
                <option v-for="item in dict.operations" :key="item.id" :value="item.id">
                  {{ item.name }}
                </option>
              </select>
              <div v-if="fieldErrors.operation_type" class="property-form__field-error">{{ fieldErrors.operation_type }}</div>
            </div>

            <div class="field">
              <label>Тип объекта <span class="property-form__required">*</span></label>
              <select ref="premisesTypeFieldRef" class="select" v-model="form.premises_type">
                <option v-for="item in dict.propertyTypes" :key="item.id" :value="item.code">
                  {{ item.name }}
                </option>
              </select>
              <div v-if="fieldErrors.premises_type" class="property-form__field-error">{{ fieldErrors.premises_type }}</div>
            </div>

            <div v-if="auth.isStaff" class="field">
              <label>Статус</label>
              <select class="select" v-model.number="form.status">
                <option v-for="item in dict.statuses" :key="item.id" :value="item.id">
                  {{ item.name }}
                </option>
              </select>
            </div>

            <div v-if="auth.isStaff" class="field">
              <label>Публикация</label>
              <label class="chip-check property-form__chip-inline">
                <input type="checkbox" v-model="form.is_published" />
                Опубликован
              </label>
            </div>
          </div>
        </div>
      </section>

      <section v-show="currentStep === 2" class="stack property-form__step-panel">
        <div class="panel panel--light property-form__subpanel">
          <div class="surface-head">
            <div class="surface-head__meta">
              <h3 class="h4">Адрес объекта</h3>
            </div>
            <div class="surface-head__caption">
              Подсказки адресов загружаются через DaData, карты и окружение подтягиваются из 2GIS.
            </div>
          </div>

          <p class="muted property-form__text">
            Начните вводить адрес, затем выберите точный вариант из подсказок.
          </p>

          <AddressAutocomplete
            ref="addressFieldRef"
            v-model="addressQuery"
            label="Поиск по адресу"
            placeholder="Город, улица, дом, квартира…"
            @pick="onAddressPick"
          />
          <div v-if="fieldErrors.address" class="property-form__field-error">{{ fieldErrors.address }}</div>

          <div v-if="addressPicked" class="row property-form__tags">
            <span class="tag tag--accent">{{ addressPicked.value }}</span>
            <span v-if="addressPicked.postal_code" class="tag">
              Индекс: {{ addressPicked.postal_code }}
            </span>
          </div>

          <div v-else-if="existingAddress" class="empty property-form__address-empty">
            <div>
              <strong>Текущий адрес</strong>
              <div class="muted">{{ existingAddress }}</div>
            </div>
          </div>

        </div>
      </section>

      <section v-show="currentStep === 3" class="stack property-form__step-panel">
        <div class="panel panel--light property-form__subpanel">
          <div class="surface-head">
            <div class="surface-head__meta">
              <h3 class="h4">Параметры объекта</h3>
            </div>
            <div class="surface-head__caption">
              Заполните базовые данные объекта и характеристики из связанных таблиц.
            </div>
          </div>

          <div class="grid grid--2 property-form__grid">
            <div class="field">
              <label>Заголовок <span class="property-form__required">*</span></label>
              <input
                ref="titleFieldRef"
                class="input"
                v-model="form.title"
                placeholder="Например: 2-комнатная на Ленина" />
              <div v-if="fieldErrors.title" class="property-form__field-error">{{ fieldErrors.title }}</div>
            </div>

            <div class="field">
              <label>Цена, ₽ <span class="property-form__required">*</span></label>
              <input ref="priceFieldRef" class="input" type="number" step="1" min="0" max="9999999999" v-model.number="form.price" />
              <div v-if="fieldErrors.price" class="property-form__field-error">{{ fieldErrors.price }}</div>
            </div>

            <div class="field">
              <label>Общая площадь, м²</label>
              <input class="input" type="number" step="0.01" min="0.1" max="999999" v-model.number="form.area_total" />
              <div v-if="fieldErrors.area_total" class="property-form__field-error">{{ fieldErrors.area_total }}</div>
            </div>

            <div v-if="showRoomsField" class="field">
              <label>Количество комнат</label>
              <input class="input" type="number" min="1" max="100" v-model.number="form.rooms_count" />
            </div>

            <div v-if="showFloorField" class="field">
              <label>Этаж</label>
              <input class="input" type="number" min="-10" max="500" v-model.number="form.floor_number" />
              <div v-if="fieldErrors.floor_number" class="property-form__field-error">{{ fieldErrors.floor_number }}</div>
            </div>

            <div class="field">
              <label>Кадастровый номер</label>
              <input class="input" v-model="form.cadastral_number" />
            </div>
          </div>
        </div>

        <div v-if="showBuildingDetailsSection" class="panel panel--light property-form__subpanel">
          <div class="surface-head">
            <div class="surface-head__meta">
              <h3 class="h4">О доме</h3>
            </div>
            <div class="surface-head__caption">Характеристики здания и общие параметры дома.</div>
          </div>

          <div class="grid grid--2 property-form__grid">
            <div class="field">
              <label>Год постройки</label>
              <input class="input" type="number" min="1800" :max="currentYear" v-model.number="form.building_details.year_built" />
              <div v-if="fieldErrors.year_built" class="property-form__field-error">{{ fieldErrors.year_built }}</div>
            </div>

            <div class="field">
              <label>Количество этажей в доме</label>
              <input class="input" type="number" min="1" max="500" v-model.number="form.building_details.total_floors" />
              <div v-if="fieldErrors.total_floors" class="property-form__field-error">{{ fieldErrors.total_floors }}</div>
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
              <label>Количество лифтов</label>
              <input class="input" type="number" min="0" max="50" v-model.number="form.building_details.elevators_count" />
            </div>
          </div>
        </div>

        <!-- Раздел "О помещении" — только для жилых объектов и гаража -->
        <div v-if="showResidentialDetailsSection || showGarageRenovationOnly" class="panel panel--light property-form__subpanel">
          <div class="surface-head">
            <div class="surface-head__meta">
              <h3 class="h4">{{ isGarageType ? 'Параметры гаража' : 'О помещении' }}</h3>
            </div>
            <div class="surface-head__caption">
              {{ isGarageType ? 'Тип ремонта и состояние гаражного помещения.' : 'Планировка, санузлы, ремонт и жилые характеристики.' }}
            </div>
          </div>

          <div class="grid grid--2 property-form__grid">
            <div v-if="showResidentialAreaFields" class="field">
              <label>Жилая площадь, м²</label>
              <input class="input" type="number" step="0.01" min="0.1" max="99999" v-model.number="form.property_details.living_area" />
            </div>

            <div v-if="showResidentialAreaFields" class="field">
              <label>Площадь кухни, м²</label>
              <input class="input" type="number" step="0.01" min="0.1" max="9999" v-model.number="form.property_details.kitchen_area" />
            </div>

            <div v-if="showResidentialAreaFields" class="field">
              <label>Высота потолков, м</label>
              <input class="input" type="number" step="0.01" min="1.5" max="30" v-model.number="form.property_details.ceiling_height" />
            </div>

            <div v-if="showBalconyField" class="field">
              <label>Количество балконов</label>
              <input class="input" type="number" min="0" max="20" v-model.number="form.property_details.balcony_count" />
            </div>

            <div v-if="showBathroomFields" class="field">
              <label>Количество санузлов</label>
              <input class="input" type="number" min="0" max="50" v-model.number="form.property_details.bathroom_count" />
            </div>

            <div v-if="showBathroomFields" class="field">
              <label>Тип санузла</label>
              <select class="select" v-model="form.property_details.bathroom_type">
                <option :value="null">Не указан</option>
                <option v-for="item in dict.bathroomTypes" :key="item.id" :value="item.id">
                  {{ item.name }}
                </option>
              </select>
            </div>

            <div v-if="showRenovationField" class="field">
              <label>Тип ремонта</label>
              <select class="select" v-model="form.property_details.renovation_type">
                <option :value="null">Не указан</option>
                <option v-for="item in dict.renovationTypes" :key="item.id" :value="item.id">
                  {{ item.name }}
                </option>
              </select>
            </div>

            <div v-if="showBedroomField" class="field">
              <label>Количество спален</label>
              <input class="input" type="number" min="0" max="50" v-model.number="form.property_details.bedrooms_count" />
            </div>

            <div v-if="isHouseType" class="field">
              <label>Количество этажей в частном доме</label>
              <input class="input" type="number" min="1" max="50" v-model.number="form.property_details.floors_count" />
            </div>

            <div v-if="showLandAreaField" class="field">
              <label>Площадь участка, м²</label>
              <input class="input" type="number" step="0.01" min="0.1" max="9999999" v-model.number="form.property_details.land_area" />
            </div>
          </div>
        </div>

        <div v-if="isCommercialType" class="panel panel--light property-form__subpanel">
          <div class="surface-head">
            <div class="surface-head__meta">
              <h3 class="h4">Коммерческая недвижимость</h3>
            </div>
            <div class="surface-head__caption">Профиль помещения, полезная площадь и коммерческие атрибуты.</div>
          </div>

          <div class="grid grid--2 property-form__grid">
            <div class="field">
              <label>Тип коммерческой недвижимости</label>
              <select class="select" v-model="form.commercial_property_details.commercial_type">
                <option :value="null">Не указан</option>
                <option v-for="item in dict.commercialTypes" :key="item.id" :value="item.id">
                  {{ item.name }}
                </option>
              </select>
            </div>

            <div class="field">
              <label>Полезная площадь, м²</label>
              <input class="input" type="number" step="0.01" min="0.1" max="999999" v-model.number="form.commercial_property_details.usable_area" />
            </div>

            <div class="field">
              <label>Высота потолков, м</label>
              <input class="input" type="number" step="0.01" min="1.5" max="50" v-model.number="form.commercial_property_details.ceiling_height" />
            </div>

            <div class="field">
              <label>Нагрузка на пол, кг/м²</label>
              <input class="input" type="number" step="0.01" min="0" max="100000" v-model.number="form.commercial_property_details.floor_load" />
            </div>

            <div class="field">
              <label>Мощность электроснабжения, кВт</label>
              <input class="input" type="number" step="0.01" min="0" max="100000" v-model.number="form.commercial_property_details.electric_power_kw" />
            </div>

            <div class="field">
              <label>Количество парковочных мест</label>
              <input class="input" type="number" min="0" max="10000" v-model.number="form.commercial_property_details.parking_spaces" />
            </div>
          </div>

          <div class="property-form__chip-grid">
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

        <div class="panel panel--light property-form__subpanel">
          <div class="surface-head">
            <div class="surface-head__meta">
              <h3 class="h4">Удобства</h3>
            </div>
            <div class="surface-head__caption">Отметьте удобства, которые относятся к объекту.</div>
          </div>

          <div class="property-form__chip-grid">
            <label v-for="item in dict.amenities" :key="item.id" class="chip-check">
              <input type="checkbox" :value="item.id" v-model="form.amenity_ids" />
              {{ item.name }}
            </label>
          </div>
        </div>
      </section>

      <section v-show="currentStep === 4" class="stack property-form__step-panel">
        <div class="panel panel--light property-form__subpanel">
          <div class="surface-head">
            <div class="surface-head__meta">
              <h3 class="h4">Медиа</h3>
            </div>
            <div class="surface-head__caption">
              Добавьте свои фото файлами или по ссылке. Обложка выбирается вручную.
            </div>
          </div>

          <p class="muted property-form__text">
            Пос��е создания объекта карты и спутниковые снимки могут подтянуться из 2GIS по адресу.
          </p>

          <div v-if="photos.length" class="grid grid--3 property-form__photo-grid">
            <div v-for="(photo, index) in photos" :key="photo.id || `new-${index}`" class="photo-tile">
              <img :src="photo.image_url || photo.preview || photo.url" alt="Фото объекта" />
              <div class="photo-tile__overlay">
                <label class="tag tag--panel property-form__photo-cover">
                  <input type="checkbox" v-model="photo.is_cover" @change="setCover(photo)" />
                  {{ photo.is_cover ? 'Обложка' : 'Сделать обложкой' }}
                </label>
                <button class="btn btn--danger btn--sm" type="button" @click="removePhoto(photo, index)">
                  Удалить
                </button>
              </div>
            </div>
          </div>
          <div v-else class="empty property-form__photos-empty">
            Фотографии пока не добавлены.
          </div>
          <div v-if="fieldWarnings.photos" class="property-form__field-error">{{ fieldWarnings.photos }}</div>

          <div class="row property-form__photo-actions">
            <label class="btn btn--sm property-form__upload-btn">
              Загрузить файл
              <input type="file" accept="image/*" multiple @change="onFilesSelected" />
            </label>
            <div class="row property-form__photo-url">
              <input class="input" v-model="newPhotoUrl" placeholder="Или вставьте ссылку на изображение" />
              <button class="btn btn--sm" type="button" @click="addPhotoByUrl">Добавить ссылку</button>
            </div>
          </div>
        </div>
      </section>

      <section v-show="currentStep === 5" class="stack property-form__step-panel">
        <div class="panel panel--light property-form__subpanel">
          <div class="surface-head">
            <div class="surface-head__meta">
              <h3 class="h4">Описание</h3>
            </div>
            <div class="surface-head__caption">Свободное описание объекта для карточки и работы мен��джера.</div>
          </div>

          <div class="field">
            <label>Описание объекта</label>
            <textarea
              class="textarea"
              v-model="form.description"
              rows="6"
              placeholder="Расскажите об объекте: состояние, инфраструктура, транспорт…"></textarea>
          </div>
        </div>

        <div v-if="auth.isStaff" class="panel panel--light property-form__subpanel">
          <div class="surface-head">
            <div class="surface-head__meta">
              <h3 class="h4">Документы объекта</h3>
            </div>
            <div class="surface-head__caption">Ссылки на документы и статус их проверки.</div>
          </div>

          <div class="stack property-form__stack-sm">
            <div class="grid grid--2 property-form__grid">
              <div class="field">
                <label>Название документа</label>
                <input class="input" v-model="newDocument.document_name" />
              </div>
              <div class="field">
                <label>Ссылк�� на файл</label>
                <input class="input" v-model="newDocument.file_url" />
              </div>
            </div>

            <div class="row property-form__doc-actions">
              <label class="chip-check">
                <input type="checkbox" v-model="newDocument.is_verified" />
                Проверен
              </label>
              <button class="btn btn--sm btn--primary" type="button" @click="submitDocument">
                Добавить документ
              </button>
            </div>

            <div v-if="documents.length" class="stack property-form__stack-sm">
              <div v-for="doc in documents" :key="doc.id" class="property-form__list-row">
                <div>
                  <strong>{{ doc.document_name }}</strong>
                  <div class="muted">
                    {{ doc.is_verified ? 'Проверен' : 'Не проверен' }}
                    <span v-if="doc.verified_by_username"> В· {{ doc.verified_by_username }}</span>
                  </div>
                </div>
                <a :href="doc.file_url" target="_blank" rel="noreferrer">Открыть</a>
              </div>
            </div>
            <div v-else class="muted">Документы не загружены.</div>
          </div>
        </div>

        <div v-if="auth.isStaff && isEdit" class="panel panel--light property-form__subpanel">
          <div class="surface-head">
            <div class="surface-head__meta">
              <h3 class="h4">Просмотры</h3>
            </div>
            <div class="surface-head__caption">
              Запланированные просмотры по объекту.
            </div>
          </div>

          <div class="row property-form__section-actions">
            <button class="btn btn--sm btn--accent" type="button" @click="openViewingDialog">
              Запланировать просмотр
            </button>
          </div>

          <div v-if="viewings.length" class="table-wrap">
            <table class="table table--responsive-cards">
              <thead>
                <tr>
                  <th>Дата</th>
                  <th>Клиент</th>
                  <th>Сотрудник</th>
                  <th>Статус</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="viewing in viewings" :key="viewing.id">
                  <td data-label="Дата">{{ formatDate(viewing.scheduled_date || viewing.viewing_date) }}</td>
                  <td data-label="Клиент">{{ formatViewingClient(viewing) }}</td>
                  <td data-label="Сотрудник">{{ formatViewingAgent(viewing) }}</td>
                  <td data-label="Статус">{{ viewing.status_name || viewing.status?.name || '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="muted">Просмотры не запланированы.</div>
        </div>

        <div v-if="auth.isStaff && isEdit" class="panel panel--light property-form__subpanel">
          <div class="surface-head">
            <div class="surface-head__meta">
              <h3 class="h4">История цен</h3>
            </div>
            <div class="surface-head__caption">Изменения стоимости объекта по времени и сотрудникам.</div>
          </div>

          <div v-if="priceHistory.length" class="table-wrap">
            <table class="table table--responsive-cards">
              <thead>
                <tr>
                  <th>Дата</th>
                  <th>Старая цена</th>
                  <th>Новая цена</th>
                  <th>Кто изменил</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in priceHistory" :key="item.id">
                  <td data-label="Дата">{{ formatDate(item.changed_at) }}</td>
                  <td data-label="Старая цена">{{ item.old_price ? `${item.old_price} ₽` : '—' }}</td>
                  <td data-label="Новая цена">{{ item.new_price ? `${item.new_price} ₽` : '—' }}</td>
                  <td data-label="Кто изменил">{{ item.changed_by_username || '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="muted">История цен отсутствует.</div>
        </div>

        <div v-if="propertyOwners.length" class="panel panel--light property-form__subpanel">
          <div class="surface-head">
            <div class="surface-head__meta">
              <h3 class="h4">Собственники</h3>
            </div>
            <div class="surface-head__caption">Список собственников, привязанных к объекту.</div>
          </div>

          <div class="stack property-form__stack-sm">
            <div
              v-for="(owner, index) in propertyOwners"
              :key="`${owner.property}-${owner.client_profile}`"
              class="property-form__list-row"
            >
              <div>
                <strong>{{ propertyOwners.length > 1 ? `Заказчик ${index + 1}` : 'Заказчик' }}</strong>
                <div class="muted">
                  {{ formatOwnerName(owner) }}
                  <span v-if="owner.ownership_share !== null && owner.ownership_share !== undefined">
                    В· {{ owner.ownership_share }}%
                  </span>
                </div>
                <div class="muted">{{ formatOwnerContacts(owner) }}</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <div v-if="error" class="property-form__error-block" role="alert">
        <div class="property-form__error-header">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/>
            <line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          <span>Ошибка сохранения</span>
        </div>
        <ul v-if="errorDetails.fields.length" class="property-form__error-list">
          <li v-for="field in errorDetails.fields" :key="field.label">
            <b>{{ field.label }}:</b> {{ field.message }}
          </li>
        </ul>
        <p v-else class="property-form__error-text">{{ error }}</p>
        <button
          v-if="errorDetails.step && errorDetails.step !== currentStep"
          class="property-form__error-goto"
          type="button"
          @click="currentStep = errorDetails.step"
        >
          Перейти к шагу {{ errorDetails.step }} ({{ steps[errorDetails.step - 1]?.title }})
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="9 18 15 12 9 6"/>
          </svg>
        </button>
      </div>

      <div class="row row--between property-form__footer">
        <button class="btn" type="button" @click="$router.back()">Отмена</button>
        <div class="row property-form__footer-actions">
          <button class="btn" type="button" :disabled="currentStep === 1 || loading" @click="goPrev">
            Назад
          </button>
          <button
            v-if="currentStep < steps.length"
            class="btn btn--primary"
            type="button"
            :disabled="loading || !isCurrentStepValid"
            @click="goNext"
          >
            Далее
          </button>
          <button
            v-else
            class="btn btn--accent"
            :disabled="loading"
            type="submit"
          >
            {{ loading ? 'Сохранение…' : (isEdit ? 'Сохранить' : 'Создать') }}
          </button>
        </div>
      </div>
    </form>

    <Teleport to="body">
      <div v-if="viewingDialogOpen" class="modal-overlay" @click.self="closeViewingDialog">
        <div class="modal property-form__modal">
          <div class="surface-head">
            <div class="surface-head__meta">
              <h3 class="h3">Запланировать просмотр</h3>
            </div>
            <div class="surface-head__caption">Выберите клиента, сотрудника и время просмотра.</div>
          </div>

          <div class="grid grid--2 property-form__modal-grid">
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
                <option v-for="item in dict.viewingStatuses" :key="item.id" :value="item.id">
                  {{ item.name }}
                </option>
              </select>
            </div>
            <div class="field property-form__modal-field-full">
              <label>Комментарий</label>
              <textarea class="textarea" v-model="viewingForm.notes" rows="4"></textarea>
            </div>
          </div>

          <div class="row property-form__modal-actions">
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
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
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
  getPropertyTypeSchema,
  normalizePropertyType,
  propertyTypeIsCommercial,
} from '@/utils/propertyTypes'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const toasts = useToastsStore()
const isEdit = computed(() => !!route.params.id)

const steps = [
  { id: 1, title: 'Тип и операция', caption: 'Сценарий сделки и публикация' },
  { id: 2, title: 'Адрес', caption: 'DaData и локация объекта' },
  { id: 3, title: 'Параметры объекта', caption: 'Основные поля и характеристики' },
  { id: 4, title: 'Медиа', caption: 'Фото, обложка и ссылки' },
  { id: 5, title: 'Описание и документы', caption: 'Контент, документы и история' },
]

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
    operation_type: null,
    status: null,
    premises_type: '',
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
const addressConfirmedValue = ref('')
const existingAddress = ref('')
const photos = ref([])
const pendingFiles = ref([])
const removedPhotoIds = ref([])
const newPhotoUrl = ref('')
const loading = ref(false)
const error = ref('')
const propertyBaseline = ref('')
const propertyDraftRestored = ref(false)
const propertyData = ref(null)
const documents = ref([])
const viewings = ref([])
const priceHistory = ref([])
const currentStep = ref(1)
const operationTypeFieldRef = ref(null)
const premisesTypeFieldRef = ref(null)
const addressFieldRef = ref(null)
const titleFieldRef = ref(null)
const priceFieldRef = ref(null)
const touchedSteps = reactive({
  1: false,
  2: false,
  3: false,
  4: false,
  5: false,
})
let initSeq = 0
// Флаг подавления очистки полей при программной инициализации формы редактирования
let isInitializingForm = false

const currentYear = new Date().getFullYear()
const normalizedPremisesType = computed(() => normalizePropertyType(form.premises_type))
const propertyTypeSchema = computed(() => getPropertyTypeSchema(normalizedPremisesType.value))
const isCommercialType = computed(() => propertyTypeIsCommercial(normalizedPremisesType.value))
const isHouseType = computed(() => normalizedPremisesType.value === 'house')
const isLandType = computed(() => normalizedPremisesType.value === 'land')
const isGarageType = computed(() => normalizedPremisesType.value === 'garage')
// "О доме": скрываем для земли, гаража и коммерции (у коммерции свой блок)
const showBuildingDetailsSection = computed(() => propertyTypeSchema.value.showBuildingDetails)
// Комнаты: только квартира, дом, комната
const showRoomsField = computed(() => propertyTypeSchema.value.showRooms)
// Этаж (номер): только квартира и комната
const showFloorField = computed(() => propertyTypeSchema.value.showFloor)
// Площадь участка: дом и земля
const showLandAreaField = computed(() => propertyTypeSchema.value.showLandArea)
// Балкон: только квартира и дом
const showBalconyField = computed(() => propertyTypeSchema.value.showBalcony)
// Жилая площадь + кухня + высота потолков: квартира, дом, комната
const showResidentialAreaFields = computed(() => propertyTypeSchema.value.showResidentialArea)
// Санузел: квартира, дом, комната
const showBathroomFields = computed(() => propertyTypeSchema.value.showBathroom)
// Ремонт: квартира, дом, комната, гараж
const showRenovationField = computed(() => propertyTypeSchema.value.showRenovation)
// Спальни: квартира, дом, комната
const showBedroomField = computed(() => propertyTypeSchema.value.showBedrooms)
// Блок "О помещении" (жилое): не для коммерции, не для земли, не для гаража (гараж видит только ремонт)
const showResidentialDetailsSection = computed(() => propertyTypeSchema.value.showResidentialDetails)
// Гараж отображает только тип ремонта в разделе "О помещении"
const showGarageRenovationOnly = computed(() => propertyTypeSchema.value.showGarageRenovationOnly)
const currentStepMeta = computed(() => steps.find((step) => step.id === currentStep.value) || steps[0])
const propertyOwners = computed(() => propertyData.value?.owners || [])
const propertyDirtySnapshot = computed(() => JSON.stringify(buildPropertyDirtyState()))

// Coordinates: prefer freshly picked from DaData, fall back to saved on existing object
const isPropertyDirty = computed(() => propertyDirtySnapshot.value !== propertyBaseline.value)
const currentStepErrors = computed(() => touchedSteps[currentStep.value] ? getStepErrors(currentStep.value) : [])
const fieldErrors = computed(() => getFieldErrorsForStep(currentStep.value))
const fieldWarnings = computed(() => getFieldWarningsForStep(currentStep.value))
const isCurrentStepValid = computed(() => validateStep(currentStep.value, false))

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

function hasAddressValue() {
  return !!(addressPicked.value?.value || form.address || existingAddress.value)
}

function normalizeTextValue(value) {
  return (value || '').toString().trim()
}

function hasConfirmedAddressSelection() {
  // In edit mode: if user hasn't changed the address query, consider it confirmed
  if (isEdit.value && !addressPicked.value) {
    const queryTrimmed = normalizeTextValue(addressQuery.value)
    const existingTrimmed = normalizeTextValue(existingAddress.value)
    const confirmedTrimmed = normalizeTextValue(addressConfirmedValue.value)
    // Address is valid if query matches the confirmed/existing value or user hasn't typed anything new
    if (confirmedTrimmed && queryTrimmed === confirmedTrimmed) return true
    if (existingTrimmed && queryTrimmed === existingTrimmed) return true
    if (!queryTrimmed && existingTrimmed) return true
  }
  const confirmedValue = normalizeTextValue(addressConfirmedValue.value)
  if (!confirmedValue) return false
  const currentValue = normalizeTextValue(addressQuery.value || form.address || existingAddress.value)
  return currentValue === confirmedValue
}

function getFieldErrorsForStep(stepId) {
  const errors = {}
  if (stepId === 1) {
    if (!form.operation_type) errors.operation_type = 'Выберите тип операции.'
    if (!form.premises_type) errors.premises_type = 'Выберите тип объекта.'
  }
  if (stepId === 2 && !hasConfirmedAddressSelection()) {
    errors.address = 'Выберите адрес из подсказок DaData.'
  }
  if (stepId === 3) {
    if (!form.title?.trim()) errors.title = 'Заполните заголовок объекта.'
    if (form.price === null || form.price === undefined || form.price === '') {
      errors.price = 'Укажите цену объекта.'
    } else if (Number(form.price) < 0) {
      errors.price = 'Цена не может быть отрицательной.'
    }
    if (form.area_total !== null && form.area_total !== undefined && form.area_total !== '' && Number(form.area_total) <= 0) {
      errors.area_total = 'Площадь должна быть больше нуля.'
    }
    // Only validate building details fields when the section is visible
    if (showBuildingDetailsSection.value && form.building_details.year_built) {
      const yr = Number(form.building_details.year_built)
      if (yr < 1800 || yr > currentYear) {
        errors.year_built = `Год постройки должен быть от 1800 до ${currentYear}.`
      }
    }
    // Only validate floor field when it is shown (apartment / room only)
    if (showFloorField.value && form.floor_number !== null && form.floor_number !== undefined && form.floor_number !== '') {
      if (Number(form.floor_number) < -10 || Number(form.floor_number) > 500) {
        errors.floor_number = 'Этаж должен быть в диапазоне от −10 до 500.'
      }
    }
    // Validate total_floors only when building section is visible
    if (showBuildingDetailsSection.value && form.building_details.total_floors !== null && form.building_details.total_floors !== undefined && form.building_details.total_floors !== '') {
      if (Number(form.building_details.total_floors) < 1) {
        errors.total_floors = 'Количество этажей должно быть не менее 1.'
      }
    }
  }
  return errors
}

function getFieldWarningsForStep(stepId) {
  const warnings = {}
  if (stepId === 4 && !photos.value.length) {
    warnings.photos = 'Фото не обязательны, но без них карточка будет менее информативной.'
  }
  return warnings
}

function getStepErrors(stepId) {
  const fieldMap = getFieldErrorsForStep(stepId)
  return Object.values(fieldMap)
}

function validateStep(stepId, touch = false) {
  if (touch) touchedSteps[stepId] = true
  return getStepErrors(stepId).length === 0
}

function isStepComplete(stepId) {
  return validateStep(stepId, false)
}

function isStepAccessible(stepId) {
  if (stepId <= currentStep.value) return true
  for (let index = 1; index < stepId; index += 1) {
    if (!validateStep(index, false)) return false
  }
  return true
}

function openStep(stepId) {
  if (!isStepAccessible(stepId)) return
  currentStep.value = stepId
}

function goPrev() {
  if (currentStep.value > 1) currentStep.value -= 1
}

async function focusFirstInvalidField(stepId) {
  await nextTick()
  const errorMap = getFieldErrorsForStep(stepId)
  if (errorMap.operation_type) {
    operationTypeFieldRef.value?.focus?.()
    return
  }
  if (errorMap.premises_type) {
    premisesTypeFieldRef.value?.focus?.()
    return
  }
  if (errorMap.address) {
    const addressInput = addressFieldRef.value?.$el?.querySelector?.('input') || addressFieldRef.value?.querySelector?.('input')
    addressInput?.focus?.()
    return
  }
  if (errorMap.title) {
    titleFieldRef.value?.focus?.()
    return
  }
  if (errorMap.price) {
    priceFieldRef.value?.focus?.()
  }
}

async function goNext() {
  if (!validateStep(currentStep.value, true)) {
    await focusFirstInvalidField(currentStep.value)
    return
  }
  currentStep.value = Math.min(currentStep.value + 1, steps.length)
}

async function handleSubmit() {
  for (const step of steps) {
    if (!validateStep(step.id, true)) {
      currentStep.value = step.id
      await focusFirstInvalidField(step.id)
      return
    }
  }
  await submit()
}

function onAddressPick(result) {
  addressPicked.value = result
  form.address = result?.value || null
  addressConfirmedValue.value = result?.value || ''
}

function formatCoordinate(value) {
  const numberValue = Number(value)
  return Number.isFinite(numberValue) ? numberValue.toFixed(4) : value
}

function mapClientProfileOption(profile) {
  return {
    id: profile.id,
    label: [profile.last_name, profile.first_name, profile.middle_name].filter(Boolean).join(' ') || profile.user?.email || `Клиент #${profile.id}`,
    hint: profile.user?.email || '',
  }
}

function mapEmployeeProfileOption(profile) {
  return {
    id: profile.id,
    label: [profile.last_name, profile.first_name, profile.middle_name].filter(Boolean).join(' ') || profile.user?.email || `Сотрудник #${profile.id}`,
    hint: profile.user?.email || '',
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

function onFilesSelected(event) {
  const files = Array.from(event.target.files || [])
  for (const file of files) {
    const preview = URL.createObjectURL(file)
    const photo = { file, preview, is_cover: false, _new: true }
    photos.value.push(photo)
    pendingFiles.value.push(photo)
  }
  event.target.value = ''
}

function addPhotoByUrl() {
  const url = newPhotoUrl.value.trim()
  if (!url) return
  photos.value.push({ url, image_url: url, is_cover: false, _new: true, _fromUrl: true })
  newPhotoUrl.value = ''
}

function setCover(target) {
  photos.value.forEach((photo) => {
    photo.is_cover = photo === target
  })
}

function revokePreview(photo) {
  if (photo?.preview?.startsWith('blob:')) {
    URL.revokeObjectURL(photo.preview)
  }
}

function removePhoto(photo, index) {
  if (photo.id) removedPhotoIds.value.push(photo.id)
  pendingFiles.value = pendingFiles.value.filter((item) => item !== photo)
  revokePreview(photo)
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
    operation_type: 'Тип операц��и',
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
  addressConfirmedValue.value = draft?.addressPicked?.value || ''
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

function resetPropertyFormState() {
  Object.assign(form, defaultForm())
  addressQuery.value = ''
  addressPicked.value = null
  addressConfirmedValue.value = ''
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
  errorDetails.message = ''
  errorDetails.step = null
  errorDetails.fields = []
  propertyDraftRestored.value = false
  currentStep.value = 1
  for (const key of Object.keys(touchedSteps)) {
    touchedSteps[key] = false
  }
}

async function ensureOperationTypesLoaded() {
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

// Remove all *_data keys (nested objects returned by the API) from a form object
// so they don't accidentally get sent to the backend as non-PK values.
function stripDataKeys(obj) {
  if (!obj || typeof obj !== 'object') return {}
  return Object.fromEntries(Object.entries(obj).filter(([key]) => !key.endsWith('_data')))
}

function resetPropertyTypeSpecificFields(type) {
  const schema = getPropertyTypeSchema(type)

  if (!schema.showRooms) {
    form.rooms_count = null
  }
  if (!schema.showFloor) {
    form.floor_number = null
  }
  if (!schema.showBuildingDetails) {
    form.building_details.year_built = null
    form.building_details.total_floors = null
    form.building_details.building_material = null
    form.building_details.elevators_count = null
  }
  if (!schema.showResidentialArea) {
    form.property_details.living_area = null
    form.property_details.kitchen_area = null
    form.property_details.ceiling_height = null
  }
  if (!schema.showBalcony) {
    form.property_details.balcony_count = null
  }
  if (!schema.showBathroom) {
    form.property_details.bathroom_count = null
    form.property_details.bathroom_type = null
  }
  if (!schema.showRenovation) {
    form.property_details.renovation_type = null
  }
  if (!schema.showBedrooms) {
    form.property_details.bedrooms_count = null
  }
  if (!schema.showPrivateHouseFloors) {
    form.property_details.floors_count = null
  }
  if (!schema.showLandArea) {
    form.property_details.land_area = null
  }
  if (!schema.showCommercialDetails) {
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
}

function buildPropertyPayload() {
  const schema = getPropertyTypeSchema(form.premises_type)

  return {
    title: form.title,
    operation_type: form.operation_type,
    status: form.status,
    premises_type: form.premises_type,
    price: form.price,
    area_total: form.area_total,
    rooms_count: schema.showRooms ? form.rooms_count : null,
    floor_number: schema.showFloor ? form.floor_number : null,
    cadastral_number: form.cadastral_number || null,
    is_published: !!form.is_published,
    description: form.description,
    building_details_data: schema.showBuildingDetails ? stripDataKeys({
      year_built: form.building_details.year_built || null,
      total_floors: form.building_details.total_floors || null,
      building_material: form.building_details.building_material || null,
      elevators_count: form.building_details.elevators_count ?? 0,
    }) : null,
    property_details_data: schema.showCommercialDetails
      ? null
      : schema.showGarageRenovationOnly
        ? stripDataKeys({
          renovation_type: form.property_details.renovation_type || null,
        })
        : stripDataKeys({
          living_area: schema.showResidentialArea ? (form.property_details.living_area || null) : null,
          kitchen_area: schema.showResidentialArea ? (form.property_details.kitchen_area || null) : null,
          ceiling_height: schema.showResidentialArea ? (form.property_details.ceiling_height || null) : null,
          balcony_count: schema.showBalcony ? (form.property_details.balcony_count ?? 0) : null,
          bathroom_count: schema.showBathroom ? (form.property_details.bathroom_count ?? 1) : null,
          bathroom_type: schema.showBathroom ? (form.property_details.bathroom_type || null) : null,
          renovation_type: schema.showRenovation ? (form.property_details.renovation_type || null) : null,
          bedrooms_count: schema.showBedrooms ? (form.property_details.bedrooms_count ?? null) : null,
          floors_count: schema.showPrivateHouseFloors ? (form.property_details.floors_count ?? 1) : null,
          land_area: schema.showLandArea ? (form.property_details.land_area || null) : null,
        }),
    commercial_property_details_data: schema.showCommercialDetails ? stripDataKeys({
      commercial_type: form.commercial_property_details.commercial_type || null,
      usable_area: form.commercial_property_details.usable_area || null,
      ceiling_height: form.commercial_property_details.ceiling_height || null,
      floor_load: form.commercial_property_details.floor_load ?? null,
      electric_power_kw: form.commercial_property_details.electric_power_kw ?? null,
      parking_spaces: form.commercial_property_details.parking_spaces ?? null,
      has_separate_entrance: !!form.commercial_property_details.has_separate_entrance,
      has_display_windows: !!form.commercial_property_details.has_display_windows,
      is_first_line: !!form.commercial_property_details.is_first_line,
    }) : null,
    amenity_ids: [...form.amenity_ids],
  }
}

async function initializeForm() {
  const seq = ++initSeq
  loading.value = true
  isInitializingForm = true
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

    viewingForm.status = dict.viewingStatuses[0]?.id || null

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
          ...stripDataKeys(data.building_details || {}),
          building_material: data.building_details?.building_material
            ?? data.building_details?.building_material_data?.id
            ?? null,
        },
        property_details: {
          ...createPropertyDetailsForm(),
          ...stripDataKeys(data.property_details || {}),
          bathroom_type: data.property_details?.bathroom_type
            ?? data.property_details?.bathroom_type_data?.id
            ?? null,
          renovation_type: data.property_details?.renovation_type
            ?? data.property_details?.renovation_type_data?.id
            ?? null,
        },
        commercial_property_details: {
          ...createCommercialPropertyDetailsForm(),
          ...stripDataKeys(data.commercial_property_details || {}),
          commercial_type: data.commercial_property_details?.commercial_type
            ?? data.commercial_property_details?.commercial_type_data?.id
            ?? null,
        },
        amenity_ids: (data.amenities || []).map((item) => item.amenity),
      })
      existingAddress.value = data.full_address || ''
      addressQuery.value = data.full_address || data.address || ''
      addressConfirmedValue.value = data.full_address || data.address || ''
      photos.value = (data.photos || []).map((photo) => ({ ...photo }))
      documents.value = unpackPaginated(data.documents).items
      priceHistory.value = unpackPaginated(data.price_history).items
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
      syncPropertyBaseline()
      // Restore any unsaved edits from sessionStorage (e.g. after accidental refresh)
      restorePropertyEditDraft()
    } else {
      form.status = dict.statuses[0]?.id || null
      syncPropertyBaseline()
      // Restore create-mode draft AFTER form defaults are ready so it is not wiped
      restorePropertyCreateDraft()
    }
  } catch (e) {
    if (seq !== initSeq) return
    error.value = extractError(e, 'Не удалось инициализировать форму объекта.')
  } finally {
    if (seq === initSeq) {
      loading.value = false
      // Снимаем флаг инициализации в следующем тике, чтобы watcher premises_type
      // не затёр только что загруженные данные
      nextTick(() => { isInitializingForm = false })
    }
  }
}

const { clearDraft: clearPropertyDraft, restoreDraft: restorePropertyCreateDraft } = useDraftPersistence({
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

const { clearDraft: clearPropertyEditDraft, restoreDraft: restorePropertyEditDraft } = useDraftPersistence({
  key: () => isEdit.value ? `property-form:edit:${route.params.id}` : null,
  enabled: () => isEdit.value,
  getData: buildPropertyDraftData,
  applyData: (draft) => {
    propertyDraftRestored.value = true
    applyPropertyDraft(draft)
    toasts.info('Несохранённые изменения восстановлены')
  },
  isEmpty: isPropertyDraftEmpty,
})

useUnsavedChangesGuard({
  enabled: () => isPropertyDirty.value,
  isDirty: () => isPropertyDirty.value,
  message: 'Есть несохра��ённые изменения в карточке объекта. Покинуть страницу?',
})

async function uploadPhotos(propertyId) {
  for (const photo of pendingFiles.value) {
    const formData = new FormData()
    formData.append('property', propertyId)
    formData.append('image', photo.file)
    formData.append('is_cover', photo.is_cover ? 'true' : 'false')
    await api.post('/property-photos/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  }
  pendingFiles.value = []

  for (const photo of photos.value.filter((item) => item._new && item._fromUrl)) {
    await api.post('/property-photos/', {
      property: propertyId,
      url: photo.url,
      is_cover: photo.is_cover,
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

// Map server error field names to step numbers for navigation
const FIELD_STEP_MAP = {
  operation_type: 1, premises_type: 1,
  address: 2, address_data: 2,
  title: 3, price: 3, area_total: 3, rooms_count: 3, floor_number: 3,
  cadastral_number: 3, status: 3,
  building_details_data: 3, property_details_data: 3, commercial_property_details_data: 3,
  description: 5, documents: 5,
}

// Reactive error details for structured display
const errorDetails = reactive({ message: '', step: null, fields: [] })

// Russian labels for all backend field names (top-level and nested)
const FIELD_LABELS = {
  // Top-level
  title: 'Название', operation_type: 'Тип операции', status: 'Статус',
  premises_type: 'Тип помещения', price: 'Цена', area_total: 'Общая площадь',
  rooms_count: 'Количество комнат', floor_number: 'Этаж', address: 'Адрес',
  cadastral_number: 'Кадастровый номер', is_published: 'Публикация',
  description: 'Описание', amenity_ids: 'Удобства',
  building_details_data: 'Параметры здания',
  property_details_data: 'Параметры помещения',
  commercial_property_details_data: 'Коммерческие параметры',
  // building_details sub-fields
  year_built: 'Год постройки', total_floors: 'Этажей в здании',
  building_material: 'Мат��риал стен', elevators_count: 'Количество лифтов',
  // property_details sub-fields
  living_area: 'Жилая площадь', kitchen_area: 'Площадь кухни',
  ceiling_height: 'Высота потолков', balcony_count: 'Количество балконов',
  bathroom_count: 'Количество санузлов', bathroom_type: 'Тип санузла',
  renovation_type: 'Тип ремонта', bedrooms_count: 'Спальни',
  floors_count: 'Этажей в помещении', land_area: 'Площадь участка',
  // commercial sub-fields
  commercial_type: 'Тип коммерции', usable_area: 'Полезная площадь',
  floor_load: 'Нагрузка на пол', electric_power_kw: 'Электрическая мощность',
  parking_spaces: 'Парковочные места', has_separate_entrance: 'Отдельный вход',
  has_display_windows: 'Витринные окна', is_first_line: 'Первая линия',
}

function parseServerErrors(data) {
  if (!data || typeof data !== 'object') return { message: '', step: null, fields: [] }
  const fields = []
  let firstStep = null
  for (const [key, value] of Object.entries(data)) {
    // Flatten nested errors (e.g. building_details_data: {elevators_count: [...]})
    if (typeof value === 'object' && !Array.isArray(value) && value !== null) {
      for (const [subKey, subVal] of Object.entries(value)) {
        const msg = Array.isArray(subVal) ? subVal.filter(Boolean).join(' ') : String(subVal || '')
        const parentLabel = FIELD_LABELS[key] || key
        const subLabel = FIELD_LABELS[subKey] || subKey
        if (msg) fields.push({ label: `${parentLabel} / ${subLabel}`, message: msg })
      }
    } else {
      const msg = Array.isArray(value) ? value.filter(Boolean).join(' ') : String(value || '')
      if (msg) fields.push({ label: FIELD_LABELS[key] || key, message: msg })
    }
    const step = FIELD_STEP_MAP[key]
    if (step && (!firstStep || step < firstStep)) firstStep = step
  }
  const message = fields.map((f) => `${f.label}: ${f.message}`).join(' · ')
  return { message, step: firstStep, fields }
}

function isHtmlErrorResponse(data) {
  if (typeof data !== 'string') return false
  const normalized = data.trim().toLowerCase()
  return normalized.startsWith('<!doctype html') || normalized.startsWith('<html')
}

async function submit() {
  loading.value = true
  error.value = ''
  errorDetails.message = ''
  errorDetails.step = null
  errorDetails.fields = []
  try {
    const payload = buildPropertyPayload()
    if (addressPicked.value) {
      // User selected a new address from DaData suggestions
      payload.address_data = addressPicked.value
    } else if (isEdit.value && form.address && typeof form.address === 'number') {
      // Editing: keep existing address by its numeric PK — don't re-send address_data
      payload.address = form.address
    } else if (isEdit.value) {
      // Editing without touching the address field — omit address entirely,
      // backend will keep the existing one
    } else {
      throw new Error('Выбе��ите адрес из подсказок.')
    }

    const url = isEdit.value ? `/properties/${route.params.id}/` : '/properties/'
    const method = isEdit.value ? 'put' : 'post'
    const { data } = await api[method](url, payload)

    await uploadPhotos(data.id)
    clearPropertyDraft()
    clearPropertyEditDraft()
    syncPropertyBaseline()
    router.push(`/properties/${data.id}`)
  } catch (e) {
    const data = e.response?.data
    if (isHtmlErrorResponse(data)) {
      error.value = 'Не удалось сохранить объект. Сервер вернул внутреннюю ошибку.'
      errorDetails.message = error.value
      errorDetails.step = currentStep.value
      errorDetails.fields = []
      return
    }
    if (typeof data === 'object' && data) {
      const parsed = parseServerErrors(data)
      errorDetails.message = parsed.message
      errorDetails.step = parsed.step
      errorDetails.fields = parsed.fields
      error.value = parsed.message || extractError(e, 'Не удалось сохранить объект.')
      // Auto-navigate to the step that has errors
      if (parsed.step && parsed.step !== currentStep.value) {
        currentStep.value = parsed.step
      }
    } else {
      error.value = extractError(e, 'Не удалось сохранить объект. Попробуйте ещё раз.')
      errorDetails.message = error.value
    }
  } finally {
    loading.value = false
  }
}

watch(() => `${route.name || ''}:${route.params.id || 'new'}`, () => {
  void initializeForm()
}, { immediate: true })

watch(addressQuery, (value) => {
  const normalizedValue = normalizeTextValue(value)
  const pickedValue = normalizeTextValue(addressPicked.value?.value)
  if (addressPicked.value && normalizedValue !== pickedValue) {
    addressPicked.value = null
  }
  form.address = normalizedValue || null
})

watch(() => form.premises_type, (value) => {
  if (isInitializingForm) return
  const type = normalizePropertyType(value)
  if (!type) return
  resetPropertyTypeSpecificFields(type)
})

onBeforeUnmount(() => {
  photos.value.forEach(revokePreview)
})
</script>

<style scoped>
.property-form-page {
  min-height: 0;
  position: relative;
  z-index: 1;
}

.property-form__hero {
  padding: 24px 28px 32px;
  gap: 20px;
  height: auto;
  min-height: auto;
  max-height: none;
  flex: 0 0 auto;
  overflow: visible;
  contain: none;
}

.property-form__hero-top {
  flex-wrap: wrap;
  gap: 12px;
}

.property-form__hero-copy {
  gap: 8px;
}

.property-form__hero-title {
  margin: 0;
  color: #fff;
}

.property-form__hero-text {
  max-width: 720px;
  color: var(--c-ink-soft);
  font-size: 14px;
  line-height: 1.5;
}

.property-form__stepper {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 14px;
}

.property-form__step {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px;
  border-radius: var(--r-md);
  border: 1px solid rgba(120, 216, 206, 0.16);
  background: rgba(255, 255, 255, 0.05);
  color: var(--c-text);
  text-align: left;
  cursor: pointer;
  transition: transform 0.2s ease, border-color 0.2s ease, background 0.2s ease;
}

.property-form__step:hover:not(:disabled) {
  transform: translateY(-2px);
  border-color: rgba(120, 216, 206, 0.3);
}

.property-form__step:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.property-form__step.is-active {
  border-color: rgba(120, 216, 206, 0.42);
  background: rgba(120, 216, 206, 0.12);
  box-shadow: var(--shadow-glow);
}

.property-form__step.is-complete .property-form__step-index {
  background: var(--grad-accent);
  color: #04221f;
}

.property-form__step-index {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  flex: 0 0 32px;
  border-radius: 999px;
  border: 1px solid rgba(120, 216, 206, 0.26);
  background: rgba(255, 255, 255, 0.08);
  font-size: 13px;
  font-weight: 700;
}

.property-form__step-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.property-form__step-title {
  font-size: 14px;
  font-weight: 700;
}

.property-form__step-caption {
  font-size: 12px;
  color: var(--c-ink-soft);
  line-height: 1.4;
}

.property-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 22px;
  overflow: visible;
}

.property-form__surface-head {
  padding-bottom: 6px;
  border-bottom: 1px solid var(--c-border);
}

.property-form__step-panel {
  gap: 16px;
}

.property-form__subpanel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 18px;
  border: 1px solid var(--c-border);
  overflow: hidden;
}

.property-form__grid {
  gap: 16px;
}

.property-form__grid > .field > .input,
.property-form__grid > .field > .select,
.property-form__grid > .field > .textarea {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(230, 238, 242, 0.95)) !important;
  color: var(--c-page-text) !important;
  border-color: rgba(21, 56, 57, 0.16) !important;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.84),
    0 10px 22px rgba(16, 55, 52, 0.08);
}

.property-form__grid > .field > .select {
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
}

.property-form__text {
  margin: 0;
}

.property-form__required {
  color: var(--c-danger);
}

/* ── Structured server error block ─────────────────────── */
.property-form__error-block {
  border: 1px solid rgba(194, 85, 74, 0.45);
  background: rgba(194, 85, 74, 0.10);
  border-radius: 16px;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.property-form__error-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  font-size: 14px;
  color: var(--c-danger-2, #e87b72);
}

.property-form__error-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
  color: var(--c-ink-soft);
}

.property-form__error-list b {
  color: var(--c-danger-2, #e87b72);
  font-weight: 600;
}

.property-form__error-text {
  font-size: 13px;
  color: var(--c-ink-soft);
  margin: 0;
}

.property-form__error-goto {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  align-self: flex-start;
  padding: 7px 14px;
  border-radius: 999px;
  border: 1px solid rgba(194, 85, 74, 0.35);
  background: rgba(194, 85, 74, 0.12);
  color: var(--c-danger-2, #e87b72);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease;
}

.property-form__error-goto:hover {
  background: rgba(194, 85, 74, 0.20);
  border-color: rgba(194, 85, 74, 0.55);
}

.property-form__field-error {
  margin-top: 6px;
  color: #ffd4d4;
  font-size: 12px;
  line-height: 1.45;
}

.property-form__tags {
  gap: 12px;
  flex-wrap: wrap;
  max-width: 100%;
  width: 100%;
  align-items: flex-start;
}

.property-form__tags .tag {
  max-width: 100%;
  overflow-wrap: anywhere;
}

.property-form__address-empty {
  min-height: 120px;
}

.property-form__chip-inline {
  width: fit-content;
}

.property-form__chip-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.property-form__photo-grid {
  gap: 16px;
}

.photo-tile {
  position: relative;
  aspect-ratio: 4 / 3;
  overflow: hidden;
  border-radius: 22px;
  border: 1px solid var(--c-border);
  background: rgba(255, 255, 255, 0.06);
  box-shadow: var(--shadow-1);
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
  gap: 8px;
  flex-wrap: wrap;
  padding: 10px;
  background: linear-gradient(to top, rgba(7, 19, 29, 0.86), transparent);
}

.property-form__photo-cover {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.property-form__photo-cover input {
  accent-color: var(--c-accent);
}

.property-form__photos-empty {
  min-height: 160px;
}

.property-form__photo-actions {
  gap: 12px;
  flex-wrap: wrap;
  align-items: stretch;
}

.property-form__upload-btn {
  position: relative;
  cursor: pointer;
}

.property-form__upload-btn input {
  display: none;
}

.property-form__photo-url {
  flex: 1 1 320px;
  gap: 8px;
}

.property-form__stack-sm {
  gap: 10px;
}

.property-form__list-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  border-radius: var(--r-md);
  border: 1px solid var(--c-border);
  background: rgba(255, 255, 255, 0.04);
}

.property-form__doc-actions,
.property-form__section-actions,
.property-form__footer-actions,
.property-form__modal-actions {
  gap: 10px;
  flex-wrap: wrap;
}

.property-form__footer {
  padding-top: 8px;
  padding-bottom: 8px;
  border-top: 1px solid var(--c-border);
  position: relative;
  z-index: 10;
  margin-top: 20px;
}

.property-form__step-errors {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.property-form__step-error {
  padding: 12px 14px;
  border-radius: var(--r-sm);
  border: 1px solid rgba(194, 85, 74, 0.35);
  background: rgba(194, 85, 74, 0.10);
  color: var(--c-danger-2, #e87b72);
  font-size: 14px;
}

.property-form__modal {
  width: min(760px, calc(100vw - 32px));
}

.property-form__modal-grid {
  gap: 14px;
  margin-top: 18px;
}

.property-form__modal-field-full {
  grid-column: 1 / -1;
}

@media (max-width: 1080px) {
  .property-form__stepper {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .property-form {
    padding: 18px;
  }

  .property-form__stepper {
    grid-template-columns: 1fr;
  }

  .property-form__photo-actions,
  .property-form__photo-url,
  .property-form__list-row,
  .property-form__footer,
  .property-form__modal-actions {
    flex-direction: column;
    align-items: stretch;
  }
}

/* ── Coordinates auto-filled from DaData ─────────────────── */
.property-form__coords-row {
  margin-top: 4px;
}

.property-form__coords-label {
  display: flex;
  align-items: center;
  gap: 8px;
}

.property-form__coords-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(120, 216, 206, 0.12);
  border: 1px solid rgba(120, 216, 206, 0.25);
  color: var(--c-accent, #78d8ce);
  font-weight: 600;
  letter-spacing: 0.02em;
}

.property-form__coords-input {
  opacity: 0.72;
  cursor: default;
  pointer-events: none;
}
</style>
