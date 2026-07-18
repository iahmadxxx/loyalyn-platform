'use client'
export function WalletPreview(){
 return <div className="relative w-full max-w-sm mx-auto rounded-[34px] overflow-hidden shadow-2xl shadow-lime-300/10 border border-white/15 bg-gradient-to-br from-[#191d24] to-[#0b0d11]">
  <div className="p-6 min-h-[430px] flex flex-col">
   <div className="flex justify-between items-start"><div><p className="text-xs text-white/45">BRUNO REWARDS</p><h3 className="text-2xl font-black mt-1">Welcome, Ahmed</h3></div><div className="w-12 h-12 rounded-2xl bg-lime-300 text-black font-black grid place-items-center">B</div></div>
   <div className="mt-12"><p className="text-sm text-white/50">Your progress</p><div className="flex justify-between items-end mt-2"><div className="text-6xl font-black">4<span className="text-white/25">/6</span></div><div className="text-left text-sm">تبقى زيارتان<br/><span className="text-lime-300">للحصول على مكافأتك</span></div></div></div>
   <div className="mt-8 grid grid-cols-6 gap-2">{[1,2,3,4,5,6].map(i=><div key={i} className={`aspect-square rounded-full border ${i<=4?'bg-lime-300 border-lime-300':'border-white/20'} grid place-items-center text-xs text-black font-bold`}>{i<=4?'✓':''}</div>)}</div>
   <div className="mt-auto rounded-3xl bg-white p-4 flex items-center justify-between text-black"><div><p className="text-xs text-black/45">MEMBER ID</p><p className="font-mono text-sm">LYN-8F2A-44C9</p></div><div className="w-20 h-20 bg-[repeating-linear-gradient(45deg,#000_0_4px,#fff_4px_8px)] rounded-lg"/></div>
  </div>
 </div>
}
