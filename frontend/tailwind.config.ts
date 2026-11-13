import type { Config } from 'tailwindcss';
const config: Config = { content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'], theme: { extend: { colors: { navy: '#10172C', brand: '#315EFA', violet: '#8157F5', teal: '#14B8A6' } } }, plugins: [] };
export default config;
