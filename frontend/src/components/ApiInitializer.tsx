"use client";

import { useEffect } from 'react';
import { initializeApiConfig } from '@/lib/api';

const ApiInitializer = () => {
  useEffect(() => {
    // Initialize API configuration when the app loads
    initializeApiConfig().catch((error) => {
      console.error('Failed to initialize API configuration:', error);
    });
  }, []);

  // This component doesn't render anything
  return null;
};

export default ApiInitializer; 