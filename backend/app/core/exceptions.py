class InsufficientCreditsError(Exception):
    pass


class BillingConsistencyError(Exception):
    pass


class DuplicateBillingOperationError(Exception):
    pass


class PromocodeNotFoundError(Exception):
    pass


class PromocodeInactiveError(Exception):
    pass


class PromocodeExpiredError(Exception):
    pass


class PromocodeActivationLimitError(Exception):
    pass


class PromocodeAlreadyActivatedError(Exception):
    pass


class InvalidChallengeSubmissionError(Exception):
    pass


class ModelNotFoundError(Exception):
    pass


class ModelLoadError(Exception):
    pass


class InvalidFeaturePayloadError(Exception):
    pass


class ModelMetadataNotFoundError(Exception):
    pass


class PredictionNotFoundError(Exception):
    pass
