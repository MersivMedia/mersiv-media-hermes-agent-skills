---
name: "AI Tool Sticky Ads Layout"
description: "Advanced sticky ad layout for AI tools - vertical sidebars plus smart bottom banner"
category: "ad-monetization"
---

# AI Tool Sticky Ads Layout

Advanced sticky advertisement layout that maximizes revenue while maintaining excellent UX through strategic positioning and smart footer detection.

## When to Use

- AI tools with high traffic potential
- Revenue optimization priority
- Desktop-first user base (sidebar ads hidden on mobile)
- Need for maximum ad inventory without UX disruption

## Ad Placement Strategy (9 Locations)

### Fixed Sticky Ads
```css
.sidebar-left {
    position: fixed;
    left: 10px;
    top: 50%;
    transform: translateY(-50%);
    width: 160px;
    z-index: 900;
}

.sidebar-right {
    position: fixed;
    right: 10px;
    top: 50%;
    transform: translateY(-50%);
    width: 160px;
    z-index: 900;
}
```

### Smart Bottom Banner
```css
.ad-slot-sticky {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 1000;
    background: var(--card);
    border-top: 1px solid var(--border);
    padding: 0.5rem;
    transition: transform 0.3s ease;
}

.ad-slot-sticky.hidden {
    transform: translateY(100%);
}
```

## Footer Detection Script

```javascript
function handleStickyAdVisibility() {
    const footer = document.querySelector('footer');
    const stickyAd = document.querySelector('.ad-slot-sticky');
    
    if (!footer || !stickyAd) return;

    const footerRect = footer.getBoundingClientRect();
    const windowHeight = window.innerHeight;
    
    // Hide sticky ad when footer is visible (within 100px of viewport)
    if (footerRect.top <= windowHeight + 100) {
        stickyAd.classList.add('hidden');
    } else {
        stickyAd.classList.remove('hidden');
    }
}

// Add scroll listener for sticky ad
document.addEventListener('DOMContentLoaded', function() {
    window.addEventListener('scroll', handleStickyAdVisibility);
    handleStickyAdVisibility(); // Check initial state
});
```

## Complete Ad Layout Structure

1. **Top Banner** (728x90) - Above fold visibility
2. **Left Sticky** (160x600) - Always visible desktop
3. **Right Sticky** (160x600) - Always visible desktop  
4. **Mid Content Large** (728x250) - Between main sections
5. **Features Large** (728x250) - After features section
6. **FAQ Mid Banner** (728x90) - Between FAQ items
7. **FAQ Bottom Large** (728x250) - End of FAQ
8. **Sticky Bottom** (728x90) - Smart footer detection
9. **Auto Ads** - Google's additional placements

## Responsive Behavior

```css
@media (max-width: 1200px) {
    .sidebar-left, .sidebar-right {
        display: none;
    }
    
    .main-content {
        max-width: 1000px;
    }
}

@media (max-width: 768px) {
    .sidebar-left, .sidebar-right {
        display: none;
    }
    
    .main-content {
        max-width: 100%;
    }
}
```

## Layout Optimization

- Main content max-width: 1000px for readability
- Sidebars hidden below 1200px screen width
- 100px buffer zone for smooth footer transitions
- Smooth CSS transitions for professional feel

## Revenue Benefits

- Maximum ad inventory (9 placements) without UX disruption
- High viewability rates for sticky positioned ads
- Smart footer detection maintains user trust
- Responsive design preserves mobile experience
- Professional implementation builds credibility

## Implementation Notes

- Use unique ad slot IDs for each placement
- Test scroll behavior across different content lengths
- Monitor viewability metrics for optimization
- Consider A/B testing placement positions
- Ensure GDPR compliance with cookie consent

## Pitfalls to Avoid

- Don't block main content with ads
- Test on various screen sizes thoroughly  
- Ensure footer remains accessible
- Monitor Core Web Vitals impact
- Balance revenue vs user experience