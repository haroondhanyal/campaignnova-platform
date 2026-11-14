'use client';
import Link from 'next/link';
import {ReactNode} from 'react';
import {API_BASE} from '@/lib/api';

export function AuthFrame({title,subtitle,children,footer,brandName='CampaignNova',logoUrl}:{
 title:string;subtitle:string;children:ReactNode;footer:ReactNode;brandName?:string;logoUrl?:string|null;
}){
 const logo=logoUrl?`${API_BASE}${logoUrl}`:'/icon.svg';
 return <main className="auth-page"><section className="auth-layout">
  <aside className="auth-visual" aria-label="CampaignNova campaign workspace">
   <Link href="/login" className="auth-visual-brand"><img src={logo} alt=""/><span><b>{brandName}</b><small>INTELLIGENT CAMPAIGN WORKSPACE</small></span></Link>
   <div className="auth-visual-copy"><span className="auth-kicker">CUSTOMER VALUE, IN MOTION</span><h2>Turn every customer moment into a smarter campaign.</h2><p>Plan, personalize and learn across your customer lifecycle from one connected workspace.</p></div>
   <div className="auth-art" aria-hidden="true"><div className="auth-orbit orbit-one"/><div className="auth-orbit orbit-two"/><div className="auth-art-glow"/><div className="auth-art-card"><div className="auth-art-top"><span><i/> Campaign performance</span><b>↗ 18.6%</b></div><div className="auth-chart"><i/><i/><i/><i/><i/><i/><i/><svg viewBox="0 0 400 110" preserveAspectRatio="none"><path d="M0 89 C30 84 33 49 66 57 S103 90 135 61 177 64 202 39 240 55 267 32 305 51 332 19 370 29 400 5"/></svg></div><div className="auth-art-bottom"><span>Customer engagement</span><span>Last 30 days <b>⌄</b></span></div></div><div className="auth-art-chip chip-one"><span>✦</span><div><b>Next best action</b><small>Personalized for each audience</small></div></div><div className="auth-art-chip chip-two"><span>◎</span><div><b>4.8M</b><small>customer profiles</small></div></div></div>
   <div className="auth-visual-foot"><span>Secure company workspaces</span><span>·</span><span>Built for customer teams</span></div>
  </aside>
  <section className="auth-card"><div className="auth-mobile-brand"><Link href="/login" className="auth-brand"><img src={logo} alt=""/><span><b>{brandName}</b><small>Customer value & campaign workspace</small></span></Link></div><div className="auth-heading"><span className="auth-kicker">YOUR WORKSPACE</span><h1>{title}</h1><p>{subtitle}</p></div>{children}<div className="auth-footer">{footer}</div><small className="auth-footnote">Every company gets a separate workspace with its own administrator, team, and data.</small></section>
 </section></main>
}
