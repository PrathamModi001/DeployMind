"use client";

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Github, Rocket, Zap, Shield, Terminal, Activity, ArrowRight, Sparkles } from 'lucide-react';
import { motion } from 'framer-motion';

export default function Home() {
  const router = useRouter();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    // Check if user is logged in
    const token = localStorage.getItem('token');
    if (token) {
      router.push('/dashboard');
    }
  }, [router]);

  if (!mounted) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background relative overflow-hidden">
      {/* Animated gradient orbs (Stripe-style) */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <motion.div
          className="absolute top-0 left-1/4 w-[500px] h-[500px] rounded-full bg-primary/10 blur-3xl"
          animate={{
            scale: [1, 1.3, 1],
            opacity: [0.3, 0.5, 0.3],
          }}
          transition={{
            duration: 10,
            repeat: Infinity,
            ease: "easeInOut"
          }}
        />
        <motion.div
          className="absolute bottom-0 right-1/4 w-[500px] h-[500px] rounded-full bg-blue-500/10 blur-3xl"
          animate={{
            scale: [1.3, 1, 1.3],
            opacity: [0.5, 0.3, 0.5],
          }}
          transition={{
            duration: 12,
            repeat: Infinity,
            ease: "easeInOut"
          }}
        />
      </div>

      {/* Hero Section */}
      <div className="relative z-10">
        {/* Header */}
        <header className="border-b border-border/50 backdrop-blur-sm">
          <div className="container mx-auto px-4 h-16 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-primary/50 flex items-center justify-center">
                <Rocket className="w-5 h-5 text-white" />
              </div>
              <span className="text-lg font-semibold">DeployMind</span>
            </div>

            <Button
              onClick={() => router.push('/login')}
              variant="ghost"
              className="gap-2"
            >
              <Github className="w-4 h-4" />
              Sign in with GitHub
            </Button>
          </div>
        </header>

        {/* Hero Content */}
        <div className="container mx-auto px-4 py-24 md:py-32">
          <div className="max-w-4xl mx-auto text-center">
            {/* Badge */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 text-sm text-primary mb-8"
            >
              <Sparkles className="w-4 h-4" />
              AI-Powered Deployment Platform
            </motion.div>

            {/* Headline */}
            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.1 }}
              className="text-5xl md:text-7xl font-bold mb-6 bg-gradient-to-r from-foreground via-foreground/90 to-foreground/70 bg-clip-text text-transparent"
            >
              Ship faster with
              <br />
              <span className="bg-gradient-to-r from-primary via-blue-400 to-primary bg-clip-text text-transparent">
                AI-powered deployments
              </span>
            </motion.h1>

            {/* Subheadline */}
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.2 }}
              className="text-xl text-muted-foreground mb-12 max-w-2xl mx-auto leading-relaxed"
            >
              Automated security scanning, intelligent builds, and zero-downtime deployments.
              Connect your GitHub repo and deploy in seconds.
            </motion.p>

            {/* CTA Buttons */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.3 }}
              className="flex flex-col sm:flex-row items-center justify-center gap-4"
            >
              <Button
                onClick={() => router.push('/login')}
                size="lg"
                className="w-full sm:w-auto h-12 px-8 text-base bg-foreground text-background hover:bg-foreground/90 shadow-lg hover-lift gap-2"
              >
                <Github className="w-5 h-5" />
                Start Deploying
                <ArrowRight className="w-4 h-4" />
              </Button>

              <Button
                variant="outline"
                size="lg"
                className="w-full sm:w-auto h-12 px-8 text-base hover-lift"
                onClick={() => {
                  // Scroll to features
                  document.getElementById('features')?.scrollIntoView({ behavior: 'smooth' });
                }}
              >
                See how it works
              </Button>
            </motion.div>
          </div>
        </div>

        {/* Features Section */}
        <div id="features" className="container mx-auto px-4 py-24">
          <div className="grid md:grid-cols-3 gap-8 max-w-6xl mx-auto">
            {/* Feature 1 */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5 }}
              className="group p-8 rounded-2xl bg-card border border-border/50 hover:border-border transition-all hover-lift"
            >
              <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                <Shield className="w-6 h-6 text-primary" />
              </div>
              <h3 className="text-xl font-semibold mb-3">AI Security Scanning</h3>
              <p className="text-muted-foreground leading-relaxed">
                Automated vulnerability detection powered by Trivy and AI agents.
                Catch issues before they reach production.
              </p>
            </motion.div>

            {/* Feature 2 */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: 0.1 }}
              className="group p-8 rounded-2xl bg-card border border-border/50 hover:border-border transition-all hover-lift"
            >
              <div className="w-12 h-12 rounded-xl bg-blue-500/10 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                <Zap className="w-6 h-6 text-blue-400" />
              </div>
              <h3 className="text-xl font-semibold mb-3">Intelligent Builds</h3>
              <p className="text-muted-foreground leading-relaxed">
                Smart Dockerfile detection and optimization. Auto-detects languages
                and builds optimized containers.
              </p>
            </motion.div>

            {/* Feature 3 */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: 0.2 }}
              className="group p-8 rounded-2xl bg-card border border-border/50 hover:border-border transition-all hover-lift"
            >
              <div className="w-12 h-12 rounded-xl bg-green-500/10 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                <Activity className="w-6 h-6 text-green-400" />
              </div>
              <h3 className="text-xl font-semibold mb-3">Zero-Downtime Deploys</h3>
              <p className="text-muted-foreground leading-relaxed">
                Rolling deployments with health checks. Automatic rollbacks
                if issues are detected.
              </p>
            </motion.div>
          </div>
        </div>

        {/* CTA Section */}
        <div className="container mx-auto px-4 py-24">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="max-w-4xl mx-auto text-center bg-gradient-to-br from-primary/10 via-blue-500/5 to-transparent border border-primary/20 rounded-3xl p-12"
          >
            <Terminal className="w-12 h-12 text-primary mx-auto mb-6" />
            <h2 className="text-3xl md:text-4xl font-bold mb-4">
              Ready to deploy smarter?
            </h2>
            <p className="text-lg text-muted-foreground mb-8">
              Join developers shipping production-grade applications faster with AI
            </p>
            <Button
              onClick={() => router.push('/login')}
              size="lg"
              className="h-12 px-8 text-base bg-foreground text-background hover:bg-foreground/90 shadow-lg hover-lift gap-2"
            >
              <Github className="w-5 h-5" />
              Get Started Free
              <ArrowRight className="w-4 h-4" />
            </Button>
          </motion.div>
        </div>

        {/* Footer */}
        <footer className="border-t border-border/50 backdrop-blur-sm mt-24">
          <div className="container mx-auto px-4 py-8">
            <div className="flex flex-col md:flex-row items-center justify-between gap-4 text-sm text-muted-foreground">
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-primary to-primary/50 flex items-center justify-center">
                  <Rocket className="w-4 h-4 text-white" />
                </div>
                <span>© 2026 DeployMind. All rights reserved.</span>
              </div>
              <div className="flex items-center gap-6">
                <a href="#" className="hover:text-foreground transition-colors">Terms</a>
                <a href="#" className="hover:text-foreground transition-colors">Privacy</a>
                <a href="#" className="hover:text-foreground transition-colors">Docs</a>
                <a href="#" className="hover:text-foreground transition-colors">GitHub</a>
              </div>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}
