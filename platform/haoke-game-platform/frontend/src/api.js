let csrf = '';
export function setCSRF(value) { csrf = value || ''; }
export async function api(path, options = {}) {
  const method = options.method || 'GET';
  const headers = { ...options.headers };
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';
  if (!['GET','HEAD'].includes(method)) {
    if (csrf) headers['X-CSRF-Token'] = csrf;
    if (path.startsWith('/admin/')) headers['Idempotency-Key'] = options.idempotencyKey || crypto.randomUUID();
  }
  let response;
  try {
    response = await fetch('/api' + path, { ...options, method, headers, credentials: 'same-origin', body: options.body === undefined ? undefined : JSON.stringify(options.body) });
  } catch (e) {
    if (e.name === 'AbortError') throw e;
    throw new Error('暂时无法连接服务，请检查本地服务是否运行');
  }
  let result;
  try { result = await response.json(); } catch { throw new Error('服务返回了异常响应，请稍后重试'); }
  if (!response.ok) {
    const error = new Error(result.error?.message || '操作未成功，请重试');
    error.code = result.error?.code;
    error.status = response.status;
    error.fields = result.error?.fields;
    throw error;
  }
  return result;
}
export const post = (path, body = {}) => api(path, { method: 'POST', body });
export const fmtDate = (value) => value ? new Intl.DateTimeFormat('zh-CN', {timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(value*1000)) : '—';
