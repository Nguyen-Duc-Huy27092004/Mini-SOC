/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        cyber: {
          bg: '#080C14',        // Deep Space Charcoal
          card: '#0F1626',      // Dark Slate Carbon Card
          border: '#1E293B',    // Slate Border
          text: '#F8FAFC',      // Slate White
          muted: '#94A3B8',     // Muted Slate Gray
          ok: '#10B981',        // Neon Emerald Green
          warning: '#F59E0B',   // Neon Amber Yellow
          critical: '#EF4444',  // Neon Crimson Red
          accent: '#06B6D4',    // Cyber Neon Cyan
          glow: 'rgba(6, 182, 212, 0.15)'
        }
      },
      boxShadow: {
        'cyber-neon': '0 0 12px rgba(6, 182, 212, 0.25)',
        'cyber-red': '0 0 12px rgba(239, 68, 68, 0.25)',
        'cyber-green': '0 0 12px rgba(16, 185, 129, 0.25)',
        'cyber-card': '0 4px 20px rgba(0, 0, 0, 0.35)',
      },
      backgroundImage: {
        'cyber-grid': 'linear-gradient(to right, rgba(30, 41, 59, 0.15) 1px, transparent 1px), linear-gradient(to bottom, rgba(30, 41, 59, 0.15) 1px, transparent 1px)',
      }
    },
  },
  plugins: [],
}
