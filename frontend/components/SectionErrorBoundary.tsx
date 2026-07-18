'use client'
import React from 'react'
import {AlertTriangle, RefreshCw} from 'lucide-react'

export class SectionErrorBoundary extends React.Component<{children:React.ReactNode;onRetry?:()=>void},{failed:boolean}> {
  state={failed:false}
  static getDerivedStateFromError(){return {failed:true}}
  componentDidCatch(error:unknown){console.error(error)}
  render(){
    if(this.state.failed)return <section className="section-error"><AlertTriangle/><h2>تعذر عرض هذا القسم</h2><p>لم تتأثر بقية لوحة التحكم. أعد المحاولة، وإذا استمرت المشكلة حدّث الصفحة.</p><button type="button" className="btn primary" onClick={()=>{this.setState({failed:false});this.props.onRetry?.()}}><RefreshCw size={17}/>إعادة المحاولة</button></section>
    return this.props.children
  }
}
