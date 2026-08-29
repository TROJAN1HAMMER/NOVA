import { memo } from "react";

/**
 * Enterprise dark ambient background for NOVA landing page.
 * Provides a deep navy/near-black atmosphere with faint architectural grid,
 * subtle radial lighting, slow data particles, and glowing node connection lines.
 */
export const LandingBackground = memo(function LandingBackground() {
  return (
    <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden bg-[#07090e]" aria-hidden="true">
      <style>{`
        @keyframes nova-particle-float {
          0%, 100% { transform: translateY(0px) translateX(0px); opacity: 0.3; }
          50% { transform: translateY(-30px) translateX(15px); opacity: 0.7; }
        }
        @keyframes nova-pulse-glow {
          0%, 100% { opacity: 0.25; transform: scale(1); }
          50% { opacity: 0.45; transform: scale(1.08); }
        }
        @keyframes nova-grid-flow {
          0% { background-position: 0px 0px; }
          100% { background-position: 40px 40px; }
        }
        .nova-bg-grid {
          background-image:
            linear-gradient(to right, rgba(56, 189, 248, 0.04) 1px, transparent 1px),
            linear-gradient(to bottom, rgba(56, 189, 248, 0.04) 1px, transparent 1px);
          background-size: 40px 40px;
          animation: nova-grid-flow 60s linear infinite;
        }
        .nova-glow-cyan {
          background: radial-gradient(circle, rgba(14, 165, 233, 0.15) 0%, rgba(3, 105, 161, 0.03) 50%, transparent 70%);
          animation: nova-pulse-glow 14s ease-in-out infinite;
        }
        .nova-glow-blue {
          background: radial-gradient(circle, rgba(59, 130, 246, 0.14) 0%, rgba(29, 78, 216, 0.02) 50%, transparent 70%);
          animation: nova-pulse-glow 18s ease-in-out infinite reverse;
        }
        @media (prefers-reduced-motion: reduce) {
          .nova-bg-grid, .nova-glow-cyan, .nova-glow-blue {
            animation: none;
          }
        }
      `}</style>

      {/* Grid Overlay */}
      <div className="nova-bg-grid absolute inset-0 opacity-80" />

      {/* Ambient Lighting Orbs */}
      <div className="nova-glow-cyan absolute -left-40 -top-40 size-[600px] rounded-full blur-3xl" />
      <div className="nova-glow-blue absolute -right-40 top-1/4 size-[700px] rounded-full blur-3xl" />
      <div className="nova-glow-cyan absolute bottom-[-10rem] left-1/3 size-[650px] rounded-full blur-3xl" />

      {/* Subtle Vector Topology Mesh SVG */}
      <svg className="absolute inset-0 size-full opacity-20" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="nova-grad-line" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.05" />
          </linearGradient>
        </defs>
        <path d="M 0,200 Q 400,100 800,300 T 1600,200" fill="none" stroke="url(#nova-grad-line)" strokeWidth="1" />
        <path d="M 0,400 Q 600,600 1200,350 T 2400,500" fill="none" stroke="url(#nova-grad-line)" strokeWidth="1" />
        <circle cx="400" cy="150" r="3" fill="#38bdf8" className="animate-pulse" />
        <circle cx="800" cy="300" r="4" fill="#60a5fa" className="animate-pulse" />
        <circle cx="1200" cy="350" r="3" fill="#38bdf8" className="animate-pulse" />
      </svg>
    </div>
  );
});
