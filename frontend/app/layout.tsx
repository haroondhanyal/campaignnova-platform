import './globals.css';
import type { Metadata } from 'next';
import { AppShell } from '@/components/AppShell';
export const metadata: Metadata = {
  title: 'CampaignNova | Think Smarter. Target Better.',
  description: 'AI-powered enterprise campaign management and customer intelligence.',
  icons: {
    icon: '/icon.svg',
    shortcut: '/icon.svg',
    apple: '/icon.svg',
  },
};
export default function RootLayout({children}:{children:React.ReactNode}) { return <html lang="en"><body><AppShell>{children}</AppShell></body></html>; }
