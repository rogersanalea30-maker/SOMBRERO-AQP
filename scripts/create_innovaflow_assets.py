# -*- coding: utf-8 -*-
import sys
import os

def create_svgs():
    sys.stdout.reconfigure(encoding='utf-8')
    # 1. Full Horizontal Logo: InnovaFlow Perú
    logo_svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 160" width="100%" height="100%">
  <defs>
    <!-- Gradients -->
    <linearGradient id="flowCyanBlue" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#00d2ff"/>
      <stop offset="100%" stop-color="#0066ff"/>
    </linearGradient>
    <linearGradient id="flowBlueIndigo" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0066ff"/>
      <stop offset="100%" stop-color="#6366f1"/>
    </linearGradient>
    <linearGradient id="flowPeruRed" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#dc2626"/>
      <stop offset="100%" stop-color="#ff4757"/>
    </linearGradient>
    <linearGradient id="textFlowGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#0066ff"/>
      <stop offset="100%" stop-color="#6366f1"/>
    </linearGradient>
    <!-- Drop Shadow -->
    <filter id="softGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="6" stdDeviation="8" flood-color="#0066ff" flood-opacity="0.25"/>
    </filter>
    <filter id="redGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#dc2626" flood-opacity="0.35"/>
    </filter>
  </defs>

  <!-- Group Emblem (Left: 20 to 140, Height 140) -->
  <g transform="translate(15, 12)" filter="url(#softGlow)">
    <!-- Background rounded squircle shield -->
    <rect x="5" y="5" width="126" height="126" rx="32" fill="#0f172a" />
    
    <!-- Outer Dynamic Infinity / Flow Wave Loop (I and F fusion) -->
    <!-- Lower flow wave (Cyan to Blue) -->
    <path d="M 32 94 C 32 108, 48 116, 68 116 C 94 116, 114 96, 114 72 C 114 54, 102 44, 88 44 C 70 44, 58 56, 58 72 C 58 84, 68 92, 80 92 C 86 92, 94 88, 98 82" 
          fill="none" stroke="url(#flowCyanBlue)" stroke-width="11" stroke-linecap="round"/>

    <!-- Upper dynamic ribbon forming the "F" crossbar and forward speed arrow -->
    <path d="M 36 38 C 48 24, 76 20, 96 28 C 108 34, 116 46, 118 56" 
          fill="none" stroke="url(#flowBlueIndigo)" stroke-width="11" stroke-linecap="round"/>

    <!-- The "F" middle bar and dynamic speed slash -->
    <path d="M 52 64 L 92 64" 
          fill="none" stroke="url(#flowCyanBlue)" stroke-width="10" stroke-linecap="round"/>

    <!-- Peru Red Accent Wave & Spark (Representing Peru's dynamic surge) -->
    <path d="M 40 46 C 40 34, 54 28, 68 28 L 102 28 C 110 28, 116 34, 116 42" 
          fill="none" stroke="url(#flowPeruRed)" stroke-width="7" stroke-linecap="round" filter="url(#redGlow)"/>

    <!-- Glowing Accent Node -->
    <circle cx="102" cy="28" r="4.5" fill="#ffffff" />
    <circle cx="98" cy="82" r="3.5" fill="#00d2ff" />
  </g>

  <!-- Typography Wordmark -->
  <!-- "Innova" -->
  <text x="165" y="86" font-family="'Montserrat', 'Figtree', system-ui, -apple-system, sans-serif" font-size="52" font-weight="900" fill="#0f172a" letter-spacing="-1.5">Innova<tspan fill="url(#textFlowGrad)">Flow</tspan></text>

  <!-- "PERÚ" Modern Badge -->
  <g transform="translate(485, 48)">
    <rect x="0" y="0" width="94" height="34" rx="10" fill="#dc2626"/>
    <!-- Micro Peru flag bar accent inside badge -->
    <rect x="6" y="7" width="4" height="20" rx="2" fill="#ffffff" opacity="0.9"/>
    <text x="52" y="23" font-family="'Montserrat', 'Figtree', system-ui, sans-serif" font-size="15" font-weight="900" fill="#ffffff" letter-spacing="3" text-anchor="middle">PERÚ</text>
  </g>

  <!-- Subtitle Tagline -->
  <text x="168" y="118" font-family="'Figtree', 'Montserrat', system-ui, sans-serif" font-size="13" font-weight="800" fill="#64748b" letter-spacing="2.8">GESTIÓN INTELIGENTE &amp; FACTURACIÓN ELECTRÓNICA</text>

  <!-- Feature Dots (Cloud, Real-time, SUNAT) -->
  <g transform="translate(168, 134)">
    <circle cx="4" cy="4" r="3" fill="#10b981"/>
    <text x="13" y="7" font-family="system-ui, sans-serif" font-size="10" font-weight="700" fill="#059669">SUNAT UBL 2.1</text>
    
    <circle cx="120" cy="4" r="3" fill="#0066ff"/>
    <text x="129" y="7" font-family="system-ui, sans-serif" font-size="10" font-weight="700" fill="#2563eb">CLOUD POS</text>

    <circle cx="218" cy="4" r="3" fill="#8b5cf6"/>
    <text x="227" y="7" font-family="system-ui, sans-serif" font-size="10" font-weight="700" fill="#7c3aed">MULTI-SUCURSAL</text>
  </g>
</svg>'''

    with open('app/static/logo.svg', 'w', encoding='utf-8') as f:
        f.write(logo_svg)
    print("✓ Created app/static/logo.svg")

    # 2. Square Icon / Emblem: InnovaFlow Icon (For Favicon, App Avatar, Touch Screen)
    icon_svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="100%" height="100%">
  <defs>
    <linearGradient id="icBg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0f172a"/>
      <stop offset="100%" stop-color="#1e1b4b"/>
    </linearGradient>
    <linearGradient id="icCyanBlue" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#00d2ff"/>
      <stop offset="100%" stop-color="#0066ff"/>
    </linearGradient>
    <linearGradient id="icBlueIndigo" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0066ff"/>
      <stop offset="100%" stop-color="#6366f1"/>
    </linearGradient>
    <linearGradient id="icPeruRed" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#dc2626"/>
      <stop offset="100%" stop-color="#ff4757"/>
    </linearGradient>
    <filter id="icGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="8" stdDeviation="10" flood-color="#0066ff" flood-opacity="0.35"/>
    </filter>
  </defs>

  <!-- Squircle Base -->
  <rect x="10" y="10" width="180" height="180" rx="50" fill="url(#icBg)" filter="url(#icGlow)"/>
  <rect x="10" y="10" width="180" height="180" rx="50" fill="none" stroke="#334155" stroke-width="2"/>

  <!-- Fluid "IF" Monogram Wave -->
  <!-- Lower loop (Cyan-Blue) -->
  <path d="M 50 134 C 50 152, 70 162, 98 162 C 134 162, 160 136, 160 102 C 160 76, 142 62, 122 62 C 98 62, 82 78, 82 102 C 82 118, 96 130, 114 130 C 122 130, 134 124, 140 114" 
        fill="none" stroke="url(#icCyanBlue)" stroke-width="16" stroke-linecap="round"/>

  <!-- Upper wave (Blue-Indigo) -->
  <path d="M 56 56 C 72 36, 110 32, 136 42 C 152 50, 162 66, 166 80" 
        fill="none" stroke="url(#icBlueIndigo)" stroke-width="16" stroke-linecap="round"/>

  <!-- Center Crossbar -->
  <path d="M 74 92 L 130 92" 
        fill="none" stroke="url(#icCyanBlue)" stroke-width="14" stroke-linecap="round"/>

  <!-- Peru Crimson Red Crown Accent -->
  <path d="M 62 66 C 62 48, 80 40, 102 40 L 146 40 C 158 40, 166 48, 166 58" 
        fill="none" stroke="url(#icPeruRed)" stroke-width="9" stroke-linecap="round"/>

  <!-- Glowing Nodes -->
  <circle cx="146" cy="40" r="6" fill="#ffffff" />
  <circle cx="140" cy="114" r="5" fill="#00d2ff" />
</svg>'''

    with open('app/static/logo_icon.svg', 'w', encoding='utf-8') as f:
        f.write(icon_svg)
    print("✓ Created app/static/logo_icon.svg")

    # 3. Favicon SVG
    with open('app/static/favicon.svg', 'w', encoding='utf-8') as f:
        f.write(icon_svg)
    print("✓ Created app/static/favicon.svg")

if __name__ == '__main__':
    create_svgs()
