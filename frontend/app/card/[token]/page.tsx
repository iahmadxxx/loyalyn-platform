'use client'

import {useEffect,useState} from 'react'
import {useParams} from 'next/navigation'
import {API} from '@/lib/api'
import {AlertTriangle,Gift,Loader2,QrCode,WalletCards} from 'lucide-react'

const stampIcon=(value:string)=>({coffee:'☕',cake:'🍰',cookie:'🍪',cup:'🥤',star:'★'} as any)[value]||'●'

export default function PublicCard(){
  const params=useParams<{token:string}>()
  const [data,setData]=useState<any>(null)
  const [error,setError]=useState('')
  const [isIOS,setIsIOS]=useState(false)
  useEffect(()=>{setIsIOS(/iPad|iPhone|iPod/.test(navigator.userAgent)||((navigator as any).platform==='MacIntel'&&(navigator as any).maxTouchPoints>1))},[])
  useEffect(()=>{fetch(`${API}/api/wallet/public/card/${params.token}`,{cache:'no-store'}).then(async response=>{const body=await response.json();if(!response.ok)throw new Error(body.detail||'البطاقة غير موجودة');setData(body)}).catch(e=>setError(e.message))},[params.token])
  if(error)return <main className="public-card-page grid-bg"><div className="warning-box"><h1>تعذر فتح البطاقة</h1><p>{error}</p></div></main>
  if(!data)return <main className="public-card-page grid-bg"><Loader2 className="animate-spin"/></main>

  const d=data.design,c=data.customer,b=data.brand
  const w=data.wallet||{ready:Boolean(data.download_url),message:'Apple Wallet غير جاهز حاليًا.',download_url:data.download_url}
  const programs=Array.isArray(data.stamp_cards)?data.stamp_cards:[]
  const overlay=Math.max(0,Math.min(90,Number(d.overlay_opacity||0)))/100
  const style:any={backgroundColor:d.background_color,color:d.foreground_color}
  if(d.background_image_url)style.backgroundImage=`linear-gradient(rgba(0,0,0,${overlay}),rgba(0,0,0,${overlay})),url(${d.background_image_url})`

  return <main className="public-card-page grid-bg"><div className="public-card-wrap">
    <div className={`wallet-preview customer-wallet-card layout-${d.layout_style||'classic'}`} style={style}>
      <div className="wallet-header"><div><small style={{color:d.label_color}}>MEMBER CARD</small><h3>{d.logo_text||b.name}</h3></div><div className="wallet-logo">{d.logo_url?<img src={d.logo_url} alt={b.name}/>:b.name[0]}</div></div>
      {d.hero_url&&<img className="wallet-hero-image" src={d.hero_url} alt=""/>}
      <div className="wallet-member-line"><div><small style={{color:d.label_color}}>{d.card_title||'بطاقة الولاء'}</small><b>{c.name}</b></div><span>{data.card_template?.name}</span></div>
      {programs.length?<div className="wallet-programs expanded">{programs.slice(0,3).map((x:any)=><div key={x.id}><span>{stampIcon(x.stamp_icon)}</span><div><small style={{color:d.label_color}}>{x.name}</small><b>{x.stamps} / {x.required_stamps}</b><em>{x.rewards_available?`${x.rewards_available} مكافأة جاهزة`:x.reward_title||''}</em></div></div>)}</div>:<div className="wallet-values">{d.fields?.show_points&&<span><small style={{color:d.label_color}}>النقاط</small><b>{c.points}</b></span>}{d.fields?.show_rewards&&<span><small style={{color:d.label_color}}>المكافآت</small><b>{c.rewards}</b></span>}</div>}
      <div className="wallet-footer"><span>{programs.length>3?`+${programs.length-3} برامج أخرى`:d.fields?.show_tier?c.tier:''}</span><div className="qr-box">QR</div></div>
    </div>

    {programs.length>0&&<section className="public-stamp-section"><div className="public-section-title"><div><h2>{data.card_template?.name}</h2><p>كل برنامج ختم مستقل داخل نفس بطاقة Wallet.</p></div><span>{programs.length} برامج</span></div><div className="public-stamp-list">{programs.map((x:any)=><div key={x.id} style={{borderColor:x.accent_color}}><span>{stampIcon(x.stamp_icon)}</span><div><b>{x.name}</b><small>{x.stamps} من {x.required_stamps} · {x.reward_title||'مكافأة'}</small></div>{x.rewards_available>0&&<em><Gift size={14}/>{x.rewards_available} جاهزة</em>}</div>)}</div></section>}

    <div className="public-card-meta"><h2>{c.name}</h2><p className="muted mt-2">رقم العضوية: {c.membership_code}</p></div>
    {w.ready&&w.download_url?<div className="wallet-ready-box public-wallet-cta"><WalletCards/><div><b>جاهزة للإضافة إلى Apple Wallet</b><small>{isIOS?'اضغط الزر ثم اختر «إضافة».':'افتح الصفحة من Safari على iPhone.'}</small></div><a className="btn primary wallet-add-button" href={w.download_url}><WalletCards size={18}/>إضافة إلى Apple Wallet</a></div>:<div className="wallet-pending-box public-wallet-cta"><AlertTriangle/><div><b>Apple Wallet غير جاهز بعد</b><small>{w.message}</small></div></div>}
    <div className="member-code-note"><QrCode/><span>الباركود داخل البطاقة خاص بسكان الموظف، ولا يمثل زر إضافة Wallet.</span></div>
  </div></main>
}
