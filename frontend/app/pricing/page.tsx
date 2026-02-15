"use client";

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Github, Rocket, Check, Sparkles, Zap, Shield, ArrowRight } from 'lucide-react';
import { motion } from 'framer-motion';

const plans = [
  {
    name: 'Starter',
    price: 0,
    description: 'Perfect for side projects and learning',
    features: [
      '5 deployments per month',
      'Community support',
      'Basic security scanning',
      '1 concurrent deployment',
      '500 MB Docker image storage',
    ],
    cta: 'Start Free',
    popular: false,
    gradient: 'from-blue-500/20 to-blue-600/5',
    border: 'border-blue-500/20',
  },
  {
    name: 'Pro',
    price: 29,
    description: 'For professional developers and teams',
    features: [
      'Unlimited deployments',
      'Priority support (24h response)',
      'Advanced security scanning',
      '5 concurrent deployments',
      '10 GB Docker image storage',
      'Custom domains',
      'Rollback to any version',
      'Health monitoring & alerts',
    ],
    cta: 'Start Free Trial',
    popular: true,
    gradient: 'from-primary/20 to-primary/5',
    border: 'border-primary/50',
    glow: 'shadow-lg shadow-primary/20',
  },
  {
    name: 'Enterprise',
    price: null,
    description: 'For organizations with custom needs',
    features: [
      'Everything in Pro',
      'Dedicated support engineer',
      'SLA guarantees (99.9% uptime)',
      'Unlimited concurrent deployments',
      'Unlimited storage',
      'On-premise deployment',
      'Custom AI model training',
      'Advanced compliance (SOC 2, HIPAA)',
    ],
    cta: 'Contact Sales',
    popular: false,
    gradient: 'from-green-500/20 to-green-600/5',
    border: 'border-green-500/20',
  },
];

const faqs = [
  {
    question: 'Can I switch plans anytime?',
    answer: 'Yes! You can upgrade or downgrade your plan at any time. Changes take effect immediately.',
  },
  {
    question: 'What payment methods do you accept?',
    answer: 'We accept all major credit cards, PayPal, and wire transfers for Enterprise customers.',
  },
  {
    question: 'Do you offer refunds?',
    answer: 'Yes, we offer a 30-day money-back guarantee for all paid plans, no questions asked.',
  },
  {
    question: 'Is there a free trial?',
    answer: 'Yes! Pro plan includes a 14-day free trial. No credit card required to start.',
  },
];

export default function PricingPage() {
  const router = useRouter();
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('monthly');

  return (
    <div className="min-h-screen bg-background relative overflow-hidden">
      {/* Gradient orbs background */}
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

      {/* Header */}
      <header className="relative z-10 border-b border-border/50 backdrop-blur-sm">
        <div className="container mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2 cursor-pointer" onClick={() => router.push('/')}>
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
            Sign in
          </Button>
        </div>
      </header>

      {/* Hero Section */}
      <div className="relative z-10 container mx-auto px-4 py-24">
        <div className="max-w-3xl mx-auto text-center mb-16">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 text-sm text-primary mb-6"
          >
            <Sparkles className="w-4 h-4" />
            Simple, transparent pricing
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="text-5xl md:text-6xl font-bold mb-6 bg-gradient-to-r from-foreground via-foreground/90 to-foreground/70 bg-clip-text text-transparent"
          >
            Deploy smarter,
            <br />
            <span className="bg-gradient-to-r from-primary via-blue-400 to-primary bg-clip-text text-transparent">
              pay less
            </span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="text-xl text-muted-foreground mb-8"
          >
            Start free, upgrade when you need more power. All plans include AI-powered deployments.
          </motion.p>

          {/* Billing Toggle */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="inline-flex items-center gap-4 p-1 rounded-lg bg-card border border-border/50"
          >
            <button
              onClick={() => setBillingCycle('monthly')}
              className={`px-6 py-2 rounded-md text-sm font-medium transition-all ${
                billingCycle === 'monthly'
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              Monthly
            </button>
            <button
              onClick={() => setBillingCycle('yearly')}
              className={`px-6 py-2 rounded-md text-sm font-medium transition-all flex items-center gap-2 ${
                billingCycle === 'yearly'
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              Yearly
              <span className="px-2 py-0.5 rounded-full bg-green-500/10 text-green-400 text-xs">
                Save 20%
              </span>
            </button>
          </motion.div>
        </div>

        {/* Pricing Cards */}
        <div className="grid md:grid-cols-3 gap-8 max-w-7xl mx-auto mb-24">
          {plans.map((plan, index) => (
            <motion.div
              key={plan.name}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 * index }}
              className={`relative overflow-hidden rounded-2xl border ${plan.border} ${
                plan.popular ? 'scale-105 md:scale-110' : ''
              }`}
            >
              {/* Popular badge */}
              {plan.popular && (
                <div className="absolute top-0 right-0 left-0 h-px bg-gradient-to-r from-transparent via-primary to-transparent" />
              )}

              {/* Gradient background */}
              <div className={`absolute inset-0 bg-gradient-to-br ${plan.gradient} opacity-50`} />

              {/* Content */}
              <div className="relative p-8 bg-card/50 backdrop-blur-sm">
                {plan.popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1 rounded-full bg-primary text-primary-foreground text-xs font-medium">
                    Most Popular
                  </div>
                )}

                <h3 className="text-2xl font-bold mb-2">{plan.name}</h3>
                <p className="text-sm text-muted-foreground mb-6">{plan.description}</p>

                <div className="mb-8">
                  {plan.price !== null ? (
                    <>
                      <div className="flex items-baseline gap-1">
                        <span className="text-5xl font-bold">
                          ${billingCycle === 'yearly' ? Math.floor(plan.price * 0.8) : plan.price}
                        </span>
                        <span className="text-muted-foreground">/month</span>
                      </div>
                      {billingCycle === 'yearly' && (
                        <p className="text-xs text-muted-foreground mt-1">
                          Billed ${Math.floor(plan.price * 0.8 * 12)}/year
                        </p>
                      )}
                    </>
                  ) : (
                    <div className="text-3xl font-bold">Custom</div>
                  )}
                </div>

                <Button
                  className={`w-full mb-8 ${
                    plan.popular
                      ? 'bg-foreground text-background hover:bg-foreground/90'
                      : 'bg-card hover:bg-card-hover'
                  } ${plan.glow || ''}`}
                  onClick={() => router.push('/login')}
                >
                  {plan.cta}
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>

                <div className="space-y-3">
                  {plan.features.map((feature) => (
                    <div key={feature} className="flex items-start gap-3">
                      <Check className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
                      <span className="text-sm text-foreground/90">{feature}</span>
                    </div>
                  ))}
                </div>
              </div>
            </motion.div>
          ))}
        </div>

        {/* FAQ Section */}
        <div className="max-w-3xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-12">Frequently Asked Questions</h2>

          <div className="grid gap-6">
            {faqs.map((faq, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.1 }}
                className="p-6 rounded-xl bg-card border border-border/50"
              >
                <h3 className="text-lg font-semibold mb-2">{faq.question}</h3>
                <p className="text-muted-foreground">{faq.answer}</p>
              </motion.div>
            ))}
          </div>
        </div>

        {/* CTA Section */}
        <div className="max-w-4xl mx-auto mt-24">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center bg-gradient-to-br from-primary/10 via-blue-500/5 to-transparent border border-primary/20 rounded-3xl p-12"
          >
            <Zap className="w-12 h-12 text-primary mx-auto mb-6" />
            <h2 className="text-3xl font-bold mb-4">
              Ready to deploy smarter?
            </h2>
            <p className="text-lg text-muted-foreground mb-8">
              Start with our free plan. No credit card required.
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
      </div>

      {/* Footer */}
      <footer className="relative z-10 border-t border-border/50 backdrop-blur-sm mt-24">
        <div className="container mx-auto px-4 py-8">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4 text-sm text-muted-foreground">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-primary to-primary/50 flex items-center justify-center">
                <Rocket className="w-4 h-4 text-white" />
              </div>
              <span>© 2026 DeployMind. All rights reserved.</span>
            </div>
            <div className="flex items-center gap-6">
              <a href="/" className="hover:text-foreground transition-colors">Home</a>
              <a href="/pricing" className="hover:text-foreground transition-colors">Pricing</a>
              <a href="#" className="hover:text-foreground transition-colors">Docs</a>
              <a href="#" className="hover:text-foreground transition-colors">GitHub</a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
