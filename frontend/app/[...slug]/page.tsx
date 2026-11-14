'use client';
import {useEffect,useState} from 'react';
import {useParams,useRouter} from 'next/navigation';
import {Activity,Download,Layers3,Plus,Search} from 'lucide-react';
import {allNav} from '@/lib/navigation';
import {apiGet,apiPost,moduleRows} from '@/lib/api';
import {CampaignCalendar} from '@/features/campaigns/CampaignCalendar';
import {CampaignStudio} from '@/features/campaigns/CampaignStudio';
import {Customer360} from '@/features/customers/Customer360';
import {SegmentManager} from '@/features/audiences/SegmentManager';
import {OfferCatalog} from '@/features/offers/OfferCatalog';
import {ScenarioWorkspace} from '@/features/scenarios/ScenarioWorkspace';
import {JourneyBuilder} from '@/features/journeys/JourneyBuilder';
import {BusinessRuleManager} from '@/features/rules/BusinessRuleManager';
import {ExecutionConsole} from '@/features/execution/ExecutionConsole';
import {ApprovalsWorkspace} from '@/features/governance/ApprovalsWorkspace';
import {IntegrationHub} from '@/features/governance/IntegrationHub';
import {NovaAssistant} from '@/features/intelligence/NovaAssistant';
import {ReportsWorkspace} from '@/features/reports/ReportsWorkspace';
import {IntelligenceWorkspace} from '@/features/intelligence/IntelligenceWorkspace';
import {ExperimentWorkspace} from '@/features/intelligence/ExperimentWorkspace';
import {AdministrationWorkspace} from '@/features/governance/AdministrationWorkspace';
import {SettingsWorkspace} from '@/features/governance/SettingsWorkspace';
import {AutomationCenter} from '@/features/orchestration/AutomationCenter';
import {AuditLogWorkspace} from '@/features/governance/AuditLogWorkspace';
import {FeatureAccessWorkspace} from '@/features/governance/FeatureAccessWorkspace';

const moduleText:Record<string,{action:string;description:string;intro?:string}>= {
  'scenario-studio':{action:'New scenario',description:'Build a reusable campaign scenario from customer segments, offers and channels.'},
  'campaign-studio':{action:'New campaign',description:'Build, validate and manage campaign drafts.'},
  'campaign-calendar':{action:'Schedule campaign',description:'Coordinate campaign dates and spot launch conflicts.'},
  'customer-360':{action:'Find customer',description:'Explore masked profiles, consent, value and engagement history.'},
  'audience-segments':{action:'Create segment',description:'Build reusable audiences from customer attributes and behavior.'},
  'ai-segment-builder':{action:'Estimate audience',description:'Use validated rules to preview the local synthetic sample; no ML model is used.'},
  'offer-management':{action:'Create offer',description:'Manage offer details, eligibility and approval state.'},
  'journey-orchestration':{action:'Create journey',description:'Build and validate customer journeys with a consent-filtered audience preview.'},
  'workflow-automation':{action:'View automation',description:'Overview of journeys, eligibility rules, and local execution simulations.'},
  'campaign-execution':{action:'Start simulation',description:'Monitor local campaign execution simulations. No messages are sent.'},
  'channel-management':{action:'Review channels',description:'Review channel adapter requirements. No external channels are connected.'},
  'nova-ai':{action:'Start conversation',description:'Ask about synthetic workspace data or draft campaign copy with Gemini when configured, otherwise local templates.',intro:'How can Nova help?'},
  'predictive-intelligence':{action:'Review cues',description:'Explore explainable rule-based offer cues and observed customer aggregates. No evaluated predictive model is available.'},
  'ab-testing':{action:'Create experiment',description:'Plan a test hypothesis and preview consent-filtered sample allocation.'},
  'analytics-insights':{action:'Build analysis',description:'Explore observed aggregates, descriptive cohorts, and explicit record review signals.'},
  'reports-exports':{action:'Create report',description:'Explore observed campaign and simulation data; export CSV or JSON.'},
  integrations:{action:'Connector catalog',description:'Review available connector requirements. No external systems are configured.'},
  'business-rules':{action:'Create rule',description:'Configure eligibility, frequency caps and quiet-hour suppression.'},
  approvals:{action:'Review queue',description:'Review campaign, offer and scenario requests with an auditable decision trail.'},
  'user-roles':{action:'Manage directory',description:'Maintain a local role catalog and directory plan. API authorization is not enabled.'},
  'audit-logs':{action:'Export logs',description:'Approval requests and decisions are retained in the local SQLite audit trail.'},
  settings:{action:'Save preferences',description:'Set workspace preferences and inspect development connection status.'},
};
export default function ModulePage(){
  const params=useParams<{slug:string[]}>();const router=useRouter();const slug=params.slug?.[0]||'';const page=allNav.find(item=>item.href.slice(1)===slug);const title=page?.title||'Workspace';const text=moduleText[slug]||{action:'Open module',description:'CampaignNova module workspace.'};
  const [filter,setFilter]=useState('');const [notice,setNotice]=useState('');const [items,setItems]=useState<string[]>([]);const [description,setDescription]=useState(text.description);const [capability,setCapability]=useState('loading');const [apiReady,setApiReady]=useState(false);const Icon=page?.icon||Layers3;
  useEffect(()=>{let active=true;apiGet<any>(`/modules/${slug}`).then(payload=>{if(!active)return;setItems(moduleRows(slug,payload));setDescription(payload.description||text.description);setCapability(payload.capability||'available');setApiReady(true)}).catch(()=>{if(!active)return;setDescription(`${text.description} API unavailable; module preview only.`);setCapability('preview')});return()=>{active=false}},[slug]);
  async function primaryAction(){setNotice('');if(slug==='scenario-studio'){document.getElementById('scenario-form')?.scrollIntoView({behavior:'smooth'});return}if(slug==='campaign-studio'){document.getElementById('campaign-form')?.scrollIntoView({behavior:'smooth'});return}if(slug==='offer-management'){document.getElementById('offer-form')?.scrollIntoView({behavior:'smooth'});return}if(slug==='audience-segments'||slug==='ai-segment-builder'){document.getElementById('segment-form')?.scrollIntoView({behavior:'smooth'});return}if(slug==='customer-360'){document.getElementById('customer-search')?.focus();return}if(slug==='campaign-calendar'){router.push('/campaign-studio');return}if(slug==='workflow-automation'){router.push('/journey-orchestration');return}try{const result=await apiPost<any>(`/modules/${slug}/actions`,{action:'primary_action',label:text.action});setNotice(result.message||'Action request recorded.')}catch(error){setNotice(error instanceof Error?error.message:'Could not record the action.')}}
  const exportItems=()=>{const csv=['item',...items.map(item=>`"${item.replaceAll('"','""')}"`)].join('\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const link=document.createElement('a');link.href=url;link.download=`campaignnova-${slug}.csv`;link.click();URL.revokeObjectURL(url)};
  const specialized=['scenario-studio','campaign-studio','campaign-calendar','customer-360','audience-segments','ai-segment-builder','offer-management','journey-orchestration','campaign-execution','business-rules','approvals','integrations','channel-management','nova-ai','predictive-intelligence','analytics-insights','reports-exports','ab-testing','workflow-automation','user-roles','settings','audit-logs','feature-access'].includes(slug);
  const moduleHasOwnActions=['journey-orchestration','campaign-execution','business-rules','approvals','integrations','channel-management','nova-ai','predictive-intelligence','analytics-insights','reports-exports','ab-testing','workflow-automation','user-roles','settings','audit-logs'].includes(slug);
  return <><div className="page-head"><div><div className="eyebrow">CampaignNova / {title}</div><h1 className="page-title">{title}</h1><p className="page-desc">{description}</p></div>{!moduleHasOwnActions&&<button className="primary-btn" onClick={primaryAction}><Plus size={15}/>{text.action}</button>}</div>
    {notice&&<div className="card" role="status" style={{padding:'11px 14px',marginBottom:14,color:'#315efa',fontSize:12}}>{notice}<button onClick={()=>setNotice('')} style={{float:'right',border:0,background:'transparent',color:'#7d899b'}}>Dismiss</button></div>}
    {apiReady&&capability==='planned'&&<div className="card" style={{padding:'11px 14px',marginBottom:14,color:'#67758b',fontSize:12}}>Planned capability · {description}</div>}
    {slug==='scenario-studio'?<ScenarioWorkspace/>:slug==='campaign-studio'?<CampaignStudio/>:slug==='campaign-calendar'?<CampaignCalendar/>:slug==='customer-360'?<Customer360/>:slug==='audience-segments'||slug==='ai-segment-builder'?<SegmentManager/>:slug==='offer-management'?<OfferCatalog/>:slug==='journey-orchestration'?<JourneyBuilder/>:slug==='campaign-execution'?<ExecutionConsole/>:slug==='business-rules'?<BusinessRuleManager/>:slug==='approvals'?<ApprovalsWorkspace/>:slug==='integrations'||slug==='channel-management'?<IntegrationHub/>:slug==='nova-ai'?<NovaAssistant/>:slug==='reports-exports'?<ReportsWorkspace/>:slug==='predictive-intelligence'||slug==='analytics-insights'?<IntelligenceWorkspace/>:slug==='ab-testing'?<ExperimentWorkspace/>:slug==='workflow-automation'?<AutomationCenter/>:slug==='user-roles'?<AdministrationWorkspace/>:slug==='settings'?<SettingsWorkspace/>:slug==='audit-logs'?<AuditLogWorkspace/>:slug==='feature-access'?<FeatureAccessWorkspace/>:<>
      {!specialized&&<div className="filters"><label className="searchbox" style={{width:260,background:'#fff'}}><Search size={14}/><input placeholder={`Search ${title.toLowerCase()}...`} value={filter} onChange={e=>setFilter(e.target.value)}/></label><button className="secondary-btn" onClick={()=>setNotice('Use the search field to narrow the current API records. Additional structured filters are planned with each module.')}>Filters</button><button className="secondary-btn" onClick={exportItems}><Download size={13}/> Export CSV</button><span className="filter-select" style={{marginLeft:'auto'}}>{capability==='loading'?'Loading API…':capability==='planned'?'Planned module':'API records'}</span></div>}
      {items.length?<section className="simple-grid">{items.filter(item=>item.toLowerCase().includes(filter.toLowerCase())).map(item=><article key={item} className="card module-card"><div className="module-icon"><Icon size={17}/></div><h3>{item}</h3><p>{description}</p></article>)}</section>:<section className="card empty-panel"><div className="module-icon"><Icon size={18}/></div><h2>{text.intro||title}</h2><p>{description} This screen will show records here as its Phase 2–4 capabilities are delivered.</p></section>}
      {!specialized&&<div className="card" style={{marginTop:15,padding:16,display:'flex',gap:10,alignItems:'center',color:'#8490a2',fontSize:11}}><Activity size={15} color="#315efa"/> Module data and capability state come from the CampaignNova API. External services remain unconnected.</div>}
    </>}
  </>;
}
