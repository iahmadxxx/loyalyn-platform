'use client'
import {useEffect,useState} from 'react'
import {useParams} from 'next/navigation'
import {API} from '@/lib/api'
import {Loader2,WalletCards} from 'lucide-react'

const stampIcon=(value:string)=>({coffee:'☕',cake:'🍰',cookie:'🍪',cup:'🥤',star:'★'} as any)[value]||'●'

export default function PublicCard(){
 const params=useParams<{token:string}>();const [data,setData]=useState<any>(null),[error,setError]=useState('')
 useEffect(()=>{fetch(`${API}/api/wallet/public/card/${params.token}`,{cache:'no-store'}).then(async r=>{const d=await r.json();if(!r.ok)throw new Error(d.detail||'البطاقة غير موجودة');setData(d)}).catch(e=>setError(e.message))},[params.token])
 if(error)return <main className="public-card-page grid-bg"><div className="warning-box"><h1>تعذر فتح البطاقة</h1><p>{error}</p></div></main>
 if(!data)return <main className="public-card-page grid-bg"><Loader2 className="animate-spin"/></main>
 const d=data.design,c=data.customer,b=data.brand
 const background=d.background_image_url?`${API}/api/wallet/public/assets/${d.brand_id}/background`:''
 const overlay=Math.max(0,Math.min(90,Number(d.overlay_opacity||0)))/100
 const style:any={backgroundColor:d.background_color,color:d.foreground_color}
 if(background)style.backgroundImage=`linear-gradient(rgba(0,0,0,${overlay}),rgba(0,0,0,${overlay})),url(${background})`
 return <main className="public-card-page grid-bg"><div className="public-card-wrap"><div className={`wallet-preview layout-${d.layout_style||'classic'}`} style={style}><div className="wallet-header"><div><small style={{color:d.label_color}}>MEMBER CARD</small><h3>{d.logo_text||b.name}</h3></div><div className="wallet-logo">{b.name[0]}</div></div><p className="wallet-title">{d.card_title}</p>{data.stamp_cards?.length?<div className="wallet-programs">{data.stamp_cards.slice(0,2).map((x:any)=><div key={x.id}><span>{stampIcon(x.stamp_icon)}</span><div><small style={{color:d.label_color}}>{x.name}</small><b>{x.stamps} / {x.required_stamps}</b></div></div>)}</div>:<div className="wallet-values">{d.fields.show_points&&<span><small style={{color:d.label_color}}>النقاط</small><b>{c.points}</b></span>}{d.fields.show_rewards&&<span><small style={{color:d.label_color}}>المكافآت</small><b>{c.rewards}</b></span>}{d.fields.show_stamps&&<span><small style={{color:d.label_color}}>الأختام</small><b>{c.stamps}</b></span>}</div>}<div className="wallet-footer"><span>{d.fields.show_tier?c.tier:''}</span><div className="qr-box">QR</div></div></div>{data.stamp_cards?.length>0&&<div className="public-stamp-list">{data.stamp_cards.map((x:any)=><div key={x.id} style={{borderColor:x.accent_color}}><span>{stampIcon(x.stamp_icon)}</span><div><b>{x.name}</b><small>{x.stamps} من {x.required_stamps} · {x.rewards_available} مكافأة جاهزة</small></div></div>)}</div>}<div className="public-card-meta"><h2>{c.name}</h2><p className="muted mt-2">رقم العضوية: {c.membership_code}</p></div><div className="public-card-actions"><a className="btn primary" href={data.download_url}><WalletCards size={18}/> إضافة إلى Apple Wallet</a></div></div></main>
}
