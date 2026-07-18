'use client'

import {
  LayoutDashboard, Building2, MapPin, Users, UserCog, SlidersHorizontal,
  WalletCards, Bell, ScrollText, ShieldCheck, LogOut, Menu, X, Stamp,
  ScanLine, ChevronLeft
} from 'lucide-react'
import {useEffect, useMemo, useState} from 'react'
import {logout} from '@/lib/api'

type NavItem = {
  id:string
  label:string
  icon:any
  permission?:string
  capability?:string
}

const baseItems:NavItem[]=[
  {id:'overview',label:'نظرة عامة',icon:LayoutDashboard},
  {id:'brands',label:'البراندات',icon:Building2,permission:'brand.manage'},
  {id:'branches',label:'الفروع',icon:MapPin,permission:'branches.view'},
  {id:'customers',label:'العملاء',icon:Users,permission:'customers.view'},
  {id:'staff',label:'الموظفون',icon:UserCog,permission:'staff.view'},
  {id:'stamp-cards',label:'بطاقات الأختام',icon:Stamp,permission:'loyalty.manage',capability:'stamps'},
  {id:'scan',label:'السكان السريع',icon:ScanLine,permission:'fast_scan.use',capability:'fast_scan'},
  {id:'loyalty',label:'محرك الولاء',icon:SlidersHorizontal,permission:'loyalty.manage'},
  {id:'wallet',label:'استوديو البطاقة',icon:WalletCards,permission:'wallet.design',capability:'wallet'},
  {id:'campaigns',label:'الإشعارات والحملات',icon:Bell,permission:'campaigns.view',capability:'campaigns'},
  {id:'audit',label:'سجل التدقيق',icon:ScrollText,permission:'audit.view'},
]

export function Shell({children,active,onChange,role,accessRole,userName,brandName,capabilities,permissions}: {
  children:React.ReactNode
  active:string
  onChange:(value:string)=>void
  role:string
  accessRole?:string
  userName:string
  brandName?:string
  capabilities?:Record<string,boolean>
  permissions?:Record<string,boolean>
}) {
  const [mobileOpen,setMobileOpen]=useState(false)
  const caps=capabilities||{}
  const perms=permissions||{}
  const isPlatform=role==='platform_owner'
  const can=(permission?:string)=>!permission||isPlatform||perms['*']===true||perms[permission]===true

  const items=useMemo(()=>{
    let visible=baseItems.filter(item=>{
      if(!can(item.permission))return false
      if(item.capability&&caps[item.capability]===false)return false
      if(item.id==='loyalty'&&!caps.points&&!caps.cashback&&!caps.tiers&&!caps.coupons&&!caps.stamps)return false
      return true
    })
    if(isPlatform)visible=[...visible,{id:'platform-wallet',label:'شهادة Apple المركزية',icon:ShieldCheck}]
    else visible=visible.map(item=>item.id==='brands'?{...item,label:'إعدادات البراند'}:item)
    return visible
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[role,accessRole,JSON.stringify(caps),JSON.stringify(perms)])

  useEffect(()=>{setMobileOpen(false)},[active])
  useEffect(()=>{
    document.body.style.overflow=mobileOpen?'hidden':''
    return()=>{document.body.style.overflow=''}
  },[mobileOpen])
  useEffect(()=>{
    if(active!=='overview'&&!items.some(item=>item.id===active))onChange('overview')
  },[active,items,onChange])

  const choose=(id:string)=>{onChange(id);setMobileOpen(false)}
  const scanVisible=items.some(item=>item.id==='scan')

  return <div className="app-shell grid-bg">
    <header className="mobile-header">
      <button className="mobile-menu-btn" type="button" onClick={()=>setMobileOpen(true)} aria-label="فتح القائمة"><Menu/></button>
      <div className="mobile-brand"><b>LOYALYN<span>.</span></b><small>{brandName||'إدارة المنصة'}</small></div>
      {scanVisible?<button className="mobile-scan-btn" type="button" onClick={()=>choose('scan')} aria-label="السكان السريع"><ScanLine/></button>:<span className="mobile-header-spacer"/>}
    </header>

    {mobileOpen&&<button type="button" className="sidebar-overlay" aria-label="إغلاق القائمة" onClick={()=>setMobileOpen(false)}/>} 
    <aside className={`sidebar ${mobileOpen?'open':''}`}>
      <button className="sidebar-close" type="button" onClick={()=>setMobileOpen(false)} aria-label="إغلاق القائمة"><X/></button>
      <div>
        <div className="sidebar-logo">LOYALYN<span>.</span></div>
        <p className="sidebar-kicker">LOYALTY OPERATING SYSTEM</p>
        <div className="user-chip mt-6"><div className="avatar">{userName?.[0]||'L'}</div><div><b>{userName}</b><small>{brandName||'إدارة المنصة'}</small></div></div>
      </div>
      <nav className="sidebar-nav">{items.map(({id,label,icon:Icon})=><button key={id} type="button" onClick={()=>choose(id)} className={`nav-btn ${active===id?'active':''}`}><Icon size={18}/><span>{label}</span><ChevronLeft size={15} className="nav-arrow"/></button>)}</nav>
      <button type="button" onClick={()=>void logout()} className="nav-btn danger"><LogOut size={18}/><span>تسجيل الخروج</span></button>
    </aside>
    <main className="app-main">{children}</main>
  </div>
}
