# BrainInk Backend - Chainlink/Kana AI Integration

This document outlines the integration between the BrainInk FastAPI backend and the React-based Chainlink/Kana AI question generator.

## Overview

The integration allows the tournament system to generate dynamic questions using the AI-powered question generator from your React frontend repo.

## Architecture

```
React Frontend (Chainlink/Kana AI) -> HTTP API -> FastAPI Backend -> Tournament Questions
```

## Key Components

### 1. Schemas (`schemas/chainlink_schemas.py`)
- `ChainlinkQuestionRequest`: Request format for the Chainlink service
- `ChainlinkQuestionResponse`: Response format from Chainlink service  
- `ConvertedTournamentQuestion`: Converted format for tournament use

### 2. Service Layer (`services/chainlink_service.py`)
- `ChainlinkQuestionService`: Main integration service
- Handles API communication with React/Chainlink service
- Converts question formats between systems
- Provides fallback mechanisms

### 3. Tournament Integration (`functions/tournament_functions.py`)
- Updated `TournamentService` with async question generation
- Integrates Chainlink service into tournament creation
- Fallback to local questions if service unavailable

### 4. API Endpoints (`Endpoints/chainlink.py`)
- `/chainlink/test-question-generation`: Test the integration
- `/chainlink/generate-tournament-questions`: Generate questions for tournaments
- `/chainlink/health`: Check service availability

## Question Format Conversion

### From Chainlink/Kana AI:
```javascript
{
  question: "What is 2+2?",
  options: ["3", "4", "5", "6"],
  correctAnswer: 1, // Index (0-3)
  xpReward: 10,
  topic: "Basic Math"
}
```

### To Tournament Format:
```python
{
  question_text: "What is 2+2?",
  option_a: "3",
  option_b: "4", 
  option_c: "5",
  option_d: "6",
  correct_answer: "B", // Letter (A-D)
  subject: "Mathematics",
  topic: "Basic Math",
  difficulty_level: "elementary",
  points_value: 10,
  time_limit_seconds: 30
}
```

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
# Chainlink Service URL (update to match your React app)
CHAINLINK_API_URL=http://localhost:3000/api/generate-questions
CHAINLINK_ENABLED=true

# Tournament defaults
DEFAULT_QUESTION_COUNT=50
DEFAULT_TIME_LIMIT_MINUTES=60
DEFAULT_DIFFICULTY=middle_school

# Fallback settings
USE_FALLBACK_QUESTIONS=true
FALLBACK_ON_ERROR=true
```

## Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Update React Frontend
Your React component needs to expose an HTTP API endpoint that accepts:

```javascript
// POST /api/generate-questions
{
  topics: ["mathematics", "physics"],
  difficulty: "middle_school",
  count: 10,
  subject: "Science",
  timeLimit: 60
}
```

And returns:
```javascript
{
  questions: [
    {
      question: "What is the speed of light?",
      options: ["299,792,458 m/s", "300,000,000 m/s", "299,000,000 m/s", "298,000,000 m/s"],
      correctAnswer: 0,
      xpReward: 15,
      topic: "Physics"
    }
    // ... more questions
  ]
}
```

### 3. Start Services
1. Start your React app with the question generator service
2. Start the FastAPI backend
3. Test the integration using `/chainlink/health` endpoint

## API Usage

### Create Tournament with AI Questions
```python
POST /tournaments/create
{
  "name": "Physics Tournament",
  "max_players": 16,
  "tournament_type": "public",
  "bracket_type": "single_elimination",
  "prize_config": {
    "has_prizes": true,
    "first_place_prize": "100 XP"
  },
  "question_config": {
    "total_questions": 20,
    "time_limit_minutes": 30,
    "difficulty_level": "high_school",
    "subject_category": "Physics",
    "custom_topics": ["mechanics", "thermodynamics", "optics"]
  }
}
```

### Test Question Generation
```python
POST /chainlink/test-question-generation
{
  "topics": ["mathematics", "algebra"],
  "difficulty_level": "middle_school", 
  "question_count": 5,
  "subject_category": "Mathematics"
}
```

## Error Handling

The system includes multiple fallback mechanisms:

1. **Service Unavailable**: Falls back to local question bank
2. **Network Errors**: Retries with exponential backoff
3. **Invalid Responses**: Validates and filters invalid questions
4. **Partial Failures**: Uses available questions and fills gaps with fallbacks

## Testing

### Health Check
```bash
curl http://localhost:8000/chainlink/health
```

### Generate Test Questions
```bash
curl -X POST http://localhost:8000/chainlink/test-question-generation \
  -H "Content-Type: application/json" \
  -d '{
    "topics": ["test"],
    "difficulty_level": "elementary",
    "question_count": 1
  }'
```

## Compatibility Checklist

- ✅ Question format conversion (index → letter)
- ✅ Topic mapping and validation
- ✅ Difficulty level standardization  
- ✅ XP/points value handling
- ✅ Time limit distribution
- ✅ Error handling and fallbacks
- ✅ Async operation support
- ✅ Database integration
- ✅ API endpoint exposure

## Next Steps

1. **Deploy React Service**: Ensure your React app exposes the API endpoint
2. **Update Configuration**: Set the correct `CHAINLINK_API_URL` in your environment
3. **Test Integration**: Use the health check and test endpoints
4. **Monitor Logs**: Check for integration errors and adjust as needed
5. **Scale Considerations**: Add rate limiting and caching if needed

## Troubleshooting

### Common Issues

1. **Connection Refused**: Ensure React app is running and API endpoint is accessible
2. **Invalid Questions**: Check question format from Chainlink service
3. **Timeout Errors**: Increase timeout values for large question counts
4. **Format Mismatches**: Verify the conversion logic in `chainlink_service.py`

### Debug Mode

Enable debug logging by setting:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```
