import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  metadataBase: new URL('https://mac-health-checkup.young-hen-7947.chatgpt.site'),
  title: 'Mac Health Checkup — Local-first Mac diagnostics',
  description: 'Explore the complete Mac Health Checkup product showcase, then download the full macOS app.',
  openGraph: {
    title: 'Mac Health Checkup',
    description: 'Know your Mac. Keep your data.',
    type: 'website',
    images: [{ url: '/og.png', width: 1731, height: 909, alt: 'Mac Health Checkup — Know your Mac. Keep your data.' }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Mac Health Checkup',
    description: 'Know your Mac. Keep your data.',
    images: ['/og.png'],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
