from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from sqlalchemy import Table, MetaData
from db.database import engine
import enum

Base = declarative_base()

# Reflect the existing users table
metadata = MetaData()
users_table = Table('users', metadata, autoload_with=engine)

class FriendshipStatus(enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    BLOCKED = "blocked"
    DECLINED = "declined"

class MessageStatus(enum.Enum):
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"

class Friendship(Base):
    __tablename__ = "friendships"
    
    id = Column(Integer, primary_key=True, index=True)
    requester_id = Column(Integer, ForeignKey(users_table.c.id), nullable=False, index=True)
    addressee_id = Column(Integer, ForeignKey(users_table.c.id), nullable=False, index=True)
    # Use String instead of Enum to avoid database enum issues
    status = Column(String(20), default="pending", nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    accepted_at = Column(DateTime, nullable=True)
    
    # Additional info
    message = Column(Text, nullable=True)  # Optional message with friend request
    
    def __repr__(self):
        return f"<Friendship(requester_id={self.requester_id}, addressee_id={self.addressee_id}, status={self.status})>"

class FriendMessage(Base):
    __tablename__ = "friend_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey(users_table.c.id), nullable=False, index=True)
    receiver_id = Column(Integer, ForeignKey(users_table.c.id), nullable=False, index=True)
    friendship_id = Column(Integer, ForeignKey("friendships.id"), nullable=False, index=True)
    
    # Message content
    content = Column(Text, nullable=False)
    message_type = Column(String(20), default="text")  # text, image, file, etc.
    
    # Message status - use String instead of Enum
    status = Column(String(20), default="sent", nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    read_at = Column(DateTime, nullable=True)
    
    # Relationships
    friendship = relationship("Friendship")
    
    def __repr__(self):
        return f"<FriendMessage(sender_id={self.sender_id}, receiver_id={self.receiver_id})>"

class FriendInvite(Base):
    __tablename__ = "friend_invites"
    
    id = Column(Integer, primary_key=True, index=True)
    inviter_id = Column(Integer, ForeignKey(users_table.c.id), nullable=False, index=True)
    invite_code = Column(String(50), unique=True, nullable=False, index=True)
    
    # Invite settings
    max_uses = Column(Integer, default=1)
    current_uses = Column(Integer, default=0)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Optional settings
    message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<FriendInvite(inviter_id={self.inviter_id}, code={self.invite_code})>"

class InviteUsage(Base):
    __tablename__ = "invite_usages"
    
    id = Column(Integer, primary_key=True, index=True)
    invite_id = Column(Integer, ForeignKey("friend_invites.id"), nullable=False, index=True)
    used_by_user_id = Column(Integer, ForeignKey(users_table.c.id), nullable=False, index=True)
    used_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    invite = relationship("FriendInvite")
    
    def __repr__(self):
        return f"<InviteUsage(invite_id={self.invite_id}, used_by={self.used_by_user_id})>"