import json
import logging
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from .room_service import room_service

logger = logging.getLogger("kshan.faceshare.consumer")

class FaceShareSignalingConsumer(AsyncJsonWebsocketConsumer):
    """
    Async WebSocket signaling relay for WebRTC connections between Host and Participants.
    Facilitates:
    - Host room connection
    - Participant join request & approval
    - WebRTC SDP Offer / Answer exchange
    - ICE candidate forwarding
    - Participant disconnect notifications
    Does NOT handle, receive, or store photos/embeddings.
    """

    async def connect(self):
        self.room_code = self.scope['url_route']['kwargs'].get('room_code', '').upper()
        self.room_group_name = f"faceshare_{self.room_code}"
        self.role = None
        self.peer_id = None
        self.host_token = None

        if not self.room_code:
            await self.close(code=4000)
            return

        # Accept connection initially to receive authentication / role handshake
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name') and self.room_group_name:
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

        if self.role == 'host':
            logger.info(f"Host disconnected from room {self.room_code}")
            # Notify all participants that host disconnected
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'signaling_message',
                    'sender': 'system',
                    'action': 'host_disconnected',
                    'message': 'Host has disconnected from this sharing room.'
                }
            )
        elif self.role == 'participant' and self.peer_id:
            logger.info(f"Participant {self.peer_id} disconnected from room {self.room_code}")
            room_service.remove_participant(self.peer_id)
            # Notify host
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'signaling_message',
                    'sender': 'system',
                    'action': 'peer_disconnected',
                    'peer_id': self.peer_id
                }
            )

    async def receive_json(self, content):
        action = content.get('action')
        
        # 1. Host Initial Handshake
        if action == 'host_init':
            token = content.get('host_token')
            if room_service.verify_host(self.room_code, token):
                self.role = 'host'
                self.host_token = token
                await self.channel_layer.group_add(
                    self.room_group_name,
                    self.channel_name
                )
                await self.send_json({
                    'action': 'host_ready',
                    'room_code': self.room_code,
                    'status': 'active'
                })
                logger.info(f"Host initialized signaling for {self.room_code}")
            else:
                await self.send_json({'action': 'error', 'message': 'Invalid host authorization token.'})
                await self.close(code=4003)

        # 2. Participant Initial Handshake
        elif action == 'participant_init':
            peer_id = content.get('peer_id')
            self.role = 'participant'
            self.peer_id = peer_id
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            # Notify Host that a participant is present in room signaling
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'signaling_message',
                    'sender': self.peer_id,
                    'action': 'participant_waiting',
                    'peer_id': self.peer_id,
                    'display_name': content.get('display_name', 'Guest')
                }
            )

        # 3. Host Approves / Rejects Participant
        elif action == 'host_decision':
            if self.role != 'host':
                return
            target_peer = content.get('peer_id')
            decision = content.get('decision')  # 'approved' or 'rejected'
            approved = (decision == 'approved')
            
            res = room_service.set_approval(self.room_code, self.host_token, target_peer, approved)
            if res.get('success'):
                # Broadcast decision to the room group
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'signaling_message',
                        'sender': 'host',
                        'action': 'approval_status',
                        'target_peer': target_peer,
                        'approved': approved,
                        'message': 'Host approved your access.' if approved else 'Host declined your access.'
                    }
                )

        # 4. WebRTC Offer (From Host or Participant)
        elif action == 'webrtc_offer':
            target_peer = content.get('target_peer')
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'signaling_message',
                    'sender': self.peer_id if self.role == 'participant' else 'host',
                    'target_peer': target_peer,
                    'action': 'webrtc_offer',
                    'sdp': content.get('sdp')
                }
            )

        # 5. WebRTC Answer
        elif action == 'webrtc_answer':
            target_peer = content.get('target_peer')
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'signaling_message',
                    'sender': self.peer_id if self.role == 'participant' else 'host',
                    'target_peer': target_peer,
                    'action': 'webrtc_answer',
                    'sdp': content.get('sdp')
                }
            )

        # 6. WebRTC ICE Candidate Forwarding
        elif action == 'webrtc_ice_candidate':
            target_peer = content.get('target_peer')
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'signaling_message',
                    'sender': self.peer_id if self.role == 'participant' else 'host',
                    'target_peer': target_peer,
                    'action': 'webrtc_ice_candidate',
                    'candidate': content.get('candidate')
                }
            )

        # 7. Keepalive Ping
        elif action == 'ping':
            await self.send_json({'action': 'pong'})

    async def signaling_message(self, event):
        """
        Filters and sends signaling message to the intended recipient.
        """
        sender = event.get('sender')
        target_peer = event.get('target_peer')
        action = event.get('action')

        # Don't echo message back to the sender
        if self.role == 'host' and sender == 'host':
            return
        if self.role == 'participant' and sender == self.peer_id:
            return

        # Target peer filtering
        if target_peer:
            if self.role == 'participant' and target_peer != self.peer_id and target_peer != 'all':
                return
            if self.role == 'host' and target_peer != 'host' and target_peer != 'all':
                return

        # Forward message
        await self.send_json(event)
