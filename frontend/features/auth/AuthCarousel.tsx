'use client';
import {useEffect, useState} from 'react';

type AuthVariant='signin'|'signup'|'recovery';
const scenes=[
 {image:'/auth-scenes/eid-ad.svg',kicker:'CAMPAIGNNOVA EID GREETINGS',title:'Eid Mubarak — celebrate the joy together.',detail:'Wishing you and your loved ones a bright, peaceful and joyful Eid.'},
 {image:'/auth-scenes/campaigns.svg',kicker:'CAMPAIGN STUDIO',title:'Plan every campaign in one clear view.',detail:'Coordinate channels, creative, approvals and timing without losing sight of your audience.'},
 {image:'/auth-scenes/insights.svg',kicker:'LIVE INTELLIGENCE',title:'Turn customer signals into useful insight.',detail:'Explore engagement patterns and make your next decision with context.'},
 {image:'/auth-scenes/audience.svg',kicker:'AUDIENCE & OFFERS',title:'Build relevant experiences for every segment.',detail:'Bring audience rules, customer value and timely offers together.'},
 {image:'/auth-scenes/customer.svg',kicker:'CUSTOMER 360',title:'See the journey behind every customer.',detail:'Keep preferences, activity and relationship history close to each decision.'},
 {image:'/auth-scenes/workspace.svg',kicker:'SECURE WORKSPACES',title:'Give every team a place of its own.',detail:'Company workspaces keep people, permissions and campaign data organized.'},
 {image:'/auth-scenes/security.svg',kicker:'ACCOUNT SECURITY',title:'Get back to work with confidence.',detail:'Protected account access keeps your workspace in the right hands.'},
];
const orders:Record<AuthVariant,number[]>={signin:[0,1,2,3,4,5,6],signup:[0,5,3,1,4,2,6],recovery:[0,6,5,2,3,1,4]};

export function AuthCarousel({variant='signin'}:{variant?:AuthVariant}){
 const order=orders[variant];const [position,setPosition]=useState(0);const slide=scenes[order[position]];
 const isEid=slide.image==='/auth-scenes/eid-ad.svg';
 useEffect(()=>{const query=window.matchMedia('(prefers-reduced-motion: reduce)');if(query.matches)return;const timer=window.setInterval(()=>setPosition(value=>(value+1)%order.length),5000);return()=>window.clearInterval(timer)},[order]);
 const move=(direction:number)=>setPosition(value=>(value+direction+order.length)%order.length);
 return <div className="auth-carousel" aria-roledescription="carousel" aria-label="CampaignNova workspace highlights">
  <div className="auth-scene-wrap" aria-live="polite"><img key={slide.image} className="auth-scene-image" src={slide.image} alt=""/><div className="auth-scene-copy" key={slide.title}><span>{slide.kicker}</span><h2>{slide.title}</h2><p>{slide.detail}</p></div><div className={`auth-scene-glass${isEid?' auth-scene-eid':''}`}><i/><span>{isEid?'Eid Mubarak':'Workspace insights'}</span>{!isEid&&<b>+18.6%</b>}</div></div>
  <div className="auth-carousel-controls"><button type="button" onClick={()=>move(-1)} aria-label="Previous image">‹</button><div className="auth-carousel-dots" aria-label={`Slide ${position+1} of ${order.length}`}>{order.map((sceneIndex,index)=><button key={sceneIndex} type="button" className={index===position?'active':''} onClick={()=>setPosition(index)} aria-label={`Show image ${index+1}`} aria-current={index===position?'true':undefined}/>)}</div><span>{String(position+1).padStart(2,'0')} <i>/</i> {String(order.length).padStart(2,'0')}</span><button type="button" onClick={()=>move(1)} aria-label="Next image">›</button></div>
 </div>
}
