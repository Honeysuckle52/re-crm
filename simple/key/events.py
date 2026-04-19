"""
Доменные события CRM.

Соглашение: триггерящая сторона (ViewSet или сервис) отправляет сигнал
после успешной модификации состояния, ресиверы в ``signals.py``
реагируют (автозакрытие задач, запись KPI, постановка письма в очередь).

Важно: отправлять сигнал нужно ВНУТРИ транзакции, а побочные эффекты
с внешним миром (SMTP) выполнять через ``transaction.on_commit`` —
чтобы письмо не ушло, если транзакция откатилась.
"""
from django.dispatch import Signal


# kwargs: request, property, agent, match
#   request  — :class:`key.models.Request`
#   property — :class:`key.models.Property`
#   agent    — :class:`key.models.User` (агент, предложивший/подтвердивший)
#   match    — :class:`key.models.RequestPropertyMatch` (может быть None
#              при прямом событии, но для сценария «подобрал клиента»
#              всегда есть)
request_client_matched = Signal()


# kwargs: viewing (PropertyViewing), agent, client
viewing_completed = Signal()


# kwargs: deal (Deal), agent, client
deal_created = Signal()


# kwargs: request (Request), actor (User, кто закрыл)
request_closed = Signal()
