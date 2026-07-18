'use client'

import {useEffect, useMemo, useState} from 'react'
import {useParams} from 'next/navigation'
import {API} from '@/lib/api'
import {
  AlertTriangle, Check, CheckCircle2, ExternalLink, Layers3, Loader2,
  QrCode, Smartphone, WalletCards,
} from 'lucide-react'

type Row = Record<string, any>
const stampIcon=(value:string)=>({coffee:'☕',espresso:'☕',bean:'◉',cup:'🥤',cold_drink:'🧋',tea:'🍵',juice:'🧃',cake:'🍰',cookie:'🍪',donut:'🍩',croissant:'🥐',cupcake:'🧁',icecream:'🍨',chocolate:'🍫',breakfast:'🍳',burger:'🍔',pizza:'🍕',sandwich:'🥪',salad:'🥗',star:'★',heart:'♥',gift:'🎁',crown:'♛',sparkle:'✦',custom:'●'} as any)[value]||'●'

function templateFields(template:Row){
  return {background_mode:'solid',gradient_start:template.background_color||'#111827',gradient_end:template.background_color||'#111827',image_fit:'cover',image_position:'center',max_front_programs:2,card_corner_style:'rounded',...(template.fields||{})}
}

function MiniStampProgress({program,mode}:any){
  const settings=program.settings||{},total=Math.max(1,Number(program.required_stamps||1)),visible=Math.min(total,8)
  const display=mode==='program'?(settings.display_mode||'icons_count'):mode==='count'?'count_only':mode==='icons'?'icons_only':settings.display_mode||'icons_count'
  if(display==='count_only')return <small>0 / {total}</small>
  if(display==='progress')return <div className="stamp-progress mini"><i style={{width:'0%',background:program.accent_color}}/></div>
  return <div className="mini-stamp-dots">{Array.from({length:visible}).map((_,index)=><i key={index} className={`stamp-shape-${settings.stamp_shape||'circle'}`} style={{borderColor:program.accent_color,color:program.accent_color}}>{stampIcon(program.stamp_icon)}</i>)}</div>
}

function MiniCard({template,brand,selected}:any){
  const fields=templateFields(template),overlay=Math.max(0,Math.min(90,Number(template.overlay_opacity||25)))/100
  const style:any={backgroundColor:template.background_color||brand.primary_color,color:template.foreground_color||'#fff',backgroundPosition:fields.image_position||'center',backgroundSize:fields.image_fit||'cover',backgroundRepeat:'no-repeat'}
  const gradient=`linear-gradient(135deg,${fields.gradient_start},${fields.gradient_end})`
  if(fields.background_mode==='gradient')style.backgroundImage=gradient
  if(template.background_image_url&&fields.background_mode==='image')style.backgroundImage=`linear-gradient(rgba(0,0,0,${overlay}),rgba(0,0,0,${overlay})),url(${template.background_image_url})`
  if(template.background_image_url&&fields.background_mode==='image_gradient')style.backgroundImage=`linear-gradient(135deg,${fields.gradient_start}99,${fields.gradient_end}99),linear-gradient(rgba(0,0,0,${overlay}),rgba(0,0,0,${overlay})),url(${template.background_image_url})`
  const rows=(template.programs||[]).filter((x:Row)=>x.settings?.show_on_wallet_front!==false).slice(0,Math.max(1,Math.min(3,Number(fields.max_front_programs||2))))
  return <div className={`join-template-card ${selected?'selected':''} layout-${template.layout_style||'classic'} corners-${fields.card_corner_style||'rounded'}`} style={style}>
    <div className="join-template-head"><div><small style={{color:template.label_color}}>MEMBER CARD</small><b>{template.logo_text||brand.name}</b></div>{template.logo_url?<img className="join-template-logo" src={template.logo_url} alt=""/>:selected&&<span className="template-check"><Check size={16}/></span>}</div>
    {template.hero_url&&<img className="join-template-hero" src={template.hero_url} style={{objectFit:fields.image_fit||'cover',objectPosition:fields.image_position||'center'}} alt=""/>}
    <p>{template.card_title||'بطاقة الولاء'}</p>
    <div className="join-template-programs advanced">{rows.map((program:Row)=><span key={program.id}><i>{stampIcon(program.stamp_icon)}</i><div><b>{program.name}</b><MiniStampProgress program={program} mode={fields.stamp_display_mode||'program'}/></div></span>)}</div>
    {(template.programs||[]).length>rows.length&&<em>+ {(template.programs||[]).length-rows.length} برامج أخرى</em>}
  </div>
}

export default function BrandJoin(){
  const params=useParams<{slug:string}>()
  const [profile,setProfile]=useState<any>(null)
  const [selectedTemplate,setSelectedTemplate]=useState('')
  const [result,setResult]=useState<any>(null)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [isIOS,setIsIOS]=useState(false)

  useEffect(()=>{
    setIsIOS(/iPad|iPhone|iPod/.test(navigator.userAgent)||((navigator as any).platform==='MacIntel'&&(navigator as any).maxTouchPoints>1))
  },[])

  useEffect(()=>{
    fetch(`${API}/api/public/brands/${params.slug}`,{cache:'no-store'})
      .then(async response=>{
        const data=await response.json()
        if(!response.ok)throw new Error(data.detail||'صفحة التسجيل غير متاحة')
        setProfile(data)
        const templates=Array.isArray(data.card_templates)?data.card_templates:[]
        const preferred=templates.find((x:Row)=>x.id===data.default_card_template_id)?.id||templates[0]?.id||''
        setSelectedTemplate(preferred)
      })
      .catch(e=>setError(e.message))
  },[params.slug])

  async function submit(e:React.FormEvent<HTMLFormElement>){
    e.preventDefault()
    if(!selectedTemplate){setError('اختر البطاقة التي تريدها أولًا');return}
    setBusy(true);setError('')
    const fd=new FormData(e.currentTarget)
    try{
      const response=await fetch(`${API}/api/public/brands/${params.slug}/join`,{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          name:fd.get('name'),phone:fd.get('phone'),email:fd.get('email')||null,
          birthday:fd.get('birthday')||null,selected_card_template_id:selectedTemplate,
        }),
      })
      const data=await response.json()
      if(!response.ok)throw new Error(Array.isArray(data.detail)?data.detail.map((x:any)=>x.msg).join('، '):data.detail||'تعذر التسجيل')
      setResult(data)
    }catch(e:any){setError(e.message)}finally{setBusy(false)}
  }

  const wallet=useMemo(()=>result?.wallet||{
    ready:Boolean(result?.wallet_ready),status:result?.wallet_ready?'ready':'not_ready',
    message:result?.wallet_ready?'بطاقتك جاهزة للإضافة إلى Apple Wallet.':'Apple Wallet غير جاهز حاليًا.',
    card_url:result?.card_url,download_url:result?.download_url,
  },[result])

  if(error&&!profile)return <main className="join-page grid-bg"><div className="warning-box"><h1>تعذر فتح التسجيل</h1><p>{error}</p></div></main>
  if(!profile)return <main className="join-page grid-bg"><Loader2 className="animate-spin"/></main>
  const brand=profile.brand
  const templates=Array.isArray(profile.card_templates)?profile.card_templates:[]

  if(result)return <main className="join-page grid-bg"><section className="join-shell"><div className="join-success">
    <CheckCircle2/><h1>تم إنشاء عضويتك</h1>
    <p>تم ربطك ببطاقة <b>{result.card_template?.name}</b>. أضفها إلى Apple Wallet، واستخدم رمز العضوية عند الموظف.</p>
    {wallet.ready&&wallet.download_url?<div className="wallet-ready-box"><WalletCards/><div><b>بطاقتك جاهزة</b><small>{isIOS?'اضغط الزر ثم اختر «إضافة» داخل Wallet.':'افتح هذا الرابط من Safari على iPhone لإضافتها إلى Wallet.'}</small></div><a className="btn primary wallet-add-button" href={wallet.download_url}><WalletCards size={19}/>إضافة إلى Apple Wallet</a></div>:<div className="wallet-pending-box"><AlertTriangle/><div><b>Apple Wallet غير جاهز بعد</b><small>{wallet.message}</small></div>{wallet.card_url&&<a className="btn secondary" href={wallet.card_url}><ExternalLink size={17}/>فتح صفحة بطاقتي</a>}</div>}
    <div className="member-qr-block"><div className="member-qr-title"><QrCode/><div><b>رمز العضوية للموظف</b><small>يعرضه العميل عند الكاشير لإضافة ختم أو صرف مكافأة.</small></div></div><img src={`${API}/api/public/members/${result.customer.membership_code}/qr.svg`} alt="رمز العضوية للموظف"/><code>{result.customer.membership_code}</code></div>
    <div className="public-card-actions">{wallet.card_url&&<a className="btn secondary" href={wallet.card_url}><Smartphone size={18}/>عرض بطاقتي</a>}<button type="button" className="btn secondary" onClick={()=>location.reload()}>تسجيل عميل آخر</button></div>
  </div></section></main>

  return <main className="join-page grid-bg"><section className="join-shell">
    <header className="join-brand" style={{borderColor:brand.accent_color}}><div className="brand-mark large" style={{background:brand.primary_color,color:brand.accent_color}}>{brand.name[0]}</div><div><small>LOYALYN MEMBER</small><h1>{brand.name}</h1><p>{brand.join_welcome_text}</p></div></header>
    {error&&<div className="inline-error"><AlertTriangle size={18}/><span>{error}</span></div>}
    <form className="join-form" onSubmit={submit}>
      <div className="join-step-title"><span>1</span><div><b>اختر بطاقتك</b><small>بطاقة واحدة في Wallet تحتوي على برامج الأختام الموضحة داخلها.</small></div></div>
      {templates.length?<div className="join-template-grid">{templates.map((template:Row)=><label key={template.id} className="join-template-option"><input type="radio" name="card_template" value={template.id} checked={selectedTemplate===template.id} onChange={()=>setSelectedTemplate(template.id)}/><MiniCard template={template} brand={brand} selected={selectedTemplate===template.id}/><div className="join-template-description"><div><b>{template.name}</b><small>{template.description||`${template.programs?.length||0} برامج أختام`}</small></div><span><Layers3 size={15}/>{template.programs?.length||0}</span></div></label>)}</div>:<div className="wallet-pending-box"><AlertTriangle/><div><b>لا توجد بطاقة متاحة حاليًا</b><small>يجب على مدير البراند نشر بطاقة وتفعيلها للتسجيل العام.</small></div></div>}
      <div className="join-step-title"><span>2</span><div><b>أدخل بياناتك</b><small>سنستخدمها لإنشاء عضويتك وربط البطاقة برقم جوالك.</small></div></div>
      <label><span>الاسم</span><input name="name" required minLength={2} placeholder="اسم العميل" autoComplete="name"/></label>
      <label><span>رقم الجوال</span><input name="phone" required minLength={5} inputMode="tel" placeholder="مثال: 55555555" autoComplete="tel"/></label>
      <label><span>البريد الإلكتروني {brand.join_require_email?'':'(اختياري)'}</span><input name="email" type="email" required={brand.join_require_email} autoComplete="email"/></label>
      <label><span>تاريخ الميلاد (اختياري)</span><input name="birthday" type="date"/></label>
      <button className="btn primary join-submit" disabled={busy||!templates.length||!selectedTemplate}>{busy?<Loader2 className="animate-spin"/>:<WalletCards/>}<span>{busy?'جاري إنشاء العضوية...':'إنشاء عضويتي'}</span></button>
      <p className="join-privacy">بالتسجيل توافق على حفظ بيانات العضوية لدى البراند فقط.</p>
    </form>
  </section></main>
}
