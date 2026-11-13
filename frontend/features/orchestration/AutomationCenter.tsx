'use client';
import {useEffect,useState} from 'react';
import Link from 'next/link';
import {Activity,ArrowRight,GitBranch,ShieldCheck} from 'lucide-react';
import {apiGet} from '@/lib/api';

type Overview={journeys:number;active_rules:number;simulations:number;pending_simulations:number};
export function AutomationCenter(){
  const [data,setData]=useState<Overview|null>(null);const [error,setError]=useState('');
  useEffect(()=>{Promise.all([apiGet<any[]>('/journeys'),apiGet<any[]>('/business-rules'),apiGet<any[]>('/execution/runs')]).then(([journeys,rules,runs])=>setData({journeys:journeys.length,active_rules:rules.filter(r=>r.active).length,simulations:runs.length,pending_simulations:runs.filter(r=>r.status==='Queued'||r.status==='Paused').length})).catch(e=>setError(e.message))},[]);
  return <div style={{display:'grid',gap:15}}><section className="card section-card"><div className="card-head"><div><h2 className="section-title">Automation workspace</h2><p className="section-sub">Build journeys, govern eligibility with rules, then inspect local execution simulations.</p></div><span className="status scheduled">API OVERVIEW</span></div>{error&&<p role="alert" style={{fontSize:12,color:'#c2413b'}}>{error}</p>}<div className="metric-grid">{[['Saved journeys',data?.journeys??'—'],['Active business rules',data?.active_rules??'—'],['Execution simulations',data?.simulations??'—'],['Queued or paused',data?.pending_simulations??'—']].map(([label,value])=><article key={label} className="card metric-card"><div className="metric-top">{label}</div><div className="metric-value">{value}</div></article>)}</div><div className="insight"><span className="insight-icon">ⓘ</span><p>Execution is simulation-only. This screen does not start campaigns, send messages, or create a separate workflow runtime.</p></div></section>
    <section className="simple-grid">{[{title:'Journey Orchestration',description:'Design and validate customer paths with consent-filtered previews.',href:'/journey-orchestration',icon:GitBranch},{title:'Business Rules Engine',description:'Control audience eligibility, frequency caps, and quiet hours.',href:'/business-rules',icon:ShieldCheck},{title:'Campaign Execution',description:'Inspect simulation batches, outcomes, retries, and suppression counts.',href:'/campaign-execution',icon:Activity}].map(item=><article key={item.href} className="card module-card"><div className="module-icon"><item.icon size={18}/></div><h3>{item.title}</h3><p>{item.description}</p><Link className="secondary-btn" href={item.href}>Open module <ArrowRight size={13}/></Link></article>)}</section>
  </div>
}
