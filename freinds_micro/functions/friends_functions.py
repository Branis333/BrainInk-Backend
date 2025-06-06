from sqlalchemy.orm import Session
from sqlalchemy import text, or_, and_
from sqlalchemy.exc import OperationalError, DisconnectionError
from models.friends_models import Friendship, FriendMessage, FriendInvite, InviteUsage, FriendshipStatus, MessageStatus
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import secrets
import string
import time

class FriendsService:
    def __init__(self, db: Session):
        self.db = db
    
    def _execute_with_retry(self, query, params=None, max_retries=3):
        """Execute database query with retry logic"""
        for attempt in range(max_retries):
            try:
                if params:
                    result = self.db.execute(query, params)
                else:
                    result = self.db.execute(query)
                return result
            except (OperationalError, DisconnectionError) as e:
                print(f"Database query attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    # Rollback and wait before retry
                    try:
                        self.db.rollback()
                    except:
                        pass
                    time.sleep(1)  # Wait 1 second before retry
                    continue
                else:
                    raise e
            except Exception as e:
                # For non-connection errors, don't retry
                raise e
    
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user info by username using raw SQL with retry logic"""
        try:
            query = text("SELECT id, username, fname, lname, avatar FROM users WHERE username = :username AND is_active = true")
            result = self._execute_with_retry(query, {"username": username})
            row = result.fetchone()
            
            if row:
                return {
                    "id": row.id,
                    "username": row.username,
                    "fname": row.fname,
                    "lname": row.lname,
                    "avatar": row.avatar
                }
            return None
        except Exception as e:
            print(f"Error getting user by username '{username}': {e}")
            return None
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user info by ID using raw SQL with retry logic"""
        try:
            query = text("SELECT id, username, fname, lname, avatar FROM users WHERE id = :user_id AND is_active = true")
            result = self._execute_with_retry(query, {"user_id": user_id})
            row = result.fetchone()
            
            if row:
                return {
                    "id": row.id,
                    "username": row.username,
                    "fname": row.fname,
                    "lname": row.lname,
                    "avatar": row.avatar
                }
            return None
        except Exception as e:
            print(f"Error getting user by ID '{user_id}': {e}")
            return None
    
    def send_friend_request(self, requester_id: int, addressee_username: str, message: str = None) -> Tuple[bool, str, Optional[Friendship]]:
        """Send a friend request with better error handling"""
        try:
            # Get addressee user
            addressee = self.get_user_by_username(addressee_username)
            if not addressee:
                return False, "User not found", None
            
            addressee_id = addressee["id"]
            
            # Check if it's the same user
            if requester_id == addressee_id:
                return False, "Cannot send friend request to yourself", None
            
            # Check if friendship already exists
            existing = self.db.query(Friendship).filter(
                or_(
                    and_(Friendship.requester_id == requester_id, Friendship.addressee_id == addressee_id),
                    and_(Friendship.requester_id == addressee_id, Friendship.addressee_id == requester_id)
                )
            ).first()
            
            if existing:
                if existing.status == "accepted":
                    return False, "You are already friends", None
                elif existing.status == "pending":
                    return False, "Friend request already sent", None
                elif existing.status == "blocked":
                    return False, "Cannot send friend request", None
            
            # Create new friendship
            friendship = Friendship(
                requester_id=requester_id,
                addressee_id=addressee_id,
                status="pending",  # Use string instead of enum
                message=message
            )
            
            self.db.add(friendship)
            self.db.commit()
            self.db.refresh(friendship)
            
            return True, "Friend request sent successfully", friendship
            
        except Exception as e:
            self.db.rollback()
            print(f"Error sending friend request: {e}")
            return False, f"Failed to send friend request: {str(e)}", None
    
    def respond_to_friend_request(self, user_id: int, friendship_id: int, status: str) -> Tuple[bool, str]:
        """Respond to a friend request with better error handling"""
        try:
            # Convert enum value to string if needed
            if hasattr(status, 'value'):
                status_str = status.value
            else:
                status_str = str(status)
            
            friendship = self.db.query(Friendship).filter(
                Friendship.id == friendship_id,
                Friendship.addressee_id == user_id,
                Friendship.status == "pending"
            ).first()
            
            if not friendship:
                return False, "Friend request not found or already responded"
            
            # Update using string values
            friendship.status = status_str
            friendship.updated_at = datetime.utcnow()
            
            if status_str == "accepted":
                friendship.accepted_at = datetime.utcnow()
            
            self.db.commit()
            
            return True, f"Friend request {status_str}"
            
        except Exception as e:
            self.db.rollback()
            print(f"Error responding to friend request: {e}")
            return False, f"Failed to respond to friend request: {str(e)}"
    
    def get_friends_list(self, user_id: int) -> List[Dict[str, Any]]:
        """Get list of user's friends with error handling"""
        try:
            friendships = self.db.query(Friendship).filter(
                or_(
                    and_(Friendship.requester_id == user_id, Friendship.status == "accepted"),
                    and_(Friendship.addressee_id == user_id, Friendship.status == "accepted")
                )
            ).all()
            
            friends = []
            for friendship in friendships:
                friend_id = friendship.addressee_id if friendship.requester_id == user_id else friendship.requester_id
                friend_info = self.get_user_by_id(friend_id)
                if friend_info:
                    friends.append(friend_info)
            
            return friends
            
        except Exception as e:
            print(f"Error getting friends list: {e}")
            return []
    
    def get_pending_requests(self, user_id: int) -> List[Friendship]:
        """Get pending friend requests received by user"""
        try:
            return self.db.query(Friendship).filter(
                Friendship.addressee_id == user_id,
                Friendship.status == "pending"
            ).all()
        except Exception as e:
            print(f"Error getting pending requests: {e}")
            return []
    
    def get_sent_requests(self, user_id: int) -> List[Friendship]:
        """Get pending friend requests sent by user"""
        try:
            return self.db.query(Friendship).filter(
                Friendship.requester_id == user_id,
                Friendship.status == "pending"
            ).all()
        except Exception as e:
            print(f"Error getting sent requests: {e}")
            return []
    
    def are_friends(self, user_id1: int, user_id2: int) -> bool:
        """Check if two users are friends with error handling"""
        try:
            friendship = self.db.query(Friendship).filter(
                or_(
                    and_(Friendship.requester_id == user_id1, Friendship.addressee_id == user_id2),
                    and_(Friendship.requester_id == user_id2, Friendship.addressee_id == user_id1)
                ),
                Friendship.status == "accepted"
            ).first()
            
            return friendship is not None
            
        except Exception as e:
            print(f"Error checking friendship: {e}")
            return False
    
    def send_message(self, sender_id: int, receiver_username: str, content: str, message_type: str = "text") -> Tuple[bool, str, Optional[FriendMessage]]:
        """Send a message to a friend"""
        try:
            # Get receiver user
            receiver = self.get_user_by_username(receiver_username)
            if not receiver:
                return False, "User not found", None
            
            receiver_id = receiver["id"]
            
            # Check if they are friends
            if not self.are_friends(sender_id, receiver_id):
                return False, "You can only message friends", None
            
            # Get friendship
            friendship = self.db.query(Friendship).filter(
                or_(
                    and_(Friendship.requester_id == sender_id, Friendship.addressee_id == receiver_id),
                    and_(Friendship.requester_id == receiver_id, Friendship.addressee_id == sender_id)
                ),
                Friendship.status == "accepted"
            ).first()
            
            # Create message
            message = FriendMessage(
                sender_id=sender_id,
                receiver_id=receiver_id,
                friendship_id=friendship.id,
                content=content,
                message_type=message_type,
                status="sent"  # Use string instead of enum
            )
            
            self.db.add(message)
            self.db.commit()
            self.db.refresh(message)
            
            return True, "Message sent successfully", message
            
        except Exception as e:
            self.db.rollback()
            print(f"Error sending message: {e}")
            return False, f"Failed to send message: {str(e)}", None
    
    def get_conversation(self, user_id: int, friend_username: str, page: int = 1, page_size: int = 50) -> Tuple[List[FriendMessage], int]:
        """Get conversation messages between two friends"""
        try:
            friend = self.get_user_by_username(friend_username)
            if not friend:
                return [], 0
            
            friend_id = friend["id"]
            
            # Check if they are friends
            if not self.are_friends(user_id, friend_id):
                return [], 0
            
            # Get total count
            total_count = self.db.query(FriendMessage).filter(
                or_(
                    and_(FriendMessage.sender_id == user_id, FriendMessage.receiver_id == friend_id),
                    and_(FriendMessage.sender_id == friend_id, FriendMessage.receiver_id == user_id)
                )
            ).count()
            
            # Get messages with pagination
            offset = (page - 1) * page_size
            messages = self.db.query(FriendMessage).filter(
                or_(
                    and_(FriendMessage.sender_id == user_id, FriendMessage.receiver_id == friend_id),
                    and_(FriendMessage.sender_id == friend_id, FriendMessage.receiver_id == user_id)
                )
            ).order_by(FriendMessage.created_at.desc()).offset(offset).limit(page_size).all()
            
            return messages, total_count
            
        except Exception as e:
            print(f"Error getting conversation: {e}")
            return [], 0
    
    def mark_messages_as_read(self, user_id: int, friend_username: str) -> bool:
        """Mark all messages from a friend as read"""
        try:
            friend = self.get_user_by_username(friend_username)
            if not friend:
                return False
            
            friend_id = friend["id"]
            
            # Update unread messages
            self.db.query(FriendMessage).filter(
                FriendMessage.sender_id == friend_id,
                FriendMessage.receiver_id == user_id,
                FriendMessage.status != "read"
            ).update({
                "status": "read",
                "read_at": datetime.utcnow()
            })
            
            self.db.commit()
            return True
            
        except Exception as e:
            print(f"Error marking messages as read: {e}")
            return False
    
    def create_invite(self, inviter_id: int, max_uses: int = 1, expires_in_hours: int = 24, message: str = None) -> FriendInvite:
        """Create a friend invite code"""
        try:
            # Generate unique invite code
            while True:
                code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
                existing = self.db.query(FriendInvite).filter(FriendInvite.invite_code == code).first()
                if not existing:
                    break
            
            expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours) if expires_in_hours else None
            
            invite = FriendInvite(
                inviter_id=inviter_id,
                invite_code=code,
                max_uses=max_uses,
                expires_at=expires_at,
                message=message
            )
            
            self.db.add(invite)
            self.db.commit()
            self.db.refresh(invite)
            
            return invite
            
        except Exception as e:
            self.db.rollback()
            print(f"Error creating invite: {e}")
            raise e
    
    def use_invite(self, user_id: int, invite_code: str) -> Tuple[bool, str]:
        """Use an invite code to send friend request"""
        try:
            invite = self.db.query(FriendInvite).filter(
                FriendInvite.invite_code == invite_code,
                FriendInvite.is_active == True
            ).first()
            
            if not invite:
                return False, "Invalid invite code"
            
            # Check if expired
            if invite.expires_at and invite.expires_at < datetime.utcnow():
                return False, "Invite code has expired"
            
            # Check if max uses reached
            if invite.current_uses >= invite.max_uses:
                return False, "Invite code has reached maximum uses"
            
            # Check if user already used this invite
            existing_usage = self.db.query(InviteUsage).filter(
                InviteUsage.invite_id == invite.id,
                InviteUsage.used_by_user_id == user_id
            ).first()
            
            if existing_usage:
                return False, "You have already used this invite code"
            
            # Send friend request
            inviter = self.get_user_by_id(invite.inviter_id)
            success, message, friendship = self.send_friend_request(
                user_id, 
                inviter["username"], 
                f"Used invite code: {invite.message}" if invite.message else "Used invite code"
            )
            
            if success:
                # Record invite usage
                usage = InviteUsage(
                    invite_id=invite.id,
                    used_by_user_id=user_id
                )
                self.db.add(usage)
                
                # Update invite usage count
                invite.current_uses += 1
                
                # Deactivate if max uses reached
                if invite.current_uses >= invite.max_uses:
                    invite.is_active = False
                
                self.db.commit()
                
                return True, "Friend request sent using invite code"
            else:
                return False, message
                
        except Exception as e:
            self.db.rollback()
            print(f"Error using invite: {e}")
            return False, f"Failed to use invite: {str(e)}"