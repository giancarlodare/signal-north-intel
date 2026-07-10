/** @type {import('next').NextConfig} */
const nextConfig = {
  // Belt-and-suspenders noindex: an HTTP header on every response, in addition
  // to the <meta name="robots"> in the layout. This tool must never be indexed.
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Robots-Tag", value: "noindex, nofollow, noarchive, nosnippet" },
        ],
      },
    ];
  },
};

export default nextConfig;
