'use client';
import Link from 'next/link';
import {ReactNode} from 'react';
import {workspaceLogoSrc} from '@/lib/workspace';
import {AuthCarousel} from './AuthCarousel';

export function AuthFrame({title,subtitle,children,footer,brandName='CampaignNova',logoUrl,variant='signin',showBrand=true}:{
 title:string;subtitle:string;children:ReactNode;footer:ReactNode;brandName?:string;logoUrl?:string|null;variant?:'signin'|'signup'|'recovery';showBrand?:boolean;
}){
 const logo=workspaceLogoSrc(logoUrl);
 return <main className="auth-page"><section className="auth-layout">
  <aside className="auth-visual" aria-label="CampaignNova campaign workspace">
   {showBrand&&<Link href="/login" className="auth-visual-brand"><img src={logo} alt=""/><span><b>{brandName}</b><small>INTELLIGENT CAMPAIGN WORKSPACE</small></span></Link>}
   <AuthCarousel variant={variant}/>
   <div className="auth-visual-foot"><span>Secure company workspaces</span><span>·</span><span>Built for customer teams</span></div>
  </aside>
  <section className="auth-card">{showBrand&&<div className="auth-mobile-brand"><Link href="/login" className="auth-brand"><img src={logo} alt=""/><span><b>{brandName}</b><small>Customer value & campaign workspace</small></span></Link></div>}<div className="auth-heading"><span className="auth-kicker">YOUR WORKSPACE</span><h1>{title}</h1><p>{subtitle}</p></div>{children}<div className="auth-footer">{footer}</div><small className="auth-footnote">Every company gets a separate workspace with its own administrator, team, and data.</small></section>
 </section></main>
}
