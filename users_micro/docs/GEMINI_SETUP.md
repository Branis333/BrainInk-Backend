# Gemini API Configuration for After-School Learning System

## Environment Variables Required

Add these environment variables to your `.env` file:

```bash
# Gemini API Key (Google AI Studio)
GEMINI_API_KEY=your_gemini_api_key_here

# Optional: Gemini Model Configuration
GEMINI_MODEL=gemini-1.5-pro
GEMINI_TEMPERATURE=0.7
GEMINI_MAX_TOKENS=8192
```

## How to Get Your Gemini API Key

1. Visit [Google AI Studio](https://aistudio.google.com/)
2. Sign in with your Google account
3. Click "Get API Key" 
4. Create a new API key or use existing one
5. Copy the API key to your `.env` file

## Features Enabled with Gemini Integration

### 🤖 AI-Powered Course Creation
- **Textbook Analysis**: Upload textbook content and AI creates structured courses
- **Learning Block Generation**: Automatically creates weekly learning blocks
- **Resource Discovery**: Generates links to YouTube videos and educational articles
- **Assignment Creation**: Auto-generates assignments with rubrics and deadlines

### 📚 Comprehensive Learning Structure
- **Time-Based Organization**: Courses organized by weeks and blocks
- **Progressive Learning**: AI ensures logical content progression
- **Age-Appropriate Content**: Automatically adjusts complexity for target age group
- **Multi-Modal Resources**: Combines text, video, and interactive content

### 📝 Integrated Assignment System
- **Auto-Assignment Distribution**: Students get assignments when enrolling
- **Deadline Management**: Automatic due date calculation
- **Grading Integration**: Assignments connect to existing grading system
- **Progress Tracking**: Complete learning analytics and progress monitoring

## API Endpoints

### Course Creation from Textbook
```
POST /after-school/courses/from-textbook
```

### Student Enrollment with Auto-Assignment
```
POST /after-school/courses/{course_id}/enroll
```

### Assignment Management
```
GET /after-school/courses/assignments/my-assignments
```

## Example Usage

```python
# Create a course from textbook
course_data = {
    "title": "Advanced Mathematics for Grade 8",
    "subject": "Mathematics", 
    "textbook_content": "Chapter 1: Algebra Fundamentals...",
    "total_weeks": 12,
    "blocks_per_week": 2,
    "age_min": 13,
    "age_max": 14,
    "difficulty_level": "intermediate"
}

# This will create:
# - 24 learning blocks (12 weeks × 2 blocks)
# - Comprehensive assignments with deadlines
# - Resource links to YouTube and articles
# - Complete course structure ready for students
```

## Security and Rate Limiting

- API keys are securely stored as environment variables
- Requests to Gemini are rate-limited to prevent abuse
- Content generation is cached to reduce API calls
- Error handling ensures graceful fallbacks

## Troubleshooting

### Common Issues:
1. **GEMINI_API_KEY not set**: Add the environment variable
2. **API quota exceeded**: Check Google AI Studio usage limits
3. **Content too long**: Textbook content is automatically truncated
4. **Generation timeout**: Large courses may take 30-60 seconds

### Support:
- Check Google AI Studio documentation
- Verify API key permissions
- Monitor API usage quotas
- Review error logs for specific issues