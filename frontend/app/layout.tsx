import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Альфа-Маршрут · знания для вашего дела',
  description: 'Конкурсный прототип персональных образовательных маршрутов для предпринимателей. Hack&Change 2026.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ru"><body>{children}</body></html>;
}
