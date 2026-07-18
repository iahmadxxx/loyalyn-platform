'use client'

import {useEffect,useMemo,useState} from 'react'
import {useParams} from 'next/navigation'
import {API} from '@/lib/api'
import {AlertTriangle,Gift,Loader2,QrCode,WalletCards} from 'lucide-react'

type Row=Record<string,any>
const stampIcon=(value:string)=>({coffee:'☕',espresso:'☕',bean:'◉',cup:'🥤',cold_drink:'🧋',tea:'🍵',juice:'🧃',cake:'🍰',cookie:'🍪',donut:'🍩',croissant:'🥐',cupcake:'🧁',icecream:'🍨',chocolate:'🍫',breakfast:'🍳',burger:'🍔',pizza:'🍕',sandwich:'🥪',salad:'🥗',star:'★',heart:'♥',gift:'🎁',crown:'♛',sparkle:'✦',custom:'●'} as Record<string,string>)[value]||'●'

function designFields(design:Row){
  return {
    show_member_name:true,show_qr:true,show_reward_line:true,show_rewards:true,show_stamps:true,
    background_mode:'solid',gradient_start:design.background_color||'#111827',gradient_end:design.background_color||'#111827',
    image_fit:'cover',image_position:'center',stamp_display_mode:'program',max_front_programs:2,card_corner_style:'rounded',
    ...(design.fields||{}),
  }
}

function cardStyle(design:Row,fields:Row){
  const overlay=Math.max(0,Math.min(90,Number(design.overlay_opacity||0)))/100
  const background=design.background_image_url
  const gradient=`linear-gradient(135deg,${fields.gradient_start||design.background_color},${fields.gradient_end||design.background_color})`
  const style:React.CSSProperties={
    backgroundColor:design.background_color,color:design.foreground_color,
    backgroundPosition:fields.image_position||'center',backgroundSize:fields.image_fit||'cover',backgroundRepeat:'no-repeat',
  }
  if(fields.background_mode==='gradient')style.backgroundImage=gradient
  if(background&&fields.background_mode==='image')style.backgroundImage=`linear-gradient(rgba(0,0,0,${overlay}),rgba(0,0,0,${overlay})),url(${background})`
  if(background&&fields.background_mode==='image_gradient')style.backgroundImage=`linear-gradient(135deg,${fields.gradient_start}99,${fields.gradient_end}99),linear-gradient(rgba(0,0,0,${overlay}),rgba(0,0,0,${overlay})),url(${background})`
  return style
}

function ProgramProgress({program,globalMode,labelColor}:any){
  const settings=program.settings||{}
  const current=Math.max(0,Number(program.stamps||0)),total=Math.max(1,Number(program.required_stamps||1))
  const mode=globalMode==='program'?(settings.display_mode||'icons_count'):globalMode==='count'?'count_only':globalMode==='icons'?'icons_only':settings.display_mode||'icons_count'
  const visible=Math.min(total,10),filled=Math.min(current,visible),shape=settings.stamp_shape||'circle',size=settings.icon_size||'medium'
  const emptyImage=program.empty_stamp_asset_url||program.empty_stamp_image_url
  const filledImage=program.filled_stamp_asset_url||program.filled_stamp_image_url
  return <div className="wallet-program-row public-program-row">
    <div className="wallet-program-title"><span>{stampIcon(program.stamp_icon)}</span><div><small style={{color:labelColor}}>{program.name}</small><b>{current} / {total}</b>{settings.show_reward_title!==false&&<em>{program.rewards_available?`${program.rewards_available} مكافأة جاهزة`:program.reward_title||''}</em>}</div></div>
    {mode==='progress'?<div className="stamp-progress"><i style={{width:`${Math.min(100,(current/total)*100)}%`,background:program.accent_color}}/></div>:mode!=='count_only'&&<div className={`wallet-stamp-dots stamp-size-${size}`} aria-label={`${current} من ${total}`}>{Array.from({length:visible}).map((_,index)=>{const done=index<filled,img=done?filledImage:emptyImage;return <i key={index} className={`stamp-shape-${shape} ${done?'filled':'empty'} ${settings[done?'filled_style':'empty_style']||''}`} style={{borderColor:program.accent_color,backgroundColor:done&&!img?program.accent_color:'transparent',color:done?'#07100a':program.accent_color}}>{img?<img src={img} alt=""/>:stampIcon(program.stamp_icon)}</i>})}</div>}
  </div>
}

export default function PublicCard(){
  const params=useParams<{token:string}>()
  const [data,setData]=useState<any>(null)
  const [error,setError]=useState('')
  const [isIOS,setIsIOS]=useState(false)
  useEffect(()=>{setIsIOS(/iPad|iPhone|iPod/.test(navigator.userAgent)||((navigator as any).platform==='MacIntel'&&(navigator as any).maxTouchPoints>1))},[])
  useEffect(()=>{fetch(`${API}/api/wallet/public/card/${params.token}`,{cache:'no-store'}).then(async response=>{const body=await response.json();if(!response.ok)throw new Error(body.detail||'البطاقة غير موجودة');setData(body)}).catch(e=>setError(e.message))},[params.token])
  const computed=useMemo(()=>{
    if(!data)return null
    const design=data.design||{},fields=designFields(design),programs=Array.isArray(data.stamp_cards)?data.stamp_cards:[]
    const maxPrograms=Math.max(1,Math.min(3,Number(fields.max_front_programs||2)))
    return {design,fields,programs,frontPrograms:programs.filter((x:Row)=>x.settings?.show_on_wallet_front!==false).slice(0,maxPrograms),style:cardStyle(design,fields)}
  },[data])
  if(error)return <main className="public-card-page grid-bg"><div className="warning-box"><h1>تعذر فتح البطاقة</h1><p>{error}</p></div></main>
  if(!data||!computed)return <main className="public-card-page grid-bg"><Loader2 className="animate-spin"/></main>

  const {design:d,fields,programs,frontPrograms,style}=computed,c=data.customer,b=data.brand
  const w=data.wallet||{ready:Boolean(data.download_url),message:'Apple Wallet غير جاهز حاليًا.',download_url:data.download_url}

  return <main className="public-card-page grid-bg"><div className="public-card-wrap">
    <div className={`wallet-preview customer-wallet-card layout-${d.layout_style||'classic'} corners-${fields.card_corner_style||'rounded'}`} style={style}>
      <div className="wallet-header"><div><small style={{color:d.label_color}}>MEMBER CARD</small><h3>{d.logo_text||b.name}</h3></div><div className="wallet-logo">{d.logo_url?<img src={d.logo_url} alt={b.name}/>:b.name[0]}</div></div>
      {d.hero_url&&<img className="wallet-hero-image" style={{objectFit:fields.image_fit||'cover',objectPosition:fields.image_position||'center'}} src={d.hero_url} alt=""/>}
      {fields.show_member_name!==false&&<div className="wallet-member-line"><div><small style={{color:d.label_color}}>{d.card_title||'بطاقة الولاء'}</small><b>{c.name}</b></div><span>{data.card_template?.name}</span></div>}
      {fields.show_stamps!==false&&frontPrograms.length?<div className="wallet-program-list">{frontPrograms.map((program:Row)=><ProgramProgress key={program.id} program={program} globalMode={fields.stamp_display_mode||'program'} labelColor={d.label_color}/>)}</div>:<div className="wallet-values">{fields.show_points&&<span><small style={{color:d.label_color}}>النقاط</small><b>{c.points}</b></span>}{fields.show_rewards&&<span><small style={{color:d.label_color}}>المكافآت</small><b>{c.rewards}</b></span>}</div>}
      <div className="wallet-footer"><span>{programs.length>frontPrograms.length?`+${programs.length-frontPrograms.length} برامج أخرى`:fields.show_tier?c.tier:''}</span>{fields.show_qr!==false&&<div className="qr-box">QR</div>}</div>
      {fields.show_reward_line!==false&&programs.some((x:Row)=>x.rewards_available>0)&&<div className="wallet-reward-line"><Gift size={16}/>لديك مكافأة جاهزة</div>}
    </div>

    {programs.length>0&&<section className="public-stamp-section"><div className="public-section-title"><div><h2>{data.card_template?.name}</h2><p>كل برنامج ختم مستقل داخل نفس بطاقة Wallet.</p></div><span>{programs.length} برامج</span></div><div className="public-stamp-list">{programs.map((x:Row)=><div key={x.id} style={{borderColor:x.accent_color}}><span>{stampIcon(x.stamp_icon)}</span><div><b>{x.name}</b><small>{x.stamps} من {x.required_stamps} · {x.reward_title||'مكافأة'}</small></div>{x.rewards_available>0&&<em><Gift size={14}/>{x.rewards_available} جاهزة</em>}</div>)}</div></section>}

    <div className="public-card-meta"><h2>{c.name}</h2><p className="muted mt-2">رقم العضوية: {c.membership_code}</p></div>
    {w.ready&&w.download_url?<div className="wallet-ready-box public-wallet-cta"><WalletCards/><div><b>جاهزة للإضافة إلى Apple Wallet</b><small>{isIOS?'اضغط الزر ثم اختر «إضافة».':'افتح الصفحة من Safari على iPhone.'}</small></div><a className="btn primary wallet-add-button" href={w.download_url}><WalletCards size={18}/>إضافة إلى Apple Wallet</a></div>:<div className="wallet-pending-box public-wallet-cta"><AlertTriangle/><div><b>Apple Wallet غير جاهز بعد</b><small>{w.message}</small></div></div>}
    <div className="member-code-note"><QrCode/><span>الباركود داخل البطاقة خاص بسكان الموظف، ولا يمثل زر إضافة Wallet.</span></div>
  </div></main>
}
