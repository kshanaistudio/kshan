import json
from django.test import TestCase, Client
from faceshare.room_service import FaceShareRoomService

class FaceShareTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.room_service = FaceShareRoomService.get_instance()

    def test_create_and_get_room(self):
        room = self.room_service.create_room(host_name="Trek Leader")
        code = room['room_code']
        self.assertTrue(len(code) == 6)
        
        info = self.room_service.get_room(code)
        self.assertIsNotNone(info)
        self.assertEqual(info['host_name'], "Trek Leader")
        self.assertEqual(info['participant_count'], 0)

    def test_participant_join_and_approval(self):
        room = self.room_service.create_room(host_name="Host")
        code = room['room_code']
        token = room['host_token']

        # Join Request
        join_res = self.room_service.join_request(code, display_name="Aarav")
        self.assertTrue(join_res['success'])
        peer_id = join_res['peer_id']

        # Approval
        app_res = self.room_service.set_approval(code, token, peer_id, approved=True)
        self.assertTrue(app_res['success'])
        self.assertTrue(app_res['approved'])

    def test_participant_rejection(self):
        room = self.room_service.create_room(host_name="Host")
        code = room['room_code']
        token = room['host_token']

        join_res = self.room_service.join_request(code, display_name="Rohan")
        peer_id = join_res['peer_id']

        app_res = self.room_service.set_approval(code, token, peer_id, approved=False)
        self.assertTrue(app_res['success'])
        self.assertFalse(app_res['approved'])

    def test_api_create_and_status(self):
        res = self.client.post('/faceshare/api/create/', data=json.dumps({'host_name': 'Tester'}), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        
        code = data['room_code']
        status_res = self.client.get(f'/faceshare/api/{code}/status/')
        self.assertEqual(status_res.status_code, 200)
        self.assertTrue(status_res.json()['success'])

    def test_api_join_and_end(self):
        # Create
        create_res = self.client.post('/faceshare/api/create/', data=json.dumps({'host_name': 'Host Rahul'}), content_type='application/json')
        data = create_res.json()
        code = data['room_code']
        token = data['host_token']

        # Join
        join_res = self.client.post(f'/faceshare/api/{code}/join/', data=json.dumps({'display_name': 'Priya'}), content_type='application/json')
        self.assertEqual(join_res.status_code, 200)
        self.assertTrue(join_res.json()['success'])

        # End Room with valid token
        end_res = self.client.post(f'/faceshare/api/{code}/end/', data=json.dumps({'host_token': token}), content_type='application/json')
        self.assertEqual(end_res.status_code, 200)
        self.assertTrue(end_res.json()['success'])

        # Status after end should be 404
        after_res = self.client.get(f'/faceshare/api/{code}/status/')
        self.assertEqual(after_res.status_code, 404)

    def test_page_views(self):
        landing_res = self.client.get('/faceshare/')
        self.assertEqual(landing_res.status_code, 200)

        # Create a room
        room = self.room_service.create_room(host_name="Host")
        code = room['room_code']
        token = room['host_token']

        # Host view
        host_page = self.client.get(f'/faceshare/host/{code}/?token={token}')
        self.assertEqual(host_page.status_code, 200)

        # Participant view
        part_page = self.client.get(f'/faceshare/join/{code}/')
        self.assertEqual(part_page.status_code, 200)
