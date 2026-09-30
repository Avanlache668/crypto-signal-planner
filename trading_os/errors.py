class TradingOSError(Exception):
    """Base domain error."""


class ValidationError(TradingOSError):
    pass


class ConcurrencyError(TradingOSError):
    pass


class CapabilityDenied(TradingOSError):
    pass


class StaleData(ValidationError):
    pass


class DuplicateEvent(TradingOSError):
    pass
