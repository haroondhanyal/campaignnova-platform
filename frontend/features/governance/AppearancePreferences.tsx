'use client';

import {useEffect,useState} from 'react';
import {Check,Contrast,Eye,Palette,Type} from 'lucide-react';
import {ACCENTS,Appearance,COLOR_THEMES,DEFAULT_APPEARANCE,FONTS,applyAppearance,readAppearance,saveAppearance} from '@/lib/appearance';

const modes=[
  {id:'light',label:'Light',description:'Bright and clean',icon:'☀'},
  {id:'dark',label:'Dark',description:'Low-light workspace',icon:'☾'},
  {id:'contrast',label:'High contrast',description:'Clear edges and text',icon:'◐'},
  {id:'grey',label:'Grey',description:'Neutral surfaces',icon:'◒'},
] as const;

export function AppearancePreferences(){
  const [appearance,setAppearance]=useState<Appearance>(DEFAULT_APPEARANCE);
  const [hexDraft,setHexDraft]=useState(DEFAULT_APPEARANCE.accent);
  useEffect(()=>{const saved=readAppearance();setAppearance(saved);setHexDraft(saved.accent);applyAppearance(saved)},[]);
  function change(values:Partial<Appearance>){const next={...appearance,...values};setAppearance(next);setHexDraft(next.accent);saveAppearance(next)}
  return <section className="card section-card appearance-section">
    <div className="card-head"><div><h2 className="section-title">Appearance & personalization</h2><p className="section-sub">Choose your display mode, color system, and interface font. Changes apply immediately and stay in this browser.</p></div><span className="appearance-mark"><Palette size={17}/></span></div>
    <div className="appearance-group"><div className="appearance-label"><Contrast size={15}/><div><b>Display mode</b><small>Contrast and surface style</small></div></div><div className="appearance-modes">{modes.map(mode=><button type="button" key={mode.id} onClick={()=>change({mode:mode.id})} className={`appearance-mode ${appearance.mode===mode.id?'selected':''}`} aria-pressed={appearance.mode===mode.id}><span className="appearance-mode-icon">{mode.icon}</span><span><b>{mode.label}</b><small>{mode.description}</small></span>{appearance.mode===mode.id&&<Check size={15}/>}</button>)}</div></div>
    <div className="appearance-group"><div className="appearance-label"><Palette size={15}/><div><b>Color themes</b><small>Five coordinated accent styles</small></div></div><div className="appearance-theme-cards">{COLOR_THEMES.map(theme=><button type="button" key={theme.name} className={`appearance-theme ${appearance.accent===theme.hex?'selected':''}`} onClick={()=>change({accent:theme.hex})} aria-pressed={appearance.accent===theme.hex}><span className="appearance-theme-preview" style={{'--theme-accent':theme.hex} as React.CSSProperties}><i/><i/><i/></span><b>{theme.name}</b><small>{theme.description}</small></button>)}</div></div>
    <div className="appearance-group"><div className="appearance-label"><Palette size={15}/><div><b>Custom accent color</b><small>20 ready-made colors plus your own</small></div></div><div className="appearance-swatches" role="radiogroup" aria-label="Accent colors">{ACCENTS.map(color=><button type="button" key={color.hex} onClick={()=>change({accent:color.hex})} className={`appearance-swatch ${appearance.accent.toLowerCase()===color.hex?'selected':''}`} style={{'--swatch':color.hex} as React.CSSProperties} title={color.name} aria-label={`${color.name} accent`} aria-checked={appearance.accent.toLowerCase()===color.hex} role="radio">{appearance.accent.toLowerCase()===color.hex&&<Check size={14}/>}</button>)}</div><div className="appearance-custom-row"><label className="appearance-color-input">Custom color<input type="color" value={appearance.accent} onChange={event=>change({accent:event.target.value})}/></label><label className="appearance-hex-input">Hex value<input value={hexDraft} maxLength={7} onChange={event=>{const value=event.target.value;setHexDraft(value);if(/^#[\da-f]{6}$/i.test(value))change({accent:value})}} onBlur={()=>setHexDraft(appearance.accent)}/></label><span className="appearance-current"><i style={{background:appearance.accent}}/>Selected accent</span></div></div>
    <div className="appearance-group"><div className="appearance-label"><Type size={15}/><div><b>System font</b><small>Ten local font stacks, no external font downloads</small></div></div><label className="appearance-font-select">Interface font<select value={appearance.font} onChange={event=>change({font:event.target.value})}>{FONTS.map(font=><option key={font.name} value={font.name}>{font.name}</option>)}</select></label><div className="font-preview" style={{fontFamily:FONTS.find(font=>font.name===appearance.font)?.stack}}><b>CampaignNova workspace</b><span>Customer insights, campaigns and decisions</span></div></div>
    <div className="appearance-group"><div className="appearance-label"><Eye size={15}/><div><b>Live preview</b><small>Buttons and sidebar selection use your accent</small></div></div><div className="appearance-preview"><div className="appearance-preview-nav"><span className="appearance-preview-brand"><span/>CampaignNova</span><span className="appearance-preview-nav-item active"><i/>Marketing</span><span className="appearance-preview-nav-item"><i/>Customer 360</span></div><div className="appearance-preview-content"><span className="eyebrow">Your workspace</span><h3>Campaign overview</h3><p>Color and contrast preview</p><div><button type="button" className="primary-btn">Primary action</button><button type="button" className="secondary-btn">Secondary</button><span className="appearance-preview-dot"/></div></div></div></div>
    <p className="appearance-note">Appearance preferences are stored locally in this browser and are separate from your company’s shared settings.</p>
  </section>;
}
