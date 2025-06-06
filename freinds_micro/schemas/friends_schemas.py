from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class FriendshipStatusEnum(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    BLOCKED = "blocked"
    DECLINED = "declined"

class MessageStatusEnum(str, Enum):
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"

# Request schemas
class SendFriendRequestSchema(BaseModel):
    addressee_username: str
    message: Optional[str] = None

class RespondToFriendRequestSchema(BaseModel):
    friendship_id: int
    status: FriendshipStatusEnum  # accepted, declined, blocked

class SendMessageSchema(BaseModel):
    receiver_username: str
    content: str
    message_type: str = "text"

class CreateInviteSchema(BaseModel):
    max_uses: int = 1
    expires_in_hours: Optional[int] = 24
    message: Optional[str] = None

# Response schemas
class UserBasicInfo(BaseModel):
    id: int
    username: str
    fname: Optional[str]
    lname: Optional[str]
    avatar: Optional[str]
    
    class Config:
        from_attributes = True

class FriendshipResponse(BaseModel):
    id: int
    requester_id: int
    addressee_id: int
    status: FriendshipStatusEnum
    created_at: datetime
    updated_at: datetime
    accepted_at: Optional[datetime]
    message: Optional[str]
    
    # Friend info (populated by service)
    friend_info: Optional[UserBasicInfo] = None
    
    class Config:
        from_attributes = True

class FriendMessageResponse(BaseModel):
    id: int
    sender_id: int
    receiver_id: int
    content: str
    message_type: str
    status: MessageStatusEnum
    created_at: datetime
    read_at: Optional[datetime]
    
    # Sender info (populated by service)
    sender_info: Optional[UserBasicInfo] = None
    
    class Config:
        from_attributes = True

class FriendInviteResponse(BaseModel):
    id: int
    invite_code: str
    max_uses: int
    current_uses: int
    expires_at: Optional[datetime]
    is_active: bool
    message: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class ChatConversationResponse(BaseModel):
    friend_info: UserBasicInfo
    last_message: Optional[FriendMessageResponse]
    unread_count: int
    friendship_id: int

class FriendsListResponse(BaseModel):
    friends: List[UserBasicInfo]
    total_count: int

class PaginatedMessagesResponse(BaseModel):
    messages: List[FriendMessageResponse]
    total_count: int
    page: int
    page_size: int
    has_next: bool