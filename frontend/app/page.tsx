import Link from 'next/link'
import { ArrowLeft, ShieldCheck, Smartphone, Layers3 } from 'lucide-react'
import { WalletPreview } from '@/components/WalletPreview'
export default function Home(){return <main className="min-h-screen grid-bg overflow-hidden">
 <header className="max-w-7xl mx-auto p-6 flex justify-between items-center"><div className="text-2xl font-black">LOYALYN<span className="text-lime-300">.</span></div><Link href="/admin" className="px-5 py-3 rounded-2xl glass">دخول الإدارة</Link></header>
 <section className="max-w-7xl mx-auto px-6 py-16 grid lg:grid-cols-2 gap-16 items-center">
  <div><span className="inline-flex px-4 py-2 rounded-full bg-lime-300/10 text-lime-300 text-sm">منصة ولاء متعددة البراندات</span><h1 className="text-5xl md:text-7xl font-black leading-[1.08] mt-6">خلّ عملاءك<br/>يرجعون أكثر.</h1><p className="text-lg text-white/55 mt-6 max-w-xl leading-8">بطاقات ولاء ذكية، إدارة عملاء وموظفين، مكافآت مرنة، وتصميم Apple Wallet قابل للتعديل من لوحة واحدة.</p><div className="flex gap-3 mt-8"><Link href="/admin" className="bg-lime-300 text-black px-6 py-4 rounded-2xl font-bold flex items-center gap-2">فتح المنصة <ArrowLeft size={18}/></Link></div>
   <div className="grid sm:grid-cols-3 gap-3 mt-12">{[[ShieldCheck,'أمان وصلاحيات'],[Smartphone,'متوافق مع الجوال'],[Layers3,'براندات غير محدودة']].map(([Icon,label]:any)=><div key={label} className="glass rounded-2xl p-4 flex items-center gap-3"><Icon size={18}/><span className="text-sm">{label}</span></div>)}</div>
  </div><WalletPreview/>
 </section>
 </main>}
