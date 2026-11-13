export type AppearanceMode = 'light' | 'dark' | 'contrast' | 'grey';
export type Accent = { name: string; hex: string };
export type FontChoice = { name: string; stack: string };
export type Appearance = { mode: AppearanceMode; accent: string; font: string };

export const APPEARANCE_KEY = 'campaignnova-appearance-v1';

export const ACCENTS: Accent[] = [
  {name:'Cobalt',hex:'#315efa'}, {name:'Blue',hex:'#2563eb'}, {name:'Indigo',hex:'#4f46e5'},
  {name:'Violet',hex:'#7c3aed'}, {name:'Purple',hex:'#9333ea'}, {name:'Fuchsia',hex:'#c026d3'},
  {name:'Pink',hex:'#db2777'}, {name:'Rose',hex:'#e11d48'}, {name:'Red',hex:'#dc2626'},
  {name:'Orange',hex:'#ea580c'}, {name:'Amber',hex:'#d97706'}, {name:'Yellow',hex:'#ca8a04'},
  {name:'Lime',hex:'#65a30d'}, {name:'Green',hex:'#16a34a'}, {name:'Emerald',hex:'#059669'},
  {name:'Teal',hex:'#0d9488'}, {name:'Cyan',hex:'#0891b2'}, {name:'Sky',hex:'#0284c7'},
  {name:'Slate',hex:'#475569'}, {name:'Charcoal',hex:'#374151'},
];

export const COLOR_THEMES = [
  {name:'Ocean',hex:'#315efa',description:'Clear blue'},
  {name:'Amethyst',hex:'#7c3aed',description:'Rich violet'},
  {name:'Forest',hex:'#059669',description:'Calm green'},
  {name:'Sunset',hex:'#ea580c',description:'Warm orange'},
  {name:'Rose',hex:'#db2777',description:'Modern pink'},
];

export const FONTS: FontChoice[] = [
  {name:'Inter',stack:'Inter, ui-sans-serif, system-ui, sans-serif'},
  {name:'System UI',stack:'system-ui, -apple-system, BlinkMacSystemFont, sans-serif'},
  {name:'Arial',stack:'Arial, Helvetica, sans-serif'},
  {name:'Helvetica Neue',stack:'"Helvetica Neue", Helvetica, Arial, sans-serif'},
  {name:'Verdana',stack:'Verdana, Geneva, sans-serif'},
  {name:'Tahoma',stack:'Tahoma, Verdana, sans-serif'},
  {name:'Trebuchet MS',stack:'"Trebuchet MS", Arial, sans-serif'},
  {name:'Georgia',stack:'Georgia, serif'},
  {name:'Times New Roman',stack:'"Times New Roman", Times, serif'},
  {name:'Courier New',stack:'"Courier New", monospace'},
];

export const DEFAULT_APPEARANCE: Appearance = {mode:'light',accent:'#315efa',font:'Inter'};

export function readAppearance(): Appearance {
  if (typeof window === 'undefined') return DEFAULT_APPEARANCE;
  try {
    const parsed = JSON.parse(window.localStorage.getItem(APPEARANCE_KEY) || 'null');
    const mode: AppearanceMode = ['light','dark','contrast','grey'].includes(parsed?.mode) ? parsed.mode : 'light';
    const accent = /^#[\da-f]{6}$/i.test(parsed?.accent || '') ? parsed.accent : DEFAULT_APPEARANCE.accent;
    const font = FONTS.some(item=>item.name===parsed?.font) ? parsed.font : DEFAULT_APPEARANCE.font;
    return {mode,accent,font};
  } catch { return DEFAULT_APPEARANCE; }
}

function rgb(hex: string) {
  const value=hex.replace('#','');
  return [0,2,4].map(index=>parseInt(value.slice(index,index+2),16)).join(', ');
}

function textColor(hex: string) {
  const channels=[0,2,4].map(index=>parseInt(hex.replace('#','').slice(index,index+2),16)/255)
    .map(channel=>channel<=.04045?channel/12.92:((channel+.055)/1.055)**2.4);
  const luminance=.2126*channels[0]+.7152*channels[1]+.0722*channels[2];
  return luminance>.42?'#172033':'#ffffff';
}

export function applyAppearance(appearance: Appearance) {
  if (typeof document === 'undefined') return;
  const root=document.documentElement;
  root.dataset.themeMode=appearance.mode;
  root.style.setProperty('--accent',appearance.accent);
  root.style.setProperty('--accent-rgb',rgb(appearance.accent));
  root.style.setProperty('--accent-contrast',textColor(appearance.accent));
  root.style.setProperty('--font-ui',FONTS.find(item=>item.name===appearance.font)?.stack||FONTS[0].stack);
}

export function saveAppearance(appearance: Appearance) {
  applyAppearance(appearance);
  try { window.localStorage.setItem(APPEARANCE_KEY,JSON.stringify(appearance)); } catch { /* Storage can be disabled by the browser. */ }
}
