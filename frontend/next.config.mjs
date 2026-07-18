/** @type {import('next').NextConfig} */
const securityHeaders = [
  {key:'X-DNS-Prefetch-Control',value:'off'},
  {key:'X-Content-Type-Options',value:'nosniff'},
  {key:'X-Frame-Options',value:'DENY'},
  {key:'Referrer-Policy',value:'strict-origin-when-cross-origin'},
  {key:'Permissions-Policy',value:'camera=(self), microphone=(), geolocation=()'},
  {key:'Content-Security-Policy',value:[
    "default-src 'self'",
    "base-uri 'self'",
    "frame-ancestors 'none'",
    "object-src 'none'",
    "form-action 'self'",
    "img-src 'self' data: blob: https://api.loyalyn.site http://localhost:8000 http://127.0.0.1:8000",
    "connect-src 'self' https://api.loyalyn.site http://localhost:8000 http://127.0.0.1:8000",
    "media-src 'self' blob:",
    "font-src 'self' data:",
    "style-src 'self' 'unsafe-inline'",
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
  ].join('; ')},
]

/** @type {import('next').NextConfig} */
const nextConfig = {
  poweredByHeader:false,
  async headers(){return [{source:'/:path*',headers:securityHeaders}]},
}

export default nextConfig
