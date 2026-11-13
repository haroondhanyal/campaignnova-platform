'use client';
import {FormEvent, useCallback, useEffect, useState} from 'react';
import {apiGet, apiPatch, apiPost} from '@/lib/api';

type Campaign = {id:string;name:string;objective:string;channel:string;audience:string;status:string;start_date:string|null;budget:number;segment_id?:string|null;offer_id?:string|null};
type Option = {id:string;name:string};
const nextAction:Record<string,{status:string;label:string}> = {
  Approved:{status:'Scheduled',label:'Schedule'},
};

export function CampaignStudio(){
  const [campaigns,setCampaigns]=useState<Campaign[]>([]); const [segments,setSegments]=useState<Option[]>([]); const [offers,setOffers]=useState<Option[]>([]);
  const [error,setError]=useState(''); const [message,setMessage]=useState(''); const [busy,setBusy]=useState(false);const [checks,setChecks]=useState<any[]>([]);
  const refresh=useCallback(async()=>{const [campaignRows,segmentRows,offerRows]=await Promise.all([apiGet<Campaign[]>('/campaigns'),apiGet<Option[]>('/segments'),apiGet<Option[]>('/offers')]);setCampaigns(campaignRows);setSegments(segmentRows);setOffers(offerRows)},[]);
  useEffect(()=>{refresh().catch(e=>setError(e.message))},[refresh]);
  async function createCampaign(event:FormEvent<HTMLFormElement>){event.preventDefault();const formElement=event.currentTarget;setBusy(true);setError('');setMessage('');const form=new FormData(formElement);const value=(key:string)=>String(form.get(key)||'');
    const selectedSegment=segments.find(segment=>segment.id===value('segment_id'));const payload={name:value('name'),description:value('description'),objective:value('objective'),campaign_type:value('campaign_type'),business_unit:value('business_unit'),owner:value('owner'),priority:value('priority'),channel:value('channel'),audience:selectedSegment?.name||value('audience')||'All eligible customers',segment_id:value('segment_id')||null,offer_id:value('offer_id')||null,start_date:value('start_date')||null,end_date:value('end_date')||null,budget:Number(value('budget')||0),tags:value('tags').split(',').map(x=>x.trim()).filter(Boolean)};
    try{const validation=await apiPost<any>('/campaigns/validate',payload);setChecks(validation.checks);if(!validation.can_create){setError('Resolve the campaign validation errors before saving.');setBusy(false);return}await apiPost('/campaigns',payload);formElement.reset();setMessage('Draft campaign saved after validation. It is ready to request approval.');await refresh()}catch(e){setError(e instanceof Error?e.message:'Could not create the campaign.')}finally{setBusy(false)}}
  async function changeStatus(campaign:Campaign){const action=nextAction[campaign.status];setError('');setMessage('');try{if(campaign.status==='Draft'){await apiPost('/approvals',{resource_type:'campaign',resource_id:campaign.id,summary:`Review campaign: ${campaign.name}`});setMessage('Campaign submitted to the approval queue.');await refresh();return}if(action){await apiPost(`/campaigns/${campaign.id}/status`,{status:action.status,reason:action.label});setMessage(`${campaign.name}: ${action.label.toLowerCase()} recorded.`);await refresh()}}catch(e){setError(e instanceof Error?e.message:'Could not update the campaign.')}}
  async function saveDraft(campaign:Campaign){const name=window.prompt('Campaign name',campaign.name);if(!name||name.trim()===campaign.name)return;setError('');try{await apiPatch(`/campaigns/${campaign.id}`,{name:name.trim()});setMessage('Draft campaign updated.');await refresh()}catch(e){setError(e instanceof Error?e.message:'Could not update the campaign.')}}
  return <div style={{display:'grid',gap:16}}>
    <section id="campaign-form" className="card section-card"><div className="card-head"><div><h2 className="section-title">Campaign information and targeting</h2><p className="section-sub">Create a persisted draft, then move it through the approval lifecycle.</p></div><span className="status draft">Draft</span></div>
      {error&&<p role="alert" style={{color:'#c2413b',fontSize:12}}>{error}</p>}{message&&<p role="status" style={{color:'#0b9472',fontSize:12}}>{message}</p>}{checks.length>0&&<div style={{display:'grid',gap:5,marginBottom:12}}>{checks.map((check:any)=><div key={check.key} style={{fontSize:11,color:check.status==='error'?'#bd3933':check.status==='warning'?'#a56a13':'#16835f'}}>● {check.message}</div>)}</div>}
      <form onSubmit={createCampaign} style={{display:'grid',gridTemplateColumns:'repeat(3,minmax(0,1fr))',gap:12}}>
        <label className="form-field">Campaign name<input name="name" required minLength={2} maxLength={120} placeholder="e.g. Prepaid data booster"/></label>
        <label className="form-field">Objective<select name="objective"><option>Retention</option><option>Acquisition</option><option>Churn Prevention</option><option>Upselling</option><option>Cross-selling</option><option>Win-back</option><option>Revenue Growth</option></select></label>
        <label className="form-field">Campaign type<select name="campaign_type"><option>Retention</option><option>Acquisition</option><option>Churn Prevention</option><option>Upselling</option><option>Cross-selling</option><option>Usage Stimulation</option><option>Loyalty</option></select></label>
        <label className="form-field">Business unit<select name="business_unit"><option>Mobile</option><option>Prepaid</option><option>Postpaid</option><option>Broadband / FTTH</option><option>Digital Services</option></select></label>
        <label className="form-field">Priority<select name="priority"><option>Normal</option><option>Low</option><option>High</option><option>Urgent</option></select></label>
        <div className="form-field">Owner<small>Assigned automatically from your signed-in account.</small></div>
        <label className="form-field">Audience segment<select name="segment_id"><option value="">All eligible customers</option>{segments.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
        <label className="form-field">Offer<select name="offer_id"><option value="">No offer selected</option>{offers.filter((o:any)=>o.status==='Active').map(o=><option key={o.id} value={o.id}>{o.name}</option>)}</select></label>
        <label className="form-field">Channel<select name="channel"><option>SMS</option><option>WhatsApp</option><option>USSD</option><option>Push</option><option>Email</option><option>In-App</option></select></label>
        <label className="form-field">Start date<input name="start_date" type="date"/></label>
        <label className="form-field">End date<input name="end_date" type="date"/></label>
        <label className="form-field">Budget (PKR)<input name="budget" type="number" min="0" step="1" defaultValue="0"/></label>
        <label className="form-field" style={{gridColumn:'1 / -1'}}>Description<textarea name="description" rows={2} maxLength={1000} placeholder="What should this campaign achieve?"/></label>
        <label className="form-field" style={{gridColumn:'1 / -1'}}>Tags<input name="tags" placeholder="retention, prepaid, november"/><small>Separate tags with commas.</small></label>
        <div style={{gridColumn:'1 / -1'}}><button className="primary-btn" type="submit" disabled={busy}>{busy?'Saving…':'Save draft'}</button></div>
      </form>
    </section>
    <section className="card table-card"><div className="table-head"><div><h2 className="section-title">Campaign lifecycle</h2><p className="section-sub">Approval decisions happen in the governed approval queue; schedule does not launch delivery.</p></div></div><div className="responsive-table"><table className="data-table"><thead><tr><th>CAMPAIGN</th><th>OBJECTIVE</th><th>AUDIENCE</th><th>CHANNEL</th><th>START</th><th>BUDGET</th><th>STATUS / ACTION</th></tr></thead><tbody>{campaigns.map(c=>{const action=nextAction[c.status];return <tr key={c.id}><td>{c.name}</td><td>{c.objective}</td><td>{c.audience}</td><td>{c.channel}</td><td>{c.start_date||'—'}</td><td>PKR {Number(c.budget).toLocaleString()}</td><td><span className={`status ${c.status==='Running'?'live':c.status==='Scheduled'?'scheduled':c.status==='Paused'?'paused':c.status==='Completed'?'completed':'draft'}`}>{c.status}</span>{action&&<button className="secondary-btn" style={{marginLeft:7,padding:'5px 8px'}} onClick={()=>changeStatus(c)}>{action.label}</button>}{c.status==='Draft'&&<><button className="secondary-btn" style={{marginLeft:7,padding:'5px 8px'}} onClick={()=>changeStatus(c)}>Request approval</button><button className="icon-button" title="Edit draft name" onClick={()=>saveDraft(c)}>✎</button></>}{c.status==='Pending Approval'&&<small style={{marginLeft:7,color:'#8290a5'}}>Awaiting review</small>}</td></tr>})}</tbody></table></div></section>
  </div>
}
