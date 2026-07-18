'use client'
import {useEffect,useState} from 'react'
import {useParams} from 'next/navigation'
import {API} from '@/lib/api'
import {Loader2,WalletCards} from 'lucide-react'

export default function PublicCard(){
 const params=useParams<{token:string}>();const [data,setData]=useState<any>(null),[error,setError]=useState('')
 useEffect(()=>{fetch(`${API}/api/wallet/public/card/${params.token}`,{cache:'no-store'}).then(async r=>{const d=await r.json();if(!r.ok)throw new Error(d.detail||'البطاقة غير موجودة');setData(d)}).catch(e=>setError(e.message))},[params.token])
 if(error)return <main className="public-card-page grid-bg"><div className="warning-box"><h1>تعذر فتح البطاقة</h1><p>{error}</p></div></main>
 if(!data)return <main className="public-card-page grid-bg"><Loader2 className="animate-spin"/></main>
 const d=data.design,c=data.customer,b=data.brand
 return <main className="public-card-page grid-bg"><div className="public-card-wrap"><div className="wallet-preview" style={{background:d.background_color,color:d.foreground_color}}><div className="wallet-header"><div><small style={{color:d.label_color}}>MEMBER CARD</small><h3>{d.logo_text||b.name}</h3></div><div className="wallet-logo">{b.name[0]}</div></div><p className="wallet-title">{d.card_title}</p><div className="wallet-values"><span><small style={{color:d.label_color}}>النقاط</small><b>{c.points}</b></span><span><small style={{color:d.label_color}}>المكافآت</small><b>{c.rewards}</b></span><span><small style={{color:d.label_color}}>الأختام</small><b>{c.stamps}</b></span></div><div className="wallet-footer"><span>{c.tier}</span><div className="qr-box">QR</div></div></div><div className="public-card-meta"><h2>{c.name}</h2><p className="muted mt-2">رقم العضوية: {c.membership_code}</p></div><div className="public-card-actions"><a className="btn primary" href={data.download_url}><WalletCards size={18}/> إضافة إلى Apple Wallet</a></div></div></main>
}
