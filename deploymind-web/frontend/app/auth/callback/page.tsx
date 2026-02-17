"use client";

import { useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { motion } from 'framer-motion';
import { Sparkles, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';
import confetti from 'canvas-confetti';

function AuthCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleCallback = async () => {
      const code = searchParams.get('code');
      const errorParam = searchParams.get('error');

      // Check if user denied access
      if (errorParam) {
        setError('GitHub authorization was denied');
        toast.error('Login cancelled', {
          description: 'You cancelled the GitHub authorization',
        });
        setTimeout(() => router.push('/login'), 2000);
        return;
      }

      // Check if we have the authorization code
      if (!code) {
        setError('No authorization code received');
        toast.error('Login failed', {
          description: 'No authorization code from GitHub',
        });
        setTimeout(() => router.push('/login'), 2000);
        return;
      }

      try {
        // Exchange code for JWT token
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        const response = await fetch(`${apiUrl}/api/auth/github/callback`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code }),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || 'Authentication failed');
        }

        const { access_token } = await response.json();

        // Store JWT token
        localStorage.setItem('token', access_token);

        // Trigger confetti celebration! 🎉
        confetti({
          particleCount: 100,
          spread: 70,
          origin: { y: 0.6 },
          colors: ['#9f7aea', '#60a5fa', '#4ade80', '#fbbf24']
        });

        // Show success toast
        toast.success('Welcome to DeployMind! 🚀', {
          description: 'Let\'s ship something amazing today',
        });

        // Redirect to dashboard
        setTimeout(() => {
          router.push('/dashboard');
        }, 800);
      } catch (error) {
        console.error('GitHub OAuth callback error:', error);
        const errorMessage = error instanceof Error ? error.message : 'Unknown error';
        setError(errorMessage);
        toast.error('Login failed', {
          description: errorMessage,
        });
        setTimeout(() => router.push('/login'), 2000);
      }
    };

    handleCallback();
  }, [searchParams, router]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="bg-card border border-red-500/20 rounded-2xl p-8 max-w-md text-center"
        >
          <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center mx-auto mb-4">
            <AlertCircle className="w-6 h-6 text-red-500" />
          </div>
          <h2 className="text-xl font-semibold mb-2">Authentication Failed</h2>
          <p className="text-muted-foreground mb-4">{error}</p>
          <p className="text-sm text-muted-foreground">Redirecting to login...</p>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="text-center"
      >
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
          className="inline-block mb-4"
        >
          <Sparkles className="w-12 h-12 text-primary" />
        </motion.div>
        <h2 className="text-xl font-semibold mb-2">Completing login...</h2>
        <p className="text-muted-foreground">Please wait while we authenticate you</p>
      </motion.div>
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-background">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-center"
        >
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
            className="inline-block mb-4"
          >
            <Sparkles className="w-12 h-12 text-primary" />
          </motion.div>
          <h2 className="text-xl font-semibold mb-2">Loading...</h2>
        </motion.div>
      </div>
    }>
      <AuthCallbackContent />
    </Suspense>
  );
}
