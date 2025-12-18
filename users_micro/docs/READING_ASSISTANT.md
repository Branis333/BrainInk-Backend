# BrainInk Reading Assistant

An AI-powered reading assistance feature designed to help kindergarten through primary 3 students improve their reading skills through interactive speech analysis and personalized feedback.

## 🌟 Features

### Core Functionality
- **Speech-to-Text Analysis**: Uses Google Gemini AI to transcribe and analyze student reading
- **Real-time Pronunciation Feedback**: Identifies mispronounced words and provides correction tips
- **Fluency Assessment**: Measures reading speed, pauses, and rhythm
- **Progress Tracking**: Monitors student improvement over time
- **Personalized Recommendations**: Suggests appropriate content based on current skill level
- **Goal Setting**: Allows students to set and track reading goals

### AI-Powered Content Generation
- **Age-Appropriate Content**: Generates reading materials suited for specific grade levels
- **Phonics-Focused**: Creates content targeting specific phonetic patterns
- **Vocabulary Building**: Includes word definitions and usage examples
- **Difficulty Progression**: Automatically adjusts content complexity

### Educational Features
- **Multi-Level Support**: Kindergarten through Grade 3 content
- **Difficulty Gradations**: Beginner, Intermediate, and Advanced within each grade
- **Learning Objectives**: Clear educational goals for each reading session
- **Comprehensive Feedback**: Encouraging, constructive guidance for improvement

## 📚 Reading Levels & Content Types

### Reading Levels
- **Kindergarten** (Ages 4-5): 3-10 words per sentence, CVC words, basic sight words
- **Grade 1** (Ages 5-6): 5-15 words per sentence, simple compound words, phonics patterns
- **Grade 2** (Ages 6-7): 10-20 words per sentence, complex vocabulary, longer stories
- **Grade 3** (Ages 7-8): 15-25 words per sentence, chapter-like content, varied structures

### Content Types
- **Sentences**: Simple practice sentences focusing on specific skills
- **Paragraphs**: Short connected text for comprehension practice
- **Stories**: Engaging narratives with characters and plot progression

## 🔧 API Endpoints

### Content Management
```
POST   /after-school/reading-assistant/content           # Create reading content
POST   /after-school/reading-assistant/content/generate  # AI-generate content
GET    /after-school/reading-assistant/content           # List content with filters
GET    /after-school/reading-assistant/content/{id}      # Get specific content
```

### Reading Sessions
```
POST   /after-school/reading-assistant/sessions/start           # Start reading session
POST   /after-school/reading-assistant/sessions/{id}/complete   # Complete session
```

### Audio Processing
```
POST   /after-school/reading-assistant/audio/upload      # Upload & analyze reading audio
```

### Progress & Analytics
```
GET    /after-school/reading-assistant/progress          # Get student progress
GET    /after-school/reading-assistant/dashboard         # Comprehensive dashboard
GET    /after-school/reading-assistant/recommendations   # Content recommendations
```

### Goals & Achievements
```
POST   /after-school/reading-assistant/goals             # Create reading goal
GET    /after-school/reading-assistant/goals             # List student goals
```

## 📊 Database Schema

### Core Tables
- **reading_content**: Stores reading materials with metadata
- **reading_sessions**: Tracks individual practice sessions
- **reading_attempts**: Records specific reading attempts with audio
- **reading_progress**: Monitors overall student advancement
- **reading_feedback**: AI-generated feedback and suggestions
- **reading_goals**: Student learning objectives and targets

### Key Relationships
- Students have multiple reading sessions
- Sessions contain multiple attempts (for practice/retry)
- Each attempt generates detailed word-level feedback
- Progress tracks long-term learning trends

## 🤖 AI Integration

### Gemini AI Services
- **Speech Analysis**: Transcribes audio and analyzes pronunciation
- **Content Generation**: Creates age-appropriate reading materials
- **Feedback Generation**: Provides personalized learning guidance
- **Progress Assessment**: Evaluates skill development patterns

### Analysis Capabilities
- Word-by-word accuracy assessment
- Pronunciation error identification
- Reading fluency measurement
- Pause pattern analysis
- Phonetic error categorization

## 🎯 Learning Progression

### Automatic Level Advancement
Students progress when they consistently achieve:
- **Accuracy**: ≥85% word recognition
- **Fluency**: ≥75% age-appropriate reading speed
- **Consistency**: Success across multiple sessions

### Difficulty Adjustment
- **Within Level**: Beginner → Intermediate → Advanced
- **Between Levels**: Kindergarten → Grade 1 → Grade 2 → Grade 3
- **Adaptive Content**: Recommendations based on current performance

## 📱 Frontend Integration

### Expected Usage Flow
1. **Student Login**: Authenticate and access personalized dashboard
2. **Content Selection**: Choose or receive recommended reading material
3. **Reading Session**: Read aloud while system records audio
4. **Instant Feedback**: Receive pronunciation and fluency feedback
5. **Progress Review**: View improvement trends and achievements
6. **Goal Setting**: Establish and work toward reading objectives

### Dashboard Components
- Current reading level and progress
- Recent session results
- Active goals and achievements
- Recommended next content
- Weekly reading statistics

## 🔐 Security & Privacy

### Data Protection
- Student audio recordings are processed and then optionally deleted
- Personal progress data is encrypted and access-controlled
- All AI analysis happens through secure Gemini API calls
- COPPA-compliant data handling for young learners

### Authentication
- Requires valid user authentication for all endpoints
- Role-based access control for teachers/parents vs. students
- Session-based security for reading activities

## 🚀 Setup & Installation

### Prerequisites
```bash
# Install required dependencies
pip install google-generativeai>=0.3.0
pip install librosa  # For audio processing
pip install numpy   # For numerical analysis
```

### Environment Configuration
```bash
# Set up Gemini API key
GEMINI_API_KEY=your_api_key_here

# Database connection (existing Supabase setup)
DATABASE_URL=your_database_url
```

### Database Migration
```python
# Run to create reading assistant tables
from models.reading_assistant_models import Base
Base.metadata.create_all(bind=engine)

# Populate sample content
python utils/populate_reading_content.py
```

## 📈 Analytics & Reporting

### Student Metrics
- **Accuracy Trends**: Word recognition improvement over time
- **Fluency Development**: Reading speed progression
- **Vocabulary Growth**: New words learned and retained
- **Goal Achievement**: Progress toward learning objectives

### Teacher/Parent Insights
- Individual student progress summaries
- Class-wide performance analytics
- Struggling student identification
- Content engagement metrics

## 🔮 Future Enhancements

### Planned Features
- **Real-time WebSocket Audio**: Live feedback during reading
- **Comprehension Questions**: Post-reading understanding assessment
- **Multi-language Support**: Reading assistance in different languages
- **Voice Synthesis**: AI-generated pronunciation examples
- **Collaborative Reading**: Peer reading sessions and competitions

### Advanced AI Features
- **Emotion Detection**: Analyze reading confidence and engagement
- **Learning Style Adaptation**: Personalize based on individual preferences
- **Predictive Analytics**: Identify potential reading difficulties early
- **Adaptive Curriculum**: Dynamic content generation based on learning patterns

## 📞 API Response Examples

### Content Generation Response
```json
{
  "id": 1,
  "title": "The Magic Garden",
  "content": "Emma planted seeds in her small garden...",
  "reading_level": "kindergarten",
  "difficulty_level": "intermediate",
  "vocabulary_words": {
    "planted": "put seeds in the ground to grow",
    "garden": "a place where plants grow"
  },
  "learning_objectives": [
    "Read longer sentences with confidence",
    "Understand sequence of events"
  ],
  "phonics_focus": ["consonant blends", "long vowels"],
  "word_count": 25,
  "estimated_reading_time": 50
}
```

### Audio Analysis Response
```json
{
  "success": true,
  "attempt_id": 123,
  "transcribed_text": "Emma planted seeds in her small garden",
  "analysis_results": {
    "accuracy_percentage": 92.0,
    "fluency_score": 85.0,
    "pronunciation_score": 88.0,
    "reading_speed": 45.0,
    "word_accuracy": [
      {
        "target_word": "planted",
        "spoken_word": "planted",
        "is_correct": true,
        "pronunciation_accuracy": 95.0
      }
    ]
  },
  "feedback_message": "Great job reading! You pronounced most words clearly...",
  "next_suggestions": [
    {
      "id": 2,
      "title": "Animals in Winter",
      "reading_level": "kindergarten",
      "difficulty_level": "intermediate"
    }
  ]
}
```

## 📋 Testing

### Sample Content Included
- 3+ stories per reading level
- Various difficulty progressions
- Phonics-focused exercises
- Vocabulary building activities

### Testing Endpoints
```bash
# Health check
GET /after-school/reading-assistant/health

# Test content generation
POST /after-school/reading-assistant/content/generate
{
  "reading_level": "kindergarten",
  "difficulty_level": "beginner",
  "content_type": "story",
  "topic": "animals"
}
```

---

## 📞 Support

For technical questions or feature requests related to the Reading Assistant:

- **Backend Issues**: Check the FastAPI logs and database connections
- **AI Integration**: Verify Gemini API key and quota limits  
- **Audio Processing**: Ensure proper audio file formats (WAV, MP3, M4A)
- **Performance**: Monitor database query efficiency and API response times

The Reading Assistant is designed to be a comprehensive, AI-powered solution for early literacy development, providing both students and educators with the tools they need to improve reading skills effectively.