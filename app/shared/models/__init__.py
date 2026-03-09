"""
Import all shared models so SQLAlchemy registers them on Base.metadata.
Import from here to avoid circular imports between model files.
"""
from app.shared.models.user import User, UserProfile, UserEmail  # noqa: F401
from app.shared.models.auth import AuthSession, AuthProvider, EmailVerificationToken  # noqa: F401
from app.shared.models.org import Organization, OrgMembership, OrgInvite  # noqa: F401
from app.shared.models.product_access import ProductAccess  # noqa: F401
from app.shared.models.customer import Customer  # noqa: F401
from app.shared.models.plan import Plan  # noqa: F401
from app.shared.models.subscription import Subscription  # noqa: F401
from app.shared.models.payment import PaymentMethod, Transaction  # noqa: F401
from app.shared.models.invoice import Invoice, InvoiceItem  # noqa: F401
from app.shared.models.provider_link import ProviderLink  # noqa: F401
from app.shared.models.webhook_event import WebhookEvent  # noqa: F401
from app.shared.models.notification import Notification  # noqa: F401
from app.shared.models.api_key import ApiKey  # noqa: F401
from app.shared.models.feature_flag import FeatureFlag  # noqa: F401
from app.shared.models.audit_log import AuditLog  # noqa: F401
