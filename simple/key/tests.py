# -*- coding: utf-8 -*-
import io
import json
import shutil
import sys
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from reportlab.pdfbase import pdfmetrics
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.test import APIClient

from . import deals_service, documents, mailing, models, reports, task_actions
from .xlsx_utils import WorkbookSheet, build_xlsx_bytes, load_xlsx_rows


class AuthLogoutTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.user = models.User.objects.create_user(
            username='logout-user',
            email='logout-user@example.com',
            password='Secret123!',
            user_type='client',
        )

    def test_logout_blacklists_refresh_token(self):
        login_response = self.api.post(
            '/api/auth/login/',
            {'username': self.user.username, 'password': 'Secret123!'},
            format='json',
        )

        self.assertEqual(login_response.status_code, 200)
        refresh = login_response.data['refresh']

        logout_response = self.api.post(
            '/api/auth/logout/',
            {'refresh': refresh},
            format='json',
        )

        self.assertEqual(logout_response.status_code, 200)

        refresh_response = self.api.post(
            '/api/auth/refresh/',
            {'refresh': refresh},
            format='json',
        )

        self.assertIn(refresh_response.status_code, {400, 401})


class ClientRegistrationProfileDetailsTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        cache.clear()

    def _verify_registration(self, register_response, code='123456'):
        self.assertEqual(register_response.status_code, 202)
        token = register_response.data['verification_token']
        return self.api.post(
            '/api/auth/verify-email/',
            {'token': token, 'code': code},
            format='json',
        )

    @patch('key.mailing._send_direct_email')
    @patch('key.email_verification.generate_code', return_value='123456')
    def test_register_individual_creates_separate_passport_details(self, _code_mock, _send_mock):
        response = self.api.post(
            '/api/auth/register/',
            {
                'username': 'reg-individual',
                'email': 'reg-individual@example.com',
                'password': 'Secret123!',
                'password_confirm': 'Secret123!',
                'first_name': 'Иван',
                'last_name': 'Клиентов',
                'client_kind': models.ClientProfile.CLIENT_KIND_INDIVIDUAL,
                'birth_date': '1990-05-12',
                'passport_series': '1234',
                'passport_number': '567890',
                'passport_issued_by': 'ОУФМС России по Иркутской области',
                'passport_issued_date': '2010-06-20',
                'passport_code': '380-001',
                'registration_address': 'г. Иркутск, ул. Ленина, д. 10',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 202)
        self.assertFalse(models.User.objects.filter(username='reg-individual').exists())
        verify_response = self._verify_registration(response)
        self.assertEqual(verify_response.status_code, 200)
        user = models.User.objects.get(username='reg-individual')
        profile = user.client_profile
        self.assertTrue(user.is_email_verified)
        self.assertEqual(profile.client_kind, models.ClientProfile.CLIENT_KIND_INDIVIDUAL)
        self.assertEqual(profile.individual_details.passport_number, '567890')
        self.assertFalse(models.ClientCompanyDetails.objects.filter(profile=profile).exists())

    @patch('key.mailing._send_direct_email')
    @patch('key.email_verification.generate_code', return_value='123456')
    def test_register_company_creates_separate_company_details(self, _code_mock, _send_mock):
        response = self.api.post(
            '/api/auth/register/',
            {
                'username': 'reg-company',
                'email': 'reg-company@example.com',
                'password': 'Secret123!',
                'password_confirm': 'Secret123!',
                'first_name': 'Мария',
                'last_name': 'Директорова',
                'client_kind': models.ClientProfile.CLIENT_KIND_COMPANY,
                'company_inn': '3808000000',
                'registration_address': 'г. Иркутск, ул. Ленина, д. 10',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 202)
        self.assertFalse(models.User.objects.filter(username='reg-company').exists())
        verify_response = self._verify_registration(response)
        self.assertEqual(verify_response.status_code, 200)
        user = models.User.objects.get(username='reg-company')
        profile = user.client_profile
        self.assertTrue(user.is_email_verified)
        self.assertEqual(profile.client_kind, models.ClientProfile.CLIENT_KIND_COMPANY)
        self.assertEqual(profile.company_details.company_inn, '3808000000')
        self.assertFalse(models.ClientIndividualDetails.objects.filter(profile=profile).exists())

    def test_register_rejects_password_mismatch(self):
        response = self.api.post(
            '/api/auth/register/',
            {
                'username': 'reg-mismatch',
                'email': 'reg-mismatch@example.com',
                'password': 'Secret123!',
                'password_confirm': 'OtherSecret123!',
                'first_name': 'Иван',
                'last_name': 'Клиентов',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('password_confirm', response.data)
        self.assertFalse(models.User.objects.filter(username='reg-mismatch').exists())

    @patch('key.mailing._send_direct_email')
    @patch('key.email_verification.generate_code', return_value='123456')
    def test_unconfirmed_registration_is_not_saved_to_database(self, _code_mock, _send_mock):
        response = self.api.post(
            '/api/auth/register/',
            {
                'username': 'reg-unconfirmed',
                'email': 'reg-unconfirmed@example.com',
                'password': 'Secret123!',
                'password_confirm': 'Secret123!',
                'first_name': 'Иван',
                'last_name': 'Клиентов',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 202)
        self.assertIn('verification_token', response.data)
        self.assertFalse(models.User.objects.filter(username='reg-unconfirmed').exists())
        self.assertFalse(models.ClientProfile.objects.filter(user__username='reg-unconfirmed').exists())
        _send_mock.assert_called_once()

    @patch('key.mailing.send_email_verification_code', side_effect=RuntimeError('SMTP failed'))
    def test_register_does_not_save_user_when_email_code_cannot_be_sent(self, _send_mock):
        response = self.api.post(
            '/api/auth/register/',
            {
                'username': 'reg-mail-failed',
                'email': 'reg-mail-failed@example.com',
                'password': 'Secret123!',
                'password_confirm': 'Secret123!',
                'first_name': 'Иван',
                'last_name': 'Клиентов',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 503)
        self.assertIn('email', response.data)
        self.assertFalse(models.User.objects.filter(username='reg-mail-failed').exists())
        _send_mock.assert_called_once()

    def test_client_profile_update_switches_between_detail_tables(self):
        user = models.User.objects.create_user(
            username='profile-switch',
            email='profile-switch@example.com',
            password='Secret123!',
            user_type='client',
        )
        profile = models.ClientProfile.objects.create(
            user=user,
            first_name='Анна',
            last_name='Клиентова',
        )
        models.ClientIndividualDetails.objects.create(
            profile=profile,
            passport_series='1234',
            passport_number='567890',
        )
        self.api.force_authenticate(user=user)

        response = self.api.patch(
            f'/api/client-profiles/{profile.pk}/',
            {
                'client_kind': models.ClientProfile.CLIENT_KIND_COMPANY,
                'company_inn': '3808000000',
                'registration_address': 'г. Иркутск, ул. Ленина, д. 10',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        profile.refresh_from_db()
        self.assertEqual(profile.client_kind, models.ClientProfile.CLIENT_KIND_COMPANY)
        self.assertEqual(profile.company_details.company_inn, '3808000000')
        self.assertEqual(response.data['company_inn'], '3808000000')
        self.assertFalse(models.ClientIndividualDetails.objects.filter(profile=profile).exists())


class OutgoingEmailHtmlDeliveryTests(TestCase):
    def setUp(self):
        self.user = models.User.objects.create_user(
            username='email-user',
            email='email-user@example.com',
            password='Secret123!',
            user_type='client',
        )

    @patch('key.mailing.socket.setdefaulttimeout')
    @patch('key.mailing.socket.getdefaulttimeout', return_value=None)
    @patch('key.mailing.EmailMultiAlternatives')
    @patch('key.mailing.get_connection')
    def test_send_via_smtp_attaches_html_alternative(
        self,
        connection_mock,
        email_class_mock,
        _getdefaulttimeout_mock,
        _setdefaulttimeout_mock,
    ):
        email_message = email_class_mock.return_value
        queued = models.OutgoingEmail.objects.create(
            recipient=self.user,
            subject='HTML message',
            body='Plain body',
            html_body='<strong>HTML body</strong>',
        )

        mailing._send_via_smtp(queued)

        self.assertEqual(email_class_mock.call_args.args[1], 'Plain body')
        self.assertEqual(email_class_mock.call_args.kwargs['to'], [self.user.email])
        self.assertEqual(email_class_mock.call_args.kwargs['connection'], connection_mock.return_value)
        email_message.attach_alternative.assert_called_once_with(
            '<strong>HTML body</strong>', 'text/html',
        )
        email_message.send.assert_called_once_with(fail_silently=False)

    @patch('key.mailing.socket.setdefaulttimeout')
    @patch('key.mailing.socket.getdefaulttimeout', return_value=None)
    @patch('key.mailing.EmailMultiAlternatives')
    @patch('key.mailing.get_connection')
    def test_send_via_smtp_supports_legacy_embedded_html(
        self,
        _connection_mock,
        email_class_mock,
        _getdefaulttimeout_mock,
        _setdefaulttimeout_mock,
    ):
        email_message = email_class_mock.return_value
        queued = models.OutgoingEmail.objects.create(
            recipient=self.user,
            subject='Legacy HTML message',
            body='Plain body\n\n---- HTML ----\n<strong>Legacy HTML body</strong>',
        )

        mailing._send_via_smtp(queued)

        self.assertEqual(email_class_mock.call_args.args[1], 'Plain body')
        email_message.attach_alternative.assert_called_once_with(
            '<strong>Legacy HTML body</strong>', 'text/html',
        )

    @override_settings(
        EMAIL_HOST='smtp.yandex.ru',
        EMAIL_PORT=465,
        EMAIL_USE_SSL=True,
        EMAIL_USE_TLS=False,
        EMAIL_TIMEOUT=30,
        EMAIL_FALLBACK_ENABLED=True,
        EMAIL_FALLBACK_HOST='smtp.yandex.ru',
        EMAIL_FALLBACK_PORT=587,
        EMAIL_FALLBACK_USE_SSL=False,
        EMAIL_FALLBACK_USE_TLS=True,
        EMAIL_FALLBACK_TIMEOUT=30,
    )
    @patch('key.mailing.socket.setdefaulttimeout')
    @patch('key.mailing.socket.getdefaulttimeout', return_value=None)
    @patch('key.mailing.EmailMultiAlternatives')
    @patch('key.mailing.get_connection')
    def test_send_via_smtp_retries_with_fallback_channel_on_timeout(
        self,
        connection_mock,
        email_class_mock,
        _getdefaulttimeout_mock,
        _setdefaulttimeout_mock,
    ):
        primary_connection = Mock(name='primary_connection')
        fallback_connection = Mock(name='fallback_connection')
        connection_mock.side_effect = [primary_connection, fallback_connection]

        primary_message = Mock(name='primary_message')
        primary_message.send.side_effect = TimeoutError('handshake timed out')
        fallback_message = Mock(name='fallback_message')
        email_class_mock.side_effect = [primary_message, fallback_message]

        queued = models.OutgoingEmail.objects.create(
            recipient=self.user,
            subject='Fallback HTML message',
            body='Plain body',
            html_body='<strong>HTML body</strong>',
        )

        mailing._send_via_smtp(queued)

        self.assertEqual(connection_mock.call_count, 2)
        self.assertEqual(connection_mock.call_args_list[0].kwargs['port'], 465)
        self.assertTrue(connection_mock.call_args_list[0].kwargs['use_ssl'])
        self.assertFalse(connection_mock.call_args_list[0].kwargs['use_tls'])
        self.assertEqual(connection_mock.call_args_list[1].kwargs['port'], 587)
        self.assertFalse(connection_mock.call_args_list[1].kwargs['use_ssl'])
        self.assertTrue(connection_mock.call_args_list[1].kwargs['use_tls'])
        primary_message.send.assert_called_once_with(fail_silently=False)
        fallback_message.send.assert_called_once_with(fail_silently=False)
        primary_connection.close.assert_called_once()
        fallback_connection.close.assert_called_once()


class OutgoingEmailQueueWorkerTests(TestCase):
    def setUp(self):
        self.user = models.User.objects.create_user(
            username='queue-user',
            email='queue-user@example.com',
            password='Secret123!',
            user_type='client',
        )

    def test_process_email_queue_marks_email_as_sent(self):
        queued = models.OutgoingEmail.objects.create(
            recipient=self.user,
            subject='Queued email',
            body='Plain body',
            status='pending',
        )

        with patch('key.mailing._send_via_smtp') as send_mock:
            summary = mailing.process_email_queue(limit=5)

        queued.refresh_from_db()
        self.assertEqual(summary, {'processed': 1, 'sent': 1, 'failed': 0})
        self.assertEqual(queued.status, 'sent')
        self.assertIsNotNone(queued.sent_at)
        self.assertIsNone(queued.processing_started_at)
        send_mock.assert_called_once()

    def test_process_email_queue_marks_failure(self):
        queued = models.OutgoingEmail.objects.create(
            recipient=self.user,
            subject='Queued email',
            body='Plain body',
            status='pending',
        )

        with patch('key.mailing._send_via_smtp', side_effect=RuntimeError('SMTP down')):
            summary = mailing.process_email_queue(limit=5)

        queued.refresh_from_db()
        self.assertEqual(summary, {'processed': 1, 'sent': 0, 'failed': 1})
        self.assertEqual(queued.status, 'failed')
        self.assertIn('SMTP down', queued.error_message)
        self.assertIsNone(queued.processing_started_at)

    def test_resend_requeues_failed_email(self):
        queued = models.OutgoingEmail.objects.create(
            recipient=self.user,
            subject='Failed email',
            body='Plain body',
            status='failed',
            error_message='SMTP down',
            processing_started_at=timezone.now(),
        )

        mailing.resend(queued)

        queued.refresh_from_db()
        self.assertEqual(queued.status, 'pending')
        self.assertIsNone(queued.error_message)
        self.assertIsNone(queued.processing_started_at)



class DealContractQueueTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.operation_type = models.OperationType.objects.create(
            code='sale',
            name='Sale',
        )
        self.property_status = models.PropertyStatus.objects.create(
            code='active',
            name='Active',
        )
        self.deal_status = models.DealStatus.objects.create(
            code='new',
            name='New',
            order=10,
        )
        self.employee = models.User.objects.create_user(
            username='contract-agent',
            email='contract-agent@example.com',
            password='Secret123!',
            user_type='employee',
        )
        self.client_user = models.User.objects.create_user(
            username='contract-client',
            email='contract-client@example.com',
            password='Secret123!',
            user_type='client',
        )
        city = models.City.objects.create(name='Irkutsk', region='Region')
        street = models.Street.objects.create(city=city, name='Lenina')
        house = models.House.objects.create(street=street, house_number='22')
        address = models.Address.objects.create(house=house, apartment_number='6')
        self.property = models.Property.objects.create(
            title='Contract property',
            operation_type=self.operation_type,
            status=self.property_status,
            address=address,
            price=7_300_000,
        )
        self.deal = models.Deal.objects.create(
            deal_number='D-2026-0200',
            property=self.property,
            agent=self.employee,
            client=self.client_user,
            operation_type=self.operation_type,
            status=self.deal_status,
            price_final=self.property.price,
            deal_date=timezone.now().date(),
        )
        self.api.force_authenticate(user=self.employee)

    def test_money_words_formats_russian_amounts(self):
        self.assertEqual(
            documents._money_words(Decimal('182500.40')),
            'Сто восемьдесят две тысячи пятьсот рублей 40 копеек',
        )
        self.assertEqual(
            documents._money_words(Decimal('1.01')),
            'Один рубль 01 копейка',
        )

    def test_contract_fonts_are_registered_from_local_times_family(self):
        documents._ensure_fonts_registered()

        self.assertEqual(
            pdfmetrics.getFont(documents.FONT_REGULAR).fontName,
            documents.FONT_REGULAR,
        )
        self.assertEqual(
            pdfmetrics.getFont(documents.FONT_BOLD).fontName,
            documents.FONT_BOLD,
        )
        self.assertEqual(
            pdfmetrics.getFont(documents.FONT_ITALIC).fontName,
            documents.FONT_ITALIC,
        )
        self.assertEqual(
            pdfmetrics.getFont(documents.FONT_BOLD_ITALIC).fontName,
            documents.FONT_BOLD_ITALIC,
        )

    @override_settings(
        AGENCY_NAME='РИЭЛТ',
        AGENCY_LEGAL_NAME='ООО «РИЭЛТ»',
        AGENCY_REPLY_TO='office@rielt.example',
        AGENCY_PUBLIC_URL='https://rielt.example',
        AGENCY_PHONE='+7 (3952) 11-22-33',
        AGENCY_ADDRESS='г. Иркутск, ул. Ленина, д. 1',
        AGENCY_INN='3808000000',
        AGENCY_KPP='380801001',
        AGENCY_OGRN='1023800000000',
        AGENCY_BANK_DETAILS='р/с 40702810000000000001; БИК 042520607; ПАО Сбербанк',
        AGENCY_SIGNATORY_NAME='Иванов Иван Иванович',
        AGENCY_SIGNATORY_TITLE='Генеральный директор',
        AGENCY_SIGNATORY_BASIS='Устава',
    )
    def test_contract_requisites_are_composed_from_settings(self):
        self.assertEqual(documents._agency_legal_name(), 'ООО «РИЭЛТ»')
        self.assertEqual(documents._agency_signatory_name(self.employee), 'Иванов Иван Иванович')
        self.assertEqual(documents._agency_signatory_title(self.employee), 'Генеральный директор')
        self.assertEqual(documents._agency_signatory_basis(), 'Устава')
        self.assertEqual(
            documents._agency_contact_line(),
            '+7 (3952) 11-22-33 / office@rielt.example / https://rielt.example',
        )
        self.assertEqual(
            documents._agency_requisites_lines(),
            [
                'Адрес: г. Иркутск, ул. Ленина, д. 1',
                'Телефон: +7 (3952) 11-22-33',
                'Email: office@rielt.example',
                'ИНН: 3808000000',
                'КПП: 380801001',
                'ОГРН: 1023800000000',
                'р/с 40702810000000000001',
                'БИК 042520607',
                'ПАО Сбербанк',
                'Сайт: https://rielt.example',
            ],
        )

    def test_render_contract_pdf_builds_detailed_document_and_escapes_dynamic_text(self):
        models.EmployeeProfile.objects.create(
            user=self.employee,
            first_name='Иван',
            last_name='Агентов',
            middle_name='Петрович',
            position='Агент по недвижимости',
        )
        client_profile = models.ClientProfile.objects.create(
            user=self.client_user,
            first_name='Мария',
            last_name='Клиентова',
            middle_name='Сергеевна',
            registration_address='г. Иркутск, ул. Тестовая, д. 1, кв. 2',
            actual_address='г. Иркутск, ул. Тестовая, д. 1, кв. 2',
            preferred_contact_method='email',
        )
        models.ClientIndividualDetails.objects.create(
            profile=client_profile,
            passport_series='1234',
            passport_number='567890',
            passport_issued_by='ОУФМС России по Иркутской области',
            passport_code='380-001',
            passport_issued_date=timezone.now().date(),
        )
        self.property.title = 'Квартира <с отделкой> & мебелью'
        self.property.area_total = Decimal('48.50')
        self.property.rooms_count = 2
        self.property.floor_number = 5
        self.property.total_floors = 9
        self.property.save(update_fields=[
            'title',
            'area_total',
            'rooms_count',
            'floor_number',
            'total_floors',
        ])
        self.deal.commission_percent = Decimal('2.50')
        self.deal.commission_amount = 182500
        self.deal.notes = (
            'Особые условия:\n'
            '1. Сопровождение <под ключ>.\n'
            '2. Проверка документов & расчётов.'
        )
        self.deal.save(update_fields=[
            'commission_percent',
            'commission_amount',
            'notes',
        ])

        pdf = documents.render_contract_pdf(self.deal)
        content = pdf.read()

        self.assertEqual(pdf.name, f'contract-{self.deal.deal_number}.pdf')
        self.assertTrue(content.startswith(b'%PDF-'))
        self.assertGreater(len(content), 20_000)

    def test_queue_contract_generation_marks_deal_pending(self):
        queued = deals_service.queue_contract_generation(self.deal)

        queued.refresh_from_db()
        self.assertEqual(queued.contract_status, 'pending')
        self.assertIsNotNone(queued.contract_requested_at)
        self.assertFalse(bool(queued.contract_file))

    def test_process_contract_queue_marks_deal_ready(self):
        deals_service.queue_contract_generation(self.deal)

        with patch(
            'key.deals_service.render_contract_pdf',
            return_value=ContentFile(b'%PDF-1.4 test', name='contract.pdf'),
        ):
            summary = deals_service.process_contract_queue(limit=5)

        self.deal.refresh_from_db()
        self.assertEqual(summary, {'processed': 1, 'generated': 1, 'failed': 0})
        self.assertEqual(self.deal.contract_status, 'ready')
        self.assertIsNotNone(self.deal.contract_generated_at)
        self.assertTrue(bool(self.deal.contract_file))
        self.assertIsNone(self.deal.contract_processing_started_at)

    def test_process_contract_queue_marks_failure(self):
        deals_service.queue_contract_generation(self.deal)

        with patch(
            'key.deals_service.render_contract_pdf',
            side_effect=RuntimeError('PDF down'),
        ):
            summary = deals_service.process_contract_queue(limit=5)

        self.deal.refresh_from_db()
        self.assertEqual(summary, {'processed': 1, 'generated': 0, 'failed': 1})
        self.assertEqual(self.deal.contract_status, 'failed')
        self.assertIn('PDF down', self.deal.contract_error_message)
        self.assertIsNone(self.deal.contract_processing_started_at)

    def test_contract_endpoint_reports_pending_generation(self):
        deals_service.queue_contract_generation(self.deal)

        response = self.api.get(f'/api/deals/{self.deal.pk}/contract/')

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['contract_status'], 'pending')
        self.assertEqual(response.data['contract_status_display'], 'В очереди')
        self.assertIsNotNone(response.data['contract_requested_at'])

    def test_contract_endpoint_returns_pdf_when_contract_is_ready(self):
        self.deal.contract_file.save(
            'contract-ready.pdf',
            ContentFile(b'%PDF-1.4 ready test', name='contract-ready.pdf'),
            save=False,
        )
        self.deal.contract_status = 'ready'
        self.deal.contract_generated_at = timezone.now()
        self.deal.save(update_fields=[
            'contract_file',
            'contract_status',
            'contract_generated_at',
        ])

        response = self.api.get(f'/api/deals/{self.deal.pk}/contract/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn(
            f'contract-{self.deal.deal_number}.pdf',
            response['Content-Disposition'],
        )
        self.assertEqual(
            b''.join(response.streaming_content),
            b'%PDF-1.4 ready test',
        )

    def test_regenerate_contract_requeues_and_clears_existing_file(self):
        self.deal.contract_file.save(
            'contract-old.pdf',
            ContentFile(b'old pdf', name='contract-old.pdf'),
            save=False,
        )
        self.deal.contract_status = 'ready'
        self.deal.contract_generated_at = timezone.now()
        self.deal.save(update_fields=[
            'contract_file', 'contract_status', 'contract_generated_at',
        ])

        response = self.api.post(
            f'/api/deals/{self.deal.pk}/regenerate_contract/',
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.contract_status, 'pending')
        self.assertFalse(bool(self.deal.contract_file))
        self.assertIsNone(self.deal.contract_generated_at)


class RequestMatchConfirmationTests(TestCase):
    def setUp(self):
        self.api = APIClient()

        self.operation_type = models.OperationType.objects.create(
            code='sale',
            name='Продажа',
        )
        self.property_status = models.PropertyStatus.objects.create(
            code='active',
            name='Активен',
        )
        self.request_status = models.RequestStatus.objects.create(
            code='open',
            name='Открыта',
        )

        self.client_user = models.User.objects.create_user(
            username='client',
            email='client@example.com',
            password='Secret123!',
            user_type='client',
        )
        self.agent = models.User.objects.create_user(
            username='agent',
            email='agent@example.com',
            password='Secret123!',
            user_type='employee',
        )
        self.second_agent = models.User.objects.create_user(
            username='second-agent',
            email='second-agent@example.com',
            password='Secret123!',
            user_type='employee',
        )

        city = models.City.objects.create(name='Иркутск', region='Иркутская область')
        street = models.Street.objects.create(city=city, name='Ленина')
        house = models.House.objects.create(street=street, house_number='10')

        self.direct_property = self._create_property(house, 'Объект №1', 5_000_000)
        self.confirmed_property = self._create_property(house, 'Объект №2', 6_000_000)
        self.old_property = self._create_property(house, 'Объект №3', 7_000_000)

        self.request_obj = models.Request.objects.create(
            client=self.client_user,
            agent=self.agent,
            property=self.direct_property,
            operation_type=self.operation_type,
            status=self.request_status,
        )
        self.target_match = models.RequestPropertyMatch.objects.create(
            request=self.request_obj,
            property=self.confirmed_property,
            agent=self.agent,
            is_offered=True,
        )
        self.old_match = models.RequestPropertyMatch.objects.create(
            request=self.request_obj,
            property=self.old_property,
            agent=self.second_agent,
            is_offered=True,
            is_confirmed=True,
            confirmed_at=timezone.now(),
            confirmed_by=self.second_agent,
        )

    def _create_property(self, house, title, price):
        address = models.Address.objects.create(
            house=house,
            apartment_number=title,
        )
        return models.Property.objects.create(
            title=title,
            operation_type=self.operation_type,
            status=self.property_status,
            address=address,
            price=price,
        )

    def test_confirm_property_marks_selected_match_as_confirmed(self):
        self.api.force_authenticate(user=self.agent)

        response = self.api.post(
            f'/api/requests/{self.request_obj.pk}/confirm_property/',
            {'match_id': self.target_match.pk},
            format='json',
        )

        self.assertEqual(response.status_code, 200)

        self.target_match.refresh_from_db()
        self.old_match.refresh_from_db()

        self.assertTrue(self.target_match.is_confirmed)
        self.assertFalse(self.target_match.is_rejected)
        self.assertIsNotNone(self.target_match.confirmed_at)
        self.assertEqual(self.target_match.confirmed_by, self.agent)
        self.assertFalse(self.old_match.is_confirmed)
        self.assertIsNone(self.old_match.confirmed_at)
        self.assertIsNone(self.old_match.confirmed_by)
        self.assertEqual(response.data['match']['state'], 'confirmed')

    def test_deal_property_resolver_prefers_confirmed_match(self):
        self.target_match.is_confirmed = True
        self.target_match.confirmed_at = timezone.now()
        self.target_match.confirmed_by = self.agent
        self.target_match.save(
            update_fields=['is_confirmed', 'confirmed_at', 'confirmed_by'],
        )

        resolved = deals_service._resolve_property_for_request(self.request_obj)

        self.assertEqual(resolved, self.confirmed_property)


class RequestFilteringTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.operation_type = models.OperationType.objects.create(
            code='sale',
            name='Sale',
        )
        self.status_open = models.RequestStatus.objects.create(
            code='open',
            name='Open',
        )
        self.status_closed = models.RequestStatus.objects.create(
            code='closed',
            name='Closed',
        )
        self.status_completed = models.RequestStatus.objects.create(
            code='completed',
            name='Completed',
        )
        self.employee = models.User.objects.create_user(
            username='employee',
            email='employee@example.com',
            password='Secret123!',
            user_type='employee',
        )
        self.client_one = models.User.objects.create_user(
            username='client-one',
            email='client-one@example.com',
            phone='+70000000001',
            password='Secret123!',
            user_type='client',
        )
        self.client_two = models.User.objects.create_user(
            username='client-two',
            email='client-two@example.com',
            phone='+70000000002',
            password='Secret123!',
            user_type='client',
        )
        self.client_three = models.User.objects.create_user(
            username='client-three',
            email='client-three@example.com',
            phone='+70000000003',
            password='Secret123!',
            user_type='client',
        )
        self.request_one = models.Request.objects.create(
            client=self.client_one,
            agent=self.employee,
            operation_type=self.operation_type,
            status=self.status_open,
        )
        self.request_two = models.Request.objects.create(
            client=self.client_two,
            agent=self.employee,
            operation_type=self.operation_type,
            status=self.status_completed,
        )
        self.request_three = models.Request.objects.create(
            client=self.client_three,
            agent=self.employee,
            operation_type=self.operation_type,
            status=self.status_closed,
            closed_at=timezone.now(),
        )

    def test_request_list_supports_client_filter_and_contact_fields(self):
        self.api.force_authenticate(user=self.employee)

        response = self.api.get(f'/api/requests/?client={self.client_one.pk}')

        self.assertEqual(response.status_code, 200)
        payload = response.data['results']
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]['id'], self.request_one.pk)
        self.assertEqual(payload[0]['client_email'], self.client_one.email)
        self.assertEqual(payload[0]['client_phone'], self.client_one.phone)

    def test_request_list_supports_multiple_status_codes(self):
        self.api.force_authenticate(user=self.employee)

        response = self.api.get('/api/requests/?status_code=open,completed')

        self.assertEqual(response.status_code, 200)
        payload = response.data['results']
        self.assertEqual(len(payload), 3)
        self.assertEqual(
            {item['status_code'] for item in payload},
            {'open', 'completed'},
        )
        self.assertEqual(
            {item['id'] for item in payload},
            {self.request_one.pk, self.request_two.pk, self.request_three.pk},
        )

    def test_request_status_list_hides_legacy_closed_code(self):
        self.api.force_authenticate(user=self.employee)

        response = self.api.get('/api/request-statuses/')

        self.assertEqual(response.status_code, 200)
        payload = response.data['results']
        self.assertEqual(
            {item['code'] for item in payload},
            {'open', 'completed'},
        )

    def test_request_list_supports_search_by_id_and_client(self):
        self.api.force_authenticate(user=self.employee)

        response_by_id = self.api.get(f'/api/requests/?search={self.request_one.pk}')
        self.assertEqual(response_by_id.status_code, 200)
        payload_by_id = response_by_id.data['results']
        self.assertEqual(len(payload_by_id), 1)
        self.assertEqual(payload_by_id[0]['id'], self.request_one.pk)

        response_by_client = self.api.get('/api/requests/?search=client-two')
        self.assertEqual(response_by_client.status_code, 200)
        payload_by_client = response_by_client.data['results']
        self.assertEqual(len(payload_by_client), 1)
        self.assertEqual(payload_by_client[0]['id'], self.request_two.pk)

    def test_request_list_supports_operation_type_and_created_at_range(self):
        self.api.force_authenticate(user=self.employee)
        rent_operation = models.OperationType.objects.create(
            code='rent',
            name='Rent',
        )
        rent_request = models.Request.objects.create(
            client=self.client_one,
            agent=self.employee,
            operation_type=rent_operation,
            status=self.status_open,
        )
        older_date = timezone.now() - timedelta(days=3)
        current_date = timezone.now()
        models.Request.objects.filter(pk=self.request_one.pk).update(
            created_at=older_date,
        )
        models.Request.objects.filter(pk=self.request_two.pk).update(
            created_at=current_date,
        )
        models.Request.objects.filter(pk=self.request_three.pk).update(
            created_at=current_date,
        )
        models.Request.objects.filter(pk=rent_request.pk).update(
            created_at=current_date,
        )

        response = self.api.get('/api/requests/', {
            'operation_type': self.operation_type.pk,
            'date_from': timezone.localdate().isoformat(),
            'date_to': timezone.localdate().isoformat(),
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {item['id'] for item in response.data['results']},
            {self.request_two.pk, self.request_three.pk},
        )

    def test_client_cannot_export_requests(self):
        self.api.force_authenticate(user=self.client_one)

        response = self.api.get(
            '/api/requests/export/',
            {'export_format': 'csv'},
        )

        self.assertEqual(response.status_code, 403)


class RequestClosePermissionTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.operation_type = models.OperationType.objects.create(
            code='sale',
            name='Sale',
        )
        self.status_open = models.RequestStatus.objects.create(
            code='open',
            name='Open',
        )
        self.client_user = models.User.objects.create_user(
            username='request-client',
            email='request-client@example.com',
            password='Secret123!',
            user_type='client',
        )
        self.employee = models.User.objects.create_user(
            username='request-agent',
            email='request-agent@example.com',
            password='Secret123!',
            user_type='employee',
        )
        self.request_obj = models.Request.objects.create(
            client=self.client_user,
            agent=self.employee,
            operation_type=self.operation_type,
            status=self.status_open,
        )

    def test_client_cannot_close_own_request(self):
        self.api.force_authenticate(user=self.client_user)

        response = self.api.post(
            f'/api/requests/{self.request_obj.pk}/close/',
            format='json',
        )

        self.assertEqual(response.status_code, 403)
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status_id, self.status_open.pk)
        self.assertFalse(
            models.Deal.objects.filter(request=self.request_obj).exists(),
        )


class RequestOwnPropertyTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.operation_type = models.OperationType.objects.create(
            code='sale',
            name='Sale',
        )
        self.request_status_open = models.RequestStatus.objects.create(
            code='open',
            name='Open',
        )
        self.property_status_active = models.PropertyStatus.objects.create(
            code='active',
            name='Active',
        )
        city = models.City.objects.create(name='Irkutsk')
        street = models.Street.objects.create(city=city, name='Lenina')
        house = models.House.objects.create(street=street, house_number='1')
        self.address = models.Address.objects.create(house=house)
        self.owner = models.User.objects.create_user(
            username='own-property-owner',
            email='own-property-owner@example.com',
            password='Secret123!',
            user_type='client',
        )
        self.other_client = models.User.objects.create_user(
            username='own-property-other-client',
            email='own-property-other-client@example.com',
            password='Secret123!',
            user_type='client',
        )
        self.property_obj = models.Property.objects.create(
            title='Owner property',
            operation_type=self.operation_type,
            status=self.property_status_active,
            address=self.address,
            owner=self.owner,
            price=5_000_000,
        )

    def test_owner_cannot_create_request_for_own_property(self):
        self.api.force_authenticate(user=self.owner)

        response = self.api.post(
            '/api/requests/',
            {
                'operation_type': self.operation_type.pk,
                'property': self.property_obj.pk,
                'status': self.request_status_open.pk,
                'description': 'Call me',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('property', response.data)
        self.assertFalse(
            models.Request.objects.filter(
                client=self.owner,
                property=self.property_obj,
            ).exists(),
        )

    def test_other_client_can_create_request_for_property(self):
        self.api.force_authenticate(user=self.other_client)

        response = self.api.post(
            '/api/requests/',
            {
                'operation_type': self.operation_type.pk,
                'property': self.property_obj.pk,
                'status': self.request_status_open.pk,
                'description': 'Interested in viewing',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        request_obj = models.Request.objects.get(pk=response.data['id'])
        self.assertEqual(request_obj.client_id, self.other_client.id)
        self.assertEqual(request_obj.property_id, self.property_obj.id)

    def test_apartment_request_does_not_require_floor_preferences(self):
        self.api.force_authenticate(user=self.other_client)

        response = self.api.post(
            '/api/requests/',
            {
                'operation_type': self.operation_type.pk,
                'status': self.request_status_open.pk,
                'property_type': models.Property.PREMISES_APARTMENT,
                'rooms_count': 2,
                'description': 'Looking for an apartment',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        request_obj = models.Request.objects.get(pk=response.data['id'])
        self.assertEqual(request_obj.property_type, models.Property.PREMISES_APARTMENT)
        self.assertEqual(request_obj.rooms_count, 2)


class RequestEditingRulesTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.operation_type = models.OperationType.objects.create(
            code='sale',
            name='Sale',
        )
        self.status_open = models.RequestStatus.objects.create(
            code='open',
            name='Open',
        )
        self.status_completed = models.RequestStatus.objects.create(
            code='completed',
            name='Completed',
        )
        self.client_user = models.User.objects.create_user(
            username='request-edit-client',
            email='request-edit-client@example.com',
            password='Secret123!',
            user_type='client',
        )
        self.employee = models.User.objects.create_user(
            username='request-edit-agent',
            email='request-edit-agent@example.com',
            password='Secret123!',
            user_type='employee',
        )
        self.request_obj = models.Request.objects.create(
            client=self.client_user,
            agent=self.employee,
            operation_type=self.operation_type,
            status=self.status_completed,
            description='Original description',
        )
        self.api.force_authenticate(user=self.employee)

    def test_terminal_request_cannot_be_updated(self):
        response = self.api.patch(
            f'/api/requests/{self.request_obj.pk}/',
            {'description': 'Updated description'},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.description, 'Original description')
        self.assertIn('Нельзя редактировать закрытую заявку.', str(response.data))


    def test_terminal_request_cannot_be_deleted(self):
        response = self.api.delete(f'/api/requests/{self.request_obj.pk}/')

        self.assertEqual(response.status_code, 400)
        self.assertTrue(models.Request.objects.filter(pk=self.request_obj.pk).exists())
        self.assertIn('Нельзя удалить закрытую заявку.', str(response.data))


class UserAssignRoleTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.role_manager = models.UserRole.objects.create(
            code='manager',
            name='Manager',
        )
        self.role_agent = models.UserRole.objects.create(
            code='agent',
            name='Agent',
        )
        self.manager = models.User.objects.create_user(
            username='manager',
            email='manager@example.com',
            password='Secret123!',
            user_type='employee',
            role=self.role_manager,
        )

    def test_assign_role_creates_employee_profile_for_promoted_client(self):
        client = models.User.objects.create_user(
            username='client-user',
            email='client-user@example.com',
            password='Secret123!',
            user_type='client',
        )
        models.ClientProfile.objects.create(
            user=client,
            first_name='Jane',
            last_name='Doe',
            middle_name='K',
        )
        self.api.force_authenticate(user=self.manager)

        response = self.api.post(
            f'/api/users/{client.pk}/assign_role/',
            {'user_type': 'employee', 'role_id': self.role_agent.pk},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        client.refresh_from_db()
        self.assertEqual(client.user_type, 'employee')
        self.assertEqual(client.role_id, self.role_agent.pk)
        self.assertTrue(client.is_staff)
        self.assertTrue(hasattr(client, 'employee_profile'))
        self.assertEqual(client.employee_profile.first_name, 'Jane')
        self.assertEqual(client.employee_profile.last_name, 'Doe')

    def test_assign_role_creates_client_profile_and_clears_role(self):
        employee = models.User.objects.create_user(
            username='employee-user',
            email='employee-user@example.com',
            password='Secret123!',
            user_type='employee',
            role=self.role_agent,
        )
        models.EmployeeProfile.objects.create(
            user=employee,
            first_name='Ann',
            last_name='Smith',
        )
        self.api.force_authenticate(user=self.manager)

        response = self.api.post(
            f'/api/users/{employee.pk}/assign_role/',
            {'user_type': 'client'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        employee.refresh_from_db()
        self.assertEqual(employee.user_type, 'client')
        self.assertIsNone(employee.role)
        self.assertFalse(employee.is_staff)
        self.assertTrue(hasattr(employee, 'client_profile'))
        self.assertEqual(employee.client_profile.first_name, 'Ann')
        self.assertEqual(employee.client_profile.last_name, 'Smith')


class UserListFilteringTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.employee = models.User.objects.create_user(
            username='list-employee',
            email='list-employee@example.com',
            password='Secret123!',
            user_type='employee',
        )
        models.User.objects.create_user(
            username='list-client',
            email='list-client@example.com',
            password='Secret123!',
            user_type='client',
        )
        models.User.objects.create_user(
            username='list-superuser',
            email='list-superuser@example.com',
            password='Secret123!',
            user_type='employee',
            is_superuser=True,
            is_staff=True,
        )
        self.api.force_authenticate(user=self.employee)

    def test_user_list_supports_page_size(self):
        response = self.api.get('/api/users/?page_size=1')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 3)
        self.assertEqual(len(response.data['results']), 1)

    def test_user_list_supports_is_superuser_filter(self):
        response = self.api.get('/api/users/?is_superuser=true')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['username'], 'list-superuser')


class DashboardStatsTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.operation_type = models.OperationType.objects.create(
            code='sale',
            name='Sale',
        )
        self.request_status_open = models.RequestStatus.objects.create(
            code='open',
            name='Open',
        )
        self.request_status_processing = models.RequestStatus.objects.create(
            code='processing',
            name='Processing',
        )
        self.request_status_completed = models.RequestStatus.objects.create(
            code='completed',
            name='Completed',
        )
        self.task_status_new = models.TaskStatus.objects.create(
            code='new',
            name='New',
            order=10,
        )
        self.task_status_waiting = models.TaskStatus.objects.create(
            code='waiting',
            name='Waiting',
            order=20,
        )
        self.task_status_in_progress = models.TaskStatus.objects.create(
            code='in_progress',
            name='In progress',
            order=30,
        )
        self.task_status_done = models.TaskStatus.objects.create(
            code='done',
            name='Done',
            order=40,
        )
        self.manager_role = models.UserRole.objects.create(
            code='manager',
            name='Manager',
        )
        self.employee = models.User.objects.create_user(
            username='dashboard-employee',
            email='dashboard-employee@example.com',
            password='Secret123!',
            user_type='employee',
        )
        self.other_employee = models.User.objects.create_user(
            username='dashboard-other',
            email='dashboard-other@example.com',
            password='Secret123!',
            user_type='employee',
        )
        self.manager = models.User.objects.create_user(
            username='dashboard-manager',
            email='dashboard-manager@example.com',
            password='Secret123!',
            user_type='employee',
            role=self.manager_role,
        )
        self.client_user = models.User.objects.create_user(
            username='dashboard-client',
            email='dashboard-client@example.com',
            password='Secret123!',
            user_type='client',
        )

    def test_employee_dashboard_counts_active_requests_and_own_tasks(self):
        models.Request.objects.create(
            client=self.client_user,
            agent=self.employee,
            operation_type=self.operation_type,
            status=self.request_status_open,
        )
        models.Request.objects.create(
            client=self.client_user,
            agent=self.other_employee,
            operation_type=self.operation_type,
            status=self.request_status_processing,
        )
        models.Request.objects.create(
            client=self.client_user,
            agent=self.employee,
            operation_type=self.operation_type,
            status=self.request_status_completed,
        )
        models.Task.objects.create(
            title='Employee active task',
            status=self.task_status_new,
            assignee=self.employee,
            created_by=self.employee,
        )
        models.Task.objects.create(
            title='Other employee active task',
            status=self.task_status_waiting,
            assignee=self.other_employee,
            created_by=self.manager,
        )
        models.Task.objects.create(
            title='Completed-but-active task',
            status=self.task_status_in_progress,
            assignee=self.employee,
            created_by=self.manager,
            completed_at=timezone.now(),
        )
        models.Task.objects.create(
            title='Done task',
            status=self.task_status_done,
            assignee=self.employee,
            created_by=self.manager,
        )
        self.api.force_authenticate(user=self.employee)

        response = self.api.get('/api/dashboard/stats/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['requests_open'], 2)
        self.assertEqual(response.data['tasks_open'], 1)

    def test_manager_dashboard_counts_active_tasks_for_all_employees(self):
        models.Task.objects.create(
            title='Employee task',
            status=self.task_status_new,
            assignee=self.employee,
            created_by=self.manager,
        )
        models.Task.objects.create(
            title='Other task',
            status=self.task_status_waiting,
            assignee=self.other_employee,
            created_by=self.manager,
        )
        models.Task.objects.create(
            title='Finished active status task',
            status=self.task_status_in_progress,
            assignee=self.other_employee,
            created_by=self.manager,
            completed_at=timezone.now(),
        )
        self.api.force_authenticate(user=self.manager)

        response = self.api.get('/api/dashboard/stats/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['tasks_open'], 2)

    def test_client_dashboard_stats_do_not_include_tasks_open(self):
        self.api.force_authenticate(user=self.client_user)

        response = self.api.get('/api/dashboard/stats/')

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('tasks_open', response.data)


class ReportApiTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.operation_type = models.OperationType.objects.create(
            code='sale',
            name='Sale',
        )
        self.property_status = models.PropertyStatus.objects.create(
            code='active',
            name='Active',
        )
        self.deal_status = models.DealStatus.objects.create(
            code='signed',
            name='Signed',
        )
        self.task_status_new = models.TaskStatus.objects.create(
            code='new',
            name='New',
            order=10,
        )
        self.task_status_done = models.TaskStatus.objects.create(
            code='done',
            name='Done',
            order=20,
        )
        self.manager = models.User.objects.create_user(
            username='report-manager',
            email='report-manager@example.com',
            password='Secret123!',
            user_type='employee',
            role=models.UserRole.objects.create(code='manager', name='Manager'),
        )
        self.moderator = models.User.objects.create_user(
            username='report-moderator',
            email='report-moderator@example.com',
            password='Secret123!',
            user_type='employee',
            role=models.UserRole.objects.create(code='moderator', name='Moderator'),
        )
        self.employee = models.User.objects.create_user(
            username='report-agent',
            email='report-agent@example.com',
            password='Secret123!',
            user_type='employee',
        )
        self.other_employee = models.User.objects.create_user(
            username='report-other-agent',
            email='report-other-agent@example.com',
            password='Secret123!',
            user_type='employee',
        )
        self.client_user = models.User.objects.create_user(
            username='report-client',
            email='report-client@example.com',
            password='Secret123!',
            user_type='client',
        )

        city = models.City.objects.create(name='Irkutsk', region='Region')
        street = models.Street.objects.create(city=city, name='Lenina')
        house = models.House.objects.create(street=street, house_number='18')
        address = models.Address.objects.create(
            house=house,
            apartment_number='5',
        )
        self.property = models.Property.objects.create(
            title='Report property',
            operation_type=self.operation_type,
            status=self.property_status,
            address=address,
            price=9_500_000,
        )

        models.Deal.objects.create(
            deal_number='REP-001',
            property=self.property,
            agent=self.employee,
            client=self.client_user,
            operation_type=self.operation_type,
            status=self.deal_status,
            price_final=9_500_000,
            commission_percent=3,
            commission_amount=285_000,
            deal_date=timezone.localdate(),
        )
        models.Deal.objects.create(
            deal_number='REP-002',
            property=self.property,
            agent=self.other_employee,
            client=self.client_user,
            operation_type=self.operation_type,
            status=self.deal_status,
            price_final=7_200_000,
            commission_percent=2,
            commission_amount=144_000,
            deal_date=timezone.localdate(),
        )

        models.Task.objects.create(
            title='Prepare documents',
            task_type='documents',
            status=self.task_status_new,
            assignee=self.employee,
            created_by=self.manager,
            client=self.client_user,
            property=self.property,
            due_date=timezone.now() + timedelta(days=1),
        )
        models.Task.objects.create(
            title='Call other client',
            task_type='call',
            status=self.task_status_done,
            assignee=self.other_employee,
            created_by=self.manager,
            completed_at=timezone.now(),
            result='Done',
        )

    def test_deals_report_returns_filtered_summary(self):
        self.api.force_authenticate(user=self.manager)

        response = self.api.get('/api/reports/deals/', {
            'agent': self.employee.pk,
            'date_from': timezone.localdate().isoformat(),
            'date_to': timezone.localdate().isoformat(),
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['report_code'], 'deals')
        self.assertEqual(response.data['summary']['Всего сделок'], 1)
        self.assertEqual(len(response.data['rows']), 1)
        self.assertEqual(response.data['rows'][0]['deal_number'], 'REP-001')

    def test_tasks_report_returns_full_dataset_for_manager(self):
        self.api.force_authenticate(user=self.manager)

        response = self.api.get('/api/reports/tasks/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['report_code'], 'tasks')
        self.assertEqual(response.data['summary']['Всего задач'], 2)
        self.assertEqual(len(response.data['rows']), 2)
        self.assertEqual(
            {row['assignee_username'] for row in response.data['rows']},
            {self.employee.username, self.other_employee.username},
        )

    def test_moderator_can_access_reports(self):
        self.api.force_authenticate(user=self.moderator)

        deals_response = self.api.get('/api/reports/deals/')
        tasks_response = self.api.get('/api/reports/tasks/')

        self.assertEqual(deals_response.status_code, 200)
        self.assertEqual(tasks_response.status_code, 200)
        self.assertEqual(deals_response.data['report_code'], 'deals')
        self.assertEqual(tasks_response.data['report_code'], 'tasks')

    def test_agent_cannot_access_reports(self):
        self.api.force_authenticate(user=self.employee)

        deals_response = self.api.get('/api/reports/deals/')
        tasks_response = self.api.get('/api/reports/tasks/')

        self.assertEqual(deals_response.status_code, 403)
        self.assertEqual(tasks_response.status_code, 403)

    def test_deals_report_can_export_csv(self):
        self.api.force_authenticate(user=self.manager)

        response = self.api.get('/api/reports/deals/', {'export': 'csv'})

        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response['Content-Type'])
        self.assertIn('REP-001', response.content.decode('utf-8'))

    def test_tasks_report_can_export_xlsx(self):
        self.api.force_authenticate(user=self.manager)

        response = self.api.get('/api/reports/tasks/', {'export': 'xlsx'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        rows = load_xlsx_rows(response.content, sheet_name='Данные')
        self.assertEqual(rows[0][1], 'Задача')
        self.assertTrue(any('Prepare documents' in row for row in rows))

    def test_tasks_report_can_export_pdf(self):
        self.api.force_authenticate(user=self.manager)

        response = self.api.get('/api/reports/tasks/', {'export': 'pdf'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_deals_report_supports_user_defined_sorting(self):
        self.api.force_authenticate(user=self.manager)

        response = self.api.get('/api/reports/deals/', {'ordering': 'price_final'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['ordering'], 'price_final')
        self.assertEqual(response.data['rows'][0]['deal_number'], 'REP-002')
        self.assertEqual(response.data['rows'][1]['deal_number'], 'REP-001')

    def test_tasks_report_supports_user_defined_sorting(self):
        self.api.force_authenticate(user=self.manager)

        response = self.api.get('/api/reports/tasks/', {'ordering': 'title'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['ordering'], 'title')
        self.assertEqual(response.data['rows'][0]['title'], 'Call other client')
        self.assertEqual(response.data['rows'][1]['title'], 'Prepare documents')

    def test_deals_report_can_export_json(self):
        self.api.force_authenticate(user=self.manager)

        response = self.api.get('/api/reports/deals/', {'export': 'json'})

        self.assertEqual(response.status_code, 200)
        self.assertIn('application/json', response['Content-Type'])
        self.assertIn('REP-001', response.content.decode('utf-8'))

    def test_client_cannot_access_reports(self):
        self.api.force_authenticate(user=self.client_user)

        deals_response = self.api.get('/api/reports/deals/')
        tasks_response = self.api.get('/api/reports/tasks/')

        self.assertEqual(deals_response.status_code, 403)
        self.assertEqual(tasks_response.status_code, 403)

    def test_completed_deal_auto_closes_active_tasks_and_creates_snapshots(self):
        completed_status = models.DealStatus.objects.create(
            code='completed',
            name='Completed',
        )
        in_progress_status = models.TaskStatus.objects.create(
            code='in_progress',
            name='In progress',
            order=15,
        )
        deal = models.Deal.objects.create(
            deal_number='REP-003',
            property=self.property,
            agent=self.employee,
            client=self.client_user,
            operation_type=self.operation_type,
            status=self.deal_status,
            price_final=8_000_000,
            commission_percent=4,
            deal_date=timezone.localdate(),
        )
        task = models.Task.objects.create(
            title='Follow up signed deal',
            task_type='call',
            status=in_progress_status,
            assignee=self.employee,
            created_by=self.manager,
            deal=deal,
        )

        deal.status = completed_status
        deal.save(update_fields=['status'])
        models.rebuild_report_snapshots(
            deal_dates=[timezone.localdate()],
            task_dates=[timezone.localdate()],
        )

        task.refresh_from_db()
        self.assertTrue(task.is_auto_closed)
        self.assertEqual(task.status.code, 'done')
        self.assertIsNotNone(task.completed_at)
        self.assertTrue(
            models.ReportMetricSnapshot.objects.filter(
                entity_type=models.ReportMetricSnapshot.ENTITY_DEAL,
                snapshot_date=timezone.localdate(),
            ).exists()
        )
        self.assertTrue(
            models.AgentPerformanceSnapshot.objects.filter(
                user=self.employee,
                snapshot_date=timezone.localdate(),
            ).exists()
        )

    def test_reports_payload_contains_analytics_insights(self):
        self.api.force_authenticate(user=self.manager)
        models.rebuild_report_snapshots(
            deal_dates=[timezone.localdate()],
            task_dates=[timezone.localdate()],
        )

        response = self.api.get('/api/reports/tasks/')

        self.assertEqual(response.status_code, 200)
        report_payload = reports.build_tasks_report({}, user=self.manager)
        self.assertTrue(report_payload['insights'])


class DataExchangeApiTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.operation_sale = models.OperationType.objects.create(
            code='sale',
            name='Sale',
        )
        self.operation_rent = models.OperationType.objects.create(
            code='rent',
            name='Rent',
        )
        self.status_active = models.PropertyStatus.objects.create(
            code='active',
            name='Active',
        )
        self.status_archived = models.PropertyStatus.objects.create(
            code='archived',
            name='Archived',
        )
        self.role_manager = models.UserRole.objects.create(
            code='manager',
            name='Manager',
        )
        self.manager = models.User.objects.create_user(
            username='exchange-manager',
            email='exchange-manager@example.com',
            password='Secret123!',
            user_type='employee',
            role=self.role_manager,
        )
        self.employee = models.User.objects.create_user(
            username='exchange-employee',
            email='exchange-employee@example.com',
            password='Secret123!',
            user_type='employee',
        )
        self.client_user = models.User.objects.create_user(
            username='exchange-client',
            email='exchange-client@example.com',
            password='Secret123!',
            user_type='client',
        )
        self.request_status_open = models.RequestStatus.objects.create(
            code='open',
            name='Open',
        )
        self.task_status_new = models.TaskStatus.objects.create(
            code='new',
            name='New',
            order=10,
        )
        self.deal_status_signed = models.DealStatus.objects.create(
            code='signed',
            name='Signed',
            order=10,
        )

        city = models.City.objects.create(name='Иркутск', region='Иркутская область')
        street = models.Street.objects.create(city=city, name='Ленина', street_type='ул.')
        house = models.House.objects.create(street=street, house_number='1', postal_code='664000')
        address = models.Address.objects.create(house=house, apartment_number='5')

        self.property = models.Property.objects.create(
            title='Тестовый объект',
            operation_type=self.operation_sale,
            status=self.status_active,
            address=address,
            price=5_500_000,
            rooms_count=2,
        )
        self.archived_property = models.Property.objects.create(
            title='Архивный объект',
            operation_type=self.operation_rent,
            status=self.status_archived,
            address=address,
            price=45_000,
            rooms_count=1,
        )
        self.request_obj = models.Request.objects.create(
            client=self.client_user,
            agent=self.employee,
            property=self.property,
            operation_type=self.operation_sale,
            status=self.request_status_open,
            description='Экспортная заявка',
        )
        self.task_obj = models.Task.objects.create(
            title='Экспортная задача',
            task_type='call',
            status=self.task_status_new,
            assignee=self.employee,
            created_by=self.manager,
            client=self.client_user,
            property=self.property,
            request=self.request_obj,
        )
        self.deal_obj = models.Deal.objects.create(
            deal_number='EX-001',
            property=self.property,
            agent=self.employee,
            client=self.client_user,
            request=self.request_obj,
            operation_type=self.operation_sale,
            status=self.deal_status_signed,
            price_final=5_500_000,
            deal_date=timezone.localdate(),
        )

    def _csv_upload(self, content: str, name: str = 'properties.csv'):
        return SimpleUploadedFile(
            name,
            content.encode('utf-8'),
            content_type='text/csv',
        )

    def _xlsx_upload(self, rows, name: str = 'properties.xlsx'):
        return SimpleUploadedFile(
            name,
            build_xlsx_bytes([WorkbookSheet.from_rows('Объекты', rows)]),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

    def test_property_export_csv_respects_filters(self):
        self.api.force_authenticate(user=self.manager)

        response = self.api.get('/api/properties/export/', {
            'export_format': 'csv',
            'status': self.status_active.pk,
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response['Content-Type'])
        content = response.content.decode('utf-8')
        self.assertIn('Тестовый объект', content)
        self.assertNotIn('Архивный объект', content)

    def test_property_export_json_returns_catalog(self):
        self.api.force_authenticate(user=self.manager)

        response = self.api.get('/api/properties/export/', {'export_format': 'json'})

        self.assertEqual(response.status_code, 200)
        self.assertIn('application/json', response['Content-Type'])
        self.assertIn('properties_exchange-manager_', response['Content-Disposition'])
        self.assertIn('Тестовый объект', response.content.decode('utf-8'))
        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(len(payload), 2)
        self.assertIn('Идентификатор', payload[0])
        self.assertNotIn('description', payload[0])

    def test_request_export_json_respects_filters(self):
        models.Request.objects.create(
            client=self.client_user,
            agent=self.manager,
            property=self.property,
            operation_type=self.operation_sale,
            status=self.request_status_open,
            description='Чужая заявка',
        )
        self.api.force_authenticate(user=self.manager)

        response = self.api.get('/api/requests/export/', {
            'export_format': 'json',
            'agent': self.employee.pk,
        })

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]['Описание'], 'Экспортная заявка')
        self.assertIn('requests_exchange-manager_', response['Content-Disposition'])

    def test_request_export_is_forbidden_for_employee(self):
        self.api.force_authenticate(user=self.employee)

        response = self.api.get('/api/requests/export/', {
            'export_format': 'json',
            'date_from': timezone.localdate().isoformat(),
        })

        self.assertEqual(response.status_code, 403)

    def test_task_export_xlsx_returns_rows(self):
        self.api.force_authenticate(user=self.manager)

        response = self.api.get('/api/tasks/export/', {'export_format': 'xlsx'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        rows = load_xlsx_rows(response.content, sheet_name='Задачи')
        self.assertEqual(rows[0][1], 'Название')
        self.assertTrue(any('Экспортная задача' in row for row in rows[1:]))
        self.assertIn('tasks_exchange-manager_', response['Content-Disposition'])

    def test_task_export_is_forbidden_for_employee(self):
        self.api.force_authenticate(user=self.employee)

        response = self.api.get('/api/tasks/export/', {
            'export_format': 'xlsx',
            'date_from': timezone.localdate().isoformat(),
        })

        self.assertEqual(response.status_code, 403)

    def test_deal_export_csv_returns_rows(self):
        self.api.force_authenticate(user=self.manager)

        response = self.api.get('/api/deals/export/', {'export_format': 'csv'})

        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response['Content-Type'])
        self.assertIn('EX-001', response.content.decode('utf-8'))

    def test_user_export_requires_manager_role(self):
        self.api.force_authenticate(user=self.employee)

        denied = self.api.get('/api/users/export/', {'export_format': 'json'})

        self.assertEqual(denied.status_code, 403)

        self.api.force_authenticate(user=self.manager)
        allowed = self.api.get('/api/users/export/', {'export_format': 'json'})

        self.assertEqual(allowed.status_code, 200)
        body = allowed.content.decode('utf-8')
        self.assertIn('"Логин"', body)
        self.assertIn('exchange-employee', body)
        self.assertIn('clients_exchange-manager_', allowed['Content-Disposition'])

    def test_property_export_xlsx_returns_catalog(self):
        self.api.force_authenticate(user=self.manager)

        response = self.api.get('/api/properties/export/', {'export_format': 'xlsx'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        rows = load_xlsx_rows(response.content)
        self.assertEqual(rows[0][1], 'Название')
        self.assertTrue(any('Тестовый объект' in row for row in rows[1:]))
        self.assertIn('properties_exchange-manager_', response['Content-Disposition'])

    def test_agent_cannot_create_property(self):
        self.api.force_authenticate(user=self.employee)

        response = self.api.post(
            '/api/properties/',
            {
                'title': 'Недоступный объект',
                'operation_type': self.operation_sale.pk,
                'status': self.status_active.pk,
                'premises_type': 'apartment',
                'price': '5100000',
                'address_data': {
                    'value': 'Иркутск, ул. Ленина, д. 1',
                    'city': 'Иркутск',
                    'region': 'Иркутская область',
                    'street': 'Ленина',
                    'street_type': 'ул.',
                    'house': '1',
                    'flat': '1',
                    'postal_code': '664000',
                },
            },
            format='json',
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(models.Property.objects.filter(title='Недоступный объект').exists())

    def test_property_import_csv_creates_property(self):
        self.api.force_authenticate(user=self.manager)
        upload = self._csv_upload(
            '\n'.join([
                'id;title;operation_type_code;status_code;city;region;street;street_type;house;block;flat;postal_code;price;area_total;rooms_count;floor_number;total_floors;description',
                ';"Новый объект";sale;active;Иркутск;Иркутская область;Советская;ул.;15;;12;664000;6200000;56.4;2;3;9;"Импортирован из CSV"',
            ]),
        )

        response = self.api.post(
            '/api/properties/import-csv/',
            {'file': upload},
            format='multipart',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created'], 1)
        self.assertEqual(response.data['updated'], 0)
        created = models.Property.objects.get(title='Новый объект')
        self.assertEqual(created.status.code, 'active')
        self.assertEqual(created.operation_type.code, 'sale')
        self.assertEqual(str(created.address.house.street.city.name), 'Иркутск')
        self.assertTrue(models.AuditLog.objects.filter(
            entity_type='property',
            entity_id=created.pk,
            action_code='import_created',
        ).exists())

    def test_property_import_xlsx_creates_property(self):
        self.api.force_authenticate(user=self.manager)
        upload = self._xlsx_upload([
            (
                'id', 'title', 'operation_type_code', 'status_code', 'city', 'region',
                'street', 'street_type', 'house', 'block', 'flat', 'postal_code',
                'price', 'area_total', 'rooms_count', 'floor_number', 'total_floors',
                'description',
            ),
            (
                '', 'Новый объект XLSX', 'sale', 'active', 'Иркутск', 'Иркутская область',
                'Советская', 'ул.', '20', '', '14', '664000',
                '6400000', '58.2', '2', '4', '10', 'Импортирован из XLSX',
            ),
        ])

        response = self.api.post(
            '/api/properties/import-csv/',
            {'file': upload},
            format='multipart',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created'], 1)
        self.assertEqual(response.data['source'], 'xlsx_import')
        created = models.Property.objects.get(title='Новый объект XLSX')
        self.assertEqual(created.status.code, 'active')
        self.assertEqual(created.operation_type.code, 'sale')

    def test_agent_cannot_import_properties(self):
        self.api.force_authenticate(user=self.employee)
        upload = self._csv_upload(
            '\n'.join([
                'id;title;operation_type_code;status_code;city;region;street;street_type;house;block;flat;postal_code;price',
                ';"Запрещенный импорт";sale;active;Иркутск;Иркутская область;Советская;ул.;15;;12;664000;6200000',
            ]),
        )

        response = self.api.post(
            '/api/properties/import-csv/',
            {'file': upload},
            format='multipart',
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(models.Property.objects.filter(title='Запрещенный импорт').exists())

    def test_property_import_csv_updates_existing_property(self):
        self.api.force_authenticate(user=self.manager)
        upload = self._csv_upload(
            '\n'.join([
                'id;title;operation_type_code;status_code;city;region;street;street_type;house;block;flat;postal_code;price;area_total;rooms_count;floor_number;total_floors;description',
                f'{self.property.pk};"Объект после импорта";sale;active;Иркутск;Иркутская область;Ленина;ул.;1;;5;664000;7300000;61.0;3;5;10;"Обновлено из CSV"',
            ]),
        )

        response = self.api.post(
            '/api/properties/import-csv/',
            {'file': upload},
            format='multipart',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created'], 0)
        self.assertEqual(response.data['updated'], 1)
        self.property.refresh_from_db()
        self.assertEqual(self.property.title, 'Объект после импорта')
        self.assertEqual(self.property.price, 7_300_000)
        self.assertEqual(self.property.rooms_count, 3)
        self.assertTrue(models.AuditLog.objects.filter(
            entity_type='property',
            entity_id=self.property.pk,
            action_code='import_updated',
        ).exists())

    def test_property_import_csv_validates_status_and_rolls_back(self):
        self.api.force_authenticate(user=self.manager)
        before_count = models.Property.objects.count()
        upload = self._csv_upload(
            '\n'.join([
                'id;title;operation_type_code;status_code;city;region;street;street_type;house;block;flat;postal_code;price',
                ';"Ошибочный объект";sale;missing_status;Иркутск;Иркутская область;Марата;ул.;8;;;664000;4100000',
            ]),
        )

        response = self.api.post(
            '/api/properties/import-csv/',
            {'file': upload},
            format='multipart',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(models.Property.objects.count(), before_count)
        self.assertIn('status_code', response.data)

    def test_dictionary_export_json_returns_reference_bundle(self):
        self.api.force_authenticate(user=self.manager)

        response = self.api.get('/api/dictionaries/export/', {'export_format': 'json'})

        self.assertEqual(response.status_code, 200)
        self.assertIn('application/json', response['Content-Type'])
        body = response.content.decode('utf-8')
        self.assertIn('Типы операций', body)
        self.assertIn('Роли пользователей', body)
        payload = json.loads(body)
        self.assertTrue(any(item['Код'] == 'sale' for item in payload))

    def test_dictionary_export_xlsx_returns_reference_bundle(self):
        self.api.force_authenticate(user=self.manager)

        response = self.api.get('/api/dictionaries/export/', {'export_format': 'xlsx'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        rows = load_xlsx_rows(response.content, sheet_name='Справочники')
        self.assertEqual(rows[0][0], 'Справочник')
        self.assertTrue(any('sale' in row for row in rows[1:]))


class PropertyClientVisibilityTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.operation_type = models.OperationType.objects.create(
            code='sale',
            name='Продажа',
        )
        self.pending_status = models.PropertyStatus.objects.create(
            code='pending',
            name='На модерации',
        )
        self.active_status = models.PropertyStatus.objects.create(
            code='active',
            name='Активно',
        )
        self.archived_status = models.PropertyStatus.objects.create(
            code='archived',
            name='Архив',
        )
        self.manager_role = models.UserRole.objects.create(
            code='manager',
            name='Менеджер',
        )
        city = models.City.objects.create(name='Иркутск')
        street = models.Street.objects.create(city=city, name='Ленина')
        house = models.House.objects.create(street=street, house_number='1')
        self.address = models.Address.objects.create(house=house)
        self.client_user = models.User.objects.create_user(
            username='property-owner',
            email='property-owner@example.com',
            password='Secret123!',
            user_type='client',
            phone='+79990000001',
        )
        self.other_client = models.User.objects.create_user(
            username='property-other-client',
            email='property-other-client@example.com',
            password='Secret123!',
            user_type='client',
        )
        self.manager = models.User.objects.create_user(
            username='property-manager',
            email='property-manager@example.com',
            password='Secret123!',
            user_type='employee',
            role=self.manager_role,
        )
        self.moderator = models.User.objects.create_user(
            username='property-moderator',
            email='property-moderator@example.com',
            password='Secret123!',
            user_type='employee',
            role=models.UserRole.objects.create(
                code='moderator',
                name='Модератор',
            ),
        )

    def test_client_create_property_sets_owner_and_pending_status(self):
        self.api.force_authenticate(user=self.client_user)

        response = self.api.post(
            '/api/properties/',
            {
                'title': 'Client warehouse',
                'operation_type': self.operation_type.pk,
                'status': self.active_status.pk,
                'premises_type': models.Property.PREMISES_WAREHOUSE,
                'address': self.address.pk,
                'price': 5_000_000,
                'area_total': '120.00',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        property_obj = models.Property.objects.get(pk=response.data['id'])
        self.assertEqual(property_obj.owner_id, self.client_user.id)
        self.assertEqual(property_obj.status.code, 'pending')

    def test_client_can_upload_photo_to_own_pending_property(self):
        property_obj = models.Property.objects.create(
            title='Own pending property with photo',
            operation_type=self.operation_type,
            status=self.pending_status,
            address=self.address,
            owner=self.client_user,
            price=5_000_000,
            premises_type=models.Property.PREMISES_WAREHOUSE,
            area_total='120.00',
        )
        self.api.force_authenticate(user=self.client_user)

        response = self.api.post(
            '/api/property-photos/',
            {
                'property': property_obj.pk,
                'url': 'https://example.com/client-photo.jpg',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        photo = models.PropertyPhoto.objects.get(pk=response.data['id'])
        self.assertEqual(photo.property_id, property_obj.pk)

    def test_client_can_retrieve_own_pending_property(self):
        property_obj = models.Property.objects.create(
            title='Own pending property',
            operation_type=self.operation_type,
            status=self.pending_status,
            address=self.address,
            owner=self.client_user,
            price=5_000_000,
        )
        self.api.force_authenticate(user=self.client_user)

        response = self.api.get(f'/api/properties/{property_obj.pk}/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], property_obj.pk)

    def test_pending_property_is_hidden_from_public_catalog(self):
        pending_property = models.Property.objects.create(
            title='Pending public hidden property',
            operation_type=self.operation_type,
            status=self.pending_status,
            address=self.address,
            owner=self.client_user,
            price=5_000_000,
        )
        active_property = models.Property.objects.create(
            title='Active public property',
            operation_type=self.operation_type,
            status=self.active_status,
            address=self.address,
            owner=self.other_client,
            price=6_000_000,
        )
        self.api.force_authenticate(user=self.client_user)

        response = self.api.get('/api/properties/')

        self.assertEqual(response.status_code, 200)
        ids = {item['id'] for item in response.data['results']}
        self.assertNotIn(pending_property.pk, ids)
        self.assertIn(active_property.pk, ids)

    def test_client_sees_own_pending_property_only_in_my_properties(self):
        pending_property = models.Property.objects.create(
            title='Own pending list property',
            operation_type=self.operation_type,
            status=self.pending_status,
            address=self.address,
            owner=self.client_user,
            price=5_000_000,
        )
        self.api.force_authenticate(user=self.client_user)

        response = self.api.get('/api/properties/?owner=me')

        self.assertEqual(response.status_code, 200)
        ids = {item['id'] for item in response.data['results']}
        self.assertIn(pending_property.pk, ids)

    def test_client_cannot_retrieve_foreign_pending_property(self):
        property_obj = models.Property.objects.create(
            title='Foreign pending property',
            operation_type=self.operation_type,
            status=self.pending_status,
            address=self.address,
            owner=self.other_client,
            price=5_000_000,
        )
        self.api.force_authenticate(user=self.client_user)

        response = self.api.get(f'/api/properties/{property_obj.pk}/')

        self.assertEqual(response.status_code, 404)

    def test_manager_moderation_lists_pending_with_owner_contacts(self):
        property_obj = models.Property.objects.create(
            title='Pending moderation property',
            operation_type=self.operation_type,
            status=self.pending_status,
            address=self.address,
            owner=self.client_user,
            price=5_000_000,
        )
        self.api.force_authenticate(user=self.manager)

        response = self.api.get('/api/properties/moderation/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['id'], property_obj.pk)
        self.assertEqual(response.data[0]['owner_email'], self.client_user.email)
        self.assertEqual(response.data[0]['owner_phone'], self.client_user.phone)

    def test_manager_can_approve_pending_property(self):
        property_obj = models.Property.objects.create(
            title='Approve property',
            operation_type=self.operation_type,
            status=self.pending_status,
            address=self.address,
            owner=self.client_user,
            price=5_000_000,
        )
        self.api.force_authenticate(user=self.manager)

        response = self.api.post(f'/api/properties/{property_obj.pk}/approve/')

        self.assertEqual(response.status_code, 200)
        property_obj.refresh_from_db()
        self.assertEqual(property_obj.status.code, 'active')

    def test_manager_can_reject_pending_property(self):
        property_obj = models.Property.objects.create(
            title='Reject property',
            operation_type=self.operation_type,
            status=self.pending_status,
            address=self.address,
            owner=self.client_user,
            price=5_000_000,
        )
        self.api.force_authenticate(user=self.manager)

        response = self.api.post(f'/api/properties/{property_obj.pk}/reject/')

        self.assertEqual(response.status_code, 200)
        property_obj.refresh_from_db()
        self.assertEqual(property_obj.status.code, 'archived')

    def test_moderator_can_approve_pending_property(self):
        property_obj = models.Property.objects.create(
            title='Moderator approve property',
            operation_type=self.operation_type,
            status=self.pending_status,
            address=self.address,
            owner=self.client_user,
            price=5_000_000,
        )
        self.api.force_authenticate(user=self.moderator)

        response = self.api.post(f'/api/properties/{property_obj.pk}/approve/')

        self.assertEqual(response.status_code, 200)
        property_obj.refresh_from_db()
        self.assertEqual(property_obj.status.code, 'active')

    def test_warehouse_rejects_rooms_and_floors(self):
        self.api.force_authenticate(user=self.manager)

        response = self.api.post(
            '/api/properties/',
            {
                'title': 'Invalid warehouse',
                'operation_type': self.operation_type.pk,
                'status': self.active_status.pk,
                'premises_type': models.Property.PREMISES_WAREHOUSE,
                'address': self.address.pk,
                'price': 5_000_000,
                'area_total': '120.00',
                'rooms_count': 2,
                'floor_number': 1,
                'total_floors': 1,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('rooms_count', response.data)
        self.assertIn('floor_number', response.data)
        self.assertIn('total_floors', response.data)

    def test_apartment_allows_empty_floor_fields(self):
        self.api.force_authenticate(user=self.manager)

        response = self.api.post(
            '/api/properties/',
            {
                'title': 'Apartment without floor',
                'operation_type': self.operation_type.pk,
                'status': self.active_status.pk,
                'premises_type': models.Property.PREMISES_APARTMENT,
                'address': self.address.pk,
                'price': 5_000_000,
                'area_total': '45.00',
                'rooms_count': 2,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        property_obj = models.Property.objects.get(pk=response.data['id'])
        self.assertIsNone(property_obj.floor_number)
        self.assertIsNone(property_obj.total_floors)

    def test_house_rejects_separate_floor_number(self):
        self.api.force_authenticate(user=self.manager)

        response = self.api.post(
            '/api/properties/',
            {
                'title': 'Invalid house',
                'operation_type': self.operation_type.pk,
                'status': self.active_status.pk,
                'premises_type': models.Property.PREMISES_HOUSE,
                'address': self.address.pk,
                'price': 5_000_000,
                'area_total': '120.00',
                'floor_number': 1,
                'total_floors': 2,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('floor_number', response.data)

    def test_land_update_ignores_hidden_residential_fields(self):
        self.api.force_authenticate(user=self.manager)
        property_type = models.PropertyType.objects.create(
            code=models.Property.PROPERTY_TYPE_LAND,
            name='Земельный участок',
        )
        land_property = models.Property.objects.create(
            title='Участок для обновления',
            operation_type=self.operation_type,
            status=self.active_status,
            house=self.address.house,
            property_type_ref=property_type,
            price=3_000_000,
            area_total='1200.00',
        )

        response = self.api.put(
            f'/api/properties/{land_property.pk}/',
            {
                'title': 'Участок для обновления',
                'operation_type': self.operation_type.pk,
                'status': self.active_status.pk,
                'premises_type': models.Property.PROPERTY_TYPE_LAND,
                'address': self.address.pk,
                'price': 3_250_000,
                'area_total': '1200.00',
                'rooms_count': None,
                'floor_number': None,
                'building_details_data': {
                    'year_built': None,
                    'total_floors': None,
                    'building_material': None,
                    'elevators_count': 0,
                },
                'property_details_data': {
                    'living_area': None,
                    'kitchen_area': None,
                    'ceiling_height': None,
                    'balcony_count': None,
                    'bathroom_count': None,
                    'bathroom_type': None,
                    'renovation_type': None,
                    'bedrooms_count': None,
                    'floors_count': None,
                    'land_area': '1200.00',
                },
                'commercial_property_details_data': {
                    'commercial_type': None,
                    'usable_area': None,
                },
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        land_property.refresh_from_db()
        self.assertEqual(land_property.price, 3_250_000)
        self.assertIsNone(land_property.rooms_count)
        self.assertIsNone(land_property.floor_number)
        self.assertIsNone(land_property.total_floors)


class AuditLogApiTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.operation_type = models.OperationType.objects.create(
            code='sale',
            name='Sale',
        )
        self.request_status_open = models.RequestStatus.objects.create(
            code='open',
            name='Open',
        )
        self.request_status_processing = models.RequestStatus.objects.create(
            code='processing',
            name='Processing',
        )
        self.property_status_active = models.PropertyStatus.objects.create(
            code='active',
            name='Active',
        )
        self.property_status_archived = models.PropertyStatus.objects.create(
            code='archived',
            name='Archived',
        )
        self.task_status_new = models.TaskStatus.objects.create(
            code='new',
            name='New',
            order=10,
        )
        self.task_status_done = models.TaskStatus.objects.create(
            code='done',
            name='Done',
            order=20,
        )
        self.deal_status_new = models.DealStatus.objects.create(
            code='new',
            name='New',
            order=10,
        )
        self.deal_status_negotiation = models.DealStatus.objects.create(
            code='negotiation',
            name='Negotiation',
            order=20,
        )
        self.employee = models.User.objects.create_user(
            username='audit-agent',
            email='audit-agent@example.com',
            password='Secret123!',
            user_type='employee',
        )
        self.client_user = models.User.objects.create_user(
            username='audit-client',
            email='audit-client@example.com',
            password='Secret123!',
            user_type='client',
        )
        self.other_client = models.User.objects.create_user(
            username='audit-other-client',
            email='audit-other-client@example.com',
            password='Secret123!',
            user_type='client',
        )

        city = models.City.objects.create(name='Irkutsk', region='Region')
        street = models.Street.objects.create(city=city, name='Lenina')
        house = models.House.objects.create(street=street, house_number='42')
        address = models.Address.objects.create(
            house=house,
            apartment_number='8',
        )
        self.property = models.Property.objects.create(
            title='Audit property',
            operation_type=self.operation_type,
            status=self.property_status_active,
            address=address,
            price=8_800_000,
        )
        self.request_obj = models.Request.objects.create(
            client=self.client_user,
            operation_type=self.operation_type,
            status=self.request_status_open,
            property=self.property,
        )

    def test_take_request_creates_request_and_task_audit_entries(self):
        self.api.force_authenticate(user=self.employee)

        response = self.api.post(
            f'/api/requests/{self.request_obj.pk}/take/',
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(models.AuditLog.objects.filter(
            request=self.request_obj,
            action_code='assigned',
        ).exists())
        contact_task = models.Task.objects.get(
            request=self.request_obj,
            task_type='contact_client',
        )
        self.assertTrue(models.AuditLog.objects.filter(
            task=contact_task,
            action_code='created',
        ).exists())

    def test_property_status_change_is_available_in_audit_endpoint(self):
        self.api.force_authenticate(user=self.employee)

        response = self.api.post(
            f'/api/properties/{self.property.pk}/change_status/',
            {'status_id': self.property_status_archived.pk},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(models.AuditLog.objects.filter(
            property=self.property,
            action_code='status_changed',
        ).exists())

        logs_response = self.api.get('/api/audit-log/', {
            'property': self.property.pk,
            'page_size': 50,
        })

        self.assertEqual(logs_response.status_code, 200)
        self.assertTrue(any(
            item['action_code'] == 'status_changed'
            for item in logs_response.data['results']
        ))

    def test_client_cannot_access_audit_logs_endpoint(self):
        other_request = models.Request.objects.create(
            client=self.other_client,
            operation_type=self.operation_type,
            status=self.request_status_open,
        )
        self.api.force_authenticate(user=self.employee)
        self.api.post(f'/api/requests/{self.request_obj.pk}/take/', format='json')
        self.api.post(f'/api/requests/{other_request.pk}/take/', format='json')

        self.api.force_authenticate(user=self.client_user)
        response = self.api.get('/api/audit-log/', {'page_size': 100})

        self.assertEqual(response.status_code, 403)

    def test_task_completion_creates_audit_entry_and_filter_works(self):
        task = models.Task.objects.create(
            title='Audit task',
            task_type='call',
            status=self.task_status_new,
            assignee=self.employee,
            created_by=self.employee,
            client=self.client_user,
            property=self.property,
            request=self.request_obj,
        )
        self.api.force_authenticate(user=self.employee)

        response = self.api.post(
            f'/api/tasks/{task.pk}/complete/',
            {'result': 'Completed successfully'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(models.AuditLog.objects.filter(
            task=task,
            action_code='completed',
        ).exists())

        logs_response = self.api.get('/api/audit-log/', {
            'task': task.pk,
            'page_size': 50,
        })
        self.assertEqual(logs_response.status_code, 200)
        self.assertTrue(any(
            item['action_code'] == 'completed'
            for item in logs_response.data['results']
        ))

    def test_property_update_audit_contains_old_and_new_values(self):
        self.api.force_authenticate(user=self.employee)

        response = self.api.patch(
            f'/api/properties/{self.property.pk}/',
            {
                'title': 'Audit property updated',
                'price': 9_100_000,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        audit_entry = models.AuditLog.objects.filter(
            property=self.property,
            action_code='updated',
        ).latest('created_at')
        field_changes = audit_entry.metadata['field_changes']
        self.assertEqual(field_changes['title']['old'], 'Audit property')
        self.assertEqual(field_changes['title']['new'], 'Audit property updated')
        self.assertEqual(field_changes['price']['old'], 8_800_000)
        self.assertEqual(field_changes['price']['new'], 9_100_000)

    def test_task_update_audit_contains_related_field_diff(self):
        task = models.Task.objects.create(
            title='Audit task update',
            task_type='call',
            status=self.task_status_new,
            assignee=self.employee,
            created_by=self.employee,
            client=self.client_user,
            property=self.property,
            request=self.request_obj,
        )
        self.api.force_authenticate(user=self.employee)

        response = self.api.patch(
            f'/api/tasks/{task.pk}/',
            {
                'title': 'Audit task changed',
                'client': self.other_client.pk,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        audit_entry = models.AuditLog.objects.filter(
            task=task,
            action_code='updated',
        ).latest('created_at')
        field_changes = audit_entry.metadata['field_changes']
        self.assertEqual(field_changes['title']['old'], 'Audit task update')
        self.assertEqual(field_changes['title']['new'], 'Audit task changed')
        self.assertEqual(
            field_changes['client']['old'],
            {'id': self.client_user.pk, 'label': self.client_user.username},
        )
        self.assertEqual(
            field_changes['client']['new'],
            {'id': self.other_client.pk, 'label': self.other_client.username},
        )

    def test_deal_status_change_creates_audit_entry(self):
        deal = models.Deal.objects.create(
            deal_number='AUD-001',
            property=self.property,
            agent=self.employee,
            client=self.client_user,
            operation_type=self.operation_type,
            status=self.deal_status_new,
            request=self.request_obj,
            price_final=8_800_000,
            deal_date=timezone.localdate(),
        )
        self.api.force_authenticate(user=self.employee)

        response = self.api.post(
            f'/api/deals/{deal.pk}/change_status/',
            {'status_id': self.deal_status_negotiation.pk},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(models.AuditLog.objects.filter(
            deal=deal,
            action_code='status_changed',
        ).exists())


class RoleBasedWorkloadLimitTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.role_agent = models.UserRole.objects.create(
            code='agent',
            name='Agent',
            max_active_tasks=3,
            max_in_progress_tasks=2,
            max_active_requests=1,
        )
        self.employee = models.User.objects.create_user(
            username='role-limit-agent',
            email='role-limit-agent@example.com',
            password='Secret123!',
            user_type='employee',
            role=self.role_agent,
        )
        self.other_employee = models.User.objects.create_user(
            username='role-limit-other',
            email='role-limit-other@example.com',
            password='Secret123!',
            user_type='employee',
        )
        self.client_user = models.User.objects.create_user(
            username='role-limit-client',
            email='role-limit-client@example.com',
            password='Secret123!',
            user_type='client',
        )
        self.request_status_open = models.RequestStatus.objects.create(
            code='open',
            name='Open',
        )
        self.operation_type = models.OperationType.objects.create(
            code='sale',
            name='Sale',
        )
        self.task_status_waiting = models.TaskStatus.objects.create(
            code='waiting',
            name='Waiting',
            order=10,
        )
        self.task_status_in_progress = models.TaskStatus.objects.create(
            code='in_progress',
            name='In progress',
            order=20,
        )

    def test_workload_endpoint_uses_limits_from_role(self):
        models.Task.objects.create(
            title='Waiting task',
            status=self.task_status_waiting,
            assignee=self.employee,
            created_by=self.employee,
        )
        models.Request.objects.create(
            client=self.client_user,
            agent=self.employee,
            operation_type=self.operation_type,
            status=self.request_status_open,
        )
        self.api.force_authenticate(user=self.employee)

        response = self.api.get('/api/users/me/workload/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['max_active_tasks'], 3)
        self.assertEqual(response.data['max_in_progress_tasks'], 2)
        self.assertEqual(response.data['max_active_requests'], 1)
        self.assertEqual(response.data['active_tasks'], 1)
        self.assertEqual(response.data['active_requests'], 1)

    def test_role_limit_allows_second_task_in_progress(self):
        current_task = models.Task.objects.create(
            title='Current task',
            status=self.task_status_in_progress,
            assignee=self.employee,
            created_by=self.employee,
        )
        waiting_task = models.Task.objects.create(
            title='Waiting task',
            status=self.task_status_waiting,
            assignee=self.employee,
            created_by=self.employee,
        )
        self.api.force_authenticate(user=self.employee)

        response = self.api.post(f'/api/tasks/{waiting_task.pk}/start/')

        self.assertEqual(response.status_code, 200)
        current_task.refresh_from_db()
        waiting_task.refresh_from_db()
        self.assertEqual(current_task.status_id, self.task_status_in_progress.pk)
        self.assertEqual(waiting_task.status_id, self.task_status_in_progress.pk)

    def test_role_limit_blocks_second_active_request_when_cap_is_one(self):
        models.Request.objects.create(
            client=self.client_user,
            agent=self.employee,
            operation_type=self.operation_type,
            status=self.request_status_open,
        )
        new_request = models.Request.objects.create(
            client=models.User.objects.create_user(
                username='role-limit-client-2',
                email='role-limit-client-2@example.com',
                password='Secret123!',
                user_type='client',
            ),
            agent=None,
            operation_type=self.operation_type,
            status=self.request_status_open,
        )
        self.api.force_authenticate(user=self.employee)

        response = self.api.post(f'/api/requests/{new_request.pk}/take/')

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['code'], 'max_active_requests')


class RequestDealCreationTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.operation_type = models.OperationType.objects.create(
            code='sale',
            name='Sale',
        )
        self.request_status_open = models.RequestStatus.objects.create(
            code='open',
            name='Open',
        )
        self.request_status_completed = models.RequestStatus.objects.create(
            code='completed',
            name='Completed',
        )
        self.property_status = models.PropertyStatus.objects.create(
            code='active',
            name='Active',
        )
        self.employee = models.User.objects.create_user(
            username='deal-agent',
            email='deal-agent@example.com',
            password='Secret123!',
            user_type='employee',
        )
        self.client_user = models.User.objects.create_user(
            username='deal-client',
            email='deal-client@example.com',
            password='Secret123!',
            user_type='client',
        )
        city = models.City.objects.create(name='Irkutsk', region='Region')
        street = models.Street.objects.create(city=city, name='Lenina')
        house = models.House.objects.create(street=street, house_number='10')
        address = models.Address.objects.create(
            house=house,
            apartment_number='1',
        )
        self.property = models.Property.objects.create(
            title='Suggested property',
            operation_type=self.operation_type,
            status=self.property_status,
            address=address,
            price=7_500_000,
        )
        self.request_obj = models.Request.objects.create(
            client=self.client_user,
            agent=self.employee,
            operation_type=self.operation_type,
            status=self.request_status_open,
        )
        models.RequestPropertyMatch.objects.create(
            request=self.request_obj,
            property=self.property,
            agent=self.employee,
            is_offered=True,
        )
        self.api.force_authenticate(user=self.employee)

    def test_close_with_only_offered_match_does_not_create_deal(self):
        response = self.api.post(
            f'/api/requests/{self.request_obj.pk}/close/',
            {'outcome': 'completed'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.request_obj.refresh_from_db()
        self.assertEqual(
            self.request_obj.status_id, self.request_status_completed.pk,
        )
        self.assertEqual(response.data['status_code'], 'completed')
        self.assertNotIn('deal', response.data)
        self.assertFalse(
            models.Deal.objects.filter(request=self.request_obj).exists(),
        )


class RequestWorkflowLifecycleTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.operation_type = models.OperationType.objects.create(
            code='sale',
            name='Sale',
        )
        self.request_status_open = models.RequestStatus.objects.create(
            code='open',
            name='Open',
        )
        self.request_status_processing = models.RequestStatus.objects.create(
            code='processing',
            name='Processing',
        )
        self.request_status_completed = models.RequestStatus.objects.create(
            code='completed',
            name='Completed',
        )
        self.property_status = models.PropertyStatus.objects.create(
            code='active',
            name='Active',
        )
        self.task_status_new = models.TaskStatus.objects.create(
            code='new',
            name='New',
            order=10,
        )
        self.task_status_done = models.TaskStatus.objects.create(
            code='done',
            name='Done',
            order=20,
        )
        self.deal_status_new = models.DealStatus.objects.create(
            code='new',
            name='New',
            order=10,
        )
        self.manager_role = models.UserRole.objects.create(
            code='manager',
            name='Manager',
        )
        self.employee = models.User.objects.create_user(
            username='workflow-agent',
            email='workflow-agent@example.com',
            password='Secret123!',
            user_type='employee',
        )
        models.EmployeeProfile.objects.create(
            user=self.employee,
            first_name='Иван',
            last_name='Петров',
        )
        self.client_user = models.User.objects.create_user(
            username='workflow-client',
            email='workflow-client@example.com',
            password='Secret123!',
            user_type='client',
        )
        models.ClientProfile.objects.create(
            user=self.client_user,
            first_name='Анна',
            last_name='Сидорова',
            middle_name='Олеговна',
        )
        self.manager = models.User.objects.create_user(
            username='workflow-manager',
            email='workflow-manager@example.com',
            password='Secret123!',
            user_type='employee',
            role=self.manager_role,
        )

        city = models.City.objects.create(name='Irkutsk', region='Region')
        street = models.Street.objects.create(city=city, name='Lenina')
        house = models.House.objects.create(street=street, house_number='15')
        address = models.Address.objects.create(
            house=house,
            apartment_number='5',
        )
        self.property = models.Property.objects.create(
            title='Workflow property',
            operation_type=self.operation_type,
            status=self.property_status,
            address=address,
            price=9_100_000,
        )

    def test_take_request_creates_contact_task_and_email(self):
        request_obj = models.Request.objects.create(
            client=self.client_user,
            operation_type=self.operation_type,
            status=self.request_status_open,
        )
        self.api.force_authenticate(user=self.employee)

        response = self.api.post(
            f'/api/requests/{request_obj.pk}/take/',
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        request_obj.refresh_from_db()
        self.assertEqual(request_obj.agent_id, self.employee.pk)
        self.assertEqual(
            request_obj.status_id,
            self.request_status_processing.pk,
        )

        task = models.Task.objects.get(
            request=request_obj,
            task_type='contact_client',
        )
        self.assertEqual(task.assignee_id, self.employee.pk)
        self.assertEqual(task.status_id, self.task_status_new.pk)
        self.assertTrue(task.title.startswith('Связаться с клиентом'))

        self.assertTrue(models.OutgoingEmail.objects.filter(
            trigger_code='request_taken',
            request=request_obj,
            recipient=self.client_user,
            status='pending',
        ).exists())

    def test_take_request_response_contains_client_and_agent_full_names(self):
        request_obj = models.Request.objects.create(
            client=self.client_user,
            operation_type=self.operation_type,
            status=self.request_status_open,
        )
        self.api.force_authenticate(user=self.employee)

        response = self.api.post(
            f'/api/requests/{request_obj.pk}/take/',
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['client_full_name'], 'Сидорова Анна Олеговна')
        self.assertEqual(response.data['agent_full_name'], 'Петров Иван')

    def test_request_search_finds_by_client_full_name(self):
        models.Request.objects.create(
            client=self.client_user,
            operation_type=self.operation_type,
            status=self.request_status_open,
        )
        self.api.force_authenticate(user=self.manager)

        response = self.api.get('/api/requests/?search=Сидорова')

        self.assertEqual(response.status_code, 200)
        items = response.data['results']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['client_full_name'], 'Сидорова Анна Олеговна')

    def test_take_request_persists_employee_profile_field(self):
        request_obj = models.Request.objects.create(
            client=self.client_user,
            operation_type=self.operation_type,
            status=self.request_status_open,
        )

        result = request_lifecycle.take_request(
            request_obj,
            actor=self.employee,
        )

        request_obj.refresh_from_db()
        self.assertEqual(result.request.pk, request_obj.pk)
        self.assertEqual(request_obj.employee_profile_id, self.employee.employee_profile.pk)
        self.assertEqual(request_obj.agent_id, self.employee.pk)

    def test_repeated_take_does_not_duplicate_contact_task_and_email(self):
        request_obj = models.Request.objects.create(
            client=self.client_user,
            operation_type=self.operation_type,
            status=self.request_status_open,
        )
        self.api.force_authenticate(user=self.employee)

        first_response = self.api.post(
            f'/api/requests/{request_obj.pk}/take/',
            format='json',
        )
        second_response = self.api.post(
            f'/api/requests/{request_obj.pk}/take/',
            format='json',
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(
            models.Task.objects.filter(
                request=request_obj,
                task_type='contact_client',
                assignee=self.employee,
            ).count(),
            1,
        )
        self.assertEqual(
            models.OutgoingEmail.objects.filter(
                trigger_code='request_taken',
                request=request_obj,
                recipient=self.client_user,
                status='pending',
            ).count(),
            1,
        )

    def test_create_request_with_assigned_agent_creates_contact_task_and_email(self):
        self.api.force_authenticate(user=self.employee)

        response = self.api.post(
            '/api/requests/',
            {
                'client': self.client_user.pk,
                'agent': self.employee.pk,
                'operation_type': self.operation_type.pk,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        request_obj = models.Request.objects.get(pk=response.data['id'])
        self.assertEqual(request_obj.agent_id, self.employee.pk)
        self.assertEqual(request_obj.status_id, self.request_status_processing.pk)
        self.assertTrue(models.Task.objects.filter(
            request=request_obj,
            task_type='contact_client',
            assignee=self.employee,
        ).exists())
        self.assertTrue(models.OutgoingEmail.objects.filter(
            trigger_code='request_taken',
            request=request_obj,
            recipient=self.client_user,
            status='pending',
        ).exists())

    def test_assigning_agent_via_update_creates_contact_task_and_email(self):
        request_obj = models.Request.objects.create(
            client=self.client_user,
            operation_type=self.operation_type,
            status=self.request_status_open,
        )
        self.api.force_authenticate(user=self.manager)

        response = self.api.patch(
            f'/api/requests/{request_obj.pk}/',
            {'agent': self.employee.pk},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        request_obj.refresh_from_db()
        self.assertEqual(request_obj.agent_id, self.employee.pk)
        self.assertEqual(request_obj.status_id, self.request_status_processing.pk)
        self.assertTrue(models.Task.objects.filter(
            request=request_obj,
            task_type='contact_client',
            assignee=self.employee,
        ).exists())
        self.assertTrue(models.OutgoingEmail.objects.filter(
            trigger_code='request_taken',
            request=request_obj,
            recipient=self.client_user,
            status='pending',
        ).exists())

    def test_confirm_property_auto_closes_search_task_and_queues_email(self):
        request_obj = models.Request.objects.create(
            client=self.client_user,
            agent=self.employee,
            operation_type=self.operation_type,
            status=self.request_status_processing,
        )
        match = models.RequestPropertyMatch.objects.create(
            request=request_obj,
            property=self.property,
            agent=self.employee,
            is_offered=True,
        )
        search_task = models.Task.objects.create(
            title='Search properties',
            task_type='property_search',
            status=self.task_status_new,
            assignee=self.employee,
            created_by=self.employee,
            client=self.client_user,
            request=request_obj,
        )
        self.api.force_authenticate(user=self.employee)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.api.post(
                f'/api/requests/{request_obj.pk}/confirm_property/',
                {'match_id': match.pk},
                format='json',
            )

        self.assertEqual(response.status_code, 200)
        search_task.refresh_from_db()
        self.assertEqual(search_task.status_id, self.task_status_done.pk)
        self.assertIsNotNone(search_task.completed_at)
        self.assertTrue(search_task.is_auto_closed)
        self.assertEqual(search_task.steps_log[-1]['outcome'], 'auto')

        self.assertTrue(models.OutgoingEmail.objects.filter(
            trigger_code='property_match_confirmed',
            request=request_obj,
            property=self.property,
            recipient=self.client_user,
            status='pending',
        ).exists())

    def test_close_request_with_confirmed_match_creates_deal(self):
        request_obj = models.Request.objects.create(
            client=self.client_user,
            agent=self.employee,
            operation_type=self.operation_type,
            status=self.request_status_processing,
        )
        models.RequestPropertyMatch.objects.create(
            request=request_obj,
            property=self.property,
            agent=self.employee,
            is_offered=True,
            is_confirmed=True,
            confirmed_at=timezone.now(),
            confirmed_by=self.employee,
        )
        self.api.force_authenticate(user=self.employee)

        response = self.api.post(
            f'/api/requests/{request_obj.pk}/close/',
            {'outcome': 'completed'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        request_obj.refresh_from_db()
        self.assertEqual(request_obj.status_id, self.request_status_completed.pk)

        deal = models.Deal.objects.get(request=request_obj)
        self.assertEqual(deal.property_id, self.property.pk)
        self.assertEqual(deal.agent_id, self.employee.pk)
        self.assertEqual(deal.client_id, self.client_user.pk)
        self.assertEqual(deal.contract_status, 'pending')
        self.assertFalse(bool(deal.contract_file))
        self.assertEqual(response.data['deal']['id'], deal.pk)
        self.assertEqual(response.data['deal']['property'], self.property.pk)
        self.assertEqual(response.data['deal']['contract_status'], 'pending')

        self.assertTrue(models.OutgoingEmail.objects.filter(
            trigger_code='request_closed',
            request=request_obj,
            recipient=self.client_user,
            status='pending',
        ).exists())

    def test_close_request_with_cancelled_outcome_does_not_create_deal(self):
        request_status_cancelled = models.RequestStatus.objects.create(
            code='cancelled',
            name='Cancelled',
        )
        request_obj = models.Request.objects.create(
            client=self.client_user,
            agent=self.employee,
            operation_type=self.operation_type,
            status=self.request_status_processing,
        )
        self.api.force_authenticate(user=self.employee)

        response = self.api.post(
            f'/api/requests/{request_obj.pk}/close/',
            {'outcome': 'cancelled'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        request_obj.refresh_from_db()
        self.assertEqual(request_obj.status_id, request_status_cancelled.pk)
        self.assertEqual(response.data['status_code'], 'cancelled')
        self.assertFalse(
            models.Deal.objects.filter(request=request_obj).exists(),
        )


class CoreCrmFlowTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.operation_type = models.OperationType.objects.create(
            code='sale',
            name='Sale',
        )
        self.request_status_open = models.RequestStatus.objects.create(
            code='open',
            name='Open',
        )
        self.request_status_processing = models.RequestStatus.objects.create(
            code='processing',
            name='Processing',
        )
        self.request_status_completed = models.RequestStatus.objects.create(
            code='completed',
            name='Completed',
        )
        self.property_status_active = models.PropertyStatus.objects.create(
            code='active',
            name='Active',
        )
        self.deal_status_new = models.DealStatus.objects.create(
            code='new',
            name='New',
            order=10,
        )
        self.task_status_new = models.TaskStatus.objects.create(
            code='new',
            name='New',
            order=10,
        )
        self.task_status_done = models.TaskStatus.objects.create(
            code='done',
            name='Done',
            order=20,
        )
        self.employee = models.User.objects.create_user(
            username='core-flow-agent',
            email='core-flow-agent@example.com',
            password='Secret123!',
            user_type='employee',
        )
        self.client_user = models.User.objects.create_user(
            username='core-flow-client',
            email='core-flow-client@example.com',
            password='Secret123!',
            user_type='client',
        )
        city = models.City.objects.create(name='Irkutsk', region='Region')
        street = models.Street.objects.create(city=city, name='Lenina')
        house = models.House.objects.create(street=street, house_number='21')
        address = models.Address.objects.create(
            house=house,
            apartment_number='6',
        )
        self.property = models.Property.objects.create(
            title='Core flow property',
            operation_type=self.operation_type,
            status=self.property_status_active,
            address=address,
            price=9_700_000,
        )
        self.request_obj = models.Request.objects.create(
            client=self.client_user,
            operation_type=self.operation_type,
            status=self.request_status_open,
        )
        self.api.force_authenticate(user=self.employee)

    def test_request_to_deal_flow_stays_consistent(self):
        take_response = self.api.post(
            f'/api/requests/{self.request_obj.pk}/take/',
            format='json',
        )
        self.assertEqual(take_response.status_code, 200)

        search_task = models.Task.objects.create(
            title='Property search',
            task_type='property_search',
            status=self.task_status_new,
            assignee=self.employee,
            created_by=self.employee,
            client=self.client_user,
            request=self.request_obj,
        )

        attach_response = self.api.post(
            f'/api/requests/{self.request_obj.pk}/attach_property/',
            {
                'property_id': self.property.pk,
                'agent_note': 'Подходящий вариант для клиента',
            },
            format='json',
        )
        self.assertEqual(attach_response.status_code, 201)
        match_id = attach_response.data['id']

        confirm_response = self.api.post(
            f'/api/requests/{self.request_obj.pk}/confirm_property/',
            {'match_id': match_id},
            format='json',
        )
        self.assertEqual(confirm_response.status_code, 200)

        search_task.refresh_from_db()
        self.assertEqual(search_task.status_id, self.task_status_done.pk)
        self.assertTrue(search_task.is_auto_closed)
        self.assertIsNotNone(search_task.completed_at)

        close_response = self.api.post(
            f'/api/requests/{self.request_obj.pk}/close/',
            {'outcome': 'completed'},
            format='json',
        )
        self.assertEqual(close_response.status_code, 200)

        self.request_obj.refresh_from_db()
        self.assertEqual(
            self.request_obj.status_id,
            self.request_status_completed.pk,
        )
        self.assertIsNotNone(self.request_obj.closed_at)

        deal = models.Deal.objects.get(request=self.request_obj)
        self.assertEqual(deal.property_id, self.property.pk)
        self.assertEqual(deal.agent_id, self.employee.pk)
        self.assertEqual(deal.client_id, self.client_user.pk)
        self.assertEqual(deal.contract_status, 'pending')

        contract_response = self.api.get(f'/api/deals/{deal.pk}/contract/')
        self.assertEqual(contract_response.status_code, 409)
        self.assertEqual(contract_response.data['contract_status'], 'pending')

        self.assertEqual(
            models.OutgoingEmail.objects.filter(
                request=self.request_obj,
                recipient=self.client_user,
                status='pending',
            ).count(),
            3,
        )


class RequestAgentScopeTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.operation_type = models.OperationType.objects.create(
            code='sale',
            name='Sale',
        )
        self.status_open = models.RequestStatus.objects.create(
            code='open',
            name='Open',
        )
        self.status_processing = models.RequestStatus.objects.create(
            code='processing',
            name='Processing',
        )
        self.agent = models.User.objects.create_user(
            username='scope-agent',
            email='scope-agent@example.com',
            password='Secret123!',
            user_type='employee',
        )
        self.other_agent = models.User.objects.create_user(
            username='scope-other-agent',
            email='scope-other-agent@example.com',
            password='Secret123!',
            user_type='employee',
        )
        self.client_one = models.User.objects.create_user(
            username='scope-client-one',
            email='scope-client-one@example.com',
            password='Secret123!',
            user_type='client',
        )
        self.client_two = models.User.objects.create_user(
            username='scope-client-two',
            email='scope-client-two@example.com',
            password='Secret123!',
            user_type='client',
        )
        self.own_request = models.Request.objects.create(
            client=self.client_one,
            agent=self.agent,
            operation_type=self.operation_type,
            status=self.status_processing,
        )
        self.unassigned_request = models.Request.objects.create(
            client=self.client_two,
            operation_type=self.operation_type,
            status=self.status_open,
        )
        self.foreign_request = models.Request.objects.create(
            client=self.client_two,
            agent=self.other_agent,
            operation_type=self.operation_type,
            status=self.status_processing,
        )

    def test_agent_list_sees_only_own_and_unassigned_requests(self):
        self.api.force_authenticate(user=self.agent)

        response = self.api.get('/api/requests/')

        self.assertEqual(response.status_code, 200)
        ids = {item['id'] for item in response.data['results']}
        self.assertIn(self.own_request.pk, ids)
        self.assertIn(self.unassigned_request.pk, ids)
        self.assertNotIn(self.foreign_request.pk, ids)

    def test_agent_cannot_close_foreign_request(self):
        self.api.force_authenticate(user=self.agent)

        response = self.api.post(
            f'/api/requests/{self.foreign_request.pk}/close/',
            {'outcome': 'completed'},
            format='json',
        )

        self.assertEqual(response.status_code, 404)
        self.foreign_request.refresh_from_db()
        self.assertEqual(self.foreign_request.status_id, self.status_processing.pk)


class TaskStatusChangeTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.status_new = models.TaskStatus.objects.create(
            code='new',
            name='New',
            order=10,
        )
        self.status_done = models.TaskStatus.objects.create(
            code='done',
            name='Done',
            order=20,
        )
        self.status_cancelled = models.TaskStatus.objects.create(
            code='cancelled',
            name='Cancelled',
            order=30,
        )
        self.employee = models.User.objects.create_user(
            username='task-user',
            email='task-user@example.com',
            password='Secret123!',
            user_type='employee',
        )

    def test_change_status_to_done_uses_completion_flow(self):
        task = models.Task.objects.create(
            title='Call client',
            status=self.status_new,
            assignee=self.employee,
            created_by=self.employee,
        )
        self.api.force_authenticate(user=self.employee)

        response = self.api.post(
            f'/api/tasks/{task.pk}/change_status/',
            {
                'status_id': self.status_done.pk,
                'result': {'summary': 'Reached the client'},
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.status_id, self.status_done.pk)
        self.assertIsNotNone(task.completed_at)
        self.assertEqual(task.result, 'Reached the client')
        self.assertEqual(task.steps_log[-1]['step'], 'completed')
        self.assertEqual(task.steps_log[-1]['outcome'], 'done')

    def test_change_status_to_cancelled_sets_completed_at(self):
        task = models.Task.objects.create(
            title='Prepare documents',
            status=self.status_new,
            assignee=self.employee,
            created_by=self.employee,
        )
        self.api.force_authenticate(user=self.employee)

        response = self.api.post(
            f'/api/tasks/{task.pk}/change_status/',
            {'status_id': self.status_cancelled.pk},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.status_id, self.status_cancelled.pk)
        self.assertIsNotNone(task.completed_at)


class TaskCrudRulesTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.status_new = models.TaskStatus.objects.create(
            code='new',
            name='New',
            order=10,
        )
        self.status_done = models.TaskStatus.objects.create(
            code='done',
            name='Done',
            order=20,
        )
        self.role_agent = models.UserRole.objects.create(
            code='agent',
            name='Agent',
            max_active_tasks=1,
        )
        self.creator = models.User.objects.create_user(
            username='task-crud-creator',
            email='task-crud-creator@example.com',
            password='Secret123!',
            user_type='employee',
            role=self.role_agent,
        )
        self.target_assignee = models.User.objects.create_user(
            username='task-crud-target',
            email='task-crud-target@example.com',
            password='Secret123!',
            user_type='employee',
            role=self.role_agent,
        )
        self.api.force_authenticate(user=self.creator)

    def test_terminal_task_cannot_be_updated(self):
        task = models.Task.objects.create(
            title='Completed task',
            status=self.status_done,
            assignee=self.creator,
            created_by=self.creator,
            completed_at=timezone.now(),
        )

        response = self.api.patch(
            f'/api/tasks/{task.pk}/',
            {'title': 'Updated title'},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        task.refresh_from_db()
        self.assertEqual(task.title, 'Completed task')
        self.assertIn('Нельзя редактировать завершённую задачу.', str(response.data))

    def test_terminal_task_cannot_be_deleted(self):
        task = models.Task.objects.create(
            title='Completed task',
            status=self.status_done,
            assignee=self.creator,
            created_by=self.creator,
            completed_at=timezone.now(),
        )

        response = self.api.delete(f'/api/tasks/{task.pk}/')

        self.assertEqual(response.status_code, 400)
        self.assertTrue(models.Task.objects.filter(pk=task.pk).exists())
        self.assertIn('Нельзя удалить завершённую задачу.', str(response.data))

    def test_patch_task_respects_assignee_active_task_limit(self):
        models.Task.objects.create(
            title='Busy task',
            status=self.status_new,
            assignee=self.target_assignee,
            created_by=self.target_assignee,
        )
        task = models.Task.objects.create(
            title='Reassign me',
            status=self.status_new,
            assignee=self.creator,
            created_by=self.creator,
        )

        response = self.api.patch(
            f'/api/tasks/{task.pk}/',
            {'assignee': self.target_assignee.pk},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        task.refresh_from_db()
        self.assertEqual(task.assignee_id, self.creator.pk)
        self.assertIn('Нельзя назначить задачу', str(response.data))


class TaskWorkflowValidationTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.status_new = models.TaskStatus.objects.create(
            code='new',
            name='New',
            order=10,
        )
        self.status_done = models.TaskStatus.objects.create(
            code='done',
            name='Done',
            order=20,
        )
        self.employee = models.User.objects.create_user(
            username='task-workflow-user',
            email='task-workflow-user@example.com',
            password='Secret123!',
            user_type='employee',
        )
        self.client_user = models.User.objects.create_user(
            username='task-workflow-client',
            email='task-workflow-client@example.com',
            password='Secret123!',
            user_type='client',
        )
        self.operation_type = models.OperationType.objects.create(
            code='sale',
            name='Sale',
        )
        self.request_status = models.RequestStatus.objects.create(
            code='processing',
            name='Processing',
        )
        self.match_status_confirmed = models.RequestMatchStatus.objects.create(
            code='confirmed',
            name='Confirmed',
        )
        self.property_status = models.PropertyStatus.objects.create(
            code='active',
            name='Active',
        )
        self.viewing_status_scheduled = models.ViewingStatus.objects.create(
            code='scheduled',
            name='Scheduled',
        )
        self.priority = models.TaskPriority.objects.create(
            code='normal',
            name='Normal',
        )
        self.showing_task_type = models.TaskType.objects.create(
            code='showing',
            name='Showing',
        )
        self.property_search_task_type = models.TaskType.objects.create(
            code='property_search',
            name='Property search',
        )
        self.contact_task_type = models.TaskType.objects.create(
            code='contact_client',
            name='Contact client',
        )
        self.employee_profile = models.EmployeeProfile.objects.create(
            user=self.employee,
            first_name='Workflow',
            last_name='Agent',
        )
        self.client_profile = models.ClientProfile.objects.create(
            user=self.client_user,
            first_name='Workflow',
            last_name='Client',
        )

        city = models.City.objects.create(name='Irkutsk', region='Region')
        street = models.Street.objects.create(city=city, name='Lenina')
        house = models.House.objects.create(street=street, house_number='21')
        address = models.Address.objects.create(
            house=house,
            apartment_number='8',
        )
        self.property = models.Property.objects.create(
            title='Workflow validation property',
            operation_type=self.operation_type,
            status=self.property_status,
            address=address,
            price=8_500_000,
        )

        self.api.force_authenticate(user=self.employee)

    def test_task_detail_includes_backend_workflow_steps(self):
        task = models.Task.objects.create(
            title='Search property',
            status=self.status_new,
            assignee=self.employee,
            created_by=self.employee,
            task_type_ref=self.property_search_task_type,
        )

        response = self.api.get(f'/api/tasks/{task.pk}/')

        self.assertEqual(response.status_code, 200)
        step_ids = [step['id'] for step in response.data['workflow_steps']]
        self.assertEqual(step_ids, ['contact', 'request', 'match', 'complete'])
        self.assertEqual(response.data['workflow_current_step'], 'contact')

    def test_terminal_task_detail_points_to_complete_step(self):
        task = models.Task.objects.create(
            title='Completed search property',
            status=self.status_done,
            assignee=self.employee,
            created_by=self.employee,
            completed_at=timezone.now(),
            task_type_ref=self.property_search_task_type,
        )

        response = self.api.get(f'/api/tasks/{task.pk}/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['workflow_current_step'], 'complete')

    def test_record_step_rejects_out_of_order_transition(self):
        task = models.Task.objects.create(
            title='Contact client',
            status=self.status_new,
            assignee=self.employee,
            created_by=self.employee,
            task_type_ref=self.contact_task_type,
        )

        response = self.api.post(
            f'/api/tasks/{task.pk}/record_step/',
            {'step': 'request', 'outcome': 'linked'},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('Сначала зафиксируйте этап', str(response.data['detail']))

    def test_request_step_requires_linked_request(self):
        task = models.Task.objects.create(
            title='Contact client',
            status=self.status_new,
            assignee=self.employee,
            created_by=self.employee,
            client_profile=self.client_profile,
            task_type_ref=self.contact_task_type,
        )

        first_response = self.api.post(
            f'/api/tasks/{task.pk}/record_step/',
            {'step': 'contact', 'outcome': 'called'},
            format='json',
        )
        second_response = self.api.post(
            f'/api/tasks/{task.pk}/record_step/',
            {'step': 'request', 'outcome': 'linked'},
            format='json',
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 400)
        self.assertEqual(
            str(second_response.data['detail']),
            'Сначала привяжите или создайте заявку для задачи.',
        )

    def test_match_confirmed_requires_confirmed_request_match(self):
        request_obj = models.Request.objects.create(
            client=self.client_user,
            agent=self.employee,
            operation_type=self.operation_type,
            status=self.request_status,
        )
        task = models.Task.objects.create(
            title='Search property',
            status=self.status_new,
            assignee=self.employee,
            created_by=self.employee,
            client_profile=self.client_profile,
            request=request_obj,
            task_type_ref=self.property_search_task_type,
        )

        self.api.post(
            f'/api/tasks/{task.pk}/record_step/',
            {'step': 'contact', 'outcome': 'called'},
            format='json',
        )
        self.api.post(
            f'/api/tasks/{task.pk}/record_step/',
            {'step': 'request', 'outcome': 'exists'},
            format='json',
        )
        response = self.api.post(
            f'/api/tasks/{task.pk}/record_step/',
            {'step': 'match', 'outcome': 'confirmed'},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('нет подтверждённого варианта', str(response.data['detail']))

    def test_match_workflow_accepts_valid_sequence(self):
        request_obj = models.Request.objects.create(
            client=self.client_user,
            agent=self.employee,
            operation_type=self.operation_type,
            status=self.request_status,
        )
        models.RequestPropertyMatch.objects.create(
            request=request_obj,
            property=self.property,
            employee_profile=self.employee_profile,
            status=self.match_status_confirmed,
            confirmed_at=timezone.now(),
            confirmed_by=self.employee,
        )
        task = models.Task.objects.create(
            title='Search property',
            status=self.status_new,
            assignee=self.employee,
            created_by=self.employee,
            client_profile=self.client_profile,
            request=request_obj,
            task_type_ref=self.property_search_task_type,
        )

        contact_response = self.api.post(
            f'/api/tasks/{task.pk}/record_step/',
            {'step': 'contact', 'outcome': 'called'},
            format='json',
        )
        request_response = self.api.post(
            f'/api/tasks/{task.pk}/record_step/',
            {'step': 'request', 'outcome': 'exists'},
            format='json',
        )
        match_response = self.api.post(
            f'/api/tasks/{task.pk}/record_step/',
            {'step': 'match', 'outcome': 'confirmed'},
            format='json',
        )

        self.assertEqual(contact_response.status_code, 200)
        self.assertEqual(request_response.status_code, 200)
        self.assertEqual(match_response.status_code, 200)
        self.assertEqual(match_response.data['workflow_current_step'], 'complete')
        self.assertEqual(match_response.data['steps_log'][-1]['step'], 'match')
        self.assertEqual(match_response.data['steps_log'][-1]['outcome'], 'confirmed')

    def test_showing_task_detail_includes_payment_step(self):
        task = models.Task.objects.create(
            title='Showing workflow',
            status=self.status_new,
            assignee=self.employee,
            created_by=self.employee,
            client_profile=self.client_profile,
            property=self.property,
            priority_ref=self.priority,
            task_type_ref=self.showing_task_type,
        )

        response = self.api.get(f'/api/tasks/{task.pk}/')

        self.assertEqual(response.status_code, 200)
        step_ids = [step['id'] for step in response.data['workflow_steps']]
        self.assertEqual(step_ids, ['contact', 'request', 'match', 'payment', 'complete'])
        self.assertEqual(response.data['workflow_current_step'], 'contact')

    def test_schedule_viewing_action_creates_viewing_for_showing_task(self):
        request_obj = models.Request.objects.create(
            client=self.client_user,
            agent=self.employee,
            operation_type=self.operation_type,
            status=self.request_status,
        )
        task = models.Task.objects.create(
            title='Schedule real viewing',
            status=self.status_new,
            assignee=self.employee,
            created_by=self.employee,
            client_profile=self.client_profile,
            property=self.property,
            request=request_obj,
            priority_ref=self.priority,
            task_type_ref=self.showing_task_type,
        )

        response = self.api.post(
            f'/api/tasks/{task.pk}/schedule_viewing/',
            {
                'viewing_date': '2030-01-01T10:30:00+08:00',
                'note': 'Client agreed to a real viewing',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data['task']['viewing_id'])
        self.assertEqual(response.data['viewing']['status_name'], 'Scheduled')
        self.assertEqual(
            models.PropertyViewing.objects.filter(
                property=self.property,
                client_profile=self.client_profile,
            ).count(),
            1,
        )

    def test_payment_step_requires_payment_link_for_showing_task(self):
        request_obj = models.Request.objects.create(
            client=self.client_user,
            agent=self.employee,
            operation_type=self.operation_type,
            status=self.request_status,
        )
        task = models.Task.objects.create(
            title='Showing payment step',
            status=self.status_new,
            assignee=self.employee,
            created_by=self.employee,
            client_profile=self.client_profile,
            property=self.property,
            request=request_obj,
            priority_ref=self.priority,
            task_type_ref=self.showing_task_type,
        )

        self.api.post(
            f'/api/tasks/{task.pk}/record_step/',
            {'step': 'contact', 'outcome': 'called'},
            format='json',
        )
        self.api.post(
            f'/api/tasks/{task.pk}/record_step/',
            {'step': 'request', 'outcome': 'exists'},
            format='json',
        )
        viewing = models.PropertyViewing.objects.create(
            property=self.property,
            client_profile=self.client_profile,
            employee_profile=self.employee_profile,
            viewing_date=timezone.now() + timedelta(days=1),
            status=self.viewing_status_scheduled,
        )
        self.api.post(
            f'/api/tasks/{task.pk}/record_step/',
            {'step': 'match', 'outcome': 'showing_scheduled'},
            format='json',
        )

        response = self.api.post(
            f'/api/tasks/{task.pk}/record_step/',
            {'step': 'payment', 'outcome': 'link_sent'},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('ссылку на оплату', str(response.data['detail']).lower())
        self.assertIsNone(getattr(viewing, 'payment', None))

    @override_settings(
        SBER_USERNAME='test-sber-username',
        SBER_PASSWORD='test-sber-password',
    )
    @patch('key.viewing_payments.SberAcquiringClient.register_order')
    def test_initiate_viewing_payment_action_creates_payment_link(self, register_order_mock):
        register_order_mock.return_value = {
            'error_code': '0',
            'orderId': 'task-sber-order-1',
            'formUrl': 'https://sber.test/pay/task-1',
        }
        request_obj = models.Request.objects.create(
            client=self.client_user,
            agent=self.employee,
            operation_type=self.operation_type,
            status=self.request_status,
        )
        task = models.Task.objects.create(
            title='Create viewing payment',
            status=self.status_new,
            assignee=self.employee,
            created_by=self.employee,
            client_profile=self.client_profile,
            property=self.property,
            request=request_obj,
            priority_ref=self.priority,
            task_type_ref=self.showing_task_type,
        )
        models.PropertyViewing.objects.create(
            property=self.property,
            client_profile=self.client_profile,
            employee_profile=self.employee_profile,
            viewing_date=timezone.now() + timedelta(days=2),
            status=self.viewing_status_scheduled,
        )

        response = self.api.post(
            f'/api/tasks/{task.pk}/initiate_viewing_payment/',
            {},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['payment']['status'], models.ViewingPayment.STATUS_PENDING)
        self.assertEqual(response.data['payment']['payment_url'], 'https://sber.test/pay/task-1')
        self.assertEqual(response.data['task']['showing_payment_url'], 'https://sber.test/pay/task-1')

    def test_client_can_list_only_own_tasks(self):
        other_client = models.User.objects.create_user(
            username='task-workflow-client-other',
            email='task-workflow-client-other@example.com',
            password='Secret123!',
            user_type='client',
        )
        other_profile = models.ClientProfile.objects.create(
            user=other_client,
            first_name='Other',
            last_name='Client',
        )
        own_task = models.Task.objects.create(
            title='Own client task',
            status=self.status_new,
            assignee=self.employee,
            created_by=self.employee,
            client_profile=self.client_profile,
            task_type_ref=self.showing_task_type,
            priority_ref=self.priority,
        )
        models.Task.objects.create(
            title='Foreign client task',
            status=self.status_new,
            assignee=self.employee,
            created_by=self.employee,
            client_profile=other_profile,
            task_type_ref=self.showing_task_type,
            priority_ref=self.priority,
        )
        self.api.force_authenticate(user=self.client_user)

        response = self.api.get('/api/tasks/')

        self.assertEqual(response.status_code, 200)
        items = response.data['results'] if 'results' in response.data else response.data
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['id'], own_task.pk)

    def test_client_cannot_schedule_viewing_or_initiate_payment(self):
        request_obj = models.Request.objects.create(
            client=self.client_user,
            agent=self.employee,
            operation_type=self.operation_type,
            status=self.request_status,
        )
        task = models.Task.objects.create(
            title='Forbidden showing actions',
            status=self.status_new,
            assignee=self.employee,
            created_by=self.employee,
            client_profile=self.client_profile,
            property=self.property,
            request=request_obj,
            priority_ref=self.priority,
            task_type_ref=self.showing_task_type,
        )
        self.api.force_authenticate(user=self.client_user)

        schedule_response = self.api.post(
            f'/api/tasks/{task.pk}/schedule_viewing/',
            {'viewing_date': '2030-01-01T10:30:00+08:00'},
            format='json',
        )
        payment_response = self.api.post(
            f'/api/tasks/{task.pk}/initiate_viewing_payment/',
            {},
            format='json',
        )

        self.assertEqual(schedule_response.status_code, 403)
        self.assertEqual(payment_response.status_code, 403)


class TaskWorkloadEndpointTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.status_new = models.TaskStatus.objects.create(
            code='new',
            name='New',
            order=10,
        )
        self.status_waiting = models.TaskStatus.objects.create(
            code='waiting',
            name='Waiting',
            order=20,
        )
        self.status_in_progress = models.TaskStatus.objects.create(
            code='in_progress',
            name='In progress',
            order=30,
        )
        self.status_done = models.TaskStatus.objects.create(
            code='done',
            name='Done',
            order=40,
        )
        self.employee = models.User.objects.create_user(
            username='task-workload-user',
            email='task-workload-user@example.com',
            password='Secret123!',
            user_type='employee',
        )
        self.api.force_authenticate(user=self.employee)

    def test_current_and_workload_ignore_completed_task_with_active_status(self):
        models.Task.objects.create(
            title='Inconsistent task',
            status=self.status_in_progress,
            assignee=self.employee,
            created_by=self.employee,
            completed_at=timezone.now(),
        )
        models.Task.objects.create(
            title='Waiting task',
            status=self.status_waiting,
            assignee=self.employee,
            created_by=self.employee,
        )

        current_response = self.api.get('/api/tasks/current/')
        workload_response = self.api.get('/api/users/me/workload/')

        self.assertEqual(current_response.status_code, 200)
        self.assertIsNone(current_response.data)
        self.assertEqual(workload_response.status_code, 200)
        self.assertEqual(workload_response.data['active_tasks'], 1)
        self.assertEqual(workload_response.data['in_progress_tasks'], 0)
        self.assertTrue(workload_response.data['can_start_task'])

    def test_pause_releases_in_progress_slot_and_clears_current_task(self):
        task = models.Task.objects.create(
            title='Call client',
            status=self.status_in_progress,
            assignee=self.employee,
            created_by=self.employee,
        )

        response = self.api.post(f'/api/tasks/{task.pk}/pause/')

        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.status_id, self.status_waiting.pk)
        self.assertIsNone(task.completed_at)

        current_response = self.api.get('/api/tasks/current/')
        workload_response = self.api.get('/api/users/me/workload/')

        self.assertEqual(current_response.status_code, 200)
        self.assertIsNone(current_response.data)
        self.assertEqual(workload_response.data['active_tasks'], 1)
        self.assertEqual(workload_response.data['in_progress_tasks'], 0)
        self.assertTrue(workload_response.data['can_start_task'])

    def test_completing_current_task_releases_limit_for_next_task(self):
        current_task = models.Task.objects.create(
            title='Current task',
            status=self.status_in_progress,
            assignee=self.employee,
            created_by=self.employee,
        )
        waiting_task = models.Task.objects.create(
            title='Waiting task',
            status=self.status_waiting,
            assignee=self.employee,
            created_by=self.employee,
        )

        blocked_response = self.api.post(f'/api/tasks/{waiting_task.pk}/start/')
        self.assertEqual(blocked_response.status_code, 409)

        complete_response = self.api.post(
            f'/api/tasks/{current_task.pk}/complete/',
            {'result': {'summary': 'Done'}},
            format='json',
        )
        self.assertEqual(complete_response.status_code, 200)

        current_response = self.api.get('/api/tasks/current/')
        workload_response = self.api.get('/api/users/me/workload/')
        self.assertEqual(current_response.status_code, 200)
        self.assertIsNone(current_response.data)
        self.assertEqual(workload_response.data['active_tasks'], 1)
        self.assertEqual(workload_response.data['in_progress_tasks'], 0)
        self.assertTrue(workload_response.data['can_start_task'])

        started_response = self.api.post(f'/api/tasks/{waiting_task.pk}/start/')
        self.assertEqual(started_response.status_code, 200)
        waiting_task.refresh_from_db()
        self.assertEqual(waiting_task.status_id, self.status_in_progress.pk)
        self.assertIsNone(waiting_task.completed_at)


class DealPermissionTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.operation_type = models.OperationType.objects.create(
            code='sale',
            name='Sale',
        )
        self.property_status = models.PropertyStatus.objects.create(
            code='active',
            name='Active',
        )
        self.deal_status_new = models.DealStatus.objects.create(
            code='new',
            name='New',
            order=10,
        )
        self.deal_status_completed = models.DealStatus.objects.create(
            code='completed',
            name='Completed',
            order=20,
        )
        self.employee = models.User.objects.create_user(
            username='deal-employee',
            email='deal-employee@example.com',
            password='Secret123!',
            user_type='employee',
        )
        self.other_employee = models.User.objects.create_user(
            username='deal-other-employee',
            email='deal-other-employee@example.com',
            password='Secret123!',
            user_type='employee',
        )
        self.client_user = models.User.objects.create_user(
            username='deal-owner',
            email='deal-owner@example.com',
            password='Secret123!',
            user_type='client',
        )
        city = models.City.objects.create(name='Irkutsk', region='Region')
        street = models.Street.objects.create(city=city, name='Lenina')
        house = models.House.objects.create(street=street, house_number='11')
        address = models.Address.objects.create(
            house=house,
            apartment_number='2',
        )
        self.property = models.Property.objects.create(
            title='Deal property',
            operation_type=self.operation_type,
            status=self.property_status,
            address=address,
            price=8_200_000,
        )
        self.deal = models.Deal.objects.create(
            deal_number='D-2026-0001',
            property=self.property,
            agent=self.employee,
            client=self.client_user,
            operation_type=self.operation_type,
            status=self.deal_status_new,
            price_final=self.property.price,
            deal_date=timezone.now().date(),
            notes='Initial note',
        )

    def test_client_cannot_change_own_deal_status(self):
        self.api.force_authenticate(user=self.client_user)

        response = self.api.post(
            f'/api/deals/{self.deal.pk}/change_status/',
            {'status_id': self.deal_status_completed.pk},
            format='json',
        )

        self.assertEqual(response.status_code, 403)
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.status_id, self.deal_status_new.pk)

    def test_client_cannot_patch_own_deal(self):
        self.api.force_authenticate(user=self.client_user)

        response = self.api.patch(
            f'/api/deals/{self.deal.pk}/',
            {'notes': 'Changed by client'},
            format='json',
        )

        self.assertEqual(response.status_code, 403)
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.notes, 'Initial note')

    def test_client_can_view_own_deal_list_and_detail(self):
        self.api.force_authenticate(user=self.client_user)

        list_response = self.api.get('/api/deals/')
        detail_response = self.api.get(f'/api/deals/{self.deal.pk}/')

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data['count'], 1)
        self.assertEqual(list_response.data['results'][0]['id'], self.deal.pk)
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.data['id'], self.deal.pk)

    def test_employee_cannot_see_foreign_deal(self):
        self.api.force_authenticate(user=self.other_employee)

        list_response = self.api.get('/api/deals/')
        detail_response = self.api.get(f'/api/deals/{self.deal.pk}/')

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 404)
        self.assertEqual(list_response.data['results'], [])

    def test_deal_list_supports_status_filter(self):
        second_deal = models.Deal.objects.create(
            deal_number='D-2026-0002',
            property=self.property,
            agent=self.employee,
            client=self.client_user,
            operation_type=self.operation_type,
            status=self.deal_status_completed,
            price_final=self.property.price,
            deal_date=timezone.now().date(),
        )
        self.api.force_authenticate(user=self.employee)

        response = self.api.get(
            f'/api/deals/?status={self.deal_status_completed.pk}',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.data['results']
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]['id'], second_deal.pk)
        self.assertEqual(payload[0]['status_code'], 'completed')

    def test_deal_list_supports_operation_type_and_date_range(self):
        rent_operation = models.OperationType.objects.create(
            code='rent',
            name='Rent',
        )
        second_property = models.Property.objects.create(
            title='Rent deal property',
            operation_type=rent_operation,
            status=self.property_status,
            address=self.property.address,
            price=6_100_000,
        )
        old_sale_deal = models.Deal.objects.create(
            deal_number='D-2026-0003',
            property=self.property,
            agent=self.employee,
            client=self.client_user,
            operation_type=self.operation_type,
            status=self.deal_status_new,
            price_final=self.property.price,
            deal_date=timezone.localdate() - timedelta(days=2),
        )
        models.Deal.objects.create(
            deal_number='D-2026-0004',
            property=second_property,
            agent=self.employee,
            client=self.client_user,
            operation_type=rent_operation,
            status=self.deal_status_new,
            price_final=second_property.price,
            deal_date=timezone.localdate(),
        )
        self.api.force_authenticate(user=self.employee)

        response = self.api.get('/api/deals/', {
            'operation_type': self.operation_type.pk,
            'date_from': timezone.localdate().isoformat(),
            'date_to': timezone.localdate().isoformat(),
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {item['id'] for item in response.data['results']},
            {self.deal.pk},
        )
        self.assertNotIn(old_sale_deal.pk, {item['id'] for item in response.data['results']})

    def test_client_cannot_export_deals(self):
        self.api.force_authenticate(user=self.client_user)

        response = self.api.get(
            '/api/deals/export/',
            {'export_format': 'csv'},
        )

        self.assertEqual(response.status_code, 403)

    def test_employee_cannot_export_deals(self):
        self.api.force_authenticate(user=self.employee)

        response = self.api.get(
            '/api/deals/export/',
            {'export_format': 'csv'},
        )

        self.assertEqual(response.status_code, 403)


class TaskFilteringTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.operation_sale = models.OperationType.objects.create(
            code='sale',
            name='Sale',
        )
        self.operation_rent = models.OperationType.objects.create(
            code='rent',
            name='Rent',
        )
        self.request_status_open = models.RequestStatus.objects.create(
            code='open',
            name='Open',
        )
        self.task_status_new = models.TaskStatus.objects.create(
            code='new',
            name='New',
            order=10,
        )
        self.deal_status_new = models.DealStatus.objects.create(
            code='new',
            name='New',
            order=10,
        )
        self.property_status = models.PropertyStatus.objects.create(
            code='active',
            name='Active',
        )
        self.employee = models.User.objects.create_user(
            username='task-filter-employee',
            email='task-filter-employee@example.com',
            password='Secret123!',
            user_type='employee',
        )
        self.client_user = models.User.objects.create_user(
            username='task-filter-client',
            email='task-filter-client@example.com',
            password='Secret123!',
            user_type='client',
        )
        city = models.City.objects.create(name='Irkutsk', region='Region')
        street = models.Street.objects.create(city=city, name='Lenina')
        house = models.House.objects.create(street=street, house_number='21')
        address = models.Address.objects.create(
            house=house,
            apartment_number='8',
        )
        self.sale_property = models.Property.objects.create(
            title='Sale property',
            operation_type=self.operation_sale,
            status=self.property_status,
            address=address,
            price=7_400_000,
        )
        self.rent_property = models.Property.objects.create(
            title='Rent property',
            operation_type=self.operation_rent,
            status=self.property_status,
            address=address,
            price=3_100_000,
        )
        self.sale_request = models.Request.objects.create(
            client=self.client_user,
            agent=self.employee,
            operation_type=self.operation_sale,
            status=self.request_status_open,
        )
        self.sale_deal = models.Deal.objects.create(
            deal_number='TASK-2026-0001',
            property=self.sale_property,
            agent=self.employee,
            client=self.client_user,
            operation_type=self.operation_sale,
            status=self.deal_status_new,
            price_final=self.sale_property.price,
            deal_date=timezone.localdate(),
        )
        self.request_task = models.Task.objects.create(
            title='Sale request task',
            status=self.task_status_new,
            assignee=self.employee,
            created_by=self.employee,
            request=self.sale_request,
        )
        self.property_task = models.Task.objects.create(
            title='Rent property task',
            status=self.task_status_new,
            assignee=self.employee,
            created_by=self.employee,
            property=self.rent_property,
        )
        self.old_deal_task = models.Task.objects.create(
            title='Old sale deal task',
            status=self.task_status_new,
            assignee=self.employee,
            created_by=self.employee,
            deal=self.sale_deal,
        )

    def test_task_list_supports_operation_type_and_created_at_range(self):
        models.Task.objects.filter(pk=self.request_task.pk).update(
            created_at=timezone.now(),
        )
        models.Task.objects.filter(pk=self.property_task.pk).update(
            created_at=timezone.now(),
        )
        models.Task.objects.filter(pk=self.old_deal_task.pk).update(
            created_at=timezone.now() - timedelta(days=2),
        )
        self.api.force_authenticate(user=self.employee)

        response = self.api.get('/api/tasks/', {
            'operation_type': self.operation_sale.pk,
            'date_from': timezone.localdate().isoformat(),
            'date_to': timezone.localdate().isoformat(),
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {item['id'] for item in response.data['results']},
            {self.request_task.pk},
        )

    def test_client_cannot_export_tasks(self):
        self.api.force_authenticate(user=self.client_user)

        response = self.api.get(
            '/api/tasks/export/',
            {'export_format': 'csv'},
        )

        self.assertEqual(response.status_code, 403)


class PropertyStatusTransitionTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.employee = models.User.objects.create_user(
            username='property-status-user',
            email='property-status-user@example.com',
            password='Secret123!',
            user_type='employee',
        )
        self.operation_sale = models.OperationType.objects.create(
            code='sale',
            name='Sale',
        )
        self.operation_rent = models.OperationType.objects.create(
            code='rent',
            name='Rent',
        )
        self.status_active = models.PropertyStatus.objects.create(
            code='active',
            name='Active',
        )
        self.status_reserved = models.PropertyStatus.objects.create(
            code='reserved',
            name='Reserved',
        )
        self.status_sold = models.PropertyStatus.objects.create(
            code='sold',
            name='Sold',
        )
        self.status_rented = models.PropertyStatus.objects.create(
            code='rented',
            name='Rented',
        )
        self.status_archived = models.PropertyStatus.objects.create(
            code='archived',
            name='Archived',
        )
        city = models.City.objects.create(name='Irkutsk', region='Region')
        street = models.Street.objects.create(city=city, name='Lenina')
        house = models.House.objects.create(street=street, house_number='15')
        address = models.Address.objects.create(house=house, apartment_number='10')
        self.sale_property = models.Property.objects.create(
            title='Sale property',
            operation_type=self.operation_sale,
            status=self.status_active,
            address=address,
            price=6_500_000,
        )
        self.api.force_authenticate(user=self.employee)

    def test_sale_property_cannot_switch_directly_to_rented(self):
        response = self.api.post(
            f'/api/properties/{self.sale_property.pk}/change_status/',
            {'status_id': self.status_rented.pk},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.sale_property.refresh_from_db()
        self.assertEqual(self.sale_property.status_id, self.status_active.pk)
        self.assertFalse(
            models.PropertyStatusHistory.objects.filter(
                property=self.sale_property,
            ).exists(),
        )

    def test_reserved_property_can_be_marked_as_sold(self):
        self.sale_property.status = self.status_reserved
        self.sale_property.save(update_fields=['status'])

        response = self.api.post(
            f'/api/properties/{self.sale_property.pk}/change_status/',
            {'status_id': self.status_sold.pk},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.sale_property.refresh_from_db()
        self.assertEqual(self.sale_property.status_id, self.status_sold.pk)
        self.assertEqual(
            models.PropertyStatusHistory.objects.filter(
                property=self.sale_property,
            ).count(),
            1,
        )

    def test_property_detail_exposes_only_allowed_status_ids(self):
        response = self.api.get(f'/api/properties/{self.sale_property.pk}/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.data['allowed_status_ids']),
            {
                self.status_active.pk,
                self.status_reserved.pk,
                self.status_archived.pk,
                self.status_sold.pk,
            },
        )


class DealStatusTransitionTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.employee = models.User.objects.create_user(
            username='deal-status-user',
            email='deal-status-user@example.com',
            password='Secret123!',
            user_type='employee',
        )
        self.client_user = models.User.objects.create_user(
            username='deal-status-client',
            email='deal-status-client@example.com',
            password='Secret123!',
            user_type='client',
        )
        self.operation_type = models.OperationType.objects.create(
            code='sale',
            name='Sale',
        )
        self.property_status = models.PropertyStatus.objects.create(
            code='active',
            name='Active',
        )
        self.status_new = models.DealStatus.objects.create(
            code='new',
            name='New',
            order=10,
        )
        self.status_negotiation = models.DealStatus.objects.create(
            code='negotiation',
            name='Negotiation',
            order=20,
        )
        self.status_documents = models.DealStatus.objects.create(
            code='documents',
            name='Documents',
            order=30,
        )
        self.status_completed = models.DealStatus.objects.create(
            code='completed',
            name='Completed',
            order=40,
        )
        self.status_cancelled = models.DealStatus.objects.create(
            code='cancelled',
            name='Cancelled',
            order=90,
        )
        city = models.City.objects.create(name='Irkutsk', region='Region')
        street = models.Street.objects.create(city=city, name='Lenina')
        house = models.House.objects.create(street=street, house_number='16')
        address = models.Address.objects.create(house=house, apartment_number='4')
        self.property = models.Property.objects.create(
            title='Deal transition property',
            operation_type=self.operation_type,
            status=self.property_status,
            address=address,
            price=8_800_000,
        )
        self.deal = models.Deal.objects.create(
            deal_number='D-2026-0100',
            property=self.property,
            agent=self.employee,
            client=self.client_user,
            operation_type=self.operation_type,
            status=self.status_new,
            price_final=self.property.price,
            deal_date=timezone.now().date(),
        )
        self.api.force_authenticate(user=self.employee)

    def test_deal_cannot_skip_from_new_to_completed(self):
        response = self.api.post(
            f'/api/deals/{self.deal.pk}/change_status/',
            {'status_id': self.status_completed.pk},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.status_id, self.status_new.pk)

    def test_deal_can_move_to_next_pipeline_stage(self):
        response = self.api.post(
            f'/api/deals/{self.deal.pk}/change_status/',
            {'status_id': self.status_negotiation.pk},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.status_id, self.status_negotiation.pk)

    def test_deal_list_exposes_only_allowed_status_ids(self):
        response = self.api.get('/api/deals/')

        self.assertEqual(response.status_code, 200)
        payload = response.data['results'][0]
        self.assertEqual(
            set(payload['allowed_status_ids']),
            {
                self.status_new.pk,
                self.status_negotiation.pk,
                self.status_cancelled.pk,
            },
        )


class PropertyPhotoCoverTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.manager_role = models.UserRole.objects.create(
            code='manager',
            name='Manager',
        )
        self.employee = models.User.objects.create_user(
            username='photo-user',
            email='photo-user@example.com',
            password='Secret123!',
            user_type='employee',
            role=self.manager_role,
        )
        self.operation_type = models.OperationType.objects.create(
            code='sale',
            name='Sale',
        )
        self.property_status = models.PropertyStatus.objects.create(
            code='active',
            name='Active',
        )
        city = models.City.objects.create(name='Irkutsk', region='Region')
        street = models.Street.objects.create(city=city, name='Lenina')
        house = models.House.objects.create(street=street, house_number='10')
        address = models.Address.objects.create(
            house=house,
            apartment_number='1',
        )
        self.property = models.Property.objects.create(
            title='Property',
            operation_type=self.operation_type,
            status=self.property_status,
            address=address,
            price=5_000_000,
        )
        self.api.force_authenticate(user=self.employee)

    def test_first_created_photo_becomes_cover(self):
        response = self.api.post(
            '/api/property-photos/',
            {
                'property': self.property.pk,
                'url': 'https://example.com/1.jpg',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        photo = models.PropertyPhoto.objects.get(pk=response.data['id'])
        self.assertTrue(photo.is_cover)
        self.assertFalse(photo.is_hidden)

    def test_creating_new_cover_photo_resets_previous_cover(self):
        previous = models.PropertyPhoto.objects.create(
            property=self.property,
            url='https://example.com/old.jpg',
            is_cover=True,
            order=0,
        )

        response = self.api.post(
            '/api/property-photos/',
            {
                'property': self.property.pk,
                'url': 'https://example.com/new.jpg',
                'is_cover': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        previous.refresh_from_db()
        created = models.PropertyPhoto.objects.get(pk=response.data['id'])
        self.assertFalse(previous.is_cover)
        self.assertTrue(created.is_cover)
        self.assertFalse(created.is_hidden)

    def test_deleting_cover_photo_promotes_next_photo(self):
        cover = models.PropertyPhoto.objects.create(
            property=self.property,
            url='https://example.com/cover.jpg',
            is_cover=True,
            order=0,
        )
        fallback = models.PropertyPhoto.objects.create(
            property=self.property,
            url='https://example.com/fallback.jpg',
            is_cover=False,
            is_hidden=True,
            order=1,
        )

        response = self.api.delete(f'/api/property-photos/{cover.pk}/')

        self.assertEqual(response.status_code, 204)
        fallback.refresh_from_db()
        self.assertTrue(fallback.is_cover)
        self.assertFalse(fallback.is_hidden)


class BulkOperationsApiTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.employee = models.User.objects.create_user(
            username='bulk-employee',
            email='bulk-employee@example.com',
            password='Secret123!',
            user_type='employee',
        )
        self.other_employee = models.User.objects.create_user(
            username='bulk-other',
            email='bulk-other@example.com',
            password='Secret123!',
            user_type='employee',
        )
        self.client_user = models.User.objects.create_user(
            username='bulk-client',
            email='bulk-client@example.com',
            password='Secret123!',
            user_type='client',
        )
        self.operation_type = models.OperationType.objects.create(
            code='sale',
            name='Sale',
        )
        self.property_status_active = models.PropertyStatus.objects.create(
            code='active',
            name='Active',
        )
        self.property_status_archived = models.PropertyStatus.objects.create(
            code='archived',
            name='Archived',
        )
        self.request_status_open = models.RequestStatus.objects.create(
            code='open',
            name='Open',
        )
        self.request_status_cancelled = models.RequestStatus.objects.create(
            code='cancelled',
            name='Cancelled',
        )
        self.task_status_new = models.TaskStatus.objects.create(
            code='new',
            name='New',
            order=10,
        )
        self.task_status_waiting = models.TaskStatus.objects.create(
            code='waiting',
            name='Waiting',
            order=20,
        )
        self.task_status_done = models.TaskStatus.objects.create(
            code='done',
            name='Done',
            order=30,
        )
        self.api.force_authenticate(user=self.employee)

    def _address(self, suffix='1'):
        city = models.City.objects.create(
            name=f'City {suffix}',
            region='Region',
        )
        street = models.Street.objects.create(
            city=city,
            name=f'Street {suffix}',
        )
        house = models.House.objects.create(
            street=street,
            house_number=str(suffix),
        )
        return models.Address.objects.create(
            house=house,
            apartment_number=str(suffix),
        )

    def test_bulk_archive_properties(self):
        first = models.Property.objects.create(
            title='Bulk property 1',
            operation_type=self.operation_type,
            status=self.property_status_active,
            address=self._address('11'),
            price=4_100_000,
        )
        second = models.Property.objects.create(
            title='Bulk property 2',
            operation_type=self.operation_type,
            status=self.property_status_active,
            address=self._address('12'),
            price=5_200_000,
        )

        response = self.api.post(
            '/api/properties/bulk-archive/',
            {'ids': [first.pk, second.pk]},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['archived'], 2)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status_id, self.property_status_archived.pk)
        self.assertEqual(second.status_id, self.property_status_archived.pk)
        self.assertEqual(
            models.AuditLog.objects.filter(action_code='bulk_archived').count(),
            2,
        )

    def test_bulk_close_requests_respects_scope(self):
        own_request = models.Request.objects.create(
            client=self.client_user,
            agent=self.employee,
            operation_type=self.operation_type,
            status=self.request_status_open,
            description='Own request',
        )
        foreign_request = models.Request.objects.create(
            client=self.client_user,
            agent=self.other_employee,
            operation_type=self.operation_type,
            status=self.request_status_open,
            description='Foreign request',
        )

        response = self.api.post(
            '/api/requests/bulk-close/',
            {'ids': [own_request.pk, foreign_request.pk], 'outcome': 'cancelled'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['closed'], 1)
        self.assertIn(foreign_request.pk, response.data['not_found_ids'])
        own_request.refresh_from_db()
        foreign_request.refresh_from_db()
        self.assertEqual(own_request.status_id, self.request_status_cancelled.pk)
        self.assertEqual(foreign_request.status_id, self.request_status_open.pk)

    def test_bulk_complete_tasks(self):
        first = models.Task.objects.create(
            title='Bulk task 1',
            task_type='call',
            status=self.task_status_new,
            assignee=self.employee,
            created_by=self.employee,
        )
        second = models.Task.objects.create(
            title='Bulk task 2',
            task_type='documents',
            status=self.task_status_waiting,
            assignee=self.employee,
            created_by=self.employee,
        )

        response = self.api.post(
            '/api/tasks/bulk-action/',
            {
                'ids': [first.pk, second.pk],
                'action': 'complete',
                'result': 'Closed in bulk',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['processed'], 2)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status_id, self.task_status_done.pk)
        self.assertEqual(second.status_id, self.task_status_done.pk)
        self.assertTrue(first.completed_at)
        self.assertTrue(second.completed_at)


class DjangoAdminAccessTests(TestCase):
    def setUp(self):
        temp_root = Path(settings.BASE_DIR) / '.tmp-admin-backups'
        temp_root.mkdir(parents=True, exist_ok=True)
        self.temp_path = temp_root / f'backups-{uuid4().hex}'
        self.temp_path.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(self.temp_path, ignore_errors=True))
        self.override = override_settings(DATABASE_BACKUP_ROOT=self.temp_path / 'backups')
        self.override.enable()
        self.addCleanup(self.override.disable)

        self.admin_role = models.UserRole.objects.create(
            code='admin',
            name='Администратор',
        )
        self.manager_role = models.UserRole.objects.create(
            code='manager',
            name='Менеджер',
        )

        self.admin_user = models.User.objects.create_user(
            username='django-admin-role',
            email='django-admin@example.com',
            password='Secret123!',
            user_type='employee',
            role=self.admin_role,
            is_staff=True,
        )
        self.manager_user = models.User.objects.create_user(
            username='django-manager-role',
            email='django-manager@example.com',
            password='Secret123!',
            user_type='employee',
            role=self.manager_role,
            is_staff=True,
        )

    def test_admin_role_user_can_open_django_admin_index_and_models(self):
        self.client.force_login(self.admin_user)

        index_response = self.client.get('/admin/')
        users_response = self.client.get('/admin/key/user/')

        self.assertEqual(index_response.status_code, 200)
        self.assertEqual(users_response.status_code, 200)

    def test_admin_index_uses_russian_navigation_and_backup_entry(self):
        self.client.force_login(self.admin_user)

        response = self.client.get('/admin/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Системная панель')
        self.assertContains(response, 'Резервное копирование БД')
        self.assertNotContains(response, 'Дашборд')
        self.assertNotContains(response, 'Django Admin')

    def test_admin_role_user_can_open_database_backup_page(self):
        self.client.force_login(self.admin_user)

        response = self.client.get('/admin/backups/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Резервное копирование БД')
        self.assertContains(response, 'Полный резервный снимок')
        self.assertContains(response, 'История резервных копий')

    @patch('key.admin.db_backups.build_full_database_backup')
    @patch('key.admin.db_backups.create_database_backup_record')
    def test_admin_backup_download_returns_generated_file(self, create_record_mock, build_backup_mock):
        self.client.force_login(self.admin_user)
        build_backup_mock.return_value = (b'backup-bytes', 're-crm.dump')

        response = self.client.post('/admin/backups/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/octet-stream')
        self.assertEqual(
            response['Content-Disposition'],
            'attachment; filename="re-crm.dump"',
        )
        self.assertEqual(response.content, b'backup-bytes')
        create_record_mock.assert_called_once()

    @patch('key.admin.db_backups.build_full_database_backup')
    def test_admin_backup_history_file_is_downloadable(self, build_backup_mock):
        self.client.force_login(self.admin_user)
        build_backup_mock.return_value = (b'backup-bytes', 're-crm.dump')

        response = self.client.post('/admin/backups/')
        self.assertEqual(response.status_code, 200)

        backup = models.DatabaseBackup.objects.latest('id')
        history_response = self.client.get(f'/admin/backups/{backup.pk}/download/')

        self.assertEqual(history_response.status_code, 200)
        self.assertEqual(history_response['Content-Type'], 'application/octet-stream')
        self.assertEqual(b''.join(history_response.streaming_content), b'backup-bytes')
        self.assertEqual(
            history_response['Content-Disposition'],
            f'attachment; filename="{backup.filename}"',
        )

    def test_manager_role_user_is_blocked_from_django_admin(self):
        self.client.force_login(self.manager_user)

        index_response = self.client.get('/admin/')
        users_response = self.client.get('/admin/key/user/')
        backups_response = self.client.get('/admin/backups/')

        self.assertEqual(index_response.status_code, 302)
        self.assertEqual(users_response.status_code, 302)
        self.assertEqual(backups_response.status_code, 302)


class SeedDataCommandTests(TestCase):
    def setUp(self):
        temp_root = Path(getattr(settings, 'DATABASE_BACKUP_ROOT', settings.BASE_DIR)) / '.tmp-tests'
        temp_root.mkdir(parents=True, exist_ok=True)
        self.temp_path = temp_root / f'seed-{uuid4().hex}'
        self.temp_path.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(self.temp_path, ignore_errors=True))
        self.override = override_settings(MEDIA_ROOT=self.temp_path / 'media')
        self.override.enable()
        self.addCleanup(self.override.disable)

    def test_seed_data_default_creates_realistic_crm_dataset(self):
        call_command('seed_data', stdout=io.StringIO())

        self.assertTrue(models.User.objects.filter(username='seed_admin_1').exists())
        self.assertFalse(models.User.objects.filter(username__startswith='demo').exists())
        self.assertEqual(models.Property.objects.count(), 30)
        self.assertEqual(models.Property.objects.filter(description__contains='__seed_batch__').count(), 0)
        self.assertEqual(models.Request.objects.count(), 15)
        self.assertEqual(models.Task.objects.count(), 20)
        self.assertEqual(models.Deal.objects.count(), 5)
        self.assertGreaterEqual(models.PropertyPhoto.objects.count(), 60)
        self.assertEqual(models.OperationType.objects.count(), 2)

        call_command('seed_data', stdout=io.StringIO())
        self.assertEqual(models.User.objects.filter(username='seed_admin_1').count(), 1)
        self.assertEqual(models.Property.objects.count(), 30)
        self.assertEqual(models.Request.objects.count(), 15)
        self.assertEqual(models.Task.objects.count(), 20)
        self.assertEqual(models.Deal.objects.count(), 5)


@override_settings(
    SBER_USERNAME='test-sber-username',
    SBER_PASSWORD='test-sber-password',
)
class ViewingPaymentsTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.user_type_employee, _ = models.UserType.objects.get_or_create(code='employee', defaults={'name': 'Employee'})
        self.user_type_client, _ = models.UserType.objects.get_or_create(code='client', defaults={'name': 'Client'})
        self.client_kind_individual, _ = models.ClientKind.objects.get_or_create(
            code='individual',
            defaults={'name': 'Individual'},
        )
        self.operation_type, _ = models.OperationType.objects.get_or_create(code='sale', defaults={'name': 'Sale'})
        self.property_status, _ = models.PropertyStatus.objects.get_or_create(code='active', defaults={'name': 'Active'})
        self.viewing_status_scheduled, _ = models.ViewingStatus.objects.get_or_create(code='scheduled', defaults={'name': 'Scheduled'})
        self.viewing_status_confirmed, _ = models.ViewingStatus.objects.get_or_create(code='confirmed', defaults={'name': 'Confirmed'})
        self.task_status_new, _ = models.TaskStatus.objects.get_or_create(code='new', defaults={'name': 'New', 'order': 10})
        self.task_status_done, _ = models.TaskStatus.objects.get_or_create(code='done', defaults={'name': 'Done', 'order': 20})
        self.property_type, _ = models.PropertyType.objects.get_or_create(code='apartment', defaults={'name': 'Apartment'})
        self.priority, _ = models.TaskPriority.objects.get_or_create(code='normal', defaults={'name': 'Normal'})
        self.task_type_showing, _ = models.TaskType.objects.get_or_create(code='showing', defaults={'name': 'Showing'})

        self.agent = models.User.objects.create_user(
            username='viewing-agent',
            email='viewing-agent@example.com',
            password='Secret123!',
            user_type_ref=self.user_type_employee,
            is_staff=True,
        )
        self.client_user = models.User.objects.create_user(
            username='viewing-client',
            email='viewing-client@example.com',
            password='Secret123!',
            user_type_ref=self.user_type_client,
        )
        self.employee_profile = models.EmployeeProfile.objects.create(
            user=self.agent,
            first_name='Agent',
            last_name='One',
        )
        self.client_profile = models.ClientProfile.objects.create(
            user=self.client_user,
            first_name='Client',
            last_name='One',
            client_kind_ref=self.client_kind_individual,
        )

        city = models.City.objects.create(name='Irkutsk', region='Region')
        street = models.Street.objects.create(city=city, name='Lenina')
        house = models.House.objects.create(street=street, house_number='10')
        self.property = models.Property.objects.create(
            title='Viewing payment property',
            operation_type=self.operation_type,
            status=self.property_status,
            property_type_ref=self.property_type,
            house=house,
            price=5_000_000,
            area_total=Decimal('45.00'),
        )
        self.viewing = models.PropertyViewing.objects.create(
            property=self.property,
            client_profile=self.client_profile,
            employee_profile=self.employee_profile,
            viewing_date=timezone.now() + timedelta(days=1),
            status=self.viewing_status_scheduled,
        )

    def test_property_viewing_cannot_be_confirmed_without_paid_payment(self):
        models.ViewingPayment.objects.create(
            viewing=self.viewing,
            client=self.client_user,
            property=self.property,
            amount=Decimal('500.00'),
            status=models.ViewingPayment.STATUS_PENDING,
        )
        self.viewing.status = self.viewing_status_confirmed
        with self.assertRaises(ValidationError):
            self.viewing.full_clean()

    def test_complete_showing_task_requires_paid_payment(self):
        task = models.Task.objects.create(
            title='Showing task',
            status=self.task_status_new,
            assignee=self.agent,
            created_by=self.agent,
            client_profile=self.client_profile,
            property=self.property,
            priority_ref=self.priority,
            task_type_ref=self.task_type_showing,
        )
        with self.assertRaises(DRFValidationError):
            task_actions.complete_task(task, actor=self.agent, result={'summary': 'Done'})

    @patch('key.viewing_payments.SberAcquiringClient.register_order')
    def test_initiate_viewing_payment_creates_payment(self, register_order_mock):
        register_order_mock.return_value = {
            'error_code': '0',
            'orderId': 'sber-order-1',
            'formUrl': 'https://sber.test/pay/1',
        }
        self.api.force_authenticate(user=self.client_user)

        response = self.api.post(
            '/api/viewing-payments/initiate/',
            {'viewing_id': self.viewing.pk},
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        payment = models.ViewingPayment.objects.get(viewing=self.viewing)
        self.assertEqual(payment.status, models.ViewingPayment.STATUS_PENDING)
        self.assertEqual(payment.sber_order_id, 'sber-order-1')
        self.assertEqual(payment.payment_url, 'https://sber.test/pay/1')
        self.assertEqual(models.PaymentHistory.objects.filter(payment=payment).count(), 1)

    @patch('key.viewing_payments.SberAcquiringClient.get_order_status_extended')
    def test_success_endpoint_marks_payment_paid(self, status_mock):
        status_mock.return_value = {
            'error_code': '0',
            'order_status': 2,
            'transactionId': 'txn-1',
        }
        payment = models.ViewingPayment.objects.create(
            viewing=self.viewing,
            client=self.client_user,
            property=self.property,
            amount=Decimal('500.00'),
            status=models.ViewingPayment.STATUS_PENDING,
            sber_order_id='sber-order-2',
        )
        self.api.force_authenticate(user=self.client_user)

        response = self.api.get('/api/viewing-payments/success/', {'payment_id': payment.pk})

        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        self.viewing.refresh_from_db()
        self.assertEqual(payment.status, models.ViewingPayment.STATUS_PAID)
        self.assertEqual(self.viewing.status.code, 'confirmed')

    @patch('key.viewing_payments.SberAcquiringClient.get_order_status_extended')
    def test_success_endpoint_marks_payment_failed_on_error_status(self, status_mock):
        status_mock.return_value = {
            'error_code': '0',
            'order_status': 6,
        }
        payment = models.ViewingPayment.objects.create(
            viewing=self.viewing,
            client=self.client_user,
            property=self.property,
            amount=Decimal('500.00'),
            status=models.ViewingPayment.STATUS_PENDING,
            sber_order_id='sber-order-3',
        )
        self.api.force_authenticate(user=self.client_user)

        response = self.api.get('/api/viewing-payments/success/', {'payment_id': payment.pk})

        self.assertEqual(response.status_code, 400)
        payment.refresh_from_db()
        self.assertEqual(payment.status, models.ViewingPayment.STATUS_FAILED)

    def test_viewing_payments_report_returns_summary(self):
        manager_role = models.UserRole.objects.create(
            code='manager',
            name='Manager',
        )
        manager_user = models.User.objects.create_user(
            username='viewing-manager',
            email='viewing-manager@example.com',
            password='Secret123!',
            user_type_ref=self.user_type_employee,
            role=manager_role,
            is_staff=True,
        )
        second_viewing = models.PropertyViewing.objects.create(
            property=self.property,
            client_profile=self.client_profile,
            employee_profile=self.employee_profile,
            viewing_date=timezone.now() + timedelta(days=2),
            status=self.viewing_status_scheduled,
        )
        models.ViewingPayment.objects.create(
            viewing=self.viewing,
            client=self.client_user,
            property=self.property,
            amount=Decimal('500.00'),
            status=models.ViewingPayment.STATUS_PAID,
            paid_at=timezone.now(),
            sber_order_id='sber-order-report-1',
        )
        models.ViewingPayment.objects.create(
            viewing=second_viewing,
            client=self.client_user,
            property=self.property,
            amount=Decimal('500.00'),
            status=models.ViewingPayment.STATUS_FAILED,
            sber_order_id='sber-order-report-2',
        )
        self.api.force_authenticate(user=manager_user)

        response = self.api.get('/api/reports/viewing-payments/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['report_code'], 'viewing-payments')
        self.assertEqual(response.data['summary']['Успешных оплат'], 1)
        self.assertEqual(response.data['summary']['Неуспешных оплат'], 1)
        self.assertEqual(len(response.data['rows']), 2)
