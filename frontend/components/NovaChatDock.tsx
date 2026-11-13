'use client';

import {FormEvent,KeyboardEvent,useEffect,useRef,useState} from 'react';
import {Bot,MessageCircle,Send,Sparkles,X} from 'lucide-react';
import {apiPost} from '@/lib/api';

type ChatLine={role:'user'|'assistant';text:string};
type AssistReply={answer:string;provider:string|null;data_scope:string;contacted_customers:boolean};
const starters=['Summarize this workspace','Help me plan a campaign','Explain customer segments'];

export function NovaChatDock({open,onClose}:{open:boolean;onClose:()=>void}){
  const [lines,setLines]=useState<ChatLine[]>([]);const [draft,setDraft]=useState('');const [busy,setBusy]=useState(false);const [error,setError]=useState('');
  const scrollRef=useRef<HTMLDivElement|null>(null);
  useEffect(()=>{if(open)scrollRef.current?.scrollTo({top:scrollRef.current.scrollHeight,behavior:'smooth'})},[open,lines,busy]);
  async function ask(value:string){
    const prompt=value.trim();if(prompt.length<2||busy)return;
    setDraft('');setError('');setLines(current=>[...current,{role:'user',text:prompt}]);setBusy(true);
    try{const reply=await apiPost<AssistReply>('/ai/assist',{prompt,mode:'question'});setLines(current=>[...current,{role:'assistant',text:reply.answer}])}
    catch(e){setError(e instanceof Error?e.message:'Nova could not answer right now.')}
    finally{setBusy(false)}
  }
  function submit(event:FormEvent){event.preventDefault();void ask(draft)}
  function keyDown(event:KeyboardEvent<HTMLTextAreaElement>){if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();void ask(draft)}}
  if(!open)return null;
  return <section className="nova-chat-panel" aria-label="Nova AI assistant">
    <header className="nova-chat-head"><div className="nova-chat-brand"><span><Bot size={17}/></span><div><b>Nova assistant</b><small>Uses aggregate workspace data · no subscriber data</small></div></div><button className="nova-chat-close" onClick={onClose} aria-label="Close assistant"><X size={17}/></button></header>
    <div className="nova-chat-messages" ref={scrollRef} aria-live="polite">
      {!lines.length&&<div className="nova-chat-welcome"><span><Sparkles size={20}/></span><h3>How can I help?</h3><p>Ask about workspace data or get help planning campaign work.</p><div>{starters.map(item=><button key={item} className="nova-chat-starter" onClick={()=>void ask(item)}>{item}</button>)}</div></div>}
      {lines.map((line,index)=><article key={index} className={`nova-chat-line ${line.role}`}><small>{line.role==='user'?'You':'Nova'}</small><p>{line.text}</p></article>)}
      {busy&&<article className="nova-chat-line assistant"><small>Nova</small><p className="nova-chat-typing">Thinking<span> · · ·</span></p></article>}
      {error&&<p className="nova-chat-error" role="alert">{error}</p>}
    </div>
    <form className="nova-chat-compose" onSubmit={submit}><textarea value={draft} onChange={event=>setDraft(event.target.value)} onKeyDown={keyDown} maxLength={1000} rows={2} placeholder="Ask Nova anything…" aria-label="Message Nova"/><button className="primary-btn" disabled={busy||draft.trim().length<2} aria-label="Send message"><Send size={16}/></button><small>Enter to send · no messages sent · don’t enter subscriber details</small></form>
  </section>;
}
