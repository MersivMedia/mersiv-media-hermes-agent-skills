---
name: AI Tool Deployment Troubleshooting & Recovery
description: Diagnose and fix failing Vercel builds and AI tool deploys.
tags: [vercel, deployment, debugging, ai-tools, troubleshooting, build-errors, react, static-html, architecture]
complexity: intermediate
time_estimate: 30-60 minutes
last_updated: 2026-09-27
---

# AI Tool Deployment Troubleshooting & Recovery

## When to Use This Skill

- Vercel deployment failures with cryptic error messages ("Invalid Version",
  "Function Runtimes must have a valid version", npm install failures)
- React/TypeScript build issues in AI tools, including builds that work
  locally but fail on Vercel
- API endpoint corruption or syntax errors
- Errors that persist after vercel.json and API routes have been fixed
- Deciding whether to fix a React build or convert it to static HTML

The full React → static HTML procedure, the fix-vs-convert decision table and
a worked case are in **`references/react-to-static-conversion.md`**.

## Common Deployment Issues & Solutions

### 1. Vercel Runtime Configuration Errors

**Error**: `Function Runtimes must have a valid version, for example now-php@1. 0.0`

**Root Cause**: Invalid runtime specification in `vercel.json`

**Solutions** (try in order):
```json
// Option 1: Use nodejs18.x
{
  "functions": {
    "api/endpoint.ts": {
      "runtime": "nodejs18.x"
    }
  }
}

// Option 2: Simplify and let Vercel auto-detect
{
  "functions": {
    "api/endpoint.js": {
      "maxDuration": 30
    }
  }
}

// Option 3: Remove vercel.json entirely for simple projects
```

### 2. Corrupted API Files

**Symptoms**: 
- Build succeeds but API doesn't work
- Syntax errors in TypeScript compilation
- Lines like `const openaiApiKey=proces...KEY;`

**Diagnosis**:
```bash
# Check for corrupted lines
grep -n "proces\.\.\." api/*.ts api/*.js
```

**Fix**: 
1. Read the entire corrupted file
2. Rewrite it completely (don't try to patch corrupted syntax)
3. Verify all environment variable references are correct

### 3. React Build Complexity Issues

**Quick diagnosis:** a package.json over ~40 lines, a `src/` component tree
and `api/*.ts` routes, against working tools with under 15 lines, static HTML
and `api/*.js`, points to an architecture mismatch rather than a config bug.

**Fix React** when it's genuinely needed (complex state, real-time features,
a large working codebase). **Convert** when the tool is a simple form → API →
results and build errors persist after config fixes.

**When React/TypeScript builds fail repeatedly**, convert to simple HTML:

**Conversion Strategy**:
1. **Backup React files**: `cp package.json package-react.json.bak`
2. **Create simple package.json**:
   ```json
   {
     "name": "ai-tool-name",
     "version": "1.0.0", 
     "dependencies": {
       "openai": "^4.0.0"
     }
   }
   ```
3. **Convert React JSX to HTML**: Copy UI exactly, replace JSX syntax
4. **Convert TypeScript API to JavaScript**: Remove type annotations
5. **Test locally**: Ensure functionality matches original

## Systematic Debugging Process

### Step 1: Identify Error Type

**Build Errors**:
- Check Vercel deployment logs
- Look for TypeScript compilation failures
- Verify all imports and dependencies

**Runtime Errors**:
- Check API endpoint structure
- Verify environment variables
- Test API routes locally

**Configuration Errors**:
- Review vercel.json syntax
- Check package.json dependencies
- Validate runtime specifications

### Step 2: Quick Fixes (Try First)

```bash
# 1. Clean deployment
rm -rf node_modules package-lock.json
git add . && git commit -m "Clean deployment"
git push

# 2. Simplify vercel.json
# Remove complex configurations, use defaults

# 3. Check for file corruption
grep -rn "proces\.\.\." api/
grep -rn "undefined" api/
```

### Step 3: Nuclear Option - HTML Conversion

When React builds continue failing:

```bash
# 1. Backup React version
cp package.json package-react.json.bak
cp vercel.json vercel-react.json.bak
cp -r src/ src-react-backup/

# 2. Create simple structure
cat > package.json << EOF
{
  "name": "ai-tool",
  "dependencies": { "openai": "^4.0.0" }
}
EOF

# 3. Convert API endpoints
mv api/endpoint.ts api/endpoint.js
# Edit file: remove TypeScript types, keep logic
```

## Proven Working Structure

Use this structure for reliable deployments:

```
ai-tool/
├── index.html              # Main app (no React)
├── api/endpoint.js          # JavaScript API (no TypeScript)
├── package.json             # Minimal dependencies
├── vercel.json              # Simple config or none
├── privacy-policy.html      # Compliance
├── terms-of-service.html    # Compliance  
├── robots.txt               # SEO
├── sitemap.xml              # SEO
└── public/ads.txt           # Monetization
```

## API Endpoint Template

**Working JavaScript API pattern**:
```javascript
const OpenAI = require('openai');

let openai;
if (process.env.OPENAI_API_KEY) {
    openai = new OpenAI({
        apiKey: process.env.OPENAI_API_KEY,
    });
}

export default async function handler(req, res) {
    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    // Rate limiting
    const clientIP = req.headers['x-forwarded-for'] || req.connection.remoteAddress || 'unknown';
    const today = new Date().toDateString();
    const rateLimitKey = `${clientIP}_${today}`;
    
    if (!global.rateLimitStore) global.rateLimitStore = {};
    if (!global.rateLimitStore[rateLimitKey]) global.rateLimitStore[rateLimitKey] = 0;
    
    if (global.rateLimitStore[rateLimitKey] >= 3) {
        return res.status(429).json({ 
            error: 'Rate limit exceeded',
            message: 'Daily limit reached. Try again tomorrow!'
        });
    }
    global.rateLimitStore[rateLimitKey]++;

    const { text } = req.body;

    // Validation
    if (!text) {
        return res.status(400).json({ error: 'Text required' });
    }

    try {
        // Demo mode if no API key
        if (!openai) {
            return res.json({ result: "Demo response..." });
        }

        // Real OpenAI call
        const completion = await openai.chat.completions.create({
            model: "gpt-4o-mini",
            messages: [/* your messages */],
            temperature: 0.3,
        });

        return res.json({ result: completion.choices[0].message.content });

    } catch (error) {
        console.error('API Error:', error);
        return res.status(500).json({ error: 'Processing failed' });
    }
}
```

## Pitfalls to Avoid

1. **Don't edit corrupted files in-place** - rewrite completely
2. **Don't ignore runtime errors** - they often indicate file corruption
3. **Don't over-complicate vercel.json** - simpler is more reliable
4. **Don't use TypeScript for simple AI tools** - JavaScript is more reliable
5. **Always test API endpoints locally** before deployment

## Success Indicators

✅ **Deployment succeeds** without build errors
✅ **API responds** with demo data when no OpenAI key
✅ **Rate limiting works** (test with multiple requests)
✅ **UI functions** identically to original React version
✅ **Mobile responsive** design maintained
✅ **SEO and ads** integrated properly

## When This Approach Works Best

- Simple AI tools (document processors, text generators, analyzers)
- Revenue-focused projects where reliability > complexity
- When React build issues persist despite troubleshooting
- Projects requiring fast deployment and iteration
- Tools targeting ad monetization (simpler = better performance)

This "nuclear option" of converting React to HTML often saves hours of debugging and produces more reliable, faster-loading AI tools.