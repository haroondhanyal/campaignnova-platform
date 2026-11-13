'use client';
import {useEffect,useState} from 'react';
import {apiGet} from '@/lib/api';

type Overview={data_mode:string;analytics_method:string;sample:{customers:number;campaign_records:number;execution_simulations:number};observed_campaigns:{campaign_count:number;reached:number;conversions:number;conversion_rate_percent:number|null;observed_revenue_pkr:number};observed_customer_profile:{consented_sample:number;average_monthly_value_pkr:number;average_data_usage_gb:number;high_churn_risk_sample:number};simulation_only:{simulated_delivered:number;simulated_failed:number;provider_delivery_events:number};signals:{type:string;severity:string;entity:string;message:string}[];limitations:string[]};
type Cohort={dimension:string;basis:string;sample_total:number;cohorts:{cohort:string;sample_customers:number;consented:number;average_monthly_value_pkr:number;average_data_usage_gb:number;high_churn_risk:number}[];interpretation:string};
type Comparison={dimension:string;groups:{group:string;campaign_count:number;reached:number;conversions:number;conversion_rate_percent:number|null;observed_revenue_pkr:number;average_budget_pkr:number}[];method:string;note:string};
type Suggestion={customer_id:string;masked_identifier:string;profile_segment:string;existing_churn_label:string;suggested_offer:{id:string;name:string;product:string}|null;preferred_channel:string;reasons:string[];method:string;probability:null;message:string};
type Suggestions={basis:string;model_status:string;suggestions:Suggestion[];note:string};
const fmt=(value:number)=>new Intl.NumberFormat('en-US').format(value);
const money=(value:number)=>`PKR ${fmt(value)}`;

export function IntelligenceWorkspace(){
  const [overview,setOverview]=useState<Overview|null>(null);const [cohorts,setCohorts]=useState<Cohort|null>(null);const [comparison,setComparison]=useState<Comparison|null>(null);const [suggestions,setSuggestions]=useState<Suggestions|null>(null);
  const [dimension,setDimension]=useState('segment');const [compareBy,setCompareBy]=useState('channel');const [error,setError]=useState('');
  useEffect(()=>{apiGet<Overview>('/intelligence/overview').then(setOverview).catch(e=>setError(e.message));apiGet<Suggestions>('/intelligence/offer-fit').then(setSuggestions).catch(e=>setError(e.message))},[]);
  useEffect(()=>{apiGet<Cohort>(`/intelligence/cohorts?dimension=${dimension}`).then(setCohorts).catch(e=>setError(e.message))},[dimension]);
  useEffect(()=>{apiGet<Comparison>(`/intelligence/campaign-comparison?dimension=${compareBy}`).then(setComparison).catch(e=>setError(e.message))},[compareBy]);
  if(error&&!overview)return <section className="card empty-panel"><h2>Intelligence API unavailable</h2><p>{error}</p></section>;
  if(!overview)return <section className="card empty-panel"><h2>Loading observed workspace data…</h2></section>;
  const signals=overview.signals;
  return <div style={{display:'grid',gap:15}}>
    <section className="card section-card"><div className="card-head"><div><h2 className="section-title">Observed performance overview</h2><p className="section-sub">Descriptive metrics calculated from local synthetic customer and seeded campaign records.</p></div><span className="status scheduled">{overview.analytics_method.replaceAll('_',' ').toUpperCase()}</span></div>
      <div className="metric-grid" style={{gridTemplateColumns:'repeat(4,minmax(0,1fr))'}}>{[
        ['Sample customers',fmt(overview.sample.customers)],['Campaign records',fmt(overview.observed_campaigns.campaign_count)],['Observed reach',fmt(overview.observed_campaigns.reached)],['Observed conversions',fmt(overview.observed_campaigns.conversions)],
        ['Observed conversion rate',overview.observed_campaigns.conversion_rate_percent===null?'—':`${overview.observed_campaigns.conversion_rate_percent}%`],['Observed revenue',money(overview.observed_campaigns.observed_revenue_pkr)],['Consent in sample',`${overview.observed_customer_profile.consented_sample}/${overview.sample.customers}`],['High churn label',fmt(overview.observed_customer_profile.high_churn_risk_sample)],
      ].map(([label,value])=><article className="card metric-card" key={label}><div className="metric-top">{label}</div><div className="metric-value" style={{fontSize:20}}>{value}</div></article>)}</div>
      <div className="insight" style={{marginTop:12}}><span className="insight-icon">ⓘ</span><p>Sample: {overview.sample.customers} customers · {overview.sample.campaign_records} campaigns · {overview.sample.execution_simulations} execution simulations. Simulated outcomes are separate from provider delivery events ({overview.simulation_only.provider_delivery_events}). No statistical inference or evaluated predictive model is available.</p></div>
    </section>
    <div className="phase2-split" style={{gridTemplateColumns:'minmax(0,1fr) minmax(0,1fr)'}}>
      <section className="card section-card"><div className="card-head"><div><h2 className="section-title">Customer cohorts</h2><p className="section-sub">Local sample only · descriptive grouping</p></div><select className="filter-select" aria-label="Cohort dimension" value={dimension} onChange={e=>setDimension(e.target.value)}><option value="segment">Segment</option><option value="churn_risk">Existing churn label</option><option value="customer_type">Customer type</option><option value="preferred_channel">Preferred channel</option><option value="subscription_status">Subscription status</option></select></div>
        {cohorts&&<><div className="responsive-table"><table className="data-table"><thead><tr><th>COHORT</th><th>SAMPLE</th><th>OPTED IN</th><th>AVG MONTHLY VALUE</th><th>AVG DATA</th></tr></thead><tbody>{cohorts.cohorts.map(row=><tr key={row.cohort}><td>{row.cohort}</td><td>{row.sample_customers}</td><td>{row.consented}</td><td>{money(row.average_monthly_value_pkr)}</td><td>{row.average_data_usage_gb} GB</td></tr>)}</tbody></table></div><p className="section-sub" style={{marginTop:10}}>{cohorts.interpretation}</p></>}
      </section>
      <section className="card section-card"><div className="card-head"><div><h2 className="section-title">Campaign comparison</h2><p className="section-sub">Observed aggregate results; no causal or significance claim</p></div><select className="filter-select" aria-label="Campaign comparison grouping" value={compareBy} onChange={e=>setCompareBy(e.target.value)}><option value="channel">By channel</option><option value="objective">By objective</option></select></div>
        {comparison&&<><div className="responsive-table"><table className="data-table"><thead><tr><th>GROUP</th><th>CAMPAIGNS</th><th>REACHED</th><th>CONVERTED</th><th>RATE</th><th>REVENUE</th></tr></thead><tbody>{comparison.groups.map(row=><tr key={row.group}><td>{row.group}</td><td>{row.campaign_count}</td><td>{fmt(row.reached)}</td><td>{fmt(row.conversions)}</td><td>{row.conversion_rate_percent===null?'—':`${row.conversion_rate_percent}%`}</td><td>{money(row.observed_revenue_pkr)}</td></tr>)}</tbody></table></div><p className="section-sub" style={{marginTop:10}}>{comparison.note}</p></>}
      </section>
    </div>
    <section className="card section-card"><div className="card-head"><div><h2 className="section-title">Rule-based offer fit cues</h2><p className="section-sub">For consented active sample customers. No probability scores or evaluated model predictions.</p></div><span className="status draft">NO EVALUATED MODEL</span></div>
      {suggestions&&<><p className="section-sub">{suggestions.note}</p><div className="responsive-table"><table className="data-table"><thead><tr><th>CUSTOMER</th><th>SEGMENT / EXISTING LABEL</th><th>OFFER SUGGESTION</th><th>PREFERRED CHANNEL</th><th>WHY THIS CUE</th></tr></thead><tbody>{suggestions.suggestions.map(row=><tr key={row.customer_id}><td>{row.masked_identifier}</td><td>{row.profile_segment}<br/><small>{row.existing_churn_label} existing label</small></td><td>{row.suggested_offer?`${row.suggested_offer.name} · ${row.suggested_offer.product}`:'No active offer available'}</td><td>{row.preferred_channel}</td><td>{row.reasons.join(' · ')}</td></tr>)}</tbody></table></div></>}
    </section>
    <section className="card section-card"><div className="card-head"><div><h2 className="section-title">Operational review signals</h2><p className="section-sub">Transparent checks over stored records, not statistical anomaly detection.</p></div><span className="filter-select">{signals.length} signals</span></div>
      {signals.length?<div style={{display:'grid',gap:8}}>{signals.map((signal,index)=><article key={`${signal.type}-${index}`} className="insight"><span className="insight-icon">{signal.severity==='review'?'⚑':'ⓘ'}</span><p><b>{signal.entity}</b><br/>{signal.message}</p></article>)}</div>:<div className="card empty-panel"><h3>No review signals in current records</h3><p>These checks only describe the available workspace sample.</p></div>}
      <p className="section-sub" style={{marginTop:10}}>Simulation only: {overview.simulation_only.simulated_delivered} accepted by local adapter · {overview.simulation_only.simulated_failed} locally marked failed. These are not actual delivery receipts.</p>
    </section>
  </div>;
}
