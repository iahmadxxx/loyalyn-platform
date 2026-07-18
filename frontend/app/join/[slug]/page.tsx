'use client'

import {useEffect, useState} from 'react'
import {useParams} from 'next/navigation'
import {API} from '@/lib/api'
import {AlertTriangle, CheckCircle2, Loader2, QrCode, Sparkles} from 'lucide-react'

type Row = Record<string, any>

export default function BrandJoin(){
  const params=useParams<{slug:string}>()
  const [profile,setProfile]=useState<Row|null>(null)
  const [result,setResult]=useState<Row|null>(null)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')

  useEffect(()=>{
    fetch(`${API}/api/public/brands/${params.slug}`,{cache:'no-store'})
      .then(async response=>{
        const data=await response.json()
        if(!response.ok)throw new Error(data.detail||'صفحة التسجيل غير متاحة')
        setProfile(data)
      })
      .catch(e=>setError(e.message))
  },[params.slug])

  async function submit(event:React.FormEvent<HTMLFormElement>){
    event.preventDefault();setBusy(true);setError('')
    const form=new FormData(event.currentTarget)
    try{
      const response=await fetch(`${API}/api/public/brands/${params.slug}/join`,{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          name:form.get('name'),phone:form.get('phone'),email:form.get('email')||null,
          birthday:form.get('birthday')||null,
        }),
      })
      const data=await response.json()
      if(!response.ok)throw new Error(Array.isArray(data.detail)?data.detail.map((x:Row)=>x.msg).join('، '):data.detail||'تعذر التسجيل')
      setResult(data)
    }catch(e:any){setError(e.message)}finally{setBusy(false)}
  }

  if(error&&!profile)return <main className="join-page grid-bg"><div className="warning-box"><h1>تعذر فتح التسجيل</h1><p>{error}</p></div></main>
  if(!profile)return <main className="join-page grid-bg"><Loader2 className="animate-spin"/></main>
  const brand=profile.brand

  if(result)return <main className="join-page grid-bg"><section className="join-shell"><div className="join-success">
    <CheckCircle2/><h1>تم تسجيل عضويتك</h1>
    <p>تم إنشاء حسابك لدى <b>{brand.name}</b>. سيحدد البراند البطاقة أو البطاقات المناسبة لك، ثم يرسل لك رابط إضافة كل بطاقة إلى Apple Wallet.</p>
    <div className="wallet-pending-box"><Sparkles/><div><b>بطاقاتك تُجهّز حسب اختيار البراند</b><small>{result.wallet?.message||'يمكن تفعيل بطاقة القهوة أو الحلى أو أكثر من بطاقة لنفس العضوية.'}</small></div></div>
    <div className="member-qr-block"><div className="member-qr-title"><QrCode/><div><b>رمز العضوية للموظف</b><small>احتفظ به ليتعرف الموظف على حسابك وإضافة الأختام للبطاقات المفعلة.</small></div></div><img src={`${API}/api/public/members/${result.customer.membership_code}/qr.svg`} alt="رمز العضوية للموظف"/><code>{result.customer.membership_code}</code></div>
    <button type="button" className="btn secondary" onClick={()=>location.reload()}>تسجيل عميل آخر</button>
  </div></section></main>

  return <main className="join-page grid-bg"><section className="join-shell">
    <header className="join-brand" style={{borderColor:brand.accent_color}}><div className="brand-mark large" style={{background:brand.primary_color,color:brand.accent_color}}>{brand.name[0]}</div><div><small>LOYALYN MEMBER</small><h1>{brand.name}</h1><p>{brand.join_welcome_text||'سجّل عضويتك، والبراند يختار لك البطاقة المناسبة.'}</p></div></header>
    {error&&<div className="inline-error"><AlertTriangle size={18}/><span>{error}</span></div>}
    <form className="join-form" onSubmit={submit}>
      <div className="join-step-title"><span>1</span><div><b>أدخل بياناتك</b><small>بطاقاتك تُضاف لاحقًا حسب اختيار البراند، ويمكن تشغيل أكثر من بطاقة معًا.</small></div></div>
      <label><span>الاسم</span><input name="name" required minLength={2} placeholder="اسم العميل" autoComplete="name"/></label>
      <label><span>رقم الجوال</span><input name="phone" required minLength={5} inputMode="tel" placeholder="مثال: 55555555" autoComplete="tel"/></label>
      <label><span>البريد الإلكتروني {brand.join_require_email?'':'(اختياري)'}</span><input name="email" type="email" required={brand.join_require_email} autoComplete="email"/></label>
      <label><span>تاريخ الميلاد (اختياري)</span><input name="birthday" type="date"/></label>
      <button className="btn primary join-submit" disabled={busy}>{busy?<Loader2 className="animate-spin"/>:<Sparkles/>}<span>{busy?'جاري إنشاء العضوية...':'إنشاء عضويتي'}</span></button>
      <p className="join-privacy">بالتسجيل توافق على حفظ بيانات العضوية لدى البراند فقط.</p>
    </form>
  </section></main>
}
