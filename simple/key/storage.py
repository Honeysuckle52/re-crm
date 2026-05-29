"""Private file storages used by the CRM backend."""

from django.conf import settings
from django.core.files.storage import FileSystemStorage


def database_backup_storage():
    return FileSystemStorage(location=settings.DATABASE_BACKUP_ROOT, base_url=None)
