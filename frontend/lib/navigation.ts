import { Activity, Archive, Bot, Boxes, CalendarDays, ChartNoAxesCombined, CircleHelp, ClipboardCheck, ContactRound, FileBarChart2, FileClock, Gauge, GitBranch, Lightbulb, ListFilter, LockKeyhole, Map, Megaphone, Network, Package, PanelsTopLeft, Radio, Settings2, ShieldCheck, Sparkles, Users, Workflow } from 'lucide-react';
export const navGroups = [
 { label:'Workspace', items:[{title:'Executive Dashboard',href:'/',icon:Gauge},{title:'Scenario Studio',href:'/scenario-studio',icon:Map},{title:'Campaign Studio',href:'/campaign-studio',icon:Megaphone},{title:'Campaign Calendar',href:'/campaign-calendar',icon:CalendarDays},{title:'Customer 360',href:'/customer-360',icon:ContactRound}]},
 { label:'Audience & Offers', items:[{title:'Audience & Segments',href:'/audience-segments',icon:Users},{title:'AI Segment Builder',href:'/ai-segment-builder',icon:Sparkles},{title:'Offer Management',href:'/offer-management',icon:Package}]},
 { label:'Orchestration', items:[{title:'Journey Orchestration',href:'/journey-orchestration',icon:GitBranch},{title:'Workflow Automation',href:'/workflow-automation',icon:Workflow},{title:'Campaign Execution',href:'/campaign-execution',icon:Activity},{title:'Channel Management',href:'/channel-management',icon:Radio}]},
 { label:'Intelligence', items:[{title:'Nova AI Assistant',href:'/nova-ai',icon:Bot},{title:'Predictive Intelligence',href:'/predictive-intelligence',icon:Lightbulb},{title:'A/B Testing',href:'/ab-testing',icon:ChartNoAxesCombined},{title:'Analytics & Insights',href:'/analytics-insights',icon:PanelsTopLeft},{title:'Reports & Exports',href:'/reports-exports',icon:FileBarChart2}]},
 { label:'Platform', items:[{title:'Data Integration Hub',href:'/integrations',icon:Network},{title:'Business Rules Engine',href:'/business-rules',icon:Boxes},{title:'Approvals & Governance',href:'/approvals',icon:ShieldCheck},{title:'Feature Access',href:'/feature-access',icon:LockKeyhole},{title:'User & Role Management',href:'/user-roles',icon:Users},{title:'Audit Logs',href:'/audit-logs',icon:FileClock},{title:'System Configuration',href:'/settings',icon:Settings2}]}
];
export const allNav = navGroups.flatMap(g=>g.items);
const departmentModules:Record<string,Set<string>>={
 Marketing:new Set(['campaign-studio','campaign-calendar','scenario-studio','customer-360','audience-segments','offer-management','journey-orchestration','workflow-automation','campaign-execution','nova-ai','analytics-insights','reports-exports','business-rules','approvals']),
 Commercial:new Set(['campaign-studio','campaign-calendar','customer-360','scenario-studio','audience-segments','offer-management','analytics-insights','reports-exports','business-rules','approvals']),
 CVM:new Set(['campaign-studio','scenario-studio','customer-360','audience-segments','ai-segment-builder','offer-management','journey-orchestration','workflow-automation','campaign-execution','nova-ai','predictive-intelligence','analytics-insights','reports-exports','business-rules','approvals']),
 Segments:new Set(['customer-360','audience-segments','ai-segment-builder','predictive-intelligence','analytics-insights','reports-exports']),
 'Customer Care':new Set(['customer-360']),
 'Retail Sales':new Set(['campaign-studio','campaign-calendar','customer-360','scenario-studio','offer-management','analytics-insights','reports-exports']),
 'Digital Services':new Set(['campaign-studio','campaign-calendar','scenario-studio','customer-360','offer-management','journey-orchestration','workflow-automation','campaign-execution','business-rules','analytics-insights','reports-exports']),
 'Business Development':new Set(['campaign-studio','campaign-calendar','customer-360','scenario-studio','offer-management','analytics-insights','reports-exports','approvals']),
 'Business Operations':new Set(['campaign-studio','campaign-calendar','scenario-studio','audience-segments','offer-management','journey-orchestration','workflow-automation','campaign-execution','business-rules','approvals','reports-exports']),
 'Product & Services':new Set(['campaign-studio','campaign-calendar','scenario-studio','customer-360','audience-segments','offer-management','analytics-insights','reports-exports']),
 Sales:new Set(['campaign-studio','campaign-calendar','scenario-studio','customer-360','offer-management','analytics-insights','reports-exports']),
 'Customer Success':new Set(['customer-360','audience-segments','analytics-insights','reports-exports']),
 Operations:new Set(['campaign-studio','campaign-calendar','scenario-studio','audience-segments','offer-management','journey-orchestration','workflow-automation','campaign-execution','business-rules','approvals','reports-exports']),
 'Carrier & International Wholesale':new Set(['analytics-insights','reports-exports']),
 'Campaign Operations':new Set(['campaign-studio','campaign-calendar','scenario-studio','audience-segments','offer-management','journey-orchestration','workflow-automation','campaign-execution','business-rules','approvals','reports-exports']),
 'Data & Analytics':new Set(['predictive-intelligence','analytics-insights','reports-exports','ab-testing']),
 'Technology & IT':new Set(['integrations','channel-management','settings','audit-logs']),
 Engineering:new Set(['integrations','channel-management','settings','audit-logs']),
 Finance:new Set(['analytics-insights','reports-exports']),
 'People & Organization':new Set(),
 'Human Resources':new Set(),
 'Legal & Regulatory':new Set(['approvals','audit-logs','business-rules','reports-exports']),
 Administration:new Set(allNav.map(item=>item.href.slice(1))),
};
export function canSeeModule(user:{role:string;department:string;enabled_modules?:string[];department_modules?:string[];module_access?:string[]|null},href:string){
 if(href==='/'){
  if(user.enabled_modules&&!user.enabled_modules.includes('dashboard'))return false;
  return !Array.isArray(user.module_access)||user.module_access.includes('dashboard');
 }
 const module=href.slice(1),isAdmin=['Super Admin','Organization Admin','Admin'].includes(user.role);
 if(user.enabled_modules&&!user.enabled_modules.includes(module))return false;
 if(isAdmin)return !Array.isArray(user.module_access)||user.module_access.includes(module);
 if(Array.isArray(user.module_access))return user.module_access.includes(module);
 if(module==='feature-access')return true;
 return user.department_modules?user.department_modules.includes(module):departmentModules[user.department]?.has(module)||false;
}
export function visibleNavGroups(user:{role:string;department:string;enabled_modules?:string[];department_modules?:string[];module_access?:string[]|null}){return navGroups.map(group=>({...group,items:group.items.filter(item=>canSeeModule(user,item.href))})).filter(group=>group.items.length>0)}
