'use client';

import {useEffect,useState} from 'react';
import Link from 'next/link';

export default function OAuthPopupCompletePage(){
 const [result,setResult]=useState('error');
 const [error,setError]=useState<string|null>(null);
 const [standalone,setStandalone]=useState(false);
 useEffect(()=>{
  const params=new URLSearchParams(window.location.search);
  const outcome=params.get('result')||'error';
  const errorCode=params.get('error');
  setResult(outcome);setError(errorCode);
  const message={type:'campaignnova-oauth-complete',result:outcome,error:errorCode};
  if(window.opener){
   window.opener.postMessage(message,window.location.origin);
   window.close();
   window.setTimeout(()=>setStandalone(true),350);
  }else setStandalone(true);
 },[]);
 return standalone?<main className="auth-page"><section className="auth-card"><div className="auth-heading"><h1>{result==='success'?'Sign-in complete':'Sign-in could not be completed'}</h1><p>{result==='success'?'Return to your CampaignNova window.':error==='account_not_found'?'No active company account matches this provider email.':'Return to CampaignNova and try again.'}</p></div><Link className="primary-btn auth-submit" href={result==='success'?'/':'/login'}>Continue to CampaignNova</Link></section></main>:null;
}
