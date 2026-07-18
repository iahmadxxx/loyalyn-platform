'use client'
import {useState} from 'react'
import {api} from '@/lib/api'
import {LockKeyhole} from 'lucide-react'

export default function Login(){
  const [email,setEmail]=useState('admin@loyalyn.site')
  const [password,setPassword]=useState('')
  const [error,setError]=useState('')
  const [busy,setBusy]=useState(false)
  async function submit(e:React.FormEvent){
    e.preventDefault();setBusy(true);setError('')
    try{await api('/api/auth/login',{method:'POST',body:JSON.stringify({email,password})});localStorage.removeItem('loyalyn_token');location.href='/admin'}
    catch(e:any){setError(e.message)}finally{setBusy(false)}
  }
  return <main className="login-page grid-bg"><form onSubmit={submit} className="login-card">
    <div className="login-icon"><LockKeyhole/></div>
    <div><p className="eyebrow">LOYALYN CONTROL CENTER</p><h1>دخول الإدارة</h1><p className="muted">أدخل بيانات حسابك للوصول إلى البراندات المصرح بها.</p></div>
    <label className="field"><span>البريد الإلكتروني</span><input className="input" type="email" autoComplete="username" value={email} onChange={e=>setEmail(e.target.value)} required/></label>
    <label className="field"><span>كلمة المرور</span><input type="password" className="input" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} required/></label>
    {error&&<p className="login-error" role="alert">{error}</p>}
    <button disabled={busy} className="btn primary login-submit">{busy?'جاري الدخول...':'دخول'}</button>
  </form></main>
}
