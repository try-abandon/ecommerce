from enum import StrEnum

STAFF_CHANNEL = "customer-service:staff"


class RealTimeOutBoxType(StrEnum):
    MESSAGE_CREATE = "message_created"
    HANDOFF_CHANG = "handoff_changed"
