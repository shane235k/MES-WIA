from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class SafeToolDefinition(BaseModel):
    name: str
    description: str
    permission: str = "MUTATION"  # "READ_ONLY" or "MUTATION"
    parameters_schema: Dict[str, Any]
    required_parameters: List[str]
    expected_state_change: str

SAFE_TOOL_REGISTRY: Dict[str, SafeToolDefinition] = {
    "get_machine_status": SafeToolDefinition(
        name="get_machine_status",
        description="Retrieve real-time telemetry, runtime state, and active assignments of a specific machine.",
        permission="READ_ONLY",
        parameters_schema={
            "machineId": {"type": "string", "description": "Machine ObjectId"},
            "machineCode": {"type": "string", "description": "Machine business code e.g. M-03"}
        },
        required_parameters=[],
        expected_state_change="None (Read-only query)"
    ),
    "get_work_order_execution": SafeToolDefinition(
        name="get_work_order_execution",
        description="Retrieve comprehensive DAG execution status, operation states, and resource assignments for a work order.",
        permission="READ_ONLY",
        parameters_schema={
            "workOrderId": {"type": "string", "description": "Work Order ObjectId"},
            "workOrderCode": {"type": "string", "description": "Work Order code e.g. WO-1001"}
        },
        required_parameters=[],
        expected_state_change="None (Read-only query)"
    ),
    "get_incident_context": SafeToolDefinition(
        name="get_incident_context",
        description="Retrieve deep incident snapshot including reporting operator, machine, work order, and telemetry events.",
        permission="READ_ONLY",
        parameters_schema={
            "incidentId": {"type": "string", "description": "Incident ObjectId"}
        },
        required_parameters=["incidentId"],
        expected_state_change="None (Read-only query)"
    ),
    "get_available_resources": SafeToolDefinition(
        name="get_available_resources",
        description="Find compatible, idle machines and available certified operators for rerouting or failover.",
        permission="READ_ONLY",
        parameters_schema={
            "requiredMachineType": {"type": "string", "description": "Optional generic machine type e.g. WELDING, CUTTING"},
            "department": {"type": "string", "description": "Optional shop floor department filter"}
        },
        required_parameters=[],
        expected_state_change="None (Read-only query)"
    ),
    "pause_operation": SafeToolDefinition(
        name="pause_operation",
        description="Safely pause an in-progress work order operation due to machine failure, maintenance, or material issue.",
        permission="MUTATION",
        parameters_schema={
            "workOrderId": {"type": "string", "description": "Work Order ObjectId or code"},
            "operationId": {"type": "string", "description": "Operation ID e.g. OP-30"},
            "reason": {"type": "string", "description": "Reason for pausing operation"}
        },
        required_parameters=["workOrderId", "operationId"],
        expected_state_change="Operation enters PAUSED state; machine and operator released if specified."
    ),
    "resume_operation": SafeToolDefinition(
        name="resume_operation",
        description="Resume a previously paused or interrupted work order operation once resources are restored.",
        permission="MUTATION",
        parameters_schema={
            "workOrderId": {"type": "string", "description": "Work Order ObjectId or code"},
            "operationId": {"type": "string", "description": "Operation ID e.g. OP-30"},
            "reason": {"type": "string", "description": "Reason for resuming operation"}
        },
        required_parameters=["workOrderId", "operationId"],
        expected_state_change="Operation transitions to READY or IN_PROGRESS depending on resource availability."
    ),
    "stop_work_order": SafeToolDefinition(
        name="stop_work_order",
        description="Halt execution of an entire work order and all active operations.",
        permission="MUTATION",
        parameters_schema={
            "workOrderId": {"type": "string", "description": "Work Order ObjectId or code"},
            "reason": {"type": "string", "description": "Reason for stopping work order"}
        },
        required_parameters=["workOrderId"],
        expected_state_change="Work Order enters PAUSED or FAILED state; all running operations paused."
    ),
    "mark_machine_down": SafeToolDefinition(
        name="mark_machine_down",
        description="Authoritatively transition machine to DOWN state via authoritative Incident / Machine failure service.",
        permission="MUTATION",
        parameters_schema={
            "machineId": {"type": "string", "description": "Machine ObjectId"},
            "machineCode": {"type": "string", "description": "Machine business code e.g. M-03"},
            "incidentId": {"type": "string", "description": "Optional associated Incident ID"},
            "reason": {"type": "string", "description": "Detailed failure justification"}
        },
        required_parameters=[],
        expected_state_change="Machine status becomes DOWN; incident updated to ACTION_REQUIRED; failover evaluated."
    ),
    "reroute_operation": SafeToolDefinition(
        name="reroute_operation",
        description="Reroute a work order operation from a failed or occupied machine to a compatible available backup machine.",
        permission="MUTATION",
        parameters_schema={
            "workOrderId": {"type": "string", "description": "Work Order ObjectId or code"},
            "operationId": {"type": "string", "description": "Operation ID e.g. OP-30"},
            "targetMachineId": {"type": "string", "description": "Target backup Machine ObjectId"},
            "targetMachineCode": {"type": "string", "description": "Target backup Machine code e.g. M-04"},
            "targetOperatorId": {"type": "string", "description": "Optional target Operator ID"}
        },
        required_parameters=["workOrderId", "operationId"],
        expected_state_change="Operation assigned machine updated; operation set to READY; failover event logged."
    ),
    "schedule_maintenance": SafeToolDefinition(
        name="schedule_maintenance",
        description="Schedule repair downtime for a machine and transition status to MAINTENANCE with estimated return timer.",
        permission="MUTATION",
        parameters_schema={
            "machineId": {"type": "string", "description": "Machine ObjectId"},
            "machineCode": {"type": "string", "description": "Machine business code e.g. M-03"},
            "incidentId": {"type": "string", "description": "Optional associated Incident ID"},
            "durationMinutes": {"type": "integer", "description": "Estimated repair duration in minutes"},
            "reason": {"type": "string", "description": "Repair explanation"}
        },
        required_parameters=["durationMinutes"],
        expected_state_change="Machine status becomes MAINTENANCE; countdown timer initialized."
    ),
    "resolve_incident": SafeToolDefinition(
        name="resolve_incident",
        description="Resolve an active incident, record root cause resolution notes, and recover equipment to IDLE.",
        permission="MUTATION",
        parameters_schema={
            "incidentId": {"type": "string", "description": "Incident ObjectId"},
            "resolution": {"type": "string", "description": "Root cause resolution summary"}
        },
        required_parameters=["incidentId", "resolution"],
        expected_state_change="Incident status becomes RESOLVED; associated DOWN machine recovered to IDLE."
    ),
    "create_execution_action_log": SafeToolDefinition(
        name="create_execution_action_log",
        description="Record an AI execution annotation or supervisor advisory note in the execution event stream.",
        permission="MUTATION",
        parameters_schema={
            "workOrderId": {"type": "string", "description": "Work Order ObjectId or code"},
            "message": {"type": "string", "description": "Advisory log message"},
            "details": {"type": "object", "description": "Optional structured metadata"}
        },
        required_parameters=["workOrderId", "message"],
        expected_state_change="Execution event appended to execution_events and broadcast via WebSocket."
    )
}

def validate_tool_call(tool_name: str, parameters: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Validate that a proposed tool call exists in the safe registry and has valid parameters.
    Returns (is_valid, error_message).
    """
    if tool_name not in SAFE_TOOL_REGISTRY:
        return False, f"Tool '{tool_name}' is not in the safe registered tool catalog."

    tool_def = SAFE_TOOL_REGISTRY[tool_name]
    for req_param in tool_def.required_parameters:
        if req_param not in parameters or parameters[req_param] is None:
            return False, f"Tool '{tool_name}' is missing mandatory parameter '{req_param}'."

    return True, None

def get_tools_summary_for_prompt() -> str:
    """
    Generate structured prompt descriptions of all safe registered tools for Gemini.
    """
    lines = []
    for name, tool in SAFE_TOOL_REGISTRY.items():
        lines.append(f"- Tool: `{name}` ({tool.permission})")
        lines.append(f"  Description: {tool.description}")
        lines.append(f"  Parameters: {tool.parameters_schema}")
        lines.append(f"  Expected Effect: {tool.expected_state_change}")
    return "\n".join(lines)
