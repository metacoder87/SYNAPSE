const backendUrl = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";

/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    // Proxy API calls to the FastAPI backend (host dev or container)
    return [
      {
        source: "/api/backend/:path*",
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
};
export default nextConfig;
