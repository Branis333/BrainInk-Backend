# 📱 Frontend Integration Guide - Reading Assistant

## 🎯 Complete API Reference for Mobile App Integration

### 🔑 **Authentication Required**
All endpoints require JWT token in Authorization header:
```javascript
headers: {
  'Authorization': 'Bearer YOUR_JWT_TOKEN',
  'Content-Type': 'application/json'
}
```

---

## 📚 **1. READING CONTENT MANAGEMENT**

### Get Reading Content for Student
```javascript
// Get age-appropriate reading content
const getReadingContent = async (studentId, gradeLevel = 'K') => {
  const response = await fetch(`/reading-assistant/content?grade_level=${gradeLevel}&limit=10`, {
    headers: {
      'Authorization': `Bearer ${jwtToken}`,
      'Content-Type': 'application/json'
    }
  });
  
  const data = await response.json();
  /*
  Returns:
  {
    "success": true,
    "content": [
      {
        "id": 1,
        "title": "The Big Cat",
        "content": "The big cat runs fast. The cat is black.",
        "difficulty_level": "beginner",
        "reading_level": "K",
        "word_count": 9,
        "estimated_duration": 30
      }
    ]
  }
  */
  return data.content;
};
```

### Create Custom Reading Content (Teachers)
```javascript
const createReadingContent = async (contentData) => {
  const response = await fetch('/reading-assistant/content', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${jwtToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      title: "My Custom Story",
      content: "The sun is bright. Birds sing songs.",
      difficulty_level: "beginner",
      reading_level: "K",
      subject: "reading"
    })
  });
  
  return await response.json();
};
```

---

## 🎤 **2. READING SESSION & AUDIO ANALYSIS**

### Start Reading Session
```javascript
const startReadingSession = async (studentId, contentId) => {
  const response = await fetch('/reading-assistant/session/start', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${jwtToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      student_id: studentId,
      content_id: contentId
    })
  });
  
  const session = await response.json();
  /*
  Returns:
  {
    "success": true,
    "session": {
      "id": 123,
      "student_id": 456,
      "content_id": 1,
      "status": "active",
      "started_at": "2025-09-24T10:00:00Z"
    }
  }
  */
  return session;
};
```

### Upload Audio for Analysis ⭐ **MAIN FEATURE**
```javascript
const analyzeReading = async (sessionId, audioBlob, expectedText) => {
  const formData = new FormData();
  formData.append('audio_file', audioBlob, 'reading.wav');
  formData.append('session_id', sessionId);
  formData.append('expected_text', expectedText);
  
  const response = await fetch('/reading-assistant/analyze-audio', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${jwtToken}`
      // Don't set Content-Type for FormData - browser handles it
    },
    body: formData
  });
  
  const analysis = await response.json();
  /*
  Returns:
  {
    "success": true,
    "transcribed_text": "The big ket runs fest",
    "analysis": {
      "overall_score": 7.5,
      "reading_pace": "appropriate",
      "word_analysis": [
        {
          "word": "The",
          "expected": "The",
          "status": "correct",
          "confidence": 0.95
        },
        {
          "word": "ket", 
          "expected": "cat",
          "status": "incorrect",
          "confidence": 0.80,
          "pronunciation_url": "/pronunciation-audio/cat_123.mp3"
        },
        {
          "word": "fest",
          "expected": "fast", 
          "status": "incorrect",
          "confidence": 0.75,
          "pronunciation_url": "/pronunciation-audio/fast_124.mp3"
        }
      ]
    },
    "feedback": {
      "encouragement": "Great job reading! Let's practice a couple words together.",
      "suggestions": ["Practice the 'cat' sound", "Try saying 'fast' slower"]
    }
  }
  */
  return analysis;
};
```

---

## 🔊 **3. PRONUNCIATION FEATURES** ⭐ **NEW TTS SYSTEM**

### Get Word Pronunciation
```javascript
const getWordPronunciation = async (word) => {
  const response = await fetch('/reading-assistant/pronunciation/word', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${jwtToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      word: word,
      speed: "slow", // "slow", "normal", "fast"
      voice_type: "child_friendly"
    })
  });
  
  const result = await response.json();
  /*
  Returns:
  {
    "success": true,
    "word": "cat",
    "audio_url": "/pronunciation-audio/cat_123.mp3",
    "phonetic": "kæt",
    "syllables": ["cat"],
    "tips": "Make the 'k' sound, then 'a' as in 'apple', then 't'"
  }
  */
  
  // Play the audio
  if (result.success && result.audio_url) {
    const audio = new Audio(result.audio_url);
    audio.play();
  }
  
  return result;
};
```

### Get Sentence Pronunciation
```javascript
const getSentencePronunciation = async (sentence) => {
  const response = await fetch('/reading-assistant/pronunciation/sentence', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${jwtToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      sentence: sentence,
      speed: "slow",
      pause_between_words: true
    })
  });
  
  const result = await response.json();
  /*
  Returns:
  {
    "success": true,
    "sentence": "The big cat runs fast",
    "audio_url": "/pronunciation-audio/sentence_456.mp3",
    "word_breakdown": [
      {
        "word": "The",
        "phonetic": "ðə",
        "audio_url": "/pronunciation-audio/the_789.mp3"
      }
    ]
  }
  */
  
  return result;
};
```

---

## 📊 **4. PROGRESS TRACKING**

### Get Student Progress
```javascript
const getStudentProgress = async (studentId) => {
  const response = await fetch(`/reading-assistant/progress/${studentId}`, {
    headers: {
      'Authorization': `Bearer ${jwtToken}`,
      'Content-Type': 'application/json'
    }
  });
  
  const progress = await response.json();
  /*
  Returns:
  {
    "success": true,
    "progress": {
      "current_level": "K",
      "sessions_completed": 15,
      "average_score": 8.2,
      "words_mastered": 45,
      "recent_sessions": [...],
      "achievements": ["First Reading!", "10 Words Mastered"]
    }
  }
  */
  return progress;
};
```

### Update Reading Progress
```javascript
const updateProgress = async (sessionId, score, wordsCorrect, totalWords) => {
  const response = await fetch('/reading-assistant/progress/update', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${jwtToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      session_id: sessionId,
      score: score,
      words_correct: wordsCorrect,
      total_words: totalWords,
      completed: true
    })
  });
  
  return await response.json();
};
```

---

## 📱 **5. COMPLETE MOBILE APP FLOW**

### React Native Implementation Example
```javascript
import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, Alert } from 'react-native';
import { Audio } from 'expo-av';

const ReadingAssistant = ({ studentId, jwtToken }) => {
  const [reading, setReading] = useState(null);
  const [session, setSession] = useState(null);
  const [recording, setRecording] = useState(null);
  const [analysis, setAnalysis] = useState(null);

  // 1. Load reading content
  useEffect(() => {
    loadReadingContent();
  }, []);

  const loadReadingContent = async () => {
    try {
      const response = await fetch('/reading-assistant/content?grade_level=K&limit=1', {
        headers: {
          'Authorization': `Bearer ${jwtToken}`,
          'Content-Type': 'application/json'
        }
      });
      const data = await response.json();
      if (data.success && data.content.length > 0) {
        setReading(data.content[0]);
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to load reading content');
    }
  };

  // 2. Start reading session
  const startSession = async () => {
    try {
      const response = await fetch('/reading-assistant/session/start', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${jwtToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          student_id: studentId,
          content_id: reading.id
        })
      });
      const sessionData = await response.json();
      if (sessionData.success) {
        setSession(sessionData.session);
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to start session');
    }
  };

  // 3. Record and analyze audio
  const startRecording = async () => {
    try {
      const { status } = await Audio.requestPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission needed', 'Microphone access required');
        return;
      }

      const recordingOptions = {
        android: {
          extension: '.wav',
          outputFormat: Audio.RECORDING_OPTION_ANDROID_OUTPUT_FORMAT_MPEG_4,
          audioEncoder: Audio.RECORDING_OPTION_ANDROID_AUDIO_ENCODER_AAC,
          sampleRate: 16000,
          numberOfChannels: 1,
          bitRate: 128000,
        },
        ios: {
          extension: '.wav',
          outputFormat: Audio.RECORDING_OPTION_IOS_OUTPUT_FORMAT_LINEARPCM,
          audioQuality: Audio.RECORDING_OPTION_IOS_AUDIO_QUALITY_HIGH,
          sampleRate: 16000,
          numberOfChannels: 1,
          bitRate: 128000,
          linearPCMBitDepth: 16,
          linearPCMIsBigEndian: false,
          linearPCMIsFloat: false,
        },
      };

      const { recording } = await Audio.Recording.createAsync(recordingOptions);
      setRecording(recording);
    } catch (error) {
      Alert.alert('Error', 'Failed to start recording');
    }
  };

  const stopRecording = async () => {
    try {
      await recording.stopAndUnloadAsync();
      const uri = recording.getURI();
      
      // Upload and analyze
      await analyzeAudio(uri);
    } catch (error) {
      Alert.alert('Error', 'Failed to stop recording');
    }
  };

  const analyzeAudio = async (audioUri) => {
    try {
      const formData = new FormData();
      formData.append('audio_file', {
        uri: audioUri,
        type: 'audio/wav',
        name: 'reading.wav',
      });
      formData.append('session_id', session.id);
      formData.append('expected_text', reading.content);

      const response = await fetch('/reading-assistant/analyze-audio', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${jwtToken}`,
        },
        body: formData,
      });

      const analysisData = await response.json();
      if (analysisData.success) {
        setAnalysis(analysisData);
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to analyze audio');
    }
  };

  // 4. Handle pronunciation help
  const playPronunciation = async (word) => {
    try {
      const response = await fetch('/reading-assistant/pronunciation/word', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${jwtToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          word: word,
          speed: "slow"
        })
      });

      const result = await response.json();
      if (result.success && result.audio_url) {
        const { sound } = await Audio.Sound.createAsync({ uri: result.audio_url });
        await sound.playAsync();
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to play pronunciation');
    }
  };

  return (
    <View>
      {reading && (
        <View>
          <Text style={{ fontSize: 24, marginBottom: 20 }}>
            {reading.title}
          </Text>
          
          <Text style={{ fontSize: 18, marginBottom: 20 }}>
            {reading.content}
          </Text>

          {!session && (
            <TouchableOpacity onPress={startSession}>
              <Text>Start Reading</Text>
            </TouchableOpacity>
          )}

          {session && !recording && (
            <TouchableOpacity onPress={startRecording}>
              <Text>🎤 Start Recording</Text>
            </TouchableOpacity>
          )}

          {recording && (
            <TouchableOpacity onPress={stopRecording}>
              <Text>⏹️ Stop Recording</Text>
            </TouchableOpacity>
          )}

          {analysis && (
            <View>
              <Text>Score: {analysis.analysis.overall_score}/10</Text>
              <Text>{analysis.feedback.encouragement}</Text>
              
              {analysis.analysis.word_analysis.map((word, index) => (
                <View key={index} style={{ 
                  flexDirection: 'row',
                  backgroundColor: word.status === 'correct' ? '#90EE90' : '#FFB6C1',
                  margin: 5,
                  padding: 10,
                  borderRadius: 5
                }}>
                  <Text>{word.word}</Text>
                  {word.status === 'incorrect' && (
                    <TouchableOpacity onPress={() => playPronunciation(word.expected)}>
                      <Text>🔊</Text>
                    </TouchableOpacity>
                  )}
                </View>
              ))}
            </View>
          )}
        </View>
      )}
    </View>
  );
};

export default ReadingAssistant;
```

---

## 🎯 **6. KEY API ENDPOINTS SUMMARY**

| Endpoint | Method | Purpose |
|----------|---------|---------|
| `/reading-assistant/content` | GET | Get reading materials |
| `/reading-assistant/content` | POST | Create custom content |
| `/reading-assistant/session/start` | POST | Start reading session |
| `/reading-assistant/analyze-audio` | POST | **Main feature - analyze reading** |
| `/reading-assistant/pronunciation/word` | POST | **Get word pronunciation** |
| `/reading-assistant/pronunciation/sentence` | POST | Get sentence pronunciation |
| `/reading-assistant/progress/{student_id}` | GET | Get reading progress |
| `/reading-assistant/sessions/{student_id}` | GET | Get session history |

---

## 💡 **Usage Tips:**

1. **Authentication**: Always include JWT token
2. **Audio Format**: Use WAV format, 16kHz sample rate for best results
3. **Error Handling**: Check `success` field in responses
4. **Pronunciation URLs**: Cache audio files for offline replay
5. **Progress Tracking**: Update progress after each session
6. **Mobile Optimization**: Use device TTS as fallback for offline mode

---

## 🔧 **Testing Endpoints:**

```bash
# Test with curl
curl -X POST "http://your-api/reading-assistant/pronunciation/word" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"word": "cat", "speed": "slow"}'
```

This guide provides everything you need to integrate the reading assistant into your mobile app! 🚀📱