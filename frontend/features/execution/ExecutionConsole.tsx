'use client';
import {useCallback, useEffect, useState} from 'react';
import {apiGet, apiPost} from '@/lib/api';

type Campaign={id:string;name:string;channel:string;status:string};
type CustomerAttempt={customer_id:string;identifier:string;status:string;attempts:number;result:string};
type Run={id:string;campaign_id:string;campaign_name:string;channel:string;mode:string;status:string;batch_number:number;summary:{targeted:number;queued:number;simulated_delivered:number;failed:number;dead_letter:number;consent_excluded:number;rule_excluded:number};customers:CustomerAttempt[]};

export function ExecutionConsole(){
  const [campaigns,setCampaigns]=useState<Campaign[]>([]);const [runs,setRuns]=useState<Run[]>([]);const [campaignId,setCampaignId]=useState('');
  const [error,setError]=useState('');const [notice,setNotice]=useState('');const [busy,setBusy]=useState(false);
  const refresh=useCallback(async()=>{const [cs,rs]=await Promise.all([apiGet<Campaign[]>('/campaigns'),apiGet<Run[]>('/execution/runs')]);setCampaigns(cs);setRuns(rs);if(!campaignId&&cs.length)setCampaignId(cs[0].id)},[campaignId]);
  useEffect(()=>{refresh().catch(e=>setError(e.message))},[refresh]);
  async function act(runId:string,action:'pause'|'resume'|'retry'){setBusy(true);setError('');setNotice('');try{await apiPost(`/execution/runs/${runId}/${action}`,{});await refresh();setNotice(`Simulation ${action} action recorded.`)}catch(e){setError(e instanceof Error?e.message:'Could not update simulation.')}finally{setBusy(false)}}
  async function start(){setBusy(true);setError('');setNotice('');try{const run=await apiPost<Run>('/execution/runs',{campaign_id:campaignId,idempotency_key:`ui-${campaignId}-${Date.now()}`,batch_size:25,rate_limit_per_minute:60});await refresh();setNotice(`Simulation ${run.id} created. No customer message was sent.`)}catch(e){setError(e instanceof Error?e.message:'Could not start simulation.')}finally{setBusy(false)}}
  return <div style={{display:'grid',gap:15}}>
    <section className="card section-card"><div className="card-head"><div><h2 className="section-title">Campaign delivery simulation</h2><p className="section-sub">Preview audience eligibility and batch outcomes using local synthetic data.</p></div><span className="status scheduled">SIMULATION ONLY</span></div>
      <div style={{display:'flex',gap:10,alignItems:'end',flexWrap:'wrap'}}><label className="form-field" style={{minWidth:260}}>Approved campaign<select value={campaignId} onChange={e=>setCampaignId(e.target.value)}><option value="">Select a campaign</option>{campaigns.filter(c=>['Approved','Scheduled','Running'].includes(c.status)).map(c=><option key={c.id} value={c.id}>{c.name} · {c.status}</option>)}</select></label><button className="primary-btn" disabled={busy||!campaignId} onClick={start}>{busy?'Working…':'Start simulation'}</button></div>
      <p style={{fontSize:10,color:'#7d899b',margin:'12px 0 0'}}>Uses masked customer identifiers and consent checks. The adapter records simulated outcomes only; it never sends SMS, WhatsApp, push, email, or other messages.</p>
      {error&&<p role="alert" style={{color:'#c2413b',fontSize:12}}>{error}</p>}{notice&&<p role="status" style={{color:'#0b9472',fontSize:12}}>{notice}</p>}
    </section>
    {runs.map(run=><section className="card" key={run.id} style={{overflow:'hidden'}}><div className="table-head"><div><h2 className="section-title">{run.campaign_name} <span style={{color:'#8995a7',fontWeight:400}}>· {run.id}</span></h2><p className="section-sub">{run.channel} adapter · batch {run.batch_number} · {run.status} · idempotent run</p></div><div style={{display:'flex',gap:7,flexWrap:'wrap'}}>{run.status==='Queued'&&<button className="secondary-btn" disabled={busy} onClick={()=>act(run.id,'pause')}>Pause</button>}{(run.status==='Paused'||run.status==='Queued')&&<button className="secondary-btn" disabled={busy} onClick={()=>act(run.id,'resume')}>Next batch / resume</button>}{run.summary.failed>0&&<button className="secondary-btn" disabled={busy} onClick={()=>act(run.id,'retry')}>Retry failures</button>}</div></div>
      <div style={{display:'flex',gap:18,flexWrap:'wrap',padding:'0 18px 14px',fontSize:11,color:'#65748b'}}><span>Eligible: <b>{run.summary.targeted}</b></span><span>Simulated delivered: <b>{run.summary.simulated_delivered}</b></span><span>Queued: <b>{run.summary.queued}</b></span><span>Failed: <b>{run.summary.failed}</b></span><span>Dead letter: <b style={{color:run.summary.dead_letter?'#bd3933':undefined}}>{run.summary.dead_letter}</b></span><span>Excluded without consent/inactive: <b>{run.summary.consent_excluded}</b></span><span>Suppressed by active rules: <b>{run.summary.rule_excluded}</b></span><span>Mode: <b>{run.mode}</b></span></div>
      <div className="responsive-table"><table className="data-table"><thead><tr><th>CUSTOMER</th><th>SIMULATION STATUS</th><th>ATTEMPTS</th><th>LOCAL ADAPTER RESULT</th></tr></thead><tbody>{run.customers.map(item=><tr key={item.customer_id}><td>{item.identifier}</td><td><span className={`status ${item.status==='Simulated Delivered'?'completed':item.status==='Simulated Failed'?'paused':'draft'}`}>{item.status}{item.status==='Simulated Failed'&&item.attempts>=3?' · DEAD LETTER':''}</span></td><td>{item.attempts}</td><td>{item.result}</td></tr>)}</tbody></table></div>
    </section>)}
    {!runs.length&&<section className="card empty-panel"><h2>No simulations yet</h2><p>Select an approved campaign to create a local execution preview.</p></section>}
  </div>
}
