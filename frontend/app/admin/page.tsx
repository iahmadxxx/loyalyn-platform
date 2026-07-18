'use client'

import {useCallback, useEffect, useMemo, useRef, useState} from 'react'
import {
  Archive, Check, ChevronDown, ChevronUp, Coffee, Copy, CreditCard, Download, Eye, Gift,
  Image as ImageIcon, Loader2, Minus, Palette, Plus, QrCode, Redo2, RefreshCw, Save,
  ScanLine, Settings, ShieldCheck, Sparkles, Stamp, Trash2, Undo2, Upload, UserPlus, Users,
  WalletCards, X
} from 'lucide-react'
import {api, API} from '@/lib/api'
import {Shell} from '@/components/Shell'

type Row=Record<string,any>
type BrandAccess={id:string;name:string;slug:string;permissions?:Record<string,boolean>}
type Me={id:string;name:string;email:string;role:string;brands:BrandAccess[]}
type Toast={type:'ok'|'error';text:string}

const icons=[
  ['coffee','☕','قهوة'],['cup','🥤','كوب سفري'],['bean','●','حبة بن'],['cake','🍰','حلى'],
  ['cookie','🍪','كوكيز'],['donut','🍩','دونات'],['croissant','🥐','كرواسون'],['icecream','🍦','آيس كريم'],
  ['star','★','نجمة'],['gift','🎁','هدية'],['heart','♥','قلب'],['crown','♛','تاج'],
]
const safe=<T,>(value:unknown):T[]=>Array.isArray(value)?value as T[]:[]
const slugify=(value:string)=>value.trim().toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')||`card-${Date.now()}`
const stampDefaults={icon_size:42,gap:8,offset_x:0,offset_y:0,fit:'contain',shape:'none',empty_opacity:35}

export default function AdminPage(){
  const [me,setMe]=useState<Me|null>(null)
  const [brand,setBrand]=useState<Row|null>(null)
  const [tab,setTab]=useState('studio')
  const [templates,setTemplates]=useState<Row[]>([])
  const [programs,setPrograms]=useState<Row[]>([])
  const [customers,setCustomers]=useState<Row[]>([])
  const [transactions,setTransactions]=useState<Row[]>([])
  const [credential,setCredential]=useState<Row|null>(null)
  const [selectedId,setSelectedId]=useState('')
  const [draft,setDraft]=useState<Row|null>(null)
  const [busy,setBusy]=useState('')
  const [loading,setLoading]=useState(true)
  const [toast,setToast]=useState<Toast|null>(null)
  const [customerModal,setCustomerModal]=useState<Row|null>(null)
  const [assignments,setAssignments]=useState<Row[]>([])
  const [scanResult,setScanResult]=useState<Row|null>(null)
  const [history,setHistory]=useState<Row[]>([])
  const historyIndex=useRef(-1)

  const selected=useMemo(()=>templates.find(x=>x.id===selectedId)||templates[0]||null,[templates,selectedId])
  const selectedPrograms=useMemo(()=>{
    const ids=safe<string>(draft?.program_ids||selected?.program_ids)
    const byId=new Map(programs.map(x=>[x.id,x]))
    return ids.map(id=>byId.get(id)).filter(Boolean) as Row[]
  },[draft,selected,programs])

  const tell=useCallback((text:string,type:'ok'|'error'='ok')=>{
    setToast({text,type});window.setTimeout(()=>setToast(null),4200)
  },[])
  const run=useCallback(async<T,>(key:string,fn:()=>Promise<T>,success?:string)=>{
    setBusy(key)
    try{const value=await fn();if(success)tell(success);return value}
    catch(error:any){tell(error?.message||'حدث خطأ غير متوقع','error');throw error}
    finally{setBusy('')}
  },[tell])

  const reload=useCallback(async(keepSelection=true)=>{
    if(!brand?.id)return
    const [cardRows,programRows,customerRows,transactionRows]=await Promise.all([
      api<Row[]>(`/api/cards/templates?brand_id=${brand.id}&include_archived=true`),
      api<Row[]>(`/api/stamps/programs?brand_id=${brand.id}`),
      api<Row[]>(`/api/customers?brand_id=${brand.id}&active_only=false`),
      api<Row[]>(`/api/stamps/transactions?brand_id=${brand.id}&limit=150`),
    ])
    setTemplates(safe(cardRows));setPrograms(safe(programRows));setCustomers(safe(customerRows));setTransactions(safe(transactionRows))
    const next=(keepSelection&&cardRows.some(x=>x.id===selectedId)?selectedId:cardRows[0]?.id)||''
    setSelectedId(next)
  },[brand?.id,selectedId])

  useEffect(()=>{
    void(async()=>{
      setLoading(true)
      try{
        const profile=await api<Me>('/api/auth/me')
        const brands=await api<Row[]>('/api/brands')
        const first=brands[0]
        setMe(profile);setBrand(first||null)
        if(!first)throw new Error('لا يوجد براند مرتبط بالحساب')
        const [cardRows,programRows,customerRows,transactionRows]=await Promise.all([
          api<Row[]>(`/api/cards/templates?brand_id=${first.id}&include_archived=true`),
          api<Row[]>(`/api/stamps/programs?brand_id=${first.id}`),
          api<Row[]>(`/api/customers?brand_id=${first.id}&active_only=false`),
          api<Row[]>(`/api/stamps/transactions?brand_id=${first.id}&limit=150`),
        ])
        setTemplates(cardRows);setPrograms(programRows);setCustomers(customerRows);setTransactions(transactionRows)
        setSelectedId(cardRows[0]?.id||'')
        if(profile.role==='platform_owner'){
          setCredential(await api('/api/wallet/platform/credential').catch(()=>null))
        }
      }catch(error:any){tell(error?.message||'تعذر تحميل لوحة التحكم','error')}
      finally{setLoading(false)}
    })()
  },[tell])

  useEffect(()=>{
    if(!selected){setDraft(null);return}
    const copy=structuredClone(selected)
    setDraft(copy)
    setHistory([copy]);historyIndex.current=0
  },[selected?.id])

  function change(patch:Row,track=true){
    setDraft(current=>{
      if(!current)return current
      const next={...current,...patch}
      if(track){
        const list=history.slice(0,historyIndex.current+1)
        list.push(structuredClone(next));setHistory(list.slice(-40));historyIndex.current=Math.min(39,list.length-1)
      }
      return next
    })
  }
  function undo(){if(historyIndex.current<=0)return;historyIndex.current-=1;setDraft(structuredClone(history[historyIndex.current]))}
  function redo(){if(historyIndex.current>=history.length-1)return;historyIndex.current+=1;setDraft(structuredClone(history[historyIndex.current]))}

  async function createCard(){
    if(!brand)return
    const name=prompt('اسم البطاقة الجديدة مثل: قهوة وحلى')?.trim()
    if(!name)return
    await run('create-card',async()=>{
      const program=await api<Row>('/api/stamps/programs',{method:'POST',body:JSON.stringify({
        brand_id:brand.id,name:'قهوة',slug:slugify(`coffee-${Date.now()}`),description:'',required_stamps:7,
        reward_title:'مشروب مجاني',reward_type:'free_item',stamp_icon:'coffee',background_color:brand.primary_color||'#A79889',
        accent_color:brand.accent_color||'#FFFFFF',display_options:stampDefaults,is_default:false,sort_order:0,
      })})
      const card=await api<Row>('/api/cards/templates',{method:'POST',body:JSON.stringify({
        brand_id:brand.id,name,name_en:'',slug:slugify(`${name}-${Date.now()}`),description:'',is_default:templates.length===0,
        allow_public_join:false,sort_order:templates.length,program_ids:[program.id],background_color:brand.primary_color||'#A79889',
        foreground_color:'#FFFFFF',label_color:'#FFFFFF',logo_text:brand.name,card_title:'بطاقة الولاء',layout_style:'visual',
        overlay_opacity:15,barcode_format:'PKBarcodeFormatQR',fields:{show_stamps:true,show_rewards:true,show_points:false,show_tier:false,show_visits:false,render_stamp_strip:true,stamp_panel_color:'#FFFFFF',stamp_panel_text_color:'#756B63',stamp_panel_title:'LOYALTY CARD'},terms:'',
      })})
      await reload(false);setSelectedId(card.id)
      return card
    },'تم إنشاء البطاقة مع أول برنامج ختم')
  }

  async function saveDraft(showMessage=true){
    if(!draft)return
    return run('save-card',async()=>{
      const body={
        name:draft.name,name_en:draft.name_en||null,slug:draft.slug,description:draft.description||null,
        is_default:!!draft.is_default,allow_public_join:!!draft.allow_public_join,sort_order:Number(draft.sort_order||0),
        program_ids:safe<string>(draft.program_ids),background_color:draft.background_color,foreground_color:draft.foreground_color,
        label_color:draft.label_color,logo_text:draft.logo_text,card_title:draft.card_title,layout_style:draft.layout_style||'visual',
        overlay_opacity:Number(draft.overlay_opacity||0),barcode_format:draft.barcode_format||'PKBarcodeFormatQR',fields:draft.fields||{},terms:draft.terms||null,
      }
      const updated=await api<Row>(`/api/cards/templates/${draft.id}`,{method:'PATCH',body:JSON.stringify(body)})
      setTemplates(rows=>rows.map(x=>x.id===updated.id?updated:x));setDraft(updated)
      return updated
    },showMessage?'تم حفظ جميع التعديلات في نفس المكان':undefined)
  }

  async function publish(){
    if(!draft)return
    await saveDraft(false)
    const updated=await run('publish-card',()=>api<Row>(`/api/cards/templates/${draft.id}/publish`,{method:'POST'}),'تم نشر البطاقة وأصبحت جاهزة للإصدار')
    setTemplates(rows=>rows.map(x=>x.id===updated.id?updated:x));setDraft(updated)
  }

  async function duplicateCard(){
    if(!draft)return
    const copy=await run('duplicate-card',()=>api<Row>(`/api/cards/templates/${draft.id}/duplicate`,{method:'POST'}),'تم نسخ البطاقة وبرامجها بشكل مستقل')
    await reload(false);setSelectedId(copy.id)
  }

  async function archiveCard(){
    if(!draft||!confirm('أرشفة البطاقة؟ البطاقات الموجودة عند العملاء ستتوقف.'))return
    await run('archive-card',()=>api(`/api/cards/templates/${draft.id}/archive`,{method:'POST'}),'تمت أرشفة البطاقة')
    await reload(false)
  }

  async function uploadCardAsset(kind:string,file?:File){
    if(!draft||!file)return
    const fd=new FormData();fd.append('kind',kind);fd.append('file',file)
    const result=await run(`asset-${kind}`,()=>api<Row>(`/api/cards/templates/${draft.id}/asset`,{method:'POST',body:fd}),'تم وضع الصورة في مكانها الصحيح')
    const field={logo:'logo_url',hero:'hero_url',background:'background_image_url',strip:'strip_url'}[kind]
    if(field)change({[field]:`${result.asset_url}?t=${Date.now()}`},false)
  }
  async function removeCardAsset(kind:string){
    if(!draft)return
    await run(`remove-${kind}`,()=>api(`/api/cards/templates/${draft.id}/asset/${kind}`,{method:'DELETE'}),'تم حذف الصورة')
    const field={logo:'logo_url',hero:'hero_url',background:'background_image_url',strip:'strip_url'}[kind]
    if(field)change({[field]:null},false)
  }

  async function addProgram(){
    if(!brand||!draft)return
    const name=prompt('اسم برنامج الختم: قهوة، حلى، فطور...')?.trim()
    if(!name)return
    const program=await run('add-program',()=>api<Row>('/api/stamps/programs',{method:'POST',body:JSON.stringify({
      brand_id:brand.id,name,slug:slugify(`${name}-${Date.now()}`),description:'',required_stamps:7,reward_title:'مكافأة مجانية',
      reward_type:'free_item',stamp_icon:name.includes('حل')?'cake':'coffee',background_color:draft.background_color,
      accent_color:draft.label_color,display_options:stampDefaults,is_default:false,sort_order:selectedPrograms.length,
    })}),'تمت إضافة البرنامج داخل هذه البطاقة')
    setPrograms(rows=>[...rows,program]);change({program_ids:[...safe<string>(draft.program_ids),program.id]})
  }
  async function updateProgram(program:Row,patch:Row){
    const local={...program,...patch}
    setPrograms(rows=>rows.map(x=>x.id===program.id?local:x))
    await run(`program-${program.id}`,()=>api<Row>(`/api/stamps/programs/${program.id}`,{method:'PATCH',body:JSON.stringify(patch)}))
  }
  function moveProgram(index:number,direction:-1|1){
    if(!draft)return
    const ids=[...safe<string>(draft.program_ids)];const target=index+direction
    if(target<0||target>=ids.length)return
    ;[ids[index],ids[target]]=[ids[target],ids[index]];change({program_ids:ids})
  }
  async function removeProgram(program:Row){
    if(!draft||!confirm(`إزالة ${program.name} من هذه البطاقة؟`))return
    change({program_ids:safe<string>(draft.program_ids).filter(id=>id!==program.id)})
  }
  async function uploadProgramAsset(program:Row,kind:string,file?:File){
    if(!file)return
    const fd=new FormData();fd.append('kind',kind);fd.append('file',file)
    const result=await run(`program-asset-${program.id}-${kind}`,()=>api<Row>(`/api/stamps/programs/${program.id}/asset`,{method:'POST',body:fd}),'تم ضبط الرمز تلقائيًا داخل خانة الختم')
    setPrograms(rows=>rows.map(x=>x.id===program.id?{...x,[kind==='filled_stamp'?'filled_stamp_image_url':'empty_stamp_image_url']:`${result.asset_url}?t=${Date.now()}`}:x))
  }

  async function openCustomer(customer:Row){
    setCustomerModal(customer);setAssignments([])
    setAssignments(await api<Row[]>(`/api/cards/customers/${customer.id}/assignments`))
  }
  async function toggleCustomerCard(template:Row,active:boolean){
    if(!customerModal)return
    if(active){
      await run(`detach-${template.id}`,()=>api(`/api/cards/customers/${customerModal.id}/assignments/${template.id}`,{method:'DELETE'}),'تمت إزالة البطاقة من العميل')
    }else{
      await run(`attach-${template.id}`,()=>api(`/api/cards/customers/${customerModal.id}/assignments/${template.id}`,{method:'POST'}),'تمت إضافة البطاقة للعميل')
    }
    setAssignments(await api<Row[]>(`/api/cards/customers/${customerModal.id}/assignments`))
  }
  async function issueCard(template:Row){
    if(!customerModal)return
    const result=await run(`issue-${template.id}`,()=>api<Row>(`/api/wallet/passes/${customerModal.id}/${template.id}`,{method:'POST'}),'تم إصدار بطاقة Wallet لهذا العميل')
    setAssignments(await api<Row[]>(`/api/cards/customers/${customerModal.id}/assignments`))
    window.open(result.card_url,'_blank')
    return result
  }
  async function copyCardLink(template:Row,existingUrl?:string){
    if(!customerModal)return
    let url=existingUrl
    if(!url){
      const result=await run(`copy-${template.id}`,()=>api<Row>(`/api/wallet/passes/${customerModal.id}/${template.id}`,{method:'POST'}),'تم تجهيز بطاقة Wallet')
      url=result.card_url
      setAssignments(await api<Row[]>(`/api/cards/customers/${customerModal.id}/assignments`))
    }
    await navigator.clipboard.writeText(String(url))
    tell('تم نسخ رابط البطاقة لإرساله للعميل')
  }

  async function createCustomer(event:React.FormEvent<HTMLFormElement>){
    event.preventDefault();if(!brand)return
    const form=event.currentTarget;const fd=new FormData(form)
    await run('create-customer',()=>api('/api/customers',{method:'POST',body:JSON.stringify({
      brand_id:brand.id,name:fd.get('name'),phone:fd.get('phone'),email:fd.get('email')||null,birthday:null,tags:[],notes:null,
      card_template_id:fd.get('card_template_id')||null,
    })}),'تم إنشاء العميل')
    form.reset();await reload()
  }

  async function scan(event:React.FormEvent<HTMLFormElement>){
    event.preventDefault();if(!brand)return
    const code=String(new FormData(event.currentTarget).get('code')||'').trim()
    if(!code)return
    setScanResult(await run('scan',()=>api<Row>(`/api/stamps/scan/${encodeURIComponent(code)}?brand_id=${brand.id}`)))
  }
  async function addStamp(program:Row){
    if(!scanResult)return
    const result=await run(`stamp-${program.id}`,()=>api<Row>(`/api/stamps/customers/${scanResult.customer.id}/programs/${program.id}/add`,{method:'POST',body:JSON.stringify({quantity:1,branch_id:null,idempotency_key:`studio-${Date.now()}-${program.id}`})}),'تمت إضافة الختم')
    setScanResult((current:Row|null)=>current?{...current,cards:result.cards}:current);await reload()
  }
  async function reverse(tx:Row){
    const reason=prompt('سبب التراجع عن الختم')?.trim();if(!reason)return
    await run(`reverse-${tx.id}`,()=>api(`/api/stamps/transactions/${tx.id}/reverse`,{method:'POST',body:JSON.stringify({reason,idempotency_key:`reverse-${Date.now()}-${tx.id}`})}),'تم التراجع عن العملية بأمان')
    await reload()
  }

  if(loading||!me||!brand)return <div className="v6-loading"><Loader2 className="spin"/><b>جاري تجهيز الاستوديو…</b></div>

  return <Shell active={tab} onChange={setTab} userName={me.name} brandName={brand.name} role={me.role}>
    {toast&&<div className={`v6-toast ${toast.type}`}><span>{toast.text}</span><button onClick={()=>setToast(null)}><X/></button></div>}
    <div className="v6-page-head"><div><span>LOYALYN STAMP STUDIO</span><h1>{tab==='studio'?'استوديو البطاقات':tab==='customers'?'العملاء والبطاقات':tab==='scan'?'السكان السريع':tab==='operations'?'سجل العمليات':'الإعدادات'}</h1><p>براند واحد، كل شيء في مكان واحد، ومعاينة حية قبل النشر.</p></div>{tab==='studio'&&<div className="v6-head-actions"><button className="v6-btn ghost" onClick={undo} disabled={historyIndex.current<=0}><Undo2/>تراجع</button><button className="v6-btn ghost" onClick={redo} disabled={historyIndex.current>=history.length-1}><Redo2/>إعادة</button><button className="v6-btn ghost" onClick={()=>void saveDraft()} disabled={!draft||busy==='save-card'}>{busy==='save-card'?<Loader2 className="spin"/>:<Save/>}حفظ</button><button className="v6-btn primary" onClick={()=>void publish()} disabled={!draft||busy==='publish-card'}>{busy==='publish-card'?<Loader2 className="spin"/>:<Upload/>}حفظ ونشر</button></div>}</div>

    {tab==='studio'&&<Studio brand={brand} draft={draft} change={change} templates={templates} selectedId={selectedId} setSelectedId={setSelectedId} selectedPrograms={selectedPrograms} busy={busy} createCard={createCard} duplicateCard={duplicateCard} archiveCard={archiveCard} uploadCardAsset={uploadCardAsset} removeCardAsset={removeCardAsset} addProgram={addProgram} updateProgram={updateProgram} moveProgram={moveProgram} removeProgram={removeProgram} uploadProgramAsset={uploadProgramAsset}/>} 
    {tab==='customers'&&<Customers brand={brand} customers={customers} templates={templates.filter(x=>x.status==='published')} createCustomer={createCustomer} openCustomer={openCustomer}/>} 
    {tab==='scan'&&<Scan scan={scan} result={scanResult} addStamp={addStamp} busy={busy}/>} 
    {tab==='operations'&&<Operations rows={transactions} reverse={reverse} busy={busy}/>} 
    {tab==='settings'&&<SettingsPage brand={brand} me={me} credential={credential} busy={busy} run={run} setCredential={setCredential}/>} 

    {customerModal&&<CustomerCardsModal customer={customerModal} templates={templates.filter(x=>x.status==='published')} assignments={assignments} busy={busy} onClose={()=>setCustomerModal(null)} toggle={toggleCustomerCard} issue={issueCard} copyLink={copyCardLink}/>} 
  </Shell>
}

function Studio(props:Row){
  const {brand,draft,change,templates,selectedId,setSelectedId,selectedPrograms,busy,createCard,duplicateCard,archiveCard,uploadCardAsset,removeCardAsset,addProgram,updateProgram,moveProgram,removeProgram,uploadProgramAsset}=props
  if(!draft)return <div className="v6-empty"><CreditCard/><h2>أنشئ أول بطاقة</h2><p>سنضيف لك أول برنامج ختم تلقائيًا ثم تقدر تعدل كل شيء من نفس الشاشة.</p><button className="v6-btn primary" onClick={createCard}><Plus/>إنشاء بطاقة</button></div>
  return <div className="studio-workspace">
    <aside className="studio-card-list">
      <div className="studio-list-head"><div><b>بطاقاتك</b><small>كلها تعمل معًا</small></div><button onClick={createCard}><Plus/></button></div>
      <div className="studio-card-scroll">{templates.map((card:Row)=><button key={card.id} className={card.id===selectedId?'active':''} onClick={()=>setSelectedId(card.id)}><span style={{background:card.background_color}}><CreditCard/></span><div><b>{card.name}</b><small>{card.status==='published'?'منشورة وتعمل':'مسودة'} · {card.programs?.length||0} برنامج</small></div>{card.status==='published'&&<i><Check/></i>}</button>)}</div>
      <div className="studio-card-actions"><button onClick={duplicateCard}><Copy/>نسخ مستقل</button><button className="danger" onClick={archiveCard}><Archive/>أرشفة</button></div>
    </aside>

    <section className="studio-preview-column">
      <div className="preview-toolbar"><span><Eye/>المعاينة الحية</span><em>كل تغيير يظهر فورًا</em></div>
      <WalletLivePreview brand={brand} design={draft} programs={selectedPrograms}/>
      <div className="preview-note"><Sparkles/><div><b>المعاينة مطابقة للمنطق الحقيقي</b><small>الرموز تدخل تلقائيًا داخل خانات ثابتة ولا تقفز فوق أو تحت صف الأختام.</small></div></div>
    </section>

    <section className="studio-controls">
      <details open><summary><Palette/>الهوية والألوان<ChevronDown/></summary><div className="control-body">
        <Text label="اسم البطاقة" value={draft.name} onChange={(value)=>change({name:value})}/>
        <div className="control-two"><Text label="اسم البراند على البطاقة" value={draft.logo_text||''} onChange={(value)=>change({logo_text:value})}/><Text label="عنوان البطاقة" value={draft.card_title||''} onChange={(value)=>change({card_title:value})}/></div>
        <div className="control-three"><Color label="الخلفية" value={draft.background_color} onChange={(value)=>change({background_color:value})}/><Color label="النص" value={draft.foreground_color} onChange={(value)=>change({foreground_color:value})}/><Color label="التمييز" value={draft.label_color} onChange={(value)=>change({label_color:value})}/></div>
        <div className="asset-row"><Asset label="الشعار" value={draft.logo_url} busy={busy==='asset-logo'} onUpload={(file)=>uploadCardAsset('logo',file)} onRemove={()=>removeCardAsset('logo')}/><Asset label="خلفية البطاقة" value={draft.background_image_url} busy={busy==='asset-background'} onUpload={(file)=>uploadCardAsset('background',file)} onRemove={()=>removeCardAsset('background')}/></div>
        <label className="v6-switch"><input type="checkbox" checked={draft.allow_public_join} onChange={e=>change({allow_public_join:e.target.checked})}/><span>إتاحة البطاقة للتسجيل العام</span></label>
      </div></details>

      <details open><summary><Stamp/>برامج الأختام داخل البطاقة<ChevronDown/></summary><div className="control-body program-editor-list">
        {selectedPrograms.map((program:Row,index:number)=><ProgramEditor key={program.id} program={program} index={index} total={selectedPrograms.length} busy={busy} update={updateProgram} move={moveProgram} remove={removeProgram} upload={uploadProgramAsset}/>) }
        <button className="add-program" onClick={addProgram}><Plus/><span><b>إضافة برنامج ختم</b><small>قهوة، حلى، فطور أو أي اسم تبيه</small></span></button>
      </div></details>

      <details><summary><Settings/>تفاصيل الإصدار<ChevronDown/></summary><div className="control-body">
        <Text label="رابط البطاقة الداخلي" value={draft.slug} onChange={(value)=>change({slug:slugify(value)})}/>
        <Text label="الشروط" value={draft.terms||''} onChange={(value)=>change({terms:value})}/>
        <div className="control-two"><Select label="الباركود" value={draft.barcode_format} onChange={(value)=>change({barcode_format:value})} options={[['PKBarcodeFormatQR','QR'],['PKBarcodeFormatPDF417','PDF417'],['PKBarcodeFormatAztec','Aztec']]}/><NumberField label="ترتيب البطاقة" value={draft.sort_order||0} min={0} max={999} onChange={(value)=>change({sort_order:value})}/></div>
      </div></details>
    </section>
  </div>
}

function WalletLivePreview({brand,design,programs}:{brand:Row;design:Row;programs:Row[]}){
  const style:React.CSSProperties={backgroundColor:design.background_color,color:design.foreground_color}
  if(design.background_image_url)style.backgroundImage=`linear-gradient(rgba(0,0,0,.14),rgba(0,0,0,.14)),url(${design.background_image_url})`
  const fields=design.fields||{}
  return <div className="iphone-frame"><div className="wallet-card-live" style={style}>
    <header><div className="wallet-logo-live">{design.logo_url?<img src={design.logo_url} alt="الشعار"/>:<b>{design.logo_text||brand.name}</b>}</div><div><small>NAME</small><strong>Ali</strong></div></header>
    <StampPanel programs={programs} fields={fields}/>
    <div className="wallet-fields-live"><div><small>COFFEE</small><b>{programs[0]?`0/${programs[0].required_stamps}`:'—'}</b></div><div><small>REWARDS</small><b>0</b></div></div>
    <div className="wallet-qr-live"><div className="fake-qr">{Array.from({length:81}).map((_,i)=><i key={i} className={(i*7+i%5)%3===0?'on':''}/>)}</div><span>{design.logo_text||brand.name}</span></div>
  </div></div>
}

function StampPanel({programs,fields}:{programs:Row[];fields:Row}){
  const shown=programs.slice(0,2)
  return <div className="stamp-panel-live" style={{background:fields.stamp_panel_color||'#fff',color:fields.stamp_panel_text_color||'#756B63'}}>
    <div className="stamp-panel-title"><i/><span>{fields.stamp_panel_title||'LOYALTY CARD'}</span><i/></div>
    {shown.length?shown.map((program,index)=><StampRow key={program.id} program={program} sample={index===0?Math.min(6,program.required_stamps-1):Math.min(2,program.required_stamps-1)}/>):<div className="stamp-placeholder">أضف برنامج ختم</div>}
  </div>
}

function StampRow({program,sample}:{program:Row;sample:number}){
  const options={...stampDefaults,...(program.display_options||{})}
  const total=Math.min(14,Math.max(1,Number(program.required_stamps||1)))
  return <div className="stamp-row-live"><div className="stamp-slots" style={{gap:`${Math.max(2,Number(options.gap))}px`}}>{Array.from({length:total}).map((_,index)=>{
    const filled=index<sample;const source=filled?program.filled_stamp_image_url:program.empty_stamp_image_url
    return <span key={index} className={`stamp-slot ${options.shape||'none'} ${filled?'filled':'empty'}`} style={{width:`${Math.min(58,Math.max(22,Number(options.icon_size)))}px`,height:`${Math.min(58,Math.max(22,Number(options.icon_size)))}px`,opacity:filled?1:Number(options.empty_opacity||35)/100,color:program.accent_color}}>{source?<img src={source} alt="" style={{objectFit:options.fit==='cover'?'cover':'contain',transform:`translate(${Number(options.offset_x||0)}px,${Number(options.offset_y||0)}px)`}}/>:<span>{symbol(program.stamp_icon)}</span>}</span>})}</div><em>{sample}/{total}</em></div>
}

function ProgramEditor({program,index,total,busy,update,move,remove,upload}:Row){
  const [open,setOpen]=useState(true)
  const options={...stampDefaults,...(program.display_options||{})}
  const patchOptions=(patch:Row)=>update(program,{display_options:{...options,...patch}})
  return <article className="program-editor">
    <header><button onClick={()=>setOpen(!open)}><span className="program-symbol">{symbol(program.stamp_icon)}</span><div><b>{program.name}</b><small>{program.required_stamps} أختام · {program.reward_title}</small></div></button><div><button onClick={()=>move(index,-1)} disabled={index===0}><ChevronUp/></button><button onClick={()=>move(index,1)} disabled={index===total-1}><ChevronDown/></button><button className="danger" onClick={()=>remove(program)}><Trash2/></button></div></header>
    {open&&<div className="program-editor-body">
      <div className="control-two"><Text label="اسم الختم" value={program.name} onBlur={(value)=>update(program,{name:value})}/><Text label="المكافأة" value={program.reward_title} onBlur={(value)=>update(program,{reward_title:value})}/></div>
      <div className="control-two"><NumberField label="عدد الأختام" value={program.required_stamps} min={1} max={14} onBlur={(value)=>update(program,{required_stamps:value})}/><Color label="لون الختم" value={program.accent_color} onChange={(value)=>update(program,{accent_color:value})}/></div>
      <div className="icon-library">{icons.map(([value,icon,label])=><button key={value} className={program.stamp_icon===value?'active':''} title={label} onClick={()=>update(program,{stamp_icon:value})}><span>{icon}</span><small>{label}</small></button>)}</div>
      <div className="asset-row"><Asset label="الختم المكتمل" value={program.filled_stamp_image_url} busy={busy===`program-asset-${program.id}-filled_stamp`} onUpload={(file)=>upload(program,'filled_stamp',file)}/><Asset label="الختم الفارغ" value={program.empty_stamp_image_url} busy={busy===`program-asset-${program.id}-empty_stamp`} onUpload={(file)=>upload(program,'empty_stamp',file)}/></div>
      <div className="precision-grid"><NumberField label="الحجم px" value={options.icon_size} min={22} max={72} onBlur={(value)=>patchOptions({icon_size:value})}/><NumberField label="المسافة px" value={options.gap} min={2} max={24} onBlur={(value)=>patchOptions({gap:value})}/><NumberField label="يمين / يسار" value={options.offset_x} min={-18} max={18} onBlur={(value)=>patchOptions({offset_x:value})}/><NumberField label="أعلى / أسفل" value={options.offset_y} min={-18} max={18} onBlur={(value)=>patchOptions({offset_y:value})}/></div>
      <div className="control-two"><Select label="احتواء الصورة" value={options.fit} onChange={(value)=>patchOptions({fit:value})} options={[["contain","احتواء كامل"],["cover","ملء الخانة"]]}/><Select label="شكل الخانة" value={options.shape} onChange={(value)=>patchOptions({shape:value})} options={[["none","بدون إطار"],["circle","دائرة"],["rounded","مربع مستدير"],["dashed","إطار متقطع"]]}/></div>
      <p className="precision-help">الموضع مضبوط داخل كل خانة بالبكسل. مهما كان مقاس الصورة، لن تظهر فوق أو تحت صف الأختام.</p>
    </div>}
  </article>
}

function Customers({brand,customers,templates,createCustomer,openCustomer}:Row){
  const [q,setQ]=useState('')
  const rows=safe<Row>(customers).filter(x=>`${x.name} ${x.phone}`.toLowerCase().includes(q.toLowerCase()))
  return <div className="customers-layout"><section className="v6-panel"><div className="v6-panel-head"><div><h2>إضافة عميل</h2><p>أنشئ العميل أولًا، ثم اختر له أي بطاقة أو عدة بطاقات معًا.</p></div><UserPlus/></div><form className="v6-form" onSubmit={createCustomer}><TextInput name="name" label="اسم العميل"/><TextInput name="phone" label="رقم الجوال"/><TextInput name="email" label="البريد الإلكتروني" required={false}/><label><span>البطاقة الأولية (اختياري)</span><select name="card_template_id"><option value="">بدون بطاقة الآن</option>{templates.map((x:Row)=><option key={x.id} value={x.id}>{x.name}</option>)}</select></label><button className="v6-btn primary"><Plus/>إضافة العميل</button></form></section>
    <section className="v6-panel"><div className="v6-panel-head"><div><h2>العملاء</h2><p>أضف لكل عميل أي عدد من البطاقات المنشورة.</p></div><Users/></div><div className="customer-search"><input value={q} onChange={e=>setQ(e.target.value)} placeholder="ابحث بالاسم أو الجوال"/></div><div className="customer-grid">{rows.map((customer:Row)=><button key={customer.id} onClick={()=>openCustomer(customer)}><i>{customer.name?.[0]||'ع'}</i><div><b>{customer.name}</b><small>{customer.phone}</small></div><span>{customer.stamps} ختم</span></button>)}</div></section></div>
}

function CustomerCardsModal({customer,templates,assignments,busy,onClose,toggle,issue,copyLink}:Row){
  const activeIds=new Set(safe<Row>(assignments).map(x=>x.card_template?.id))
  const assignmentById=new Map(safe<Row>(assignments).map(x=>[x.card_template?.id,x]))
  return <div className="v6-modal-backdrop"><div className="v6-modal"><header><div><h2>بطاقات {customer.name}</h2><p>فعّل بطاقة واحدة أو عدة بطاقات معًا، ثم انسخ رابط كل بطاقة وأرسله للعميل.</p></div><button onClick={onClose}><X/></button></header><div className="customer-card-choices">{templates.map((template:Row)=>{const active=activeIds.has(template.id);const assignment=assignmentById.get(template.id);return <article key={template.id}><div className="choice-color" style={{background:template.background_color}}><CreditCard/></div><div><b>{template.name}</b><small>{template.programs?.map((p:Row)=>p.name).join(' + ')||'بدون برامج'}</small></div><button className={`mini-toggle ${active?'on':''}`} onClick={()=>toggle(template,active)} disabled={busy===`attach-${template.id}`||busy===`detach-${template.id}`}>{active?'مفعلة':'إضافة'}</button>{active&&<div className="customer-card-wallet-actions"><button className="v6-btn primary small" onClick={()=>issue(template)} disabled={busy===`issue-${template.id}`}><WalletCards/>{assignment?.wallet_pass?'فتح البطاقة':'إصدار Wallet'}</button><button className="v6-btn ghost small" onClick={()=>copyLink(template,assignment?.wallet_pass?.card_url)} disabled={busy===`copy-${template.id}`}><Copy/>نسخ الرابط</button></div>}</article>})}</div></div></div>
}

function Scan({scan,result,addStamp,busy}:Row){
  return <div className="scan-layout"><section className="v6-panel"><div className="v6-panel-head"><div><h2>امسح أو أدخل الرمز</h2><p>بعدها تظهر كل بطاقات العميل وبرامجها في شاشة واحدة.</p></div><ScanLine/></div><form className="scan-form" onSubmit={scan}><input name="code" placeholder="رمز العضوية" autoFocus/><button className="v6-btn primary" disabled={busy==='scan'}>{busy==='scan'?<Loader2 className="spin"/>:<ScanLine/>}فتح العميل</button></form></section>{result&&<section className="v6-panel scan-result"><div className="scan-customer"><i>{result.customer.name[0]}</i><div><h2>{result.customer.name}</h2><p>{result.customer.phone} · {result.customer.membership_code}</p></div></div>{safe<Row>(result.card_templates).map(group=><div className="scan-card-group" key={group.id}><h3><CreditCard/>{group.name}</h3>{safe<Row>(group.cards).map(program=><div className="scan-program" key={program.id}><span className="program-symbol">{symbol(program.stamp_icon)}</span><div><b>{program.name}</b><small>{program.stamps} / {program.required_stamps} · مكافآت {program.rewards_available}</small></div><button className="v6-btn primary" onClick={()=>addStamp(program)} disabled={busy===`stamp-${program.id}`}><Plus/>ختم</button></div>)}</div>)}</section>}</div>
}

function Operations({rows,reverse,busy}:Row){return <section className="v6-panel"><div className="v6-panel-head"><div><h2>سجل الأختام والتراجع</h2><p>كل عملية محفوظة، ويمكن عكس العملية الخاطئة بدون تخريب السجل.</p></div><Stamp/></div><div className="operations-list">{safe<Row>(rows).map(tx=><div key={tx.id} className={tx.reversed_at?'reversed':''}><span className={`op-dot ${tx.action}`}/><div><b>{tx.action==='add'?`+${tx.delta_stamps} ختم`:tx.action==='redeem'?'استبدال مكافأة':'تراجع'}</b><small>{new Date(tx.created_at).toLocaleString('ar-QA')} · {tx.note||tx.reference||'بدون ملاحظة'}</small></div>{tx.action!=='reversal'&&!tx.reversed_at&&<button className="v6-btn ghost small" onClick={()=>reverse(tx)} disabled={busy===`reverse-${tx.id}`}><Undo2/>تراجع</button>}{tx.reversed_at&&<em>تم التراجع</em>}</div>)}</div></section>}

function SettingsPage({brand,me,credential,busy,run,setCredential}:Row){
  const joinUrl=typeof window==='undefined'?'':`${location.origin}/join/${brand.slug}`
  async function upload(event:React.FormEvent<HTMLFormElement>){event.preventDefault();const fd=new FormData(event.currentTarget);const result=await run('cert',()=>api('/api/wallet/platform/credential',{method:'POST',body:fd}),'تم تفعيل شهادة Apple Wallet');setCredential(result)}
  return <div className="settings-layout"><section className="v6-panel"><div className="v6-panel-head"><div><h2>رابط التسجيل</h2><p>العميل يسجل أولًا، ثم أنت تحدد البطاقات التي تريد إصدارها له.</p></div><QrCode/></div><div className="join-settings"><img src={`${API}/api/public/brands/${brand.slug}/join-qr.svg`} alt="QR التسجيل"/><div><code>{joinUrl}</code><button className="v6-btn ghost" onClick={()=>navigator.clipboard.writeText(joinUrl)}><Copy/>نسخ الرابط</button></div></div></section>{me.role==='platform_owner'&&<section className="v6-panel"><div className="v6-panel-head"><div><h2>شهادة Apple Wallet</h2><p>تضبط مرة واحدة فقط، وبعدها إصدار كل البطاقات يتم من نفس الاستوديو.</p></div><ShieldCheck/></div>{credential?.configured?<div className="credential-ready"><ShieldCheck/><div><b>الشهادة مفعلة</b><small>{credential.pass_type_identifier} · تنتهي {credential.expires_at?new Date(credential.expires_at).toLocaleDateString('ar-QA'):'—'}</small></div></div>:<form className="v6-form" onSubmit={upload}><TextInput name="p12_file" label="ملف .p12" type="file" accept=".p12"/><TextInput name="wwdr_file" label="Apple WWDR" type="file" accept=".cer,.pem"/><TextInput name="password" label="كلمة مرور الشهادة" type="password"/><TextInput name="pass_type_identifier" label="Pass Type Identifier"/><TextInput name="team_identifier" label="Team ID"/><TextInput name="organization_name" label="اسم الجهة" defaultValue={brand.name}/><button className="v6-btn primary" disabled={busy==='cert'}><Upload/>رفع وتفعيل</button></form>}</section>}</div>
}

function Asset({label,value,busy,onUpload,onRemove}:{label:string;value?:string;busy:boolean;onUpload:(file?:File)=>void;onRemove?:()=>void}){return <div className="asset-box"><div className="asset-preview">{value?<img src={value} alt=""/>:<ImageIcon/>}</div><div><b>{label}</b><small>PNG أو JPG أو WebP</small><label className="asset-button">{busy?<Loader2 className="spin"/>:<Upload/>}رفع<input type="file" accept="image/png,image/jpeg,image/webp" onChange={e=>onUpload(e.target.files?.[0])}/></label>{value&&onRemove&&<button className="asset-remove" onClick={onRemove}><Trash2/>حذف</button>}</div></div>}
function Text({label,value,onChange,onBlur}:{label:string;value:string;onChange?:(v:string)=>void;onBlur?:(v:string)=>void}){const [local,setLocal]=useState(value);useEffect(()=>setLocal(value),[value]);return <label className="control-field"><span>{label}</span><input value={local} onChange={e=>{setLocal(e.target.value);onChange?.(e.target.value)}} onBlur={()=>onBlur?.(local)}/></label>}
function Color({label,value,onChange}:{label:string;value:string;onChange:(v:string)=>void}){return <label className="control-field"><span>{label}</span><div className="color-control"><input type="color" value={value||'#000000'} onChange={e=>onChange(e.target.value)}/><code>{value}</code></div></label>}
function NumberField({label,value,min,max,onChange,onBlur}:{label:string;value:number;min:number;max:number;onChange?:(v:number)=>void;onBlur?:(v:number)=>void}){const [local,setLocal]=useState(Number(value));useEffect(()=>setLocal(Number(value)),[value]);return <label className="control-field"><span>{label}</span><input type="number" value={local} min={min} max={max} onChange={e=>{const v=Number(e.target.value);setLocal(v);onChange?.(v)}} onBlur={()=>onBlur?.(local)}/></label>}
function Select({label,value,onChange,options}:{label:string;value:string;onChange:(v:string)=>void;options:string[][]}){return <label className="control-field"><span>{label}</span><select value={value} onChange={e=>onChange(e.target.value)}>{options.map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></label>}
function TextInput({name,label,type='text',required=true,accept,defaultValue}:{name:string;label:string;type?:string;required?:boolean;accept?:string;defaultValue?:string}){return <label><span>{label}</span><input name={name} type={type} required={required} accept={accept} defaultValue={defaultValue}/></label>}
const symbol=(value:string)=>icons.find(x=>x[0]===value)?.[1]||'★'
