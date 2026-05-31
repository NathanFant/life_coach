/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Compile shared workspace packages from source.
  transpilePackages: ["@repo/ui", "@repo/core", "@repo/api-client", "@repo/types"],
};

export default nextConfig;
