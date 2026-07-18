'use client'
import Link from 'next/link'
import { LayoutDashboard, ScanLine, Users, WalletCards, Settings, Building2 } from 'lucide-react'
const items = [
  ['لوحة التحكم','/admin',LayoutDashboard], ['المسح السريع','/employee',ScanLine],
  ['العملاء','/admin#customers',Users], ['البراندات','/admin#brands',Building2],
  ['تصميم البطاقة','/admin#wallet',WalletCards], ['الإعدادات','/admin#settings',Settings],
] as const
export function Shell({children}:{children:React.ReactNode}){
 return <div className="min-h-screen grid-bg md:flex">
   <aside className="hidden md:flex w-72 p-5 border-l border-white/10 flex-col gap-6 sticky top-0 h-screen">
    <div><div className="text-2xl font-black tracking-tight">LOYALYN<span className="text-lime-300">.</span></div><p className="text-xs text-white/40 mt-1">LOYALTY, BUILT TO GROW</p></div>
    <nav className="space-y-2">{items.map(([label,href,Icon])=><Link key={href} href={href} className="flex items-center gap-3 px-4 py-3 rounded-2xl text-white/65 hover:text-white hover:bg-white/5"><Icon size={18}/>{label}</Link>)}</nav>
    <div className="mt-auto glass rounded-3xl p-4"><p className="text-xs text-white/45">حالة Apple Wallet</p><div className="flex items-center gap-2 mt-2"><span className="w-2 h-2 bg-amber-400 rounded-full"/><span className="text-sm">بانتظار الشهادة</span></div></div>
   </aside>
   <main className="flex-1 p-4 md:p-8 pb-24">{children}</main>
   <nav className="md:hidden fixed bottom-0 inset-x-0 glass p-3 flex justify-around z-50">{items.slice(0,4).map(([label,href,Icon])=><Link key={href} href={href} className="flex flex-col items-center gap-1 text-[10px] text-white/65"><Icon size={20}/>{label}</Link>)}</nav>
 </div>
}
