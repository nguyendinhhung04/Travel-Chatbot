import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Hide the Next.js development indicator (the floating "N" button).
  // It can overlap the chat shell while developing locally.
  devIndicators: false,
  ...(process.env.NEXT_DIST_DIR
    ? { distDir: process.env.NEXT_DIST_DIR }
    : {}),
};

export default nextConfig;
