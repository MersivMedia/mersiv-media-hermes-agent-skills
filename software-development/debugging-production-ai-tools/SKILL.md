---
name: Debugging Production AI Tools
description: Systematic approach to debug failing AI-powered web applications with multiple potential issues
tags: [debugging, ai-tools, production, frontend, backend, adsense]
---

# Debugging Production AI Tools

Systematic debugging methodology for AI-powered web applications that aren't working as expected. Based on real debugging session where user reported "results aren't showing" but multiple issues were discovered.

## When to Use

- User reports AI tool "not working" or "results not appearing"  
- Production AI applications showing unexpected behavior
- Need to systematically identify root causes in multi-layered applications
- Tools with frontend, backend, rate limiting, and monetization components

## Prerequisites

- Access to application code repository
- Browser developer tools knowledge
- Basic understanding of HTML/JavaScript and API integration

## Systematic Debugging Process

### Step 1: Identify the Correct Project

**Problem:** User says "fix the legal-translator-ai" but multiple similar projects exist
**Solution:** Search for correct project directory and verify with repo names

```bash
# Find projects with similar names
find ~/projects -name "*translator*" -type d
find ~/projects -name "*legal*" -type d

# Check package.json or git remotes to confirm correct project
cd ~/projects/[project-name] && git remote -v
```

### Step 2: Check Rate Limiting Implementation

**Common Issue:** Rate limit errors fall back to demo content instead of showing error messages

**Symptoms:**
- Users see demo content when rate limited
- No clear error messaging about daily limits

**Fix Pattern:**
```javascript
if (!response.ok) {
    if (response.status === 429) {
        const errorData = await response.json();
        showError(errorData.message || 'Rate limit exceeded...');
        return; // CRITICAL: Always return to prevent demo fallback
    }
    throw new Error('API error');
}
```

**Key Points:**
- Always `return` after handling 429 errors
- Call `hideError()` at start of requests to clear previous errors
- Add proper error display functions if missing

### Step 3: Check HTML Structure Integrity

**Common Issue:** Malformed HTML preventing DOM access

**Symptoms:**
- `document.getElementById()` returns `null`
- Console errors about element access
- Results not displaying despite successful API calls

**Debugging:**
```javascript
// Add temporary debugging
console.log('Element found:', document.getElementById('targetId'));
```

**Fix Pattern:**
Look for escaped quotes in HTML:
```html
<!-- BROKEN: -->
<div class=\"result-content\" id=\"simplifiedText\"></div>

<!-- FIXED: -->
<div class="result-content" id="simplifiedText"></div>
```

### Step 4: API Response Handling

**Common Issue:** OpenAI returning non-JSON formatted responses

**Symptoms:**
- JSON.parse() errors in browser console
- API calls succeed but results don't display

**Enhanced Error Handling:**
```javascript
try {
    const result = completion.choices[0].message.content;
    const parsedResult = JSON.parse(result);
    return res.status(200).json(parsedResult);
} catch (parseError) {
    console.error('JSON Parse Error:', parseError);
    console.error('Raw OpenAI Response:', result);
    
    // Fallback: Create structured response from raw text
    const fallbackResponse = {
        simplified: result || 'Unable to process request',
        keyPoints: ['Please try again with different text'],
        risks: ['API response formatting issue']
    };
    return res.status(200).json(fallbackResponse);
}
```

**System Prompt Enhancement:**
```javascript
content: `CRITICAL: You must respond with ONLY a valid JSON object. No additional text, explanations, or formatting outside the JSON.

Respond with exactly this JSON structure:
{
  "simplified": "...",
  "keyPoints": ["..."],
  "risks": ["..."]  
}

Respond with valid JSON only - no markdown formatting or additional text.`
```

### Step 5: AdSense Integration Issues

**Common Issue:** Complex AdSense setup not working

**Symptoms:**
- No ads showing despite proper publisher ID
- Console errors about AdSense initialization

**Debugging Approach:**
1. **Simplify First:** Remove complex ad units, use basic auto ads
2. **Add Visual Indicators:** Wrap ads in visible containers for debugging
3. **Check Prerequisites:** Account approval, site verification

**Simple Test Ad Pattern:**
```html
<div style="text-align: center; margin: 20px 0; padding: 20px; background: #f5f5f5; border: 1px solid #ddd;">
    <p style="margin-bottom: 15px; color: #666;">Advertisement</p>
    <ins class="adsbygoogle" 
         style="display:block; width: 728px; height: 90px;" 
         data-ad-client="ca-pub-XXXXXXXXXX"
         data-ad-format="auto"
         data-full-width-responsive="true"></ins>
</div>
```

**Individual Ad Initialization (Most Reliable):**
```html
<!-- Each ad gets its own initialization script -->
<ins class="adsbygoogle" 
     style="display:block" 
     data-ad-client="ca-pub-XXXXXXXXXXXXXXXX"
     data-ad-format="auto"
     data-full-width-responsive="true"></ins>
<script>
    (adsbygoogle = window.adsbygoogle || []).push({});
</script>
```

**Basic Global Initialization:**
```javascript
window.addEventListener('load', function() {
    try {
        (adsbygoogle = window.adsbygoogle || []).push({});
    } catch (e) {
        console.log('AdSense error:', e);
    }
});
```

**Strategic Ad Placement Locations:**
1. **Top Banner** - First thing users see in results
2. **Mid-Content** - Between content sections (high engagement)
3. **In-Feed** - Uses fluid layout for natural integration  
4. **Bottom** - After main content before academic notes
5. **Mobile-specific** - Separate ads for mobile users
6. **Sticky Sidebar** - Desktop-only vertical ads

**Complete AdSense Integration Pattern:**
```html
<!-- Head Section -->
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-XXXXXXXXXX" crossorigin="anonymous"></script>

<!-- Multiple Strategic Ad Placements -->
<div class="ad-slot ad-slot-leaderboard">
    <div class="ad-placeholder">Advertisement - Top Banner</div>
    <ins class="adsbygoogle" 
         style="display:block" 
         data-ad-client="ca-pub-XXXXXXXXXX"
         data-ad-format="auto"
         data-full-width-responsive="true"></ins>
    <script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
</div>
```

### Step 6: Vercel Deployment Configuration Issues

**Common Issue:** Invalid runtime configuration causing build failures

**Symptoms:**
- Build fails with "Function Runtimes must have a valid version" error
- Error mentions something like "now-php@1. 0.0" format
- Deployment stops at "Running vercel build" stage
- Deployment keeps using old commit hash despite new pushes

**Root Cause Analysis:**
```bash
# Check vercel.json configuration
cat vercel.json

# Check if latest commits are being deployed
git log --oneline -5
```

**Common Problems:**
1. **Invalid runtime syntax:** `@vercel/node` without version
2. **Deprecated runtime names:** Old format references
3. **Malformed JSON:** Copy/paste errors
4. **Corrupted API files:** Syntax errors preventing compilation
5. **Deployment cache:** Vercel using stale commits

**Fix Pattern:**
```json
// BROKEN:
{
  "functions": {
    "api/simplify.ts": {
      "runtime": "@vercel/node"  // Missing version
    }
  }
}

// FIXED:
{
  "functions": {
    "api/simplify.ts": {
      "runtime": "nodejs18.x"  // Proper runtime specification
    }
  }
}

// BEST (let Vercel auto-detect):
{}
```

### Step 6.1: Check for Corrupted API Files

**Critical Issue:** Syntax errors in TypeScript API files can cause deployment failures

**Symptoms:**
- TypeScript compilation errors during build
- "Function Runtimes" error that persists after fixing vercel.json
- API files with truncated or corrupted lines

**Detection:**
```bash
# Look for corrupted environment variable access
grep -n "proces.*KEY" api/*.ts

# Check for incomplete lines ending with ...
grep -n "\.\.\." api/*.ts
```

**Common Corruption Patterns:**
```typescript
// CORRUPTED:
const openaiApiKey=proces...KEY;

// FIXED:
const openaiApiKey = process.env.OPENAI_API_KEY;
```

**Fix Approach:**
1. Read entire API file to identify corruption
2. If patch fails, rewrite entire file with clean syntax
3. Verify all imports and variable declarations are complete

**Common Runtime Options:**
- `nodejs18.x` - Node.js 18 (recommended for most projects)
- `nodejs16.x` - Node.js 16 (legacy projects)
- `nodejs20.x` - Node.js 20 (newer projects)

**Verification Steps:**
1. Fix corrupted API files first (highest priority)
2. Update/simplify `vercel.json` with correct runtime or empty object
3. Force fresh deployment with small change
4. Monitor deployment logs for successful build
5. Test API endpoints after deployment

**Force Fresh Deployment:**
```bash
# Make small change to trigger new build
echo "// Trigger deployment" >> src/App.tsx
git add . && git commit -m "Trigger fresh deployment" && git push
```

## Debugging Tools & Techniques

### Console Logging Strategy
```javascript
// API Response Debugging
console.log('API Response data:', data);
console.log('displayResults called with:', data);
console.log('Found elements:', { element1, element2 });

// Remove after debugging
```

### HTML Structure Verification
```javascript
// Check if elements exist
const elements = {
    simplified: document.getElementById('simplifiedText'),
    results: document.getElementById('resultsSection')
};
console.log('DOM Elements:', elements);
```

### Error Handling Best Practices
```javascript
// Clear previous errors at start of functions
hideError();

// Specific error messages for different failure modes
if (response.status === 429) {
    showError('Daily limit reached. Try tomorrow!');
    return;
} else if (response.status === 400) {
    showError('Invalid input. Please check your text.');
    return;
}
```

## Common Root Causes & Solutions

### 1. Rate Limiting UX Issues
**Problem:** Users confused by demo content when rate limited
**Solution:** Proper error messages, prevent demo fallback on rate limits

### 2. Malformed HTML
**Problem:** Copy/paste or template errors creating invalid HTML
**Solution:** Search for escaped quotes, validate HTML structure

### 3. API Response Format Mismatch
**Problem:** OpenAI returning text instead of JSON
**Solution:** Enhanced system prompts + fallback parsing

### 4. AdSense Integration Complexity  
**Problem:** Complex ad unit setup failing
**Solution:** Start simple with auto ads, verify account status first

### 5. AdSense Publisher ID Configuration
**Problem:** Using placeholder IDs or wrong publisher ID format
**Solution:** Replace ALL instances with real publisher ID (`ca-pub-1234567890123456`)

**Fix Pattern:**
```bash
# Search and replace all placeholder publisher IDs
grep -r "ca-pub-XXXXXXXXXX" . --include="*.html"
# Replace with real ID: ca-pub-XXXXXXXXXXXXXXXX
```

### 6. Vercel Runtime Configuration Errors
**Problem:** Invalid `vercel.json` runtime specification preventing deployment
**Solution:** Use proper Node.js runtime version format (e.g., `nodejs18.x`)

### 7. Individual vs Global AdSense Initialization
**Problem:** Global initialization not working reliably for dynamically loaded content
**Solution:** Use individual `<script>` blocks after each ad unit

**Individual Method (More Reliable):**
- Each ad gets its own `(adsbygoogle = window.adsbygoogle || []).push({});`
- Works better with dynamic content and results sections
- Easier to debug specific ad failures

**Global Method (Simpler but Less Reliable):**
- Single initialization in `window.addEventListener('load')`  
- May not catch dynamically loaded ads in results sections
- Good for static page content only

## Quality Checklist

Before declaring "fixed":
- [ ] Rate limiting shows proper error messages (not demo content)
- [ ] All DOM elements properly accessible (no escaped quotes)
- [ ] API responses parsed correctly with fallback handling
- [ ] AdSense integration simplified and tested
- [ ] Console free of JavaScript errors
- [ ] User can complete full workflow successfully

## Post-Fix Cleanup

1. **Remove debugging logs** from production code
2. **Commit incremental fixes** with clear messages
3. **Test edge cases** (rate limits, malformed input, network failures)
4. **Update memory** with lessons learned for similar tools

## Success Pattern

This methodology successfully resolved a complex "not working" issue that actually had 4 distinct root causes:
- ✅ Fixed rate limiting UX (8 AI tools)
- ✅ Fixed malformed HTML breaking DOM access  
- ✅ Added JSON parsing error handling
- ✅ Simplified AdSense integration for debugging
- ✅ Complete AdSense integration with 7 strategic ad placements

**Session Example:** Legal translator "not working" revealed:
1. **Escaped quotes** in HTML breaking DOM access (`class=\"` → `class="`)
2. **Missing API key** in Vercel environment variables
3. **Incomplete AdSense setup** - moved from test ad to full integration
4. **UI improvements** - results container with professional styling

**AdSense Integration Lessons:**
- Start with **one test ad** to verify account/publisher ID works
- Use **individual script blocks** per ad for dynamic content
- **Strategic placement** matters more than ad quantity
- **Mobile/desktop specific ads** improve performance
- **Visual indicators** during debugging (ad placeholder divs)

**Key Insight:** "Results not showing" is rarely a single issue - systematic debugging reveals multiple layered problems that each need specific solutions. AdSense integration should be done incrementally (test → strategic placement → optimization).