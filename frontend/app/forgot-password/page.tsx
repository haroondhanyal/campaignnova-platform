'use client';
import Link from 'next/link';
import {FormEvent,useEffect,useState} from 'react';
import {Mail} from 'lucide-react';
import {apiGet,apiPost} from '@/lib/api';
import {AuthFrame} from '@/features/auth/AuthFrame';
import {WorkspacePicker,type CompanyWorkspace} from '@/components/WorkspacePicker';

export default function ForgotPasswordPage(){
 const [companies,setCompanies]=useState<CompanyWorkspace[]>([]);const [workspaceSlug,setWorkspaceSlug]=useState('');const [email,setEmail]=useState('');const [message,setMessage]=useState('');const [resetUrl,setResetUrl]=useState('');const [error,setError]=useState('');const [busy,setBusy]=useState(false);
 const workspace=companies.find(company=>company.slug===workspaceSlug);
 useEffect(()=>{apiGet<CompanyWorkspace[]>('/auth/workspaces').then(rows=>{setCompanies(rows);const query=new URLSearchParams(window.location.search).get('workspace');if(query&&rows.some(row=>row.slug===query))setWorkspaceSlug(query);else if(rows.length===1)setWorkspaceSlug(rows[0].slug)}).catch(()=>setError('Could not load company workspaces. Check the CampaignNova API.'))},[]);
 async function submit(event:FormEvent){event.preventDefault();if(!workspaceSlug){setError('Choose your company workspace first.');return}setBusy(true);setError('');setMessage('');setResetUrl('');try{const result=await apiPost<{message:string;development_reset_url?:string}>('/auth/forgot-password',{workspace_slug:workspaceSlug,email});setMessage(result.message);setResetUrl(result.development_reset_url||'')}catch(e){setError(e instanceof Error?e.message:'Could not request a password reset')}finally{setBusy(false)}}
 return <AuthFrame variant="recovery" showBrand={false} title="Reset your password" subtitle="Choose your company and enter your work email to request a secure reset link." footer={<span>Remembered your password? <Link href="/login">Back to sign in</Link></span>}><form className="auth-form" onSubmit={submit}><WorkspacePicker companies={companies} value={workspaceSlug} label="Company workspace" onChange={company=>{setWorkspaceSlug(company.slug);setError('')}}/><label className="form-field">Work email<span className="auth-input"><Mail size={16}/><input type="email" autoComplete="email" required value={email} onChange={e=>setEmail(e.target.value)} placeholder="name@company.com"/></span></label>{error&&<p className="auth-error" role="alert">{error}</p>}{message&&<div className="auth-success" role="status">{message}{resetUrl&&<p><Link href={resetUrl}>Open the local development reset link</Link><small>This link is shown only in development. Configure an email provider to deliver reset instructions.</small></p>}</div>}<button className="primary-btn auth-submit" disabled={busy||!workspaceSlug}>{busy?'Preparing reset…':'Send reset instructions'}</button></form></AuthFrame>
}
