"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CheckCircle, AlertCircle, Loader2, ArrowRight, ArrowLeft, Sparkles, Key, User, CheckSquare } from "lucide-react";
import { apiRequest } from "@/lib/api";

interface OnboardingStatus {
  onboarding_complete: boolean;
  missing_required_settings: string[];
  setup_required: boolean;
}

interface UserSettings {
  full_name?: string;
  email?: string;
  timezone: string;
  notes?: string;
}

interface ApiKeyValidation {
  google_api_key?: boolean;
  [key: string]: boolean | undefined;
}

const COMMON_TIMEZONES = [
  'UTC',
  'America/New_York',
  'America/Los_Angeles', 
  'Europe/London',
  'Europe/Paris',
  'Asia/Tokyo',
  'Asia/Shanghai',
  'Australia/Sydney',
];

export default function OnboardingPage() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(0);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [onboardingStatus, setOnboardingStatus] = useState<OnboardingStatus | null>(null);
  
  // Form data
  const [userSettings, setUserSettings] = useState<UserSettings>({
    full_name: '',
    email: '',
    timezone: 'UTC',
    notes: ''
  });
  
  const [apiKeys, setApiKeys] = useState({
    google_api_key: '',
    langsmith_api_key: ''
  });
  
  const [apiKeyValidation, setApiKeyValidation] = useState<ApiKeyValidation>({});
  const [validating, setValidating] = useState<string | null>(null);

  const steps = [
    {
      id: 'welcome',
      title: 'Welcome to Nova',
      description: 'Your AI-powered productivity companion',
      icon: Sparkles
    },
    {
      id: 'api-keys',
      title: 'Connect Services',
      description: 'Configure API keys for enhanced functionality',
      icon: Key
    },
    {
      id: 'user-profile',
      title: 'User Profile',
      description: 'Tell Nova about yourself',
      icon: User
    },
    {
      id: 'complete',
      title: 'Setup Complete',
      description: 'You\'re ready to start using Nova!',
      icon: CheckSquare
    }
  ];

  // Check onboarding status on load
  useEffect(() => {
    checkOnboardingStatus();
  }, []);

  const checkOnboardingStatus = async () => {
    try {
      const status = await apiRequest('/api/user-settings/status');
      setOnboardingStatus(status);
      
      if (!status.setup_required) {
        // Already set up, redirect to main app
        router.push('/');
        return;
      }
      
      // Load existing user settings if any
      try {
        const settings = await apiRequest('/api/user-settings/');
        setUserSettings({
          full_name: settings.full_name || '',
          email: settings.email || '',
          timezone: settings.timezone || 'UTC',
          notes: settings.notes || ''
        });
      } catch (error) {
        console.log('No existing settings found:', error);
      }
      
      setLoading(false);
    } catch (error) {
      console.error('Failed to check onboarding status:', error);
      setLoading(false);
    }
  };

  const validateApiKey = async (keyType: string, value: string) => {
    if (!value.trim()) {
      setApiKeyValidation(prev => ({ ...prev, [keyType]: false }));
      return;
    }
    
    setValidating(keyType);
    try {
      const response = await apiRequest('/api/user-settings/validate-api-key', {
        method: 'POST',
        body: JSON.stringify({
          key_type: keyType,
          api_key: value
        })
      });
      
      setApiKeyValidation(prev => ({ ...prev, [keyType]: response.valid }));
    } catch (error) {
      console.error(`Failed to validate ${keyType}:`, error);
      setApiKeyValidation(prev => ({ ...prev, [keyType]: false }));
    } finally {
      setValidating(null);
    }
  };

  const handleApiKeyChange = (keyType: string, value: string) => {
    setApiKeys(prev => ({ ...prev, [keyType]: value }));
    // Debounced validation
    clearTimeout((window as any)[`validate_${keyType}`]);
    (window as any)[`validate_${keyType}`] = setTimeout(() => {
      validateApiKey(keyType, value);
    }, 500);
  };

  const canProceedFromStep = (step: number) => {
    switch (step) {
      case 0: return true; // Welcome
      case 1: // API Keys - at least Google API key should be valid
        return apiKeyValidation.google_api_key === true;
      case 2: // User Profile - name and email required
        return userSettings.full_name?.trim() && userSettings.email?.trim();
      case 3: return true; // Complete
      default: return false;
    }
  };

  const handleNext = () => {
    if (currentStep < steps.length - 1 && canProceedFromStep(currentStep)) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const completeOnboarding = async () => {
    setSubmitting(true);
    try {
      // Save API keys to .env file (Tier 2)
      const validatedKeys = Object.fromEntries(
        Object.entries(apiKeys).filter(([key, value]) => 
          value && apiKeyValidation[key] === true
        )
      );
      
      if (Object.keys(validatedKeys).length > 0) {
        await apiRequest('/api/user-settings/save-api-keys', {
          method: 'POST',
          body: JSON.stringify({ api_keys: validatedKeys })
        });
      }
      
      // Update user settings (Tier 3)
      await apiRequest('/api/user-settings/', {
        method: 'PATCH',
        body: JSON.stringify(userSettings)
      });
      
      // Mark onboarding complete
      await apiRequest('/api/user-settings/complete-onboarding', {
        method: 'POST'
      });
      
      // Force a full page reload to refresh OnboardingGuard status
      window.location.href = '/';
    } catch (error) {
      console.error('Failed to complete onboarding:', error);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4" />
          <p className="text-muted-foreground">Checking setup status...</p>
        </div>
      </div>
    );
  }

  const currentStepData = steps[currentStep];
  const StepIcon = currentStepData.icon;

  return (
    <div className="min-h-screen bg-background">
      <div className="container max-w-4xl mx-auto py-8">
        {/* Progress Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-2xl font-bold text-foreground">Nova Setup</h1>
              <p className="text-muted-foreground">Let's get you started with your AI productivity companion</p>
            </div>
            <Badge variant="outline">
              Step {currentStep + 1} of {steps.length}
            </Badge>
          </div>
          
          {/* Progress Steps */}
          <div className="flex items-center space-x-4">
            {steps.map((step, index) => {
              const isActive = index === currentStep;
              const isCompleted = index < currentStep;
              const Icon = step.icon;
              
              return (
                <div key={step.id} className="flex items-center">
                  <div className={`flex items-center justify-center w-8 h-8 rounded-full border-2 ${
                    isCompleted 
                      ? 'bg-primary border-primary text-primary-foreground' 
                      : isActive 
                        ? 'border-primary text-primary bg-background'
                        : 'border-muted text-muted-foreground bg-background'
                  }`}>
                    {isCompleted ? (
                      <CheckCircle className="h-4 w-4" />
                    ) : (
                      <Icon className="h-4 w-4" />
                    )}
                  </div>
                  {index < steps.length - 1 && (
                    <div className={`w-12 h-0.5 ml-2 ${
                      isCompleted ? 'bg-primary' : 'bg-muted'
                    }`} />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Step Content */}
        <Card className="mb-8">
          <CardHeader className="text-center">
            <div className="flex justify-center mb-4">
              <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center">
                <StepIcon className="h-8 w-8 text-primary" />
              </div>
            </div>
            <CardTitle className="text-xl">{currentStepData.title}</CardTitle>
            <CardDescription>{currentStepData.description}</CardDescription>
          </CardHeader>
          
          <CardContent className="space-y-6">
            {/* Welcome Step */}
            {currentStep === 0 && (
              <div className="text-center space-y-4">
                <div className="max-w-2xl mx-auto">
                  <p className="text-muted-foreground mb-6">
                    Nova is your AI-powered productivity companion that helps you manage tasks, 
                    organize your workflow, and stay connected with your tools and services.
                  </p>
                  
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                    <div className="p-4 bg-muted/50 rounded-lg">
                      <h3 className="font-medium mb-2">Smart Task Management</h3>
                      <p className="text-sm text-muted-foreground">
                        AI-powered kanban board with intelligent task organization
                      </p>
                    </div>
                    <div className="p-4 bg-muted/50 rounded-lg">
                      <h3 className="font-medium mb-2">Service Integration</h3>
                      <p className="text-sm text-muted-foreground">
                        Connect with Gmail, Calendar, and other productivity tools
                      </p>
                    </div>
                    <div className="p-4 bg-muted/50 rounded-lg">
                      <h3 className="font-medium mb-2">Personalized AI</h3>
                      <p className="text-sm text-muted-foreground">
                        Tailored responses based on your preferences and context
                      </p>
                    </div>
                  </div>
                  
                  <p className="text-sm text-muted-foreground">
                    This setup wizard will guide you through connecting your services and personalizing Nova.
                  </p>
                </div>
              </div>
            )}

            {/* API Keys Step */}
            {currentStep === 1 && (
              <div className="space-y-6 max-w-2xl mx-auto">
                <div className="text-center mb-6">
                  <p className="text-muted-foreground">
                    Connect Nova to external services to unlock its full potential. 
                    Your API keys are stored securely and never shared.
                  </p>
                  <p className="text-xs text-muted-foreground mt-2">
                    * Required fields
                  </p>
                </div>
                
                <div className="space-y-4">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label htmlFor="google_api_key">Google API Key *</Label>
                      <div className="flex items-center space-x-2">
                        {validating === 'google_api_key' && (
                          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                        )}
                        {apiKeyValidation.google_api_key === true && (
                          <CheckCircle className="h-4 w-4 text-green-500" />
                        )}
                        {apiKeyValidation.google_api_key === false && (
                          <AlertCircle className="h-4 w-4 text-red-500" />
                        )}
                      </div>
                    </div>
                    <Input
                      id="google_api_key"
                      type="password"
                      value={apiKeys.google_api_key}
                      onChange={(e) => handleApiKeyChange('google_api_key', e.target.value)}
                      placeholder="Enter your Google API key"
                    />
                    <p className="text-xs text-muted-foreground">
                      Required for Gmail, Calendar, and AI features. 
                      <a href="https://console.cloud.google.com/" target="_blank" rel="noopener noreferrer" 
                         className="text-primary hover:underline ml-1">
                        Get your API key →
                      </a>
                    </p>
                  </div>
                  
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label htmlFor="langsmith_api_key">LangSmith API Key</Label>
                      <div className="flex items-center space-x-2">
                        {validating === 'langsmith_api_key' && (
                          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                        )}
                        {apiKeyValidation.langsmith_api_key === true && (
                          <CheckCircle className="h-4 w-4 text-green-500" />
                        )}
                        {apiKeyValidation.langsmith_api_key === false && apiKeys.langsmith_api_key && (
                          <AlertCircle className="h-4 w-4 text-red-500" />
                        )}
                      </div>
                    </div>
                    <Input
                      id="langsmith_api_key"
                      type="password"
                      value={apiKeys.langsmith_api_key}
                      onChange={(e) => handleApiKeyChange('langsmith_api_key', e.target.value)}
                      placeholder="Enter your LangSmith API key"
                    />
                    <p className="text-xs text-muted-foreground">
                      Optional: For advanced AI debugging and monitoring.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* User Profile Step */}
            {currentStep === 2 && (
              <div className="space-y-6 max-w-2xl mx-auto">
                <div className="text-center mb-6">
                  <p className="text-muted-foreground">
                    Help Nova understand you better by sharing some basic information. 
                    This enables more personalized and relevant responses.
                  </p>
                </div>
                
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="full_name">Full Name *</Label>
                    <Input
                      id="full_name"
                      value={userSettings.full_name || ''}
                      onChange={(e) => setUserSettings(prev => ({ ...prev, full_name: e.target.value }))}
                      placeholder="Enter your full name"
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="email">Email Address *</Label>
                    <Input
                      id="email"
                      type="email"
                      value={userSettings.email || ''}
                      onChange={(e) => setUserSettings(prev => ({ ...prev, email: e.target.value }))}
                      placeholder="Enter your email address"
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="timezone">Timezone</Label>
                    <select
                      id="timezone"
                      value={userSettings.timezone}
                      onChange={(e) => setUserSettings(prev => ({ ...prev, timezone: e.target.value }))}
                      className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {COMMON_TIMEZONES.map((tz) => (
                        <option key={tz} value={tz}>{tz}</option>
                      ))}
                    </select>
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="notes">Additional Context (Optional)</Label>
                    <Textarea
                      id="notes"
                      value={userSettings.notes || ''}
                      onChange={(e) => setUserSettings(prev => ({ ...prev, notes: e.target.value }))}
                      placeholder="Tell Nova about your role, preferences, or anything that would help provide better assistance..."
                      rows={4}
                    />
                    <p className="text-xs text-muted-foreground">
                      This information helps Nova provide more relevant and personalized responses.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Complete Step */}
            {currentStep === 3 && (
              <div className="text-center space-y-6">
                <div className="max-w-2xl mx-auto">
                  <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                    <CheckCircle className="h-8 w-8 text-green-600" />
                  </div>
                  
                  <h3 className="text-xl font-semibold mb-4">You're all set!</h3>
                  
                  <p className="text-muted-foreground mb-6">
                    Nova is now configured and ready to help you be more productive. 
                    You can always adjust these settings later in the Settings page.
                  </p>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                    <div className="p-4 bg-muted/50 rounded-lg text-left">
                      <h4 className="font-medium mb-2">Next Steps</h4>
                      <ul className="text-sm text-muted-foreground space-y-1">
                        <li>• Explore the Kanban board</li>
                        <li>• Start a conversation with Nova</li>
                        <li>• Configure additional settings</li>
                      </ul>
                    </div>
                    <div className="p-4 bg-muted/50 rounded-lg text-left">
                      <h4 className="font-medium mb-2">Tips</h4>
                      <ul className="text-sm text-muted-foreground space-y-1">
                        <li>• Use natural language with Nova</li>
                        <li>• Check the Settings for customization</li>
                        <li>• Enable MCP servers for more features</li>
                      </ul>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Navigation */}
        <div className="flex justify-between">
          <Button
            variant="outline"
            onClick={handleBack}
            disabled={currentStep === 0}
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          
          <div className="flex space-x-2">
            {currentStep < steps.length - 1 ? (
              <Button
                onClick={handleNext}
                disabled={!canProceedFromStep(currentStep)}
              >
                Next
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            ) : (
              <Button
                onClick={completeOnboarding}
                disabled={submitting}
              >
                {submitting ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Completing Setup...
                  </>
                ) : (
                  <>
                    Complete Setup
                    <CheckCircle className="h-4 w-4 ml-2" />
                  </>
                )}
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}