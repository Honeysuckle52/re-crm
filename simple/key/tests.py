from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from . import deals_service, models


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
        self.request_one = models.Request.objects.create(
            client=self.client_one,
            agent=self.employee,
            operation_type=self.operation_type,
            status=self.status_open,
        )
        models.Request.objects.create(
            client=self.client_two,
            operation_type=self.operation_type,
            status=self.status_open,
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
        self.request_status_closed = models.RequestStatus.objects.create(
            code='closed',
            name='Closed',
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
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status_id, self.request_status_closed.pk)
        self.assertNotIn('deal', response.data)
        self.assertFalse(
            models.Deal.objects.filter(request=self.request_obj).exists(),
        )


class RequestWorkflowSignalTests(TestCase):
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
        self.request_status_closed = models.RequestStatus.objects.create(
            code='closed',
            name='Closed',
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
        self.employee = models.User.objects.create_user(
            username='workflow-agent',
            email='workflow-agent@example.com',
            password='Secret123!',
            user_type='employee',
        )
        self.client_user = models.User.objects.create_user(
            username='workflow-client',
            email='workflow-client@example.com',
            password='Secret123!',
            user_type='client',
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

        with patch('key.mailing._spawn_thread'):
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

        with patch('key.mailing._spawn_thread'):
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

        with patch('key.deals_service._attach_contract'), patch('key.mailing._spawn_thread'):
            response = self.api.post(
                f'/api/requests/{request_obj.pk}/close/',
                format='json',
            )

        self.assertEqual(response.status_code, 200)
        request_obj.refresh_from_db()
        self.assertEqual(request_obj.status_id, self.request_status_closed.pk)

        deal = models.Deal.objects.get(request=request_obj)
        self.assertEqual(deal.property_id, self.property.pk)
        self.assertEqual(deal.agent_id, self.employee.pk)
        self.assertEqual(deal.client_id, self.client_user.pk)
        self.assertEqual(response.data['deal']['id'], deal.pk)
        self.assertEqual(response.data['deal']['property'], self.property.pk)

        self.assertTrue(models.OutgoingEmail.objects.filter(
            trigger_code='request_closed',
            request=request_obj,
            recipient=self.client_user,
        ).exists())


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


class PropertyPhotoCoverTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.employee = models.User.objects.create_user(
            username='photo-user',
            email='photo-user@example.com',
            password='Secret123!',
            user_type='employee',
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
