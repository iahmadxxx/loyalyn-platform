export const API=process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000'
export function token(){return typeof window==='undefined'?'':localStorage.getItem('loyalyn_token')||''}
export async function api(path:string,opts:RequestInit={}){
 const h=new Headers(opts.headers); h.set('Content-Type','application/json'); const t=token(); if(t)h.set('Authorization',`Bearer ${t}`)
 const r=await fetch(`${API}${path}`,{...opts,headers:h,cache:'no-store'}); if(r.status===401&&typeof window!=='undefined'){localStorage.removeItem('loyalyn_token'); location.href='/login'}
 const data=await r.json().catch(()=>({})); if(!r.ok)throw new Error(data.detail||'Request failed'); return data
}
