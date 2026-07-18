import './globals.css'
export const metadata = { title: 'Loyalyn', description: 'Modern loyalty infrastructure for growing brands' }
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ar" dir="rtl"><body>{children}</body></html>
}
