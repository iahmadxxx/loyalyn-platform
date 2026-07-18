'use client'

import {CreditCard, LogOut, Menu, ScanLine, ScrollText, Settings, Users, X} from 'lucide-react'
import {useEffect, useMemo, useState} from 'react'
import {logout} from '@/lib/api'

type Item={id:string;label:string;icon:any}

export function Shell({children,active,onChange,userName,brandName}:{
  children:React.ReactNode
  active:string
  onChange:(value:string)=>void
  role?:string
  accessRole?:string
  userName:string
  brandName?:string
  capabilities?:Record<string,boolean>
  permissions?:Record<string,boolean>
}){
  const [open,setOpen]=useState(false)
  const items=useMemo<Item[]>(()=>[
    {id:'studio',label:'استوديو البطاقات',icon:CreditCard},
    {id:'customers',label:'العملاء',icon:Users},
    {id:'scan',label:'السكان السريع',icon:ScanLine},
    {id:'operations',label:'سجل العمليات',icon:ScrollText},
    {id:'settings',label:'الإعدادات',icon:Settings},
  ],[])
  useEffect(()=>setOpen(false),[active])
  const choose=(id:string)=>{onChange(id);setOpen(false)}
  return <div className="v6-shell">
    <header className="v6-mobile-head">
      <button onClick={()=>setOpen(true)} aria-label="فتح القائمة"><Menu/></button>
      <div><b>{brandName||'LOYALYN'}</b><small>STAMP STUDIO</small></div>
      <button onClick={()=>choose('scan')} aria-label="السكان السريع"><ScanLine/></button>
    </header>
    {open&&<button className="v6-overlay" aria-label="إغلاق" onClick={()=>setOpen(false)}/>} 
    <aside className={`v6-sidebar ${open?'open':''}`}>
      <button className="v6-close" onClick={()=>setOpen(false)} aria-label="إغلاق"><X/></button>
      <div className="v6-brand"><strong>{brandName||'LOYALYN'}</strong><span>STAMP STUDIO</span></div>
      <div className="v6-user"><i>{userName?.[0]||'L'}</i><div><b>{userName}</b><small>إدارة بطاقات البراند</small></div></div>
      <nav>{items.map(({id,label,icon:Icon})=><button key={id} className={active===id?'active':''} onClick={()=>choose(id)}><Icon size={19}/><span>{label}</span></button>)}</nav>
      <button className="v6-logout" onClick={()=>void logout()}><LogOut size={19}/><span>تسجيل الخروج</span></button>
    </aside>
    <main className="v6-main">{children}</main>
    <nav className="v6-bottom">{items.slice(0,4).map(({id,label,icon:Icon})=><button key={id} className={active===id?'active':''} onClick={()=>choose(id)}><Icon/><span>{label}</span></button>)}</nav>
  </div>
}
