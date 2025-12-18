# Database Connection & AI Feedback Storage Fix

## Problem Summary

### Issue 1: Database Connection Failures
**Error**: `psycopg2.OperationalError: server closed the connection unexpectedly`

The PostgreSQL database connection was being lost during the AI grading update, causing:
- Successful Gemini AI grading (score: 85, feedback generated)
- Failed database persistence (transaction rolled back)
- Complete request failure despite successful AI processing

### Issue 2: Incomplete Feedback Storage
Database only stored:
- ✅ `ai_score` (number)
- ✅ `ai_feedback` (text)
- ❌ `ai_strengths` (NULL - should be JSON array)
- ❌ `ai_improvements` (NULL - should be JSON array)
- ❌ `ai_corrections` (NULL - should be JSON array)

## Solutions Implemented

### 1. Database Retry Logic (uploads.py)
Added 3-attempt retry mechanism with connection refresh:

```python
max_db_retries = 3
for retry_attempt in range(max_db_retries):
    try:
        submission.ai_processed = True
        submission.ai_score = extracted_score
        submission.ai_feedback = extracted_feedback
        submission.ai_strengths = extracted_strengths  # NEW
        submission.ai_improvements = extracted_improvements  # NEW
        submission.ai_corrections = extracted_corrections  # NEW
        submission.processed_at = datetime.utcnow()
        db.commit()
        print(f"✅ Database updated successfully (attempt {retry_attempt + 1})")
        break
    except Exception as db_err:
        print(f"⚠️ Database update attempt {retry_attempt + 1} failed: {db_err}")
        db.rollback()  # Rollback failed transaction
        if retry_attempt < max_db_retries - 1:
            import time
            time.sleep(1)  # Wait 1 second before retry
            db.expire_all()  # Refresh session for new connection
        else:
            print(f"❌ Database update failed after {max_db_retries} attempts")
            raise
```

**Benefits**:
- Handles transient connection failures
- Rolls back failed transactions properly
- Refreshes database session between retries
- Provides detailed logging for debugging

### 2. Array Extraction & Storage (uploads.py)
Extract and serialize feedback arrays from Gemini response:

```python
import json

def extract_array(keys):
    for key in keys:
        if key in raw_grading:
            val = raw_grading[key]
            if isinstance(val, list):
                return json.dumps(val) if val else None
            elif isinstance(val, str) and val.strip() and val.strip() not in ['[', '{', '[]', '{}']:
                # Try parsing stringified array
                try:
                    parsed = json.loads(val)
                    if isinstance(parsed, list):
                        return json.dumps(parsed) if parsed else None
                except:
                    pass
    return None

extracted_strengths = extract_array(['strengths', '"strengths"'])
extracted_improvements = extract_array(['improvements', '"improvements"', 'recommendations', '"recommendations"'])
extracted_corrections = extract_array(['corrections', '"corrections"'])
```

**What This Does**:
- Extracts arrays from Gemini response (handles malformed keys)
- Serializes arrays as JSON strings for database TEXT columns
- Handles both clean arrays `["item1", "item2"]` and malformed `[` markers
- Stores in `ai_strengths`, `ai_improvements`, `ai_corrections` columns

### 3. Frontend Array Display (GradeDetailsScreen.tsx)
Parse and display JSON arrays from database:

```tsx
{submission.ai_strengths && (
    <Text style={styles.strengthsText}>
        {(() => {
            try {
                // Parse JSON array from database
                const strengths = JSON.parse(submission.ai_strengths);
                if (Array.isArray(strengths)) {
                    return strengths.map((s, i) => `${i + 1}. ${s}`).join('\n');
                }
            } catch {
                // Fallback to displaying as-is if not valid JSON
            }
            return submission.ai_strengths;
        })()}
    </Text>
)}
```

**Display Format**:
```
Strengths:
1. Clear explanations of skeletons and movement
2. Accurate descriptions of bone functions
3. Good understanding of causes and effects
```

## Testing Recommendations

### 1. Test Database Retry
Simulate connection failure:
```bash
# Force PostgreSQL to drop idle connections
sudo systemctl restart postgresql
```

Expected: Backend retries 3 times, succeeds on 2nd/3rd attempt

### 2. Test Array Storage
Submit assignment and verify database:
```sql
SELECT 
    id,
    ai_score,
    ai_strengths,
    ai_improvements,
    ai_corrections
FROM as_ai_submissions
WHERE id = <submission_id>;
```

Expected: JSON arrays stored as strings:
```
ai_strengths: ["Strong point 1", "Strong point 2"]
ai_improvements: ["Improvement 1", "Improvement 2"]
ai_corrections: ["Correction 1", "Correction 2"]
```

### 3. Test Frontend Display
Check GradeDetailsScreen shows:
- ✅ Numbered list format
- ✅ All array items visible
- ✅ Fallback to raw text if parsing fails

## Database Schema Verification

Ensure these columns exist in `as_ai_submissions` table:
```sql
ALTER TABLE as_ai_submissions
ADD COLUMN IF NOT EXISTS ai_strengths TEXT,
ADD COLUMN IF NOT EXISTS ai_improvements TEXT,
ADD COLUMN IF NOT EXISTS ai_corrections TEXT;
```

## Rollback Plan

If issues occur, revert to previous behavior:
1. Remove retry logic (use single `db.commit()`)
2. Remove array extraction code
3. Frontend displays raw `submission.ai_strengths` without parsing

## Performance Impact

- **Database Retry**: Adds 1-2 seconds delay only when connection fails (rare)
- **Array Extraction**: Minimal overhead (<10ms per submission)
- **Frontend Parsing**: Negligible (<1ms per array)

## Future Improvements

1. **Connection Pooling**: Use SQLAlchemy pool_pre_ping to detect stale connections
2. **Background Jobs**: Move AI processing to async task queue (Celery/RQ)
3. **JSON Columns**: Change `ai_strengths/improvements/corrections` to JSONB type
4. **Health Checks**: Add database connection monitoring

## Related Files Modified

**Backend**:
- `users_micro/Endpoints/after_school/uploads.py` (lines 530-570)

**Frontend**:
- `src/screens/grades/GradeDetailsScreen.tsx` (lines 342-407)

## Deployment Steps

1. Deploy backend changes first
2. Verify database connection retry works
3. Test with sample submission
4. Deploy frontend changes
5. Monitor logs for retry attempts
