export const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function cookie(name: string) {
  if (typeof document === 'undefined') return ''
  const prefix = `${name}=`
  return document.cookie.split(';').map(v => v.trim()).find(v => v.startsWith(prefix))?.slice(prefix.length) || ''
}

async function request(path: string, opts: RequestInit = {}, retry = true): Promise<Response> {
  const headers = new Headers(opts.headers)
  const bodyIsForm = typeof FormData !== 'undefined' && opts.body instanceof FormData
  if (!bodyIsForm && opts.body !== undefined) headers.set('Content-Type', 'application/json')
  headers.set('X-Loyalyn-Client', 'web-v5.1.0')
  const csrf = decodeURIComponent(cookie('loyalyn_csrf'))
  if (csrf && !['GET', 'HEAD', 'OPTIONS'].includes(String(opts.method || 'GET').toUpperCase())) {
    headers.set('X-Loyalyn-CSRF', csrf)
  }
  let response: Response
  try {
    response = await fetch(`${API}${path}`, {...opts, headers, credentials: 'include', cache: 'no-store'})
  } catch {
    throw new Error('تعذر الاتصال بالسيرفر. تحقق من تشغيل الـ API والاتصال بالإنترنت.')
  }
  if (response.status === 401 && retry && !path.startsWith('/api/auth/')) {
    const refreshed = await request('/api/auth/refresh', {method: 'POST'}, false).catch(() => null)
    if (refreshed?.ok) return request(path, opts, false)
  }
  return response
}

export async function api<T = any>(path: string, opts: RequestInit = {}): Promise<T> {
  const response = await request(path, opts)
  if (response.status === 401 && typeof window !== 'undefined') {
    location.href = '/login'
    throw new Error('انتهت الجلسة')
  }
  const contentType = response.headers.get('content-type') || ''
  const data: any = contentType.includes('application/json') ? await response.json().catch(() => ({})) : await response.text()
  if (!response.ok) {
    const detail = typeof data === 'object' ? data.detail : data
    if (Array.isArray(detail)) throw new Error(detail.map((item: any) => item.msg || 'بيانات غير صحيحة').join('، '))
    throw new Error(detail || `فشل الطلب (${response.status})`)
  }
  return data as T
}

export async function logout() {
  try { await api('/api/auth/logout', {method: 'POST'}) } catch {}
  localStorage.removeItem('loyalyn_token')
  location.href = '/login'
}
