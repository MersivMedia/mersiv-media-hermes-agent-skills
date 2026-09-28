---
name: Cookie Consent Integration
description: Add GDPR/CCPA compliant cookie consent banners to AI-powered websites with proper AdSense integration
tags: [gdpr, ccpa, cookies, adsense, monetization, web-development]
complexity: intermediate
---

# Cookie Consent Integration

Add professional cookie consent banners to websites for GDPR/CCPA compliance with Google AdSense integration.

## When to Use

- AI-powered websites with AdSense monetization
- Need GDPR/CCPA compliance for EU/California users
- Want to maximize ad revenue while respecting user privacy
- Existing sites missing cookie consent popups

## Implementation Approaches

### HTML/Vanilla JS Websites

1. **Add Cookie Banner HTML**
```html
<!-- Cookie Consent Banner -->
<div id="cookieConsent" style="display: none; position: fixed; bottom: 0; left: 0; right: 0; background: #2d3748; color: white; padding: 15px; z-index: 10000; border-top: 3px solid #3b82f6;">
    <div style="max-width: 1200px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 15px;">
        <div style="flex: 1; min-width: 300px;">
            <p style="margin: 0; font-size: 14px;">
                🍪 We use cookies to enhance your experience and serve personalized ads. 
                <a href="privacy-policy.html" style="color: #93c5fd; text-decoration: underline;">Learn more about our privacy practices</a>
            </p>
        </div>
        <div style="display: flex; gap: 10px; flex-wrap: wrap;">
            <button onclick="acceptCookies()" style="background: #10b981; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 14px;">Accept All</button>
            <button onclick="rejectCookies()" style="background: transparent; color: white; border: 1px solid #6b7280; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 14px;">Reject All</button>
            <button onclick="hideCookieBanner()" style="background: transparent; color: #9ca3af; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 14px;">✕</button>
        </div>
    </div>
</div>
```

2. **Add Consent Management JavaScript**
```javascript
// Cookie banner functions
function showCookieBanner() {
    const banner = document.getElementById('cookieConsent');
    if (banner && !localStorage.getItem('cookie_choice_made')) {
        banner.style.display = 'block';
    }
}

function hideCookieBanner() {
    const banner = document.getElementById('cookieConsent');
    if (banner) {
        banner.style.display = 'none';
    }
}

function acceptCookies() {
    updateConsent('granted');
    localStorage.setItem('cookie_choice_made', 'true');
    hideCookieBanner();
}

function rejectCookies() {
    updateConsent('denied');
    localStorage.setItem('cookie_choice_made', 'true');
    hideCookieBanner();
}

function updateConsent(consentStatus) {
    gtag('consent', 'update', {
        'ad_storage': consentStatus,
        'ad_user_data': consentStatus, 
        'ad_personalization': consentStatus,
        'analytics_storage': consentStatus
    });
    
    localStorage.setItem('consent_granted', consentStatus === 'granted' ? 'true' : 'false');
    
    if (consentStatus === 'granted') {
        setTimeout(function() {
            if (window.adsbygoogle && window.adsbygoogle.loaded) {
                window.adsbygoogle.push({});
            }
        }, 100);
    }
}

// Show banner on page load
window.addEventListener('load', function() {
    setTimeout(function() {
        if (!localStorage.getItem('cookie_choice_made')) {
            showCookieBanner();
        }
    }, 2000); // Show after 2 seconds
});
```

### React/TypeScript Applications

1. **Add to Main Component (App.tsx)**
```typescript
{/* Cookie Consent Banner */}
<div 
  id="cookieConsent" 
  style={{
    display: 'none',
    position: 'fixed',
    bottom: 0,
    left: 0,
    right: 0,
    background: '#2d3748',
    color: 'white',
    padding: '15px',
    zIndex: 10000,
    borderTop: '3px solid #3b82f6'
  }}
>
  <div style={{
    maxWidth: '1200px',
    margin: '0 auto',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    flexWrap: 'wrap',
    gap: '15px'
  }}>
    <div style={{ flex: 1, minWidth: '300px' }}>
      <p style={{ margin: 0, fontSize: '14px' }}>
        🍪 We use cookies to enhance your experience and serve personalized ads. 
        <a href="./privacy-policy.html" style={{ color: '#93c5fd', textDecoration: 'underline' }}>
          Learn more about our privacy practices
        </a>
      </p>
    </div>
    <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
      <button onClick={() => (window as any).acceptCookies?.()} /* ... */>Accept All</button>
      <button onClick={() => (window as any).rejectCookies?.()} /* ... */>Reject All</button>
      <button onClick={() => (window as any).hideCookieBanner?.()} /* ... */>✕</button>
    </div>
  </div>
</div>
```

2. **Add Consent Functions to index.html**
- Same JavaScript functions as vanilla implementation
- Added in `<script>` tags in public/index.html

## Design Principles

### Visual Design
- **Dark theme**: Professional appearance (#2d3748 background)
- **High contrast**: White text on dark background for readability
- **Blue accent**: #3b82f6 top border for visual appeal
- **Fixed bottom**: Non-intrusive positioning
- **High z-index**: 10000 ensures proper layering

### User Experience
- **Delayed appearance**: 2 second delay prevents immediate interruption
- **Clear choices**: Accept All, Reject All, and dismiss options
- **Persistent choice**: localStorage prevents re-showing
- **Privacy link**: Direct link to privacy policy
- **Mobile responsive**: Flexbox layout adapts to all screens

### Technical Integration
- **Default consent denial**: Privacy-first approach
- **Google CMP compatible**: Works with Funding Choices
- **Ad refresh**: Reloads ads when consent granted
- **Analytics integration**: Updates Google Analytics consent
- **Local storage**: Remembers user preference

## Required AdSense Setup

1. **Publisher ID**: Replace with actual AdSense publisher ID
2. **Google CMP**: Enable Funding Choices in AdSense dashboard
3. **Consent Mode**: Ensure gtag consent management is active
4. **Privacy Policy**: Must have accessible privacy policy page

## Common Issues

### Banner Not Showing
- Check `localStorage.getItem('cookie_choice_made')` - clear if testing
- Verify 2-second delay timing
- Ensure element ID matches JavaScript selectors

### Consent Not Updating
- Verify gtag is loaded before consent functions
- Check AdSense integration in head section
- Confirm consent storage in localStorage

### Ad Loading Issues
- Check ad refresh timing (100ms delay)
- Verify AdSense publisher ID is correct
- Ensure consent status matches ad requirements

## Testing Checklist

✅ Banner appears after 2 seconds on first visit
✅ Accept/Reject/Close buttons all work
✅ Choice persists across page refreshes
✅ Privacy policy link works
✅ Mobile responsive design
✅ Ads load properly after consent
✅ localStorage stores consent status
✅ No console errors

## Compliance Notes

- **GDPR**: Explicit consent required for EU users
- **CCPA**: Opt-out mechanism for California users  
- **Default denial**: Must not set cookies without consent
- **Clear language**: Simple explanation of cookie usage
- **Privacy policy**: Must be accessible and comprehensive