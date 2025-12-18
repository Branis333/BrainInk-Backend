from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class Subscription(Base):
	__tablename__ = "subscriptions"

	id = Column(Integer, primary_key=True, index=True)
	user_id = Column(Integer, index=True, nullable=False)

	# Simple status tracking for access control
	active = Column(Boolean, default=False, nullable=False)
	status = Column(String(32), default="inactive", nullable=False)

	# Payment bookkeeping (optional but useful)
	last_payment_id = Column(String(128), nullable=True)
	current_period_end = Column(DateTime, nullable=True)

	# Timestamps
	created_at = Column(DateTime, default=datetime.utcnow)
	updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
