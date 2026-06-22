<template>
  <section class="stack" v-if="property">

    <!-- ── Hero ─────────────────────────────────────────────── -->
    <div class="hero" style="padding: 24px 28px">
      <div class="row row--between" style="flex-wrap: wrap; gap: 12px">
        <div>
          <div class="hero__eyebrow">{{ property.operation_type_name }}</div>
          <h1 class="h2" style="color: #fff; margin-top: 8px">
            {{ property.title || 'Объект №' + property.id }}
          </h1>
          <div style="color: rgba(255,255,255,.75); font-size: 14px; margin-top: 4px">
            {{ property.full_address }}
          </div>
        </div>
        <div class="row" style="gap: 8px; flex-wrap: wrap">
          <button v-if="canLeaveRequest"
                  class="btn btn--accent"
                  @click="showRequestForm = true">
            Оставить заявку
          </button>
          <router-link v-if="auth.isAdminOrManager"
                       :to="`/properties/${property.id}/edit`" class="btn btn--sm">
            Редактировать
          </router-link>
          <button v-if="auth.isAdminOrManager" class="btn btn--danger btn--sm"
                  @click="remove">Удалить</button>
        </div>
      </div>
    </div>

    <!-- ── KPI-полоса ─────────────────────────────────────────── -->
    <div class="pd-kpi-strip">
      <article class="pd-kpi-card">
        <span class="pd-kpi-card__label">Стоимость</span>
        <strong class="pd-kpi-card__value pd-kpi-card__value--price">{{ priceLabel }}</strong>
        <span class="pd-kpi-card__meta">
          {{ property.price_per_sqm ? formatMoney(property.price_per_sqm) + ' ₽/м²' : 'цена за м² не указана' }}
        </span>
      </article>
      <article class="pd-kpi-card">
        <span class="pd-kpi-card__label">Площадь</span>
        <strong class="pd-kpi-card__value">{{ property.area_total ? property.area_total + ' м²' : '—' }}</strong>
        <span class="pd-kpi-card__meta">общая площадь</span>
      </article>
      <article v-if="showRoomsInfo" class="pd-kpi-card">
        <span class="pd-kpi-card__label">Комнат</span>
        <strong class="pd-kpi-card__value">{{ formatRoomsValue(property.premises_type, property.rooms_count) }}</strong>
        <span class="pd-kpi-card__meta">{{ premisesTypeLabel(property.premises_type) }}</span>
      </article>
      <article v-if="showFloorInfo || showBuildingFacts" class="pd-kpi-card">
        <span class="pd-kpi-card__label">Этаж</span>
        <strong class="pd-kpi-card__value">{{ property.floor_number || '—' }}</strong>
        <span class="pd-kpi-card__meta">из {{ property.total_floors || property.building_details?.total_floors || '—' }}</span>
      </article>
      <article class="pd-kpi-card">
        <span class="pd-kpi-card__label">Статус</span>
        <strong class="pd-kpi-card__value">{{ property.status_name || '—' }}</strong>
        <span class="pd-kpi-card__meta">{{ property.is_published ? 'Опубликован' : 'Не опубликован' }}</span>
      </article>
    </div>

    <!-- ── Модал заявки ──────────────────────────────────────── -->
    <div v-if="showRequestForm" class="modal" role="dialog"
         @click.self="showRequestForm = false">
      <form class="panel panel--light stack modal__card"
            @submit.prevent="submitRequest">
        <div class="row row--between">
          <h2 class="h3">Заявка на объект</h2>
          <button type="button" class="btn btn--sm btn--ghost"
                  style="color: #000"
                  @click="showRequestForm = false">×</button>
        </div>
        <div class="muted">
          Объект: <b>{{ property.title || 'Объект №' + property.id }}</b>.
          Агент свяжется с вами после получения заявки.
        </div>
        <div class="field">
          <label>Пожелания / комментарий</label>
          <textarea class="textarea" v-model="requestForm.description" rows="4"
                    placeholder="Удобное время для связи, условия осмотра и т. д.">
          </textarea>
        </div>
        <div v-if="requestError" class="error">{{ requestError }}</div>
        <div class="row" style="justify-content: flex-end; gap: 8px">
          <button type="button" class="btn btn--sm"
                  @click="showRequestForm = false">Отмена</button>
          <button type="submit" class="btn btn--accent">Отправить заявку</button>
        </div>
      </form>
    </div>

    <!-- ── Модал истории цен ──────────────────────────────────── -->
    <Teleport to="body">
      <Transition name="ph">
        <div v-if="showPriceHistory" class="ph-backdrop" role="dialog"
             @click.self="showPriceHistory = false">
          <div class="ph-modal">
            <div class="ph-modal__header">
              <div>
                <div class="ph-modal__eyebrow">История изменений</div>
                <h2 class="ph-modal__title">Динамика цены</h2>
              </div>
              <button class="lb-close" @click="showPriceHistory = false" title="Закрыть">✕</button>
            </div>
            <div class="ph-modal__body">
              <div v-if="priceHistory.length" class="ph-timeline">
                <div v-for="(item, idx) in priceHistory" :key="item.id" class="ph-item">
                  <div class="ph-item__dot"
                       :class="item.old_price && item.new_price > item.old_price ? 'ph-item__dot--up'
                               : item.old_price && item.new_price < item.old_price ? 'ph-item__dot--down'
                               : ''">
                  </div>
                  <div class="ph-item__line" v-if="idx < priceHistory.length - 1"></div>
                  <div class="ph-item__content">
                    <div class="ph-item__date">{{ formatDate(item.changed_at) }}</div>
                    <div class="ph-item__prices">
                      <span v-if="item.old_price" class="ph-item__old">
                        {{ formatMoney(item.old_price) }} ₽
                      </span>
                      <svg v-if="item.old_price" width="14" height="14" viewBox="0 0 24 24" fill="none"
                           stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"
                           class="ph-item__arrow"
                           :class="item.new_price > item.old_price ? 'ph-item__arrow--up' : 'ph-item__arrow--down'">
                        <line x1="5" y1="12" x2="19" y2="12"/>
                        <polyline points="12 5 19 12 12 19"/>
                      </svg>
                      <span class="ph-item__new">{{ formatMoney(item.new_price) }} ₽</span>
                      <span v-if="item.old_price" class="ph-item__delta"
                            :class="item.new_price > item.old_price ? 'ph-item__delta--up' : 'ph-item__delta--down'">
                        {{ item.new_price > item.old_price ? '+' : '' }}{{ formatMoney(item.new_price - item.old_price) }} ₽
                      </span>
                    </div>
                    <div v-if="item.changed_by_username" class="ph-item__by">
                      {{ item.changed_by_username }}
                    </div>
                  </div>
                </div>
              </div>
              <div v-else class="muted" style="padding: 24px 0">
                История изменений цены отсутствует.
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- ── Фотографии ─────────────────────────────────────────── -->
    <div class="panel panel--light">
      <div class="surface-head property-surface-head">
        <div>
          <div class="surface-head__meta">Медиа</div>
          <h2 class="h3">Фотографии</h2>
        </div>
        <label v-if="auth.isAdminOrManager" class="btn btn--sm">
          Загрузить фото
          <input type="file" accept="image/*" multiple @change="uploadPhotos" hidden />
        </label>
      </div>
      <div v-if="property.photos?.length" class="gallery">
        <div v-for="(ph, idx) in property.photos" :key="ph.id"
             class="gallery__item"
             :class="{ 'is-hidden': ph.is_hidden, 'is-cover': ph.is_cover }">
          <img :src="ph.image_url" :alt="property.title || 'Фото объекта'"
               class="gallery__img"
               @click="openLightbox(idx)" />
          <div class="gallery__badges">
            <span v-if="ph.is_cover" class="gallery__badge is-cover">Обложка</span>
            <span v-if="ph.is_hidden" class="gallery__badge is-hidden">Скрыто</span>
          </div>
          <div v-if="auth.isAdminOrManager" class="gallery__toolbar">
            <button class="gallery__btn"
                    :class="{ 'gallery__btn--active': ph.is_cover }"
                    :disabled="ph.is_cover"
                    :title="ph.is_cover ? 'Это текущая обложка' : 'Сделать обложкой'"
                    @click.stop="setCover(ph)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2l2.9 6.26 6.77.54-5.19 4.4 1.71 6.63L12 16.5l-6.19 3.33 1.71-6.63L2.33 8.8l6.77-.54z"/>
              </svg>
            </button>
            <button class="gallery__btn"
                    :disabled="ph.is_cover"
                    :title="ph.is_hidden ? 'Показать клиенту' : 'Скрыть от клиента'"
                    @click.stop="toggleHidden(ph)">
              <svg v-if="!ph.is_hidden" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
              </svg>
              <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>
              </svg>
            </button>
            <button class="gallery__btn gallery__btn--danger"
                    title="Удалить фото"
                    @click.stop="removePhoto(ph)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
      <div v-if="!property.photos?.length" class="muted" style="margin-top: 8px">
        Фотографии ещё не загружены.
      </div>
    </div>

    <!-- Lightbox -->
    <Teleport to="body">
      <Transition name="lb">
        <div v-if="lightbox.open"
             class="lb-backdrop"
             @click.self="closeLightbox"
             tabindex="-1"
             ref="lbEl">
          <div class="lb-modal">
            <div class="lb-modal__header">
              <span class="lb-modal__counter">{{ lightbox.index + 1 }} / {{ property.photos.length }}</span>
              <button class="lb-close" @click="closeLightbox" title="Закрыть">✕</button>
            </div>
            <div class="lb-modal__body">
              <img :src="property.photos[lightbox.index]?.image_url"
                   :alt="property.title || 'Фото объекта'"
                   class="lb-img"
                   draggable="false" />
            </div>
            <div v-if="property.photos.length > 1" class="lb-modal__footer">
              <button class="lb-nav" @click="lightboxPrev" title="Предыдущее">&#8592;</button>
              <button class="lb-nav" @click="lightboxNext" title="Следующее">&#8594;</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- ── Основная сетка: параметры + описание ─────────────── -->
    <div class="grid grid--2">
      <!-- ????????? -->
      <div class="panel panel--light">
        <div class="surface-head property-surface-head">
          <div>
            <div class="surface-head__meta">Карточка объекта</div>
            <h2 class="h3">Параметры</h2>
          </div>
          <span class="pd-status-badge">{{ property.status_name }}</span>
        </div>
        <div class="stack" style="margin-top: 12px">
          <InfoRow label="Тип объекта" :value="property.property_type_name || premisesTypeLabel(property.premises_type) || '—'" />
          <InfoRow label="Кадастровый номер" :value="property.cadastral_number || '—'" />
          <InfoRow label="Стоимость" :value="formatMoney(property.price) + ' ₽'" />
          <InfoRow label="Стоимость за м²" :value="property.price_per_sqm ? formatMoney(property.price_per_sqm) + ' ₽' : '—'" />
          <InfoRow label="Общая площадь" :value="property.area_total ? property.area_total + ' м²' : '—'" />
          <InfoRow v-if="showRoomsInfo" label="Количество комнат" :value="formatRoomsValue(property.premises_type, property.rooms_count)" />
          <InfoRow v-if="showFloorInfo || showBuildingFacts" label="Этаж / всего" :value="(property.floor_number || '—') + ' / ' + ((property.total_floors || property.building_details?.total_floors) || '—')" />
          <InfoRow label="Опубликован" :value="property.is_published ? 'Да' : 'Нет'" />
          <template v-if="auth.isAdminOrManager">
            <InfoRow label="Дата создания" :value="property.created_at ? formatDate(property.created_at) : '—'" />
            <InfoRow label="Дата обновления" :value="property.updated_at ? formatDate(property.updated_at) : '—'" />
            <InfoRow label="Дата публикации" :value="property.published_at ? formatDate(property.published_at) : '—'" />
            <InfoRow label="Снят с публикации" :value="property.unpublished_at ? formatDate(property.unpublished_at) : '—'" />
            <InfoRow label="Координаты" :value="property.coordinates_lat && property.coordinates_lon ? property.coordinates_lat + ', ' + property.coordinates_lon : '—'" />
            <InfoRow label="Владелец" :value="property.owner_username || '—'" />
          </template>
        </div>

        <button v-if="priceHistory.length"
                class="pd-price-history-btn"
                @click="showPriceHistory = true">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
          </svg>
          История изменения цены ({{ priceHistory.length }})
        </button>
      </div>

      <div class="panel panel--light">
        <div class="surface-head property-surface-head">
          <div class="surface-head__meta">Описание и теги</div>
          <div class="surface-head__caption">Описание объекта</div>
        </div>
        <h2 class="h3">Описание</h2>
        <p style="white-space: pre-wrap; margin-top: 12px; line-height: 1.7">
          {{ property.description || 'Описание не заполнено.' }}
        </p>

        <template v-if="amenities.length">
          <div class="pd-amenities-label">Удобства и особенности</div>
          <div class="pd-amenities">
            <span v-for="item in amenities" :key="item.amenity" class="pd-amenity-tag">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
              {{ item.amenity_data?.name || item.amenity }}
            </span>
          </div>
        </template>
      </div>
    </div>

    <div class="grid grid--2">
      <div class="panel panel--light">
        <div class="surface-head property-surface-head">
          <div class="surface-head__meta">Дом</div>
          <div class="surface-head__caption">Параметры здания и адреса</div>
        </div>
        <h2 class="h3">Информация о здании</h2>
        <div class="stack" style="margin-top: 12px">
          <InfoRow label="Адрес" :value="property.full_address || [property.house_data?.street?.city?.name ? 'г. ' + property.house_data.street.city.name : null, property.house_data?.street?.name ? (property.house_data.street.street_type || 'ул.') + ' ' + property.house_data.street.name : null, property.house_data?.house_number ? 'д. ' + property.house_data.house_number : null].filter(Boolean).join(', ') || '—'" />
          <InfoRow label="Город" :value="property.house_data?.street?.city?.name || '—'" />
          <InfoRow label="Регион" :value="property.house_data?.street?.city?.region || '—'" />
          <InfoRow label="Улица" :value="property.house_data?.street?.name || '—'" />
          <InfoRow label="Тип улицы" :value="property.house_data?.street?.street_type || '—'" />
          <InfoRow label="Дом" :value="property.house_data?.house_number || '—'" />
          <InfoRow label="Почтовый индекс" :value="property.house_data?.postal_code || '—'" />
          <InfoRow v-if="showBuildingFacts" label="Год постройки" :value="property.building_details?.year_built || '—'" />
          <InfoRow v-if="showBuildingFacts" label="Этажей в доме" :value="property.building_details?.total_floors || '—'" />
          <InfoRow v-if="showBuildingFacts" label="Материал стен" :value="property.building_details?.building_material_data?.name || '—'" />
          <InfoRow v-if="showBuildingFacts" label="Лифты" :value="property.building_details?.elevators_count ?? '—'" />
        </div>
      </div>

      <div class="panel panel--light">
        <div class="surface-head property-surface-head">
          <div class="surface-head__meta">
            {{ isCommercialProperty ? 'Коммерция' : showGarageInfo ? 'Гараж' : showLandInfo && !showResidentialInfo ? 'Участок' : 'Жилая часть' }}
          </div>
          <div class="surface-head__caption">Детали из связанных таблиц</div>
        </div>
        <h2 class="h3">
          {{ isCommercialProperty ? 'Коммерческие параметры' : showGarageInfo ? 'Параметры гаража' : showLandInfo && !showResidentialInfo ? 'Параметры участка' : 'Жилые параметры' }}
        </h2>
        <div v-if="isCommercialProperty" class="stack" style="margin-top: 12px">
          <InfoRow label="Тип коммерции" :value="property.commercial_property_details?.commercial_type_data?.name || '—'" />
          <InfoRow label="Полезная площадь" :value="property.commercial_property_details?.usable_area ? property.commercial_property_details.usable_area + ' м²' : '—'" />
          <InfoRow label="Высота потолков" :value="property.commercial_property_details?.ceiling_height ? property.commercial_property_details.ceiling_height + ' м' : '—'" />
          <InfoRow label="Нагрузка на пол" :value="property.commercial_property_details?.floor_load ? property.commercial_property_details.floor_load + ' кг/м²' : '—'" />
          <InfoRow label="Электрическая мощность" :value="property.commercial_property_details?.electric_power_kw ? property.commercial_property_details.electric_power_kw + ' кВт' : '—'" />
          <InfoRow label="Отдельный вход" :value="property.commercial_property_details?.has_separate_entrance ? 'Да' : 'Нет'" />
          <InfoRow label="Витринные окна" :value="property.commercial_property_details?.has_display_windows ? 'Да' : 'Нет'" />
          <InfoRow label="Первая линия" :value="property.commercial_property_details?.is_first_line ? 'Да' : 'Нет'" />
          <InfoRow label="Парковочные места" :value="property.commercial_property_details?.parking_spaces ?? '—'" />
        </div>
        <div v-else class="stack" style="margin-top: 12px">
          <InfoRow v-if="showResidentialInfo" label="Жилая площадь" :value="property.property_details?.living_area ? property.property_details.living_area + ' м²' : '—'" />
          <InfoRow v-if="showResidentialInfo" label="Площадь кухни" :value="property.property_details?.kitchen_area ? property.property_details.kitchen_area + ' м²' : '—'" />
          <InfoRow v-if="showResidentialInfo" label="Высота потолков" :value="property.property_details?.ceiling_height ? property.property_details.ceiling_height + ' м' : '—'" />
          <InfoRow v-if="propertyTypeSchema.showBalcony" label="Балконы" :value="property.property_details?.balcony_count ?? '—'" />
          <InfoRow v-if="propertyTypeSchema.showBathroom" label="Санузлы" :value="property.property_details?.bathroom_count ?? '—'" />
          <InfoRow v-if="propertyTypeSchema.showBathroom" label="Тип санузла" :value="property.property_details?.bathroom_type_data?.name || '—'" />
          <InfoRow v-if="propertyTypeSchema.showRenovation" label="Тип ремонта" :value="property.property_details?.renovation_type_data?.name || '—'" />
          <InfoRow v-if="propertyTypeSchema.showBedrooms" label="Спальни" :value="property.property_details?.bedrooms_count ?? '—'" />
          <InfoRow v-if="propertyTypeSchema.showPrivateHouseFloors" label="Этажей в помещении" :value="property.property_details?.floors_count ?? '—'" />
          <InfoRow v-if="showLandInfo" label="Площадь участка" :value="property.property_details?.land_area ? property.property_details.land_area + ' м²' : '—'" />
        </div>
      </div>
    </div>

    <div v-if="clientViewings.length" class="panel panel--light">
      <div class="surface-head property-surface-head">
        <div>
          <div class="surface-head__meta">Просмотры</div>
          <h2 class="h3">Мои просмотры по объекту</h2>
        </div>
        <div class="surface-head__caption">{{ clientViewings.length }} записей</div>
      </div>
      <div class="stack" style="margin-top: 12px">
        <div v-for="viewing in clientViewings" :key="viewing.id" class="viewing-card">
          <div class="viewing-card__main">
            <div>
              <b>{{ formatDate(viewing.scheduled_date || viewing.viewing_date) }}</b>
              <div class="muted" style="font-size: 13px; margin-top: 4px">
                Статус просмотра: {{ viewing.status_name || '—' }}
              </div>
            </div>
            <div class="viewing-card__meta">
              <span class="tag" :class="viewing.payment_status === 'paid' ? 'tag--paid' : 'tag--warning'">
                {{ viewingPaymentStatusLabel(viewing.payment_status) }}
              </span>
              <span v-if="viewing.payment_amount" class="muted">
                {{ formatMoney(viewing.payment_amount) }} ₽
              </span>
            </div>
          </div>
          <div class="viewing-card__actions">
            <a v-if="viewing.payment_url && ['pending', 'failed'].includes(viewing.payment_status)"
               class="btn btn--accent btn--sm"
               :href="viewing.payment_url"
               target="_blank" rel="noreferrer">
              Перейти к оплате
            </a>
            <button v-else-if="canInitiateViewingPayment(viewing)"
                    class="btn btn--accent btn--sm"
                    :disabled="payingViewingId === viewing.id"
                    @click="startViewingPayment(viewing)">
              {{ payingViewingId === viewing.id ? 'Подготовка…' : viewing.payment_id ? 'Получить новую ссылку' : 'Оплатить просмотр' }}
            </button>
            <button v-if="viewing.payment_id && ['pending', 'failed'].includes(viewing.payment_status)"
                    class="btn btn--sm"
                    :disabled="syncingPaymentId === viewing.payment_id"
                    @click="refreshViewingPayment(viewing)">
              {{ syncingPaymentId === viewing.payment_id ? 'Проверка…' : 'Проверить оплату' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Документы + собственники ─────────────────────────── -->
    <div class="grid grid--2">
      <div class="panel panel--light">
        <div class="surface-head property-surface-head">
          <div class="surface-head__meta">Файлы</div>
          <div class="surface-head__caption">Документы объекта</div>
        </div>
        <h2 class="h3">Документы</h2>
        <div v-if="auth.isStaff" class="row" style="margin-top: 12px; gap: 8px">
          <button class="btn btn--sm btn--primary" @click="downloadSummaryPdf">
            Скачать карточку PDF
          </button>
        </div>
        <div v-if="documents.length" class="stack" style="margin-top: 12px">
          <a v-for="doc in documents" :key="doc.id" :href="doc.file_url" class="doc-row" target="_blank" rel="noreferrer">
            <span>{{ doc.document_name }}</span>
            <span class="muted" style="font-size: 12px">
              {{ doc.is_verified ? 'Проверен' : 'Не проверен' }}
              <span v-if="doc.verified_by_username">· {{ doc.verified_by_username }}</span>
            </span>
          </a>
        </div>
        <div v-else class="muted" style="margin-top: 12px">Документы не загружены.</div>
      </div>

      <div v-if="property.owners?.length" class="panel panel--light">
        <div class="surface-head property-surface-head">
          <div class="surface-head__meta">Собственники</div>
          <div class="surface-head__caption">{{ property.owners.length }} записей</div>
        </div>
        <h2 class="h3">Владельцы объекта</h2>
        <div class="stack" style="margin-top: 12px">
          <div v-for="owner in property.owners" :key="`${owner.property}-${owner.client_profile}`" class="owner-row">
            <div class="owner-row__main">
              <b>{{ [owner.client_last_name, owner.client_first_name, owner.client_middle_name].filter(Boolean).join(' ') || owner.client_username || '—' }}</b>
              <div class="muted" style="font-size: 12px">
                {{ owner.client_username || '—' }}
                <span v-if="owner.ownership_share !== null && owner.ownership_share !== undefined">
                  · {{ owner.ownership_share }}%
                </span>
              </div>
            </div>
            <div class="owner-row__contacts">
              <span v-if="owner.client_phone">{{ owner.client_phone }}</span>
              <span v-if="owner.client_email">{{ owner.client_email }}</span>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="panel panel--light">
        <div class="surface-head property-surface-head">
          <div class="surface-head__meta">Собственники</div>
          <div class="surface-head__caption">Нет данных</div>
        </div>
        <h2 class="h3">Владельцы объекта</h2>
        <div class="muted" style="margin-top: 12px">Собственники не указаны.</div>
      </div>
    </div>

    <!-- ── Управление статусом (только для сотрудников) ──────── -->
    <div v-if="auth.isAdminOrManager" class="panel panel--light">
      <div class="surface-head property-surface-head">
        <div class="surface-head__meta">Управление</div>
        <div class="surface-head__caption">{{ property.status_name }}</div>
      </div>
      <div class="row row--between">
        <h2 class="h3">Смена статуса объекта</h2>
      </div>
      <div class="row property-status-actions" style="gap: 10px; flex-wrap: wrap; margin-top: 12px">
        <button v-for="s in allowedStatuses" :key="s.id"
                class="btn btn--sm"
                :class="{ 'btn--primary': s.id === property.status }"
                :disabled="s.id === property.status"
                @click="changeStatus(s.id)">
          {{ s.name }}
        </button>
      </div>
    </div>

    <!-- ── История изменений статуса ─────────────────────────── -->
    <div class="panel panel--light" v-if="history.length">
      <div class="surface-head property-surface-head">
        <div class="surface-head__meta">Журнал изменений</div>
        <div class="surface-head__caption">{{ historyCount }} записей</div>
      </div>
      <h2 class="h3">История изменений статуса</h2>
      <div class="table-wrap property-history-table">
        <table class="table">
          <thead><tr><th>Дата</th><th>Статус</th><th>Сотрудник</th></tr></thead>
          <tbody>
            <tr v-for="h in history" :key="h.id">
              <td>{{ formatDate(h.changed_at) }}</td>
              <td>{{ h.status_name }}</td>
              <td>{{ h.changed_by_username }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <AuditLogPanel
      v-if="auth.isStaff && property"
      :params="{ property: property.id }"
      title="История объекта"
      caption="Журнал действий"
      empty-text="По объекту ещё нет записей журнала."
      :page-size="12"
    />
  </section>
  <div v-else class="empty">Загрузка объекта…</div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import * as viewingPaymentsApi from '../api/viewingPayments'
import AuditLogPanel from '../components/AuditLogPanel.vue'
import InfoRow from '../components/InfoRow.vue'
import { useAuthStore } from '../store/auth'
import { useConfirmStore } from '../store/confirm'
import { extractError, useToastsStore } from '../store/toasts'
import { formatMoney as fmtMoney, formatDate } from '@/utils/formatters'
import { LOOKUP_PAGE_SIZE, unpackPaginated } from '@/utils/paginated'
import { formatRoomsValue, getPropertyTypeSchema, normalizePropertyType, propertyTypeLabel } from '@/utils/propertyTypes'
import { downloadBlobResponse } from '@/utils/downloads'

const route = useRoute(); const router = useRouter()
const auth = useAuthStore()
const confirm = useConfirmStore()
const toasts = useToastsStore()
const property = ref(null)
const statuses = ref([])
const history = ref([])
const clientViewings = ref([])
const payingViewingId = ref(null)
const syncingPaymentId = ref(null)

// Lightbox
const lbEl = ref(null)
const lightbox = reactive({ open: false, index: 0 })

function openLightbox (idx) {
  lightbox.index = idx
  lightbox.open = true
  nextTick(() => lbEl.value?.focus())
}
function closeLightbox () { lightbox.open = false }
function lightboxPrev () {
  lightbox.index = (lightbox.index - 1 + (property.value?.photos?.length || 1)) % (property.value?.photos?.length || 1)
}
function lightboxNext () {
  lightbox.index = (lightbox.index + 1) % (property.value?.photos?.length || 1)
}
function onKeydown (e) {
  if (!lightbox.open) return
  if (e.key === 'ArrowLeft') lightboxPrev()
  else if (e.key === 'ArrowRight') lightboxNext()
  else if (e.key === 'Escape') closeLightbox()
}
onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))

const showRequestForm = ref(false)
const showPriceHistory = ref(false)
const requestError = ref('')
const requestForm = reactive({ description: '' })

const photosCount = computed(() => property.value?.photos?.length || 0)
const visiblePhotosCount = computed(() => (
  property.value?.photos?.filter((photo) => !photo.is_hidden).length || 0
))
const historyCount = computed(() => history.value.length)
const amenities = computed(() => property.value?.amenities || [])
const documents = computed(() => property.value?.documents || [])
const priceHistory = computed(() => property.value?.price_history || [])
const priceLabel = computed(() => (
  property.value?.price ? `${formatMoney(property.value.price)} ₽` : '—'
))
const propertyTypeCode = computed(() => normalizePropertyType(
  property.value?.property_type_code || property.value?.premises_type,
))
const propertyTypeSchema = computed(() => getPropertyTypeSchema(propertyTypeCode.value))
const isCommercialProperty = computed(() => propertyTypeSchema.value.showCommercialDetails)
const showBuildingFacts = computed(() => propertyTypeSchema.value.showBuildingDetails)
const showRoomsInfo = computed(() => propertyTypeSchema.value.showRooms)
const showFloorInfo = computed(() => propertyTypeSchema.value.showFloor)
const showResidentialInfo = computed(() => propertyTypeSchema.value.showResidentialDetails)
const showGarageInfo = computed(() => propertyTypeSchema.value.showGarageRenovationOnly)
const showLandInfo = computed(() => propertyTypeSchema.value.showLandArea)
const allowedStatuses = computed(() => {
  const allowedIds = new Set(property.value?.allowed_status_ids || [])
  return statuses.value.filter((status) => allowedIds.has(status.id))
})
const isOwnProperty = computed(() => (
  auth.isClient
  && property.value?.owner
  && Number(property.value.owner) === Number(auth.user?.id)
))
const canLeaveRequest = computed(() => !auth.isStaff && !isOwnProperty.value)

function viewingPaymentStatusLabel(status) {
  return {
    paid: 'Оплата подтверждена',
    pending: 'Ожидает оплаты',
    failed: 'Ошибка оплаты',
    refunded: 'Возврат выполнен',
  }[status] || 'Оплата не создана'
}

function canInitiateViewingPayment(viewing) {
  return (
    auth.isClient
    && (
      !viewing.payment_id
      || (
        ['pending', 'failed'].includes(viewing.payment_status)
        && !viewing.payment_url
      )
    )
  )
}

async function loadClientViewings() {
  if (!auth.isClient || !property.value?.id) {
    clientViewings.value = []
    return
  }
  try {
    const { data } = await api.get('/property-viewings/', {
      params: { property: property.value.id },
    })
    clientViewings.value = unpackPaginated(data).items
  } catch (_err) {
    clientViewings.value = []
  }
}

async function startViewingPayment(viewing) {
  payingViewingId.value = viewing.id
  const { ok, data, error } = await viewingPaymentsApi.initiateViewingPayment(viewing.id)
  payingViewingId.value = null
  if (!ok) {
    toasts.error(error || 'Не удалось создать оплату просмотра')
    return
  }
  await loadClientViewings()
  if (data?.payment_url) {
    window.open(data.payment_url, '_blank', 'noopener,noreferrer')
    return
  }
  toasts.success('Платёж создан. Ссылка на оплату готова.')
}

async function refreshViewingPayment(viewing) {
  if (!viewing.payment_id) return
  syncingPaymentId.value = viewing.payment_id
  const { ok, error } = await viewingPaymentsApi.syncViewingPayment(viewing.payment_id)
  syncingPaymentId.value = null
  if (!ok) {
    toasts.error(error || 'Не удалось обновить статус оплаты')
    return
  }
  await Promise.all([load(), loadClientViewings()])
  toasts.success('Статус оплаты обновлён')
}

async function submitRequest () {
  if (!canLeaveRequest.value) {
    requestError.value = 'Нельзя оставить заявку на собственный объект.'
    return
  }
  requestError.value = ''
  try {
    await api.post('/requests/', {
      operation_type: property.value.operation_type,
      property: property.value.id,
      description: requestForm.description,
    })
    showRequestForm.value = false
    requestForm.description = ''
    router.push('/requests')
  } catch (err) {
    requestError.value = err.response?.data
      ? Object.values(err.response.data).flat().join(' ')
      : 'Не удалось отправить заявку.'
  }
}

async function load() {
  const propertyId = route.params.id
  try {
    const [propertyResponse, historyResponse] = await Promise.all([
      api.get(`/properties/${propertyId}/`),
      api.get(`/properties/${propertyId}/history/`).catch(() => ({ data: [] })),
    ])
    property.value = {
      ...propertyResponse.data,
      photos: (propertyResponse.data?.photos || []).filter((photo) => photo.image_url),
    }
    history.value = Array.isArray(historyResponse.data) ? historyResponse.data : []
    await loadClientViewings()
  } catch (err) {
    property.value = null
    history.value = []
    clientViewings.value = []
    toasts.error(extractError(err, 'Не удалось загрузить объект'))
    return
  }

  api.get('/property-statuses/', {
    params: { page_size: LOOKUP_PAGE_SIZE },
  })
    .then(({ data }) => {
      statuses.value = unpackPaginated(data).items
    })
    .catch(() => {
      statuses.value = []
    })

}

async function changeStatus(id) {
  try {
    await api.post(`/properties/${route.params.id}/change_status/`,
                   { status_id: id })
    await load()
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось изменить статус объекта'))
  }
}

async function downloadSummaryPdf() {
  try {
    const response = await api.get(`/properties/${route.params.id}/summary-pdf/`, {
      responseType: 'blob',
    })
    downloadBlobResponse(response, `property-${route.params.id}.pdf`)
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось скачать карточку объекта'))
  }
}

async function uploadPhotos(e) {
  const files = Array.from(e.target.files || [])
  if (!files.length) return
  let uploaded = false
  try {
    for (const file of files) {
      const fd = new FormData()
      fd.append('image', file)
      await api.post(`/properties/${route.params.id}/upload_photo/`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      uploaded = true
    }
    await load()
  } catch (err) {
    if (uploaded) await load()
    toasts.error(extractError(
      err,
      uploaded
        ? 'Часть фотографий загружена, но операция завершилась с ошибкой'
        : 'Не удалось загрузить фотографии',
    ))
  } finally {
    e.target.value = ''
  }
}

async function removePhoto(photo) {
  const approved = await confirm.ask({
    title: 'Удаление фотографии',
    message: 'Удалить фотографию?',
    confirmLabel: 'Удалить',
    danger: true,
  })
  if (!approved) return
  try {
    await api.delete(`/property-photos/${photo.id}/`)
    await load()
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось удалить фотографию'))
  }
}

async function setCover (photo) {
  try {
    await api.post(`/property-photos/${photo.id}/set_cover/`)
    await load()
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось установить обложку'))
  }
}

async function toggleHidden (photo) {
  try {
    await api.post(`/property-photos/${photo.id}/toggle_hidden/`)
    await load()
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось изменить видимость'))
  }
}

async function remove() {
  const approved = await confirm.ask({
    title: 'Удаление объекта',
    message: 'Вы уверены, что хотите удалить этот объект? Удаление невозможно, если к объекту привязаны заявки, сделки или просмотры.',
    confirmLabel: 'Удалить',
    danger: true,
  })
  if (!approved) return
  try {
    await api.delete(`/properties/${route.params.id}/`)
    router.push('/properties')
  } catch (err) {
    toasts.error(extractError(err, 'Не удалось удалить объект'))
  }
}

function formatMoney (v) { return fmtMoney(v, '0') }
function premisesTypeLabel (value) {
  return propertyTypeLabel(normalizePropertyType(value)) || '—'
}

watch(() => route.params.id, () => {
  load()
}, { immediate: true })
</script>

<style scoped>
.gallery {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 14px;
  margin-top: 14px;
}

.gallery__item {
  position: relative;
  aspect-ratio: 4 / 3;
  overflow: hidden;
  border-radius: 22px;
  border: 1px solid var(--c-border);
  background: rgba(255, 255, 255, 0.06);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  box-shadow: var(--shadow-1);
  transition: transform 0.3s ease, box-shadow 0.3s ease, border-color 0.3s ease, background 0.3s ease;
}

.gallery__item:hover {
  transform: translateY(-5px);
  background: rgba(255, 255, 255, 0.08);
  box-shadow: var(--shadow-glow);
  border-color: var(--c-border-strong);
}

.gallery__item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.gallery__img {
  cursor: zoom-in;
  transition: transform 0.25s ease;
}

.gallery__item:hover .gallery__img {
  transform: scale(1.04);
}

.owner-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  border: 1px solid var(--c-border);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.04);
}

.owner-row__main,
.owner-row__contacts {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.owner-row__contacts {
  align-items: flex-end;
  text-align: right;
  color: var(--c-ink-soft);
  font-size: 13px;
}

.viewing-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  border: 1px solid var(--c-border);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.04);
}

.viewing-card__main,
.viewing-card__actions,
.viewing-card__meta {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.viewing-card__main {
  justify-content: space-between;
  flex: 1 1 auto;
}

.tag--paid {
  background: rgba(99, 208, 197, 0.16);
  color: #effffd;
  border-color: rgba(99, 208, 197, 0.24);
}

.tag--warning {
  background: rgba(255, 191, 87, 0.14);
  color: #ffe6ae;
  border-color: rgba(255, 191, 87, 0.22);
}

/* ---- Lightbox ---- */
.lb-backdrop {
  position: fixed;
  inset: 0;
  z-index: 200;
  background: rgba(4, 12, 20, 0.72);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  display: flex;
  align-items: center;
  justify-content: center;
  outline: none;
}

.lb-modal {
  position: relative;
  display: flex;
  flex-direction: column;
  width: min(80vw, 960px);
  max-height: 85vh;
  background: rgba(10, 24, 38, 0.88);
  border: 1px solid var(--c-border-strong, rgba(255,255,255,0.12));
  border-radius: 24px;
  box-shadow: 0 40px 120px rgba(0, 0, 0, 0.65);
  overflow: hidden;
}

.lb-modal__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}

.lb-modal__counter {
  color: rgba(255, 255, 255, 0.45);
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.4px;
}

.lb-modal__body {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  padding: 0;
}

.lb-img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  display: block;
  user-select: none;
}

.lb-close {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.10);
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.7);
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s ease, color 0.2s ease, transform 0.2s ease;
}

.lb-close:hover {
  background: rgba(255, 111, 134, 0.22);
  color: #fff;
  transform: rotate(90deg);
}

.lb-modal__footer {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 12px 18px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}

.lb-nav {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.10);
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.7);
  font-size: 16px;
  cursor: pointer;
  transition: background 0.2s ease, color 0.2s ease;
}

.lb-nav:hover {
  background: rgba(31, 163, 154, 0.22);
  color: #fff;
}

/* Transition */
.lb-enter-active,
.lb-leave-active {
  transition: opacity 0.2s ease;
}
.lb-enter-active .lb-modal,
.lb-leave-active .lb-modal {
  transition: transform 0.2s ease;
}
.lb-enter-from,
.lb-leave-to {
  opacity: 0;
}
.lb-enter-from .lb-modal {
  transform: scale(0.95) translateY(8px);
}
.lb-leave-to .lb-modal {
  transform: scale(0.95) translateY(8px);
}

.gallery__item.is-hidden img {
  filter: grayscale(0.85) opacity(0.42);
}

.gallery__item.is-cover {
  box-shadow: 0 0 0 2px rgba(99, 208, 197, 0.28), var(--shadow-glow);
}

.gallery__badges {
  position: absolute;
  top: 10px;
  left: 10px;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.gallery__badge {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(7, 19, 29, 0.64);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.gallery__badge.is-cover {
  border-color: rgba(99, 208, 197, 0.24);
  background: rgba(99, 208, 197, 0.18);
  color: #f0fffc;
}

.gallery__badge.is-hidden {
  border-color: rgba(255, 111, 134, 0.18);
  background: rgba(255, 111, 134, 0.14);
  color: #ffd7df;
}

.gallery__toolbar {
  position: absolute;
  bottom: 10px;
  right: 10px;
  display: flex;
  gap: 5px;
  opacity: 0;
  transform: translateY(4px);
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.gallery__item:hover .gallery__toolbar {
  opacity: 1;
  transform: translateY(0);
}

.gallery__btn {
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.10);
  background: rgba(7, 19, 29, 0.72);
  color: rgba(255, 255, 255, 0.75);
  cursor: pointer;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  transition: background 0.18s ease, color 0.18s ease, border-color 0.18s ease;
}

.gallery__btn:hover:not(:disabled) {
  background: rgba(31, 163, 154, 0.28);
  border-color: rgba(31, 163, 154, 0.3);
  color: #fff;
}

.gallery__btn--active {
  background: rgba(99, 208, 197, 0.2);
  border-color: rgba(99, 208, 197, 0.3);
  color: #63d0c5;
}

.gallery__btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.gallery__btn--danger:hover:not(:disabled) {
  background: rgba(255, 111, 134, 0.28);
  border-color: rgba(255, 111, 134, 0.3);
  color: #fff;
}

.modal {
  z-index: 80;
}

.modal__card {
  width: 100%;
  max-width: 520px;
  max-height: calc(100vh - 32px);
  overflow: auto;
}

.property-surface-head {
  margin-bottom: 12px;
}

.property-status-actions {
  margin-top: 14px !important;
}

.property-history-table .table {
  min-width: 560px;
}

/* ── KPI-полоса ─────────────────────────────────────────── */
.pd-kpi-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
}

.pd-kpi-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 18px 20px;
  background: var(--grad-card-soft);
  border: 1px solid var(--c-border);
  border-radius: 22px;
  box-shadow: var(--shadow-1);
}

.pd-kpi-card__value--price {
  color: var(--c-ink);
}

.pd-kpi-card__label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--c-text-muted);
}

.pd-kpi-card__value {
  font-size: 22px;
  font-weight: 800;
  color: var(--c-ink);
  line-height: 1.15;
}

.pd-kpi-card__meta {
  font-size: 12px;
  color: var(--c-text-muted);
  margin-top: 2px;
}

/* ── Статус-бейдж ─────────────────────────────────────── */
.pd-status-badge {
  display: inline-flex;
  align-items: center;
  height: 28px;
  padding: 0 14px;
  border-radius: 999px;
  border: 1px solid rgba(99, 208, 197, 0.22);
  background: rgba(99, 208, 197, 0.10);
  color: var(--c-accent-2);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  white-space: nowrap;
  align-self: flex-start;
}

/* ── Удобства ─────────────────────────────────────────── */
.pd-amenities-label {
  margin-top: 20px;
  margin-bottom: 10px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--c-text-muted);
}

.pd-amenities {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.pd-amenity-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 999px;
  border: 1px solid var(--c-border);
  background: rgba(255, 255, 255, 0.05);
  color: var(--c-ink-soft);
  font-size: 13px;
  font-weight: 500;
  transition: background 0.2s ease, border-color 0.2s ease;
}

.pd-amenity-tag svg {
  color: var(--c-accent);
  flex-shrink: 0;
}

.pd-amenity-tag:hover {
  background: rgba(99, 208, 197, 0.08);
  border-color: rgba(99, 208, 197, 0.22);
}

/* ── Кнопка истории цен ─────────────────────────────── */
.pd-price-history-btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  margin-top: 18px;
  padding: 9px 18px;
  border-radius: 999px;
  border: 1px solid var(--c-border);
  background: rgba(255, 255, 255, 0.04);
  color: var(--c-text-muted);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease, color 0.2s ease;
}

.pd-price-history-btn:hover {
  background: rgba(99, 208, 197, 0.10);
  border-color: rgba(99, 208, 197, 0.28);
  color: var(--c-accent-2);
}

.pd-price-history-btn svg {
  color: var(--c-accent);
  flex-shrink: 0;
}

/* ── Модал истории цен ───────────────────────────────── */
.ph-backdrop {
  position: fixed;
  inset: 0;
  z-index: 200;
  background: rgba(4, 12, 20, 0.72);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.ph-modal {
  display: flex;
  flex-direction: column;
  width: min(560px, 100%);
  max-height: 80vh;
  background: linear-gradient(180deg, #0d3b3e 0%, #042e2e 100%);
  border: 1px solid var(--c-border-strong);
  border-radius: 28px;
  box-shadow: 0 40px 120px rgba(0, 0, 0, 0.65), var(--shadow-glow);
  overflow: hidden;
}

.ph-modal__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 22px 24px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}

.ph-modal__eyebrow {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--c-accent);
  margin-bottom: 4px;
}

.ph-modal__title {
  font-size: 20px;
  font-weight: 800;
  color: var(--c-ink);
  margin: 0;
}

.ph-modal__body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px 24px;
}

/* ── Timeline ─────────────────────────────────────────── */
.ph-timeline {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.ph-item {
  display: flex;
  gap: 16px;
  position: relative;
}

.ph-item__dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--c-border-strong);
  border: 2px solid rgba(120, 216, 206, 0.4);
  flex-shrink: 0;
  margin-top: 4px;
  z-index: 1;
}

.ph-item__dot--up {
  background: rgba(94, 208, 194, 0.30);
  border-color: var(--c-success);
}

.ph-item__dot--down {
  background: rgba(194, 85, 74, 0.28);
  border-color: var(--c-danger);
}

.ph-item__line {
  position: absolute;
  left: 5px;
  top: 16px;
  bottom: -20px;
  width: 2px;
  background: rgba(120, 216, 206, 0.12);
}

.ph-item__content {
  flex: 1;
  padding-bottom: 20px;
}

.ph-item__date {
  font-size: 12px;
  color: var(--c-text-muted);
  margin-bottom: 6px;
}

.ph-item__prices {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.ph-item__old {
  font-size: 14px;
  color: var(--c-text-muted);
  text-decoration: line-through;
}

.ph-item__arrow {
  flex-shrink: 0;
}

.ph-item__arrow--up {
  color: var(--c-success);
  transform: rotate(-45deg);
}

.ph-item__arrow--down {
  color: var(--c-danger);
  transform: rotate(45deg);
}

.ph-item__new {
  font-size: 16px;
  font-weight: 800;
  color: var(--c-ink);
}

.ph-item__delta {
  font-size: 12px;
  font-weight: 700;
  padding: 2px 10px;
  border-radius: 999px;
}

.ph-item__delta--up {
  background: rgba(94, 208, 194, 0.14);
  color: var(--c-success);
  border: 1px solid rgba(94, 208, 194, 0.22);
}

.ph-item__delta--down {
  background: rgba(194, 85, 74, 0.14);
  color: var(--c-danger-2);
  border: 1px solid rgba(194, 85, 74, 0.22);
}

.ph-item__by {
  font-size: 12px;
  color: var(--c-text-muted);
  margin-top: 4px;
}

/* ── Transition модала цен ────────────────────────────── */
.ph-enter-active,
.ph-leave-active {
  transition: opacity 0.22s ease;
}
.ph-enter-active .ph-modal,
.ph-leave-active .ph-modal {
  transition: transform 0.22s ease;
}
.ph-enter-from,
.ph-leave-to {
  opacity: 0;
}
.ph-enter-from .ph-modal {
  transform: scale(0.95) translateY(10px);
}
.ph-leave-to .ph-modal {
  transform: scale(0.95) translateY(10px);
}
</style>
