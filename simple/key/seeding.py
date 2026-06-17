# -*- coding: utf-8 -*-
"""Компактный слой заполнения справочников и тестовых данных."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from .models import (
    Amenity,
    AuditAction,
    AuditEntityType,
    BathroomType,
    BuildingDetails,
    BuildingMaterial,
    City,
    ClientCompanyDetails,
    ClientIndividualDetails,
    ClientKind,
    ClientProfile,
    CommercialPropertyDetails,
    CommercialPropertyType,
    ContractStatus,
    Deal,
    DealParticipantRole,
    DealStatus,
    DocumentType,
    EmployeeProfile,
    House,
    OperationType,
    Property,
    PropertyDetails,
    PropertyExternalSource,
    PropertyOwner,
    PropertyPhoto,
    PropertyStatus,
    PropertyType,
    RenovationType,
    Request,
    RequestMatchStatus,
    RequestStatus,
    Street,
    Task,
    TaskPriority,
    TaskStatus,
    TaskType,
    User,
    UserRole,
    UserType,
    ViewingStatus,
)
from .seeding_catalog import (
    CITY_DATA,
    COMPANY_CLIENTS,
    DEAL_STATUSES,
    EMPLOYEE_SPECS,
    INDIVIDUAL_CLIENTS,
    LOOKUP_TABLES,
    OPERATION_TYPES,
    PROPERTY_BLUEPRINTS,
    PROPERTY_STATUSES,
    REQUEST_STATUSES,
    TASK_STATUSES,
    USER_ROLES,
)
from .twogis import TwoGisClient


SEED_MARKER = '__seed_demo__'
SEED_PASSWORD = 'SeedPass123!'
DECIMAL_100 = Decimal('100.00')


@dataclass
class PropertyBundle:
    property: Property
    city: City
    employee: EmployeeProfile
    category: str
    subtype: str
    operation_code: str
    status_code: str
    commercial_type_code: str | None
    land_area: Decimal | None
    is_commercial_like: bool


class SeedLogger:
    def __init__(self, command=None):
        self.command = command

    def _write(self, message: str, style: str | None = None) -> None:
        if self.command is None:
            return
        if style:
            message = getattr(self.command.style, style)(message)
        self.command.stdout.write(message)

    def info(self, message: str) -> None:
        self._write(message)

    def success(self, message: str) -> None:
        self._write(message, 'SUCCESS')

    def warning(self, message: str) -> None:
        self._write(message, 'WARNING')

    def step(self, current: int, total: int, label: str) -> None:
        self.info(f'[{current}/{total}] {label}')


class SeedDataService:
    """Сервис заполнения проекта справочниками и тестовыми данными."""

    def __init__(self, command=None, **_: Any):
        self.log = SeedLogger(command)

    def seed_dictionaries(self, *, flush: bool = False) -> dict[str, tuple[int, int]]:
        if flush:
            for model in reversed(
                [
                    ViewingStatus,
                    DealParticipantRole,
                    DocumentType,
                    RequestMatchStatus,
                    AuditAction,
                    AuditEntityType,
                    Amenity,
                    CommercialPropertyType,
                    BuildingMaterial,
                    BathroomType,
                    RenovationType,
                    UserType,
                    ContractStatus,
                    ClientKind,
                    TaskType,
                    TaskPriority,
                    PropertyType,
                    UserRole,
                    TaskStatus,
                    DealStatus,
                    RequestStatus,
                    PropertyStatus,
                    OperationType,
                ]
            ):
                model.objects.all().delete()

        counts = {
            'operation_types': self._seed_rows(OperationType, OPERATION_TYPES),
            'property_statuses': self._seed_rows(PropertyStatus, PROPERTY_STATUSES),
            'request_statuses': self._seed_rows(RequestStatus, REQUEST_STATUSES),
            'deal_statuses': self._seed_rows(DealStatus, DEAL_STATUSES),
            'task_statuses': self._seed_rows(TaskStatus, TASK_STATUSES),
            'user_roles': self._seed_rows(UserRole, USER_ROLES),
        }
        for model, rows in LOOKUP_TABLES:
            counts[model.__name__] = self._seed_rows(model, rows)
        self.log.success('Справочники синхронизированы.')
        return counts

    def seed_demo(
        self,
        *,
        flush: bool = False,
        force_images: bool = False,
        ensure_dictionaries: bool = True,
    ) -> dict[str, int]:
        if ensure_dictionaries:
            self.seed_dictionaries(flush=False)
        if flush or self._has_seeded_demo():
            self.flush_demo()

        self.log.step(1, 6, 'Создание пользователей и профилей')
        users = self._seed_users()

        self.log.step(2, 6, 'Создание объектов недвижимости')
        properties = self._seed_properties(users['employees'], force_images=force_images)

        self.log.step(3, 6, 'Привязка владельцев и валидация долей')
        self._seed_property_owners(properties, users['individual_clients'], users['company_clients'])

        self.log.step(4, 6, 'Создание заявок')
        requests = self._seed_requests(properties, users['clients'], users['employees'])

        self.log.step(5, 6, 'Создание сделок и задач')
        deals = self._seed_deals(requests)
        tasks = self._seed_tasks(properties, requests, deals, users['clients'], users['employees'])

        self.log.step(6, 6, 'Финальная валидация')
        summary = self._validate_seed(users, properties, requests, tasks, deals)
        self.log.success(f'Готово: {summary}')
        return summary

    def flush_demo(self) -> dict[str, int]:
        seeded_users = User.objects.filter(username__startswith='seed_')
        seeded_properties = Property.objects.filter(description__contains=SEED_MARKER)
        house_ids = list(seeded_properties.values_list('house_id', flat=True))

        Task.objects.filter(
            Q(assignee__username__startswith='seed_')
            | Q(created_by__username__startswith='seed_')
            | Q(client_profile__user__username__startswith='seed_')
            | Q(property__description__contains=SEED_MARKER)
            | Q(request__client_profile__user__username__startswith='seed_')
            | Q(deal__client__username__startswith='seed_')
        ).delete()
        Deal.objects.filter(
            Q(client__username__startswith='seed_')
            | Q(agent__username__startswith='seed_')
            | Q(request__client_profile__user__username__startswith='seed_')
            | Q(property__description__contains=SEED_MARKER)
        ).delete()
        Request.objects.filter(
            Q(client_profile__user__username__startswith='seed_')
            | Q(employee_profile__user__username__startswith='seed_')
            | Q(property__description__contains=SEED_MARKER)
        ).delete()
        Property.objects.filter(pk__in=seeded_properties.values_list('pk', flat=True)).delete()
        User.objects.filter(pk__in=seeded_users.values_list('pk', flat=True)).delete()
        House.objects.filter(pk__in=house_ids, properties__isnull=True).delete()
        Street.objects.filter(houses__isnull=True).delete()
        City.objects.filter(streets__isnull=True).delete()
        BuildingDetails.objects.filter(house_id__in=house_ids).delete()
        return {'flushed': 1}

    def _has_seeded_demo(self) -> bool:
        return (
            User.objects.filter(username__startswith='seed_').exists()
            or Property.objects.filter(description__contains=SEED_MARKER).exists()
        )

    def _seed_rows(self, model, rows: list[dict[str, Any]]) -> tuple[int, int]:
        created = 0
        updated = 0
        for row in rows:
            lookup = {'code': row['code']}
            defaults = {key: value for key, value in row.items() if key != 'code'}
            _, is_created = model.objects.update_or_create(**lookup, defaults=defaults)
            created += int(is_created)
            updated += int(not is_created)
        return created, updated

    def _seed_users(self) -> dict[str, list]:
        lookups = self._lookups()
        employees: list[EmployeeProfile] = []
        individual_clients: list[ClientProfile] = []
        company_clients: list[ClientProfile] = []
        for index, (role_code, first_name, last_name, position) in enumerate(EMPLOYEE_SPECS, start=1):
            user = self._create_user(
                username=f'seed_{role_code}_{index}',
                email=f'seed.{role_code}.{index}@example.com',
                phone=f'+7999000{index:04d}',
                user_type=lookups['user_types']['employee'],
                role=lookups['user_roles'][role_code],
                is_staff=True,
            )
            profile = EmployeeProfile(
                user=user,
                first_name=first_name,
                last_name=last_name,
                position=position,
                hire_date=timezone.localdate() - timedelta(days=420 + index * 28),
                internal_phone=f'{100 + index}',
            )
            self._save(profile)
            employees.append(profile)

        for index, (first_name, last_name) in enumerate(INDIVIDUAL_CLIENTS, start=1):
            user = self._create_user(
                username=f'seed_client_ind_{index}',
                email=f'seed.client.ind.{index}@example.com',
                phone=f'+7999111{index:04d}',
                user_type=lookups['user_types']['client'],
                role=None,
                is_staff=False,
            )
            profile = ClientProfile(
                user=user,
                first_name=first_name,
                last_name=last_name,
                middle_name='Александрович' if index % 2 else 'Сергеевна',
                client_kind_ref=lookups['client_kinds']['individual'],
            )
            self._save(profile)
            details = ClientIndividualDetails(
                profile=profile,
                passport_series=f'{45 + index // 4:02d}{10 + index:02d}',
                passport_number=f'{120000 + index:06d}',
                passport_issued_by='ГУ МВД России по Иркутской области',
                passport_issued_date=timezone.localdate() - timedelta(days=3650 + index * 90),
                passport_code=f'{380 + index % 10:03d}-{100 + index:03d}',
            )
            self._save(details)
            individual_clients.append(profile)

        for index, company_name in enumerate(COMPANY_CLIENTS, start=1):
            user = self._create_user(
                username=f'seed_client_company_{index}',
                email=f'seed.client.company.{index}@example.com',
                phone=f'+7999222{index:04d}',
                user_type=lookups['user_types']['client'],
                role=None,
                is_staff=False,
            )
            profile = ClientProfile(
                user=user,
                first_name='Контакт',
                last_name=f'Компания {index}',
                middle_name=None,
                client_kind_ref=lookups['client_kinds']['company'],
            )
            self._save(profile)
            details = ClientCompanyDetails(
                profile=profile,
                company_name=company_name,
                company_inn=f'3808{index:06d}',
                company_ogrn=f'1023800{index:06d}',
                company_kpp=f'38080{index:04d}',
                legal_address=f'г. {CITY_DATA["irkutsk"]["name"]}, ул. Байкальская, д. {40 + index}',
            )
            self._save(details)
            company_clients.append(profile)

        return {
            'employees': employees,
            'clients': individual_clients + company_clients,
            'individual_clients': individual_clients,
            'company_clients': company_clients,
        }

    def _seed_properties(self, employees: list[EmployeeProfile], *, force_images: bool) -> list[PropertyBundle]:
        lookups = self._lookups()
        bundles: list[PropertyBundle] = []
        city_counters = {code: 0 for code in CITY_DATA}
        materials = list(lookups['building_materials'].values())
        renovations = list(lookups['renovation_types'].values())
        bathrooms = list(lookups['bathroom_types'].values())

        for index, spec in enumerate(PROPERTY_BLUEPRINTS, start=1):
            (
                city_code,
                property_type_code,
                subtype,
                rooms_count,
                area_total,
                floor_number,
                total_floors,
                land_area,
                commercial_type_code,
                operation_code,
                status_code,
            ) = spec
            city_data = CITY_DATA[city_code]
            city_index = city_counters[city_code]
            city_counters[city_code] += 1
            city, street, house = self._ensure_address(
                city_data['name'],
                city_data['region'],
                city_data['streets'][city_index % len(city_data['streets'])],
                10 + city_index * 3 + index,
                f'{index:06d}'[-6:],
            )
            created_by = employees[index % len(employees)]
            property_obj = Property(
                title=self._property_title(property_type_code, subtype, city.name, area_total, rooms_count),
                operation_type=lookups['operation_types'][operation_code],
                status=lookups['property_statuses'][status_code],
                house=house,
                property_type_ref=lookups['property_types'][property_type_code],
                price=self._property_price(city_code, property_type_code, operation_code, area_total),
                area_total=Decimal(area_total),
                rooms_count=rooms_count,
                floor_number=floor_number,
                description=self._property_description(property_type_code, subtype, city.name),
                is_published=status_code != 'archived',
                published_at=timezone.now() - timedelta(days=index + 2),
                created_at=timezone.now() - timedelta(days=45 - index),
            )
            self._save(property_obj)
            building, _ = BuildingDetails.objects.update_or_create(
                house=house,
                defaults={
                    'year_built': 1996 + (index % 24),
                    'total_floors': total_floors,
                    'building_material': materials[index % len(materials)],
                    'elevators_count': 0 if total_floors <= 2 else 1 + index % 3,
                },
            )
            self._save(building)

            if property_type_code == 'commercial':
                details = CommercialPropertyDetails(
                    property=property_obj,
                    commercial_type=lookups['commercial_property_types'][commercial_type_code],
                    usable_area=(Decimal(area_total) * Decimal('0.92')).quantize(Decimal('0.01')),
                    ceiling_height=Decimal('3.40') if subtype != 'warehouse' else Decimal('5.80'),
                    floor_load=Decimal('750.00') if subtype == 'warehouse' else Decimal('250.00'),
                    electric_power_kw=Decimal('40.00') if subtype == 'warehouse' else Decimal('18.00'),
                    has_separate_entrance=True,
                    has_display_windows=subtype == 'retail',
                    is_first_line=subtype == 'retail',
                    parking_spaces=4 if subtype == 'warehouse' else 2,
                )
                self._save(details)
            else:
                details = PropertyDetails(
                    property=property_obj,
                    living_area=self._residential_living_area(property_type_code, area_total),
                    kitchen_area=self._kitchen_area(property_type_code, subtype, area_total),
                    ceiling_height=Decimal('2.70') if property_type_code != 'house' else Decimal('3.05'),
                    balcony_count=0 if property_type_code in {'land', 'garage', 'house'} else min(2, max(0, (index + 1) % 3)),
                    bathroom_count=1 if property_type_code in {'apartment', 'room', 'garage'} else 2,
                    bathroom_type=bathrooms[index % len(bathrooms)],
                    renovation_type=renovations[index % len(renovations)],
                    bedrooms_count=self._bedrooms_count(property_type_code, rooms_count),
                    floors_count=total_floors if property_type_code == 'house' else None,
                    land_area=Decimal(land_area) if land_area else None,
                )
                self._save(details)

            if force_images:
                PropertyPhoto.objects.filter(property=property_obj).delete()
            self._enrich_property(property_obj, city.name, street.name, house.house_number)
            bundles.append(
                PropertyBundle(
                    property=property_obj,
                    city=city,
                    employee=created_by,
                    category=property_type_code,
                    subtype=subtype,
                    operation_code=operation_code,
                    status_code=status_code,
                    commercial_type_code=commercial_type_code,
                    land_area=Decimal(land_area) if land_area else None,
                    is_commercial_like=property_type_code == 'commercial' or subtype == 'commercial_land',
                )
            )
        return bundles

    def _seed_property_owners(
        self,
        properties: list[PropertyBundle],
        individual_clients: list[ClientProfile],
        company_clients: list[ClientProfile],
    ) -> None:
        single_shares = [(profile, Decimal('100.00')) for profile in (individual_clients + company_clients + individual_clients[:3])]
        share_patterns = [
            (Decimal('50.00'), Decimal('50.00')),
            (Decimal('60.00'), Decimal('40.00')),
            (Decimal('70.00'), Decimal('30.00')),
        ]
        double_residential = [0, 2, 5, 6, 9, 11, 14, 16, 18]
        double_commercial = [22, 24, 25]
        double_indices = set(double_residential + double_commercial)
        residential_queue = individual_clients + individual_clients[:9]
        company_queue = company_clients + company_clients[:3]
        residential_index = 0
        company_index = 0

        for index, bundle in enumerate(properties):
            if index in double_indices:
                shares = share_patterns[index % len(share_patterns)]
                if bundle.is_commercial_like:
                    owners = [
                        company_queue[company_index % len(company_queue)],
                        (individual_clients + company_clients)[(company_index + 1) % (len(individual_clients) + len(company_clients))],
                    ]
                    company_index += 1
                else:
                    owners = [
                        residential_queue[residential_index % len(residential_queue)],
                        residential_queue[(residential_index + 1) % len(residential_queue)],
                    ]
                    residential_index += 2
                for owner, share in zip(owners, shares):
                    self._save(PropertyOwner(property=bundle.property, client_profile=owner, ownership_share=share))
                continue

            owner = single_shares.pop(0)[0]
            if bundle.is_commercial_like and owner.client_kind != 'company':
                owner = company_clients[company_index % len(company_clients)]
                company_index += 1
            if not bundle.is_commercial_like and owner.client_kind != 'individual':
                owner = individual_clients[residential_index % len(individual_clients)]
                residential_index += 1
            self._save(PropertyOwner(property=bundle.property, client_profile=owner, ownership_share=DECIMAL_100))

    def _seed_requests(
        self,
        properties: list[PropertyBundle],
        clients: list[ClientProfile],
        employees: list[EmployeeProfile],
    ) -> list[Request]:
        lookups = self._lookups()
        by_type = self._property_index(properties)
        request_specs = [
            ('sale', 'apartment', 1, 'irkutsk', 'completed'),
            ('sale', 'apartment', 2, 'moscow', 'completed'),
            ('sale', 'house', 4, 'irkutsk', 'completed'),
            ('rent', 'apartment', 2, 'moscow', 'completed'),
            ('rent', 'commercial', None, 'moscow', 'completed'),
            ('sale', 'apartment', 3, 'khabarovsk', 'processing'),
            ('sale', 'apartment', 4, 'irkutsk', 'processing'),
            ('sale', 'apartment', 0, 'chita', 'processing'),
            ('sale', 'apartment', 2, 'moscow', 'open'),
            ('sale', 'house', 5, 'khabarovsk', 'processing'),
            ('sale', 'house', 4, 'moscow', 'open'),
            ('rent', 'apartment', 1, 'khabarovsk', 'processing'),
            ('rent', 'apartment', 4, 'irkutsk', 'open'),
            ('rent', 'commercial', None, 'irkutsk', 'cancelled'),
            ('sale', 'land', None, 'irkutsk', 'lost'),
        ]
        requests: list[Request] = []
        for index, (operation_code, property_type_code, rooms_count, city_code, status_code) in enumerate(request_specs):
            pool = by_type[(operation_code, property_type_code)]
            bundle = pool[index % len(pool)]
            client = clients[index % len(clients)]
            employee = employees[index % len(employees)]
            status = lookups['request_statuses'][status_code]
            created_at = timezone.now() - timedelta(days=24 - index)
            request_obj = Request(
                client_profile=client,
                employee_profile=employee,
                property=bundle.property if index < 10 or property_type_code in {'commercial', 'land'} else None,
                operation_type=lookups['operation_types'][operation_code],
                status=status,
                property_type=lookups['property_types'][property_type_code],
                preferred_city=City.objects.get(
                    name=CITY_DATA[city_code]['name'],
                    region=CITY_DATA[city_code]['region'],
                ),
                min_price=(bundle.property.price * Decimal('0.90')).quantize(Decimal('0.01')),
                max_price=(bundle.property.price * Decimal('1.10')).quantize(Decimal('0.01')),
                min_area=(bundle.property.area_total * Decimal('0.85')).quantize(Decimal('0.01')),
                max_area=(bundle.property.area_total * Decimal('1.15')).quantize(Decimal('0.01')),
                rooms_count=rooms_count,
                address_preferences=f'Предпочтительно {bundle.city.name}, рядом с транспортом и без долгого ремонта.',
                description=self._request_description(operation_code, property_type_code, bundle.subtype),
                created_at=created_at,
                closed_at=created_at + timedelta(days=9) if status_code in Request.TERMINAL_STATUS_CODES else None,
            )
            self._save(request_obj)
            requests.append(request_obj)
        return requests

    def _seed_deals(self, requests: list[Request]) -> list[Deal]:
        lookups = self._lookups()
        completed_requests = [request for request in requests if request.status_code == 'completed'][:5]
        deals: list[Deal] = []
        for index, request_obj in enumerate(completed_requests, start=1):
            property_obj = request_obj.property or Property.objects.filter(
                operation_type=request_obj.operation_type,
                property_type_ref=request_obj.property_type,
            ).first()
            agent_user = request_obj.employee_profile.user if request_obj.employee_profile_id else None
            deal = Deal(
                deal_number=f'SEED-2026-{index:04d}',
                property=property_obj,
                client=request_obj.client_profile.user,
                agent=agent_user,
                employee_profile=request_obj.employee_profile,
                operation_type=request_obj.operation_type,
                status=lookups['deal_statuses']['completed'],
                request=request_obj,
                price_final=(property_obj.price * Decimal('0.98')).quantize(Decimal('0.01')),
                commission_percent=Decimal('3.00') if request_obj.operation_type.code == 'sale' else Decimal('12.00'),
                deal_date=timezone.localdate() - timedelta(days=10 - index),
                contract_status_ref=lookups['contract_statuses']['signed'],
                contract_file=f'deals/contracts/seed/contract_{index}.pdf',
                notes=f'Сделка создана сидером. {SEED_MARKER}',
            )
            self._save(deal)
            deals.append(deal)
        return deals

    def _seed_tasks(
        self,
        properties: list[PropertyBundle],
        requests: list[Request],
        deals: list[Deal],
        clients: list[ClientProfile],
        employees: list[EmployeeProfile],
    ) -> list[Task]:
        lookups = self._lookups()
        task_types = (
            ['call_client'] * 5
            + ['show_property'] * 4
            + ['property_search'] * 4
            + ['prepare_docs'] * 4
            + ['negotiate'] * 2
            + ['other']
        )
        status_codes = ['new', 'in_progress', 'waiting', 'done', 'cancelled'] * 4
        priorities = ['medium', 'high', 'medium', 'urgent', 'low'] * 4
        tasks: list[Task] = []
        for index, task_type_code in enumerate(task_types):
            request_obj = requests[index % len(requests)]
            property_obj = properties[index % len(properties)].property
            deal_obj = deals[index % len(deals)] if index % 4 == 0 else None
            status_code = status_codes[index]
            task = Task(
                title=self._task_title(task_type_code, request_obj, property_obj),
                description=self._task_description(task_type_code, property_obj),
                priority_ref=lookups['task_priorities'][priorities[index]],
                task_type_ref=lookups['task_types'][task_type_code],
                status=lookups['task_statuses'][status_code],
                assignee=employees[index % len(employees)].user,
                created_by=employees[(index + 2) % len(employees)].user,
                client_profile=clients[index % len(clients)],
                property=property_obj if index % 5 != 0 else None,
                request=request_obj if index % 3 != 0 else None,
                deal=deal_obj,
                due_date=timezone.now() + timedelta(days=(index % 6) - 2, hours=2 * index),
                completed_at=timezone.now() - timedelta(days=1, hours=index) if status_code in {'done', 'cancelled'} else None,
                result=self._task_result(task_type_code, status_code),
            )
            self._save(task)
            tasks.append(task)
        return tasks

    def _validate_seed(
        self,
        users: dict[str, list],
        properties: list[PropertyBundle],
        requests: list[Request],
        tasks: list[Task],
        deals: list[Deal],
    ) -> dict[str, int]:
        user_count = User.objects.filter(username__startswith='seed_').count()
        property_count = len(properties)
        owner_count = PropertyOwner.objects.filter(property__description__contains=SEED_MARKER).count()
        request_count = len(requests)
        task_count = len(tasks)
        deal_count = len(deals)
        if user_count != 27:
            raise ValueError(f'Ожидалось 27 пользователей, получено {user_count}.')
        if property_count != 30:
            raise ValueError(f'Ожидалось 30 объектов, получено {property_count}.')
        if owner_count != 42:
            raise ValueError(f'Ожидалось 42 записи PropertyOwner, получено {owner_count}.')
        if request_count != 15 or task_count != 20 or deal_count != 5:
            raise ValueError('Нарушены контрольные количества заявок, задач или сделок.')

        for bundle in properties:
            owners = list(bundle.property.owners.select_related('client_profile__user'))
            if not owners:
                raise ValueError(f'У объекта {bundle.property.pk} нет владельцев.')
            total_share = sum(owner.ownership_share or Decimal('0.00') for owner in owners)
            if total_share != DECIMAL_100:
                raise ValueError(f'У объекта {bundle.property.pk} сумма долей равна {total_share}, ожидалось 100.')
            for owner in owners:
                if owner.client_profile.user.user_type != 'client':
                    raise ValueError('В PropertyOwner обнаружен не клиент.')

        for task in tasks:
            if task.assignee.user_type != 'employee' or task.created_by.user_type != 'employee':
                raise ValueError('В задаче обнаружен исполнитель или создатель не сотрудник.')
            if task.client_profile_id and task.client_profile.user.user_type != 'client':
                raise ValueError('В задаче обнаружен неверный client_profile.')

        for request_obj in requests:
            if request_obj.client_profile.user.user_type != 'client':
                raise ValueError('В заявке обнаружен неверный client_profile.')
            if request_obj.employee_profile_id and request_obj.employee_profile.user.user_type != 'employee':
                raise ValueError('В заявке обнаружен неверный employee_profile.')

        for deal in deals:
            if deal.client.user_type != 'client' or deal.agent.user_type != 'employee':
                raise ValueError('В сделке обнаружены неверные ссылки client/agent.')

        if len(users['employees']) != 12 or len(users['clients']) != 15:
            raise ValueError('Нарушены количества сотрудников или клиентов.')

        return {
            'users': user_count,
            'properties': property_count,
            'property_owners': owner_count,
            'requests': request_count,
            'tasks': task_count,
            'deals': deal_count,
        }

    def _create_user(self, *, username: str, email: str, phone: str, user_type, role, is_staff: bool) -> User:
        user = User(
            username=username,
            email=email,
            phone=phone,
            user_type_ref=user_type,
            role=role,
            is_staff=is_staff,
            is_active=True,
            is_email_verified=True,
            is_phone_verified=True,
        )
        user.set_password(SEED_PASSWORD)
        self._save(user)
        return user

    def _lookups(self) -> dict[str, dict[str, Any]]:
        return {
            'operation_types': {row.code: row for row in OperationType.objects.all()},
            'property_statuses': {row.code: row for row in PropertyStatus.objects.all()},
            'request_statuses': {row.code: row for row in RequestStatus.objects.all()},
            'deal_statuses': {row.code: row for row in DealStatus.objects.all()},
            'task_statuses': {row.code: row for row in TaskStatus.objects.all()},
            'user_roles': {row.code: row for row in UserRole.objects.all()},
            'property_types': {row.code: row for row in PropertyType.objects.all()},
            'task_priorities': {row.code: row for row in TaskPriority.objects.all()},
            'task_types': {row.code: row for row in TaskType.objects.all()},
            'client_kinds': {row.code: row for row in ClientKind.objects.all()},
            'contract_statuses': {row.code: row for row in ContractStatus.objects.all()},
            'user_types': {row.code: row for row in UserType.objects.all()},
            'renovation_types': {row.code: row for row in RenovationType.objects.all()},
            'bathroom_types': {row.code: row for row in BathroomType.objects.all()},
            'building_materials': {row.code: row for row in BuildingMaterial.objects.all()},
            'commercial_property_types': {row.code: row for row in CommercialPropertyType.objects.all()},
        }

    def _ensure_address(self, city_name: str, region: str, street_name: str, house_number: int, postal_code: str):
        city, _ = City.objects.get_or_create(name=city_name, region=region)
        street, _ = Street.objects.get_or_create(city=city, name=street_name, defaults={'street_type': 'ул.'})
        house, _ = House.objects.get_or_create(street=street, house_number=str(house_number), defaults={'postal_code': postal_code})
        return city, street, house

    def _property_index(self, bundles: list[PropertyBundle]) -> dict[tuple[str, str], list[PropertyBundle]]:
        result: dict[tuple[str, str], list[PropertyBundle]] = {}
        for bundle in bundles:
            result.setdefault((bundle.operation_code, bundle.category), []).append(bundle)
        return result

    def _enrich_property(self, property_obj: Property, city_name: str, street_name: str, house_number: str) -> None:
        info = TwoGisClient().search_by_address(f'{street_name}, {house_number}', city=city_name)
        if not info:
            info = self._fallback_twogis_payload(property_obj, city_name, street_name, house_number)
        lat = info.get('lat')
        lon = info.get('lon')
        if lat is not None:
            property_obj.coordinates_lat = Decimal(str(lat))
        if lon is not None:
            property_obj.coordinates_lon = Decimal(str(lon))
        description = (property_obj.description or '').strip()
        twogis_description = (info.get('description') or '').strip()
        if twogis_description and twogis_description not in description:
            property_obj.description = f'{twogis_description}\n\n{description}'.strip()
        self._save(property_obj)
        PropertyExternalSource.objects.update_or_create(
            property=property_obj,
            source_name='2gis',
            external_id=str(info.get('org_id') or f'fallback-{property_obj.pk}'),
            defaults={
                'source_object_name': info.get('name') or property_obj.title,
                'source_address': info.get('address_full') or '',
                'source_rubric': info.get('rubric_name') or '',
                'synced_at': timezone.now(),
            },
        )
        PropertyPhoto.objects.filter(property=property_obj).delete()
        for order, url in enumerate((info.get('photos') or [])[:5]):
            PropertyPhoto.objects.create(
                property=property_obj,
                url=url,
                caption='2GIS',
                order=order,
            )

    def _fallback_twogis_payload(self, property_obj: Property, city_name: str, street_name: str, house_number: str) -> dict[str, Any]:
        city_key = next(code for code, data in CITY_DATA.items() if data['name'] == city_name)
        base_lat = CITY_DATA[city_key]['lat']
        base_lon = CITY_DATA[city_key]['lon']
        lat = (base_lat + Decimal(property_obj.pk or 0) / Decimal('10000')).quantize(Decimal('0.00000001'))
        lon = (base_lon + Decimal(property_obj.pk or 0) / Decimal('12000')).quantize(Decimal('0.00000001'))
        api_key = getattr(settings, 'TWOGIS_API_KEY', '')
        marker = f'{lon},{lat}'
        base = f'center={lon},{lat}&size=600x400&markers={marker}&key={api_key}'
        return {
            'org_id': f'fallback-{property_obj.pk}',
            'name': property_obj.title,
            'address_full': f'Россия, {city_name}, ул. {street_name}, д. {house_number}',
            'rubric_name': 'Недвижимость',
            'description': f'Тестовое 2GIS-обогащение для "{property_obj.title}".',
            'lat': lat,
            'lon': lon,
            'photos': [
                f'https://static.maps.2gis.com/1.0?{base}&zoom=18',
                f'https://static.maps.2gis.com/1.0?{base}&zoom=16',
                f'https://static.maps.2gis.com/1.0?{base}&zoom=15',
            ],
        }

    def _property_title(self, property_type_code: str, subtype: str, city_name: str, area_total: str, rooms_count: int | None) -> str:
        if property_type_code == 'apartment':
            label = 'Студия' if rooms_count == 0 else f'{rooms_count}-комнатная квартира'
        elif property_type_code == 'house':
            label = {
                'private_house': 'Частный дом',
                'townhouse': 'Таунхаус',
                'duplex': 'Дуплекс',
            }[subtype]
        elif property_type_code == 'room':
            label = 'Комната в коммуналке' if subtype == 'communal_room' else 'Комната в общежитии'
        elif property_type_code == 'commercial':
            label = {
                'office': 'Офис',
                'retail': 'Торговое помещение',
                'warehouse': 'Склад',
            }[subtype]
        elif property_type_code == 'land':
            label = 'Участок ИЖС' if subtype == 'ijs_land' else 'Коммерческий участок'
        else:
            label = 'Гараж в ГСК'
        return f'{label}, {area_total} м², {city_name}'

    def _property_description(self, property_type_code: str, subtype: str, city_name: str) -> str:
        chunks = {
            'apartment': 'Формат объявления приближен к карточкам Яндекс Недвижимости: акцент на планировку, свет и транспорт.',
            'house': 'Подойдет для семьи: участок оформлен, подъезд круглый год, документы готовы к сделке.',
            'room': 'Комната с отдельным лицевым счетом, аккуратные общие зоны, понятный режим пользования.',
            'commercial': 'Помещение с понятной коммерческой функцией, хорошей видимостью и рабочим трафиком.',
            'land': 'Участок с ясным сценарием использования и базовыми вводными по подъезду и коммуникациям.',
            'garage': 'Капитальный гараж, удобный заезд, сухой бокс.',
        }
        suffix = ' Создано командой seed_data. ' + SEED_MARKER
        return f'{chunks[property_type_code]} Локация: {city_name}. {suffix}'

    def _property_price(self, city_code: str, property_type_code: str, operation_code: str, area_total: str) -> Decimal:
        area = Decimal(area_total)
        multipliers = {
            'moscow': Decimal('285000'),
            'irkutsk': Decimal('128000'),
            'khabarovsk': Decimal('119000'),
            'chita': Decimal('98000'),
        }
        if property_type_code == 'commercial':
            multipliers[city_code] *= Decimal('1.45')
        elif property_type_code == 'house':
            multipliers[city_code] *= Decimal('0.88')
        elif property_type_code == 'room':
            multipliers[city_code] *= Decimal('0.74')
        elif property_type_code == 'land':
            multipliers[city_code] *= Decimal('0.25')
        elif property_type_code == 'garage':
            multipliers[city_code] *= Decimal('0.32')
        price = area * multipliers[city_code]
        if operation_code == 'rent':
            price = price / Decimal('95')
        return price.quantize(Decimal('0.01'))

    def _residential_living_area(self, property_type_code: str, area_total: str) -> Decimal | None:
        if property_type_code in {'land', 'garage'}:
            return None
        coefficient = Decimal('0.62') if property_type_code in {'apartment', 'room'} else Decimal('0.57')
        return (Decimal(area_total) * coefficient).quantize(Decimal('0.01'))

    def _kitchen_area(self, property_type_code: str, subtype: str, area_total: str) -> Decimal | None:
        if property_type_code in {'land', 'garage', 'room'}:
            return None
        if property_type_code == 'house':
            return (Decimal(area_total) * Decimal('0.12')).quantize(Decimal('0.01'))
        if subtype == 'studio':
            return Decimal('6.50')
        return (Decimal(area_total) * Decimal('0.16')).quantize(Decimal('0.01'))

    def _bedrooms_count(self, property_type_code: str, rooms_count: int | None) -> int | None:
        if property_type_code not in {'apartment', 'house'} or rooms_count is None:
            return None
        return max(1, rooms_count - 1) if rooms_count > 1 else None

    def _request_description(self, operation_code: str, property_type_code: str, subtype: str) -> str:
        verb = 'покупку' if operation_code == 'sale' else 'аренду'
        subject = {
            'apartment': 'квартиры',
            'house': 'дома',
            'commercial': 'коммерческого помещения',
            'land': 'участка',
        }[property_type_code]
        return f'Клиент оставил заявку на {verb} {subject}. Формат: {subtype}.'

    def _task_title(self, task_type_code: str, request_obj: Request, property_obj: Property) -> str:
        mapping = {
            'call_client': f'Позвонить клиенту по заявке №{request_obj.pk}',
            'show_property': f'Организовать показ: {property_obj.title}',
            'property_search': f'Подобрать варианты по заявке №{request_obj.pk}',
            'prepare_docs': f'Подготовить документы по объекту №{property_obj.pk}',
            'negotiate': f'Провести переговоры по заявке №{request_obj.pk}',
            'other': f'Сопутствующая задача по клиенту {request_obj.client_profile.user.username}',
        }
        return mapping[task_type_code]

    def _task_description(self, task_type_code: str, property_obj: Property) -> str:
        mapping = {
            'call_client': 'Уточнить мотивацию, бюджет и сроки выхода на сделку.',
            'show_property': 'Согласовать время, подготовить маршрут и подтвердить участникам.',
            'property_search': 'Подобрать 3-5 релевантных вариантов по активной заявке.',
            'prepare_docs': f'Проверить комплект документов по объекту "{property_obj.title}".',
            'negotiate': 'Сверить коммерческие условия сторон и зафиксировать уступки.',
            'other': 'Выполнить сопутствующее действие без жесткого сценария.',
        }
        return mapping[task_type_code]

    def _task_result(self, task_type_code: str, status_code: str) -> str:
        if status_code == 'done':
            return f'Задача типа {task_type_code} закрыта с положительным результатом.'
        if status_code == 'cancelled':
            return f'Задача типа {task_type_code} отменена после изменения контекста.'
        return ''

    def _save(self, instance) -> None:
        instance.full_clean()
        instance.save()
