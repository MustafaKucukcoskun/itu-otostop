"use client";

import { useRef, useState, useCallback, type ReactNode } from "react";

interface SpotlightCardProps {
  children: ReactNode;
  className?: string;
  spotlightColor?: string;
  spotlightSize?: number;
  /** Gradient accent line along top edge */
  accent?: string;
}

export function SpotlightCard({
  children,
  className = "",
  spotlightColor = "oklch(0.7 0.18 195 / 0.12)",
  spotlightSize = 350,
  accent,
}: SpotlightCardProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [opacity, setOpacity] = useState(0);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    setPosition({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  }, []);

  return (
    <div
      ref={ref}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setOpacity(1)}
      onMouseLeave={() => setOpacity(0)}
      className={`spotlight-card relative rounded-2xl overflow-hidden ${className}`}
    >
      {/* Accent gradient top border */}
      {accent && (
        <div
          className="absolute top-0 left-0 right-0 h-px z-10"
          style={{
            background: `linear-gradient(90deg, transparent, ${accent}, transparent)`,
          }}
        />
      )}

      {/* Mouse-tracking spotlight */}
      <div
        className="pointer-events-none absolute inset-0 z-[1] transition-opacity duration-500"
        style={{
          opacity,
          background: `radial-gradient(${spotlightSize}px circle at ${position.x}px ${position.y}px, ${spotlightColor}, transparent 70%)`,
        }}
      />

      {/* Content */}
      <div className="relative z-[2]">{children}</div>
    </div>
  );
}
