import {API_BASE} from '@/lib/api';

export function workspaceSlug(value:string){
  return value.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,70).replace(/-$/,'');
}

export function workspaceLogoSrc(value?:string|null){
  if(!value)return '/icon.svg';
  if(value.startsWith('/company-logos/'))return value;
  return new URL(value,API_BASE).toString();
}
