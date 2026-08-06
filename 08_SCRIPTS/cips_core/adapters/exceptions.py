"""Excepciones de la capa de adaptadores de CIPS."""
class AdapterError(RuntimeError): pass
class AdapterContractError(AdapterError): pass
class AdapterValidationError(AdapterContractError): pass
class AdapterExecutionError(AdapterError): pass
class AdapterNotFoundError(AdapterError): pass
class AdapterAlreadyRegisteredError(AdapterError): pass
class AdapterDisabledError(AdapterError): pass
