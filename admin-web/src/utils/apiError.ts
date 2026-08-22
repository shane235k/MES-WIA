export function extractErrorMessage(errData: any, defaultMsg: string = 'Operation failed'): string {
  if (!errData) return defaultMsg;
  if (typeof errData === 'string') return errData;
  if (typeof errData.detail === 'string') return errData.detail;
  if (Array.isArray(errData.detail)) {
    return errData.detail
      .map((e: any) => {
        const field = e.loc ? e.loc.filter((l: any) => l !== 'body').join('.') : 'field';
        return `${field}: ${e.msg || 'invalid value'}`;
      })
      .join('; ');
  }
  if (errData.detail && typeof errData.detail === 'object') {
    return JSON.stringify(errData.detail);
  }
  if (errData.message && typeof errData.message === 'string') {
    return errData.message;
  }
  return defaultMsg;
}
