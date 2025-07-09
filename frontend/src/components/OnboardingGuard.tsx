"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Loader2 } from "lucide-react";
import { apiRequest } from "@/lib/api";

interface OnboardingStatus {
  onboarding_complete: boolean;
  missing_required_settings: string[];
  setup_required: boolean;
}

interface OnboardingGuardProps {
  children: React.ReactNode;
}

export default function OnboardingGuard({ children }: OnboardingGuardProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [isLoading, setIsLoading] = useState(true);
  const [onboardingStatus, setOnboardingStatus] = useState<OnboardingStatus | null>(null);

  const checkOnboardingStatus = useCallback(async () => {
    try {
      const status = await apiRequest('/api/user-settings/status') as OnboardingStatus;
      setOnboardingStatus(status);
      
      // If setup is required and user is not on onboarding page, redirect
      if (status.setup_required && pathname !== '/onboarding') {
        router.push('/onboarding');
        return;
      }
      
      // If setup is complete and user is on onboarding page, redirect to home
      if (!status.setup_required && pathname === '/onboarding') {
        router.push('/');
        return;
      }
      
      setIsLoading(false);
    } catch (error) {
      console.error('Failed to check onboarding status:', error);
      // On error, assume onboarding is needed
      if (pathname !== '/onboarding') {
        router.push('/onboarding');
      } else {
        setIsLoading(false);
      }
    }
  }, [router, pathname]);

  useEffect(() => {
    checkOnboardingStatus();
  }, [checkOnboardingStatus]);

  // Show loading spinner while checking status
  if (isLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-primary" />
          <p className="text-muted-foreground">Initializing Nova...</p>
        </div>
      </div>
    );
  }

  // If we're on the onboarding page, always show it
  if (pathname === '/onboarding') {
    return <>{children}</>;
  }

  // If onboarding is required but we're not on onboarding page, 
  // the useEffect will redirect, so show loading
  if (onboardingStatus?.setup_required) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-primary" />
          <p className="text-muted-foreground">Redirecting to setup...</p>
        </div>
      </div>
    );
  }

  // Onboarding complete, show the app
  return <>{children}</>;
}