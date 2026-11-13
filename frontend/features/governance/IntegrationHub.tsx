'use client';
import {useEffect,useState} from 'react';
import {apiGet,apiPost} from '@/lib/api';

type Connector={id:string;name:string;category:string;status:string;requirements:string};
type Catalog={mode:string;connectors:Connector[];message:string};

export function IntegrationHub(){
  const [catalog,setCatalog]=useState<Catalog|null>(null);const [error,setError]=useState('');const [notice,setNotice]=useState('');
  useEffect(()=>{apiGet<Catalog>('/integrations').then(setCatalog).catch(e=>setError(e.message))},[]);
  async function check(connector:Connector){setError('');setNotice('');try{const result=await apiPost<any>(`/integrations/${connector.id}/check`,{});setNotice(result.message)}catch(e){setError(e instanceof Error?e.message:'Could not check connector status')}}
  return <div style={{display:'grid',gap:14}}><section className="card section-card"><div className="card-head"><div><h2 className="section-title">Integration catalog</h2><p className="section-sub">Connector readiness and setup requirements for a future secure deployment.</p></div><span className="status paused">CATALOG ONLY</span></div><p style={{fontSize:11,color:'#68768c'}}>Connection checks stay disabled until endpoint settings and secrets are placed in a secure deployment environment. No credentials are stored in this workspace.</p>{error&&<p role="alert" style={{fontSize:12,color:'#c2413b'}}>{error}</p>}{notice&&<p role="status" style={{fontSize:12,color:'#7a5b14'}}>{notice}</p>}</section>
    {catalog&&<section className="simple-grid">{catalog.connectors.map(connector=><article key={connector.id} className="card module-card"><div className="card-head"><div className="module-icon">◇</div><span className="status draft">{connector.status}</span></div><small className="eyebrow">{connector.category}</small><h3>{connector.name}</h3><p>{connector.requirements}</p><button className="secondary-btn" onClick={()=>check(connector)}>Check readiness</button></article>)}</section>}
  </div>
}
