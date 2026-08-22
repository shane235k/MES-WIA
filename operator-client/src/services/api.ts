import { OperatorContext, OperatorReport } from '../types/operator';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const api = {
  /**
   * Submit an activation code to register this desktop client and request admin approval.
   */
  async activate(activationCode: string): Promise<{ sessionToken: string; status: string; operatorName: string; operatorEmployeeId: string }> {
    const res = await fetch(`${API_URL}/api/operator-activations/activate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        activationCode: activationCode.trim().toUpperCase(),
        clientInfo: {
          userAgent: navigator.userAgent,
          platform: navigator.platform,
          timestamp: new Date().toISOString()
        }
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Activation failed');
    }

    const data = await res.json();
    return {
      sessionToken: data.sessionToken,
      status: data.status,
      operatorName: data.operatorName,
      operatorEmployeeId: data.operatorEmployeeId
    };
  },

  /**
   * Check the approval status of an existing session token.
   */
  async checkStatus(sessionToken: string): Promise<{ status: string; operatorEmployeeId: string; operatorName: string }> {
    const res = await fetch(`${API_URL}/api/operator-activations/status/${sessionToken}`);
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to check status');
    }
    return await res.json();
  },

  /**
   * Fetch live operator profile & real-time workstation assignment.
   */
  async getContext(sessionToken: string): Promise<OperatorContext> {
    const res = await fetch(`${API_URL}/api/operators/me/context`, {
      headers: {
        'X-Operator-Session': sessionToken
      }
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to retrieve operator context');
    }

    return await res.json();
  },

  /**
   * Submit a free-form problem report against the current workstation.
   */
  async reportProblem(sessionToken: string, message: string, machineId?: string): Promise<any> {
    const res = await fetch(`${API_URL}/api/operator-alerts`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Operator-Session': sessionToken
      },
      body: JSON.stringify({
        operatorId: 'OPERATOR', // derived by backend from session
        message: message.trim(),
        machineId: machineId || undefined
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to submit problem report');
    }

    return await res.json();
  },

  /**
   * Fetch all reports submitted by the operator.
   */
  async getMyReports(sessionToken: string): Promise<OperatorReport[]> {
    const res = await fetch(`${API_URL}/api/operator-alerts/my-alerts`, {
      headers: {
        'X-Operator-Session': sessionToken
      }
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to fetch submitted reports');
    }

    return await res.json();
  },

  /**
   * Establish real-time WebSocket connection to receive instant admin review updates.
   */
  connectWebSocket(onEvent: (event: any) => void): () => void {
    const wsUrl = API_URL.replace(/^http/, 'ws') + '/api/ws/execution';
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (e) => {
      try {
        const parsed = JSON.parse(e.data);
        onEvent(parsed);
      } catch (err) {
        console.error('Operator WS Parse Error:', err);
      }
    };

    return () => {
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
    };
  }
};
