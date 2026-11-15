'use client';
import {useMemo,useState} from 'react';
import {Check,ChevronDown,Search} from 'lucide-react';
import {workspaceLogoSrc} from '@/lib/workspace';

export type CompanyWorkspace={name:string;slug:string;logo_url:string|null;user_signup_available?:boolean;super_admin_setup_available?:boolean};

export function WorkspacePicker({companies,value,onChange,label='Company workspace'}:{
 companies:CompanyWorkspace[];value:string;onChange:(workspace:CompanyWorkspace)=>void;label?:string;
}){
 const [open,setOpen]=useState(false);const [query,setQuery]=useState('');
 const selected=companies.find(company=>company.slug===value);
 const filtered=useMemo(()=>companies.filter(company=>`${company.name} ${company.slug}`.toLowerCase().includes(query.trim().toLowerCase())),[companies,query]);
 return <div className="workspace-picker"><span className="workspace-picker-label">{label}</span><button type="button" className="workspace-picker-trigger" aria-haspopup="listbox" aria-expanded={open} onClick={()=>setOpen(current=>!current)}>
  {selected?<><img src={workspaceLogoSrc(selected.logo_url)} alt=""/><span><b>{selected.name}</b></span></>:<span className="workspace-picker-placeholder">Choose your company workspace</span>}<ChevronDown size={16}/>
 </button>{open&&<div className="workspace-picker-menu"><label className="workspace-picker-search"><Search size={15}/><input autoFocus value={query} onChange={event=>setQuery(event.target.value)} placeholder="Search companies"/></label><div role="listbox" aria-label={label} className="workspace-picker-options">{filtered.map(company=><button type="button" role="option" aria-selected={company.slug===value} key={company.slug} onClick={()=>{onChange(company);setOpen(false);setQuery('')}}><img src={workspaceLogoSrc(company.logo_url)} alt=""/><span><b>{company.name}</b></span>{company.slug===value&&<Check size={15}/>}</button>)}{filtered.length===0&&<p className="workspace-picker-empty">No company matched that search.</p>}</div></div>}</div>
}
