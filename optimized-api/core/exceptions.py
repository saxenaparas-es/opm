class EfficiencyError(Exception):
    pass


class ValidationError(EfficiencyError):
    def __init__(self, field: str, message: str = None):
        self.field = field
        self.message = message or f"Validation failed for field: {field}"
        super().__init__(self.message)


class CalculationError(EfficiencyError):
    pass


class DataFetchError(EfficiencyError):
    pass


class ConfigurationError(EfficiencyError):
    pass