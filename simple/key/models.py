"""ORM-РјРѕРґРµР»Рё РїСЂРёР»РѕР¶РµРЅРёСЏ ``key`` (3NF-РІРµСЂСЃРёСЏ)."""
from decimal import Decimal

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models, transaction
from django.utils import timezone

from .storage import database_backup_storage

# РџРѕР»Рµ ``Task.property`` РїРµСЂРµРєСЂС‹РІР°РµС‚ builtins.property.
_property = property

phone_validator = RegexValidator(
    regex=r'^\+7\d{10}$',
    message='РўРµР»РµС„РѕРЅ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ СЂРѕСЃСЃРёР№СЃРєРёРј РЅРѕРјРµСЂРѕРј РІ С„РѕСЂРјР°С‚Рµ +7XXXXXXXXXX.',
)
passport_series_validator = RegexValidator(
    regex=r'^\d{4}$',
    message='РЎРµСЂРёСЏ РїР°СЃРїРѕСЂС‚Р° РґРѕР»Р¶РЅР° СЃРѕСЃС‚РѕСЏС‚СЊ РёР· 4 С†РёС„СЂ.',
)
passport_number_validator = RegexValidator(
    regex=r'^\d{6}$',
    message='РќРѕРјРµСЂ РїР°СЃРїРѕСЂС‚Р° РґРѕР»Р¶РµРЅ СЃРѕСЃС‚РѕСЏС‚СЊ РёР· 6 С†РёС„СЂ.',
)
passport_code_validator = RegexValidator(
    regex=r'^\d{3}-\d{3}$',
    message='РљРѕРґ РїРѕРґСЂР°Р·РґРµР»РµРЅРёСЏ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ РІ С„РѕСЂРјР°С‚Рµ 000-000.',
)
company_inn_validator = RegexValidator(
    regex=r'^\d{10}$',
    message='РРќРќ СЋСЂРёРґРёС‡РµСЃРєРѕРіРѕ Р»РёС†Р° РґРѕР»Р¶РµРЅ СЃРѕСЃС‚РѕСЏС‚СЊ РёР· 10 С†РёС„СЂ.',
)
company_ogrn_validator = RegexValidator(
    regex=r'^\d{13}$',
    message='РћР“Р Рќ РґРѕР»Р¶РµРЅ СЃРѕСЃС‚РѕСЏС‚СЊ РёР· 13 С†РёС„СЂ.',
)
company_kpp_validator = RegexValidator(
    regex=r'^\d{9}$',
    message='РљРџРџ РґРѕР»Р¶РµРЅ СЃРѕСЃС‚РѕСЏС‚СЊ РёР· 9 С†РёС„СЂ.',
)
cadastral_number_validator = RegexValidator(
    regex=r'^\d{2}:\d{2}:\d{6,}:\d+$',
    message='РќРµРІРµСЂРЅС‹Р№ С„РѕСЂРјР°С‚ РєР°РґР°СЃС‚СЂРѕРІРѕРіРѕ РЅРѕРјРµСЂР°.',
)


# =====================================================
# 1. Р‘РђР—РћР’Р«Р• РљР›РђРЎРЎР« Р РЈРўРР›РРўР«
# =====================================================

LOOKUP_NAME_DEFAULTS = {
    'PropertyType': {
        'apartment': 'РљРІР°СЂС‚РёСЂР°',
        'house': 'Р”РѕРј',
        'commercial': 'РљРѕРјРјРµСЂС‡РµСЃРєР°СЏ РЅРµРґРІРёР¶РёРјРѕСЃС‚СЊ',
        'land': 'Р—РµРјРµР»СЊРЅС‹Р№ СѓС‡Р°СЃС‚РѕРє',
        'garage': 'Р“Р°СЂР°Р¶',
        'room': 'РљРѕРјРЅР°С‚Р°',
    },
    'TaskPriority': {
        'low': 'РќРёР·РєРёР№',
        'normal': 'РћР±С‹С‡РЅС‹Р№',
        'high': 'Р’С‹СЃРѕРєРёР№',
    },
    'TaskType': {
        'contact_client': 'РЎРІСЏР·Р°С‚СЊСЃСЏ СЃ РєР»РёРµРЅС‚РѕРј',
        'property_search': 'РџРѕРґР±РѕСЂ РѕР±СЉРµРєС‚РѕРІ',
        'showing': 'РџРѕРєР°Р· РѕР±СЉРµРєС‚Р°',
        'documents': 'РџРѕРґРіРѕС‚РѕРІРєР° РґРѕРєСѓРјРµРЅС‚РѕРІ',
        'call': 'Р—РІРѕРЅРѕРє',
        'other': 'РџСЂРѕС‡РµРµ',
    },
    'ClientKind': {
        'individual': 'Р¤РёР·РёС‡РµСЃРєРѕРµ Р»РёС†Рѕ',
        'company': 'Р®СЂРёРґРёС‡РµСЃРєРѕРµ Р»РёС†Рѕ',
    },
    'ContactMethod': {
        'phone': 'РўРµР»РµС„РѕРЅ',
        'email': 'Email',
        'telegram': 'Telegram',
        'whatsapp': 'WhatsApp',
    },
    'ContractStatus': {
        'not_requested': 'РќРµ Р·Р°РїСЂРѕС€РµРЅ',
        'pending': 'Р’ РѕС‡РµСЂРµРґРё',
        'processing': 'Р¤РѕСЂРјРёСЂСѓРµС‚СЃСЏ',
        'ready': 'Р“РѕС‚РѕРІ',
        'failed': 'РћС€РёР±РєР°',
    },
    'UserType': {
        'employee': 'РЎРѕС‚СЂСѓРґРЅРёРє',
        'client': 'РљР»РёРµРЅС‚',
    },
}


def _lookup_default_name(model_class, code: str) -> str:
    return LOOKUP_NAME_DEFAULTS.get(model_class.__name__, {}).get(code, code)


def _lookup_choices(model_name: str, codes: tuple[str, ...]) -> list[tuple[str, str]]:
    defaults = LOOKUP_NAME_DEFAULTS.get(model_name, {})
    return [(code, defaults.get(code, code)) for code in codes]


def _resolve_lookup_instance(model_class, value):
    if value in (None, ''):
        return None
    if isinstance(value, model_class):
        return value
    if isinstance(value, int):
        return model_class.objects.filter(pk=value).first()
    code = str(value).strip()
    if not code:
        return None
    instance = model_class.objects.filter(code=code).first()
    if instance is not None:
        return instance
    return model_class.objects.create(
        code=code,
        name=_lookup_default_name(model_class, code),
    )


def _resolve_user_profile(value, profile_attr: str):
    """РќРѕСЂРјР°Р»РёР·СѓРµС‚ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ РёР»Рё id Рє СЃРІСЏР·Р°РЅРЅРѕРјСѓ РїСЂРѕС„РёР»СЋ."""
    if value in (None, ''):
        return None

    profile_model_name = 'ClientProfile' if profile_attr == 'client_profile' else 'EmployeeProfile'
    profile_model = globals().get(profile_model_name)
    if profile_model is not None and isinstance(value, profile_model):
        return value

    if isinstance(value, User):
        try:
            return getattr(value, profile_attr)
        except Exception:
            return None

    if hasattr(value, profile_attr):
        try:
            profile = getattr(value, profile_attr)
        except Exception:
            profile = None
        if profile is not None:
            return profile

    try:
        user_id = int(getattr(value, 'pk', value))
    except (TypeError, ValueError):
        return None

    user = User.objects.select_related(profile_attr).filter(pk=user_id).first()
    if user is None:
        return None
    try:
        return getattr(user, profile_attr)
    except Exception:
        return None


def _rewrite_legacy_update_fields(instance, kwargs):
    update_fields = kwargs.get('update_fields')
    if not update_fields:
        return

    alias_map = getattr(instance, 'QUERY_ALIASES', {})
    concrete_names = {field.name for field in instance._meta.concrete_fields}
    concrete_names.update(field.attname for field in instance._meta.concrete_fields)

    rewritten = []
    for field_name in update_fields:
        if field_name in concrete_names:
            rewritten.append(field_name)
            continue
        target = alias_map.get(field_name, field_name)
        concrete_name = target.split('__', 1)[0]
        rewritten.append(concrete_name if concrete_name in concrete_names else field_name)

    kwargs['update_fields'] = list(dict.fromkeys(rewritten))


class CodeNameLookup(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name='РљРѕРґ')
    name = models.CharField(max_length=100, verbose_name='РќР°Р·РІР°РЅРёРµ')

    class Meta:
        abstract = True
        ordering = ['name']

    def __str__(self):
        return self.name

    def __eq__(self, other):
        if isinstance(other, str):
            return self.code == other
        return super().__eq__(other)

    def __hash__(self):
        return hash((self.__class__, self.pk, self.code))


class AliasQuerySet(models.QuerySet):
    def _alias_map(self):
        return getattr(self.model, 'QUERY_ALIASES', {})

    def _rewrite_key(self, key: str) -> str:
        alias_map = self._alias_map()
        for alias, target in sorted(alias_map.items(), key=lambda item: len(item[0]), reverse=True):
            if key == alias:
                return target
            if key.startswith(f'{alias}__'):
                return f'{target}{key[len(alias):]}'
        return key

    def _rewrite_q(self, node):
        if not isinstance(node, models.Q):
            return node
        rewritten_children = []
        for child in node.children:
            if isinstance(child, tuple):
                key, value = child
                rewritten_children.append((self._rewrite_key(key), value))
            else:
                rewritten_children.append(self._rewrite_q(child))
        clone = models.Q()
        clone.connector = node.connector
        clone.negated = node.negated
        clone.children = rewritten_children
        return clone

    def _rewrite_kwargs(self, kwargs):
        return {self._rewrite_key(key): value for key, value in kwargs.items()}

    def _rewrite_update_kwargs(self, kwargs):
        rewritten = {}
        alias_map = self._alias_map()
        for key, value in kwargs.items():
            target = alias_map.get(key)
            if target is None:
                rewritten[key] = value
                continue

            if '__' not in target:
                rewritten[target] = value
                continue

            field_name, lookup = target.split('__', 1)
            try:
                field = self.model._meta.get_field(field_name)
            except Exception:
                rewritten[field_name] = value
                continue

            if lookup == 'code' and getattr(field, 'remote_field', None):
                related_model = field.remote_field.model
                resolved = _resolve_lookup_instance(related_model, value)
                rewritten[field.attname] = getattr(resolved, 'pk', None)
                continue

            rewritten[field_name] = value
        return rewritten

    def filter(self, *args, **kwargs):
        rewritten_args = tuple(self._rewrite_q(arg) for arg in args)
        return super().filter(*rewritten_args, **self._rewrite_kwargs(kwargs))

    def exclude(self, *args, **kwargs):
        rewritten_args = tuple(self._rewrite_q(arg) for arg in args)
        return super().exclude(*rewritten_args, **self._rewrite_kwargs(kwargs))

    def get(self, *args, **kwargs):
        rewritten_args = tuple(self._rewrite_q(arg) for arg in args)
        return super().get(*rewritten_args, **self._rewrite_kwargs(kwargs))

    def order_by(self, *field_names):
        rewritten = []
        for field_name in field_names:
            prefix = '-' if field_name.startswith('-') else ''
            raw = field_name[1:] if prefix else field_name
            rewritten.append(prefix + self._rewrite_key(raw))
        return super().order_by(*rewritten)

    def select_related(self, *fields):
        return super().select_related(*(self._rewrite_key(field) for field in fields))

    def update(self, **kwargs):
        alias_map = self._alias_map()
        direct_kwargs = {}
        row_level_updates = []

        for key, value in kwargs.items():
            target = alias_map.get(key)
            if target is None:
                direct_kwargs[key] = value
                continue

            if '__' not in target:
                direct_kwargs[target] = value
                continue

            field_name, lookup = target.split('__', 1)
            try:
                field = self.model._meta.get_field(field_name)
            except Exception:
                direct_kwargs[field_name] = value
                continue

            if lookup == 'code' and getattr(field, 'remote_field', None):
                related_model = field.remote_field.model
                resolved = _resolve_lookup_instance(related_model, value)
                direct_kwargs[field.attname] = getattr(resolved, 'pk', None)
                continue

            row_level_updates.append((key, value))

        affected = self.count()
        if direct_kwargs:
            super().update(**direct_kwargs)
        if row_level_updates:
            for obj in self:
                for key, value in row_level_updates:
                    setattr(obj, key, value)
                obj.save()
        return affected


class AliasManager(models.Manager):
    def get_queryset(self):
        return AliasQuerySet(self.model, using=self._db, hints=self._hints)


# =====================================================
# 2. РЎРџР РђР’РћР§РќРРљР (LOOKUPS)
# =====================================================

class OperationType(models.Model):
    """РўРёРї РѕРїРµСЂР°С†РёРё СЃ РЅРµРґРІРёР¶РёРјРѕСЃС‚СЊСЋ (РїСЂРѕРґР°Р¶Р° / Р°СЂРµРЅРґР°)."""
    code = models.CharField(max_length=10, unique=True, verbose_name='РљРѕРґ')
    name = models.CharField(max_length=50, verbose_name='РќР°Р·РІР°РЅРёРµ')

    class Meta:
        db_table = 'operation_types'
        verbose_name = 'РўРёРї РѕРїРµСЂР°С†РёРё'
        verbose_name_plural = 'РўРёРїС‹ РѕРїРµСЂР°С†РёР№'

    def __str__(self):
        return self.name


class PropertyStatus(models.Model):
    """РЎС‚Р°С‚СѓСЃ РѕР±СЉРµРєС‚Р° РЅРµРґРІРёР¶РёРјРѕСЃС‚Рё."""
    code = models.CharField(max_length=10, unique=True, verbose_name='РљРѕРґ')
    name = models.CharField(max_length=50, verbose_name='РќР°Р·РІР°РЅРёРµ')

    class Meta:
        db_table = 'property_statuses'
        verbose_name = 'РЎС‚Р°С‚СѓСЃ РѕР±СЉРµРєС‚Р°'
        verbose_name_plural = 'РЎС‚Р°С‚СѓСЃС‹ РѕР±СЉРµРєС‚РѕРІ'

    def __str__(self):
        return self.name


class RequestStatus(models.Model):
    """РЎС‚Р°С‚СѓСЃ Р·Р°СЏРІРєРё РєР»РёРµРЅС‚Р°."""
    code = models.CharField(max_length=15, unique=True, verbose_name='РљРѕРґ')
    name = models.CharField(max_length=50, verbose_name='РќР°Р·РІР°РЅРёРµ')

    class Meta:
        db_table = 'request_statuses'
        verbose_name = 'РЎС‚Р°С‚СѓСЃ Р·Р°СЏРІРєРё'
        verbose_name_plural = 'РЎС‚Р°С‚СѓСЃС‹ Р·Р°СЏРІРѕРє'

    def __str__(self):
        return self.name


class DealStatus(models.Model):
    """РЎС‚Р°С‚СѓСЃ СЃРґРµР»РєРё вЂ” СЃС‚Р°РґРёСЏ РІРѕСЂРѕРЅРєРё РїСЂРѕРґР°Р¶."""
    code = models.CharField(max_length=20, unique=True, verbose_name='РљРѕРґ')
    name = models.CharField(max_length=50, verbose_name='РќР°Р·РІР°РЅРёРµ')
    order = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0)], verbose_name='РџРѕСЂСЏРґРѕРє')

    class Meta:
        db_table = 'deal_statuses'
        verbose_name = 'РЎС‚Р°С‚СѓСЃ СЃРґРµР»РєРё'
        verbose_name_plural = 'РЎС‚Р°С‚СѓСЃС‹ СЃРґРµР»РѕРє'
        ordering = ['order']

    def __str__(self):
        return self.name


class TaskStatus(models.Model):
    """РЎС‚Р°С‚СѓСЃ Р·Р°РґР°С‡Рё СЃРѕС‚СЂСѓРґРЅРёРєР°."""
    code = models.CharField(max_length=20, unique=True, verbose_name='РљРѕРґ')
    name = models.CharField(max_length=50, verbose_name='РќР°Р·РІР°РЅРёРµ')
    order = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0)], verbose_name='РџРѕСЂСЏРґРѕРє')

    class Meta:
        db_table = 'task_statuses'
        verbose_name = 'РЎС‚Р°С‚СѓСЃ Р·Р°РґР°С‡Рё'
        verbose_name_plural = 'РЎС‚Р°С‚СѓСЃС‹ Р·Р°РґР°С‡'
        ordering = ['order']

    def __str__(self):
        return self.name


class PropertyType(CodeNameLookup):
    class Meta(CodeNameLookup.Meta):
        db_table = 'property_types'
        verbose_name = 'РўРёРї РїРѕРјРµС‰РµРЅРёСЏ'
        verbose_name_plural = 'РўРёРїС‹ РїРѕРјРµС‰РµРЅРёР№'


class TaskPriority(CodeNameLookup):
    class Meta(CodeNameLookup.Meta):
        db_table = 'task_priorities'
        verbose_name = 'РџСЂРёРѕСЂРёС‚РµС‚ Р·Р°РґР°С‡Рё'
        verbose_name_plural = 'РџСЂРёРѕСЂРёС‚РµС‚С‹ Р·Р°РґР°С‡'


class TaskType(CodeNameLookup):
    class Meta(CodeNameLookup.Meta):
        db_table = 'task_types'
        verbose_name = 'РўРёРї Р·Р°РґР°С‡Рё'
        verbose_name_plural = 'РўРёРїС‹ Р·Р°РґР°С‡'


class ClientKind(CodeNameLookup):
    class Meta(CodeNameLookup.Meta):
        db_table = 'client_kinds'
        verbose_name = 'Р’РёРґ РєР»РёРµРЅС‚Р°'
        verbose_name_plural = 'Р’РёРґС‹ РєР»РёРµРЅС‚РѕРІ'


class ContactMethod(CodeNameLookup):
    class Meta(CodeNameLookup.Meta):
        db_table = 'contact_methods'
        verbose_name = 'РЎРїРѕСЃРѕР± СЃРІСЏР·Рё'
        verbose_name_plural = 'РЎРїРѕСЃРѕР±С‹ СЃРІСЏР·Рё'


class ContractStatus(CodeNameLookup):
    class Meta(CodeNameLookup.Meta):
        db_table = 'contract_statuses'
        verbose_name = 'РЎС‚Р°С‚СѓСЃ РґРѕРіРѕРІРѕСЂР°'
        verbose_name_plural = 'РЎС‚Р°С‚СѓСЃС‹ РґРѕРіРѕРІРѕСЂРѕРІ'


class UserType(CodeNameLookup):
    class Meta(CodeNameLookup.Meta):
        db_table = 'user_types'
        verbose_name = 'РўРёРї РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ'
        verbose_name_plural = 'РўРёРїС‹ РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№'


class RenovationType(CodeNameLookup):
    """РўРёРї СЂРµРјРѕРЅС‚Р°."""
    class Meta(CodeNameLookup.Meta):
        db_table = 'renovation_types'
        verbose_name = 'РўРёРї СЂРµРјРѕРЅС‚Р°'
        verbose_name_plural = 'РўРёРїС‹ СЂРµРјРѕРЅС‚РѕРІ'


class BathroomType(CodeNameLookup):
    """РўРёРї СЃР°РЅСѓР·Р»Р° (СЃРѕРІРјРµС‰С‘РЅРЅС‹Р№/СЂР°Р·РґРµР»СЊРЅС‹Р№)."""
    class Meta(CodeNameLookup.Meta):
        db_table = 'bathroom_types'
        verbose_name = 'РўРёРї СЃР°РЅСѓР·Р»Р°'
        verbose_name_plural = 'РўРёРїС‹ СЃР°РЅСѓР·Р»РѕРІ'


class BuildingMaterial(CodeNameLookup):
    """РњР°С‚РµСЂРёР°Р» СЃС‚РµРЅ."""
    class Meta(CodeNameLookup.Meta):
        db_table = 'building_materials'
        verbose_name = 'РњР°С‚РµСЂРёР°Р» СЃС‚РµРЅ'
        verbose_name_plural = 'РњР°С‚РµСЂРёР°Р»С‹ СЃС‚РµРЅ'


class CommercialPropertyType(CodeNameLookup):
    """РўРёРї РєРѕРјРјРµСЂС‡РµСЃРєРѕР№ РЅРµРґРІРёР¶РёРјРѕСЃС‚Рё."""
    class Meta(CodeNameLookup.Meta):
        db_table = 'commercial_property_types'
        verbose_name = 'РўРёРї РєРѕРјРјРµСЂС‡РµСЃРєРѕР№ РЅРµРґРІРёР¶РёРјРѕСЃС‚Рё'
        verbose_name_plural = 'РўРёРїС‹ РєРѕРјРјРµСЂС‡РµСЃРєРѕР№ РЅРµРґРІРёР¶РёРјРѕСЃС‚Рё'


class Amenity(CodeNameLookup):
    """РЈРґРѕР±СЃС‚РІР°/РѕСЃРѕР±РµРЅРЅРѕСЃС‚Рё РѕР±СЉРµРєС‚Р°."""
    class Meta(CodeNameLookup.Meta):
        db_table = 'amenities'
        verbose_name = 'РЈРґРѕР±СЃС‚РІРѕ'
        verbose_name_plural = 'РЈРґРѕР±СЃС‚РІР°'


class AuditEntityType(CodeNameLookup):
    """РўРёРї СЃСѓС‰РЅРѕСЃС‚Рё РґР»СЏ Р°СѓРґРёС‚Р°."""
    class Meta(CodeNameLookup.Meta):
        db_table = 'audit_entity_types'
        verbose_name = 'РўРёРї СЃСѓС‰РЅРѕСЃС‚Рё Р°СѓРґРёС‚Р°'
        verbose_name_plural = 'РўРёРїС‹ СЃСѓС‰РЅРѕСЃС‚РµР№ Р°СѓРґРёС‚Р°'


class AuditAction(CodeNameLookup):
    """Р”РµР№СЃС‚РІРёРµ РґР»СЏ Р°СѓРґРёС‚Р°."""
    class Meta(CodeNameLookup.Meta):
        db_table = 'audit_actions'
        verbose_name = 'Р”РµР№СЃС‚РІРёРµ Р°СѓРґРёС‚Р°'
        verbose_name_plural = 'Р”РµР№СЃС‚РІРёСЏ Р°СѓРґРёС‚Р°'


class RequestMatchStatus(CodeNameLookup):
    """РЎС‚Р°С‚СѓСЃ СЃРѕРѕС‚РІРµС‚СЃС‚РІРёСЏ Р·Р°СЏРІРєР°-РѕР±СЉРµРєС‚."""
    class Meta(CodeNameLookup.Meta):
        db_table = 'request_match_statuses'
        verbose_name = 'РЎС‚Р°С‚СѓСЃ СЃРѕРѕС‚РІРµС‚СЃС‚РІРёСЏ'
        verbose_name_plural = 'РЎС‚Р°С‚СѓСЃС‹ СЃРѕРѕС‚РІРµС‚СЃС‚РІРёР№'


class DocumentType(CodeNameLookup):
    """РўРёРї РґРѕРєСѓРјРµРЅС‚Р°."""
    class Meta(CodeNameLookup.Meta):
        db_table = 'document_types'
        verbose_name = 'РўРёРї РґРѕРєСѓРјРµРЅС‚Р°'
        verbose_name_plural = 'РўРёРїС‹ РґРѕРєСѓРјРµРЅС‚РѕРІ'


class DealParticipantRole(CodeNameLookup):
    """Р РѕР»СЊ СѓС‡Р°СЃС‚РЅРёРєР° СЃРґРµР»РєРё."""
    class Meta(CodeNameLookup.Meta):
        db_table = 'deal_participant_roles'
        verbose_name = 'Р РѕР»СЊ СѓС‡Р°СЃС‚РЅРёРєР° СЃРґРµР»РєРё'
        verbose_name_plural = 'Р РѕР»Рё СѓС‡Р°СЃС‚РЅРёРєРѕРІ СЃРґРµР»РѕРє'


class ViewingStatus(CodeNameLookup):
    """РЎС‚Р°С‚СѓСЃ РїСЂРѕСЃРјРѕС‚СЂР° РѕР±СЉРµРєС‚Р°."""
    class Meta(CodeNameLookup.Meta):
        db_table = 'viewing_statuses'
        verbose_name = 'РЎС‚Р°С‚СѓСЃ РїСЂРѕСЃРјРѕС‚СЂР°'
        verbose_name_plural = 'РЎС‚Р°С‚СѓСЃС‹ РїСЂРѕСЃРјРѕС‚СЂРѕРІ'


class UserRole(models.Model):
    """Р РѕР»СЊ СЃРѕС‚СЂСѓРґРЅРёРєР° РІ СЃРёСЃС‚РµРјРµ (Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂ / РјРµРЅРµРґР¶РµСЂ / Р°РіРµРЅС‚)."""
    DEFAULT_MAX_ACTIVE_TASKS = 2
    DEFAULT_MAX_IN_PROGRESS_TASKS = 1
    DEFAULT_MAX_ACTIVE_REQUESTS = 2

    code = models.CharField(max_length=20, unique=True, verbose_name='РљРѕРґ')
    name = models.CharField(max_length=50, verbose_name='РќР°Р·РІР°РЅРёРµ')
    description = models.TextField(blank=True, null=True, verbose_name='РћРїРёСЃР°РЅРёРµ')

    def __init__(self, *args, **kwargs):
        self._max_active_tasks = self._coerce_limit(
            kwargs.pop('max_active_tasks', self.DEFAULT_MAX_ACTIVE_TASKS),
            self.DEFAULT_MAX_ACTIVE_TASKS,
        )
        self._max_in_progress_tasks = self._coerce_limit(
            kwargs.pop('max_in_progress_tasks', self.DEFAULT_MAX_IN_PROGRESS_TASKS),
            self.DEFAULT_MAX_IN_PROGRESS_TASKS,
        )
        self._max_active_requests = self._coerce_limit(
            kwargs.pop('max_active_requests', self.DEFAULT_MAX_ACTIVE_REQUESTS),
            self.DEFAULT_MAX_ACTIVE_REQUESTS,
        )
        super().__init__(*args, **kwargs)

    class Meta:
        db_table = 'user_roles'
        verbose_name = 'Р РѕР»СЊ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ'
        verbose_name_plural = 'Р РѕР»Рё РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№'

    def __str__(self):
        return self.name

    @staticmethod
    def _coerce_limit(value, default):
        if value in (None, ''):
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @property
    def max_active_tasks(self):
        return self._max_active_tasks

    @max_active_tasks.setter
    def max_active_tasks(self, value):
        self._max_active_tasks = self._coerce_limit(value, self.DEFAULT_MAX_ACTIVE_TASKS)

    @property
    def max_in_progress_tasks(self):
        return self._max_in_progress_tasks

    @max_in_progress_tasks.setter
    def max_in_progress_tasks(self, value):
        self._max_in_progress_tasks = self._coerce_limit(
            value,
            self.DEFAULT_MAX_IN_PROGRESS_TASKS,
        )

    @property
    def max_active_requests(self):
        return self._max_active_requests

    @max_active_requests.setter
    def max_active_requests(self, value):
        self._max_active_requests = self._coerce_limit(
            value,
            self.DEFAULT_MAX_ACTIVE_REQUESTS,
        )


# =====================================================
# 3. РђР”Р Р•РЎРђ
# =====================================================

class City(models.Model):
    """Р“РѕСЂРѕРґ / РЅР°СЃРµР»С‘РЅРЅС‹Р№ РїСѓРЅРєС‚."""
    name = models.CharField(max_length=100, verbose_name='РќР°Р·РІР°РЅРёРµ')
    region = models.CharField(max_length=100, blank=True, null=True, verbose_name='Р РµРіРёРѕРЅ')
    external_id = models.UUIDField(
        blank=True, null=True, db_index=True,
        help_text='Р’РЅРµС€РЅРёР№ РёРґРµРЅС‚РёС„РёРєР°С‚РѕСЂ Р°РґСЂРµСЃРЅРѕРіРѕ СЂРµРµСЃС‚СЂР° (РёР· DaData)',
        verbose_name='Р’РЅРµС€РЅРёР№ РёРґРµРЅС‚РёС„РёРєР°С‚РѕСЂ',
    )

    class Meta:
        db_table = 'cities'
        verbose_name = 'Р“РѕСЂРѕРґ'
        verbose_name_plural = 'Р“РѕСЂРѕРґР°'
        indexes = [models.Index(fields=['name'])]
        unique_together = [['name', 'region']]

    def __str__(self):
        return f'{self.name}, {self.region}' if self.region else self.name


class Street(models.Model):
    """РЈР»РёС†Р°."""
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='streets', verbose_name='Р“РѕСЂРѕРґ')
    name = models.CharField(max_length=150, verbose_name='РќР°Р·РІР°РЅРёРµ')
    street_type = models.CharField(max_length=20, blank=True, null=True, verbose_name='РўРёРї СѓР»РёС†С‹')
    external_id = models.UUIDField(blank=True, null=True, db_index=True, verbose_name='Р’РЅРµС€РЅРёР№ РёРґРµРЅС‚РёС„РёРєР°С‚РѕСЂ')

    class Meta:
        db_table = 'streets'
        verbose_name = 'РЈР»РёС†Р°'
        verbose_name_plural = 'РЈР»РёС†С‹'
        unique_together = [['city', 'name']]

    def __str__(self):
        return f'{self.street_type or ""} {self.name}'.strip()


class House(models.Model):
    """Р”РѕРј / СЃС‚СЂРѕРµРЅРёРµ."""
    street = models.ForeignKey(Street, on_delete=models.CASCADE, related_name='houses', verbose_name='РЈР»РёС†Р°')
    house_number = models.CharField(max_length=20, verbose_name='РќРѕРјРµСЂ РґРѕРјР°')
    postal_code = models.CharField(max_length=10, blank=True, null=True, verbose_name='РџРѕС‡С‚РѕРІС‹Р№ РёРЅРґРµРєСЃ')
    external_id = models.UUIDField(blank=True, null=True, db_index=True, verbose_name='Р’РЅРµС€РЅРёР№ РёРґРµРЅС‚РёС„РёРєР°С‚РѕСЂ')

    class Meta:
        db_table = 'houses'
        verbose_name = 'Р”РѕРј'
        verbose_name_plural = 'Р”РѕРјР°'
        unique_together = [['street', 'house_number']]

    def __str__(self):
        return f'{self.street.city}, {self.street}, Рґ. {self.house_number}'

    @property
    def house(self):
        return self


class AddressCompatibilityManager:
    """РЎРѕРІРјРµСЃС‚РёРјРѕСЃС‚СЊ СЃРѕ СЃС‚Р°СЂС‹Рј API Address РїРѕСЃР»Рµ СѓРґР°Р»РµРЅРёСЏ СЃСѓС‰РЅРѕСЃС‚Рё."""

    model = House

    @staticmethod
    def _rewrite_key(key: str) -> str:
        if key == 'house':
            return 'pk'
        if key.startswith('house__'):
            return key[len('house__'):]
        return key

    def _rewrite_kwargs(self, kwargs):
        rewritten = {}
        for key, value in kwargs.items():
            target_key = self._rewrite_key(key)
            if target_key == 'pk' and isinstance(value, House):
                rewritten[target_key] = value.pk
            else:
                rewritten[target_key] = value
        return rewritten

    def get_queryset(self):
        return House.objects.all()

    def all(self):
        return self.get_queryset()

    def select_related(self, *fields):
        rewritten = []
        for field in fields:
            mapped = self._rewrite_key(field)
            if mapped:
                rewritten.append(mapped)
        return self.get_queryset().select_related(*rewritten)

    def filter(self, *args, **kwargs):
        return self.get_queryset().filter(*args, **self._rewrite_kwargs(kwargs))

    def get(self, *args, **kwargs):
        return self.get_queryset().get(*args, **self._rewrite_kwargs(kwargs))

    def create(self, **kwargs):
        house = kwargs.get('house')
        if isinstance(house, House):
            return house
        if house not in (None, ''):
            return self.get(pk=house)
        raise TypeError('Address compatibility layer requires house=House(...) or house=<id>.')

    def get_or_create(self, defaults=None, **kwargs):
        house = kwargs.get('house')
        if isinstance(house, House):
            return house, False
        if house not in (None, ''):
            return self.get(pk=house), False
        raise TypeError('Address compatibility layer requires house=House(...) or house=<id>.')


class Address:
    """РќРµРјРёРіСЂРёСЂСѓРµРјР°СЏ СЃРѕРІРјРµСЃС‚РёРјРѕСЃС‚СЊ: СЃС‚Р°СЂС‹Р№ Address С‚РµРїРµСЂСЊ СѓРєР°Р·С‹РІР°РµС‚ РЅР° House."""

    objects = AddressCompatibilityManager()
    DoesNotExist = House.DoesNotExist
    MultipleObjectsReturned = House.MultipleObjectsReturned


# =====================================================
# 4. РџРћР›Р¬Р—РћР’РђРўР•Р›Р Р РџР РћР¤РР›Р
# =====================================================

class UserManager(BaseUserManager):
    """РњРµРЅРµРґР¶РµСЂ РєР°СЃС‚РѕРјРЅРѕР№ РјРѕРґРµР»Рё РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ."""

    def get_queryset(self):
        return AliasQuerySet(self.model, using=self._db, hints=self._hints)

    def create_user(self, username, email, password=None, **extra):
        if not username:
            raise ValueError('Р›РѕРіРёРЅ РѕР±СЏР·Р°С‚РµР»РµРЅ')
        if not email:
            raise ValueError('Р­Р»РµРєС‚СЂРѕРЅРЅР°СЏ РїРѕС‡С‚Р° РѕР±СЏР·Р°С‚РµР»СЊРЅР°')
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra):
        extra.setdefault('user_type', 'employee')
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        extra.setdefault('is_active', True)
        return self.create_user(username, email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """Р•РґРёРЅР°СЏ С‚Р°Р±Р»РёС†Р° СЃРѕС‚СЂСѓРґРЅРёРєРѕРІ Рё РєР»РёРµРЅС‚РѕРІ."""
    USER_TYPE_CHOICES = [
        ('employee', 'РЎРѕС‚СЂСѓРґРЅРёРє'),
        ('client', 'РљР»РёРµРЅС‚'),
    ]

    username = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Р›РѕРіРёРЅ',
    )
    email = models.EmailField(max_length=255, unique=True, verbose_name='Email')
    phone = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        null=True,
        validators=[phone_validator],
        verbose_name='РўРµР»РµС„РѕРЅ',
    )

    user_type_ref = models.ForeignKey(
        UserType,
        on_delete=models.PROTECT,
        related_name='users',
        verbose_name='РўРёРї РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ',
        default=1,
    )
    role = models.ForeignKey(UserRole, on_delete=models.SET_NULL,
                             verbose_name='Р РѕР»СЊ',
                             blank=True, null=True, related_name='users')

    is_active = models.BooleanField(default=True, verbose_name='РђРєС‚РёРІРµРЅ')
    is_staff = models.BooleanField(default=False, verbose_name='РЎРѕС‚СЂСѓРґРЅРёРє')
    is_email_verified = models.BooleanField(default=False, verbose_name='Email РїРѕРґС‚РІРµСЂР¶РґРµРЅ')
    is_phone_verified = models.BooleanField(default=False, verbose_name='РўРµР»РµС„РѕРЅ РїРѕРґС‚РІРµСЂР¶РґРµРЅ')

    last_login = models.DateTimeField(blank=True, null=True, verbose_name='РџРѕСЃР»РµРґРЅРёР№ РІС…РѕРґ')

    created_at = models.DateTimeField(default=timezone.now, verbose_name='Р”Р°С‚Р° СЃРѕР·РґР°РЅРёСЏ')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Р”Р°С‚Р° РѕР±РЅРѕРІР»РµРЅРёСЏ')

    objects = UserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']
    QUERY_ALIASES = {
        'user_type': 'user_type_ref__code',
        'user_type_id': 'user_type_ref_id',
    }

    class Meta:
        db_table = 'users'
        verbose_name = 'РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ'
        verbose_name_plural = 'РџРѕР»СЊР·РѕРІР°С‚РµР»Рё'

    def __str__(self):
        return f'{self.username} ({self.get_user_type_display()})'

    def __init__(self, *args, **kwargs):
        legacy_user_type = kwargs.pop('user_type', None)
        has_user_type_ref = 'user_type_ref' in kwargs or 'user_type_ref_id' in kwargs
        super().__init__(*args, **kwargs)
        if legacy_user_type not in (None, '') and not has_user_type_ref:
            self.user_type = legacy_user_type

    def clean(self):
        super().clean()
        if self.email:
            self.email = User.objects.normalize_email(self.email)
        if self.phone == '':
            self.phone = None
        if self.user_type == 'client' and (self.is_staff or self.is_superuser):
            raise ValidationError({
                'user_type': 'РљР»РёРµРЅС‚ РЅРµ РјРѕР¶РµС‚ РёРјРµС‚СЊ РґРѕСЃС‚СѓРї Рє Р°РґРјРёРЅРёСЃС‚СЂР°С‚РёРІРЅРѕР№ РїР°РЅРµР»Рё.',
                'is_staff': 'Р”Р»СЏ РєР»РёРµРЅС‚Р° РґРѕСЃС‚СѓРї staff РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ РІС‹РєР»СЋС‡РµРЅ.',
            })
        if self.user_type == 'client' and self.role_id:
            raise ValidationError({
                'role': 'Р РѕР»СЊ РЅР°Р·РЅР°С‡Р°РµС‚СЃСЏ С‚РѕР»СЊРєРѕ СЃРѕС‚СЂСѓРґРЅРёРєР°Рј.',
            })
        if self.is_staff and self.user_type != 'employee':
            raise ValidationError({
                'user_type': 'Р”РѕСЃС‚СѓРї РІ Р°РґРјРёРЅРєСѓ СЂР°Р·СЂРµС€С‘РЅ С‚РѕР»СЊРєРѕ СЃРѕС‚СЂСѓРґРЅРёРєР°Рј.',
            })

    @property
    def role_code(self) -> str | None:
        return self.role.code if self.role_id else None

    @property
    def user_type(self) -> str | None:
        return self.user_type_ref.code if self.user_type_ref_id else None

    @user_type.setter
    def user_type(self, value):
        self.user_type_ref = _resolve_lookup_instance(UserType, value)

    def get_user_type_display(self) -> str:
        if not self.user_type_ref_id:
            return ''
        return self.user_type_ref.name

    def save(self, *args, **kwargs):
        _rewrite_legacy_update_fields(self, kwargs)
        return super().save(*args, **kwargs)

    @property
    def is_admin_role(self) -> bool:
        return self.is_superuser or self.role_code == 'admin'

    @property
    def is_manager_role(self) -> bool:
        return self.role_code in {'manager', 'moderator'}

    @property
    def is_moderator_role(self) -> bool:
        return self.role_code in {'manager', 'moderator'}

    @property
    def is_admin_or_manager(self) -> bool:
        return self.is_admin_role or self.is_moderator_role

    @property
    def is_employee(self) -> bool:
        return self.user_type == 'employee'

    @property
    def is_client(self) -> bool:
        return self.user_type == 'client'


class EmployeeProfile(models.Model):
    """РџСЂРѕС„РёР»СЊ СЃРѕС‚СЂСѓРґРЅРёРєР°."""
    user = models.OneToOneField(User, on_delete=models.CASCADE,
                                verbose_name='РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ',
                                related_name='employee_profile')
    first_name = models.CharField(max_length=50, verbose_name='РРјСЏ')
    last_name = models.CharField(max_length=50, verbose_name='Р¤Р°РјРёР»РёСЏ')
    position = models.CharField(max_length=100, blank=True, null=True, verbose_name='Р”РѕР»Р¶РЅРѕСЃС‚СЊ')
    hire_date = models.DateField(blank=True, null=True, verbose_name='Р”Р°С‚Р° РЅР°Р№РјР°')
    internal_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name='Р’РЅСѓС‚СЂРµРЅРЅРёР№ С‚РµР»РµС„РѕРЅ')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Р”Р°С‚Р° СЃРѕР·РґР°РЅРёСЏ')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Р”Р°С‚Р° РѕР±РЅРѕРІР»РµРЅРёСЏ')

    class Meta:
        db_table = 'employee_profiles'
        verbose_name = 'РџСЂРѕС„РёР»СЊ СЃРѕС‚СЂСѓРґРЅРёРєР°'
        verbose_name_plural = 'РџСЂРѕС„РёР»Рё СЃРѕС‚СЂСѓРґРЅРёРєРѕРІ'

    def __init__(self, *args, **kwargs):
        self._legacy_middle_name = kwargs.pop('middle_name', None)
        self._legacy_department = kwargs.pop('department', None)
        self._legacy_notes = kwargs.pop('notes', None)
        super().__init__(*args, **kwargs)

    def __str__(self):
        return f'{self.last_name} {self.first_name}'

    def clean(self):
        super().clean()
        if self.user_id and self.user.user_type != 'employee':
            raise ValidationError({'user': 'РџСЂРѕС„РёР»СЊ СЃРѕС‚СЂСѓРґРЅРёРєР° РјРѕР¶РЅРѕ РїСЂРёРІСЏР·Р°С‚СЊ С‚РѕР»СЊРєРѕ Рє РїРѕР»СЊР·РѕРІР°С‚РµР»СЋ С‚РёРїР° "РЎРѕС‚СЂСѓРґРЅРёРє".'})

    @property
    def middle_name(self):
        return self._legacy_middle_name

    @middle_name.setter
    def middle_name(self, value):
        self._legacy_middle_name = value

    @property
    def department(self):
        return self._legacy_department

    @department.setter
    def department(self, value):
        self._legacy_department = value

    @property
    def notes(self):
        return self._legacy_notes

    @notes.setter
    def notes(self, value):
        self._legacy_notes = value


class ClientProfile(models.Model):
    """РџСЂРѕС„РёР»СЊ РєР»РёРµРЅС‚Р°."""
    CLIENT_KIND_INDIVIDUAL = 'individual'
    CLIENT_KIND_COMPANY = 'company'
    CLIENT_KIND_CHOICES = _lookup_choices(
        'ClientKind',
        (CLIENT_KIND_INDIVIDUAL, CLIENT_KIND_COMPANY),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE,
                                verbose_name='РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ',
                                related_name='client_profile')
    first_name = models.CharField(max_length=50, verbose_name='РРјСЏ')
    last_name = models.CharField(max_length=50, verbose_name='Р¤Р°РјРёР»РёСЏ')
    middle_name = models.CharField(max_length=50, blank=True, null=True, verbose_name='РћС‚С‡РµСЃС‚РІРѕ')
    client_kind_ref = models.ForeignKey(
        ClientKind,
        on_delete=models.PROTECT,
        related_name='profiles',
        verbose_name='Р’РёРґ РєР»РёРµРЅС‚Р°',
        default=1,
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Р”Р°С‚Р° СЃРѕР·РґР°РЅРёСЏ')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Р”Р°С‚Р° РѕР±РЅРѕРІР»РµРЅРёСЏ')

    class Meta:
        db_table = 'client_profiles'
        verbose_name = 'РџСЂРѕС„РёР»СЊ РєР»РёРµРЅС‚Р°'
        verbose_name_plural = 'РџСЂРѕС„РёР»Рё РєР»РёРµРЅС‚РѕРІ'

    QUERY_ALIASES = {
        'client_kind': 'client_kind_ref__code',
        'client_kind_id': 'client_kind_ref_id',
    }
    objects = AliasManager()

    def __str__(self):
        return f'{self.last_name} {self.first_name}'

    def __init__(self, *args, **kwargs):
        legacy_client_kind = kwargs.pop('client_kind', None)
        self._legacy_registration_address = kwargs.pop('registration_address', None)
        self._legacy_actual_address = kwargs.pop('actual_address', None)
        self._legacy_notes = kwargs.pop('notes', None)
        self._legacy_preferred_contact_method = kwargs.pop('preferred_contact_method', None)
        has_client_kind_ref = 'client_kind_ref' in kwargs or 'client_kind_ref_id' in kwargs
        super().__init__(*args, **kwargs)
        if legacy_client_kind not in (None, '') and not has_client_kind_ref:
            self.client_kind = legacy_client_kind

    def clean(self):
        super().clean()
        if self.user_id and self.user.user_type != 'client':
            raise ValidationError({'user': 'РџСЂРѕС„РёР»СЊ РєР»РёРµРЅС‚Р° РјРѕР¶РЅРѕ РїСЂРёРІСЏР·Р°С‚СЊ С‚РѕР»СЊРєРѕ Рє РїРѕР»СЊР·РѕРІР°С‚РµР»СЋ С‚РёРїР° "РљР»РёРµРЅС‚".'})

    @property
    def client_kind(self) -> str | None:
        return self.client_kind_ref.code if self.client_kind_ref_id else None

    @client_kind.setter
    def client_kind(self, value):
        self.client_kind_ref = _resolve_lookup_instance(ClientKind, value)

    @property
    def preferred_contact_method(self):
        return self._legacy_preferred_contact_method

    @preferred_contact_method.setter
    def preferred_contact_method(self, value):
        self._legacy_preferred_contact_method = value

    @property
    def registration_address(self):
        return self._legacy_registration_address

    @registration_address.setter
    def registration_address(self, value):
        self._legacy_registration_address = value

    @property
    def actual_address(self):
        return self._legacy_actual_address

    @actual_address.setter
    def actual_address(self, value):
        self._legacy_actual_address = value

    @property
    def notes(self):
        return self._legacy_notes

    @notes.setter
    def notes(self, value):
        self._legacy_notes = value

    def save(self, *args, **kwargs):
        _rewrite_legacy_update_fields(self, kwargs)
        return super().save(*args, **kwargs)


class ClientIndividualDetails(models.Model):
    """РџР°СЃРїРѕСЂС‚РЅС‹Рµ РґР°РЅРЅС‹Рµ РєР»РёРµРЅС‚Р°-С„РёР·Р»РёС†Р°."""
    profile = models.OneToOneField(
        ClientProfile,
        on_delete=models.CASCADE,
        related_name='individual_details',
        verbose_name='РџСЂРѕС„РёР»СЊ РєР»РёРµРЅС‚Р°',
    )
    passport_series = models.CharField(
        max_length=4,
        blank=True,
        null=True,
        validators=[passport_series_validator],
        verbose_name='РЎРµСЂРёСЏ РїР°СЃРїРѕСЂС‚Р°',
    )
    passport_number = models.CharField(
        max_length=6,
        blank=True,
        null=True,
        validators=[passport_number_validator],
        verbose_name='РќРѕРјРµСЂ РїР°СЃРїРѕСЂС‚Р°',
    )
    passport_issued_by = models.CharField(max_length=255, blank=True, null=True, verbose_name='РљРµРј РІС‹РґР°РЅ')
    passport_issued_date = models.DateField(blank=True, null=True, verbose_name='Р”Р°С‚Р° РІС‹РґР°С‡Рё')
    passport_code = models.CharField(
        max_length=7,
        blank=True,
        null=True,
        validators=[passport_code_validator],
        verbose_name='РљРѕРґ РїРѕРґСЂР°Р·РґРµР»РµРЅРёСЏ',
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Р”Р°С‚Р° СЃРѕР·РґР°РЅРёСЏ')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Р”Р°С‚Р° РѕР±РЅРѕРІР»РµРЅРёСЏ')

    class Meta:
        db_table = 'client_individual_details'
        verbose_name = 'РџР°СЃРїРѕСЂС‚РЅС‹Рµ РґР°РЅРЅС‹Рµ РєР»РёРµРЅС‚Р°'
        verbose_name_plural = 'РџР°СЃРїРѕСЂС‚РЅС‹Рµ РґР°РЅРЅС‹Рµ РєР»РёРµРЅС‚РѕРІ'

    def __str__(self):
        return f'РџР°СЃРїРѕСЂС‚РЅС‹Рµ РґР°РЅРЅС‹Рµ: {self.profile}'


class ClientCompanyDetails(models.Model):
    """Р РµРєРІРёР·РёС‚С‹ РєР»РёРµРЅС‚Р°-СЋСЂР»РёС†Р°."""
    profile = models.OneToOneField(
        ClientProfile,
        on_delete=models.CASCADE,
        related_name='company_details',
        verbose_name='РџСЂРѕС„РёР»СЊ РєР»РёРµРЅС‚Р°',
    )
    company_name = models.CharField(max_length=255, blank=True, null=True, verbose_name='РќР°Р·РІР°РЅРёРµ РєРѕРјРїР°РЅРёРё')
    company_inn = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        db_index=True,
        validators=[company_inn_validator],
        verbose_name='РРќРќ',
    )
    company_ogrn = models.CharField(
        max_length=13,
        blank=True,
        null=True,
        validators=[company_ogrn_validator],
        verbose_name='РћР“Р Рќ',
    )
    company_kpp = models.CharField(
        max_length=9,
        blank=True,
        null=True,
        validators=[company_kpp_validator],
        verbose_name='РљРџРџ',
    )
    legal_address = models.TextField(blank=True, null=True, verbose_name='Р®СЂРёРґРёС‡РµСЃРєРёР№ Р°РґСЂРµСЃ')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Р”Р°С‚Р° СЃРѕР·РґР°РЅРёСЏ')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Р”Р°С‚Р° РѕР±РЅРѕРІР»РµРЅРёСЏ')

    class Meta:
        db_table = 'client_company_details'
        verbose_name = 'Р РµРєРІРёР·РёС‚С‹ СЋСЂР»РёС†Р°'
        verbose_name_plural = 'Р РµРєРІРёР·РёС‚С‹ СЋСЂР»РёС†'

    def __str__(self):
        return f'Р®СЂР»РёС†Рѕ: {self.profile}'


# =====================================================
# 5. РќР•Р”Р’РР–РРњРћРЎРўР¬ Р Р”Р•РўРђР›Р
# =====================================================

class BuildingDetails(models.Model):
    """Р”РµС‚Р°Р»Рё РґРѕРјР°/СЃС‚СЂРѕРµРЅРёСЏ."""
    house = models.OneToOneField(House, on_delete=models.CASCADE, related_name='building_details', verbose_name='Р”РѕРј')
    year_built = models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Р“РѕРґ РїРѕСЃС‚СЂРѕР№РєРё')
    total_floors = models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Р’СЃРµРіРѕ СЌС‚Р°Р¶РµР№')
    building_material = models.ForeignKey(
        BuildingMaterial,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name='РњР°С‚РµСЂРёР°Р» СЃС‚РµРЅ',
    )
    elevators_count = models.PositiveSmallIntegerField(default=0, verbose_name='РљРѕР»РёС‡РµСЃС‚РІРѕ Р»РёС„С‚РѕРІ')

    class Meta:
        db_table = 'building_details'
        verbose_name = 'Р”РµС‚Р°Р»Рё РґРѕРјР°'
        verbose_name_plural = 'Р”РµС‚Р°Р»Рё РґРѕРјРѕРІ'

    def __str__(self):
        return f'Р”РµС‚Р°Р»Рё РґРѕРјР°: {self.house}'


class Property(models.Model):
    """РћР±СЉРµРєС‚ РЅРµРґРІРёР¶РёРјРѕСЃС‚Рё."""
    PROPERTY_TYPE_APARTMENT = 'apartment'
    PROPERTY_TYPE_HOUSE = 'house'
    PROPERTY_TYPE_COMMERCIAL = 'commercial'
    PROPERTY_TYPE_LAND = 'land'
    PROPERTY_TYPE_GARAGE = 'garage'
    PROPERTY_TYPE_ROOM = 'room'
    # Backward-compatible aliases kept for older forms / tests.
    PREMISES_APARTMENT = PROPERTY_TYPE_APARTMENT
    PREMISES_HOUSE = PROPERTY_TYPE_HOUSE
    PREMISES_COMMERCIAL = PROPERTY_TYPE_COMMERCIAL
    PREMISES_OFFICE = PROPERTY_TYPE_COMMERCIAL
    PREMISES_WAREHOUSE = PROPERTY_TYPE_COMMERCIAL
    PREMISES_TYPE_CHOICES = _lookup_choices(
        'PropertyType',
        (
            PROPERTY_TYPE_APARTMENT,
            PROPERTY_TYPE_HOUSE,
            PROPERTY_TYPE_COMMERCIAL,
            PROPERTY_TYPE_LAND,
            PROPERTY_TYPE_GARAGE,
            PROPERTY_TYPE_ROOM,
        ),
    )

    title = models.CharField(max_length=255, blank=True, null=True, verbose_name='РќР°Р·РІР°РЅРёРµ')
    operation_type = models.ForeignKey(
        OperationType,
        on_delete=models.PROTECT,
        verbose_name='РўРёРї РѕРїРµСЂР°С†РёРё',
        related_name='properties',
    )
    status = models.ForeignKey(
        PropertyStatus,
        on_delete=models.PROTECT,
        verbose_name='РЎС‚Р°С‚СѓСЃ',
        related_name='properties',
        default=1,
    )
    house = models.ForeignKey(
        House,
        on_delete=models.PROTECT,
        verbose_name='Р”РѕРј',
        related_name='properties',
    )
    property_type_ref = models.ForeignKey(
        PropertyType,
        on_delete=models.PROTECT,
        verbose_name='РўРёРї РїРѕРјРµС‰РµРЅРёСЏ',
        related_name='properties',
        default=1,
    )
    coordinates_lat = models.DecimalField(
        max_digits=10,
        decimal_places=8,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('-90')), MaxValueValidator(Decimal('90'))],
        verbose_name='РЁРёСЂРѕС‚Р°',
    )
    coordinates_lon = models.DecimalField(
        max_digits=11,
        decimal_places=8,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('-180')), MaxValueValidator(Decimal('180'))],
        verbose_name='Р”РѕР»РіРѕС‚Р°',
    )
    cadastral_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        unique=True,
        validators=[cadastral_number_validator],
        verbose_name='РљР°РґР°СЃС‚СЂРѕРІС‹Р№ РЅРѕРјРµСЂ',
    )
    price = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0)], verbose_name='Р¦РµРЅР°')
    area_total = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='РћР±С‰Р°СЏ РїР»РѕС‰Р°РґСЊ',
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    rooms_count = models.IntegerField(
        blank=True,
        null=True,
        verbose_name='РљРѕР»РёС‡РµСЃС‚РІРѕ РєРѕРјРЅР°С‚',
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    floor_number = models.IntegerField(
        blank=True,
        null=True,
        verbose_name='Р­С‚Р°Р¶',
        validators=[MinValueValidator(-5), MaxValueValidator(300)],
    )
    description = models.TextField(blank=True, null=True, verbose_name='РћРїРёСЃР°РЅРёРµ')
    is_published = models.BooleanField(default=True, verbose_name='РћРїСѓР±Р»РёРєРѕРІР°РЅРѕ')
    published_at = models.DateTimeField(blank=True, null=True, verbose_name='Р”Р°С‚Р° РїСѓР±Р»РёРєР°С†РёРё')
    unpublished_at = models.DateTimeField(blank=True, null=True, verbose_name='Р”Р°С‚Р° СЃРЅСЏС‚РёСЏ СЃ РїСѓР±Р»РёРєР°С†РёРё')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Р”Р°С‚Р° СЃРѕР·РґР°РЅРёСЏ')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Р”Р°С‚Р° РѕР±РЅРѕРІР»РµРЅРёСЏ')

    class Meta:
        db_table = 'properties'
        verbose_name = 'РћР±СЉРµРєС‚ РЅРµРґРІРёР¶РёРјРѕСЃС‚Рё'
        verbose_name_plural = 'РћР±СЉРµРєС‚С‹ РЅРµРґРІРёР¶РёРјРѕСЃС‚Рё'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(condition=models.Q(price__gte=0), name='property_price_non_negative'),
            models.CheckConstraint(
                condition=models.Q(area_total__isnull=True) | models.Q(area_total__gt=0),
                name='property_area_total_positive',
            ),
            models.CheckConstraint(
                condition=models.Q(rooms_count__isnull=True) | models.Q(rooms_count__gte=0),
                name='property_rooms_non_negative',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(coordinates_lat__isnull=True)
                    | (models.Q(coordinates_lat__gte=Decimal('-90')) & models.Q(coordinates_lat__lte=Decimal('90')))
                ),
                name='property_latitude_range',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(coordinates_lon__isnull=True)
                    | (models.Q(coordinates_lon__gte=Decimal('-180')) & models.Q(coordinates_lon__lte=Decimal('180')))
                ),
                name='property_longitude_range',
            ),
        ]

    QUERY_ALIASES = {
        'address': 'house',
        'address_id': 'house_id',
        'address__house': 'house',
        'address__house__street': 'house__street',
        'address__house__street__city': 'house__street__city',
        'owner': 'owners__client_profile__user',
        'owner_id': 'owners__client_profile__user_id',
        'total_floors': 'house__building_details__total_floors',
        'premises_type': 'property_type_ref__code',
        'premises_type_id': 'property_type_ref_id',
    }
    objects = AliasManager()

    def __init__(self, *args, **kwargs):
        legacy_premises_type = kwargs.pop('premises_type', None)
        legacy_address = kwargs.pop('address', None)
        legacy_owner = kwargs.pop('owner', None)
        legacy_owner_id = kwargs.pop('owner_id', None)
        legacy_total_floors = kwargs.pop('total_floors', None)
        has_property_type_ref = 'property_type_ref' in kwargs or 'property_type_ref_id' in kwargs
        has_house = 'house' in kwargs or 'house_id' in kwargs
        kwargs.pop('price_per_sqm', None)
        legacy_twogis = {
            'twogis_org_id': kwargs.pop('twogis_org_id', None),
            'twogis_name': kwargs.pop('twogis_name', None),
            'twogis_address_full': kwargs.pop('twogis_address_full', None),
            'twogis_rubric': kwargs.pop('twogis_rubric', None),
            'twogis_synced_at': kwargs.pop('twogis_synced_at', None),
        }
        super().__init__(*args, **kwargs)
        if legacy_premises_type not in (None, '') and not has_property_type_ref:
            self.premises_type = legacy_premises_type
        if legacy_address is not None and not has_house:
            self.address = legacy_address
        if legacy_owner not in (None, '') or legacy_owner_id not in (None, ''):
            self._pending_owner_profile = self._resolve_owner_profile(
                legacy_owner if legacy_owner not in (None, '') else legacy_owner_id,
            )
        if legacy_total_floors not in (None, ''):
            self.total_floors = legacy_total_floors
        for attr, value in legacy_twogis.items():
            if value not in (None, ''):
                setattr(self, attr, value)

    def __str__(self):
        return self.title or f'РћР±СЉРµРєС‚ в„–{self.pk}'

    @property
    def address(self):
        return self.house

    @address.setter
    def address(self, value):
        if isinstance(value, House):
            self.house = value
            return
        if hasattr(value, 'house'):
            self.house = value.house
            return
        if value in (None, ''):
            self.house = None
            return
        self.house = House.objects.filter(pk=value).first()

    def _resolve_owner_profile(self, value):
        if value in (None, ''):
            return None
        if isinstance(value, PropertyOwner):
            return value.client_profile
        if isinstance(value, ClientProfile):
            return value
        if isinstance(value, User):
            return getattr(value, 'client_profile', None)
        if hasattr(value, 'client_profile'):
            return value.client_profile
        if hasattr(value, 'user') and isinstance(value.user, User):
            return value
        try:
            user_id = int(value)
        except (TypeError, ValueError):
            return None
        user = User.objects.select_related('client_profile').filter(pk=user_id).first()
        return getattr(user, 'client_profile', None) if user else None

    def _primary_owner_relation(self):
        if getattr(self, 'pk', None) is None:
            return None
        if hasattr(self, '_prefetched_objects_cache') and 'owners' in getattr(self, '_prefetched_objects_cache', {}):
            owners = list(self.owners.all())
            return owners[0] if owners else None
        return self.owners.select_related('client_profile__user').first()

    @property
    def owner_profile(self):
        relation = self._primary_owner_relation()
        return relation.client_profile if relation else None

    @property
    def owner(self):
        relation = self._primary_owner_relation()
        return relation.client_profile.user if relation and relation.client_profile_id else None

    @property
    def owner_id(self):
        relation = self._primary_owner_relation()
        return relation.client_profile.user_id if relation else None

    def is_owned_by(self, user) -> bool:
        if user in (None, '') or not getattr(user, 'pk', None):
            return False
        return self.owners.filter(client_profile__user_id=user.pk).exists()

    @property
    def premises_type(self) -> str | None:
        return self.property_type_ref.code if self.property_type_ref_id else None

    @premises_type.setter
    def premises_type(self, value):
        if value in {'office', 'warehouse'}:
            value = self.PROPERTY_TYPE_COMMERCIAL
        self.property_type_ref = _resolve_lookup_instance(PropertyType, value)

    @property
    def price_per_sqm(self) -> float | None:
        if not self.area_total:
            return None
        try:
            area = Decimal(str(self.area_total))
            if area <= 0:
                return None
            return float(Decimal(str(self.price)) / area)
        except Exception:
            return None

    @price_per_sqm.setter
    def price_per_sqm(self, value):
        return

    def _twogis_source(self):
        if hasattr(self, '_prefetched_objects_cache') and 'external_sources' in getattr(self, '_prefetched_objects_cache', {}):
            for source in self.external_sources.all():
                if source.source_name == '2gis':
                    return source
            return None
        return self.external_sources.filter(source_name='2gis').first()

    @property
    def twogis_org_id(self):
        source = self._twogis_source()
        return source.external_id if source else None

    @twogis_org_id.setter
    def twogis_org_id(self, value):
        source = self._twogis_source()
        if source is None and value not in (None, ''):
            source = PropertyExternalSource(property=self, source_name='2gis', external_id=str(value))
        if source is not None:
            source.external_id = str(value) if value not in (None, '') else ''
            self._pending_twogis_source = source

    @property
    def twogis_name(self):
        source = self._twogis_source()
        return source.source_object_name if source else None

    @twogis_name.setter
    def twogis_name(self, value):
        source = self._twogis_source() or getattr(self, '_pending_twogis_source', None)
        if source is None and value not in (None, ''):
            source = PropertyExternalSource(property=self, source_name='2gis', external_id='')
        if source is not None:
            source.source_object_name = value
            self._pending_twogis_source = source

    @property
    def twogis_address_full(self):
        source = self._twogis_source()
        return source.source_address if source else None

    @twogis_address_full.setter
    def twogis_address_full(self, value):
        source = self._twogis_source() or getattr(self, '_pending_twogis_source', None)
        if source is None and value not in (None, ''):
            source = PropertyExternalSource(property=self, source_name='2gis', external_id='')
        if source is not None:
            source.source_address = value
            self._pending_twogis_source = source

    @property
    def twogis_rubric(self):
        source = self._twogis_source()
        return source.source_rubric if source else None

    @twogis_rubric.setter
    def twogis_rubric(self, value):
        source = self._twogis_source() or getattr(self, '_pending_twogis_source', None)
        if source is None and value not in (None, ''):
            source = PropertyExternalSource(property=self, source_name='2gis', external_id='')
        if source is not None:
            source.source_rubric = value
            self._pending_twogis_source = source

    @property
    def twogis_synced_at(self):
        source = self._twogis_source()
        return source.synced_at if source else None

    @twogis_synced_at.setter
    def twogis_synced_at(self, value):
        source = self._twogis_source() or getattr(self, '_pending_twogis_source', None)
        if source is None and value not in (None, ''):
            source = PropertyExternalSource(property=self, source_name='2gis', external_id='')
        if source is not None:
            source.synced_at = value
            self._pending_twogis_source = source

    def clean(self):
        super().clean()
        errors = {}
        if self.price is not None and self.price < 0:
            errors['price'] = 'Р¦РµРЅР° РЅРµ РјРѕР¶РµС‚ Р±С‹С‚СЊ РѕС‚СЂРёС†Р°С‚РµР»СЊРЅРѕР№.'
        if self.area_total is not None and self.area_total <= 0:
            errors['area_total'] = 'РџР»РѕС‰Р°РґСЊ РґРѕР»Р¶РЅР° Р±С‹С‚СЊ Р±РѕР»СЊС€Рµ РЅСѓР»СЏ.'
        if self.premises_type == self.PROPERTY_TYPE_COMMERCIAL and self.rooms_count is not None:
            errors['rooms_count'] = 'Р”Р»СЏ РѕС„РёСЃР° РёР»Рё СЃРєР»Р°РґР° РєРѕР»РёС‡РµСЃС‚РІРѕ РєРѕРјРЅР°С‚ РЅРµ РёСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ.'
        if self.rooms_count is not None and self.rooms_count < 0:
            errors['rooms_count'] = 'РљРѕР»РёС‡РµСЃС‚РІРѕ РєРѕРјРЅР°С‚ РЅРµ РјРѕР¶РµС‚ Р±С‹С‚СЊ РѕС‚СЂРёС†Р°С‚РµР»СЊРЅС‹Рј.'
        total_floors = self.total_floors
        if self.floor_number is not None and total_floors is not None:
            if self.floor_number > total_floors:
                errors['floor_number'] = 'Р­С‚Р°Р¶ РѕР±СЉРµРєС‚Р° РЅРµ РјРѕР¶РµС‚ Р±С‹С‚СЊ РІС‹С€Рµ РѕР±С‰РµРіРѕ РєРѕР»РёС‡РµСЃС‚РІР° СЌС‚Р°Р¶РµР№ РґРѕРјР°.'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields')
        if update_fields:
            update_fields = list(update_fields)
            if 'total_floors' in update_fields:
                update_fields = [field for field in update_fields if field != 'total_floors']
                if update_fields:
                    kwargs['update_fields'] = update_fields
                else:
                    kwargs.pop('update_fields')
        _rewrite_legacy_update_fields(self, kwargs)
        pending_total_floors = getattr(self, '_pending_total_floors', None)
        has_pending_total_floors = hasattr(self, '_pending_total_floors')
        pending_owner_profile = getattr(self, '_pending_owner_profile', None)
        has_pending_owner_profile = hasattr(self, '_pending_owner_profile')
        with transaction.atomic():
            super().save(*args, **kwargs)
            if has_pending_total_floors:
                if self.house_id is not None:
                    details = BuildingDetails.objects.filter(house_id=self.house_id).first()
                    if details is not None or pending_total_floors not in (None, ''):
                        BuildingDetails.objects.update_or_create(
                            house_id=self.house_id,
                            defaults={'total_floors': pending_total_floors},
                        )
                delattr(self, '_pending_total_floors')
            if has_pending_owner_profile is True and pending_owner_profile is not None:
                owner_link, created = PropertyOwner.objects.get_or_create(
                    property=self,
                    client_profile=pending_owner_profile,
                    defaults={
                        'ownership_share': Decimal('100')
                        if not PropertyOwner.objects.filter(property=self).exclude(
                            client_profile=pending_owner_profile,
                        ).exists()
                        else None,
                    },
                )
                if created and owner_link.ownership_share is None:
                    existing = PropertyOwner.objects.filter(property=self).count()
                    if existing == 1:
                        owner_link.ownership_share = Decimal('100')
                        owner_link.save(update_fields=['ownership_share'])
                delattr(self, '_pending_owner_profile')
            pending_source = getattr(self, '_pending_twogis_source', None)
            if pending_source is not None:
                pending_source.property = self
                if any([
                    pending_source.external_id,
                    pending_source.source_object_name,
                    pending_source.source_address,
                    pending_source.source_rubric,
                    pending_source.synced_at,
                ]):
                    pending_source.save()

    @property
    def building_details(self):
        """РЎРѕРІРјРµСЃС‚РёРјРѕСЃС‚СЊ СЃ РґРµС‚Р°Р»СЏРјРё РґРѕРјР°."""
        if getattr(self, 'house_id', None) is None:
            return None
        return BuildingDetails.objects.filter(house_id=self.house_id).first()

    @property
    def total_floors(self):
        if hasattr(self, '_pending_total_floors'):
            return self._pending_total_floors
        details = self.building_details
        if details is not None:
            return details.total_floors
        return None

    @total_floors.setter
    def total_floors(self, value):
        if value == '':
            value = None
        self._pending_total_floors = value
        details = self.building_details
        if details is not None:
            details.total_floors = value


class PropertyPriceHistory(models.Model):
    """РСЃС‚РѕСЂРёСЏ РёР·РјРµРЅРµРЅРёСЏ С†РµРЅ РѕР±СЉРµРєС‚РѕРІ."""
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='price_history', verbose_name='РћР±СЉРµРєС‚')
    old_price = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True, verbose_name='РЎС‚Р°СЂР°СЏ С†РµРЅР°')
    new_price = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='РќРѕРІР°СЏ С†РµРЅР°')
    changed_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name='РР·РјРµРЅРёР»', related_name='price_changes')
    changed_at = models.DateTimeField(default=timezone.now, verbose_name='Р”Р°С‚Р° РёР·РјРµРЅРµРЅРёСЏ')

    class Meta:
        db_table = 'property_price_history'
        verbose_name = 'РСЃС‚РѕСЂРёСЏ С†РµРЅ'
        verbose_name_plural = 'РСЃС‚РѕСЂРёСЏ С†РµРЅ'
        ordering = ['-changed_at']

    def __str__(self):
        return f'Р¦РµРЅР° РѕР±СЉРµРєС‚Р° #{self.property_id}: {self.old_price} в†’ {self.new_price}'


class PropertyStatusHistory(models.Model):
    """РСЃС‚РѕСЂРёСЏ СЃРјРµРЅ СЃС‚Р°С‚СѓСЃР° РѕР±СЉРµРєС‚Р° РЅРµРґРІРёР¶РёРјРѕСЃС‚Рё."""
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='status_history',
        verbose_name='РћР±СЉРµРєС‚',
    )
    old_status = models.ForeignKey(
        PropertyStatus,
        on_delete=models.PROTECT,
        related_name='property_status_history_old',
        blank=True,
        null=True,
        verbose_name='РЎС‚Р°СЂС‹Р№ СЃС‚Р°С‚СѓСЃ',
    )
    new_status = models.ForeignKey(
        PropertyStatus,
        on_delete=models.PROTECT,
        related_name='property_status_history_new',
        verbose_name='РќРѕРІС‹Р№ СЃС‚Р°С‚СѓСЃ',
    )
    changed_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='property_status_changes',
        verbose_name='РР·РјРµРЅРёР»',
    )
    changed_at = models.DateTimeField(default=timezone.now, verbose_name='Р”Р°С‚Р° РёР·РјРµРЅРµРЅРёСЏ')

    class Meta:
        db_table = 'property_status_history'
        verbose_name = 'РСЃС‚РѕСЂРёСЏ СЃС‚Р°С‚СѓСЃР° РѕР±СЉРµРєС‚Р°'
        verbose_name_plural = 'РСЃС‚РѕСЂРёСЏ СЃС‚Р°С‚СѓСЃРѕРІ РѕР±СЉРµРєС‚РѕРІ'
        ordering = ['-changed_at']

    def __str__(self):
        old_status = self.old_status.name if self.old_status_id else 'вЂ”'
        new_status = self.new_status.name if self.new_status_id else 'вЂ”'
        return f'РЎС‚Р°С‚СѓСЃ РѕР±СЉРµРєС‚Р° #{self.property_id}: {old_status} в†’ {new_status}'


class PropertyOwner(models.Model):
    """РЎРѕР±СЃС‚РІРµРЅРЅРёРє РѕР±СЉРµРєС‚Р° РЅРµРґРІРёР¶РёРјРѕСЃС‚Рё (РїРѕРґРґРµСЂР¶РёРІР°РµС‚ РґРѕР»РµРІСѓСЋ СЃРѕР±СЃС‚РІРµРЅРЅРѕСЃС‚СЊ)."""
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='owners', verbose_name='РћР±СЉРµРєС‚')
    client_profile = models.ForeignKey(ClientProfile, on_delete=models.PROTECT, related_name='owned_properties', verbose_name='РЎРѕР±СЃС‚РІРµРЅРЅРёРє')
    ownership_share = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('100'))],
        verbose_name='Р”РѕР»СЏ СЃРѕР±СЃС‚РІРµРЅРЅРѕСЃС‚Рё (%)',
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Р”Р°С‚Р° СЃРѕР·РґР°РЅРёСЏ')

    class Meta:
        db_table = 'property_owners'
        verbose_name = 'РЎРѕР±СЃС‚РІРµРЅРЅРёРє РѕР±СЉРµРєС‚Р°'
        verbose_name_plural = 'РЎРѕР±СЃС‚РІРµРЅРЅРёРєРё РѕР±СЉРµРєС‚РѕРІ'
        unique_together = [['property', 'client_profile']]
        ordering = ['created_at', 'property_id', 'client_profile_id']

    def __str__(self):
        share = f' ({self.ownership_share}%)' if self.ownership_share else ''
        return f'{self.property} в†’ {self.client_profile}{share}'


class PropertyDetails(models.Model):
    """Р”РµС‚Р°Р»СЊРЅР°СЏ РёРЅС„РѕСЂРјР°С†РёСЏ РѕР± РѕР±СЉРµРєС‚Рµ РЅРµРґРІРёР¶РёРјРѕСЃС‚Рё (РґР»СЏ Р¶РёР»РѕР№ РЅРµРґРІРёР¶РёРјРѕСЃС‚Рё)."""
    property = models.OneToOneField(Property, on_delete=models.CASCADE, related_name='details', verbose_name='РћР±СЉРµРєС‚')
    living_area = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Р–РёР»Р°СЏ РїР»РѕС‰Р°РґСЊ',
    )
    kitchen_area = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='РџР»РѕС‰Р°РґСЊ РєСѓС…РЅРё',
    )
    ceiling_height = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='Р’С‹СЃРѕС‚Р° РїРѕС‚РѕР»РєРѕРІ (Рј)',
    )
    balcony_count = models.PositiveSmallIntegerField(default=0, verbose_name='РљРѕР»РёС‡РµСЃС‚РІРѕ Р±Р°Р»РєРѕРЅРѕРІ/Р»РѕРґР¶РёР№')
    bathroom_count = models.PositiveSmallIntegerField(default=1, verbose_name='РљРѕР»РёС‡РµСЃС‚РІРѕ СЃР°РЅСѓР·Р»РѕРІ')
    bathroom_type = models.ForeignKey(
        BathroomType,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name='РўРёРї СЃР°РЅСѓР·Р»Р°',
    )
    renovation_type = models.ForeignKey(
        RenovationType,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name='РўРёРї СЂРµРјРѕРЅС‚Р°',
    )
    bedrooms_count = models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='РљРѕР»РёС‡РµСЃС‚РІРѕ СЃРїР°Р»РµРЅ')
    floors_count = models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='РљРѕР»РёС‡РµСЃС‚РІРѕ СЌС‚Р°Р¶РµР№ (РґР»СЏ РґРѕРјР°)')
    land_area = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='РџР»РѕС‰Р°РґСЊ СѓС‡Р°СЃС‚РєР°',
    )

    class Meta:
        db_table = 'property_details'
        verbose_name = 'Р”РµС‚Р°Р»Рё РѕР±СЉРµРєС‚Р°'
        verbose_name_plural = 'Р”РµС‚Р°Р»Рё РѕР±СЉРµРєС‚РѕРІ'

    def __str__(self):
        return f'Р”РµС‚Р°Р»Рё РѕР±СЉРµРєС‚Р° #{self.property_id}'


class CommercialPropertyDetails(models.Model):
    """Р”РµС‚Р°Р»СЊРЅР°СЏ РёРЅС„РѕСЂРјР°С†РёСЏ Рѕ РєРѕРјРјРµСЂС‡РµСЃРєРѕР№ РЅРµРґРІРёР¶РёРјРѕСЃС‚Рё."""
    property = models.OneToOneField(Property, on_delete=models.CASCADE, related_name='commercial_details', verbose_name='РћР±СЉРµРєС‚')
    commercial_type = models.ForeignKey(
        CommercialPropertyType,
        on_delete=models.PROTECT,
        verbose_name='РўРёРї РєРѕРјРјРµСЂС‡РµСЃРєРѕР№ РЅРµРґРІРёР¶РёРјРѕСЃС‚Рё',
    )
    usable_area = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='РџРѕР»РµР·РЅР°СЏ РїР»РѕС‰Р°РґСЊ',
    )
    ceiling_height = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='Р’С‹СЃРѕС‚Р° РїРѕС‚РѕР»РєРѕРІ (Рј)',
    )
    floor_load = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='РќР°РіСЂСѓР·РєР° РЅР° РїРѕР» (РєРі/РјВІ)',
    )
    electric_power_kw = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
        verbose_name='Р­Р»РµРєС‚СЂРёС‡РµСЃРєР°СЏ РјРѕС‰РЅРѕСЃС‚СЊ (РєР’С‚)',
    )
    has_separate_entrance = models.BooleanField(default=False, verbose_name='РћС‚РґРµР»СЊРЅС‹Р№ РІС…РѕРґ')
    has_display_windows = models.BooleanField(default=False, verbose_name='Р’РёС‚СЂРёРЅРЅС‹Рµ РѕРєРЅР°')
    is_first_line = models.BooleanField(default=False, verbose_name='РџРµСЂРІР°СЏ Р»РёРЅРёСЏ РґРѕРјРѕРІ')
    parking_spaces = models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='РџР°СЂРєРѕРІРѕС‡РЅС‹Рµ РјРµСЃС‚Р°')

    class Meta:
        db_table = 'commercial_property_details'
        verbose_name = 'Р”РµС‚Р°Р»Рё РєРѕРјРјРµСЂС‡РµСЃРєРѕР№ РЅРµРґРІРёР¶РёРјРѕСЃС‚Рё'
        verbose_name_plural = 'Р”РµС‚Р°Р»Рё РєРѕРјРјРµСЂС‡РµСЃРєРѕР№ РЅРµРґРІРёР¶РёРјРѕСЃС‚Рё'

    def __str__(self):
        return f'РљРѕРјРјРµСЂС‡РµСЃРєРёРµ РґРµС‚Р°Р»Рё РѕР±СЉРµРєС‚Р° #{self.property_id}'


class PropertyAmenity(models.Model):
    """РЎРІСЏР·СЊ РѕР±СЉРµРєС‚Р° СЃ СѓРґРѕР±СЃС‚РІР°РјРё/РѕСЃРѕР±РµРЅРЅРѕСЃС‚СЏРјРё."""
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='amenities', verbose_name='РћР±СЉРµРєС‚')
    amenity = models.ForeignKey(Amenity, on_delete=models.CASCADE, verbose_name='РЈРґРѕР±СЃС‚РІРѕ')

    class Meta:
        db_table = 'property_amenities'
        verbose_name = 'РЈРґРѕР±СЃС‚РІРѕ РѕР±СЉРµРєС‚Р°'
        verbose_name_plural = 'РЈРґРѕР±СЃС‚РІР° РѕР±СЉРµРєС‚РѕРІ'
        unique_together = [['property', 'amenity']]

    def __str__(self):
        return f'{self.property} в†’ {self.amenity}'


class PropertyPhoto(models.Model):
    """Р¤РѕС‚РѕРіСЂР°С„РёСЏ РѕР±СЉРµРєС‚Р°."""
    property = models.ForeignKey(Property, on_delete=models.CASCADE,
                                 verbose_name='РћР±СЉРµРєС‚',
                                 related_name='photos')
    url = models.TextField(blank=True, null=True, verbose_name='URL')
    caption = models.CharField(max_length=255, blank=True, null=True, verbose_name='РџРѕРґРїРёСЃСЊ')
    is_hidden = models.BooleanField(default=False, verbose_name='РЎРєСЂС‹С‚Рѕ')
    order = models.PositiveIntegerField(default=0, verbose_name='РџРѕСЂСЏРґРѕРє')
    uploaded_at = models.DateTimeField(default=timezone.now, verbose_name='Р”Р°С‚Р° Р·Р°РіСЂСѓР·РєРё')

    class Meta:
        db_table = 'property_photos'
        verbose_name = 'Р¤РѕС‚Рѕ РѕР±СЉРµРєС‚Р°'
        verbose_name_plural = 'Р¤РѕС‚Рѕ РѕР±СЉРµРєС‚РѕРІ'
        ordering = ['order', '-uploaded_at']

    def __init__(self, *args, **kwargs):
        legacy_image = kwargs.pop('image', None)
        legacy_is_cover = kwargs.pop('is_cover', None)
        super().__init__(*args, **kwargs)
        if legacy_image not in (None, '') and not self.url:
            self.url = legacy_image if isinstance(legacy_image, str) else getattr(legacy_image, 'name', None)
        if legacy_is_cover not in (None, '') and bool(legacy_is_cover) and not getattr(self, 'order', None):
            self.order = 0

    @_property
    def is_cover(self):
        return self.order == 0

    @is_cover.setter
    def is_cover(self, value):
        if value:
            self.order = 0
        elif self.order == 0:
            self.order = 1


class PropertyDocument(models.Model):
    """Р”РѕРєСѓРјРµРЅС‚, РїСЂРёРІСЏР·Р°РЅРЅС‹Р№ Рє РѕР±СЉРµРєС‚Сѓ (РІС‹РїРёСЃРєР° Р•Р“Р Рќ, РґРѕРіРѕРІРѕСЂ Рё С‚. Рї.)."""
    property = models.ForeignKey(Property, on_delete=models.CASCADE,
                                 verbose_name='РћР±СЉРµРєС‚',
                                 related_name='documents')
    document_name = models.CharField(max_length=255, verbose_name='РќР°Р·РІР°РЅРёРµ РґРѕРєСѓРјРµРЅС‚Р°')
    file_url = models.TextField(verbose_name='URL С„Р°Р№Р»Р°')
    is_verified = models.BooleanField(default=False, verbose_name='РџСЂРѕРІРµСЂРµРЅРѕ')
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL,
                                    blank=True, null=True,
                                    verbose_name='РџСЂРѕРІРµСЂРёР»',
                                    related_name='verified_documents')
    verified_at = models.DateTimeField(blank=True, null=True, verbose_name='Р”Р°С‚Р° РїСЂРѕРІРµСЂРєРё')
    uploaded_at = models.DateTimeField(default=timezone.now, verbose_name='Р”Р°С‚Р° Р·Р°РіСЂСѓР·РєРё')

    class Meta:
        db_table = 'property_documents'
        verbose_name = 'Р”РѕРєСѓРјРµРЅС‚ РѕР±СЉРµРєС‚Р°'
        verbose_name_plural = 'Р”РѕРєСѓРјРµРЅС‚С‹ РѕР±СЉРµРєС‚РѕРІ'

    def clean(self):
        super().clean()
        errors = {}
        if self.is_verified and not self.verified_by_id:
            errors['verified_by'] = 'Р”Р»СЏ РїРѕРґС‚РІРµСЂР¶РґС‘РЅРЅРѕРіРѕ РґРѕРєСѓРјРµРЅС‚Р° РЅСѓР¶РЅРѕ СѓРєР°Р·Р°С‚СЊ РїСЂРѕРІРµСЂРёРІС€РµРіРѕ СЃРѕС‚СЂСѓРґРЅРёРєР°.'
        if self.verified_at and not self.is_verified:
            errors['verified_at'] = 'Р”Р°С‚Р° РїСЂРѕРІРµСЂРєРё РґРѕРїСѓСЃРєР°РµС‚СЃСЏ С‚РѕР»СЊРєРѕ РґР»СЏ РїРѕРґС‚РІРµСЂР¶РґС‘РЅРЅРѕРіРѕ РґРѕРєСѓРјРµРЅС‚Р°.'
        if errors:
            raise ValidationError(errors)


class PropertyViewing(models.Model):
    """Р—Р°РїР»Р°РЅРёСЂРѕРІР°РЅРЅС‹Р№ РїСЂРѕСЃРјРѕС‚СЂ РѕР±СЉРµРєС‚Р° РєР»РёРµРЅС‚РѕРј."""
    QUERY_ALIASES = {
        'client': 'client_profile__user',
        'client_id': 'client_profile__user_id',
        'agent': 'employee_profile__user',
        'agent_id': 'employee_profile__user_id',
    }
    objects = AliasManager()

    property = models.ForeignKey(Property, on_delete=models.PROTECT,
                                 verbose_name='РћР±СЉРµРєС‚',
                                 related_name='viewings')
    client_profile = models.ForeignKey(ClientProfile, on_delete=models.PROTECT,
                                       related_name='viewings',
                                       verbose_name='РљР»РёРµРЅС‚')
    employee_profile = models.ForeignKey(EmployeeProfile, on_delete=models.PROTECT,
                                         related_name='viewings',
                                         verbose_name='РЎРѕС‚СЂСѓРґРЅРёРє')
    viewing_date = models.DateTimeField(verbose_name='Р”Р°С‚Р° РїСЂРѕСЃРјРѕС‚СЂР°')
    status = models.ForeignKey(ViewingStatus, on_delete=models.PROTECT,
                               verbose_name='РЎС‚Р°С‚СѓСЃ', default=1)
    comment = models.TextField(blank=True, null=True, verbose_name='РљРѕРјРјРµРЅС‚Р°СЂРёР№')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Р”Р°С‚Р° СЃРѕР·РґР°РЅРёСЏ')

    class Meta:
        db_table = 'property_viewings'
        verbose_name = 'РџСЂРѕСЃРјРѕС‚СЂ РѕР±СЉРµРєС‚Р°'
        verbose_name_plural = 'РџСЂРѕСЃРјРѕС‚СЂС‹ РѕР±СЉРµРєС‚РѕРІ'
        ordering = ['-viewing_date']

    def clean(self):
        super().clean()
        errors = {}
        if self.client_profile_id and self.client_profile.user.user_type != 'client':
            errors['client_profile'] = 'РљР»РёРµРЅС‚РѕРј РїСЂРѕСЃРјРѕС‚СЂР° РјРѕР¶РµС‚ Р±С‹С‚СЊ С‚РѕР»СЊРєРѕ РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ С‚РёРїР° "РљР»РёРµРЅС‚".'
        if self.employee_profile_id and self.employee_profile.user.user_type != 'employee':
            errors['employee_profile'] = 'РЎРѕС‚СЂСѓРґРЅРёРєРѕРј РїСЂРѕСЃРјРѕС‚СЂР° РјРѕР¶РµС‚ Р±С‹С‚СЊ С‚РѕР»СЊРєРѕ СЃРѕС‚СЂСѓРґРЅРёРє.'
        if errors:
            raise ValidationError(errors)

    @_property
    def client(self):
        return self.client_profile.user if self.client_profile_id else None

    @client.setter
    def client(self, value):
        self.client_profile = _resolve_user_profile(value, 'client_profile')

    @_property
    def client_id(self):
        return self.client_profile.user_id if self.client_profile_id else None

    @client_id.setter
    def client_id(self, value):
        self.client_profile = _resolve_user_profile(value, 'client_profile')

    @_property
    def agent(self):
        return self.employee_profile.user if self.employee_profile_id else None

    @agent.setter
    def agent(self, value):
        self.employee_profile = _resolve_user_profile(value, 'employee_profile')

    @_property
    def agent_id(self):
        return self.employee_profile.user_id if self.employee_profile_id else None

    @agent_id.setter
    def agent_id(self, value):
        self.employee_profile = _resolve_user_profile(value, 'employee_profile')

    @_property
    def scheduled_date(self):
        return self.viewing_date

    @scheduled_date.setter
    def scheduled_date(self, value):
        self.viewing_date = value

    @_property
    def notes(self):
        return self.comment

    @notes.setter
    def notes(self, value):
        self.comment = value


class PropertyExternalSource(models.Model):
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='external_sources',
        verbose_name='РћР±СЉРµРєС‚',
    )
    source_name = models.CharField(max_length=50, verbose_name='РСЃС‚РѕС‡РЅРёРє')
    external_id = models.CharField(max_length=128, verbose_name='Р’РЅРµС€РЅРёР№ РёРґРµРЅС‚РёС„РёРєР°С‚РѕСЂ')
    source_object_name = models.CharField(max_length=255, blank=True, null=True, verbose_name='РќР°Р·РІР°РЅРёРµ РѕР±СЉРµРєС‚Р°')
    source_address = models.TextField(blank=True, null=True, verbose_name='РђРґСЂРµСЃ РёСЃС‚РѕС‡РЅРёРєР°')
    source_rubric = models.CharField(max_length=255, blank=True, null=True, verbose_name='Р СѓР±СЂРёРєР° РёСЃС‚РѕС‡РЅРёРєР°')
    synced_at = models.DateTimeField(blank=True, null=True, verbose_name='Р”Р°С‚Р° СЃРёРЅС…СЂРѕРЅРёР·Р°С†РёРё')

    class Meta:
        db_table = 'property_external_sources'
        verbose_name = 'Р’РЅРµС€РЅРёР№ РёСЃС‚РѕС‡РЅРёРє РѕР±СЉРµРєС‚Р°'
        verbose_name_plural = 'Р’РЅРµС€РЅРёРµ РёСЃС‚РѕС‡РЅРёРєРё РѕР±СЉРµРєС‚РѕРІ'
        constraints = [
            models.UniqueConstraint(
                fields=['property', 'source_name', 'external_id'],
                name='property_external_source_unique',
            ),
        ]

    def __str__(self):
        return f'{self.source_name}: {self.external_id}'


# =====================================================
# 6. Р—РђРЇР’РљР, РЎР”Р•Р›РљР, РЈР§РђРЎРўРќРРљР Р Р”РћРљРЈРњР•РќРўР«
# =====================================================

class Request(models.Model):
    """Р—Р°СЏРІРєР° РєР»РёРµРЅС‚Р° РЅР° РїРѕРґР±РѕСЂ РёР»Рё РєРѕРЅРєСЂРµС‚РЅС‹Р№ РѕР±СЉРµРєС‚."""
    LEGACY_STATUS_CODE_ALIASES = {
        'closed': 'completed',
    }
    STATUS_DISPLAY_NAMES = {
        'open': 'РћС‚РєСЂС‹С‚Р°',
        'processing': 'Р’ РѕР±СЂР°Р±РѕС‚РєРµ',
        'completed': 'Р—Р°РІРµСЂС€РµРЅР°',
        'cancelled': 'РћС‚РјРµРЅРµРЅР°',
        'rejected': 'РћС‚РєР»РѕРЅРµРЅР°',
        'lost': 'РџРѕС‚РµСЂСЏРЅР°',
    }
    ACTIVE_STATUS_CODES = ('open', 'processing')
    TERMINAL_STATUS_CODES = (
        'completed', 'cancelled', 'rejected', 'lost',
    )
    SUCCESS_STATUS_CODES = ('completed',)

    client_profile = models.ForeignKey(ClientProfile, on_delete=models.PROTECT,
                                       related_name='requests',
                                       verbose_name='РљР»РёРµРЅС‚')
    employee_profile = models.ForeignKey(EmployeeProfile, on_delete=models.PROTECT,
                                         related_name='handled_requests',
                                         blank=True, null=True,
                                         verbose_name='РЎРѕС‚СЂСѓРґРЅРёРє')
    property = models.ForeignKey('Property', on_delete=models.PROTECT,
                                 related_name='direct_requests',
                                 verbose_name='РћР±СЉРµРєС‚',
                                 blank=True, null=True)

    operation_type = models.ForeignKey(OperationType, on_delete=models.PROTECT,
                                       verbose_name='РўРёРї РѕРїРµСЂР°С†РёРё',
                                       related_name='requests')
    status = models.ForeignKey(RequestStatus, on_delete=models.PROTECT,
                               verbose_name='РЎС‚Р°С‚СѓСЃ',
                               related_name='requests', default=1)
    property_type = models.ForeignKey(PropertyType, on_delete=models.SET_NULL,
                                      blank=True, null=True,
                                      verbose_name='РўРёРї РїРѕРјРµС‰РµРЅРёСЏ')
    preferred_city = models.ForeignKey(City, on_delete=models.SET_NULL,
                                       blank=True, null=True,
                                       verbose_name='РџСЂРµРґРїРѕС‡РёС‚Р°РµРјС‹Р№ РіРѕСЂРѕРґ')
    preferred_district = models.CharField(max_length=100, blank=True, null=True, verbose_name='РџСЂРµРґРїРѕС‡РёС‚Р°РµРјС‹Р№ СЂР°Р№РѕРЅ')
    min_price = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True,
                                    validators=[MinValueValidator(0)], verbose_name='РњРёРЅРёРјР°Р»СЊРЅР°СЏ С†РµРЅР°')
    max_price = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True,
                                    validators=[MinValueValidator(0)], verbose_name='РњР°РєСЃРёРјР°Р»СЊРЅР°СЏ С†РµРЅР°')
    min_area = models.DecimalField(max_digits=8, decimal_places=2,
                                   blank=True, null=True,
                                   verbose_name='РњРёРЅРёРјР°Р»СЊРЅР°СЏ РїР»РѕС‰Р°РґСЊ',
                                   validators=[MinValueValidator(Decimal('0.01'))])
    max_area = models.DecimalField(max_digits=8, decimal_places=2,
                                   blank=True, null=True,
                                   verbose_name='РњР°РєСЃРёРјР°Р»СЊРЅР°СЏ РїР»РѕС‰Р°РґСЊ',
                                   validators=[MinValueValidator(Decimal('0.01'))])
    rooms_count = models.IntegerField(blank=True, null=True,
                                      verbose_name='РљРѕР»РёС‡РµСЃС‚РІРѕ РєРѕРјРЅР°С‚',
                                      validators=[MinValueValidator(0), MaxValueValidator(100)])

    address_preferences = models.TextField(blank=True, null=True, verbose_name='РџРѕР¶РµР»Р°РЅРёСЏ РїРѕ Р°РґСЂРµСЃСѓ')
    description = models.TextField(blank=True, null=True, verbose_name='РћРїРёСЃР°РЅРёРµ')

    created_at = models.DateTimeField(default=timezone.now, verbose_name='Р”Р°С‚Р° СЃРѕР·РґР°РЅРёСЏ')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Р”Р°С‚Р° РѕР±РЅРѕРІР»РµРЅРёСЏ')
    closed_at = models.DateTimeField(blank=True, null=True, verbose_name='Р”Р°С‚Р° Р·Р°РєСЂС‹С‚РёСЏ')

    class Meta:
        db_table = 'requests'
        verbose_name = 'Р—Р°СЏРІРєР° РєР»РёРµРЅС‚Р°'
        verbose_name_plural = 'Р—Р°СЏРІРєРё РєР»РёРµРЅС‚РѕРІ'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(min_price__isnull=True) | models.Q(min_price__gte=0),
                name='request_min_price_non_negative',
            ),
            models.CheckConstraint(
                condition=models.Q(max_price__isnull=True) | models.Q(max_price__gte=0),
                name='request_max_price_non_negative',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(min_price__isnull=True)
                    | models.Q(max_price__isnull=True)
                    | models.Q(min_price__lte=models.F('max_price'))
                ),
                name='request_price_range_valid',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(min_area__isnull=True)
                    | models.Q(max_area__isnull=True)
                    | models.Q(min_area__lte=models.F('max_area'))
                ),
                name='request_area_range_valid',
            ),
            models.CheckConstraint(
                condition=models.Q(rooms_count__isnull=True) | models.Q(rooms_count__gte=0),
                name='request_rooms_non_negative',
            ),
        ]

    objects = AliasManager()
    QUERY_ALIASES = {
        'client': 'client_profile__user',
        'client_id': 'client_profile__user_id',
        'agent': 'employee_profile__user',
        'agent_id': 'employee_profile__user_id',
    }

    def __str__(self):
        return f'Р—Р°СЏРІРєР° в„–{self.pk} РѕС‚ {self.client_profile.user.username}'

    @_property
    def client(self):
        return self.client_profile.user if self.client_profile_id else None

    @client.setter
    def client(self, value):
        self.client_profile = _resolve_user_profile(value, 'client_profile')

    @_property
    def client_id(self):
        return self.client_profile.user_id if self.client_profile_id else None

    @client_id.setter
    def client_id(self, value):
        self.client_profile = _resolve_user_profile(value, 'client_profile')

    @_property
    def agent(self):
        return self.employee_profile.user if self.employee_profile_id else None

    @agent.setter
    def agent(self, value):
        self.employee_profile = _resolve_user_profile(value, 'employee_profile')

    @_property
    def agent_id(self):
        return self.employee_profile.user_id if self.employee_profile_id else None

    @agent_id.setter
    def agent_id(self, value):
        self.employee_profile = _resolve_user_profile(value, 'employee_profile')

    def clean(self):
        super().clean()
        errors = {}
        if self.client_profile_id and self.client_profile.user.user_type != 'client':
            errors['client_profile'] = 'Р’ РїРѕР»Рµ РєР»РёРµРЅС‚Р° РјРѕР¶РЅРѕ РІС‹Р±СЂР°С‚СЊ С‚РѕР»СЊРєРѕ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ С‚РёРїР° "РљР»РёРµРЅС‚".'
        if self.employee_profile_id and self.employee_profile.user.user_type != 'employee':
            errors['employee_profile'] = 'Р’ РїРѕР»Рµ СЃРѕС‚СЂСѓРґРЅРёРєР° РјРѕР¶РЅРѕ РІС‹Р±СЂР°С‚СЊ С‚РѕР»СЊРєРѕ СЃРѕС‚СЂСѓРґРЅРёРєР°.'
        if self.min_price is not None and self.max_price is not None and self.min_price > self.max_price:
            errors['min_price'] = 'РњРёРЅРёРјР°Р»СЊРЅР°СЏ С†РµРЅР° РЅРµ РјРѕР¶РµС‚ Р±С‹С‚СЊ Р±РѕР»СЊС€Рµ РјР°РєСЃРёРјР°Р»СЊРЅРѕР№.'
        if self.min_area is not None and self.max_area is not None and self.min_area > self.max_area:
            errors['min_area'] = 'РњРёРЅРёРјР°Р»СЊРЅР°СЏ РїР»РѕС‰Р°РґСЊ РЅРµ РјРѕР¶РµС‚ Р±С‹С‚СЊ Р±РѕР»СЊС€Рµ РјР°РєСЃРёРјР°Р»СЊРЅРѕР№.'
        if self.property_type and self.property_type.code == 'commercial' and self.rooms_count is not None:
            errors['rooms_count'] = 'Р”Р»СЏ РѕС„РёСЃР° РёР»Рё СЃРєР»Р°РґР° РєРѕР»РёС‡РµСЃС‚РІРѕ РєРѕРјРЅР°С‚ РЅРµ РёСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ.'
        if self.rooms_count is not None and self.rooms_count < 0:
            errors['rooms_count'] = 'РљРѕР»РёС‡РµСЃС‚РІРѕ РєРѕРјРЅР°С‚ РЅРµ РјРѕР¶РµС‚ Р±С‹С‚СЊ РѕС‚СЂРёС†Р°С‚РµР»СЊРЅС‹Рј.'
        if self.closed_at and not self.status_id:
            errors['closed_at'] = 'РџРµСЂРµРґ Р·Р°РєСЂС‹С‚РёРµРј Р·Р°СЏРІРєРё РЅСѓР¶РЅРѕ СѓРєР°Р·Р°С‚СЊ СЃС‚Р°С‚СѓСЃ.'
        if errors:
            raise ValidationError(errors)

    @classmethod
    def normalize_status_code(cls, code: str | None) -> str | None:
        if code is None:
            return None
        return cls.LEGACY_STATUS_CODE_ALIASES.get(code, code)

    @classmethod
    def expand_status_filter_codes(
        cls,
        codes: list[str] | tuple[str, ...],
    ) -> tuple[str, ...]:
        expanded: list[str] = []
        reverse_aliases = {
            current: legacy
            for legacy, current in cls.LEGACY_STATUS_CODE_ALIASES.items()
        }
        for code in codes:
            normalized = (code or '').strip()
            if not normalized:
                continue
            for candidate in (
                normalized,
                cls.LEGACY_STATUS_CODE_ALIASES.get(normalized),
                reverse_aliases.get(normalized),
            ):
                if candidate and candidate not in expanded:
                    expanded.append(candidate)
        return tuple(expanded)

    @_property
    def status_code(self) -> str | None:
        if not self.status_id:
            return None
        return self.normalize_status_code(self.status.code)

    @_property
    def status_display_name(self) -> str | None:
        if not self.status_id:
            return None
        raw_code = self.status.code
        if raw_code in self.LEGACY_STATUS_CODE_ALIASES:
            normalized_code = self.normalize_status_code(raw_code)
            return self.STATUS_DISPLAY_NAMES.get(normalized_code, self.status.name)
        return self.status.name

    @_property
    def is_terminal(self) -> bool:
        return self.status_code in self.TERMINAL_STATUS_CODES


class RequestPropertyMatch(models.Model):
    """Р’Р°СЂРёР°РЅС‚ РѕР±СЉРµРєС‚Р° РїРѕ Р·Р°СЏРІРєРµ РєР»РёРµРЅС‚Р°."""
    QUERY_ALIASES = {
        'agent': 'employee_profile__user',
        'agent_id': 'employee_profile__user_id',
        'request__client': 'request__client_profile__user',
        'request__client_id': 'request__client_profile__user_id',
        'request__agent': 'request__employee_profile__user',
        'request__agent_id': 'request__employee_profile__user_id',
    }
    objects = AliasManager()

    request = models.ForeignKey(Request, on_delete=models.CASCADE,
                                verbose_name='Р—Р°СЏРІРєР°',
                                related_name='matches')
    property = models.ForeignKey('Property', on_delete=models.PROTECT,
                                 verbose_name='РћР±СЉРµРєС‚',
                                 related_name='request_matches')
    employee_profile = models.ForeignKey(EmployeeProfile, on_delete=models.PROTECT,
                                         related_name='proposed_matches',
                                         verbose_name='РЎРѕС‚СЂСѓРґРЅРёРє')
    status = models.ForeignKey(RequestMatchStatus, on_delete=models.PROTECT,
                               verbose_name='РЎС‚Р°С‚СѓСЃ', default=1)
    agent_note = models.TextField(blank=True, null=True, verbose_name='Р—Р°РјРµС‚РєР° СЃРѕС‚СЂСѓРґРЅРёРєР°')
    confirmed_at = models.DateTimeField(blank=True, null=True, verbose_name='Р”Р°С‚Р° РїРѕРґС‚РІРµСЂР¶РґРµРЅРёСЏ')
    confirmed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        blank=True, null=True,
        related_name='confirmed_request_matches',
        limit_choices_to={'user_type_ref__code': 'employee'},
        verbose_name='РџРѕРґС‚РІРµСЂРґРёР»',
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Р”Р°С‚Р° СЃРѕР·РґР°РЅРёСЏ')

    class Meta:
        db_table = 'request_property_matches'
        verbose_name = 'Р’Р°СЂРёР°РЅС‚ РїРѕ Р·Р°СЏРІРєРµ'
        verbose_name_plural = 'Р’Р°СЂРёР°РЅС‚С‹ РїРѕ Р·Р°СЏРІРєР°Рј'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['request', 'property'],
                                    name='unique_request_property_match'),
        ]

    def __str__(self):
        return f'Р—Р°СЏРІРєР° в„–{self.request_id} в†” РѕР±СЉРµРєС‚ в„–{self.property_id}'

    @_property
    def agent(self):
        return self.employee_profile.user if self.employee_profile_id else None

    @agent.setter
    def agent(self, value):
        self.employee_profile = _resolve_user_profile(value, 'employee_profile')

    @_property
    def agent_id(self):
        return self.employee_profile.user_id if self.employee_profile_id else None

    @agent_id.setter
    def agent_id(self, value):
        self.employee_profile = _resolve_user_profile(value, 'employee_profile')

    @_property
    def state_code(self) -> str:
        if self.status_id:
            return self.status.code
        return 'draft'


class Deal(models.Model):
    """РЎРґРµР»РєР° РїРѕ РѕР±СЉРµРєС‚Сѓ Рё РєР»РёРµРЅС‚Сѓ."""
    deal_number = models.CharField(max_length=50, unique=True, verbose_name='РќРѕРјРµСЂ СЃРґРµР»РєРё')
    property = models.ForeignKey(Property, on_delete=models.PROTECT,
                                 verbose_name='РћР±СЉРµРєС‚',
                                 related_name='deals')
    client = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='client_deals',
        verbose_name='РљР»РёРµРЅС‚',
        blank=True,
        null=True,
        limit_choices_to={'user_type_ref__code': 'client'},
    )
    agent = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='agent_deals',
        verbose_name='РђРіРµРЅС‚',
        blank=True,
        null=True,
        limit_choices_to={'user_type_ref__code': 'employee'},
    )
    employee_profile = models.ForeignKey(
        EmployeeProfile,
        on_delete=models.PROTECT,
        related_name='deals',
        verbose_name='РЎРѕС‚СЂСѓРґРЅРёРє',
        blank=True,
        null=True,
    )
    operation_type = models.ForeignKey(OperationType, on_delete=models.PROTECT,
                                       verbose_name='РўРёРї РѕРїРµСЂР°С†РёРё',
                                       related_name='deals')
    status = models.ForeignKey(DealStatus, on_delete=models.PROTECT,
                               related_name='deals',
                               verbose_name='РЎС‚Р°С‚СѓСЃ',
                               blank=True, null=True)

    request = models.OneToOneField(
        Request, on_delete=models.SET_NULL,
        related_name='deal', blank=True, null=True,
        verbose_name='Р—Р°СЏРІРєР°',
    )

    price_final = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0)], verbose_name='РС‚РѕРіРѕРІР°СЏ С†РµРЅР°')
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2,
                                             blank=True, null=True,
                                             verbose_name='РџСЂРѕС†РµРЅС‚ РєРѕРјРёСЃСЃРёРё',
                                             validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))])
    commission_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
        verbose_name='РЎСѓРјРјР° РєРѕРјРёСЃСЃРёРё',
    )
    deal_date = models.DateField(verbose_name='Р”Р°С‚Р° СЃРґРµР»РєРё')
    notes = models.TextField(blank=True, null=True, verbose_name='РџСЂРёРјРµС‡Р°РЅРёСЏ')

    contract_status_ref = models.ForeignKey(
        ContractStatus,
        on_delete=models.PROTECT,
        related_name='deals',
        verbose_name='РЎС‚Р°С‚СѓСЃ РґРѕРіРѕРІРѕСЂР°',
        default=1,
    )
    contract_file = models.FileField(
        upload_to='deals/contracts/%Y/%m/',
        blank=True,
        null=True,
        verbose_name='Р¤Р°Р№Р» РґРѕРіРѕРІРѕСЂР°',
    )
    contract_error_message = models.TextField(
        blank=True,
        null=True,
        verbose_name='РџСЂРёС‡РёРЅР° РѕС€РёР±РєРё РґРѕРіРѕРІРѕСЂР°',
    )
    contract_requested_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Р”Р°С‚Р° Р·Р°РїСЂРѕСЃР° РґРѕРіРѕРІРѕСЂР°',
    )
    contract_processing_started_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Р”Р°С‚Р° РЅР°С‡Р°Р»Р° С„РѕСЂРјРёСЂРѕРІР°РЅРёСЏ РґРѕРіРѕРІРѕСЂР°',
    )
    contract_generated_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Р”Р°С‚Р° С„РѕСЂРјРёСЂРѕРІР°РЅРёСЏ РґРѕРіРѕРІРѕСЂР°',
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Р”Р°С‚Р° СЃРѕР·РґР°РЅРёСЏ')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Р”Р°С‚Р° РѕР±РЅРѕРІР»РµРЅРёСЏ')

    class Meta:
        db_table = 'deals'
        verbose_name = 'РЎРґРµР»РєР°'
        verbose_name_plural = 'РЎРґРµР»РєРё'
        ordering = ['-deal_date']
        constraints = [
            models.CheckConstraint(condition=models.Q(price_final__gte=0), name='deal_price_final_non_negative'),
            models.CheckConstraint(
                condition=(
                    models.Q(commission_percent__isnull=True)
                    | (models.Q(commission_percent__gte=Decimal('0')) & models.Q(commission_percent__lte=Decimal('100')))
                ),
                name='deal_commission_percent_range',
            ),
            models.CheckConstraint(
                condition=models.Q(commission_amount__isnull=True) | models.Q(commission_amount__gte=0),
                name='deal_commission_amount_non_negative',
            ),
        ]

    QUERY_ALIASES = {
        'contract_status': 'contract_status_ref__code',
        'contract_status_id': 'contract_status_ref_id',
    }
    objects = AliasManager()

    def __str__(self):
        return f'РЎРґРµР»РєР° {self.deal_number}'

    def __init__(self, *args, **kwargs):
        legacy_contract_status = kwargs.pop('contract_status', None)
        has_contract_status_ref = (
            'contract_status_ref' in kwargs or 'contract_status_ref_id' in kwargs
        )
        super().__init__(*args, **kwargs)
        if legacy_contract_status not in (None, '') and not has_contract_status_ref:
            self.contract_status = legacy_contract_status

    def clean(self):
        super().clean()
        errors = {}
        if self.client_id and self.client.user_type != 'client':
            errors['client'] = 'РљР»РёРµРЅС‚РѕРј СЃРґРµР»РєРё РјРѕР¶РµС‚ Р±С‹С‚СЊ С‚РѕР»СЊРєРѕ РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ С‚РёРїР° "РљР»РёРµРЅС‚".'
        if self.agent_id and self.agent.user_type != 'employee':
            errors['agent'] = 'РђРіРµРЅС‚РѕРј СЃРґРµР»РєРё РјРѕР¶РµС‚ Р±С‹С‚СЊ С‚РѕР»СЊРєРѕ СЃРѕС‚СЂСѓРґРЅРёРє.'
        if self.employee_profile_id and self.employee_profile.user.user_type != 'employee':
            errors['employee_profile'] = 'РЎРѕС‚СЂСѓРґРЅРёРєРѕРј СЃРґРµР»РєРё РјРѕР¶РµС‚ Р±С‹С‚СЊ С‚РѕР»СЊРєРѕ СЃРѕС‚СЂСѓРґРЅРёРє.'
        if self.request_id and self.client_id and self.request.client_profile.user_id != self.client_id:
            errors['client'] = 'РљР»РёРµРЅС‚ СЃРґРµР»РєРё РґРѕР»Р¶РµРЅ СЃРѕРІРїР°РґР°С‚СЊ СЃ РєР»РёРµРЅС‚РѕРј Р·Р°СЏРІРєРё.'
        if self.request_id and self.agent_id and self.request.employee_profile_id:
            request_agent_user_id = self.request.employee_profile.user_id
            if request_agent_user_id != self.agent_id:
                errors['agent'] = 'РђРіРµРЅС‚ СЃРґРµР»РєРё РґРѕР»Р¶РµРЅ СЃРѕРІРїР°РґР°С‚СЊ СЃ СЃРѕС‚СЂСѓРґРЅРёРєРѕРј Р·Р°СЏРІРєРё.'
        if self.price_final is not None and self.price_final < 0:
            errors['price_final'] = 'РС‚РѕРіРѕРІР°СЏ С†РµРЅР° РЅРµ РјРѕР¶РµС‚ Р±С‹С‚СЊ РѕС‚СЂРёС†Р°С‚РµР»СЊРЅРѕР№.'
        if self.commission_percent is not None and not (Decimal('0') <= self.commission_percent <= Decimal('100')):
            errors['commission_percent'] = 'РџСЂРѕС†РµРЅС‚ РєРѕРјРёСЃСЃРёРё РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ РѕС‚ 0 РґРѕ 100.'
        if self.commission_amount is not None and self.commission_amount < 0:
            errors['commission_amount'] = 'РЎСѓРјРјР° РєРѕРјРёСЃСЃРёРё РЅРµ РјРѕР¶РµС‚ Р±С‹С‚СЊ РѕС‚СЂРёС†Р°С‚РµР»СЊРЅРѕР№.'
        if self.contract_status == 'ready' and not self.contract_file:
            errors['contract_file'] = 'Р”Р»СЏ СЃС‚Р°С‚СѓСЃР° "Р“РѕС‚РѕРІ" РЅСѓР¶РЅРѕ РїСЂРёРєСЂРµРїРёС‚СЊ С„Р°Р№Р» РґРѕРіРѕРІРѕСЂР°.'
        if self.contract_status == 'failed' and not self.contract_error_message:
            errors['contract_error_message'] = 'Р”Р»СЏ СЃС‚Р°С‚СѓСЃР° РѕС€РёР±РєРё РЅСѓР¶РЅРѕ СѓРєР°Р·Р°С‚СЊ РїСЂРёС‡РёРЅСѓ.'
        if errors:
            raise ValidationError(errors)

    @_property
    def contract_status(self) -> str | None:
        return self.contract_status_ref.code if self.contract_status_ref_id else None

    @contract_status.setter
    def contract_status(self, value):
        self.contract_status_ref = _resolve_lookup_instance(ContractStatus, value)

    def get_contract_status_display(self) -> str:
        if not self.contract_status_ref_id:
            return ''
        return self.contract_status_ref.name

    def save(self, *args, **kwargs):
        _rewrite_legacy_update_fields(self, kwargs)
        if self.client_id is None and self.request_id:
            self.client = self.request.client_profile.user
        if self.agent_id is None:
            if self.employee_profile_id:
                self.agent = self.employee_profile.user
            elif self.request_id and self.request.employee_profile_id:
                self.agent = self.request.employee_profile.user
        if self.employee_profile_id is None and self.agent_id and hasattr(self.agent, 'employee_profile'):
            self.employee_profile = self.agent.employee_profile
        if self.commission_amount is None and self.price_final is not None and self.commission_percent is not None:
            self.commission_amount = (
                Decimal(str(self.price_final))
                * Decimal(str(self.commission_percent))
                / Decimal('100')
            ).quantize(Decimal('0.01'))
        return super().save(*args, **kwargs)


class DealParticipant(models.Model):
    """РЈС‡Р°СЃС‚РЅРёРє СЃРґРµР»РєРё (РєР»РёРµРЅС‚ СЃ СЂРѕР»СЊСЋ)."""
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name='participants', verbose_name='РЎРґРµР»РєР°')
    client_profile = models.ForeignKey(ClientProfile, on_delete=models.PROTECT, related_name='deals', verbose_name='РљР»РёРµРЅС‚')
    role = models.ForeignKey(DealParticipantRole, on_delete=models.PROTECT, verbose_name='Р РѕР»СЊ')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Р”Р°С‚Р° СЃРѕР·РґР°РЅРёСЏ')

    class Meta:
        db_table = 'deal_participants'
        verbose_name = 'РЈС‡Р°СЃС‚РЅРёРє СЃРґРµР»РєРё'
        verbose_name_plural = 'РЈС‡Р°СЃС‚РЅРёРєРё СЃРґРµР»РѕРє'
        unique_together = [['deal', 'client_profile', 'role']]

    def __str__(self):
        return f'{self.deal.deal_number} в†’ {self.client_profile} ({self.role})'


class DealDocument(models.Model):
    """Р”РѕРєСѓРјРµРЅС‚ СЃРґРµР»РєРё."""
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name='documents', verbose_name='РЎРґРµР»РєР°')
    document_type = models.ForeignKey(DocumentType, on_delete=models.PROTECT, verbose_name='РўРёРї РґРѕРєСѓРјРµРЅС‚Р°')
    file_url = models.TextField(blank=True, null=True, verbose_name='URL С„Р°Р№Р»Р°')
    document_number = models.CharField(max_length=50, blank=True, null=True, verbose_name='РќРѕРјРµСЂ РґРѕРєСѓРјРµРЅС‚Р°')
    template_path = models.CharField(max_length=255, blank=True, null=True, verbose_name='РџСѓС‚СЊ Рє С€Р°Р±Р»РѕРЅСѓ')
    generated_at = models.DateTimeField(blank=True, null=True, verbose_name='Р”Р°С‚Р° РіРµРЅРµСЂР°С†РёРё')
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, verbose_name='РЎРіРµРЅРµСЂРёСЂРѕРІР°Р»')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Р”Р°С‚Р° СЃРѕР·РґР°РЅРёСЏ')

    class Meta:
        db_table = 'deal_documents'
        verbose_name = 'Р”РѕРєСѓРјРµРЅС‚ СЃРґРµР»РєРё'
        verbose_name_plural = 'Р”РѕРєСѓРјРµРЅС‚С‹ СЃРґРµР»РѕРє'

    def __str__(self):
        return f'{self.deal.deal_number} в†’ {self.document_type.name}'


class Task(models.Model):
    """Р—Р°РґР°С‡Р° СЃРѕС‚СЂСѓРґРЅРёРєР°."""
    TERMINAL_STATUS_CODES = ('done', 'cancelled')
    PRIORITY_LOW = 'low'
    PRIORITY_NORMAL = 'normal'
    PRIORITY_HIGH = 'high'
    PRIORITY_CHOICES = _lookup_choices(
        'TaskPriority',
        (
            PRIORITY_LOW,
            PRIORITY_NORMAL,
            PRIORITY_HIGH,
        ),
    )
    TASK_TYPE_CONTACT_CLIENT = 'contact_client'
    TASK_TYPE_PROPERTY_SEARCH = 'property_search'
    TASK_TYPE_SHOWING = 'showing'
    TASK_TYPE_DOCUMENTS = 'documents'
    TASK_TYPE_CALL = 'call'
    TASK_TYPE_OTHER = 'other'
    TASK_TYPE_CHOICES = _lookup_choices(
        'TaskType',
        (
            TASK_TYPE_CONTACT_CLIENT,
            TASK_TYPE_PROPERTY_SEARCH,
            TASK_TYPE_SHOWING,
            TASK_TYPE_DOCUMENTS,
            TASK_TYPE_CALL,
            TASK_TYPE_OTHER,
        ),
    )

    title = models.CharField(max_length=255, verbose_name='РќР°Р·РІР°РЅРёРµ')
    description = models.TextField(blank=True, null=True, verbose_name='РћРїРёСЃР°РЅРёРµ')
    priority_ref = models.ForeignKey(
        TaskPriority,
        on_delete=models.PROTECT,
        related_name='tasks',
        verbose_name='РџСЂРёРѕСЂРёС‚РµС‚',
        default=2,
    )
    task_type_ref = models.ForeignKey(
        TaskType,
        on_delete=models.PROTECT,
        related_name='tasks',
        verbose_name='РўРёРї Р·Р°РґР°С‡',
        default=6,
    )
    status = models.ForeignKey(TaskStatus, on_delete=models.PROTECT,
                               verbose_name='РЎС‚Р°С‚СѓСЃ',
                               related_name='tasks')

    assignee = models.ForeignKey(User, on_delete=models.PROTECT,
                                 related_name='assigned_tasks',
                                 verbose_name='РСЃРїРѕР»РЅРёС‚РµР»СЊ',
                                 limit_choices_to={'user_type_ref__code': 'employee'})
    created_by = models.ForeignKey(User, on_delete=models.PROTECT,
                                   verbose_name='РЎРѕР·РґР°С‚РµР»СЊ',
                                   related_name='created_tasks')

    client_profile = models.ForeignKey(ClientProfile, on_delete=models.SET_NULL,
                                       blank=True, null=True,
                                       related_name='tasks',
                                       verbose_name='РљР»РёРµРЅС‚')
    property = models.ForeignKey(Property, on_delete=models.SET_NULL,
                                 verbose_name='РћР±СЉРµРєС‚',
                                 blank=True, null=True, related_name='tasks')
    request = models.ForeignKey(Request, on_delete=models.SET_NULL,
                                verbose_name='Р—Р°СЏРІРєР°',
                                blank=True, null=True, related_name='tasks')
    deal = models.ForeignKey(Deal, on_delete=models.SET_NULL,
                             verbose_name='РЎРґРµР»РєР°',
                             blank=True, null=True, related_name='tasks')

    due_date = models.DateTimeField(blank=True, null=True, verbose_name='РЎСЂРѕРє')
    completed_at = models.DateTimeField(blank=True, null=True, verbose_name='Р—Р°РєСЂС‹С‚Р°')
    result = models.TextField(blank=True, null=True,
                              verbose_name='Р РµР·СѓР»СЊС‚Р°С‚',
                              help_text='Р РµР·СѓР»СЊС‚Р°С‚ РІС‹РїРѕР»РЅРµРЅРёСЏ Р·Р°РґР°С‡Рё')
    steps_log = models.JSONField(
        default=list, blank=True,
        help_text='Р–СѓСЂРЅР°Р» СЌС‚Р°РїРѕРІ РІС‹РїРѕР»РЅРµРЅРёСЏ (СЃРїРёСЃРѕРє РѕР±СЉРµРєС‚РѕРІ).',
        verbose_name='Р–СѓСЂРЅР°Р» СЌС‚Р°РїРѕРІ',
    )
    is_auto_closed = models.BooleanField(default=False,
                                         verbose_name='Р—Р°РєСЂС‹С‚Р° Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё',
                                         help_text='Р—Р°РєСЂС‹С‚Р° Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё СЃРёСЃС‚РµРјРѕР№')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Р”Р°С‚Р° СЃРѕР·РґР°РЅРёСЏ')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Р”Р°С‚Р° РѕР±РЅРѕРІР»РµРЅРёСЏ')

    class Meta:
        db_table = 'tasks'
        verbose_name = 'Р—Р°РґР°С‡Р°'
        verbose_name_plural = 'Р—Р°РґР°С‡Рё'
        ordering = ['-created_at']

    QUERY_ALIASES = {
        'priority': 'priority_ref__code',
        'priority_id': 'priority_ref_id',
        'task_type': 'task_type_ref__code',
        'task_type_id': 'task_type_ref_id',
        'client': 'client_profile__user',
        'client_id': 'client_profile__user_id',
    }
    objects = AliasManager()

    def __str__(self):
        return self.title

    @_property
    def client(self):
        return self.client_profile.user if self.client_profile_id else None

    @client.setter
    def client(self, value):
        self.client_profile = _resolve_user_profile(value, 'client_profile')

    @_property
    def client_id(self):
        return self.client_profile.user_id if self.client_profile_id else None

    @client_id.setter
    def client_id(self, value):
        self.client_profile = _resolve_user_profile(value, 'client_profile')

    def __init__(self, *args, **kwargs):
        legacy_priority = kwargs.pop('priority', None)
        legacy_task_type = kwargs.pop('task_type', None)
        has_priority_ref = 'priority_ref' in kwargs or 'priority_ref_id' in kwargs
        has_task_type_ref = 'task_type_ref' in kwargs or 'task_type_ref_id' in kwargs
        super().__init__(*args, **kwargs)
        if legacy_priority not in (None, '') and not has_priority_ref:
            self.priority = legacy_priority
        if legacy_task_type not in (None, '') and not has_task_type_ref:
            self.task_type = legacy_task_type

    def clean(self):
        super().clean()
        errors = {}
        if self.assignee_id and self.assignee.user_type != 'employee':
            errors['assignee'] = 'РСЃРїРѕР»РЅРёС‚РµР»РµРј Р·Р°РґР°С‡Рё РјРѕР¶РµС‚ Р±С‹С‚СЊ С‚РѕР»СЊРєРѕ СЃРѕС‚СЂСѓРґРЅРёРє.'
        if self.created_by_id and self.created_by.user_type != 'employee':
            errors['created_by'] = 'РЎРѕР·РґР°С‚РµР»РµРј Р·Р°РґР°С‡Рё РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ СЃРѕС‚СЂСѓРґРЅРёРє.'
        if self.client_profile_id and self.client_profile.user.user_type != 'client':
            errors['client_profile'] = 'Р’ РїРѕР»Рµ РєР»РёРµРЅС‚Р° РјРѕР¶РЅРѕ РІС‹Р±СЂР°С‚СЊ С‚РѕР»СЊРєРѕ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ С‚РёРїР° "РљР»РёРµРЅС‚".'
        if self.completed_at and self.status_id and self.status.code not in self.TERMINAL_STATUS_CODES:
            errors['completed_at'] = 'Р”Р°С‚Р° Р·Р°РІРµСЂС€РµРЅРёСЏ РґРѕРїСѓСЃРєР°РµС‚СЃСЏ С‚РѕР»СЊРєРѕ РґР»СЏ С„РёРЅР°Р»СЊРЅРѕРіРѕ СЃС‚Р°С‚СѓСЃР° Р·Р°РґР°С‡Рё.'
        if errors:
            raise ValidationError(errors)

    @_property
    def is_completed(self):
        return (self.status_id is not None
                and self.status.code in self.TERMINAL_STATUS_CODES)

    @_property
    def is_terminal(self):
        return self.is_completed

    @_property
    def task_type_display(self):
        if not self.task_type_ref_id:
            return self.task_type or ''
        return self.task_type_ref.name

    @_property
    def priority(self) -> str | None:
        return self.priority_ref.code if self.priority_ref_id else None

    @priority.setter
    def priority(self, value):
        self.priority_ref = _resolve_lookup_instance(TaskPriority, value)

    def get_priority_display(self) -> str:
        if not self.priority_ref_id:
            return ''
        return self.priority_ref.name

    @_property
    def task_type(self) -> str | None:
        return self.task_type_ref.code if self.task_type_ref_id else None

    @task_type.setter
    def task_type(self, value):
        self.task_type_ref = _resolve_lookup_instance(TaskType, value)

    def get_task_type_display(self) -> str:
        if not self.task_type_ref_id:
            return ''
        return self.task_type_ref.name

    def save(self, *args, **kwargs):
        _rewrite_legacy_update_fields(self, kwargs)
        return super().save(*args, **kwargs)


# =====================================================
# 7. РђРЈР”РРў, РџРћР§РўРђ, Р Р•Р—Р•Р Р’РќРћР• РљРћРџРР РћР’РђРќРР•
# =====================================================

class OutgoingEmail(models.Model):
    """РћС‡РµСЂРµРґСЊ РёСЃС…РѕРґСЏС‰РёС… РїРёСЃРµРј."""
    STATUS_CHOICES = [
        ('processing', 'РћР±СЂР°Р±Р°С‚С‹РІР°РµС‚СЃСЏ'),
        ('pending', 'РћР¶РёРґР°РµС‚ РѕС‚РїСЂР°РІРєРё'),
        ('sent', 'РћС‚РїСЂР°РІР»РµРЅРѕ'),
        ('failed', 'РћС€РёР±РєР° РѕС‚РїСЂР°РІРєРё'),
    ]

    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='outgoing_emails',
        verbose_name='РџРѕР»СѓС‡Р°С‚РµР»СЊ',
    )
    sender = models.ForeignKey(User, on_delete=models.SET_NULL,
                               blank=True, null=True,
                               related_name='sent_emails',
                               verbose_name='РћС‚РїСЂР°РІРёС‚РµР»СЊ',
                               limit_choices_to={'user_type_ref__code': 'employee'})
    subject = models.CharField(max_length=255, verbose_name='РўРµРјР°')
    body = models.TextField(verbose_name='РўРµРєСЃС‚ РїРёСЃСЊРјР°')
    html_body = models.TextField(blank=True, default='', verbose_name='HTML-С‚РµРєСЃС‚')
    trigger_code = models.CharField(max_length=64, blank=True, null=True, db_index=True, verbose_name='Trigger code')
    context = models.JSONField(default=dict, blank=True, verbose_name='РљРѕРЅС‚РµРєСЃС‚')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES,
                              verbose_name='РЎС‚Р°С‚СѓСЃ',
                              default='pending', db_index=True)

    task = models.ForeignKey(Task, on_delete=models.SET_NULL,
                             verbose_name='Р—Р°РґР°С‡Р°',
                             blank=True, null=True, related_name='emails')
    request = models.ForeignKey(Request, on_delete=models.SET_NULL,
                                verbose_name='Р—Р°СЏРІРєР°',
                                blank=True, null=True, related_name='emails')
    property = models.ForeignKey(Property, on_delete=models.SET_NULL,
                                 verbose_name='РћР±СЉРµРєС‚',
                                 blank=True, null=True, related_name='emails')

    error_message = models.TextField(blank=True, null=True, verbose_name='Error message')
    processing_started_at = models.DateTimeField(blank=True, null=True, verbose_name='Р”Р°С‚Р° РЅР°С‡Р°Р»Р° РѕР±СЂР°Р±РѕС‚РєРё')
    sent_at = models.DateTimeField(blank=True, null=True, verbose_name='Р”Р°С‚Р° РѕС‚РїСЂР°РІРєРё')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Р”Р°С‚Р° СЃРѕР·РґР°РЅРёСЏ')

    class Meta:
        db_table = 'outgoing_emails'
        verbose_name = 'РСЃС…РѕРґСЏС‰РµРµ РїРёСЃСЊРјРѕ'
        verbose_name_plural = 'РСЃС…РѕРґСЏС‰РёРµ РїРёСЃСЊРјР°'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=['processing', 'pending', 'sent', 'failed']),
                name='outgoing_email_status_valid',
            ),
        ]

    def __str__(self):
        return f'{self.subject} в†’ {self.recipient.email}'

    def clean(self):
        super().clean()
        errors = {}
        if self.sender_id and self.sender.user_type != 'employee':
            errors['sender'] = 'РћС‚РїСЂР°РІРёС‚РµР»РµРј РјРѕР¶РµС‚ Р±С‹С‚СЊ С‚РѕР»СЊРєРѕ СЃРѕС‚СЂСѓРґРЅРёРє.'
        if self.status == 'sent' and not self.sent_at:
            errors['sent_at'] = 'Р”Р»СЏ РѕС‚РїСЂР°РІР»РµРЅРЅРѕРіРѕ РїРёСЃСЊРјР° РЅСѓР¶РЅРѕ СѓРєР°Р·Р°С‚СЊ РґР°С‚Сѓ РѕС‚РїСЂР°РІРєРё.'
        if self.status == 'failed' and not self.error_message:
            errors['error_message'] = 'Р”Р»СЏ РѕС€РёР±РєРё РѕС‚РїСЂР°РІРєРё РЅСѓР¶РЅРѕ СѓРєР°Р·Р°С‚СЊ РїСЂРёС‡РёРЅСѓ.'
        if errors:
            raise ValidationError(errors)


class AuditLog(models.Model):
    """Р•РґРёРЅС‹Р№ Р¶СѓСЂРЅР°Р» Р·РЅР°С‡РёРјС‹С… РґРµР№СЃС‚РІРёР№ СЃРёСЃС‚РµРјС‹."""

    entity_type = models.ForeignKey(AuditEntityType, on_delete=models.PROTECT, verbose_name='РўРёРї СЃСѓС‰РЅРѕСЃС‚Рё')
    entity_id = models.PositiveIntegerField(db_index=True, verbose_name='РРґРµРЅС‚РёС„РёРєР°С‚РѕСЂ СЃСѓС‰РЅРѕСЃС‚Рё')
    action = models.ForeignKey(AuditAction, on_delete=models.PROTECT, verbose_name='Р”РµР№СЃС‚РІРёРµ')
    message = models.TextField(verbose_name='РЎРѕРѕР±С‰РµРЅРёРµ')
    metadata = models.JSONField(default=dict, blank=True, verbose_name='РњРµС‚Р°РґР°РЅРЅС‹Рµ')

    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='audit_logs',
        verbose_name='РРЅРёС†РёР°С‚РѕСЂ',
    )
    created_at = models.DateTimeField(default=timezone.now, db_index=True, verbose_name='Р”Р°С‚Р° СЃРѕР·РґР°РЅРёСЏ')

    class Meta:
        db_table = 'audit_logs'
        verbose_name = 'Р—Р°РїРёСЃСЊ Р¶СѓСЂРЅР°Р»Р°'
        verbose_name_plural = 'Р–СѓСЂРЅР°Р» РґРµР№СЃС‚РІРёР№'
        ordering = ['-created_at', '-id']

    @property
    def action_code(self):
        return self.action.code if self.action_id else None

    @property
    def action_label(self):
        return self.action.name if self.action_id else ''

    def get_entity_type_display(self):
        return self.entity_type.name if self.entity_type_id else ''

    @property
    def property(self):
        return None

    @_property
    def request(self):
        return None

    @_property
    def task(self):
        return None

    @_property
    def deal(self):
        return None

    def __str__(self):
        return f'{self.entity_type.name} #{self.entity_id}: {self.action.name}'


class DatabaseBackup(models.Model):
    """РЎРѕС…СЂР°РЅРµРЅРЅС‹Р№ С„Р°Р№Р» РїРѕР»РЅРѕР№ СЂРµР·РµСЂРІРЅРѕР№ РєРѕРїРёРё Р±Р°Р·С‹ РґР°РЅРЅС‹С…."""

    filename = models.CharField(max_length=255, verbose_name='РРјСЏ С„Р°Р№Р»Р°')
    file = models.FileField(
        storage=database_backup_storage,
        upload_to='database_backups/%Y/%m/',
        verbose_name='Р¤Р°Р№Р»',
    )
    size_bytes = models.PositiveBigIntegerField(default=0, verbose_name='Size bytes')
    database_name = models.CharField(max_length=255, verbose_name='РќР°Р·РІР°РЅРёРµ Р±Р°Р·С‹ РґР°РЅРЅС‹С…')
    engine_label = models.CharField(max_length=120, verbose_name='РЎРЈР‘Р”')
    tool_label = models.CharField(max_length=120, blank=True, default='', verbose_name='РРЅСЃС‚СЂСѓРјРµРЅС‚')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='database_backups',
        verbose_name='РЎРѕР·РґР°С‚РµР»СЊ',
    )
    created_at = models.DateTimeField(default=timezone.now, db_index=True, verbose_name='Р”Р°С‚Р° СЃРѕР·РґР°РЅРёСЏ')

    class Meta:
        db_table = 'database_backups'
        verbose_name = 'Р РµР·РµСЂРІРЅР°СЏ РєРѕРїРёСЏ Р‘Р”'
        verbose_name_plural = 'Р РµР·РµСЂРІРЅС‹Рµ РєРѕРїРёРё Р‘Р”'
        ordering = ['-created_at', '-id']

    def __str__(self):
        return self.filename
