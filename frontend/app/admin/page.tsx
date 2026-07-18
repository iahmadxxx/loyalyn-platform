
'use client'
import {useCallback, useEffect, useMemo, useRef, useState} from 'react'
import {
  Activity, Archive, Bell, Building2, Camera, CheckCircle2, Coffee, Copy, CreditCard, Eye, Gift, ImageIcon, Layers3, Loader2,
  MapPin, Pencil, Plus, QrCode, RefreshCw, RotateCcw, Save, ScanLine, Send, ShieldCheck, Sparkles, Stamp, Trash2,
  Upload, UserCog, Users, WalletCards, XCircle
} from 'lucide-react'
import {api, API} from '@/lib/api'
import {Shell} from '@/components/Shell'
import {SectionErrorBoundary} from '@/components/SectionErrorBoundary'

type Row = Record<string, any>
type BrandAccess = {id:string;name:string;slug:string;role:string;branch_id?:string|null;permissions?:Record<string,boolean>}
type Me = {id:string;name:string;email:string;role:string;brands:BrandAccess[]}
const safeArray=<T,>(value:unknown):T[]=>Array.isArray(value)?value as T[]:[]
const settledValue=<T,>(result:PromiseSettledResult<T>,fallback:T):T=>result.status==='fulfilled'?result.value:fallback
const emptyDesign={background_color:'#111827',foreground_color:'#FFFFFF',label_color:'#C6FF4A',logo_text:'LOYALYN',card_title:'بطاقة الولاء',logo_url:'',hero_url:'',background_image_url:'',strip_url:'',layout_style:'classic',overlay_opacity:25,barcode_format:'PKBarcodeFormatQR',terms:'',fields:{show_points:true,show_stamps:true,show_rewards:true,show_tier:true,show_visits:true}}
const emptyProgram={enabled:true,program_type:'hybrid',points_per_visit:10,points_per_currency:1,required_stamps:6,stamp_reward_title:'مكافأة مجانية',reward_points:100,reward_title:'مكافأة مجانية',birthday_bonus:0,referral_bonus:0,cashback_percent:0,points_expiry_days:null,daily_points_cap:null,allow_manual_adjustment:true,rules:{auto_convert_points:false,global_multiplier:1,weekday_multipliers:{},branch_multipliers:{},happy_hours:[]}}

export default function AdminPage(){
  const [me,setMe]=useState<Me|null>(null)
  const [brands,setBrands]=useState<Row[]>([])
  const [brand,setBrand]=useState('')
  const [tab,setTab]=useState('overview')
  const [data,setData]=useState<Record<string,any>>({})
  const [loading,setLoading]=useState(true)
  const [busy,setBusy]=useState('')
  const [toast,setToast]=useState<{type:'ok'|'error';text:string}|null>(null)
  const selected=useMemo(()=>safeArray<Row>(brands).find(x=>x.id===brand),[brands,brand])
  const selectedAccess=useMemo(()=>safeArray<BrandAccess>(me?.brands).find(x=>x.id===brand),[me,brand])
  const selectedCaps=selected?.capabilities||{}
  const selectedPermissions=selectedAccess?.permissions||{}

  const tell=useCallback((text:string,type:'ok'|'error'='ok')=>{setToast({text,type});window.setTimeout(()=>setToast(null),4500)},[])
  const run=useCallback(async(key:string,fn:()=>Promise<any>,success?:string)=>{
    setBusy(key)
    try{const result=await fn();if(success)tell(success);return result}
    catch(e:any){tell(e?.message||'حدث خطأ غير متوقع','error');throw e}
    finally{setBusy('')}
  },[tell])

  const loadCore=useCallback(async()=>{
    setLoading(true)
    try{
      const profile=await api<Me>('/api/auth/me')
      const brandRows=safeArray<Row>(await api<Row[]>('/api/brands'))
      setMe({...profile,brands:safeArray<BrandAccess>(profile?.brands)})
      setBrands(brandRows)
      const stored=localStorage.getItem('loyalyn_brand')
      const first=brandRows.find(x=>x.id===stored)?.id||brandRows[0]?.id||''
      setBrand(current=>brandRows.some(x=>x.id===current)?current:first)
    }catch(e:any){tell(e?.message||'تعذر تحميل حسابك','error')}
    finally{setLoading(false)}
  },[tell])

  const loadTab=useCallback(async()=>{
    if(!me)return
    if(!brand&&tab!=='brands'&&tab!=='platform-wallet'){setData({});return}
    setLoading(true)
    setData({})
    try{
      let payload:any={}
      if(tab==='overview')payload=await api(`/api/dashboard${brand?`?brand_id=${brand}`:''}`)
      if(tab==='branches')payload={branches:safeArray(await api(`/api/management/branches?brand_id=${brand}`))}
      if(tab==='customers'){
        const customers=safeArray(await api(`/api/customers?brand_id=${brand}&active_only=false`))
        const [rewardsResult,couponsResult,branchesResult,cardTemplatesResult]=await Promise.allSettled([
          selectedCaps.points&&selectedCaps.rewards&&selectedPermissions['rewards.redeem']!==false?api(`/api/management/reward-options?brand_id=${brand}`):Promise.resolve([]),
          selectedCaps.coupons&&selectedPermissions['rewards.redeem']!==false?api(`/api/management/coupon-options?brand_id=${brand}`):Promise.resolve([]),
          api(`/api/management/branch-options?brand_id=${brand}`),
          selectedCaps.stamps?api(`/api/cards/templates?brand_id=${brand}&include_archived=false`):Promise.resolve([]),
        ])
        payload={customers,rewards:safeArray(settledValue(rewardsResult,[])),coupons:safeArray(settledValue(couponsResult,[])),branches:safeArray(settledValue(branchesResult,[])),cardTemplates:safeArray(settledValue(cardTemplatesResult,[]))}
      }
      if(tab==='staff'){
        const [staffRows,branchRows]=await Promise.all([api(`/api/management/staff?brand_id=${brand}`),api(`/api/management/branches?brand_id=${brand}`)])
        payload={staff:safeArray(staffRows),branches:safeArray(branchRows)}
      }
      if(tab==='loyalty'){
        const program=await api(`/api/customers/program/${brand}`)
        const [tiersResult,rewardsResult,couponsResult,branchesResult]=await Promise.allSettled([
          selectedCaps.tiers?api(`/api/management/tiers?brand_id=${brand}`):Promise.resolve([]),
          selectedCaps.points&&selectedCaps.rewards?api(`/api/management/rewards?brand_id=${brand}`):Promise.resolve([]),
          selectedCaps.coupons?api(`/api/management/coupons?brand_id=${brand}`):Promise.resolve([]),
          api(`/api/management/branch-options?brand_id=${brand}`),
        ])
        payload={program,tiers:safeArray(settledValue(tiersResult,[])),rewards:safeArray(settledValue(rewardsResult,[])),coupons:safeArray(settledValue(couponsResult,[])),branches:safeArray(settledValue(branchesResult,[]))}
      }
      if(tab==='wallet'){
        const [design,customers,programs,cardTemplates]=await Promise.all([
          api(`/api/wallet/design/${brand}`),api(`/api/customers?brand_id=${brand}`),
          selectedCaps.stamps?api(`/api/stamps/programs?brand_id=${brand}&active_only=true`):Promise.resolve([]),
          selectedCaps.stamps?api(`/api/cards/templates?brand_id=${brand}&include_archived=false`):Promise.resolve([]),
        ])
        payload={design,customers:safeArray(customers),programs:safeArray(programs),cardTemplates:safeArray(cardTemplates)}
      }
      if(tab==='cards'){const [templates,programs]=await Promise.all([api(`/api/cards/templates?brand_id=${brand}&include_archived=true`),api(`/api/stamps/programs?brand_id=${brand}`)]);payload={templates:safeArray(templates),programs:safeArray(programs)}}
      if(tab==='stamp-cards')payload={programs:safeArray(await api(`/api/stamps/programs?brand_id=${brand}`))}
      if(tab==='scan')payload={branches:safeArray(await api(`/api/management/branch-options?brand_id=${brand}`))}
      if(tab==='campaigns'){
        const [campaigns,templates,customers,branches]=await Promise.all([
          api(`/api/notifications/campaigns?brand_id=${brand}`),api(`/api/notifications/templates?brand_id=${brand}`),
          api(`/api/customers?brand_id=${brand}&active_only=false`),api(`/api/management/branch-options?brand_id=${brand}`),
        ])
        payload={campaigns:safeArray(campaigns),templates:safeArray(templates),customers:safeArray(customers),branches:safeArray(branches)}
      }
      if(tab==='audit')payload={audit:safeArray(await api(`/api/management/audit?brand_id=${brand}`))}
      if(tab==='platform-wallet')payload={credential:await api('/api/wallet/platform/credential')}
      setData(payload&&typeof payload==='object'?payload:{})
    }catch(e:any){setData({});tell(e?.message||'تعذر تحميل هذا القسم','error')}
    finally{setLoading(false)}
  },[tab,brand,me,selectedCaps.points,selectedCaps.rewards,selectedCaps.coupons,selectedCaps.tiers,selectedCaps.stamps,selectedPermissions,tell])

  useEffect(()=>{void loadCore()},[loadCore])
  useEffect(()=>{if(me)void loadTab()},[me,loadTab])
  useEffect(()=>{if(brand)localStorage.setItem('loyalyn_brand',brand)},[brand])

  async function submitJson(path:string,e:React.FormEvent<HTMLFormElement>,extra:Row={},method='POST',success='تم الحفظ بنجاح'){
    e.preventDefault();const form=e.currentTarget;const fd=new FormData(form);const body:Row={...extra}
    fd.forEach((value,key)=>{if(value==='')body[key]=null;else if(value==='on')body[key]=true;else body[key]=value})
    await run(path,()=>api(path,{method,body:JSON.stringify(body)}),success);form.reset();await loadTab()
  }

  async function createBrand(e:React.FormEvent<HTMLFormElement>){
    e.preventDefault();const form=e.currentTarget;const fd=new FormData(form)
    const body={name:fd.get('name'),slug:String(fd.get('slug')||'').toLowerCase().trim(),primary_color:fd.get('primary_color'),accent_color:fd.get('accent_color'),currency:fd.get('currency'),timezone:'Asia/Qatar',locale:'ar',program_mode:fd.get('program_mode')||'full',feature_flags:{},join_enabled:true,join_require_email:false,manager_name:fd.get('manager_name')||null,manager_email:fd.get('manager_email')||null,manager_password:fd.get('manager_password')||null}
    const result=await run('brand-create',()=>api('/api/brands',{method:'POST',body:JSON.stringify(body)}))
    if(result?.manager?.temporary_password)tell(`تم إنشاء البراند. كلمة المرور المؤقتة للمدير: ${result.manager.temporary_password}`)
    else tell('تم إنشاء البراند وربط مديره')
    form.reset();await loadCore();if(result?.brand?.id)setBrand(result.brand.id)
  }

  async function loyaltyAction(customer:Row,action:'visit'|'spend'|'manual'){
    let amount=0,points=0,stamps=0,note=''
    if(action==='spend'){const value=prompt('أدخل قيمة الفاتورة');if(value===null)return;amount=Number(value);if(!Number.isFinite(amount)||amount<0)return tell('قيمة الفاتورة غير صحيحة','error')}
    if(action==='manual'){const p=prompt('عدد النقاط (يمكن استخدام رقم سالب للخصم)','0');if(p===null)return;const s=prompt('عدد الأختام (يمكن استخدام رقم سالب للخصم)','0');if(s===null)return;points=Number(p);stamps=Number(s);note=prompt('سبب التعديل')||''}
    await run(`loyalty-${customer.id}`,()=>api(`/api/customers/${customer.id}/loyalty`,{method:'POST',body:JSON.stringify({action,amount,points,stamps,note,idempotency_key:crypto.randomUUID()})}),'تم تحديث رصيد العميل')
    await loadTab()
  }

  async function issuePass(customer:Row){
    const result=await run(`pass-${customer.id}`,()=>api(`/api/wallet/passes/${customer.id}`,{method:'POST'}),'تم إصدار بطاقة Apple Wallet')
    if(result?.download_url){await navigator.clipboard.writeText(result.download_url);tell('تم إصدار البطاقة ونسخ رابط الإضافة')}
  }

  if(!me)return <main className="min-h-screen grid place-items-center"><Loader2 className="animate-spin"/></main>
  return <Shell active={tab} onChange={setTab} role={me.role} accessRole={selectedAccess?.role} userName={me.name} brandName={selected?.name} capabilities={selectedCaps} permissions={selectedPermissions}>
    <div className="admin-container">
      <Topbar title={tab==='brands'&&me.role!=='platform_owner'?'إعدادات البراند':titles[tab]||'لوحة التحكم'} subtitle={tab==='brands'&&me.role!=='platform_owner'?'تعديل هوية وإعدادات البراندات المصرح لك بها فقط.':subtitles[tab]||''} brands={safeArray(brands)} brand={brand} setBrand={setBrand} showBrand={tab!=='brands'&&tab!=='platform-wallet'} reload={loadTab}/>
      {toast&&<Toast {...toast} onClose={()=>setToast(null)}/>} 
      {loading&&<div className="loading-strip"><Loader2 className="animate-spin" size={17}/><span>جاري تحميل البيانات…</span></div>}
      <SectionErrorBoundary key={`${brand}-${tab}`} onRetry={loadTab}>
        {tab==='overview'&&<Overview data={data} setTab={setTab} capabilities={selectedCaps}/>} 
        {tab==='brands'&&(me.role==='platform_owner'?<Brands brands={safeArray(brands)} onSubmit={createBrand} busy={busy} reload={loadCore} run={run}/>:<BrandSettings brand={selected} busy={busy} run={run} reload={loadCore}/>)} 
        {tab==='branches'&&<Branches rows={safeArray(data.branches)} brand={brand} submit={submitJson} busy={busy} run={run} reload={loadTab}/>} 
        {tab==='customers'&&<Customers rows={safeArray(data.customers)} rewards={safeArray(data.rewards)} coupons={safeArray(data.coupons)} branches={safeArray(data.branches)} cardTemplates={safeArray(data.cardTemplates)} brand={brand} submit={submitJson} busy={busy} loyaltyAction={loyaltyAction} issuePass={issuePass} run={run} reload={loadTab} capabilities={selectedCaps} permissions={selectedPermissions} setTab={setTab}/>} 
        {tab==='staff'&&<Staff rows={safeArray(data.staff)} branches={safeArray(data.branches)} brand={brand} busy={busy} run={run} reload={loadTab} permissions={selectedPermissions}/>} 
        {tab==='cards'&&<CardTemplates rows={safeArray(data.templates)} programs={safeArray(data.programs)} brand={brand} brandInfo={selected} busy={busy} run={run} reload={loadTab}/>} 
        {tab==='stamp-cards'&&<StampCards rows={safeArray(data.programs)} brand={brand} brandInfo={selected} busy={busy} run={run} reload={loadTab}/>} 
        {tab==='scan'&&<FastScan brand={brand} branches={safeArray(data.branches)} busy={busy} run={run} permissions={selectedPermissions}/>} 
        {tab==='loyalty'&&<Loyalty program={data.program||emptyProgram} tiers={safeArray(data.tiers)} rewards={safeArray(data.rewards)} coupons={safeArray(data.coupons)} branches={safeArray(data.branches)} brand={brand} busy={busy} run={run} reload={loadTab} submit={submitJson} capabilities={selectedCaps}/>} 
        {tab==='wallet'&&<WalletStudio design={data.design||emptyDesign} customers={safeArray(data.customers)} programs={safeArray(data.programs)} cardTemplates={safeArray(data.cardTemplates)} brand={brand} brandInfo={selected} busy={busy} run={run} reload={loadTab} issuePass={issuePass}/>} 
        {tab==='campaigns'&&<Campaigns rows={safeArray(data.campaigns)} templates={safeArray(data.templates)} customers={safeArray(data.customers)} branches={safeArray(data.branches)} brand={brand} busy={busy} run={run} reload={loadTab} capabilities={selectedCaps}/>} 
        {tab==='audit'&&<Audit rows={safeArray(data.audit)}/>} 
        {tab==='platform-wallet'&&me.role==='platform_owner'&&<PlatformWallet credential={data.credential} busy={busy} run={run} reload={loadTab}/>} 
      </SectionErrorBoundary>
    </div>
  </Shell>
}

const titles:Row={overview:'مركز التحكم',brands:'إدارة البراندات',branches:'الفروع',customers:'العملاء',staff:'الموظفون والصلاحيات',cards:'البطاقات','stamp-cards':'برامج الأختام',scan:'السكان السريع',loyalty:'محرك الولاء',wallet:'استوديو Apple Wallet',campaigns:'الإشعارات والحملات',audit:'سجل التدقيق','platform-wallet':'شهادة Apple Wallet المركزية'}
const subtitles:Row={overview:'متابعة المنصة والعمليات من مكان واحد.',brands:'أنشئ البراند وحدد نوع البرنامج والمميزات لكل حساب.',branches:'إدارة الفروع وبياناتها التشغيلية.',customers:'تسجيل العملاء وتحديث الولاء وإصدار البطاقات.',staff:'حساب مستقل لكل مدير أو موظف وصلاحيات معزولة.',cards:'أنشئ أكثر من قالب بطاقة، واختر برامج الأختام والتصميم لكل بطاقة.','stamp-cards':'أنشئ مسميات الأختام مثل القهوة والحلى وعدّلها أو أرشفها بدون فقدان السجل.',scan:'امسح رمز العميل واختر البطاقة ثم أضف الختم مباشرة.',loyalty:'قواعد النقاط والمستويات والمكافآت حسب نوع البراند.',wallet:'مدير البراند يصمم؛ مدير المنصة يحتفظ بالشهادة.',campaigns:'حملات فورية أو مجدولة مع حالة إرسال حقيقية.',audit:'كل تعديل مهم محفوظ وقابل للمراجعة.','platform-wallet':'لا يظهر هذا القسم إلا لمدير المنصة.'}

function Topbar({title,subtitle,brands,brand,setBrand,showBrand,reload}:any){const rows=safeArray<Row>(brands);return <header className="topbar"><div><p className="eyebrow">LOYALYN CONTROL CENTER · V5</p><h1>{title}</h1><p className="muted mt-2">{subtitle}</p></div><div className="top-actions">{showBrand&&<select className="input brand-select" value={brand} onChange={e=>setBrand(e.target.value)} aria-label="اختيار البراند">{rows.map((x:Row)=><option key={x.id} value={x.id}>{x.name}</option>)}</select>}<button type="button" className="icon-btn" onClick={reload} title="تحديث" aria-label="تحديث القسم"><RefreshCw size={18}/></button></div></header>}
function Toast({type,text,onClose}:any){return <div className={`toast ${type}`}><span>{type==='ok'?<CheckCircle2/>:<XCircle/>}</span><b>{text}</b><button type="button" onClick={onClose}>×</button></div>}
function Panel({title,desc,action,children,className=''}:any){return <section className={`panel ${className}`}><div className="panel-head"><div><h2>{title}</h2>{desc&&<p>{desc}</p>}</div>{action}</div><div className="panel-body">{children}</div></section>}
function Empty({text='لا توجد بيانات بعد'}:{text?:string}){return <div className="empty-state"><Sparkles/><p>{text}</p></div>}
function Btn({busy,label,icon:Icon=Save,variant='primary',...props}:any){const type=props.type||(props.onClick?'button':'submit');return <button {...props} type={type} disabled={busy||props.disabled} className={`btn ${variant}`}>{busy?<Loader2 size={17} className="animate-spin"/>:<Icon size={17}/>}<span>{label}</span></button>}
function Field({label,name,type='text',defaultValue,required=true,placeholder,children,...props}:any){return <label className="field"><span>{label}</span>{children||<input className="input" name={name} type={type} defaultValue={defaultValue} required={required} placeholder={placeholder} {...props}/>}</label>}
function Switch({label,name,defaultChecked}:any){return <label className="switch-row"><input type="checkbox" name={name} defaultChecked={defaultChecked}/><span>{label}</span></label>}
function Modal({title,desc,onClose,children}:any){return <div className="modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)onClose()}}><section className="modal-card"><div className="modal-head"><div><h2>{title}</h2>{desc&&<p>{desc}</p>}</div><button type="button" className="icon-btn" onClick={onClose} aria-label="إغلاق"><XCircle size={19}/></button></div><div className="modal-body">{children}</div></section></div>}

function Overview({data,setTab,capabilities}:any){
  const caps=capabilities||{}
  const cards:any[]=[
    [data.customers||0,'العملاء',Users,true],
    [data.new_customers_30d||0,'جدد خلال 30 يوم',Sparkles,true],
    [data.transactions||0,'عمليات الولاء',Activity,true],
    [data.stamps_issued||0,'أختام صادرة',Stamp,!!caps.stamps],
    [data.stamp_rewards_redeemed||0,'مكافآت أختام مصروفة',Gift,!!caps.stamps],
    [data.wallet_passes||0,'بطاقات Wallet',WalletCards,caps.wallet!==false],
    [data.points_issued||0,'نقاط صادرة',Gift,!!caps.points],
    [data.campaigns||0,'الحملات',Bell,caps.campaigns!==false],
    [data.branches||0,'الفروع',MapPin,true],
    [data.staff||0,'الموظفون',UserCog,true],
  ]
  const quick:any[]=[
    ['customers','تسجيل عميل',Users,true],
    ['scan','إضافة ختم سريع',ScanLine,!!caps.fast_scan],
    ['stamp-cards','إدارة بطاقات الأختام',Stamp,!!caps.stamps],
    ['loyalty','ضبط برنامج الولاء',Gift,!!(caps.points||caps.cashback||caps.tiers||caps.coupons)],
    ['wallet','تصميم البطاقة',WalletCards,caps.wallet!==false],
    ['campaigns','إنشاء حملة',Bell,caps.campaigns!==false],
  ]
  return <>
    <div className="kpi-grid">{cards.filter(x=>x[3]).map(([value,label,Icon]:any)=><div className="kpi-card" key={label}><div className="kpi-icon"><Icon/></div><div><strong>{Number(value).toLocaleString('ar')}</strong><span>{label}</span></div></div>)}</div>
    <div className="content-grid mt-5">
      <Panel title="إجراءات سريعة" desc="تتغير تلقائيًا حسب نوع برنامج البراند"><div className="quick-grid">{quick.filter(x=>x[3]).map(([id,label,Icon]:any)=><button type="button" className="quick-card" key={id} onClick={()=>setTab(id)}><Icon/><b>{label}</b><span>فتح القسم</span></button>)}</div></Panel>
      <Panel title="آخر العمليات" desc="النقاط والأختام تظهر في سجل واحد حسب المميزات المفعلة">{data.recent_activity?.length?<div className="activity-list">{data.recent_activity.map((x:Row)=><div key={`${x.source||'loyalty'}-${x.id}`}><span className="dot-live"/><div><b>{x.label||actionName(x.action)}</b><small>{new Date(x.created_at).toLocaleString('ar-QA')}</small></div><em>{x.delta_points?`${x.delta_points>=0?'+':''}${x.delta_points} نقطة`:''}{x.delta_points&&x.delta_stamps?' · ':''}{x.delta_stamps?`${x.delta_stamps>=0?'+':''}${x.delta_stamps} ختم`:''}{x.delta_rewards?` · ${x.delta_rewards>=0?'+':''}${x.delta_rewards} مكافأة`:''}</em></div>)}</div>:<Empty/>}</Panel>
    </div>
  </>
}

function Brands({brands,onSubmit,busy,reload,run}:any){
  const [editing,setEditing]=useState<Row|null>(null)
  async function toggle(x:Row){await run(`brand-${x.id}`,()=>api(`/api/brands/${x.id}`,{method:'PATCH',body:JSON.stringify({is_active:!x.is_active})}),x.is_active?'تم إيقاف البراند':'تم تفعيل البراند');await reload()}
  async function update(e:React.FormEvent<HTMLFormElement>){e.preventDefault();if(!editing)return;const fd=new FormData(e.currentTarget);await run(`edit-brand-${editing.id}`,()=>api(`/api/brands/${editing.id}`,{method:'PATCH',body:JSON.stringify({name:fd.get('name'),primary_color:fd.get('primary_color'),accent_color:fd.get('accent_color'),currency:fd.get('currency'),timezone:fd.get('timezone'),locale:fd.get('locale')})}),'تم تحديث البراند');setEditing(null);await reload()}
  return <div className="content-grid mt-6">
    <Panel title="إنشاء براند ومديره" desc="ينشأ البراند وإعدادات الولاء والتصميم الافتراضي وحساب المدير في عملية واحدة"><form className="form-grid" onSubmit={onSubmit}><Field label="اسم البراند" name="name"/><Field label="الرابط المختصر" name="slug" placeholder="coffee-house" pattern="[a-z0-9-]+"/><div className="two-col"><Field label="اللون الأساسي" name="primary_color" type="color" defaultValue="#111827"/><Field label="اللون المميز" name="accent_color" type="color" defaultValue="#C6FF4A"/></div><Field label="العملة" name="currency" defaultValue="QAR"/><Field label="نوع برنامج البراند"><select className="input" name="program_mode" defaultValue="full"><option value="stamps_only">أختام فقط</option><option value="points_only">نقاط فقط</option><option value="stamps_points">أختام ونقاط</option><option value="full">نظام متكامل</option><option value="custom">إعداد مخصص</option></select></Field><div className="form-divider">حساب مدير البراند</div><Field label="اسم المدير" name="manager_name" required={false}/><Field label="بريد المدير" name="manager_email" type="email" required={false}/><Field label="كلمة مرور المدير" name="manager_password" type="password" required={false} minLength={8}/><Btn busy={busy==='brand-create'} label="إنشاء وربط البراند" icon={Plus}/></form></Panel>
    <Panel title="كل البراندات" desc={`${brands.length} براند داخل المنصة`}>{brands.length?<div className="card-list">{brands.map((x:Row)=><div className="entity-card" key={x.id}><div className="brand-mark" style={{background:x.primary_color,color:x.accent_color}}>{x.name[0]}</div><div className="entity-main"><b>{x.name}</b><small>{x.slug} · {x.currency} · {x.timezone}</small></div><span className={`badge ${x.is_active?'success':'muted-badge'}`}>{x.is_active?'فعال':'موقوف'}</span><div className="button-row"><Btn label="تعديل" icon={Pencil} variant="secondary" onClick={()=>setEditing(x)}/><Btn busy={busy===`brand-${x.id}`} label={x.is_active?'إيقاف':'تفعيل'} icon={x.is_active?XCircle:CheckCircle2} variant="secondary" onClick={()=>toggle(x)}/></div></div>)}</div>:<Empty/>}</Panel>
    {editing&&<Modal title="تعديل البراند" desc="الهوية ونوع البرنامج يحفظان بدون حذف أي بيانات قديمة" onClose={()=>setEditing(null)}><form className="form-grid" onSubmit={update}><Field label="اسم البراند" name="name" defaultValue={editing.name}/><div className="two-col"><Field label="اللون الأساسي" name="primary_color" type="color" defaultValue={editing.primary_color}/><Field label="اللون المميز" name="accent_color" type="color" defaultValue={editing.accent_color}/></div><Field label="العملة" name="currency" defaultValue={editing.currency}/><Field label="المنطقة الزمنية" name="timezone" defaultValue={editing.timezone||'Asia/Qatar'}/><Field label="اللغة" name="locale" defaultValue={editing.locale||'ar'}/><Btn busy={busy===`edit-brand-${editing.id}`} label="حفظ الهوية"/></form><div className="form-divider">نوع البرنامج والمميزات</div><ProgramProfileEditor brand={editing} busy={busy} run={run} onSaved={async()=>{await reload();setEditing(null)}}/></Modal>}
  </div>
}

function BrandSettings({brand,busy,run,reload}:any){
  async function save(e:React.FormEvent<HTMLFormElement>){e.preventDefault();if(!brand)return;const fd=new FormData(e.currentTarget);await run(`brand-settings-${brand.id}`,()=>api(`/api/brands/${brand.id}`,{method:'PATCH',body:JSON.stringify({name:fd.get('name'),primary_color:fd.get('primary_color'),accent_color:fd.get('accent_color'),currency:fd.get('currency'),timezone:fd.get('timezone'),locale:fd.get('locale')})}),'تم حفظ إعدادات البراند');await reload()}
  if(!brand)return <Panel title="إعدادات البراند" className="mt-6"><Empty text="اختر براندًا أولًا"/></Panel>
  return <><div className="content-grid mt-6"><Panel title="هوية وإعدادات البراند" desc="هذه التغييرات تخص البراند المحدد فقط"><form className="form-grid" onSubmit={save}><Field label="اسم البراند" name="name" defaultValue={brand.name}/><div className="two-col"><Field label="اللون الأساسي" name="primary_color" type="color" defaultValue={brand.primary_color}/><Field label="اللون المميز" name="accent_color" type="color" defaultValue={brand.accent_color}/></div><Field label="العملة" name="currency" defaultValue={brand.currency}/><Field label="المنطقة الزمنية" name="timezone" defaultValue={brand.timezone||'Asia/Qatar'}/><Field label="اللغة" name="locale" defaultValue={brand.locale||'ar'}/><Btn busy={busy===`brand-settings-${brand.id}`} label="حفظ إعدادات البراند"/></form></Panel><Panel title="العزل والصلاحيات"><div className="rule-summary"><Rule icon={ShieldCheck} title="بيانات معزولة" text="كل عميل وموظف وعملية مرتبطة بهذا البراند"/><Rule icon={UserCog} title="مديرو البراند" text="يرون البراندات المصرح لهم بها فقط"/><Rule icon={WalletCards} title="Wallet مركزي" text="تصمم البطاقة دون الوصول إلى شهادة Apple"/><Rule icon={Bell} title="حملات مستقلة" text="الجمهور والسجل خاصان بهذا البراند"/></div></Panel></div><Panel title="نوع البرنامج والمميزات" desc="يمكن تغيير النوع مستقبلًا؛ تعطيل أي ميزة يخفيها ولا يحذف بياناتها" className="mt-5"><ProgramProfileEditor brand={brand} busy={busy} run={run} onSaved={reload}/></Panel></>
}


const modeDefaults:Row={
  stamps_only:{stamps:true,multi_stamp_cards:true,fast_scan:true,points:false,cashback:false,tiers:false,rewards:true,coupons:false,wallet:true,campaigns:true},
  points_only:{stamps:false,multi_stamp_cards:false,fast_scan:true,points:true,cashback:false,tiers:true,rewards:true,coupons:true,wallet:true,campaigns:true},
  stamps_points:{stamps:true,multi_stamp_cards:true,fast_scan:true,points:true,cashback:false,tiers:true,rewards:true,coupons:true,wallet:true,campaigns:true},
  full:{stamps:true,multi_stamp_cards:true,fast_scan:true,points:true,cashback:true,tiers:true,rewards:true,coupons:true,wallet:true,campaigns:true},
  custom:{stamps:true,multi_stamp_cards:true,fast_scan:true,points:true,cashback:false,tiers:true,rewards:true,coupons:true,wallet:true,campaigns:true},
}
const featureLabels:Row={stamps:'بطاقات الأختام',multi_stamp_cards:'أكثر من بطاقة أختام',fast_scan:'السكان السريع',points:'النقاط',cashback:'Cashback',tiers:'مستويات العضوية',rewards:'المكافآت',coupons:'الكوبونات',wallet:'Apple Wallet',campaigns:'الإشعارات والحملات'}
function ProgramProfileEditor({brand,busy,run,onSaved}:any){
  const [mode,setMode]=useState(brand.program_mode||'full')
  const [flags,setFlags]=useState<Row>({...modeDefaults[brand.program_mode||'full'],...(brand.feature_flags||{})})
  const [joinEnabled,setJoinEnabled]=useState(brand.join_enabled!==false)
  const [requireEmail,setRequireEmail]=useState(!!brand.join_require_email)
  const [welcome,setWelcome]=useState(brand.join_welcome_text||'')
  useEffect(()=>{const next=brand.program_mode||'full';setMode(next);setFlags({...modeDefaults[next],...(brand.feature_flags||{})});setJoinEnabled(brand.join_enabled!==false);setRequireEmail(!!brand.join_require_email);setWelcome(brand.join_welcome_text||'')},[brand])
  function changeMode(value:string){setMode(value);setFlags({...modeDefaults[value]})}
  function toggle(key:string,value:boolean){setFlags((current:Row)=>({...current,[key]:value,...(key==='stamps'&&!value?{multi_stamp_cards:false}:{} )}))}
  async function save(){await run(`profile-${brand.id}`,()=>api(`/api/brands/${brand.id}/program-profile`,{method:'PATCH',body:JSON.stringify({program_mode:mode,feature_flags:flags,join_enabled:joinEnabled,join_require_email:requireEmail,join_welcome_text:welcome||null})}),'تم حفظ نوع البرنامج والمميزات بدون حذف البيانات');await onSaved()}
  return <div className="form-grid"><Field label="نوع البرنامج"><select className="input" value={mode} onChange={e=>changeMode(e.target.value)}><option value="stamps_only">أختام فقط</option><option value="points_only">نقاط فقط</option><option value="stamps_points">أختام ونقاط</option><option value="full">نظام متكامل</option><option value="custom">إعداد مخصص</option></select></Field><div className="feature-grid">{Object.entries(featureLabels).map(([key,label])=><label className={`feature-toggle ${flags[key]?'on':''}`} key={key}><input type="checkbox" checked={!!flags[key]} onChange={e=>toggle(key,e.target.checked)}/><span><b>{label as string}</b><small>{flags[key]?'مفعلة لهذا البراند':'مخفية ومتوقفة'}</small></span></label>)}</div><div className="form-divider">تسجيل العميل العام</div><label className="switch-row"><input type="checkbox" checked={joinEnabled} onChange={e=>setJoinEnabled(e.target.checked)}/><span>تفعيل رابط وQR التسجيل العام</span></label><label className="switch-row"><input type="checkbox" checked={requireEmail} onChange={e=>setRequireEmail(e.target.checked)}/><span>طلب البريد الإلكتروني من العميل</span></label><Field label="رسالة الترحيب" required={false}><textarea className="input min-h-20" value={welcome} onChange={e=>setWelcome(e.target.value)} placeholder="سجّل بياناتك وأضف بطاقتك بسهولة"/></Field><Btn busy={busy===`profile-${brand.id}`} label="حفظ نوع البرنامج" icon={Save} onClick={save}/></div>
}

function Branches({rows,brand,submit,busy,run,reload}:any){
  const [editing,setEditing]=useState<Row|null>(null)
  async function toggle(x:Row){await run(`branch-${x.id}`,()=>api(`/api/management/branches/${x.id}`,{method:'PATCH',body:JSON.stringify({is_active:!x.is_active})}),x.is_active?'تم إيقاف الفرع':'تم تفعيل الفرع');await reload()}
  async function update(e:React.FormEvent<HTMLFormElement>){e.preventDefault();if(!editing)return;const fd=new FormData(e.currentTarget);await run(`edit-branch-${editing.id}`,()=>api(`/api/management/branches/${editing.id}`,{method:'PATCH',body:JSON.stringify({name:fd.get('name'),phone:fd.get('phone')||null,manager_name:fd.get('manager_name')||null,address:fd.get('address')||null,latitude:fd.get('latitude')||null,longitude:fd.get('longitude')||null})}),'تم تحديث الفرع');setEditing(null);await reload()}
  return <div className="content-grid mt-6"><Panel title="إضافة فرع"><form className="form-grid" onSubmit={(e)=>submit('/api/management/branches',e,{brand_id:brand},'POST','تم إنشاء الفرع')}><Field label="اسم الفرع" name="name"/><Field label="الهاتف" name="phone" required={false}/><Field label="مدير الفرع" name="manager_name" required={false}/><Field label="العنوان" name="address" required={false}/><div className="two-col"><Field label="خط العرض" name="latitude" required={false}/><Field label="خط الطول" name="longitude" required={false}/></div><Btn busy={busy==='/api/management/branches'} label="إضافة الفرع" icon={Plus}/></form></Panel><Panel title="الفروع الحالية">{rows.length?<div className="card-list">{rows.map((x:Row)=><div className="entity-card" key={x.id}><div className="entity-icon"><MapPin/></div><div className="entity-main"><b>{x.name}</b><small>{x.address||'بدون عنوان'}{x.phone?` · ${x.phone}`:''}{x.manager_name?` · المدير: ${x.manager_name}`:''}</small></div><span className={`badge ${x.is_active?'success':'muted-badge'}`}>{x.is_active?'فعال':'موقوف'}</span><div className="button-row"><Btn label="تعديل" icon={Pencil} variant="secondary" onClick={()=>setEditing(x)}/><Btn busy={busy===`branch-${x.id}`} label={x.is_active?'إيقاف':'تفعيل'} variant="secondary" onClick={()=>toggle(x)}/></div></div>)}</div>:<Empty/>}</Panel>{editing&&<Modal title="تعديل الفرع" onClose={()=>setEditing(null)}><form className="form-grid" onSubmit={update}><Field label="اسم الفرع" name="name" defaultValue={editing.name}/><Field label="الهاتف" name="phone" defaultValue={editing.phone||''} required={false}/><Field label="مدير الفرع" name="manager_name" defaultValue={editing.manager_name||''} required={false}/><Field label="العنوان" name="address" defaultValue={editing.address||''} required={false}/><div className="two-col"><Field label="خط العرض" name="latitude" defaultValue={editing.latitude||''} required={false}/><Field label="خط الطول" name="longitude" defaultValue={editing.longitude||''} required={false}/></div><div className="button-row"><Btn busy={busy===`edit-branch-${editing.id}`} label="حفظ"/><Btn type="button" label="إلغاء" variant="secondary" onClick={()=>setEditing(null)}/></div></form></Modal>}</div>
}


function CardTemplates({rows,programs,brand,brandInfo,busy,run,reload}:any){
  const templates=safeArray<Row>(rows)
  const stampPrograms=safeArray<Row>(programs).filter(x=>!x.is_archived)
  const [editing,setEditing]=useState<Row|null>(null)
  const [preview,setPreview]=useState<Row|null>(null)

  const templatePayload=(fd:FormData)=>({
    brand_id:brand,
    name:fd.get('name'),
    name_en:fd.get('name_en')||null,
    slug:String(fd.get('slug')||'').trim().toLowerCase(),
    description:fd.get('description')||null,
    is_default:fd.get('is_default')==='on',
    allow_public_join:fd.get('allow_public_join')==='on',
    sort_order:Number(fd.get('sort_order')||0),
    program_ids:fd.getAll('program_ids').map(String),
    background_color:fd.get('background_color'),
    foreground_color:fd.get('foreground_color'),
    label_color:fd.get('label_color'),
    logo_text:fd.get('logo_text'),
    card_title:fd.get('card_title'),
    layout_style:fd.get('layout_style'),
    overlay_opacity:Number(fd.get('overlay_opacity')||25),
    barcode_format:fd.get('barcode_format'),
    fields:{show_stamps:true,show_rewards:true,show_points:false,show_tier:false,show_visits:false},
    terms:fd.get('terms')||null,
  })
  async function create(e:React.FormEvent<HTMLFormElement>){e.preventDefault();const form=e.currentTarget,fd=new FormData(form);if(fd.getAll('program_ids').length<1){alert('اختر برنامج ختم واحدًا على الأقل');return}await run('card-template-create',()=>api('/api/cards/templates',{method:'POST',body:JSON.stringify(templatePayload(fd))}),'تم إنشاء البطاقة كمسودة');form.reset();await reload()}
  async function update(e:React.FormEvent<HTMLFormElement>){e.preventDefault();if(!editing)return;const fd=new FormData(e.currentTarget);const payload=templatePayload(fd);delete (payload as any).brand_id;await run(`card-template-edit-${editing.id}`,()=>api(`/api/cards/templates/${editing.id}`,{method:'PATCH',body:JSON.stringify(payload)}),'تم حفظ البطاقة');setEditing(null);await reload()}
  async function action(x:Row,type:'publish'|'unpublish'|'duplicate'|'archive'|'restore'){
    const messages={publish:'تم نشر البطاقة وتحديث بطاقات العملاء',unpublish:'تم إلغاء نشر البطاقة',duplicate:'تم نسخ البطاقة كمسودة',archive:'تم أرشفة البطاقة بأمان',restore:'تمت استعادة البطاقة كمسودة'}
    if(type==='archive'&&!confirm('أرشفة البطاقة؟ إذا كانت مستخدمة سينقل العملاء إلى بطاقة منشورة بديلة.'))return
    await run(`card-${type}-${x.id}`,()=>api(`/api/cards/templates/${x.id}/${type}`,{method:'POST'}),messages[type]);await reload()
  }
  async function remove(x:Row){if(!confirm('الحذف النهائي متاح فقط للبطاقة غير المستخدمة. هل تريد المتابعة؟'))return;await run(`card-delete-${x.id}`,()=>api(`/api/cards/templates/${x.id}`,{method:'DELETE'}),'تم حذف البطاقة نهائيًا');await reload()}
  async function asset(x:Row,kind:string,file?:File){if(!file)return;const fd=new FormData();fd.append('kind',kind);fd.append('file',file);await run(`card-asset-${x.id}-${kind}`,()=>api(`/api/cards/templates/${x.id}/asset`,{method:'POST',body:fd}),'تم رفع الصورة');await reload()}
  const joinUrl=typeof window==='undefined'?'':`${location.origin}/join/${brandInfo?.slug||''}`
  return <>
    <div className="content-grid mt-6">
      <Panel title="إنشاء بطاقة جديدة" desc="اختر برامج الأختام التي ستظهر داخل بطاقة Apple Wallet الواحدة">
        <form className="form-grid" onSubmit={create}>
          <div className="two-col"><Field label="اسم البطاقة" name="name" placeholder="قهوة وحلى"/><Field label="الاسم الإنجليزي" name="name_en" required={false} placeholder="Coffee & Sweet"/></div>
          <Field label="الرابط الداخلي" name="slug" placeholder="coffee-sweet" pattern="[a-z0-9-]+"/>
          <Field label="الوصف" name="description" required={false}/>
          <ProgramPicker programs={stampPrograms}/>
          <div className="form-divider">تصميم البطاقة</div>
          <div className="two-col"><Field label="لون الخلفية" name="background_color" type="color" defaultValue={brandInfo?.primary_color||'#111827'}/><Field label="لون النص" name="foreground_color" type="color" defaultValue="#FFFFFF"/></div>
          <div className="two-col"><Field label="لون العناوين" name="label_color" type="color" defaultValue={brandInfo?.accent_color||'#C6FF4A'}/><Field label="نسبة تعتيم الصورة" name="overlay_opacity" type="number" defaultValue="25" min="0" max="90"/></div>
          <div className="two-col"><Field label="اسم الشعار" name="logo_text" defaultValue={brandInfo?.name||'LOYALYN'}/><Field label="عنوان البطاقة" name="card_title" defaultValue="بطاقة الولاء"/></div>
          <div className="two-col"><Field label="نمط التصميم"><select className="input" name="layout_style" defaultValue="classic"><option value="classic">كلاسيكي</option><option value="visual">صورة كاملة</option><option value="minimal">بسيط</option></select></Field><Field label="نوع الباركود"><select className="input" name="barcode_format" defaultValue="PKBarcodeFormatQR"><option value="PKBarcodeFormatQR">QR</option><option value="PKBarcodeFormatPDF417">PDF417</option><option value="PKBarcodeFormatAztec">Aztec</option><option value="PKBarcodeFormatCode128">Code 128</option></select></Field></div>
          <Field label="الشروط والملاحظات" name="terms" required={false}/>
          <div className="two-col"><Field label="الترتيب" name="sort_order" type="number" defaultValue="0"/><div className="switch-stack"><Switch label="البطاقة الافتراضية" name="is_default"/><Switch label="متاحة في تسجيل العميل" name="allow_public_join" defaultChecked/></div></div>
          <Btn busy={busy==='card-template-create'} label="إنشاء البطاقة" icon={Plus}/>
        </form>
      </Panel>
      <Panel title="QR التسجيل الثابت" desc="العميل يمسحه ثم يختار البطاقة المتاحة ويضيفها إلى Wallet">
        <div className="join-qr-card"><img src={`${API}/api/public/brands/${brandInfo?.slug}/join-qr.svg`} alt="QR التسجيل"/><div><b>{brandInfo?.name}</b><p>رابط واحد لكل بطاقات البراند</p><code>{joinUrl}</code><div className="button-row mt-3"><Btn label="نسخ الرابط" icon={Copy} variant="secondary" onClick={async()=>navigator.clipboard.writeText(joinUrl)}/><a className="btn secondary" href={`${API}/api/public/brands/${brandInfo?.slug}/join-qr.svg`} target="_blank"><QrCode size={18}/>فتح QR</a></div></div></div>
      </Panel>
    </div>
    <Panel title="قوالب البطاقات" desc="بطاقة قهوة فقط، قهوة وحلى، فطور أو أي تركيبة تريدها" className="mt-5">
      {templates.length?<div className="template-grid">{templates.map((x:Row)=><article className={`template-card status-${x.status}`} key={x.id}>
        <WalletCard design={x} brand={brandInfo} programs={x.programs||[]}/>
        <div className="template-card-info"><div><h3>{x.name}</h3><p>{x.description||'بدون وصف'}</p></div><span className={`badge ${x.status==='published'?'success':x.status==='archived'?'muted-badge':'warning'}`}>{x.status==='published'?'منشورة':x.status==='archived'?'مؤرشفة':'مسودة'}</span></div>
        <div className="template-meta"><span><Layers3/> {x.programs?.length||0} برامج</span><span><Users/> {x.usage_count||0} عملاء</span>{x.is_default&&<span><CheckCircle2/> افتراضية</span>}{x.has_unpublished_changes&&x.status==='published'&&<span><Pencil/> تعديلات غير منشورة</span>}</div>
        <div className="template-program-chips">{safeArray<Row>(x.programs).map(p=><span key={p.id}>{stampIcon(p.stamp_icon)} {p.name}</span>)}</div>
        <div className="asset-grid four compact-assets"><AssetUpload label="الشعار" busy={busy===`card-asset-${x.id}-logo`} onChange={(e:any)=>asset(x,'logo',e.target.files?.[0])}/><AssetUpload label="صورة علوية" busy={busy===`card-asset-${x.id}-hero`} onChange={(e:any)=>asset(x,'hero',e.target.files?.[0])}/><AssetUpload label="خلفية كاملة" busy={busy===`card-asset-${x.id}-background`} onChange={(e:any)=>asset(x,'background',e.target.files?.[0])}/><AssetUpload label="شريط Apple" busy={busy===`card-asset-${x.id}-strip`} onChange={(e:any)=>asset(x,'strip',e.target.files?.[0])}/></div>
        <div className="button-row wrap-actions"><Btn label="تعديل" icon={Pencil} variant="secondary" onClick={()=>setEditing(x)}/><Btn label="معاينة" icon={Eye} variant="secondary" onClick={()=>setPreview(x)}/>{x.status!=='archived'&&x.has_unpublished_changes&&<Btn busy={busy===`card-publish-${x.id}`} label={x.status==='published'?'نشر التعديلات':'نشر'} icon={Upload} onClick={()=>action(x,'publish')}/>} {x.status==='published'&&Number(x.usage_count||0)===0&&<Btn busy={busy===`card-unpublish-${x.id}`} label="إلغاء النشر" icon={XCircle} variant="secondary" onClick={()=>action(x,'unpublish')}/>}<Btn busy={busy===`card-duplicate-${x.id}`} label="نسخ" icon={Copy} variant="secondary" onClick={()=>action(x,'duplicate')}/>{x.status==='archived'?<Btn busy={busy===`card-restore-${x.id}`} label="استعادة" icon={RotateCcw} variant="secondary" onClick={()=>action(x,'restore')}/>:<Btn busy={busy===`card-archive-${x.id}`} label="أرشفة" icon={Archive} variant="secondary" onClick={()=>action(x,'archive')}/>}<Btn busy={busy===`card-delete-${x.id}`} label="حذف" icon={Trash2} variant="danger" onClick={()=>remove(x)}/></div>
      </article>)}</div>:<Empty text="أنشئ أول قالب بطاقة"/>}
    </Panel>
    {editing&&<Modal title={`تعديل ${editing.name}`} desc="كل تعديل يُحفظ كمسودة حتى تضغط نشر" onClose={()=>setEditing(null)}><form className="form-grid" onSubmit={update}>
      <div className="two-col"><Field label="اسم البطاقة" name="name" defaultValue={editing.name}/><Field label="الاسم الإنجليزي" name="name_en" defaultValue={editing.name_en||''} required={false}/></div><Field label="الرابط الداخلي" name="slug" defaultValue={editing.slug}/><Field label="الوصف" name="description" defaultValue={editing.description||''} required={false}/><ProgramPicker programs={stampPrograms} selected={editing.program_ids||[]}/>
      <div className="form-divider">التصميم</div><div className="two-col"><Field label="لون الخلفية" name="background_color" type="color" defaultValue={editing.background_color}/><Field label="لون النص" name="foreground_color" type="color" defaultValue={editing.foreground_color}/></div><div className="two-col"><Field label="لون العناوين" name="label_color" type="color" defaultValue={editing.label_color}/><Field label="التعتيم" name="overlay_opacity" type="number" defaultValue={editing.overlay_opacity}/></div><div className="two-col"><Field label="اسم الشعار" name="logo_text" defaultValue={editing.logo_text}/><Field label="عنوان البطاقة" name="card_title" defaultValue={editing.card_title}/></div><div className="two-col"><Field label="نمط التصميم"><select className="input" name="layout_style" defaultValue={editing.layout_style}><option value="classic">كلاسيكي</option><option value="visual">صورة كاملة</option><option value="minimal">بسيط</option></select></Field><Field label="نوع الباركود"><select className="input" name="barcode_format" defaultValue={editing.barcode_format}><option value="PKBarcodeFormatQR">QR</option><option value="PKBarcodeFormatPDF417">PDF417</option><option value="PKBarcodeFormatAztec">Aztec</option><option value="PKBarcodeFormatCode128">Code 128</option></select></Field></div><Field label="الشروط" name="terms" defaultValue={editing.terms||''} required={false}/><div className="two-col"><Field label="الترتيب" name="sort_order" type="number" defaultValue={editing.sort_order}/><div className="switch-stack"><Switch label="البطاقة الافتراضية" name="is_default" defaultChecked={editing.is_default}/><Switch label="متاحة في تسجيل العميل" name="allow_public_join" defaultChecked={editing.allow_public_join}/></div></div><div className="button-row"><Btn busy={busy===`card-template-edit-${editing.id}`} label="حفظ المسودة"/><Btn type="button" label="إلغاء" variant="secondary" onClick={()=>setEditing(null)}/></div>
    </form></Modal>}
    {preview&&<Modal title={`معاينة ${preview.name}`} desc="هذه معاينة تقريبية؛ Apple يحدد مواضع الحقول النهائية" onClose={()=>setPreview(null)}><div className="preview-modal-card"><WalletCard design={preview} brand={brandInfo} programs={preview.programs||[]}/><div className="template-program-chips">{safeArray<Row>(preview.programs).map(p=><span key={p.id}>{stampIcon(p.stamp_icon)} {p.name} · {p.required_stamps} أختام</span>)}</div></div></Modal>}
  </>
}

function ProgramPicker({programs,selected=[]}:any){
  const available=safeArray<Row>(programs).filter(x=>!x.is_archived)
  const selectedKey=JSON.stringify(safeArray<string>(selected))
  const [order,setOrder]=useState<string[]>(()=>{
    const initial=safeArray<string>(selected).filter(id=>available.some(x=>x.id===id))
    return initial
  })
  useEffect(()=>{setOrder(safeArray<string>(selected).filter(id=>available.some(x=>x.id===id)))},[selectedKey,programs])
  const toggle=(id:string)=>setOrder(current=>current.includes(id)?current.filter(x=>x!==id):[...current,id])
  const move=(id:string,direction:-1|1)=>setOrder(current=>{const next=[...current],index=next.indexOf(id),target=index+direction;if(index<0||target<0||target>=next.length)return current;[next[index],next[target]]=[next[target],next[index]];return next})
  return <div className="field"><span>برامج الأختام داخل البطاقة</span>{order.map(id=><input key={id} type="hidden" name="program_ids" value={id}/>)}<div className="program-picker">
    {available.map(program=>{const checked=order.includes(program.id),position=order.indexOf(program.id);return <div key={program.id} className={`program-picker-item ${checked?'selected':''}`}><label><input type="checkbox" checked={checked} onChange={()=>toggle(program.id)}/><span className="program-picker-icon">{stampIcon(program.stamp_icon)}</span><span><b>{program.name}</b><small>{program.required_stamps} أختام · {program.reward_title}</small></span></label>{checked&&<div className="program-order-actions"><button type="button" disabled={position===0} onClick={()=>move(program.id,-1)} aria-label="تحريك للأعلى">↑</button><em>{position+1}</em><button type="button" disabled={position===order.length-1} onClick={()=>move(program.id,1)} aria-label="تحريك للأسفل">↓</button></div>}</div>})}
    {!available.length&&<p className="muted">أنشئ برنامج ختم أولًا من قسم برامج الأختام.</p>}
  </div><small className="field-help">ترتيب البرامج هنا هو ترتيب ظهورها على البطاقة وصفحة العميل.</small></div>
}

function StampCards({rows,brand,brandInfo,busy,run,reload}:any){
  const programs=safeArray<Row>(rows)
  const [editing,setEditing]=useState<Row|null>(null)
  const payload=(fd:FormData)=>({
    brand_id:brand,name:fd.get('name'),slug:String(fd.get('slug')||'').trim().toLowerCase(),
    description:fd.get('description')||null,required_stamps:Number(fd.get('required_stamps')||6),
    reward_title:fd.get('reward_title'),reward_type:fd.get('reward_type'),stamp_icon:fd.get('stamp_icon'),
    background_color:fd.get('background_color'),accent_color:fd.get('accent_color'),
    is_default:fd.get('is_default')==='on',sort_order:Number(fd.get('sort_order')||0),
  })
  async function create(e:React.FormEvent<HTMLFormElement>){e.preventDefault();const form=e.currentTarget;await run('stamp-program-create',()=>api('/api/stamps/programs',{method:'POST',body:JSON.stringify(payload(new FormData(form)))}),'تم إنشاء برنامج الختم');form.reset();await reload()}
  async function update(e:React.FormEvent<HTMLFormElement>){e.preventDefault();if(!editing)return;const fd=new FormData(e.currentTarget);const body:any=payload(fd);delete body.brand_id;body.is_active=fd.get('is_active')==='on';await run(`stamp-edit-${editing.id}`,()=>api(`/api/stamps/programs/${editing.id}`,{method:'PATCH',body:JSON.stringify(body)}),'تم تحديث برنامج الختم');setEditing(null);await reload()}
  async function action(program:Row,type:'archive'|'restore'){
    if(type==='archive'&&!confirm('أرشفة برنامج الختم؟ سيختفي من البطاقات الجديدة والسكان، لكن السجل القديم لن يُحذف.'))return
    await run(`stamp-${type}-${program.id}`,()=>api(`/api/stamps/programs/${program.id}/${type}`,{method:'POST'}),type==='archive'?'تم أرشفة البرنامج':'تمت استعادة البرنامج');await reload()
  }
  async function remove(program:Row){if(!confirm('الحذف النهائي متاح فقط لبرنامج غير مستخدم. هل تريد المتابعة؟'))return;await run(`stamp-delete-${program.id}`,()=>api(`/api/stamps/programs/${program.id}`,{method:'DELETE'}),'تم حذف البرنامج نهائيًا');await reload()}
  async function asset(program:Row,kind:string,file?:File){if(!file)return;const fd=new FormData();fd.append('kind',kind);fd.append('file',file);await run(`stamp-asset-${program.id}-${kind}`,()=>api(`/api/stamps/programs/${program.id}/asset`,{method:'POST',body:fd}),'تم رفع الصورة');await reload()}
  const iconOptions=<><option value="coffee">قهوة</option><option value="cake">حلى</option><option value="cookie">كوكيز</option><option value="cup">مشروب</option><option value="star">نجمة</option></>
  return <>
    <div className="content-grid mt-6">
      <Panel title="إنشاء برنامج ختم" desc="البرنامج هو مسمى مستقل مثل قهوة أو حلى، ويمكن إضافته إلى بطاقة واحدة أو أكثر.">
        <form className="form-grid" onSubmit={create}>
          <div className="two-col"><Field label="اسم البرنامج" name="name" placeholder="قهوة"/><Field label="الرابط الداخلي" name="slug" placeholder="coffee" pattern="[a-z0-9-]+"/></div>
          <Field label="الوصف" name="description" required={false}/>
          <div className="two-col"><Field label="عدد الأختام المطلوبة" name="required_stamps" type="number" defaultValue="6" min="1" max="100"/><Field label="اسم المكافأة" name="reward_title" defaultValue="مشروب مجاني"/></div>
          <div className="two-col"><Field label="نوع المكافأة"><select className="input" name="reward_type"><option value="free_item">منتج مجاني</option><option value="discount">خصم</option><option value="custom">مخصص</option></select></Field><Field label="رمز الختم"><select className="input" name="stamp_icon">{iconOptions}</select></Field></div>
          <div className="two-col"><Field label="لون القسم" name="background_color" type="color" defaultValue={brandInfo?.primary_color||'#111827'}/><Field label="لون الختم" name="accent_color" type="color" defaultValue={brandInfo?.accent_color||'#C6FF4A'}/></div>
          <div className="two-col"><Field label="الترتيب" name="sort_order" type="number" defaultValue="0"/><Switch label="البرنامج الافتراضي" name="is_default"/></div>
          <Btn busy={busy==='stamp-program-create'} label="إنشاء برنامج الختم" icon={Plus}/>
        </form>
      </Panel>
      <Panel title="كيف تستخدم البرامج؟" desc="البطاقة هي الغلاف، وبرامج الأختام هي الأقسام داخلها.">
        <div className="rules-box"><Rule icon={Coffee} title="قهوة" text="6 أختام = مشروب مجاني"/><Rule icon={Gift} title="حلى" text="5 أختام = قطعة حلى"/><Rule icon={Layers3} title="بطاقة واحدة" text="يمكن جمع قهوة وحلى داخل نفس بطاقة Wallet"/></div>
        <p className="muted text-sm mt-3">بعد إنشاء البرامج، افتح قسم «البطاقات» من القائمة واختر البرامج التي تريدها داخل كل قالب.</p>
      </Panel>
    </div>
    <Panel title="برامج الأختام" desc="عدّل المسميات والأعداد والصور، أو أرشف البرنامج بدون فقدان تاريخ العملاء." className="mt-5">
      {programs.length?<div className="stamp-program-grid">{programs.map((program:Row)=><article className={`stamp-program-card ${!program.is_active||program.is_archived?'disabled':''}`} key={program.id} style={{backgroundColor:program.background_color,color:'#fff',backgroundImage:program.card_image_url?`linear-gradient(rgba(0,0,0,.25),rgba(0,0,0,.5)),url(${API}/api/stamps/public/assets/${program.id}/card)`:undefined}}>
        <div className="stamp-program-head"><span>{stampIcon(program.stamp_icon)}</span><div><b>{program.name}</b><small>{program.required_stamps} أختام · {program.reward_title}</small></div>{program.is_archived?<em>مؤرشف</em>:program.is_default?<em>افتراضي</em>:null}</div>
        <StampDots count={Math.min(4,program.required_stamps)} total={program.required_stamps} program={program}/>
        <div className="stamp-assets"><label><ImageIcon size={16}/>صورة القسم<input type="file" accept="image/*" onChange={e=>asset(program,'card',e.target.files?.[0])}/></label><label><Upload size={16}/>الختم الفارغ<input type="file" accept="image/*" onChange={e=>asset(program,'empty_stamp',e.target.files?.[0])}/></label><label><Upload size={16}/>الختم الممتلئ<input type="file" accept="image/*" onChange={e=>asset(program,'filled_stamp',e.target.files?.[0])}/></label></div>
        <div className="button-row wrap-actions"><Btn label="تعديل" icon={Pencil} variant="secondary" onClick={()=>setEditing(program)}/>{program.is_archived?<Btn busy={busy===`stamp-restore-${program.id}`} label="استعادة" icon={RotateCcw} variant="secondary" onClick={()=>action(program,'restore')}/>:<Btn busy={busy===`stamp-archive-${program.id}`} label="أرشفة" icon={Archive} variant="secondary" onClick={()=>action(program,'archive')}/>}<Btn busy={busy===`stamp-delete-${program.id}`} label="حذف" icon={Trash2} variant="danger" onClick={()=>remove(program)}/></div>
      </article>)}</div>:<Empty text="أنشئ أول برنامج ختم"/>}
    </Panel>
    {editing&&<Modal title={`تعديل ${editing.name}`} onClose={()=>setEditing(null)}><form className="form-grid" onSubmit={update}>
      <div className="two-col"><Field label="الاسم" name="name" defaultValue={editing.name}/><Field label="الرابط" name="slug" defaultValue={editing.slug}/></div><Field label="الوصف" name="description" defaultValue={editing.description||''} required={false}/>
      <div className="two-col"><Field label="عدد الأختام" name="required_stamps" type="number" defaultValue={editing.required_stamps} min="1" max="100"/><Field label="المكافأة" name="reward_title" defaultValue={editing.reward_title}/></div>
      <div className="two-col"><Field label="نوع المكافأة"><select className="input" name="reward_type" defaultValue={editing.reward_type}><option value="free_item">منتج مجاني</option><option value="discount">خصم</option><option value="custom">مخصص</option></select></Field><Field label="الرمز"><select className="input" name="stamp_icon" defaultValue={editing.stamp_icon}>{iconOptions}</select></Field></div>
      <div className="two-col"><Field label="لون القسم" name="background_color" type="color" defaultValue={editing.background_color}/><Field label="لون الختم" name="accent_color" type="color" defaultValue={editing.accent_color}/></div>
      <Field label="الترتيب" name="sort_order" type="number" defaultValue={editing.sort_order}/><Switch label="البرنامج الافتراضي" name="is_default" defaultChecked={editing.is_default}/><Switch label="البرنامج فعال" name="is_active" defaultChecked={editing.is_active}/>
      <div className="button-row"><Btn busy={busy===`stamp-edit-${editing.id}`} label="حفظ التعديلات"/><Btn type="button" label="إلغاء" variant="secondary" onClick={()=>setEditing(null)}/></div>
    </form></Modal>}
  </>
}

function FastScan({brand,branches,busy,run,permissions}:any){
  const branchRows=safeArray<Row>(branches)
  const [code,setCode]=useState('')
  const [result,setResult]=useState<any>(null)
  const [history,setHistory]=useState<Row[]>([])
  const [branch,setBranch]=useState('')
  const [camera,setCamera]=useState(false)
  const [cameraError,setCameraError]=useState('')
  const videoRef=useRef<HTMLVideoElement|null>(null)
  const streamRef=useRef<MediaStream|null>(null)
  const canReverse=permissions?.['*']===true||permissions?.['loyalty.reverse']===true

  useEffect(()=>{if(branchRows.length===1)setBranch(branchRows[0].id);else if(branch&&!branchRows.some(x=>x.id===branch))setBranch('')},[branches,branch,branchRows])
  async function loadHistory(customerId:string){try{setHistory(safeArray(await api(`/api/stamps/transactions?brand_id=${brand}&customer_id=${customerId}&limit=30`)))}catch{setHistory([])}}
  async function lookup(value=code){const clean=value.trim();if(!clean)return;const valueData=await run('scan-lookup',()=>api(`/api/stamps/scan/${encodeURIComponent(clean)}?brand_id=${brand}`));if(valueData){setResult(valueData);setCode(clean);await loadHistory(valueData.customer.id)}}
  async function add(program:Row){if(!result)return;const valueData=await run(`scan-add-${program.id}`,()=>api(`/api/stamps/customers/${result.customer.id}/programs/${program.id}/add`,{method:'POST',body:JSON.stringify({branch_id:branch||null,quantity:1,idempotency_key:crypto.randomUUID()})}),`تمت إضافة ختم إلى ${program.name}`);if(valueData){setResult({...result,card_template:valueData.card_template||result.card_template,cards:safeArray(valueData.cards)});await loadHistory(result.customer.id)}}
  async function redeem(program:Row){if(!result)return;if(!confirm(`صرف مكافأة «${program.reward_title}»؟`))return;const valueData=await run(`scan-redeem-${program.id}`,()=>api(`/api/stamps/customers/${result.customer.id}/programs/${program.id}/redeem`,{method:'POST',body:JSON.stringify({branch_id:branch||null,idempotency_key:crypto.randomUUID()})}),`تم صرف ${program.reward_title}`);if(valueData){setResult({...result,card_template:valueData.card_template||result.card_template,cards:safeArray(valueData.cards)});await loadHistory(result.customer.id)}}
  async function reverse(tx:Row){if(!result)return;const reason=prompt('اكتب سبب التراجع عن العملية');if(!reason?.trim())return;const valueData=await run(`scan-reverse-${tx.id}`,()=>api(`/api/stamps/transactions/${tx.id}/reverse`,{method:'POST',body:JSON.stringify({reason:reason.trim(),idempotency_key:crypto.randomUUID()})}),'تم التراجع عن العملية وتحديث البطاقة');if(valueData){setResult({...result,card_template:valueData.card_template||result.card_template,cards:safeArray(valueData.cards)});await loadHistory(result.customer.id)}}
  async function stopCamera(){streamRef.current?.getTracks().forEach(t=>t.stop());streamRef.current=null;setCamera(false)}
  async function startCamera(){
    setCameraError('')
    try{
      const Detector=(window as any).BarcodeDetector
      if(!Detector){setCameraError('هذا المتصفح لا يدعم قراءة QR بالكاميرا. استخدم خانة الرمز أو قارئ الباركود.');return}
      if(!navigator.mediaDevices?.getUserMedia){setCameraError('الكاميرا غير متاحة في هذا المتصفح.');return}
      const stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'}}})
      streamRef.current=stream;setCamera(true)
      window.setTimeout(async()=>{
        if(!videoRef.current)return
        videoRef.current.srcObject=stream;await videoRef.current.play()
        const detector=new Detector({formats:['qr_code','code_128']})
        const tick=async()=>{if(!streamRef.current||!videoRef.current)return;try{const codes=await detector.detect(videoRef.current);if(codes?.[0]?.rawValue){setCode(codes[0].rawValue);await stopCamera();await lookup(codes[0].rawValue);return}}catch{}requestAnimationFrame(tick)}
        void tick()
      },100)
    }catch(error:any){setCameraError(error?.name==='NotAllowedError'?'اسمح للموقع باستخدام الكاميرا من إعدادات المتصفح ثم جرّب مرة أخرى.':'تعذر تشغيل الكاميرا. استخدم الإدخال اليدوي أو قارئ الباركود.')}
  }
  useEffect(()=>{const pending=localStorage.getItem('loyalyn_scan_code');if(pending){localStorage.removeItem('loyalyn_scan_code');setCode(pending);window.setTimeout(()=>void lookup(pending),120)}return()=>{streamRef.current?.getTracks().forEach(t=>t.stop())}// eslint-disable-next-line react-hooks/exhaustive-deps
  },[brand])
  const cards=safeArray<Row>(result?.cards).filter(x=>x.card_active&&x.is_active&&!x.is_archived)
  const latestByProgram=new Map<string,string>()
  history.forEach(tx=>{if(tx.action!=='reversal'&&!tx.reversed_at&&!latestByProgram.has(tx.stamp_program_id))latestByProgram.set(tx.stamp_program_id,tx.id)})
  const programName=(id:string)=>cards.find(x=>x.id===id)?.name||'برنامج ختم'
  return <div className="scan-layout mt-6">
    <Panel title="مسح بطاقة العميل" desc="امسح QR، اختر برنامج الختم، ثم اضغط زرًا واحدًا فقط.">
      <div className="scan-controls"><Field label="رقم العضوية أو نتيجة المسح"><input className="input scan-input" value={code} onChange={e=>setCode(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')void lookup()}} autoFocus placeholder="امسح الرمز هنا" inputMode="text"/></Field>
      {branchRows.length>1&&<Field label="الفرع" required={false}><select className="input" value={branch} onChange={e=>setBranch(e.target.value)}><option value="">اختر الفرع</option>{branchRows.filter(x=>x.is_active!==false).map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></Field>}
      {branchRows.length===1&&<div className="selected-branch"><MapPin size={17}/><span>الفرع: <b>{branchRows[0].name}</b></span></div>}
      <div className="button-row"><Btn busy={busy==='scan-lookup'} label="فتح العميل" icon={ScanLine} onClick={()=>void lookup()}/><Btn label={camera?'إيقاف الكاميرا':'فتح الكاميرا'} icon={Camera} variant="secondary" onClick={()=>camera?void stopCamera():void startCamera()}/></div>
      {cameraError&&<div className="inline-error"><XCircle size={18}/><span>{cameraError}</span></div>}{camera&&<video ref={videoRef} className="scan-video" muted playsInline/>}</div>
    </Panel>
    <div className="scan-result">{result?<><div className="scan-customer"><div className="avatar large">{result.customer?.name?.[0]||'ع'}</div><div><small>العميل</small><h2>{result.customer?.name}</h2><p>{result.customer?.phone} · {result.customer?.membership_code}</p><em>{result.card_template?.name||'البطاقة الرئيسية'}</em></div><span className="badge success">جاهز</span></div>
      <div className="scan-card-grid">{cards.map((program:Row)=><article className="scan-stamp-card" key={program.id} style={{backgroundColor:program.background_color,backgroundImage:program.card_image_url?`linear-gradient(rgba(0,0,0,.28),rgba(0,0,0,.5)),url(${API}/api/stamps/public/assets/${program.id}/card)`:undefined}}><div className="stamp-program-head"><span>{stampIcon(program.stamp_icon)}</span><div><b>{program.name}</b><small>{program.reward_title}</small></div></div><StampDots count={program.stamps} total={program.required_stamps} program={program}/><div className="scan-card-meta"><span><b>{program.stamps}</b>/{program.required_stamps} ختم</span><span><b>{program.rewards_available}</b> مكافأة جاهزة</span></div><div className="button-row"><Btn busy={busy===`scan-add-${program.id}`} label="+ ختم" icon={Plus} onClick={()=>void add(program)}/><Btn busy={busy===`scan-redeem-${program.id}`} disabled={!program.rewards_available} label="صرف المكافأة" icon={Gift} variant="secondary" onClick={()=>void redeem(program)}/></div></article>)}</div>
      {!cards.length&&<Empty text="لا توجد برامج أختام فعالة داخل بطاقة هذا العميل"/>}
      <section className="scan-history"><div className="scan-history-head"><div><h3>آخر العمليات</h3><p>التراجع لا يحذف السجل؛ ينشئ عملية عكسية باسم الموظف وسبب التراجع.</p></div>{history.length>0&&<span>{history.length}</span>}</div>{history.length?<div className="ledger-list">{history.slice(0,12).map(tx=><div key={tx.id} className={tx.action==='reversal'?'reversed-row':''}><div><b>{tx.action==='add'?`إضافة ختم · ${programName(tx.stamp_program_id)}`:tx.action==='redeem'?`صرف مكافأة · ${programName(tx.stamp_program_id)}`:'تراجع عن عملية'}</b><small>{new Date(tx.created_at).toLocaleString('ar-QA')}{tx.reversal_reason?` · ${tx.reversal_reason}`:''}</small></div><span className={(tx.delta_stamps||tx.delta_rewards)>=0?'positive':'negative'}>{tx.delta_stamps?`${tx.delta_stamps>0?'+':''}${tx.delta_stamps} ختم`:''}{tx.delta_rewards?` ${tx.delta_rewards>0?'+':''}${tx.delta_rewards} مكافأة`:''}</span>{canReverse&&tx.action!=='reversal'&&!tx.reversed_at&&latestByProgram.get(tx.stamp_program_id)===tx.id&&<Btn busy={busy===`scan-reverse-${tx.id}`} label="تراجع" icon={RotateCcw} variant="danger" onClick={()=>void reverse(tx)}/>} {tx.reversed_at&&<em className="badge muted-badge">تم التراجع</em>}</div>)}</div>:<Empty text="لا توجد عمليات لهذا العميل بعد"/>}</section>
    </>:<div className="scan-empty"><QrCode/><h3>بانتظار مسح العميل</h3><p>بعد المسح تظهر بطاقة العميل وبرامج القهوة والحلى المحفوظة داخلها.</p></div>}</div>
  </div>
}

function StampDots({count,total,program}:any){const shown=Math.min(Number(total)||0,12);return <div className="stamp-dots">{Array.from({length:shown}).map((_,i)=>{const filled=i<Number(count||0);const asset=filled?program.filled_stamp_image_url:program.empty_stamp_image_url;return <span key={i} className={filled?'filled':''} style={{borderColor:program.accent_color,backgroundColor:filled&&!asset?program.accent_color:undefined}}>{asset?<img src={`${API}/api/stamps/public/assets/${program.id}/${filled?'filled_stamp':'empty_stamp'}`} alt=""/>:filled?stampIcon(program.stamp_icon):''}</span>})}{Number(total)>12&&<em>+{Number(total)-12}</em>}</div>}
const stampIcon=(value:string)=>({coffee:'☕',cake:'🍰',cookie:'🍪',cup:'🥤',star:'★'} as Row)[value]||'●'

function Customers({rows,rewards,coupons,branches,cardTemplates,brand,submit,busy,loyaltyAction,issuePass,run,reload,capabilities,permissions,setTab}:any){
  const initialRows=safeArray<Row>(rows)
  const branchRows=safeArray<Row>(branches)
  const rewardRows=safeArray<Row>(rewards)
  const couponRows=safeArray<Row>(coupons)
  const templateRows=safeArray<Row>(cardTemplates).filter(x=>x.status==='published')
  const perms=permissions||{}
  const canList=perms['*']===true||perms['customers.list']===true
  const canCreate=perms['*']===true||perms['customers.create']===true||perms['customers.manage']===true
  const canEdit=perms['*']===true||perms['customers.edit']===true||perms['customers.manage']===true
  const canHistory=perms['*']===true||perms['customers.history']===true
  const canApply=perms['*']===true||perms['loyalty.apply']===true
  const canManual=perms['*']===true||perms['loyalty.manual']===true||perms['loyalty.manage']===true
  const canRedeem=perms['*']===true||perms['rewards.redeem']===true
  const canIssue=perms['*']===true||perms['wallet.issue']===true
  const canScan=perms['*']===true||perms['fast_scan.use']===true
  const canReverse=perms['*']===true||perms['loyalty.reverse']===true||perms['loyalty.manage']===true
  const [search,setSearch]=useState('')
  const [serverRows,setServerRows]=useState<Row[]>(initialRows)
  const [searching,setSearching]=useState(false)
  const [editing,setEditing]=useState<Row|null>(null)
  const [profile,setProfile]=useState<Row|null>(null)
  const [ledger,setLedger]=useState<Row[]>([])
  const [rewardCustomer,setRewardCustomer]=useState<Row|null>(null)
  const [couponCustomer,setCouponCustomer]=useState<Row|null>(null)
  const [assignmentCustomer,setAssignmentCustomer]=useState<Row|null>(null)
  const [assignmentTemplate,setAssignmentTemplate]=useState('')
  const caps=capabilities||{}

  useEffect(()=>{if(canList)setServerRows(initialRows)},[rows,canList])
  useEffect(()=>{
    if(canList)return
    const clean=search.trim()
    if(clean.length<2){setServerRows([]);return}
    let cancelled=false
    setSearching(true)
    const timer=window.setTimeout(async()=>{
      try{const found=safeArray<Row>(await api(`/api/customers?brand_id=${brand}&active_only=false&q=${encodeURIComponent(clean)}`));if(!cancelled)setServerRows(found)}
      catch{if(!cancelled)setServerRows([])}finally{if(!cancelled)setSearching(false)}
    },300)
    return()=>{cancelled=true;window.clearTimeout(timer)}
  },[search,canList,brand])

  const shown=canList?initialRows.filter((x:Row)=>`${x.name} ${x.phone} ${x.email||''} ${x.membership_code}`.toLowerCase().includes(search.toLowerCase())):serverRows
  const branchName=(id?:string|null)=>branchRows.find((x:Row)=>x.id===id)?.name||'غير مرتبط بفرع'

  async function update(e:React.FormEvent<HTMLFormElement>){
    e.preventDefault();if(!editing)return
    const fd=new FormData(e.currentTarget)
    await run(`edit-customer-${editing.id}`,()=>api(`/api/customers/${editing.id}`,{method:'PATCH',body:JSON.stringify({name:fd.get('name'),phone:fd.get('phone'),email:fd.get('email')||null,birthday:fd.get('birthday')||null,home_branch_id:fd.get('home_branch_id')||null,notes:fd.get('notes')||null,is_active:fd.get('is_active')==='on'})}),'تم تحديث العميل')
    setEditing(null);await reload()
  }
  async function openProfile(c:Row){if(!canHistory)return;const [detail,history]=await Promise.all([run(`customer-${c.id}`,()=>api(`/api/customers/${c.id}`)),run(`ledger-${c.id}`,()=>api(`/api/customers/${c.id}/ledger`))]);setProfile(detail||c);setLedger(safeArray(history))}
  async function openEdit(c:Row){if(!canEdit)return;const detail=await run(`customer-${c.id}`,()=>api(`/api/customers/${c.id}`));setEditing(detail||c)}
  async function redeem(e:React.FormEvent<HTMLFormElement>){e.preventDefault();if(!rewardCustomer)return;const fd=new FormData(e.currentTarget);await run(`redeem-${rewardCustomer.id}`,()=>api(`/api/customers/${rewardCustomer.id}/redeem`,{method:'POST',body:JSON.stringify({reward_id:fd.get('reward_id'),idempotency_key:crypto.randomUUID()})}),'تم استبدال المكافأة');setRewardCustomer(null);await reload()}
  async function redeemEarned(c:Row){await run(`earned-${c.id}`,()=>api(`/api/customers/${c.id}/redeem-earned`,{method:'POST',body:JSON.stringify({idempotency_key:crypto.randomUUID()})}),'تم صرف المكافأة الجاهزة');await reload()}
  async function redeemCoupon(e:React.FormEvent<HTMLFormElement>){e.preventDefault();if(!couponCustomer)return;const fd=new FormData(e.currentTarget);await run(`coupon-${couponCustomer.id}`,()=>api(`/api/customers/${couponCustomer.id}/coupons/redeem`,{method:'POST',body:JSON.stringify({code:fd.get('code'),idempotency_key:crypto.randomUUID()})}),'تم تطبيق الكوبون');setCouponCustomer(null);await reload()}
  async function reverse(tx:Row){const reason=prompt('اكتب سبب عكس العملية');if(!reason)return;await run(`reverse-${tx.id}`,()=>api(`/api/customers/transactions/${tx.id}/reverse`,{method:'POST',body:JSON.stringify({reason,idempotency_key:crypto.randomUUID()})}),'تم عكس العملية');if(profile)await openProfile(profile);await reload()}
  async function openAssignment(c:Row){setAssignmentCustomer(c);const current=await run(`assignment-${c.id}`,()=>api(`/api/cards/customers/${c.id}/assignment`));setAssignmentTemplate(current?.card_template?.id||templateRows[0]?.id||'')}
  async function saveAssignment(){if(!assignmentCustomer||!assignmentTemplate)return;await run(`assignment-save-${assignmentCustomer.id}`,()=>api(`/api/cards/customers/${assignmentCustomer.id}/assignment`,{method:'PUT',body:JSON.stringify({card_template_id:assignmentTemplate})}),'تم تغيير بطاقة العميل وتحديث Wallet');setAssignmentCustomer(null);setAssignmentTemplate('');await reload()}
  function openScan(c:Row){localStorage.setItem('loyalyn_scan_code',c.membership_code);setTab('scan')}

  return <div className="wide-grid mt-6">
    {canCreate&&<Panel title="تسجيل عميل" desc={caps.stamps?'بعد التسجيل ينضم العميل تلقائيًا لبطاقات الأختام الفعالة ويمكنه استخدام QR مباشرة.':'يمكن ربط العميل بفرعه المعتاد واستخدامه في برنامج البراند.'}>
      <form className="form-grid" onSubmit={(e)=>submit('/api/customers',e,{brand_id:brand},'POST','تم تسجيل العميل')}>
        <Field label="اسم العميل" name="name"/><Field label="رقم الهاتف" name="phone"/><Field label="البريد الإلكتروني" name="email" type="email" required={false}/><Field label="تاريخ الميلاد" name="birthday" type="date" required={false}/>
        {branchRows.length>1&&<Field label="الفرع المعتاد" required={false}><select className="input" name="home_branch_id"><option value="">بدون فرع محدد</option>{branchRows.filter(x=>x.is_active!==false).map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></Field>}
        {branchRows.length===1&&<input type="hidden" name="home_branch_id" value={branchRows[0].id}/>} {caps.stamps&&templateRows.length>0&&<Field label="البطاقة"><select className="input" name="card_template_id" defaultValue={templateRows.find(x=>x.is_default)?.id||templateRows[0]?.id}>{templateRows.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></Field>}<Field label="ملاحظات" name="notes" required={false}/><Btn busy={busy==='/api/customers'} label="إضافة العميل" icon={Plus}/>
      </form>
    </Panel>}
    <Panel title={canList?'قاعدة العملاء':'البحث عن عميل'} desc={!canList?'ابحث برقم الهاتف أو الاسم أو رقم العضوية؛ لا تُحمّل قائمة العملاء كاملة لحماية الخصوصية.':undefined} action={<div className="search-box">{searching&&<Loader2 size={16} className="animate-spin"/>}<input className="input search-input" placeholder="بحث بالاسم أو الهاتف أو رقم العضوية" value={search} onChange={e=>setSearch(e.target.value)}/></div>}>
      {!canList&&search.trim().length<2?<Empty text="اكتب حرفين على الأقل للبحث عن العميل"/>:shown.length?<div className="customer-list">{shown.map((c:Row)=><div className="customer-card" key={c.id}>
        <div className="customer-top"><div className="avatar large">{c.name?.[0]||'ع'}</div><div className="entity-main"><b>{c.name}</b><small>{c.phone}{c.email?` · ${c.email}`:''} · {c.membership_code} · {branchName(c.home_branch_id)}</small></div>{caps.tiers&&<span className="tier-pill">{c.tier}</span>}</div>
        <div className="mini-stats">{caps.points&&<span><b>{c.points}</b>نقطة</span>}{caps.stamps&&<span><b>{c.stamps}</b>ختم حالي</span>}{caps.rewards&&<span><b>{c.available_rewards}</b>مكافأة</span>}<span><b>{c.visits}</b>زيارة</span></div>
        <div className="button-row">{canScan&&caps.fast_scan&&<Btn label="فتح في السكان" icon={ScanLine} onClick={()=>openScan(c)}/>} {canApply&&caps.points&&<Btn busy={busy===`loyalty-${c.id}`} label="زيارة" icon={Plus} variant="secondary" onClick={()=>loyaltyAction(c,'visit')}/>} {canApply&&caps.points&&<Btn busy={busy===`loyalty-${c.id}`} label="فاتورة" icon={CreditCard} variant="secondary" onClick={()=>loyaltyAction(c,'spend')}/>} {canManual&&(caps.points||(!caps.multi_stamp_cards&&caps.stamps))&&<Btn busy={busy===`loyalty-${c.id}`} label="تعديل رصيد" icon={Pencil} variant="secondary" onClick={()=>loyaltyAction(c,'manual')}/>} {canHistory&&<Btn label="الملف والسجل" icon={Activity} variant="secondary" onClick={()=>void openProfile(c)}/>} {canEdit&&<Btn label="بيانات العميل" icon={Pencil} variant="secondary" onClick={()=>void openEdit(c)}/>} {canEdit&&caps.stamps&&templateRows.length>0&&<Btn busy={busy===`assignment-${c.id}`} label="تغيير البطاقة" icon={CreditCard} variant="secondary" onClick={()=>void openAssignment(c)}/>} {canIssue&&caps.wallet!==false&&<Btn busy={busy===`pass-${c.id}`} label="إصدار Wallet" icon={WalletCards} variant="secondary" onClick={()=>issuePass(c)}/>} {canRedeem&&caps.points&&caps.rewards&&rewardRows.length>0&&<Btn label="مكافأة نقاط" icon={Gift} variant="secondary" onClick={()=>setRewardCustomer(c)}/>} {canRedeem&&!caps.multi_stamp_cards&&caps.rewards&&c.available_rewards>0&&<Btn busy={busy===`earned-${c.id}`} label="صرف الجاهزة" icon={Gift} variant="secondary" onClick={()=>void redeemEarned(c)}/>} {canRedeem&&caps.coupons&&couponRows.length>0&&<Btn label="تطبيق كوبون" icon={Stamp} variant="secondary" onClick={()=>setCouponCustomer(c)}/>}</div>
      </div>)}</div>:<Empty text="لا يوجد عملاء مطابقون"/>}
    </Panel>
    {canEdit&&editing&&<Modal title="تعديل بيانات العميل" onClose={()=>setEditing(null)}><form className="form-grid" onSubmit={update}><Field label="الاسم" name="name" defaultValue={editing.name}/><Field label="الهاتف" name="phone" defaultValue={editing.phone}/><Field label="البريد" name="email" type="email" defaultValue={editing.email||''} required={false}/><Field label="تاريخ الميلاد" name="birthday" type="date" defaultValue={editing.birthday||''} required={false}/>{branchRows.length>1&&<Field label="الفرع المعتاد" required={false}><select className="input" name="home_branch_id" defaultValue={editing.home_branch_id||''}><option value="">بدون فرع محدد</option>{branchRows.filter(x=>x.is_active!==false).map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></Field>}<Field label="الملاحظات"><textarea className="input min-h-24" name="notes" defaultValue={editing.notes||''}/></Field><Switch label="الحساب فعال" name="is_active" defaultChecked={editing.is_active}/><div className="button-row"><Btn busy={busy===`edit-customer-${editing.id}`} label="حفظ"/><Btn type="button" label="إلغاء" variant="secondary" onClick={()=>setEditing(null)}/></div></form></Modal>}
    {canRedeem&&rewardCustomer&&<Modal title={`استبدال مكافأة لـ ${rewardCustomer.name}`} onClose={()=>setRewardCustomer(null)}><form className="form-grid" onSubmit={redeem}><Field label="المكافأة"><select className="input" name="reward_id" required>{rewardRows.filter(r=>r.is_active).map(r=><option key={r.id} value={r.id}>{r.name} — {r.points_cost} نقطة {r.stock==null?'':`— المتبقي ${r.stock}`}</option>)}</select></Field><Btn busy={busy===`redeem-${rewardCustomer.id}`} label="تأكيد الاستبدال" icon={Gift}/></form></Modal>}
    {canRedeem&&couponCustomer&&<Modal title={`تطبيق كوبون لـ ${couponCustomer.name}`} onClose={()=>setCouponCustomer(null)}><form className="form-grid" onSubmit={redeemCoupon}><Field label="رمز الكوبون"><select className="input" name="code" required>{couponRows.filter(c=>c.is_active).map(c=><option key={c.id} value={c.code}>{c.code} — {c.name}</option>)}</select></Field><Btn busy={busy===`coupon-${couponCustomer.id}`} label="تطبيق الكوبون" icon={Stamp}/></form></Modal>}
    {assignmentCustomer&&<Modal title={`بطاقة ${assignmentCustomer.name}`} desc="اختر قالبًا منشورًا؛ سيُحفظ رصيد البرامج المشتركة وتُحدّث بطاقة Wallet." onClose={()=>{setAssignmentCustomer(null);setAssignmentTemplate('')}}><div className="form-grid"><Field label="قالب البطاقة"><select className="input" value={assignmentTemplate} onChange={e=>setAssignmentTemplate(e.target.value)}>{templateRows.map(x=><option key={x.id} value={x.id}>{x.name} · {x.programs?.map((p:Row)=>p.name).join(' + ')}</option>)}</select></Field><div className="button-row"><Btn busy={busy===`assignment-save-${assignmentCustomer.id}`} label="حفظ البطاقة" icon={Save} onClick={()=>void saveAssignment()}/><Btn label="إلغاء" variant="secondary" onClick={()=>{setAssignmentCustomer(null);setAssignmentTemplate('')}}/></div></div></Modal>}
    {canHistory&&profile&&<Modal title={`ملف ${profile.name}`} desc={[caps.points?`${profile.points} نقطة`:null,caps.stamps?`${profile.stamps} ختم`:null,caps.rewards?`${profile.available_rewards} مكافأة`:null].filter(Boolean).join(' · ')} onClose={()=>{setProfile(null);setLedger([])}}><div className="profile-summary"><Info label="رقم العضوية" value={profile.membership_code}/><Info label="الفرع المعتاد" value={branchName(profile.home_branch_id)}/><Info label="إجمالي الصرف" value={`${Number(profile.total_spend||0).toLocaleString('ar-QA')} QAR`}/><Info label="آخر زيارة" value={profile.last_visit_at?new Date(profile.last_visit_at).toLocaleString('ar-QA'):'لا توجد'}/></div><h3 className="section-title">دفتر العمليات العام</h3><div className="ledger-list">{safeArray<Row>(ledger).map((tx:Row)=><div key={tx.id}><div><b>{actionName(tx.action)}</b><small>{new Date(tx.created_at).toLocaleString('ar-QA')} · {tx.reference||'بدون مرجع'}</small></div><span className={(tx.delta_points||tx.delta_stamps)>=0?'positive':'negative'}>{caps.points?`${tx.delta_points>=0?'+':''}${tx.delta_points} نقطة`:''}{caps.points&&caps.stamps?' · ':''}{caps.stamps?`${tx.delta_stamps>=0?'+':''}${tx.delta_stamps} ختم`:''}</span>{canReverse&&!['reversal','points_expired'].includes(tx.action)&&<button type="button" className="text-btn" onClick={()=>void reverse(tx)}>عكس</button>}</div>)}{!ledger.length&&<Empty text="لا توجد عمليات عامة؛ عمليات بطاقات الأختام تظهر في السكان السريع"/>}</div></Modal>}
  </div>
}

function Staff({rows,branches,brand,busy,run,reload,permissions}:any){
  const canManage=permissions?.['*']===true||permissions?.['staff.manage']===true
  const staffRows=safeArray<Row>(rows)
  const branchRows=safeArray<Row>(branches)
  const [editing,setEditing]=useState<Row|null>(null)
  const [creating,setCreating]=useState(false)
  const [createRole,setCreateRole]=useState('employee')
  const [editingRole,setEditingRole]=useState('')
  const employeePreset:Record<string,boolean>={'brand.view':true,'branches.scoped':true,'customers.view':true,'customers.create':true,'loyalty.view':true,'loyalty.apply':true,'rewards.redeem':true,'wallet.issue':true,'fast_scan.use':true}
  const managerPreset:Record<string,boolean>={'brand.view':true,'branches.view':true,'customers.view':true,'customers.list':true,'customers.create':true,'customers.edit':true,'customers.history':true,'loyalty.view':true,'loyalty.apply':true,'loyalty.manual':true,'loyalty.reverse':true,'rewards.redeem':true,'wallet.view':true,'wallet.issue':true,'fast_scan.use':true,'campaigns.view':true}
  const permissionChoices=[
    ['fast_scan.use','السكان السريع'],['customers.view','البحث وعرض العميل'],['customers.list','عرض قائمة العملاء كاملة'],['customers.create','تسجيل عميل جديد'],['customers.edit','تعديل بيانات العملاء'],['customers.history','عرض سجل عمليات العميل'],['loyalty.apply','إضافة ختم أو عملية ولاء'],['loyalty.reverse','التراجع عن آخر ختم'],['loyalty.manual','تعديل الرصيد يدويًا'],['rewards.redeem','صرف المكافآت'],['wallet.issue','إصدار بطاقة Wallet'],
    ['branches.view','عرض الفروع'],['branches.manage','إدارة الفروع'],['staff.view','عرض الموظفين'],['staff.manage','إدارة الموظفين'],['loyalty.view','عرض إعدادات الولاء'],['loyalty.manage','تعديل إعدادات الولاء'],['wallet.view','عرض استوديو البطاقة'],['wallet.design','تعديل تصميم البطاقة'],['campaigns.view','عرض الحملات'],['campaigns.manage','إدارة الحملات'],['audit.view','عرض سجل التدقيق'],
  ]
  async function toggle(x:Row){await run(`staff-${x.id}`,()=>api(`/api/management/staff/${x.id}`,{method:'PATCH',body:JSON.stringify({is_active:!x.is_active})}),x.is_active?'تم إيقاف الحساب':'تم تفعيل الحساب');await reload()}
  const roleDefaults=(role:string)=>role==='brand_admin'?{'*':true}:role==='manager'?managerPreset:employeePreset
  const readPermissions=(fd:FormData,role:string)=>{
    if(role==='brand_admin')return {'*':true}
    const values:Record<string,boolean>={}
    permissionChoices.forEach(([key])=>{values[key]=fd.get(`perm_${key}`)==='on'})
    return values
  }
  async function create(e:React.FormEvent<HTMLFormElement>){e.preventDefault();const form=e.currentTarget;const fd=new FormData(form);const role=String(fd.get('role')||'employee');await run('staff-create',()=>api('/api/management/staff',{method:'POST',body:JSON.stringify({brand_id:brand,name:fd.get('name'),email:fd.get('email'),phone:fd.get('phone')||null,password:fd.get('password'),role,branch_id:fd.get('branch_id')||null,permissions:readPermissions(fd,role)})}),'تم إنشاء حساب الموظف');form.reset();setCreateRole('employee');setCreating(false);await reload()}
  async function update(e:React.FormEvent<HTMLFormElement>){e.preventDefault();if(!editing)return;const fd=new FormData(e.currentTarget);const password=String(fd.get('password')||'');const role=editingRole||String(fd.get('role')||editing.role);const body:Row={name:fd.get('name'),phone:fd.get('phone')||null,role,branch_id:fd.get('branch_id')||null,is_active:fd.get('is_active')==='on',permissions:readPermissions(fd,role)};if(password)body.password=password;await run(`edit-staff-${editing.id}`,()=>api(`/api/management/staff/${editing.id}`,{method:'PATCH',body:JSON.stringify(body)}),'تم تحديث الحساب والصلاحيات');setEditing(null);setEditingRole('');await reload()}
  const PermissionEditor=({defaults,roleNameValue}:any)=><div className="permission-editor"><div className="form-divider">الصلاحيات</div><p className="muted text-sm">مدير البراند يملك كل صلاحيات برانده. للموظف أو المدير اختر ما يحتاجه فقط.</p><div className="permission-grid">{permissionChoices.map(([key,label])=><label className="permission-item" key={key}><input type="checkbox" name={`perm_${key}`} defaultChecked={roleNameValue==='brand_admin'||defaults?.['*']===true||defaults?.[key]===true}/><span>{label}</span></label>)}</div></div>
  return <div className="content-grid mt-6">
    <Panel title="إضافة مدير أو موظف" desc={canManage?'حساب دخول حقيقي مع فرع وصلاحيات واضحة':'يمكنك مشاهدة الفريق فقط؛ إدارة الحسابات تحتاج صلاحية إضافية.'}>{canManage&&<Btn label={creating?'إغلاق النموذج':'إضافة موظف'} icon={creating?XCircle:Plus} onClick={()=>setCreating(!creating)}/>} {canManage&&creating&&<form className="form-grid mt-list" onSubmit={create}><Field label="الاسم" name="name"/><Field label="البريد" name="email" type="email"/><Field label="الهاتف" name="phone" required={false}/><Field label="كلمة المرور" name="password" type="password" minLength={8}/><Field label="الدور"><select className="input" name="role" value={createRole} onChange={e=>setCreateRole(e.target.value)}><option value="brand_admin">مدير البراند</option><option value="manager">مدير فرع</option><option value="employee">موظف</option></select></Field><Field label="الفرع" required={false}><select className="input" name="branch_id"><option value="">جميع الفروع / غير محدد</option>{branchRows.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></Field><PermissionEditor key={`create-${createRole}`} defaults={roleDefaults(createRole)} roleNameValue={createRole}/><Btn busy={busy==='staff-create'} label="إنشاء الحساب" icon={UserCog}/></form>}</Panel>
    <Panel title="الفريق والصلاحيات">{staffRows.length?<div className="card-list">{staffRows.map((x:Row)=><div className="entity-card" key={x.id}><div className="avatar">{x.name?.[0]||'م'}</div><div className="entity-main"><b>{x.name}</b><small>{x.email} · {roleName(x.role)} · {branchRows.find(b=>b.id===x.branch_id)?.name||'جميع الفروع'}</small><small>{x.permissions?.['*']?'صلاحيات كاملة':`${Object.keys(x.permissions||{}).filter(k=>x.permissions[k]).length} صلاحيات مخصصة`}</small></div><span className={`badge ${x.is_active?'success':'muted-badge'}`}>{x.is_active?'فعال':'موقوف'}</span>{canManage&&<div className="button-row"><Btn label="تعديل" icon={Pencil} variant="secondary" onClick={()=>{setEditing(x);setEditingRole(x.role)}}/><Btn busy={busy===`staff-${x.id}`} label={x.is_active?'إيقاف':'تفعيل'} variant="secondary" onClick={()=>void toggle(x)}/></div>}</div>)}</div>:<Empty/>}</Panel>
    {canManage&&editing&&<Modal title="تعديل حساب الموظف" desc="ترك كلمة المرور فارغة يبقيها كما هي" onClose={()=>{setEditing(null);setEditingRole('')}}><form className="form-grid" onSubmit={update}><Field label="الاسم" name="name" defaultValue={editing.name}/><Field label="الهاتف" name="phone" defaultValue={editing.phone||''} required={false}/><Field label="الدور"><select className="input" name="role" value={editingRole||editing.role} onChange={e=>setEditingRole(e.target.value)}><option value="brand_admin">مدير البراند</option><option value="manager">مدير فرع</option><option value="employee">موظف</option></select></Field><Field label="الفرع" required={false}><select className="input" name="branch_id" defaultValue={editing.branch_id||''}><option value="">جميع الفروع / غير محدد</option>{branchRows.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></Field><Field label="كلمة مرور جديدة" name="password" type="password" required={false} minLength={8}/><Switch label="الحساب فعال" name="is_active" defaultChecked={editing.is_active}/><PermissionEditor key={`${editing.id}-${editingRole||editing.role}`} defaults={(editingRole||editing.role)===editing.role?(editing.effective_permissions||roleDefaults(editing.role)):roleDefaults(editingRole||editing.role)} roleNameValue={editingRole||editing.role}/><div className="button-row"><Btn busy={busy===`edit-staff-${editing.id}`} label="حفظ"/><Btn type="button" label="إلغاء" variant="secondary" onClick={()=>{setEditing(null);setEditingRole('')}}/></div></form></Modal>}
  </div>
}

function Loyalty({program,tiers,rewards,coupons,branches,brand,busy,run,reload,submit,capabilities}:any){
  const caps=capabilities||{}
  const [p,setP]=useState<any>(program),[editTier,setEditTier]=useState<Row|null>(null),[editReward,setEditReward]=useState<Row|null>(null),[editCoupon,setEditCoupon]=useState<Row|null>(null)
  useEffect(()=>setP({...emptyProgram,...program,rules:{...emptyProgram.rules,...(program.rules||{})}}),[program])
  async function persistProgram(){await run('program-save',()=>api(`/api/customers/program/${brand}`,{method:'PUT',body:JSON.stringify(p)}),'تم تحديث محرك الولاء');await reload()}
  async function save(e:React.FormEvent){e.preventDefault();await persistProgram()}
  function setWeekdayMultiplier(day:string,value:number){setP({...p,rules:{...(p.rules||{}),weekday_multipliers:{...(p.rules?.weekday_multipliers||{}),[day]:value}}})}
  function setBranchMultiplier(branchId:string,value:number){setP({...p,rules:{...(p.rules||{}),branch_multipliers:{...(p.rules?.branch_multipliers||{}),[branchId]:value}}})}
  function updateHappyHour(index:number,key:string,value:string|number){const hours=[...(p.rules?.happy_hours||[])];hours[index]={...hours[index],[key]:value};setP({...p,rules:{...(p.rules||{}),happy_hours:hours}})}
  function addHappyHour(){setP({...p,rules:{...(p.rules||{}),happy_hours:[...(p.rules?.happy_hours||[]),{start:'14:00',end:'17:00',multiplier:2}]}})}
  function removeHappyHour(index:number){setP({...p,rules:{...(p.rules||{}),happy_hours:(p.rules?.happy_hours||[]).filter((_:any,i:number)=>i!==index)}})}
  async function updateTier(e:React.FormEvent<HTMLFormElement>){e.preventDefault();if(!editTier)return;const fd=new FormData(e.currentTarget);await run(`tier-edit-${editTier.id}`,()=>api(`/api/management/tiers/${editTier.id}`,{method:'PATCH',body:JSON.stringify({name:fd.get('name'),rank:Number(fd.get('rank')),color:fd.get('color'),min_points:Number(fd.get('min_points')),min_spend:Number(fd.get('min_spend')),points_multiplier:Number(fd.get('points_multiplier')),is_active:fd.get('is_active')==='on'})}),'تم تحديث المستوى');setEditTier(null);await reload()}
  async function updateReward(e:React.FormEvent<HTMLFormElement>){e.preventDefault();if(!editReward)return;const fd=new FormData(e.currentTarget);await run(`reward-edit-${editReward.id}`,()=>api(`/api/management/rewards/${editReward.id}`,{method:'PATCH',body:JSON.stringify({name:fd.get('name'),description:fd.get('description')||null,points_cost:Number(fd.get('points_cost')),stock:fd.get('stock')===''?null:Number(fd.get('stock')),is_active:fd.get('is_active')==='on'})}),'تم تحديث المكافأة');setEditReward(null);await reload()}
  async function updateCoupon(e:React.FormEvent<HTMLFormElement>){e.preventDefault();if(!editCoupon)return;const fd=new FormData(e.currentTarget);await run(`coupon-edit-${editCoupon.id}`,()=>api(`/api/management/coupons/${editCoupon.id}`,{method:'PATCH',body:JSON.stringify({name:fd.get('name'),description:fd.get('description')||null,reward_type:fd.get('reward_type'),reward_value:Number(fd.get('reward_value')),starts_at:fd.get('starts_at')?new Date(String(fd.get('starts_at'))).toISOString():null,ends_at:fd.get('ends_at')?new Date(String(fd.get('ends_at'))).toISOString():null,max_redemptions:fd.get('max_redemptions')===''?null:Number(fd.get('max_redemptions')),per_customer_limit:Number(fd.get('per_customer_limit')),is_active:fd.get('is_active')==='on'})}),'تم تحديث الكوبون');setEditCoupon(null);await reload()}
  const summary:any[]=[
    [Gift,`${p.points_per_visit} نقطة`,'لكل زيارة',caps.points],
    [CreditCard,`${p.points_per_currency} نقطة`,'لكل وحدة عملة',caps.points],
    [Stamp,`${p.required_stamps} أختام`,p.stamp_reward_title,caps.stamps&&!caps.multi_stamp_cards],
    [Sparkles,`× ${p.rules?.global_multiplier||1}`,'المضاعف العام',caps.points],
    [Gift,`${p.birthday_bonus} نقطة`,'مكافأة الميلاد',caps.points],
    [Activity,p.points_expiry_days?`${p.points_expiry_days} يوم`:'بدون انتهاء','صلاحية النقاط',caps.points],
    [CreditCard,`${p.cashback_percent||0}%`,'Cashback',caps.cashback],
  ]
  return <>
    <div className="content-grid mt-6">
      <Panel title="قواعد محرك الولاء" desc="يعرض فقط القواعد المفعلة لهذا البراند؛ البيانات المخفية تبقى محفوظة للمستقبل">
        <form className="form-grid" onSubmit={save}>
          {caps.points&&<><div className="two-col"><NumberInput label="نقاط كل زيارة" value={p.points_per_visit} onChange={(v:number)=>setP({...p,points_per_visit:v})}/><NumberInput label="نقاط كل وحدة عملة" value={p.points_per_currency} onChange={(v:number)=>setP({...p,points_per_currency:v})}/></div><div className="two-col"><NumberInput label="نقاط المكافأة التلقائية" value={p.reward_points} min={1} onChange={(v:number)=>setP({...p,reward_points:v})}/><Field label="اسم مكافأة النقاط"><input className="input" value={p.reward_title} onChange={e=>setP({...p,reward_title:e.target.value})}/></Field></div><div className="two-col"><NumberInput label="مكافأة عيد الميلاد" value={p.birthday_bonus} onChange={(v:number)=>setP({...p,birthday_bonus:v})}/><NumberInput label="مكافأة الإحالة" value={p.referral_bonus} onChange={(v:number)=>setP({...p,referral_bonus:v})}/></div><div className="two-col"><NumberInput label="انتهاء النقاط بعد (يوم)" value={p.points_expiry_days??''} required={false} onChange={(v:any)=>setP({...p,points_expiry_days:v===''?null:v})}/><NumberInput label="الحد اليومي للنقاط" value={p.daily_points_cap??''} required={false} onChange={(v:any)=>setP({...p,daily_points_cap:v===''?null:v})}/></div></>}
          {caps.cashback&&<NumberInput label="نسبة Cashback %" value={p.cashback_percent} onChange={(v:number)=>setP({...p,cashback_percent:v})}/>} 
          {caps.stamps&&caps.multi_stamp_cards&&<div className="mode-note"><Stamp/><div><b>الأختام مفصولة إلى بطاقات مستقلة</b><span>عدد الأختام ومكافأة القهوة والسويت وغيرها تُدار من قسم «بطاقات الأختام» وليس من هذه الصفحة.</span></div></div>}
          {caps.stamps&&!caps.multi_stamp_cards&&<div className="two-col"><NumberInput label="عدد الأختام للمكافأة" value={p.required_stamps} min={1} onChange={(v:number)=>setP({...p,required_stamps:v})}/><Field label="اسم مكافأة الأختام"><input className="input" value={p.stamp_reward_title} onChange={e=>setP({...p,stamp_reward_title:e.target.value})}/></Field></div>}
          <label className="switch-row"><input type="checkbox" checked={p.enabled} onChange={e=>setP({...p,enabled:e.target.checked})}/><span>تشغيل برنامج الولاء</span></label>
          {(caps.points||!caps.multi_stamp_cards)&&<label className="switch-row"><input type="checkbox" checked={p.allow_manual_adjustment} onChange={e=>setP({...p,allow_manual_adjustment:e.target.checked})}/><span>السماح بالتعديل اليدوي</span></label>}
          {caps.points&&<label className="switch-row"><input type="checkbox" checked={!!p.rules?.auto_convert_points} onChange={e=>setP({...p,rules:{...(p.rules||{}),auto_convert_points:e.target.checked}})}/><span>تحويل النقاط إلى مكافأة تلقائيًا</span></label>}
          <Btn busy={busy==='program-save'} label="حفظ قواعد الولاء"/>
        </form>
      </Panel>
      <Panel title="ملخص القواعد النشطة"><div className="rule-summary">{summary.filter(x=>x[3]).map(([Icon,title,text]:any)=><Rule key={`${title}-${text}`} icon={Icon} title={title} text={text}/>)}</div>{caps.stamps&&caps.multi_stamp_cards&&<div className="quick-card compact-quick"><Stamp/><b>بطاقات الأختام مستقلة</b><span>تُدار من قسم بطاقات الأختام، ولكل بطاقة رصيد ومكافأة وتصميم منفصل.</span></div>}</Panel>
    </div>
    {caps.points&&<Panel title="المضاعفات الذكية" desc="يمكن تطبيق مضاعفات حسب اليوم أو الفرع أو نافذة زمنية، ويحسبها السيرفر تلقائيًا" className="mt-5"><div className="form-grid"><div className="form-divider">مضاعفات أيام الأسبوع</div><div className="weekday-grid">{[['0','الاثنين'],['1','الثلاثاء'],['2','الأربعاء'],['3','الخميس'],['4','الجمعة'],['5','السبت'],['6','الأحد']].map(([key,label])=><label className="field" key={key}><span>{label}</span><input className="input" type="number" min="1" max="20" step="0.1" value={p.rules?.weekday_multipliers?.[key]??1} onChange={e=>setWeekdayMultiplier(key,Number(e.target.value||1))}/></label>)}</div><div className="form-divider">مضاعفات الفروع</div>{branches.length?<div className="weekday-grid">{branches.filter((x:Row)=>x.is_active).map((x:Row)=><label className="field" key={x.id}><span>{x.name}</span><input className="input" type="number" min="1" max="20" step="0.1" value={p.rules?.branch_multipliers?.[x.id]??1} onChange={e=>setBranchMultiplier(x.id,Number(e.target.value||1))}/></label>)}</div>:<p className="muted text-sm">أنشئ فرعًا أولًا لإضافة مضاعف خاص به.</p>}<div className="form-divider">الساعات المضاعفة</div><div className="happy-hour-list">{(p.rules?.happy_hours||[]).map((window:Row,index:number)=><div className="happy-hour-row" key={index}><Field label="من"><input className="input" type="time" value={window.start||''} onChange={e=>updateHappyHour(index,'start',e.target.value)}/></Field><Field label="إلى"><input className="input" type="time" value={window.end||''} onChange={e=>updateHappyHour(index,'end',e.target.value)}/></Field><Field label="المضاعف"><input className="input" type="number" min="1" max="20" step="0.1" value={window.multiplier||1} onChange={e=>updateHappyHour(index,'multiplier',Number(e.target.value||1))}/></Field><Btn type="button" label="حذف" icon={XCircle} variant="secondary" onClick={()=>removeHappyHour(index)}/></div>)}{!(p.rules?.happy_hours||[]).length&&<p className="muted text-sm">لا توجد ساعات مضاعفة.</p>}</div><div className="button-row"><Btn type="button" label="إضافة فترة" icon={Plus} variant="secondary" onClick={addHappyHour}/><Btn type="button" busy={busy==='program-save'} label="حفظ المضاعفات" onClick={persistProgram}/></div></div></Panel>}
    <div className="triple-grid mt-5">
      {caps.tiers&&<Panel title="المستويات"><form className="form-grid compact-form" onSubmit={(e)=>submit('/api/management/tiers',e,{brand_id:brand,benefits:{}},'POST','تم إنشاء المستوى')}><Field label="الاسم" name="name"/><div className="two-col"><Field label="الترتيب" name="rank" type="number" defaultValue="0"/><Field label="اللون" name="color" type="color" defaultValue="#C6FF4A"/></div><div className="two-col"><Field label="أقل نقاط" name="min_points" type="number" defaultValue="0"/><Field label="أقل إنفاق" name="min_spend" type="number" defaultValue="0"/></div><Field label="مضاعف النقاط" name="points_multiplier" type="number" defaultValue="1" min="1"/><Btn busy={busy==='/api/management/tiers'} label="إضافة مستوى" icon={Plus}/></form><div className="compact-list mt-list">{tiers.map((x:Row)=><div key={x.id}><span className="color-dot" style={{background:x.color}}/><div className="entity-main"><b>{x.name}</b><small>من {x.min_points} نقطة · ×{x.points_multiplier}</small></div><button type="button" className="text-btn" onClick={()=>setEditTier(x)}>تعديل</button></div>)}</div></Panel>}
      {caps.points&&caps.rewards&&<Panel title="مكافآت النقاط"><form className="form-grid compact-form" onSubmit={(e)=>submit('/api/management/rewards',e,{brand_id:brand},'POST','تم إنشاء المكافأة')}><Field label="اسم المكافأة" name="name"/><Field label="الوصف" name="description" required={false}/><div className="two-col"><Field label="تكلفة النقاط" name="points_cost" type="number" defaultValue="100"/><Field label="المخزون" name="stock" type="number" required={false}/></div><Btn busy={busy==='/api/management/rewards'} label="إضافة مكافأة" icon={Plus}/></form><div className="compact-list mt-list">{rewards.map((x:Row)=><div key={x.id}><Gift/><div className="entity-main"><b>{x.name}</b><small>{x.points_cost} نقطة · المخزون {x.stock??'مفتوح'}</small></div><button type="button" className="text-btn" onClick={()=>setEditReward(x)}>تعديل</button></div>)}</div></Panel>}
      {caps.coupons&&<Panel title="الكوبونات"><form className="form-grid compact-form" onSubmit={(e)=>submit('/api/management/coupons',e,{brand_id:brand},'POST','تم إنشاء الكوبون')}><div className="two-col"><Field label="الرمز" name="code" placeholder="WELCOME20"/><Field label="الاسم" name="name"/></div><Field label="نوع الميزة"><select className="input" name="reward_type">{caps.points&&<option value="points">نقاط</option>}{caps.stamps&&<option value="stamps">أختام</option>}<option value="discount_percent">خصم نسبة</option><option value="discount_amount">خصم مبلغ</option><option value="free_item">منتج مجاني</option></select></Field><div className="two-col"><Field label="القيمة" name="reward_value" type="number" defaultValue="10"/><Field label="حد كل عميل" name="per_customer_limit" type="number" defaultValue="1"/></div><div className="two-col"><Field label="يبدأ في" name="starts_at" type="datetime-local" required={false}/><Field label="ينتهي في" name="ends_at" type="datetime-local" required={false}/></div><Field label="إجمالي مرات الاستخدام" name="max_redemptions" type="number" required={false}/><Btn busy={busy==='/api/management/coupons'} label="إنشاء كوبون" icon={Stamp}/></form><div className="compact-list mt-list">{coupons.map((x:Row)=><div key={x.id}><Stamp/><div className="entity-main"><b>{x.code} · {x.name}</b><small>{couponTypeName(x.reward_type)} {x.reward_value} · استخدم {x.redemption_count}</small></div><button type="button" className="text-btn" onClick={()=>setEditCoupon(x)}>تعديل</button></div>)}</div></Panel>}
    </div>
    {editTier&&caps.tiers&&<Modal title="تعديل المستوى" onClose={()=>setEditTier(null)}><form className="form-grid" onSubmit={updateTier}><Field label="الاسم" name="name" defaultValue={editTier.name}/><Field label="الترتيب" name="rank" type="number" defaultValue={editTier.rank}/><Field label="اللون" name="color" type="color" defaultValue={editTier.color}/><Field label="أقل نقاط" name="min_points" type="number" defaultValue={editTier.min_points}/><Field label="أقل إنفاق" name="min_spend" type="number" defaultValue={editTier.min_spend}/><Field label="المضاعف" name="points_multiplier" type="number" defaultValue={editTier.points_multiplier}/><Switch label="المستوى فعال" name="is_active" defaultChecked={editTier.is_active}/><Btn busy={busy===`tier-edit-${editTier.id}`} label="حفظ"/></form></Modal>}
    {editReward&&caps.points&&caps.rewards&&<Modal title="تعديل المكافأة" onClose={()=>setEditReward(null)}><form className="form-grid" onSubmit={updateReward}><Field label="الاسم" name="name" defaultValue={editReward.name}/><Field label="الوصف" name="description" defaultValue={editReward.description||''} required={false}/><Field label="تكلفة النقاط" name="points_cost" type="number" defaultValue={editReward.points_cost}/><Field label="المخزون" name="stock" type="number" defaultValue={editReward.stock??''} required={false}/><Switch label="المكافأة فعالة" name="is_active" defaultChecked={editReward.is_active}/><Btn busy={busy===`reward-edit-${editReward.id}`} label="حفظ"/></form></Modal>}
    {editCoupon&&caps.coupons&&<Modal title="تعديل الكوبون" onClose={()=>setEditCoupon(null)}><form className="form-grid" onSubmit={updateCoupon}><Field label="الاسم" name="name" defaultValue={editCoupon.name}/><Field label="الوصف" name="description" defaultValue={editCoupon.description||''} required={false}/><Field label="نوع الميزة"><select className="input" name="reward_type" defaultValue={editCoupon.reward_type}>{caps.points&&<option value="points">نقاط</option>}{caps.stamps&&<option value="stamps">أختام</option>}<option value="discount_percent">خصم نسبة</option><option value="discount_amount">خصم مبلغ</option><option value="free_item">منتج مجاني</option></select></Field><Field label="القيمة" name="reward_value" type="number" defaultValue={editCoupon.reward_value}/><div className="two-col"><Field label="يبدأ في" name="starts_at" type="datetime-local" defaultValue={dateTimeInput(editCoupon.starts_at)} required={false}/><Field label="ينتهي في" name="ends_at" type="datetime-local" defaultValue={dateTimeInput(editCoupon.ends_at)} required={false}/></div><Field label="إجمالي مرات الاستخدام" name="max_redemptions" type="number" defaultValue={editCoupon.max_redemptions??''} required={false}/><Field label="حد كل عميل" name="per_customer_limit" type="number" defaultValue={editCoupon.per_customer_limit}/><Switch label="الكوبون فعال" name="is_active" defaultChecked={editCoupon.is_active}/><Btn busy={busy===`coupon-edit-${editCoupon.id}`} label="حفظ"/></form></Modal>}
  </>
}

function WalletStudio({design,customers,programs,cardTemplates,brand,brandInfo,busy,run,reload,issuePass}:any){
  const templates=safeArray<Row>(cardTemplates)
  const publishedTemplates=templates.filter(x=>x.status==='published')
  const [selectedTemplateId,setSelectedTemplateId]=useState('')
  const selectedTemplate=publishedTemplates.find(x=>x.id===selectedTemplateId)||publishedTemplates.find(x=>x.is_default)||publishedTemplates[0]||null
  const [d,setD]=useState<any>({...emptyDesign,...design,fields:{...emptyDesign.fields,...(design.fields||{})}})
  useEffect(()=>setD({...emptyDesign,...design,fields:{...emptyDesign.fields,...(design.fields||{})}}),[design])
  useEffect(()=>{
    if(!publishedTemplates.some(x=>x.id===selectedTemplateId))setSelectedTemplateId(publishedTemplates.find(x=>x.is_default)?.id||publishedTemplates[0]?.id||'')
  },[cardTemplates,selectedTemplateId])
  async function save(){await run('design-save',()=>api(`/api/wallet/design/${brand}`,{method:'PUT',body:JSON.stringify(d)}),'تم حفظ الإعدادات الافتراضية القديمة');reload()}
  async function publish(){await run('design-publish',()=>api(`/api/wallet/design/${brand}/publish`,{method:'POST'}),'تم نشر الإعدادات الافتراضية القديمة');reload()}
  async function asset(e:React.ChangeEvent<HTMLInputElement>,kind:'logo'|'hero'|'background'|'strip'){const file=e.target.files?.[0];if(!file)return;const fd=new FormData();fd.append('kind',kind);fd.append('file',file);await run(`asset-${kind}`,()=>api(`/api/wallet/design/${brand}/asset`,{method:'POST',body:fd}),'تم رفع صورة الإعداد الافتراضي');e.target.value='';reload()}
  const caps=brandInfo?.capabilities||{}
  const fieldOptions=[['show_points','إظهار النقاط',caps.points],['show_stamps','إظهار الأختام',caps.stamps],['show_rewards','إظهار المكافآت',caps.rewards],['show_tier','إظهار المستوى',caps.tiers],['show_visits','إظهار الزيارات',true]]
  return <>
    <div className="studio-grid mt-6">
      <Panel title="البطاقات المنشورة" desc="تصميم كل بطاقة وإضافة برامج القهوة والحلى يتم من قسم «البطاقات». هنا تراجع النتيجة وتصدرها للعملاء.">
        {publishedTemplates.length?<div className="wallet-template-selector">{publishedTemplates.map((x:Row)=><button type="button" key={x.id} onClick={()=>setSelectedTemplateId(x.id)} className={selectedTemplate?.id===x.id?'active':''}><CreditCard size={18}/><span><b>{x.name}</b><small>{safeArray<Row>(x.programs).map(p=>p.name).join(' · ')||'بدون برامج'}</small></span>{x.is_default&&<em>افتراضية</em>}</button>)}</div>:<div className="warning-box"><CreditCard/><h3>لا توجد بطاقة منشورة</h3><p>أنشئ قالبًا من قسم البطاقات، اختر برامج الأختام ثم اضغط «نشر».</p></div>}
        {selectedTemplate&&<div className="mt-5"><WalletCard design={selectedTemplate} brand={brandInfo} programs={selectedTemplate.programs||[]}/><div className="template-program-chips mt-3">{safeArray<Row>(selectedTemplate.programs).map(p=><span key={p.id}>{stampIcon(p.stamp_icon)} {p.name} · {p.required_stamps}</span>)}</div></div>}
      </Panel>
      <div className="studio-side">
        <Panel title="إصدار بطاقات العملاء" desc="العميل يحصل على بطاقة واحدة حسب القالب المربوط بحسابه.">
          <div className="compact-list scroll-list">{safeArray<Row>(customers).map((c:Row)=><div key={c.id}><div className="entity-main"><b>{c.name}</b><small>{caps.points?`${c.points} نقطة · `:''}{caps.stamps?`${c.stamps} ختم · `:''}{c.membership_code}</small></div><Btn busy={busy===`pass-${c.id}`} label="إصدار أو تحديث" icon={WalletCards} variant="secondary" onClick={()=>issuePass(c)}/></div>)}{!safeArray<Row>(customers).length&&<Empty/>}</div>
        </Panel>
        <Panel title="ملاحظات مهمة">
          <div className="rules-box"><Rule icon={CreditCard} title="بطاقة واحدة" text="كل عميل مرتبط بقالب بطاقة واحد، وداخله عدة برامج أختام."/><Rule icon={Upload} title="النشر مطلوب" text="تعديلات البطاقة تبقى مسودة حتى تنشرها من قسم البطاقات."/><Rule icon={ShieldCheck} title="الشهادة مركزية" text="مدير المنصة فقط يرفع شهادة Apple؛ مدير البراند لا يراها."/></div>
        </Panel>
      </div>
    </div>
    <details className="legacy-settings mt-5">
      <summary>الإعدادات الافتراضية القديمة للتوافق مع البطاقات السابقة</summary>
      <div className="studio-grid mt-4">
        <Panel title="الإعدادات الافتراضية" desc="تُستخدم فقط للبطاقات القديمة التي لم تُنقل إلى قالب بطاقة جديد.">
          <div className="form-grid">
            <div className="two-col"><ColorInput label="الخلفية" value={d.background_color} onChange={(v:string)=>setD({...d,background_color:v})}/><ColorInput label="النص" value={d.foreground_color} onChange={(v:string)=>setD({...d,foreground_color:v})}/></div>
            <ColorInput label="العناوين" value={d.label_color} onChange={(v:string)=>setD({...d,label_color:v})}/>
            <div className="two-col"><Field label="اسم الشعار"><input className="input" value={d.logo_text} onChange={e=>setD({...d,logo_text:e.target.value})}/></Field><Field label="عنوان البطاقة"><input className="input" value={d.card_title} onChange={e=>setD({...d,card_title:e.target.value})}/></Field></div>
            <div className="two-col"><Field label="نمط التصميم"><select className="input" value={d.layout_style} onChange={e=>setD({...d,layout_style:e.target.value})}><option value="classic">كلاسيكي</option><option value="visual">صورة كاملة</option><option value="minimal">بسيط</option></select></Field><NumberInput label="تعتيم الخلفية %" value={d.overlay_opacity} min={0} onChange={(v:number)=>setD({...d,overlay_opacity:Math.min(90,v)})}/></div>
            <div className="asset-grid four"><AssetUpload label="رفع الشعار" busy={busy==='asset-logo'} onChange={(e:any)=>asset(e,'logo')}/><AssetUpload label="الصورة العلوية" busy={busy==='asset-hero'} onChange={(e:any)=>asset(e,'hero')}/><AssetUpload label="خلفية كاملة" busy={busy==='asset-background'} onChange={(e:any)=>asset(e,'background')}/><AssetUpload label="شريط Apple" busy={busy==='asset-strip'} onChange={(e:any)=>asset(e,'strip')}/></div>
            <Field label="نوع الباركود"><select className="input" value={d.barcode_format} onChange={e=>setD({...d,barcode_format:e.target.value})}><option value="PKBarcodeFormatQR">QR</option><option value="PKBarcodeFormatPDF417">PDF417</option><option value="PKBarcodeFormatAztec">Aztec</option><option value="PKBarcodeFormatCode128">Code 128</option></select></Field>
            <Field label="الشروط والأحكام" required={false}><textarea className="input min-h-24" value={d.terms||''} onChange={e=>setD({...d,terms:e.target.value})}/></Field>
            <div className="switch-grid">{fieldOptions.filter((x:any)=>x[2]).map(([key,label]:any)=><label className="switch-row" key={key}><input type="checkbox" checked={!!d.fields[key]} onChange={e=>setD({...d,fields:{...d.fields,[key]:e.target.checked}})}/><span>{label}</span></label>)}</div>
            <div className="button-row"><Btn busy={busy==='design-save'} label="حفظ الإعداد القديم" onClick={save}/><Btn busy={busy==='design-publish'} label="نشر الإعداد القديم" icon={Upload} variant="secondary" onClick={publish}/></div>
          </div>
        </Panel>
        <Panel title="معاينة الإعداد القديم"><WalletCard design={d} brand={brandInfo} programs={programs}/></Panel>
      </div>
    </details>
  </>
}

function AssetUpload({label,busy,onChange}:any){return <label className="asset-upload"><Upload size={18}/><span>{busy?'جاري الرفع...':label}</span><input type="file" accept="image/png,image/jpeg,image/webp" onChange={onChange} disabled={busy}/></label>}

function Campaigns({rows,templates,customers,branches,brand,busy,run,reload,capabilities}:any){
  const caps=capabilities||{}
  const [name,setName]=useState('')
  const [title,setTitle]=useState('')
  const [body,setBody]=useState('')
  const [channel,setChannel]=useState('in_app')
  const [audience,setAudience]=useState('all')
  const [filter,setFilter]=useState('')
  const [selectedCustomers,setSelectedCustomers]=useState<string[]>([])
  const [recurrence,setRecurrence]=useState('none')
  const [editing,setEditing]=useState<Row|null>(null)

  function chooseTemplate(id:string){const t=templates.find((x:Row)=>x.id===id);if(t){setTitle(t.title);setBody(t.body);setChannel(t.channel)}}
  function audienceFilter(){
    if(audience==='tier')return {tier:filter}
    if(audience==='min_points')return {min_points:Number(filter||0)}
    if(audience==='inactive_days')return {days:Number(filter||30)}
    if(audience==='branch')return {branch_id:filter}
    if(audience==='selected')return {customer_ids:selectedCustomers}
    return {}
  }
  function changeAudience(value:string){setAudience(value);setFilter('');setSelectedCustomers([])}
  function toggleCustomer(id:string){setSelectedCustomers(current=>current.includes(id)?current.filter(x=>x!==id):[...current,id])}
  async function create(e:React.FormEvent<HTMLFormElement>){
    e.preventDefault();const form=e.currentTarget;const fd=new FormData(form);const sendNow=fd.get('send_now')==='on';const rawSchedule=String(fd.get('scheduled_at')||'')
    await run('campaign-create',()=>api('/api/notifications/campaigns',{method:'POST',body:JSON.stringify({brand_id:brand,name,title,body,channel,audience_type:audience,audience_filter:audienceFilter(),recurrence,scheduled_at:rawSchedule?new Date(rawSchedule).toISOString():null,send_now:sendNow})}),'تم إنشاء الحملة')
    setName('');setTitle('');setBody('');setChannel('in_app');setAudience('all');setFilter('');setSelectedCustomers([]);setRecurrence('none');form.reset();await reload()
  }
  async function createTemplate(e:React.FormEvent<HTMLFormElement>){e.preventDefault();const form=e.currentTarget;const fd=new FormData(form);await run('template-create',()=>api('/api/notifications/templates',{method:'POST',body:JSON.stringify({brand_id:brand,name:fd.get('template_name'),title:fd.get('template_title'),body:fd.get('template_body'),channel:fd.get('template_channel')})}),'تم حفظ قالب الإشعار');form.reset();await reload()}
  async function send(x:Row){await run(`send-${x.id}`,()=>api(`/api/notifications/campaigns/${x.id}/send`,{method:'POST'}),'تم وضع الحملة في قائمة الإرسال');await reload()}
  async function cancel(x:Row){await run(`cancel-${x.id}`,()=>api(`/api/notifications/campaigns/${x.id}/cancel`,{method:'POST'}),'تم إلغاء الحملة');await reload()}
  async function toggleTemplate(x:Row){await run(`template-${x.id}`,()=>api(`/api/notifications/templates/${x.id}/toggle`,{method:'PATCH'}),x.is_active?'تم إيقاف القالب':'تم تفعيل القالب');await reload()}
  async function update(e:React.FormEvent<HTMLFormElement>){e.preventDefault();if(!editing)return;const fd=new FormData(e.currentTarget);await run(`campaign-edit-${editing.id}`,()=>api(`/api/notifications/campaigns/${editing.id}`,{method:'PATCH',body:JSON.stringify({name:fd.get('name'),title:fd.get('title'),body:fd.get('body'),scheduled_at:fd.get('scheduled_at')?new Date(String(fd.get('scheduled_at'))).toISOString():null})}),'تم تحديث الحملة');setEditing(null);await reload()}

  return <>
    <div className="content-grid mt-6">
      <Panel title="إنشاء حملة" desc="تعمل عبر Worker مستقل ولا تظهر ناجحة إلا بعد التسليم الفعلي">
        <form className="form-grid" onSubmit={create}>
          {templates.length>0&&<Field label="استخدام قالب محفوظ" required={false}><select className="input" defaultValue="" onChange={e=>chooseTemplate(e.target.value)}><option value="">بدون قالب</option>{templates.filter((x:Row)=>x.is_active).map((x:Row)=><option key={x.id} value={x.id}>{x.name}</option>)}</select></Field>}
          <Field label="اسم الحملة"><input className="input" value={name} onChange={e=>setName(e.target.value)} required/></Field>
          <Field label="عنوان الرسالة"><input className="input" value={title} onChange={e=>setTitle(e.target.value)} required/></Field>
          <Field label="نص الرسالة"><textarea className="input min-h-28" value={body} onChange={e=>setBody(e.target.value)} required/></Field>
          <div className="two-col"><Field label="القناة"><select className="input" value={channel} onChange={e=>setChannel(e.target.value)}><option value="in_app">داخل صندوق العميل</option><option value="wallet_push">تحديث Apple Wallet</option><option value="email">Email</option><option value="sms">SMS</option><option value="webhook">Webhook</option></select></Field><Field label="الجمهور"><select className="input" value={audience} onChange={e=>changeAudience(e.target.value)}><option value="all">جميع العملاء</option><option value="birthday">أعياد الميلاد اليوم</option>{caps.tiers&&<option value="tier">مستوى محدد</option>}{caps.points&&<option value="min_points">حد أدنى للنقاط</option>}<option value="inactive_days">غير نشطين منذ مدة</option><option value="branch">فرع محدد</option>{caps.rewards&&<option value="rewards_ready">لديهم مكافأة جاهزة</option>}<option value="selected">عملاء محددون</option></select></Field></div>
          {audience==='tier'&&<Field label="اسم المستوى"><input className="input" value={filter} onChange={e=>setFilter(e.target.value)} required/></Field>}
          {audience==='min_points'&&<Field label="الحد الأدنى للنقاط"><input className="input" type="number" min="0" value={filter} onChange={e=>setFilter(e.target.value)} required/></Field>}
          {audience==='inactive_days'&&<Field label="عدد أيام عدم النشاط"><input className="input" type="number" min="1" value={filter} onChange={e=>setFilter(e.target.value)} required/></Field>}
          {audience==='branch'&&<Field label="الفرع المستهدف"><select className="input" value={filter} onChange={e=>setFilter(e.target.value)} required><option value="">اختر الفرع</option>{branches.filter((x:Row)=>x.is_active).map((x:Row)=><option key={x.id} value={x.id}>{x.name}</option>)}</select></Field>}
          {audience==='selected'&&<Field label={`العملاء المحددون (${selectedCustomers.length})`}><div className="selection-list">{customers.filter((x:Row)=>x.is_active).map((x:Row)=><label key={x.id}><input type="checkbox" checked={selectedCustomers.includes(x.id)} onChange={()=>toggleCustomer(x.id)}/><span><b>{x.name}</b><small>{x.phone}</small></span></label>)}{!customers.length&&<p className="muted">لا يوجد عملاء داخل البراند</p>}</div></Field>}
          <div className="two-col"><Field label="وقت الإرسال" name="scheduled_at" type="datetime-local" required={false}/><Field label="التكرار"><select className="input" value={recurrence} onChange={e=>setRecurrence(e.target.value)}><option value="none">مرة واحدة</option><option value="daily">يوميًا</option><option value="weekly">أسبوعيًا</option><option value="monthly">شهريًا</option></select></Field></div>
          <Switch label="إرسال الآن بعد الحفظ" name="send_now"/>
          <Btn busy={busy==='campaign-create'} disabled={audience==='selected'&&!selectedCustomers.length} label="إنشاء الحملة" icon={Bell}/>
        </form>
      </Panel>
      <Panel title="الحملات وحالة التسليم">{rows.length?<div className="campaign-list">{rows.map((x:Row)=><div className="campaign-card" key={x.id}><div className="campaign-head"><div><b>{x.name}</b><small>{x.title} · {channelName(x.channel)} · {audienceName(x.audience_type)}</small></div><span className={`badge status-${x.status}`}>{statusName(x.status)}</span></div><div className="delivery-bar"><div style={{width:`${x.total_recipients?Math.round((x.sent_count/x.total_recipients)*100):0}%`}}/></div><div className="delivery-stats"><span>المستهدفون <b>{x.total_recipients}</b></span><span>نجح <b>{x.sent_count}</b></span><span>فشل <b>{x.failed_count}</b></span><span>تجاوز <b>{x.skipped_count}</b></span>{x.recurrence!=='none'&&<span>التكرار <b>{recurrenceName(x.recurrence)}</b></span>}</div><div className="button-row">{['draft','scheduled'].includes(x.status)&&<Btn label="تعديل" icon={Pencil} variant="secondary" onClick={()=>setEditing(x)}/>} {['draft','scheduled','queued','failed','partially_completed'].includes(x.status)&&<Btn busy={busy===`send-${x.id}`} label="إرسال الآن" icon={Send} onClick={()=>send(x)}/>} {!['completed','partially_completed','cancelled'].includes(x.status)&&<Btn busy={busy===`cancel-${x.id}`} label="إلغاء" icon={XCircle} variant="secondary" onClick={()=>cancel(x)}/>}</div></div>)}</div>:<Empty/>}</Panel>
    </div>
    <div className="content-grid mt-5"><Panel title="إنشاء قالب إشعار"><form className="form-grid" onSubmit={createTemplate}><Field label="اسم القالب" name="template_name"/><Field label="العنوان" name="template_title"/><Field label="النص"><textarea className="input min-h-24" name="template_body" required/></Field><Field label="القناة"><select className="input" name="template_channel"><option value="in_app">داخل المنصة</option><option value="wallet_push">Apple Wallet</option><option value="email">Email</option><option value="sms">SMS</option><option value="webhook">Webhook</option></select></Field><Btn busy={busy==='template-create'} label="حفظ القالب" icon={Save}/></form></Panel><Panel title="القوالب المحفوظة">{templates.length?<div className="compact-list">{templates.map((x:Row)=><div key={x.id}><Bell/><div className="entity-main"><b>{x.name}</b><small>{x.title} · {channelName(x.channel)}</small></div><button type="button" className="text-btn" onClick={()=>toggleTemplate(x)}>{x.is_active?'إيقاف':'تفعيل'}</button></div>)}</div>:<Empty/>}</Panel></div>
    {editing&&<Modal title="تعديل الحملة" desc="يمكن تعديل المسودة أو الحملة المجدولة قبل بدء الإرسال" onClose={()=>setEditing(null)}><form className="form-grid" onSubmit={update}><Field label="اسم الحملة" name="name" defaultValue={editing.name}/><Field label="العنوان" name="title" defaultValue={editing.title}/><Field label="النص"><textarea className="input min-h-28" name="body" defaultValue={editing.body}/></Field><Field label="وقت الإرسال" name="scheduled_at" type="datetime-local" required={false}/><Btn busy={busy===`campaign-edit-${editing.id}`} label="حفظ التعديل"/></form></Modal>}
  </>
}
function Audit({rows}:any){return <Panel title="سجل التدقيق" desc="آخر 300 عملية داخل البراند" className="mt-6"><div className="table-wrap"><table><thead><tr><th>الوقت</th><th>العملية</th><th>النوع</th><th>المعرف</th><th>IP</th></tr></thead><tbody>{rows.map((x:Row)=><tr key={x.id}><td>{new Date(x.created_at).toLocaleString('ar-QA')}</td><td>{actionName(x.action)}</td><td>{x.entity_type}</td><td className="mono">{x.entity_id||'—'}</td><td>{x.ip_address||'—'}</td></tr>)}</tbody></table>{!rows.length&&<Empty/>}</div></Panel>}

function PlatformWallet({credential,busy,run,reload}:any){async function upload(e:React.FormEvent<HTMLFormElement>){e.preventDefault();const form=e.currentTarget;const fd=new FormData(form);await run('cert-upload',()=>api('/api/wallet/platform/credential',{method:'POST',body:fd}),'تم التحقق من الشهادة وتفعيلها مركزيًا');form.reset();reload()}return <div className="content-grid mt-6"><Panel title="رفع الشهادة المركزية" desc="تُحفظ مشفرة في السيرفر ولا يمكن لمديري البراندات رؤيتها"><form className="form-grid" onSubmit={upload}><Field label="شهادة Pass Type (.p12)" name="p12_file" type="file" accept=".p12"/><Field label="شهادة Apple WWDR (.cer أو .pem)" name="wwdr_file" type="file" accept=".cer,.pem"/><Field label="كلمة مرور .p12" name="password" type="password"/><Field label="Pass Type Identifier" name="pass_type_identifier" placeholder="pass.com.company.loyalyn"/><Field label="Team Identifier" name="team_identifier"/><Field label="Organization Name" name="organization_name" defaultValue="Loyalyn"/><Btn busy={busy==='cert-upload'} label="تحقق وارفع الشهادة" icon={ShieldCheck}/></form></Panel><Panel title="حالة Apple Wallet">{credential?.configured?<div className="credential-card"><div className="credential-icon"><ShieldCheck/></div><h3>الشهادة مفعلة</h3><p>{credential.filename}</p><Info label="Pass Type" value={credential.pass_type_identifier}/><Info label="Team ID" value={credential.team_identifier}/><Info label="الجهة" value={credential.organization_name}/><Info label="تاريخ الانتهاء" value={credential.expires_at?new Date(credential.expires_at).toLocaleDateString('ar-QA'):'غير متاح'}/><Info label="الحالة" value={credential.status}/></div>:<div className="warning-box"><ShieldCheck/><h3>لم تُرفع الشهادة بعد</h3><p>مديرو البراندات يستطيعون التصميم، لكن لا يمكن إصدار ملف pkpass حتى ترفع الشهادة هنا.</p></div>}</Panel></div>}

function WalletCard({design,brand,programs=[]}:any){
  const fields={...emptyDesign.fields,...(design.fields||{})}
  const resolveAsset=(value:string|undefined,kind:'logo'|'hero'|'background')=>{
    if(!value)return ''
    if(value.startsWith('http://')||value.startsWith('https://')||value.startsWith('data:'))return value
    if(design.id)return `${API}/api/cards/public/assets/${design.id}/${kind}`
    return `${API}/api/wallet/public/assets/${brand?.id}/${kind}`
  }
  const hero=resolveAsset(design.hero_url,'hero')
  const logo=resolveAsset(design.logo_url,'logo')
  const background=resolveAsset(design.background_image_url,'background')
  const overlay=Math.max(0,Math.min(90,Number(design.overlay_opacity||0)))/100
  const style:any={backgroundColor:design.background_color||'#111827',color:design.foreground_color||'#FFFFFF'}
  if(background)style.backgroundImage=`linear-gradient(rgba(0,0,0,${overlay}),rgba(0,0,0,${overlay})),url(${background})`
  const rows=safeArray<Row>(programs).slice(0,3)
  const sample=[4,2,1]
  return <div className={`wallet-preview loyalty-card-preview layout-${design.layout_style||'classic'}`} style={style}>
    {hero&&<img className="wallet-hero-image" src={hero} alt=""/>}
    <div className="wallet-header"><div><small style={{color:design.label_color||'#C6FF4A'}}>MEMBER CARD</small><h3>{design.logo_text||brand?.name||'LOYALYN'}</h3></div>{logo?<img className="wallet-logo-image" src={logo} alt="شعار البراند"/>:<div className="wallet-logo">{(brand?.name||'L')[0]}</div>}</div>
    <div className="wallet-member-line"><div><small style={{color:design.label_color||'#C6FF4A'}}>{design.card_title||'بطاقة الولاء'}</small><b>أحمد</b></div><span className="member-icon">◯</span></div>
    {fields.show_stamps&&rows.length>0?<div className="wallet-program-list">{rows.map((x:Row,index:number)=>{const current=Math.min(sample[index]||1,Math.max(1,Number(x.required_stamps||6)-1));const total=Math.max(1,Number(x.required_stamps||6));return <div className="wallet-program-row" key={x.id||x.name}><div className="wallet-program-title"><span>{stampIcon(x.stamp_icon)}</span><div><small style={{color:design.label_color||'#C6FF4A'}}>{x.name}</small><b>{current} / {total}</b></div></div><div className="wallet-stamp-dots" aria-label={`${current} من ${total}`}>{Array.from({length:Math.min(total,8)}).map((_,dot)=><i key={dot} className={dot<current?'filled':''}>{stampIcon(x.stamp_icon)}</i>)}</div></div>})}</div>:<div className="wallet-values">{fields.show_points&&<span><small style={{color:design.label_color}}>النقاط</small><b>1,250</b></span>}{fields.show_rewards&&<span><small style={{color:design.label_color}}>المكافآت</small><b>3</b></span>}{fields.show_stamps&&<span><small style={{color:design.label_color}}>الأختام</small><b>4 / 6</b></span>}</div>}
    <div className="wallet-reward-line"><Gift size={17}/><span>المكافأة القادمة: <b>{rows[0]?.reward_title||'مكافأة مجانية'}</b></span></div>
    <div className="wallet-footer"><span>{fields.show_tier?'ذهبي':design.name||''}</span><div className="qr-box">QR</div></div>
  </div>
}
function NumberInput({label,value,onChange,min=0,required=true}:any){return <label className="field"><span>{label}</span><input className="input" type="number" min={min} value={value} required={required} onChange={e=>onChange(e.target.value===''?'':Number(e.target.value))}/></label>}
function ColorInput({label,value,onChange}:any){return <label className="field"><span>{label}</span><div className="color-input"><input type="color" value={value} onChange={e=>onChange(e.target.value)}/><input className="input mono" value={value} onChange={e=>onChange(e.target.value)}/></div></label>}
function Rule({icon:Icon,title,text}:any){return <div><div className="entity-icon"><Icon/></div><b>{title}</b><span>{text}</span></div>}
function Info({label,value}:any){return <div className="info-row"><span>{label}</span><b>{value}</b></div>}
const dateTimeInput=(value:any)=>value?new Date(value).toISOString().slice(0,16):''
const actionName=(v:string)=>({visit:'زيارة',spend:'عملية شراء',manual:'تعديل يدوي',birthday:'مكافأة ميلاد',referral:'إحالة',reversal:'عكس عملية',redeem_reward:'استبدال مكافأة',brand_created:'إنشاء براند',brand_updated:'تعديل براند',customer_created:'إنشاء عميل',loyalty_applied:'تحديث ولاء',wallet_pass_issued:'إصدار بطاقة',wallet_design_published:'نشر تصميم',campaign_created:'إنشاء حملة'} as Row)[v]||v
const roleName=(v:string)=>({brand_admin:'مدير البراند',manager:'مدير فرع',employee:'موظف'} as Row)[v]||v
const channelName=(v:string)=>({in_app:'داخل المنصة',wallet_push:'Apple Wallet',email:'Email',sms:'SMS',webhook:'Webhook'} as Row)[v]||v
const audienceName=(v:string)=>({all:'الجميع',birthday:'أعياد الميلاد',tier:'مستوى محدد',min_points:'حسب النقاط',inactive_days:'غير النشطين',branch:'فرع محدد',rewards_ready:'مكافأة جاهزة',selected:'قائمة محددة'} as Row)[v]||v
const recurrenceName=(v:string)=>({none:'مرة واحدة',daily:'يومي',weekly:'أسبوعي',monthly:'شهري'} as Row)[v]||v
const couponTypeName=(v:string)=>({points:'نقاط',stamps:'أختام',discount_percent:'خصم %',discount_amount:'خصم مبلغ',free_item:'منتج مجاني'} as Row)[v]||v
const statusName=(v:string)=>({draft:'مسودة',scheduled:'مجدولة',queued:'في قائمة الإرسال',processing:'قيد الإرسال',completed:'مكتملة',failed:'فشلت',partially_completed:'مكتملة جزئيًا',cancelled:'ملغاة'} as Row)[v]||v
