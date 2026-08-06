class CIPSOrchestratorError(RuntimeError): pass
class WorkflowValidationError(CIPSOrchestratorError): pass
class DuplicateTaskError(WorkflowValidationError): pass
class TaskDependencyError(WorkflowValidationError): pass
class CircularDependencyError(WorkflowValidationError): pass
class DuplicateAgentError(CIPSOrchestratorError): pass
class AgentNotFoundError(CIPSOrchestratorError): pass
class CheckpointError(CIPSOrchestratorError): pass
