"""Выборка адресов и помещений из локальной выгрузки GAR/FIAS."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5
from xml.etree import ElementTree as ET

from django.conf import settings


CITY_LEVELS = {4, 5, 6}
STREET_LEVELS = {7, 8}
ADDR_OBJ_EXCLUDES = ('AS_ADDR_OBJ_PARAMS_', 'AS_ADDR_OBJ_DIVISION_')
HOUSES_EXCLUDES = ('AS_HOUSES_PARAMS_',)
APARTMENTS_EXCLUDES = ('AS_APARTMENTS_PARAMS_',)
REGION_NAMES = {
    '02': 'Республика Башкортостан',
    '16': 'Республика Татарстан',
    '24': 'Красноярский край',
    '38': 'Иркутская область',
    '50': 'Московская область',
    '66': 'Свердловская область',
    '76': 'Ярославская область',
}


@dataclass(frozen=True)
class GarAddressObject:
    object_id: int
    object_guid: UUID
    name: str
    type_name: str
    level: int


@dataclass(frozen=True)
class GarHouseCandidate:
    object_id: int
    object_guid: UUID
    house_number: str
    city: GarAddressObject
    street: GarAddressObject


@dataclass(frozen=True)
class GarApartmentCandidate:
    object_id: int
    object_guid: UUID
    house_object_id: int
    number: str


@dataclass(frozen=True)
class GarResolvedUnit:
    region_code: str
    region_name: str
    city_guid: UUID
    city_name: str
    street_guid: UUID
    street_name: str
    street_type: str
    house_guid: UUID
    house_number: str
    apartment_guid: UUID | None = None
    apartment_number: str | None = None


def _gar_root() -> Path:
    root = getattr(settings, 'GAR_ROOT', None)
    if root:
        return Path(root)
    return Path(settings.BASE_DIR).parent / 'GAR'


def _iter_xml_records(path: Path, tag_name: str):
    for _, element in ET.iterparse(path, events=('end',)):
        if element.tag != tag_name:
            continue
        yield element.attrib.copy()
        element.clear()


def _list_primary_files(
    directory: Path,
    prefix: str,
    *,
    exclude_prefixes: tuple[str, ...] = (),
) -> list[Path]:
    return sorted(
        path
        for path in directory.glob(f'{prefix}_*.XML')
        if not any(path.name.startswith(excluded) for excluded in exclude_prefixes)
    )


def _latest_file(
    directory: Path,
    prefix: str,
    *,
    exclude_prefixes: tuple[str, ...] = (),
) -> Path:
    matches = _list_primary_files(
        directory,
        prefix,
        exclude_prefixes=exclude_prefixes,
    )
    if not matches:
        raise FileNotFoundError(
            f'Не найден файл GAR по шаблону {prefix}_*.XML в {directory}.',
        )
    return matches[-1]


class GarSampler:
    """Читает ограниченную выборку адресов и помещений из GAR."""

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root) if root else _gar_root()

    def available_region_codes(self) -> list[str]:
        if not self.root.exists():
            return []
        return sorted(
            entry.name
            for entry in self.root.iterdir()
            if entry.is_dir() and entry.name.isdigit()
        )

    def suggest_region_codes(
        self,
        *,
        preferred: list[str] | None = None,
        limit: int = 5,
    ) -> list[str]:
        target_limit = max(int(limit or 0), 1)
        preferred_codes = self._normalize_region_codes(
            region_code=None,
            region_codes=preferred,
            fallback=[],
        )
        available = self.available_region_codes()
        ranked = sorted(
            (code for code in available if code not in preferred_codes),
            key=self._region_priority,
            reverse=True,
        )
        return (preferred_codes + ranked)[:target_limit]

    def sample(
        self,
        *,
        region_code: str = '38',
        region_codes: list[str] | None = None,
        limit: int = 20,
    ) -> list[GarResolvedUnit]:
        target_limit = max(int(limit or 0), 1)
        codes = self._normalize_region_codes(
            region_code=region_code,
            region_codes=region_codes,
            fallback=['38'],
        )
        existing_codes = [
            code for code in codes
            if (self.root / code).exists()
        ]
        if not existing_codes:
            raise FileNotFoundError(
                f'Каталоги регионов GAR не найдены для кодов: {", ".join(codes)}',
            )

        units: list[GarResolvedUnit] = []
        for code in existing_codes:
            remaining = target_limit - len(units)
            if remaining <= 0:
                break
            units.extend(
                self._sample_region(
                    region_code=code,
                    limit=remaining,
                ),
            )
        return units

    def _sample_region(
        self,
        *,
        region_code: str,
        limit: int,
    ) -> list[GarResolvedUnit]:
        target_limit = max(int(limit or 0), 1)
        region_dir = self.root / str(region_code)
        address_objects = self._load_address_objects(region_dir)
        hierarchy = self._load_hierarchy(region_dir)
        houses = self._load_houses(
            region_code=region_code,
            region_dir=region_dir,
            address_objects=address_objects,
            hierarchy=hierarchy,
            limit=max(target_limit * 6, 24),
        )
        if not houses:
            return []

        apartments = self._load_apartments(
            region_dir=region_dir,
            hierarchy=hierarchy,
            house_ids=set(houses.keys()),
            limit=max(target_limit * 8, 32),
        )
        return self._build_units(
            region_code=region_code,
            houses=houses,
            apartments=apartments,
            limit=target_limit,
        )

    def _load_address_objects(self, region_dir: Path) -> dict[int, GarAddressObject]:
        objects: dict[int, GarAddressObject] = {}
        path = _latest_file(
            region_dir,
            'AS_ADDR_OBJ',
            exclude_prefixes=ADDR_OBJ_EXCLUDES,
        )
        for attrs in _iter_xml_records(path, 'OBJECT'):
            if attrs.get('ISACTIVE') != '1' or attrs.get('ISACTUAL') != '1':
                continue
            object_id_raw = attrs.get('OBJECTID')
            object_guid_raw = attrs.get('OBJECTGUID')
            level_raw = attrs.get('LEVEL')
            if not object_id_raw or not object_guid_raw or not level_raw:
                continue
            try:
                object_id = int(object_id_raw)
                level = int(level_raw)
                object_guid = UUID(object_guid_raw)
            except (TypeError, ValueError):
                continue
            objects[object_id] = GarAddressObject(
                object_id=object_id,
                object_guid=object_guid,
                name=(attrs.get('NAME') or '').strip(),
                type_name=(attrs.get('TYPENAME') or '').strip(),
                level=level,
            )
        return objects

    def _load_hierarchy(self, region_dir: Path) -> dict[int, int]:
        parents: dict[int, int] = {}
        path = _latest_file(region_dir, 'AS_ADM_HIERARCHY')
        for attrs in _iter_xml_records(path, 'ITEM'):
            if attrs.get('ISACTIVE') != '1':
                continue
            object_id_raw = attrs.get('OBJECTID')
            parent_id_raw = attrs.get('PARENTOBJID')
            if not object_id_raw or not parent_id_raw:
                continue
            try:
                parents[int(object_id_raw)] = int(parent_id_raw)
            except (TypeError, ValueError):
                continue
        return parents

    def _load_houses(
        self,
        *,
        region_code: str,
        region_dir: Path,
        address_objects: dict[int, GarAddressObject],
        hierarchy: dict[int, int],
        limit: int,
    ) -> dict[int, GarHouseCandidate]:
        path = _latest_file(
            region_dir,
            'AS_HOUSES',
            exclude_prefixes=HOUSES_EXCLUDES,
        )
        candidates: dict[int, GarHouseCandidate] = {}
        region_name = REGION_NAMES.get(region_code, f'Регион {region_code}')
        fallback_city = self._build_region_fallback_city(
            region_code=region_code,
            region_name=region_name,
        )
        for attrs in _iter_xml_records(path, 'HOUSE'):
            if attrs.get('ISACTIVE') != '1' or attrs.get('ISACTUAL') != '1':
                continue
            object_id_raw = attrs.get('OBJECTID')
            object_guid_raw = attrs.get('OBJECTGUID')
            house_number = (attrs.get('HOUSENUM') or '').strip()
            if not object_id_raw or not object_guid_raw or not house_number:
                continue
            try:
                object_id = int(object_id_raw)
                object_guid = UUID(object_guid_raw)
            except (TypeError, ValueError):
                continue

            street = self._resolve_street(
                object_id=object_id,
                address_objects=address_objects,
                hierarchy=hierarchy,
            )
            if street is None:
                continue

            city = self._resolve_city(
                object_id=street.object_id,
                address_objects=address_objects,
                hierarchy=hierarchy,
            )
            if city is None:
                city = self._resolve_city(
                    object_id=object_id,
                    address_objects=address_objects,
                    hierarchy=hierarchy,
                )
            if city is None:
                city = fallback_city

            candidates[object_id] = GarHouseCandidate(
                object_id=object_id,
                object_guid=object_guid,
                house_number=house_number,
                city=city,
                street=street,
            )
            if len(candidates) >= limit:
                break
        return candidates

    def _load_apartments(
        self,
        *,
        region_dir: Path,
        hierarchy: dict[int, int],
        house_ids: set[int],
        limit: int,
    ) -> dict[int, list[GarApartmentCandidate]]:
        path = _latest_file(
            region_dir,
            'AS_APARTMENTS',
            exclude_prefixes=APARTMENTS_EXCLUDES,
        )
        apartments: dict[int, list[GarApartmentCandidate]] = defaultdict(list)
        collected = 0
        for attrs in _iter_xml_records(path, 'APARTMENT'):
            if attrs.get('ISACTIVE') != '1' or attrs.get('ISACTUAL') != '1':
                continue
            object_id_raw = attrs.get('OBJECTID')
            object_guid_raw = attrs.get('OBJECTGUID')
            number = (attrs.get('NUMBER') or '').strip()
            if not object_id_raw or not object_guid_raw or not number:
                continue
            try:
                object_id = int(object_id_raw)
                object_guid = UUID(object_guid_raw)
            except (TypeError, ValueError):
                continue

            house_object_id = hierarchy.get(object_id)
            if house_object_id not in house_ids:
                continue
            apartments[house_object_id].append(
                GarApartmentCandidate(
                    object_id=object_id,
                    object_guid=object_guid,
                    house_object_id=house_object_id,
                    number=number,
                ),
            )
            collected += 1
            if collected >= limit:
                break
        return apartments

    def _build_units(
        self,
        *,
        region_code: str,
        houses: dict[int, GarHouseCandidate],
        apartments: dict[int, list[GarApartmentCandidate]],
        limit: int,
    ) -> list[GarResolvedUnit]:
        units: list[GarResolvedUnit] = []
        region_name = REGION_NAMES.get(region_code, f'Регион {region_code}')
        ordered_houses = sorted(
            houses.values(),
            key=lambda item: (
                item.city.name.lower(),
                item.street.name.lower(),
                item.house_number.lower(),
            ),
        )
        for house in ordered_houses:
            house_apartments = sorted(
                apartments.get(house.object_id, []),
                key=lambda item: item.number,
            )
            if house_apartments:
                for apartment in house_apartments:
                    units.append(
                        GarResolvedUnit(
                            region_code=region_code,
                            region_name=region_name,
                            city_guid=house.city.object_guid,
                            city_name=house.city.name,
                            street_guid=house.street.object_guid,
                            street_name=house.street.name,
                            street_type=house.street.type_name,
                            house_guid=house.object_guid,
                            house_number=house.house_number,
                            apartment_guid=apartment.object_guid,
                            apartment_number=apartment.number,
                        ),
                    )
                    if len(units) >= limit:
                        return units
            else:
                units.append(
                    GarResolvedUnit(
                        region_code=region_code,
                        region_name=region_name,
                        city_guid=house.city.object_guid,
                        city_name=house.city.name,
                        street_guid=house.street.object_guid,
                        street_name=house.street.name,
                        street_type=house.street.type_name,
                        house_guid=house.object_guid,
                        house_number=house.house_number,
                    ),
                )
                if len(units) >= limit:
                    return units
        return units

    @staticmethod
    def _resolve_street(
        *,
        object_id: int,
        address_objects: dict[int, GarAddressObject],
        hierarchy: dict[int, int],
    ) -> GarAddressObject | None:
        current = hierarchy.get(object_id)
        while current:
            candidate = address_objects.get(current)
            if candidate and candidate.level in STREET_LEVELS:
                return candidate
            current = hierarchy.get(current)
        return None

    @staticmethod
    def _resolve_city(
        *,
        object_id: int,
        address_objects: dict[int, GarAddressObject],
        hierarchy: dict[int, int],
    ) -> GarAddressObject | None:
        current = hierarchy.get(object_id)
        fallback: GarAddressObject | None = None
        while current:
            candidate = address_objects.get(current)
            if candidate:
                if candidate.level in CITY_LEVELS:
                    return candidate
                if fallback is None and 2 <= candidate.level <= 6:
                    fallback = candidate
            current = hierarchy.get(current)
        return fallback

    def _region_priority(self, region_code: str) -> tuple[int, str]:
        region_dir = self.root / region_code
        if not region_dir.exists():
            return (0, region_code)
        try:
            primary = _latest_file(
                region_dir,
                'AS_ADDR_OBJ',
                exclude_prefixes=ADDR_OBJ_EXCLUDES,
            )
        except FileNotFoundError:
            return (0, region_code)
        return (primary.stat().st_size, region_code)

    @staticmethod
    def _build_region_fallback_city(
        *,
        region_code: str,
        region_name: str,
    ) -> GarAddressObject:
        return GarAddressObject(
            object_id=0,
            object_guid=uuid5(NAMESPACE_URL, f'gar-fallback-city:{region_code}'),
            name=f'Населённый пункт ({region_name})',
            type_name='г',
            level=6,
        )

    @staticmethod
    def _normalize_region_codes(
        *,
        region_code: str | None = '38',
        region_codes: list[str] | None = None,
        fallback: list[str] | None = None,
    ) -> list[str]:
        raw_items = region_codes if region_codes is not None else [region_code]
        normalized: list[str] = []
        seen: set[str] = set()
        for item in raw_items:
            for code in str(item or '').split(','):
                value = code.strip()
                if not value or value in seen:
                    continue
                seen.add(value)
                normalized.append(value)
        return normalized or list(fallback or [])
