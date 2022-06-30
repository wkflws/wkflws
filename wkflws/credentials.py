from dataclasses import dataclass


@dataclass
class BaseCredential:
    tenant_id: str  # uuid, ulid?
    integration_id: str
