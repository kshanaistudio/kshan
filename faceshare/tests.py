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

    def test_api_create_and_status(self):
        res = self.client.post('/faceshare/api/create/', data=json.dumps({'host_name': 'Tester'}), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        
        code = data['room_code']
        status_res = self.client.get(f'/faceshare/api/{code}/status/')
        self.assertEqual(status_res.status_code, 200)
        self.assertTrue(status_res.json()['success'])
