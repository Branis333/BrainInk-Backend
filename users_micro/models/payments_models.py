from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from db.database import Base


class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    provider = Column(String(32), default="flutterwave", nullable=False)
    plan_id = Column(String(64), nullable=True)
    customer_id = Column(String(64), nullable=True)
    subscription_id = Column(String(64), nullable=True)
    last_payment_id = Column(String(64), nullable=True)
    status = Column(String(32), default="inactive")  # active, cancelled, past_due
    active = Column(Boolean, default=False)
    current_period_end = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('user_id', 'provider', name='uq_user_provider'),
    )
