---
name: OpenAI API v3 to v4 Migration for Template-Based AI Tools
description: Systematic approach to migrate OpenAI SDK from v3 to v4 and fix API integration issues in template-based AI tools
category: software-development
tags: [openai, api, migration, debugging, ai-tools]
---

# OpenAI API v3 to v4 Migration for Template-Based AI Tools

## When to Use This Skill

- Converting legal document tools to other AI tool types
- Fixing "OpenAI is not a constructor" errors
- API calls returning success but no results displaying
- Template-based tools cloned from legal simplifier base
- Any OpenAI SDK v3 to v4 migration

## Common Symptoms

- `TypeError: OpenAI is not a constructor`
- API calls succeed but frontend shows no results
- Data structure mismatches between API response and display functions
- Loading messages still reference original tool type (e.g., "analyzing legal document")
- Demo data doesn't match real API response format

## 7-Step Migration Process

### 1. Update Package.json
```json
{
  "dependencies": {
    "openai": "^4.0.0"  // NOT "^3.3.0"
  }
}
```

### 2. Fix Import Syntax
```javascript
// WRONG (v3 style)
const { OpenAI } = require('openai');

// CORRECT (v4 style)  
const OpenAI = require('openai');
```

### 3. Update API Method Calls
```javascript
// WRONG (v3 method)
const completion = await openai.createChatCompletion({...});

// CORRECT (v4 method)
const completion = await openai.chat.completions.create({...});
```

### 4. Fix Response Parsing
```javascript
// WRONG (v3 response structure)
const result = completion.data.choices[0].message.content;

// CORRECT (v4 response structure)
const result = completion.choices[0].message.content;
```

### 5. Check API Key Validation Logic
```javascript
// Make sure you're checking the client, not just the env var
if (!openai) {  // CORRECT
    // Return demo response
}

// vs

if (!process.env.OPENAI_API_KEY) {  // Can be problematic
    // This might not catch all cases
}
```

### 6. Update System Prompts
Replace domain-specific language in system prompts:
```javascript
// Update from legal focus to target domain
content: `You are an expert essay and academic writing analyst...`
// Instead of: `You are a legal document simplification expert...`
```

### 7. Fix Data Structure Mismatches

**Common Issue:** Frontend expects analysis data but API returns generation data

**Legal Tool Structure:**
- `simplified` (analysis text)
- `keyPoints` (array of points)
- `risks` (array of concerns)

**Essay Tool Structure:**
- `essay` (generated content)
- `wordCount` (number)
- `readingTime` (string)
- `structure` (array of elements)

**Solution:** Create matching display functions and update demo data.

## Display Function Pattern

```javascript
// Create tool-specific display function
function displayEssayResults(data) {
    // Handle the actual API response structure
    const essayContentDiv = document.getElementById('essayContent');
    // Convert markdown to HTML, show stats, etc.
}

// Update demo data to match API structure
const demoData = {
    essay: "...",           // Not "simplified"
    wordCount: 287,         // Not "keyPoints" array
    readingTime: "2-3 min", // Not "risks" array
    structure: [...]
};
```

## Content Updates Beyond API

### Update Loading Messages
```html
<!-- FROM -->
<p>Analyzing legal document...</p>

<!-- TO -->
<p>Researching and writing your essay...</p>
```

### Update FAQ Content
Replace domain-specific FAQ items with tool-appropriate questions.

### Update Section Headers
```html
<!-- FROM -->
<h3>📝 Simplified Explanation</h3>
<h3>✅ Key Points</h3>
<h3>⚠️ Potential Concerns</h3>

<!-- TO -->
<h3>📝 Your Generated Essay</h3>
<h3>📊 Essay Statistics</h3>
<h3>🏗️ Essay Structure</h3>
```

## Testing Checklist

- [ ] API calls work with real OpenAI key
- [ ] Demo mode works without API key  
- [ ] Results display correctly
- [ ] Loading messages are tool-appropriate
- [ ] FAQ content matches tool purpose
- [ ] Section headers match functionality
- [ ] Copy functionality works (if applicable)

## Pitfalls to Avoid

1. **Partial Updates:** Don't just fix the API - update ALL content references
2. **Mixed Structures:** Ensure demo data exactly matches real API response
3. **Import Confusion:** v4 uses direct require, not destructured import
4. **Response Parsing:** Remember to remove `.data` from response access
5. **Display Mismatches:** Create new display functions instead of forcing old ones

## Success Indicators

- No console errors about OpenAI constructor
- Real API responses display properly
- Demo mode shows appropriate content for tool type
- All text references match the tool's actual purpose
- User can successfully generate and copy results

## Verified Pattern

This approach successfully converted AI Essay Writer from legal document analysis to essay generation with full functionality. Apply same pattern to all 12 tools in the portfolio.