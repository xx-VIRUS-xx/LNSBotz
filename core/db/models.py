import uuid
from sqlalchemy import String, Boolean, Integer, Float, Text, JSON, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import enum
from .base import Base


class PlanTier(str, enum.Enum):
    FREE = "free"
    STARTER = "starter"       # $9/mo
    PRO = "pro"               # $29/mo
    BUSINESS = "business"     # $99/mo


class BotCategory(str, enum.Enum):
    MONITORING = "monitoring"
    CONTENT = "content"
    TELEGRAM = "telegram"
    BUSINESS = "business"


# ── Users / Tenants ──────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    plan: Mapped[PlanTier] = mapped_column(SAEnum(PlanTier), default=PlanTier.FREE)
    stripe_customer_id: Mapped[str] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[str] = mapped_column(String(255), nullable=True)

    api_keys: Mapped[list["APIKey"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    bots: Mapped[list["BotInstance"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    usage_records: Mapped[list["UsageRecord"]] = relationship(back_populates="user")


class APIKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    key_prefix: Mapped[str] = mapped_column(String(8), nullable=False)  # e.g. "sk-abc123"
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[str] = mapped_column(String(50), nullable=True)
    requests_count: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="api_keys")


# ── Bot Instances ─────────────────────────────────────────────────────────────

class BotInstance(Base):
    __tablename__ = "bot_instances"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[BotCategory] = mapped_column(SAEnum(BotCategory), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    webhook_url: Mapped[str] = mapped_column(String(500), nullable=True)

    user: Mapped["User"] = relationship(back_populates="bots")
    executions: Mapped[list["TaskExecution"]] = relationship(back_populates="bot", cascade="all, delete-orphan")


# ── Task Executions ───────────────────────────────────────────────────────────

class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


class TaskExecution(Base):
    __tablename__ = "task_executions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bot_instances.id"), nullable=False)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[TaskStatus] = mapped_column(SAEnum(TaskStatus), default=TaskStatus.PENDING)
    input_data: Mapped[dict] = mapped_column(JSON, nullable=True)
    output_data: Mapped[dict] = mapped_column(JSON, nullable=True)
    error: Mapped[str] = mapped_column(Text, nullable=True)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

    bot: Mapped["BotInstance"] = relationship(back_populates="executions")


# ── Usage + Billing ───────────────────────────────────────────────────────────

class UsageRecord(Base):
    __tablename__ = "usage_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    bot_category: Mapped[str] = mapped_column(String(50), nullable=False)
    operation: Mapped[str] = mapped_column(String(100), nullable=False)
    tokens_input: Mapped[int] = mapped_column(Integer, default=0)
    tokens_output: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    model_used: Mapped[str] = mapped_column(String(100), nullable=True)

    user: Mapped["User"] = relationship(back_populates="usage_records")


# ── Monitoring Bot ────────────────────────────────────────────────────────────

class MonitoredSource(Base):
    __tablename__ = "monitored_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bot_instances.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)  # reddit, rss, twitter, youtube
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_checked_at: Mapped[str] = mapped_column(String(50), nullable=True)


class MonitoredAlert(Base):
    __tablename__ = "monitored_alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("monitored_sources.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=True)
    sentiment: Mapped[str] = mapped_column(String(20), nullable=True)
    urgency: Mapped[str] = mapped_column(String(20), nullable=True)
    original_url: Mapped[str] = mapped_column(String(1000), nullable=True)
    raw_data: Mapped[dict] = mapped_column(JSON, nullable=True)
    delivered: Mapped[bool] = mapped_column(Boolean, default=False)


# ── Conversation Memory (Telegram/WhatsApp bots) ──────────────────────────────

class ConversationSession(Base):
    __tablename__ = "conversation_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bot_instances.id"), nullable=False)
    external_user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    messages: Mapped[list] = mapped_column(JSON, default=list)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ── Product Jobs — track all product executions ───────────────────────────────

class ProductJobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class ProductJob(Base):
    __tablename__ = "product_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    product_category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    product_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[ProductJobStatus] = mapped_column(SAEnum(ProductJobStatus), default=ProductJobStatus.PENDING)
    input_data: Mapped[dict] = mapped_column(JSON, nullable=True)
    output_data: Mapped[dict] = mapped_column(JSON, nullable=True)
    error: Mapped[str] = mapped_column(Text, nullable=True)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=True)


# ── Scheduled Product Jobs ────────────────────────────────────────────────────

class ScheduledProduct(Base):
    __tablename__ = "scheduled_products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    product_category: Mapped[str] = mapped_column(String(50), nullable=False)
    product_type: Mapped[str] = mapped_column(String(100), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False, default="0 8 * * *")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[str] = mapped_column(String(50), nullable=True)
    run_count: Mapped[int] = mapped_column(Integer, default=0)
