import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  experimental: {
    // Pages render in the browser after login (token in localStorage), so the server can't prerender
    // them. Only validate instant navigation for segments that opt in with `export const instant`.
    instantInsights: { validationLevel: "manual-warning" },
  },
  // Chats used to be called "works": keep old links working.
  async redirects() {
    return [
      { source: "/works/:path*", destination: "/chats/:path*", permanent: true },
      { source: "/admin/works/:path*", destination: "/admin/chats/:path*", permanent: true },
      { source: "/admin/works", destination: "/admin/chats", permanent: true },
    ];
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
