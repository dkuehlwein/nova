import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'standalone',
  // API requests to backend
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/:path*`
      }
    ];
  }
};

export default nextConfig;
