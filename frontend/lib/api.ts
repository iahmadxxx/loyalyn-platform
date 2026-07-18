export const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export function token() {
  return typeof window === 'undefined' ? '' : localStorage.getItem('loyalyn_token') || ''
}

export async function api<T = any>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers = new Headers(opts.headers)
  const bodyIsForm = typeof FormData !== 'undefined' && opts.body instanceof FormData
  if (!bodyIsForm && opts.body !== undefined) headers.set('Content-Type', 'application/json')
  const auth = token()
  if (auth) headers.set('Authorization', `Bearer ${auth}`)
  let response: Response
  try {
    response = await fetch(`${API}${path}`, { ...opts, headers, cache: 'no-store' })
  } catch {
    throw new Error('تعذر الاتصال بالسيرفر. تحقق من تشغيل الـ API والاتصال بالإنترنت.')
  }
  if (response.status === 401 && typeof window !== 'undefined') {
    localStorage.removeItem('loyalyn_token')
    location.href = '/login'
    throw new Error('انتهت الجلسة')
  }
  const contentType = response.headers.get('content-type') || ''
  const data: any = contentType.includes('application/json') ? await response.json().catch(() => ({})) : await response.text()
  if (!response.ok) {
    const detail = typeof data === 'object' ? data.detail : data
    if (Array.isArray(detail)) {
      throw new Error(detail.map((item: any) => item.msg || 'بيانات غير صحيحة').join('، '))
    }
    throw new Error(detail || `فشل الطلب (${response.status})`)
  }
  return data as T
}

export function logout() {
  localStorage.removeItem('loyalyn_token')
  location.href = '/login'
}
