"use client";

import { useRouter, usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { LayoutDashboard, Rocket, BarChart3, LogOut, Menu } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  useEffect(() => {
    // Check authentication
    const token = localStorage.getItem('token');
    if (!token) {
      router.push('/login');
      return;
    }

    // Fetch user info
    api.auth.me()
      .then(response => {
        setUser(response.data);
        setLoading(false);
      })
      .catch(() => {
        localStorage.removeItem('token');
        router.push('/login');
      });
  }, [router]);

  const handleLogout = () => {
    localStorage.removeItem('token');
    router.push('/login');
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  // Arc-style navigation with color coding
  const navigation = [
    {
      name: 'Dashboard',
      href: '/dashboard',
      icon: LayoutDashboard,
      color: 'purple',
      gradient: 'from-purple-500/10 to-purple-600/5'
    },
    {
      name: 'Deployments',
      href: '/dashboard/deployments',
      icon: Rocket,
      color: 'blue',
      gradient: 'from-blue-500/10 to-blue-600/5'
    },
    {
      name: 'Analytics',
      href: '/dashboard/analytics',
      icon: BarChart3,
      color: 'green',
      gradient: 'from-green-500/10 to-green-600/5'
    },
  ];

  return (
    <div className="min-h-screen bg-background">
      {/* Arc-style Sidebar */}
      <div className={`fixed inset-y-0 left-0 z-50 w-64 bg-sidebar border-r border-border/50 transform transition-transform duration-200 ease-in-out ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="flex flex-col h-full">
          {/* Logo section with gradient */}
          <div className="h-16 px-6 flex items-center border-b border-border/50">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-primary/50 flex items-center justify-center">
                <Rocket className="w-5 h-5 text-white" />
              </div>
              <h1 className="text-xl font-semibold bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent">
                DeployMind
              </h1>
            </div>
          </div>

          {/* Navigation - Arc style */}
          <nav className="flex-1 px-3 py-6 space-y-1">
            {navigation.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;

              return (
                <Link
                  key={item.name}
                  href={item.href}
                  className={`
                    group relative flex items-center gap-3 px-3 py-2.5 rounded-lg
                    transition-all duration-200
                    ${isActive
                      ? `bg-gradient-to-r ${item.gradient} border-l-2 border-${item.color}-500`
                      : 'hover:bg-white/5'
                    }
                  `}
                >
                  {/* Accent line (Arc-style) */}
                  {isActive && (
                    <div className={`absolute left-0 top-0 bottom-0 w-1 rounded-r bg-${item.color}-500`} />
                  )}

                  <Icon className={`
                    w-5 h-5 transition-all duration-200
                    ${isActive
                      ? `text-${item.color}-400`
                      : 'text-muted-foreground group-hover:text-foreground'
                    }
                  `} />

                  <span className={`
                    text-sm font-medium transition-colors duration-200
                    ${isActive
                      ? 'text-foreground'
                      : 'text-muted-foreground group-hover:text-foreground'
                    }
                  `}>
                    {item.name}
                  </span>

                  {/* Hover indicator (subtle glow) */}
                  <div className={`
                    absolute inset-0 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity
                    bg-gradient-to-r ${item.gradient} -z-10
                  `} />
                </Link>
              );
            })}
          </nav>

          {/* User section - Railway style */}
          <div className="p-4 border-t border-border/50">
            <div className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/5 transition-colors cursor-pointer group">
              {/* Avatar with gradient border */}
              <div className="relative">
                <div className="absolute inset-0 rounded-full bg-gradient-to-br from-primary to-primary/50 blur-sm" />
                <div className="relative w-9 h-9 rounded-full bg-gradient-to-br from-primary to-primary/80 flex items-center justify-center text-white text-sm font-semibold ring-2 ring-background">
                  {user?.email?.charAt(0).toUpperCase()}
                </div>
              </div>

              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground truncate">
                  {user?.username || 'User'}
                </p>
                <p className="text-xs text-muted-foreground truncate">
                  {user?.email}
                </p>
              </div>

              <LogOut
                className="w-4 h-4 text-muted-foreground group-hover:text-foreground transition-colors"
                onClick={handleLogout}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className={`transition-all duration-200 ${sidebarOpen ? 'lg:pl-64' : ''}`}>
        {/* Top bar */}
        <div className="sticky top-0 z-40 flex h-16 items-center gap-x-4 border-b border-border bg-card px-4 sm:px-6 lg:px-8">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="text-muted-foreground"
          >
            <Menu className="h-5 w-5" />
          </Button>
          <div className="flex-1" />
        </div>

        {/* Page content with animations */}
        <main className="p-6">
          <AnimatePresence mode="wait">
            <motion.div
              key={pathname}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{
                duration: 0.3,
                ease: [0.4, 0, 0.2, 1], // Linear's easing
              }}
            >
              {children}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}
