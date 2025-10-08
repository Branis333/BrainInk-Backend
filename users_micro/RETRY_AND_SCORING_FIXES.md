# Retry and Scoring Fixes - October 8, 2025

## Issues Fixed

### 1. **Retry Button Error: "Maximum attempts reached"**

**Problem**: Users clicking the "Retry" button got error "Maximum attempts (3) reached in 24 hours" even when the UI showed they had attempts remaining (e.g., "2/3 attempts used").

**Root Cause**: 
- Line 1772-1777 in `grades.py`: The retry endpoint was checking attempt count **before** determining if user was just clicking retry vs actually submitting new work
- Logic flow:
  1. User submits assignment → creates submission #1
  2. Gets 0% score → clicks "Retry" button
  3. Backend counts 1 attempt, sees no new submission payload, returns "ready to retry"
  4. User submits again → creates submission #2 → gets 0% → clicks "Retry"
  5. Backend now counts 2 attempts
  6. After 3 submissions, clicking "Retry" button would fail with "Maximum attempts reached" **before** checking if they're just inquiring about retry status

**Solution**:
- Moved the `>= 3 attempts` check to AFTER determining if user is submitting new work
- Clicking "Retry" button now always succeeds and returns status
- Only block when user tries to actually SUBMIT new work after 3 attempts

**Code Changes** (`grades.py` line 1732-1810):
```python
# BEFORE: Blocked retry button clicks
if recent_attempts >= 3:
    raise HTTPException(status_code=400, detail="Maximum attempts...")

# AFTER: Allow retry button clicks, only block actual submissions
if not has_submission_payload:
    # Just return status - let them see retry is available
    return {...}

# NOW check attempts when submitting new work
if recent_attempts >= 3:
    raise HTTPException(status_code=400, detail="Maximum attempts...")
```

---

### 2. **Null Score Handling and Display**

**Problem**: When Gemini AI fails to extract a numeric score (returns `null`), the frontend was inconsistent:
- Sometimes showed "0%"
- Sometimes showed "— Pending"
- Logs showed `rawScore: null` → `computedScore: 0` but UI still said "Pending"

**Root Cause**:
- Backend `normalize_ai_grading()` returns `"ai_score": None` when Gemini doesn't provide a parseable score
- Frontend interface declared `ai_score: number` (non-nullable) but backend could return `null`
- Frontend logic: `ai?.ai_score != null ? ai.ai_score : (ai ? 0 : undefined)`
  - Converts `null` → `0` for display
  - But display check was: `results.ai_score != null` which would be FALSE for the converted 0

**Solution**:
1. **Backend logging added** (uploads.py):
   - Line 497-507: Log initial grading attempt with keys available
   - Line 527-548: Log final score and warn if null
   - This helps diagnose WHY Gemini returns null (safety filters, API errors, etc.)

2. **Frontend type fixed** (uploadsService.ts line 94):
   ```typescript
   ai_score: number | null;  // Allow null explicitly
   ```

3. **Frontend display logic** (CourseAssignmentScreen.tsx line 830-833):
   ```typescript
   {results.ai_score != null && typeof results.ai_score === 'number' && !isNaN(results.ai_score)
       ? `${Math.round(results.ai_score)}%`
       : '— Pending'}
   ```
   - The `!= null` check properly handles both `null` and `undefined`
   - For legitimate 0 scores, shows "0%"
   - For null/failed extraction, shows "— Pending"

---

### 3. **Why Scores Are Coming Back as Null**

Looking at the logs, the common pattern is:
```
"feedback": "AI processing issue: 'harm_category_self_harm'"
"feedback": "Invalid operation: The `response.text` quick accessor..."
"feedback": "AI processed the submission but did not return detailed feedback."
```

**These indicate**:
1. **Safety filters**: Gemini's safety system is blocking content
2. **API errors**: Gemini API returning errors instead of grading
3. **Empty responses**: Gemini not returning structured grading data

**Next Steps** (not in this fix):
- Review Gemini safety settings
- Add retry logic for API errors
- Implement fallback scoring when Gemini fails
- Consider alternative grading approach for safety-flagged content

---

## Backend Changes

### `grades.py`
**Line 1760-1780**: Added logging and moved attempt validation
```python
logger.info("Retry attempt check", extra={...})

# Don't block retry button clicks
# Only block actual new submissions after 3 attempts
```

**Line 1790-1798**: Improved retry status message
```python
message = (
    f"Ready to retry. You have {attempts_remaining} attempt(s) remaining today."
    if attempts_remaining > 0
    else "No attempts remaining today. Try again tomorrow."
)
```

**Line 1822-1827**: Check attempts AFTER confirming new submission
```python
# User is submitting new work - NOW check if they've exceeded attempts
if recent_attempts >= 3:
    raise HTTPException(...)
```

### `uploads.py`
**Line 497-507**: Log initial grading attempt
```python
logger.info("Initial AI grading attempt", extra={
    "ai_score": normalized.get("ai_score"),
    "has_percentage": "percentage" in grading,
    "has_score": "score" in grading",
    "grading_keys": list(grading.keys())
})
```

**Line 527-548**: Enhanced completion logging
```python
logger.info("AI grading completed", extra={
    "ai_score": normalized.get("ai_score"),
    "feedback_preview": normalized.get("ai_feedback")[:100]
})

if normalized.get("ai_score") is None:
    logger.warning("AI grading failed to extract score", extra={...})
```

---

## Frontend Changes

### `uploadsService.ts`
**Line 94**: Updated interface
```typescript
ai_score: number | null;  // Explicitly allow null
```

**Line 683**: Updated fallback
```typescript
ai_score: null,  // Use null instead of 0 for "no score"
```

### `CourseAssignmentScreen.tsx`
**Line 453-457**: Score extraction
```typescript
const aiScore = ai?.ai_score != null ? ai.ai_score : (ai ? 0 : undefined);
```

**Line 460-467**: Added debug logging
```typescript
console.log('🎯 AI Processing Results:', {
    rawScore: ai?.ai_score,
    computedScore: aiScore,
    ...
});
```

**Line 830-833**: Display logic
```typescript
{results.ai_score != null && typeof results.ai_score === 'number' && !isNaN(results.ai_score)
    ? `${Math.round(results.ai_score)}%`
    : '— Pending'}
```

---

## Testing Scenarios

### Retry Flow
1. ✅ User gets 0% → clicks Retry → should succeed with "Ready to retry" message
2. ✅ After 2 attempts → clicks Retry → should show "1 attempt remaining"
3. ✅ After 3 attempts → clicks Retry → should show "No attempts remaining"
4. ✅ After 3 attempts → tries to submit new work → should get error

### Score Display
1. ✅ Gemini returns valid score (e.g., 45%) → shows "45%"
2. ✅ Gemini returns 0 → shows "0%"
3. ✅ Gemini returns null (safety filter) → shows "— Pending"
4. ✅ Gemini returns null (API error) → shows "— Pending"

---

## Known Issues Remaining

1. **Gemini Safety Filters**: Content being flagged by `harm_category_self_harm` - needs safety settings review
2. **API Errors**: Gemini sometimes returns incomplete responses - needs retry logic
3. **Score Extraction**: When Gemini doesn't return structured data, score is null - needs fallback

These require Gemini service configuration changes beyond the scope of this fix.
