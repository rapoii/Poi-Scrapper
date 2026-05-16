import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@poi/shared"],
  // typedRoutes belum didukung Turbopack di Next 15.1; re-enable kalau
  // pindah ke webpack atau Next 15.2+ (Turbopack typed routes).
  async rewrites() {
    // Proxy ke FastAPI saat dev supaya tidak perlu CORS + cookie issue.
    const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${apiBase}/:path*`,
      },
    ];
  },
};

export default nextConfig;
