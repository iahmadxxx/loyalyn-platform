'use client'
import {
  LayoutDashboard, Building2, MapPin, Users, UserCog, SlidersHorizontal,
  WalletCards, Bell, ScrollText, ShieldCheck, LogOut, Menu, X
} from 'lucide-react'
import {useState} from 'react'
import {logout} from '@/lib/api'

const baseItems = [
  ['overview','نظرة عامة',LayoutDashboard],
  ['brands','البراندات',Building2],
  ['branches','الفروع',MapPin],
  ['customers','العملاء',Users],
  ['staff','الموظفون',UserCog],
  ['loyalty','محرك الولاء',SlidersHorizontal],
  ['wallet','استوديو البطاقة',WalletCards],
  ['campaigns','الإشعارات والحملات',Bell],
  ['audit','سجل التدقيق',ScrollText],
] as const

export function Shell({children, active, onChange, role, accessRole, userName, brandName}:{
  children:React.ReactNode; active:string; onChange:(value:string)=>void;
  role:string; accessRole?:string; userName:string; brandName?:string
}) {
  const [mobileOpen,setMobileOpen]=useState(false)
  const items = role === 'platform_owner'
    ? [...baseItems, ['platform-wallet','شهادة Apple المركزية',ShieldCheck] as const]
    : accessRole === 'employee'
      ? baseItems.filter(x=>['overview','customers'].includes(x[0]))
      : accessRole === 'manager'
        ? baseItems.filter(x=>!['brands','staff'].includes(x[0]))
        : baseItems.map(x=>x[0]==='brands'?['brands','إعدادات البراند',Building2] as const:x)
  const choose=(id:string)=>{onChange(id);setMobileOpen(false)}
  return <div className="min-h-screen grid-bg md:flex">
    <button className="md:hidden fixed top-4 right-4 z-[70] icon-btn" onClick={()=>setMobileOpen(!mobileOpen)}>{mobileOpen?<X/>:<Menu/>}</button>
    {mobileOpen&&<div className="md:hidden fixed inset-0 bg-black/70 z-50" onClick={()=>setMobileOpen(false)}/>} 
    <aside className={`sidebar ${mobileOpen?'open':''}`}>
      <div>
        <div className="text-2xl font-black tracking-tight">LOYALYN<span className="text-lime-300">.</span></div>
        <p className="text-[11px] text-white/35 mt-1 tracking-[.16em]">LOYALTY OPERATING SYSTEM</p>
        <div className="user-chip mt-6"><div className="avatar">{userName?.[0]||'L'}</div><div><b>{userName}</b><small>{brandName||'إدارة المنصة'}</small></div></div>
      </div>
      <nav className="space-y-1 mt-6 flex-1 overflow-y-auto">{items.map(([id,label,Icon])=><button key={id} onClick={()=>choose(id)} className={`nav-btn ${active===id?'active':''}`}><Icon size={18}/><span>{label}</span></button>)}</nav>
      <button onClick={logout} className="nav-btn danger"><LogOut size={18}/>تسجيل الخروج</button>
    </aside>
    <main className="flex-1 min-w-0 p-4 pt-20 md:p-8">{children}</main>
  </div>
}
