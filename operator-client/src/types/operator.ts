export interface OperatorIdentity {
  id: string;
  operatorId: string;
  name: string;
  role: string;
  department?: string;
  availabilityStatus?: string;
}

export interface ActiveOperatorAssignment {
  machineId: string;
  machineCode: string;
  machineName: string;
  machineType: string;
  operationId: string;
  operationName: string;
  workOrderId: string;
  workOrderCode: string;
  status: string;
  remainingSeconds?: number;
  waitingReason?: string;
  materialName?: string;
  lotNumber?: string;
  location?: string;
}

export interface OperatorContext {
  operator: OperatorIdentity;
  activationStatus: 'NOT_ACTIVATED' | 'PENDING' | 'APPROVED' | 'REJECTED' | 'REVOKED';
  assignment: ActiveOperatorAssignment | null;
  serverTime: string;
}

export interface OperatorReport {
  id: string;
  incidentCode: string;
  title: string;
  description: string;
  machineCode?: string;
  workOrderCode?: string;
  status: 'PENDING_REVIEW' | 'ACTION_REQUIRED' | 'RESOLVED' | 'DISMISSED';
  createdAt: string;
  resolution?: string;
  dismissalReason?: string;
}
