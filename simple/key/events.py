"""Доменные события CRM."""
from django.dispatch import Signal


request_client_matched = Signal()

viewing_completed = Signal()

deal_created = Signal()

request_closed = Signal()
