---
name: Professional Legal Page Separation
description: Create comprehensive, compliant Privacy Policy and Terms of Service pages separated from main application content with proper Google CMP integration
tags: ["legal-compliance", "privacy-policy", "terms-of-service", "gdpr", "ccpa", "google-cmp", "professional-websites"]
version: 1.0
---

# Professional Legal Page Separation

## Overview
Transform inline legal content into professional, dedicated legal pages (Privacy Policy & Terms of Service) with full GDPR/CCPA compliance and Google Consent Management Platform integration. This skill covers the complete separation workflow including content migration, navigation updates, and compliance features.

## When to Use
- User requests Google CMP integration for legal compliance
- Moving legal content off main pages for better UX
- Creating dedicated Privacy Policy and Terms of Service pages
- Need professional legal compliance for ad-monetized websites
- Converting basic cookie notices to comprehensive legal frameworks

## Critical Implementation Pattern

### 1. Google CMP Integration (Foundation)
**Must be implemented FIRST before page separation:**
```html
<!-- Google Consent Management Platform -->
<script async src="https://fundingchoicesmessages.google.com/i/pub-XXXXXXXXXX?ers=1" nonce="cmp-script"></script>
<script nonce="cmp-script">
    (function() {
        function signalGooglefcPresent() {
            if (!window.frames['googlefcPresent']) {
                if (document.body) {
                    const iframe = document.createElement('iframe');
                    iframe.style = 'width: 0; height: 0; border: none; z-index: -1000; left: -1000px; top: -1000px;';
                    iframe.style.display = 'none';
                    iframe.name = 'googlefcPresent';
                    document.body.appendChild(iframe);
                } else {
                    setTimeout(signalGooglefcPresent, 0);
                }
            }
        }
        signalGooglefcPresent();
    })();
</script>

<!-- Google tag (gtag.js) with Consent Management -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
<script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    
    // Default consent - deny all
    gtag('consent', 'default', {
        'ad_storage': 'denied',
        'ad_user_data': 'denied',
        'ad_personalization': 'denied',
        'analytics_storage': 'denied'
    });
    
    gtag('js', new Date());
    gtag('config', 'G-XXXXXXXXXX');
</script>
```

### 2. Privacy Policy Page Creation
**Create comprehensive `privacy-policy.html`:**

**Key Sections (Required for Compliance):**
1. **Interactive Cookie Management** - Allow users to update consent
2. **Information Collection** - What data is collected and how
3. **Cookie Categories** - Essential, Analytics, Advertising with explanations  
4. **Third-Party Services** - Google AdSense, OpenAI, analytics providers
5. **Data Protection** - GDPR rights (access, rectification, erasure, portability, objection)
6. **CCPA Compliance** - California consumer rights
7. **Data Security** - HTTPS, secure servers, access controls
8. **Data Retention** - How long different data types are kept
9. **International Transfers** - Cross-border data processing
10. **Contact Information** - How users can reach you

**Critical Features:**
- **Live consent status display** with real-time updates
- **Working consent controls** that actually update cookies
- **Mobile responsive design** matching main site
- **Professional styling** with clear hierarchy
- **Cross-linking** to main site and terms of service

### 3. Terms of Service Page Creation  
**Create comprehensive `terms-of-service.html`:**

**Key Sections (Required for Legal Protection):**
1. **Service Description** - What the tool provides
2. **Acceptable Use Policy** - Permitted vs prohibited uses
3. **Academic Integrity Notice** - Clear guidance for students
4. **Rate Limits** - Daily usage restrictions  
5. **Content Ownership** - AI-generated vs service IP
6. **Disclaimers** - Service availability, content accuracy
7. **Liability Limitations** - Standard legal protections
8. **Termination Conditions** - When access can be suspended
9. **Third-Party Services** - OpenAI, Google dependencies
10. **Governing Law** - Legal jurisdiction

**Academic Integrity Section (Critical for AI Tools):**
```html
<div class="warning-box">
    <strong>Academic Responsibility:</strong> If you're a student, you must comply with your institution's policies regarding AI assistance and academic integrity. Always disclose the use of AI tools when required.
</div>
```

### 4. Main Page Content Migration
**Remove inline legal content systematically:**

1. **Navigation Updates:**
```html
<!-- OLD -->
<a href="#privacy">Privacy & Cookies</a>

<!-- NEW -->
<!-- Remove from main navigation -->
```

2. **Section Removal:**
```html
<!-- Remove entire privacy section -->
<!-- OLD: <section id="privacy" class="content-section">...</section> -->
<!-- NEW: Empty space or additional content -->
```

3. **Footer Link Updates:**
```html
<!-- OLD -->
<a href="#privacy">Privacy Policy</a>
<a href="#terms">Terms of Service</a>

<!-- NEW -->
<a href="privacy-policy.html">Privacy Policy</a>
<a href="terms-of-service.html">Terms of Service</a>
```

4. **Cookie Banner Link Updates:**
```html
<!-- OLD -->
<a href="#privacy" style="color: #93c5fd;">Learn more</a>

<!-- NEW -->
<a href="privacy-policy.html" style="color: #93c5fd;">Learn more</a>
```

### 5. Professional Styling Pattern
**Consistent design across both pages:**
```css
body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.container {
    max-width: 800px;
    margin: 0 auto;
    padding: 20px;
    background: white;
    border-radius: 10px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.2);
}

.highlight-box {
    background: #f8fafc;
    border-left: 4px solid #3b82f6;
    padding: 20px;
    margin: 20px 0;
}

.warning-box {
    background: #fef2f2;
    border-left: 4px solid #ef4444;
    padding: 20px;
    margin: 20px 0;
}
```

## User Experience Benefits

### Before: Problems with Inline Legal Content
- **Main page bloated** with legal text
- **Poor mobile experience** with long scrolling
- **Cluttered navigation** mixing features with legal
- **Hard to find** specific legal information
- **SEO dilution** mixing app content with legal text

### After: Professional Separation
- **Clean main page** focused on tool functionality
- **Dedicated legal URLs** for easy reference
- **Professional appearance** building user trust
- **Better mobile UX** with focused content
- **SEO benefits** from specialized page targeting

## Compliance Benefits

### GDPR Compliance (EU Users)
- **Explicit consent collection** via Google CMP
- **Clear opt-out mechanisms** in privacy policy
- **Complete data rights explanation** (access, rectification, erasure, portability)
- **Legitimate interests disclosed** with objection rights

### CCPA Compliance (California Users)  
- **Consumer rights disclosure** (know, delete, opt-out, equal service)
- **Data sharing transparency** with third parties
- **Clear contact mechanisms** for exercising rights

### Google AdSense Requirements
- **Official CMP integration** using Google Funding Choices
- **Proper consent management** for personalized ads
- **Third-party disclosure** linking to Google's privacy policy

## Technical Implementation Steps

1. **Create privacy-policy.html** with comprehensive content
2. **Create terms-of-service.html** with legal protections
3. **Remove privacy section** from main page
4. **Update all navigation links** to point to new pages
5. **Update cookie banner links** to new privacy policy
6. **Add consent management** to privacy policy page
7. **Test all links** and consent functionality
8. **Deploy and verify** pages are accessible

## Verification Checklist
- [ ] Google CMP integration working (consent updates properly)
- [ ] Privacy policy loads and displays consent status
- [ ] Terms of service accessible from all required locations
- [ ] Main page no longer contains bulky legal content
- [ ] All navigation links point to correct pages
- [ ] Cookie banner links to new privacy policy
- [ ] Mobile responsive design on both legal pages
- [ ] Cross-links between legal pages work
- [ ] Professional styling consistent with main site
- [ ] Legal content comprehensive for compliance needs

## Success Pattern
**Google CMP → Privacy Policy Creation → Terms Creation → Main Page Cleanup → Link Updates → Testing → Deployment**

This creates a professional, compliant legal framework that improves both user experience and legal protection.

## Common Pitfalls to Avoid
- **Don't create basic legal pages** - Users expect comprehensive compliance
- **Don't skip consent management** - Required for ad monetization
- **Don't leave broken links** - Update all references to legal content
- **Don't ignore mobile UX** - Legal pages must be responsive
- **Don't copy generic templates** - Customize for your specific tool and data practices