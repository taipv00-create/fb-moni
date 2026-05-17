import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'FB Group Monitor',
  description: 'Theo dõi bài viết nhóm Facebook',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi">
      <body>{children}</body>
    </html>
  );
}
