---
name: AI Tool Conversion from Legal Template
description: Convert legal document simplifier template to other AI-powered tools with proper API integration, data structure alignment, and professional features
tags: ["ai-tools", "template-conversion", "openai-api", "web-development"]
version: 1.0
---

# AI Tool Conversion from Legal Template

## Overview
Convert legal document simplifier template to other AI-powered tools (essay writer, resume builder, etc.). This skill covers the complete conversion process including API fixes, content transformation, and functionality alignment.

## When to Use
- Converting legal template to any other AI tool domain
- Fixing OpenAI API integration issues in cloned tools  
- Ensuring proper data flow between APIs and frontend
- Adding professional features like rate limiting and citations

## Critical Conversion Steps

### 1. OpenAI API Migration (v3→v4)
**Common Issues:**
- `const { OpenAI } = require('openai')` → `const OpenAI = require('openai')`
- `createChatCompletion()` → `chat.completions.create()`
- `completion.data.choices[0]` → `completion.choices[0]`
- Package.json needs OpenAI v4.0.0+ (not v3.x)

### 2. Data Structure Mismatch (Critical!)
**Problem:** Frontend expects legal analysis structure but new tool returns different data
- Legal analysis: `{simplified, keyPoints, risks}`
- Essay generation: `{essay, wordCount, readingTime, structure}`

**Solution:** 
- Update HTML sections to match new data structure
- Create new display functions (`displayEssayResults` vs `displayResults`)
- Update demo data in both API and frontend JavaScript

### 3. System Prompt Transformation
**Update prompts for new domain:**
- Change from legal expert to domain expert (essay writer, etc.)
- Update response format requirements
- Add domain-specific requirements (citations for essays, etc.)
- Adjust max_tokens for longer responses if needed
- **Business Plans**: Use MBA-level expertise, include TAM/SAM/SOM analysis, 3-5 year projections
- **Resume Builder**: Focus on ATS optimization, metrics, action verbs, achievement-based content

### 4. Content Sections to Update
**All 10 sections need domain transformation:**
1. Meta tags & SEO (title, description, keywords)
2. Structured data (WebApplication schema, FAQPage)
3. Hero section (headline, subtitle, badges)
4. Features section (6 tool-specific items)
5. FAQ section (4-5 domain-specific Q&As)
6. How-it-works section (3-step workflow)
7. Form labels & placeholders (domain examples)
8. Error messages & validation text
9. Loading messages ("Analyzing legal document" → domain-appropriate)
10. API endpoints & system prompts

### 5. Rate Limiting Implementation
**Add to ALL tools (3 requests/day/IP):**
```javascript
// In API handler
const clientIP = req.headers['x-forwarded-for'] || req.connection.remoteAddress || 'unknown';
const today = new Date().toDateString();
const rateLimitKey = `${clientIP}_${today}`;

if (!global.rateLimitStore) global.rateLimitStore = {};
if (!global.rateLimitStore[rateLimitKey]) global.rateLimitStore[rateLimitKey] = 0;

if (global.rateLimitStore[rateLimitKey] >= 3) {
    return res.status(429).json({ 
        error: 'Rate limit exceeded',
        message: 'You have reached your daily limit of 3 [tool action]. Please try again tomorrow!'
    });
}
global.rateLimitStore[rateLimitKey]++;
```

## Specific Learnings from Essay Writer Conversion

### API Response Handling
- Check API response structure carefully
- Frontend display functions must match API response format
- Demo data in multiple places needs updating (API fallback + frontend fallback)

### Professional Features
- Citations: Update system prompts to require in-text citations and References section
- Word count enforcement: Explicitly mention in prompts
- Copy functionality: Compact button design with just icon
- Error handling: Graceful rate limit messaging

### Common Gotchas
- Loading messages often still say "Analyzing legal document"
- FAQ sections may contain legal-specific questions
- Demo responses show legal content instead of domain content
- Section headers may be legal-focused ("Potential Concerns" vs domain-appropriate)
- **Open Graph tags**: Often still reference "Legal Document Simplifier" 
- **Structured data**: ApplicationCategory may still be "LegalApplication"
- **FeatureList**: Individual features need complete transformation, not just bulk replacement
- **HowTo steps**: Step names and descriptions need domain-specific updates

## Verification Checklist
- [ ] OpenAI API responds correctly (not demo mode)
- [ ] Generated content displays properly (not analysis format)
- [ ] All loading/error messages are domain-appropriate
- [ ] FAQ sections are fully converted
- [ ] Demo content shows domain examples
- [ ] **Rate limiting shows error messages (NOT demo fallback)**
- [ ] Copy functionality works
- [ ] Citations/references included if applicable
- [ ] Open Graph tags are domain-specific (not legal references)
- [ ] Structured data applicationCategory updated
- [ ] FeatureList items are domain-appropriate
- [ ] HowTo structured data steps are tool-specific
- [ ] Complete package.json with correct dependencies
- [ ] Professional README with revenue projections

## Critical Rate Limiting Bug (FIXED)
**Problem:** Rate-limited users saw demo content instead of error messages, causing confusion about whether the tool was working.

**Solution:** 
1. Add explicit 429 handling: `if (response.status === 429) { showError(errorData.message); return; }`
2. Remove/comment demo fallback in catch blocks for rate limit scenarios
3. Always `return` after rate limit errors to prevent demo execution

**Impact:** Applied to 8 AI tools successfully - users now get clear "daily limit reached" messages instead of confusing demo content.

## Files to Update
- `package.json` (OpenAI version, tool-specific metadata)
- `api/generate-[tool].js` (API logic, system prompts, rate limiting)
- `api/simplify.js` or equivalent (if analysis feature exists)
- `index.html` (content, FAQ, display functions, demo data, Open Graph, structured data)
- `vercel.json` (deployment configuration)
- `README.md` (professional documentation with revenue estimates)

## Success Pattern
Template → Content Update → API Fix → Data Structure Alignment → Professional Features → Testing