from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from . import deals_service, models


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
        self.assertEqual(len(payload), 2)
        self.assertEqual(
            {item['status_code'] for item in payload},
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
        self.assertEqual(response.data['deal']['id'], deal.pk)
        self.assertEqual(response.data['deal']['property'], self.property.pk)

        self.assertTrue(models.OutgoingEmail.objects.filter(
            trigger_code='request_closed',
            request=request_obj,
            recipient=self.client_user,
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

        with patch('key.mailing._spawn_thread'):
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
