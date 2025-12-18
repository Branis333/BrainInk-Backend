# 📚 Reading Assistant Feature - Interface Design & Implementation Brief

## 🎯 **Feature Overview**
Create an AI-powered reading assistant for kindergarten to grade 3 students that:
- Shows age-appropriate reading content
- Records student reading attempts
- Provides real-time pronunciation feedback
- Offers interactive pronunciation help via tap-to-hear

---

## 🎨 **UI/UX Design Requirements**

### 📱 **Main Reading Screen Layout**
```
┌─────────────────────────────────────┐
│ 🏠 Reading Assistant    👤 Alex K   │
├─────────────────────────────────────┤
│                                     │
│     📖 "The Big Cat"                │
│                                     │
│  The big cat runs fast.             │
│  The cat likes to play.             │
│                                     │
│     [🎤 Start Reading]               │
│                                     │
│  📊 Progress: ████░░ 4/6 stories    │
│                                     │
└─────────────────────────────────────┘
```

### 🎤 **Recording State**
```
┌─────────────────────────────────────┐
│ 🔴 Recording... Tap to stop        │
├─────────────────────────────────────┤
│                                     │
│     📖 "The Big Cat"                │
│                                     │
│  The big cat runs fast.             │
│  The cat likes to play.             │
│                                     │
│     🔴 [⏹️ Stop Recording]          │
│                                     │
│  💡 Read clearly and slowly         │
│                                     │
└─────────────────────────────────────┘
```

### ✅ **Results & Feedback Screen**
```
┌─────────────────────────────────────┐
│ 🎉 Great job! Score: 8/10          │
├─────────────────────────────────────┤
│                                     │
│  The [big] [ket] runs [fest].       │
│       ✅    ❌        ❌            │
│                                     │
│  Tap red words to hear pronunciation│
│                                     │
│  🎵 [ket] → [cat] 🔊               │
│  🎵 [fest] → [fast] 🔊             │
│                                     │
│     [📚 Try Again] [➡️ Next]        │
│                                     │
└─────────────────────────────────────┘
```

---

## 🎨 **Design Guidelines**

### 🌈 **Color Scheme (Child-Friendly)**
- **Correct words**: `#90EE90` (Light Green)  
- **Incorrect words**: `#FFB6C1` (Light Pink/Red)
- **Primary buttons**: `#4CAF50` (Green)
- **Secondary buttons**: `#2196F3` (Blue)
- **Background**: `#F8F9FA` (Light Gray)
- **Text**: `#333333` (Dark Gray)

### 📝 **Typography**
- **Reading text**: Large, clear font (24-28px)
- **Instructions**: Medium font (18-20px)  
- **Buttons**: Bold, readable (16-18px)
- **Use child-friendly fonts**: Recommended - Comic Sans MS, OpenDyslexic, or similar

### 🎯 **Interaction Design**
- **Large tap targets** (minimum 44px)
- **Visual feedback** on all interactions
- **Loading states** with fun animations
- **Celebratory animations** for correct pronunciations
- **Encouraging messages** for improvements

---

## 🔗 **API Integration Guide**

### 🔑 **Authentication**
All API calls require JWT token:
```javascript
headers: {
  'Authorization': 'Bearer JWT_TOKEN_HERE',
  'Content-Type': 'application/json'
}
```

### 📋 **Implementation Flow**

#### **Step 1: Load Reading Content**
```javascript
// GET /after-school/reading-assistant/content?grade_level=K&limit=10
const loadReadingContent = async (gradeLevel) => {
  const response = await fetch(`/after-school/reading-assistant/content?grade_level=${gradeLevel}&limit=10`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  const data = await response.json();
  return data.content; // Array of reading materials
};
```

#### **Step 2: Start Reading Session**  
```javascript
// POST /after-school/reading-assistant/sessions/start
const startSession = async (studentId, contentId) => {
  const response = await fetch('/after-school/reading-assistant/sessions/start', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ student_id: studentId, content_id: contentId })
  });
  const session = await response.json();
  return session.session; // { id, student_id, content_id, status }
};
```

#### **Step 3: Record & Analyze Audio** ⭐ **MAIN FEATURE**
```javascript
// POST /after-school/reading-assistant/audio/upload
const analyzeReading = async (sessionId, contentId, audioBlob, attemptNumber = 1) => {
  const formData = new FormData();
  formData.append('audio_file', audioBlob, 'reading.wav');
  formData.append('session_id', sessionId);
  formData.append('content_id', contentId);
  formData.append('attempt_number', attemptNumber);
  
  const response = await fetch('/after-school/reading-assistant/audio/upload', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}` },
    body: formData
  });
  
  const result = await response.json();
  /*
  Returns:
  {
    "success": true,
    "transcribed_text": "The big ket runs fest",
    "analysis": {
      "overall_score": 7.5,
      "word_analysis": [
        {
          "word": "ket", 
          "expected": "cat",
          "status": "incorrect",
          "pronunciation_url": "/after-school/reading-assistant/pronunciation-audio/cat_123.mp3"
        }
      ]
    },
    "feedback": {
      "encouragement": "Great job! Let's practice a couple words.",
      "suggestions": ["Practice the 'cat' sound"]
    }
  }
  */
  return result;
};
```

#### **Step 4: Play Pronunciation** 🔊 **TAP-TO-HEAR FEATURE**
```javascript
// POST /after-school/reading-assistant/pronunciation/word
const playPronunciation = async (word) => {
  const response = await fetch('/after-school/reading-assistant/pronunciation/word', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ word: word, speed: "slow" })
  });
  
  const result = await response.json();
  if (result.success && result.audio_url) {
    const audio = new Audio(result.audio_url);
    audio.play(); // AI speaks the correct pronunciation
  }
};
```

---

## 📱 **Mobile App Development Options**

### 🔧 **SDK Compatibility Solutions**

If you encounter Expo SDK version conflicts:

**Option 1: Upgrade Project to SDK 54** (Recommended)
```bash
npx expo install --fix
npx expo upgrade
```

**Option 2: Downgrade Expo Go to SDK 53**
- Uninstall current Expo Go
- Install compatible version from app store

**Option 3: Use Expo Development Build** (Best for production)
```bash
npx expo install expo-dev-client
npx expo run:android  # or expo run:ios
```

### 📱 **React Native Implementation Example**

```jsx
import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, Alert, StyleSheet } from 'react-native';
// SDK 54 compatible imports
import { Audio } from 'expo-av';

const ReadingAssistant = ({ studentId, jwtToken }) => {
  const [content, setContent] = useState(null);
  const [session, setSession] = useState(null);
  const [recording, setRecording] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [isRecording, setIsRecording] = useState(false);

  // Load reading content on component mount
  useEffect(() => {
    loadContent();
  }, []);

  const loadContent = async () => {
    try {
      const response = await fetch('/after-school/reading-assistant/content?grade_level=K&limit=1', {
        headers: { 'Authorization': `Bearer ${jwtToken}` }
      });
      const data = await response.json();
      if (data.success) setContent(data.content[0]);
    } catch (error) {
      Alert.alert('Error', 'Failed to load content');
    }
  };

  const startReadingSession = async () => {
    try {
      const response = await fetch('/after-school/reading-assistant/sessions/start', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${jwtToken}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ student_id: studentId, content_id: content.id })
      });
      const sessionData = await response.json();
      setSession(sessionData.session);
    } catch (error) {
      Alert.alert('Error', 'Failed to start session');
    }
  };

  const startRecording = async () => {
    try {
      const { status } = await Audio.requestPermissionsAsync();
      if (status !== 'granted') return;

      const { recording } = await Audio.Recording.createAsync(
        Audio.RECORDING_OPTIONS_PRESET_HIGH_QUALITY
      );
      setRecording(recording);
      setIsRecording(true);
    } catch (error) {
      Alert.alert('Error', 'Failed to start recording');
    }
  };

  const stopRecording = async () => {
    try {
      await recording.stopAndUnloadAsync();
      const uri = recording.getURI();
      setIsRecording(false);
      
      // Analyze the recording
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
      formData.append('content_id', content.id);
      formData.append('attempt_number', 1);

      const response = await fetch('/after-school/reading-assistant/audio/upload', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${jwtToken}` },
        body: formData,
      });

      const result = await response.json();
      setAnalysis(result);
    } catch (error) {
      Alert.alert('Error', 'Failed to analyze audio');
    }
  };

  const playPronunciation = async (word) => {
    try {
      const response = await fetch('/after-school/reading-assistant/pronunciation/word', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${jwtToken}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ word, speed: "slow" })
      });

      const result = await response.json();
      if (result.success) {
        const { sound } = await Audio.Sound.createAsync({ uri: result.audio_url });
        await sound.playAsync();
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to play pronunciation');
    }
  };

  return (
    <View style={styles.container}>
      {content && (
        <>
          <Text style={styles.title}>{content.title}</Text>
          <Text style={styles.readingText}>{content.content}</Text>

          {!session ? (
            <TouchableOpacity style={styles.primaryButton} onPress={startReadingSession}>
              <Text style={styles.buttonText}>📚 Start Reading</Text>
            </TouchableOpacity>
          ) : !isRecording ? (
            <TouchableOpacity style={styles.recordButton} onPress={startRecording}>
              <Text style={styles.buttonText}>🎤 Start Recording</Text>
            </TouchableOpacity>
          ) : (
            <TouchableOpacity style={styles.stopButton} onPress={stopRecording}>
              <Text style={styles.buttonText}>⏹️ Stop Recording</Text>
            </TouchableOpacity>
          )}

          {analysis && (
            <View style={styles.resultsContainer}>
              <Text style={styles.score}>Score: {analysis.analysis.overall_score}/10 🎉</Text>
              <Text style={styles.encouragement}>{analysis.feedback.encouragement}</Text>
              
              <View style={styles.wordsContainer}>
                {analysis.analysis.word_analysis.map((word, index) => (
                  <TouchableOpacity
                    key={index}
                    style={[
                      styles.wordButton,
                      { backgroundColor: word.status === 'correct' ? '#90EE90' : '#FFB6C1' }
                    ]}
                    onPress={() => word.status === 'incorrect' && playPronunciation(word.expected)}
                  >
                    <Text style={styles.wordText}>{word.word}</Text>
                    {word.status === 'incorrect' && <Text>🔊</Text>}
                  </TouchableOpacity>
                ))}
              </View>
            </View>
          )}
        </>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: { padding: 20, backgroundColor: '#F8F9FA' },
  title: { fontSize: 24, fontWeight: 'bold', textAlign: 'center', marginBottom: 20 },
  readingText: { fontSize: 20, textAlign: 'center', marginBottom: 30, lineHeight: 30 },
  primaryButton: { backgroundColor: '#4CAF50', padding: 15, borderRadius: 10, marginBottom: 10 },
  recordButton: { backgroundColor: '#FF6B6B', padding: 15, borderRadius: 10, marginBottom: 10 },
  stopButton: { backgroundColor: '#FF4757', padding: 15, borderRadius: 10, marginBottom: 10 },
  buttonText: { color: 'white', fontSize: 18, textAlign: 'center', fontWeight: 'bold' },
  resultsContainer: { marginTop: 20 },
  score: { fontSize: 22, fontWeight: 'bold', textAlign: 'center', marginBottom: 10 },
  encouragement: { fontSize: 16, textAlign: 'center', marginBottom: 20, color: '#666' },
  wordsContainer: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center' },
  wordButton: { margin: 5, padding: 10, borderRadius: 5, minWidth: 60 },
  wordText: { fontSize: 16, textAlign: 'center' }
});

export default ReadingAssistant;
```

---

## 🎯 **Key Features to Implement**

### ✅ **Must-Have Features**
1. **Reading Content Display** - Show age-appropriate stories/sentences
2. **Audio Recording** - Record student reading attempts  
3. **Visual Feedback** - Color-coded words (green=correct, red=incorrect)
4. **Tap-to-Hear Pronunciation** - Tap red words to hear correct pronunciation
5. **Progress Tracking** - Show reading scores and improvement
6. **Encouraging Messages** - Positive feedback for young learners

### 🌟 **Nice-to-Have Features**  
1. **Reading Level Selection** - K, 1st, 2nd, 3rd grade content
2. **Voice Speed Control** - Slow/normal pronunciation speed
3. **Reading History** - Past attempts and scores
4. **Achievements/Badges** - Gamification elements
5. **Parent/Teacher Dashboard** - Progress monitoring

---

## 📊 **Testing & Validation**

### 🧪 **Test Scenarios**
1. **Happy Path**: Load content → Start session → Record audio → Get feedback → Tap pronunciation
2. **Error Handling**: No microphone permission, network failures, invalid audio
3. **Edge Cases**: Very quiet audio, background noise, mispronunciations
4. **Performance**: Large audio files, slow network, multiple sessions

### 📱 **Device Testing**
- Test on iOS and Android devices
- Various screen sizes (phones/tablets)
- Different audio quality (built-in mic vs headphones)
- Offline scenarios (cached content/device TTS fallback)

### 🔧 **Expo SDK Troubleshooting**
- **SDK Mismatch**: Use `npx expo upgrade` to update project
- **Development Build**: Use `expo-dev-client` for production apps
- **Version Compatibility**: Check expo.dev/versions for SDK compatibility

---

## 🎓 **User Experience Goals**

### 👶 **For Students (K-3)**
- **Simple, intuitive interface** - Minimal cognitive load
- **Immediate feedback** - See results right away
- **Encouraging tone** - Build confidence, not frustration  
- **Fun interactions** - Tap, hear, learn, repeat
- **Visual progress** - See improvement over time

### 👩‍🏫 **For Teachers**
- **Easy setup** - Assign reading content quickly
- **Progress monitoring** - Track student improvement
- **Classroom management** - Handle multiple students
- **Content customization** - Add custom reading materials

---

## 🚀 **Implementation Priority**

### **Phase 1: MVP (Week 1-2)**
1. Content loading and display
2. Audio recording functionality  
3. Basic analysis results display
4. Tap-to-hear pronunciation

### **Phase 2: Enhancement (Week 3-4)**  
1. Progress tracking
2. Multiple reading levels
3. Enhanced UI/animations
4. Error handling & edge cases

### **Phase 3: Advanced (Week 5+)**
1. Teacher dashboard
2. Custom content creation
3. Offline mode
4. Advanced analytics

---

## � **Mobile App Setup Guide**

### 📱 **Quick Start for Reading Assistant Mobile App**

#### **Step 1: Initialize Expo Project**
```bash
# Create new Expo project
npx create-expo-app ReadingAssistant
cd ReadingAssistant

# Install required dependencies
npx expo install expo-av expo-file-system expo-permissions
npm install @react-native-async-storage/async-storage
```

#### **Step 2: Fix SDK Compatibility**
```bash
# Check current SDK version
npx expo --version

# Upgrade to latest SDK (54)
npx expo upgrade

# Fix any dependency issues
npx expo install --fix
```

#### **Step 3: Configure Audio Permissions**
Add to `app.json`:
```json
{
  "expo": {
    "name": "Reading Assistant",
    "version": "1.0.0",
    "permissions": [
      "RECORD_AUDIO",
      "MICROPHONE"
    ],
    "android": {
      "permissions": [
        "android.permission.RECORD_AUDIO"
      ]
    },
    "ios": {
      "infoPlist": {
        "NSMicrophoneUsageDescription": "This app needs microphone access to help students practice reading pronunciation."
      }
    }
  }
}
```

#### **Step 4: Alternative Development Options**

**Option A: Use Expo Development Build** (Recommended for production)
```bash
# Install development build
npx expo install expo-dev-client

# Build for your device
npx expo run:android  # For Android
npx expo run:ios      # For iOS (requires Xcode)
```

**Option B: Use Web Version for Testing**
```bash
# Test in browser first
npx expo start --web
```

**Option C: Use Standalone React Native**
```bash
# Create pure React Native project
npx react-native init ReadingAssistantRN
cd ReadingAssistantRN

# Install audio packages
npm install react-native-audio-recorder-player
npm install @react-native-voice/voice
```

### 📱 **Updated React Native Code (SDK 54 Compatible)**

```jsx
import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, Alert, StyleSheet, Platform } from 'react-native';
import { Audio } from 'expo-av';
import * as FileSystem from 'expo-file-system';

const ReadingAssistant = ({ studentId, jwtToken }) => {
  const [content, setContent] = useState(null);
  const [session, setSession] = useState(null);
  const [recording, setRecording] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [isRecording, setIsRecording] = useState(false);
  const [permissionResponse, requestPermission] = Audio.usePermissions();

  // Configure audio mode for recording
  useEffect(() => {
    configureAudio();
    loadContent();
  }, []);

  const configureAudio = async () => {
    try {
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });
    } catch (error) {
      console.error('Failed to configure audio:', error);
    }
  };

  const loadContent = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/after-school/reading-assistant/content?grade_level=K&limit=1`, {
        headers: { 'Authorization': `Bearer ${jwtToken}` }
      });
      const data = await response.json();
      if (data.success) setContent(data.content[0]);
    } catch (error) {
      Alert.alert('Error', 'Failed to load content');
    }
  };

  const startReadingSession = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/after-school/reading-assistant/sessions/start`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${jwtToken}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ student_id: studentId, content_id: content.id })
      });
      const sessionData = await response.json();
      setSession(sessionData.session);
    } catch (error) {
      Alert.alert('Error', 'Failed to start session');
    }
  };

  const startRecording = async () => {
    try {
      // Request permission if needed
      if (!permissionResponse?.granted) {
        const permission = await requestPermission();
        if (!permission.granted) {
          Alert.alert('Permission Required', 'Please allow microphone access to record reading.');
          return;
        }
      }

      // Start recording with proper settings for SDK 54
      const { recording } = await Audio.Recording.createAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY
      );
      
      setRecording(recording);
      setIsRecording(true);
    } catch (error) {
      Alert.alert('Error', `Failed to start recording: ${error.message}`);
    }
  };

  const stopRecording = async () => {
    try {
      if (!recording) return;

      await recording.stopAndUnloadAsync();
      const uri = recording.getURI();
      setIsRecording(false);
      setRecording(null);
      
      // Analyze the recording
      if (uri) {
        await analyzeAudio(uri);
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to stop recording');
    }
  };

  const analyzeAudio = async (audioUri) => {
    try {
      const formData = new FormData();
      
      // For SDK 54 compatibility
      const audioFile = {
        uri: audioUri,
        type: 'audio/wav',
        name: 'reading.wav',
      };
      
      formData.append('audio_file', audioFile);
      formData.append('session_id', session.id);
      formData.append('content_id', content.id);
      formData.append('attempt_number', '1');

      const response = await fetch(`${API_BASE_URL}/after-school/reading-assistant/audio/upload`, {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${jwtToken}`,
          'Content-Type': 'multipart/form-data'
        },
        body: formData,
      });

      const result = await response.json();
      setAnalysis(result);
    } catch (error) {
      Alert.alert('Error', 'Failed to analyze audio');
    }
  };

  const playPronunciation = async (word) => {
    try {
      const response = await fetch(`${API_BASE_URL}/after-school/reading-assistant/pronunciation/word`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${jwtToken}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ word, speed: "slow" })
      });

      const result = await response.json();
      if (result.success && result.audio_url) {
        const { sound } = await Audio.Sound.createAsync(
          { uri: `${API_BASE_URL}${result.audio_url}` },
          { shouldPlay: true }
        );
        
        // Cleanup sound after playing
        sound.setOnPlaybackStatusUpdate((status) => {
          if (status.didJustFinish) {
            sound.unloadAsync();
          }
        });
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to play pronunciation');
    }
  };

  return (
    <View style={styles.container}>
      {content && (
        <>
          <Text style={styles.title}>{content.title}</Text>
          <Text style={styles.readingText}>{content.content}</Text>

          {!session ? (
            <TouchableOpacity style={styles.primaryButton} onPress={startReadingSession}>
              <Text style={styles.buttonText}>📚 Start Reading</Text>
            </TouchableOpacity>
          ) : !isRecording ? (
            <TouchableOpacity style={styles.recordButton} onPress={startRecording}>
              <Text style={styles.buttonText}>🎤 Start Recording</Text>
            </TouchableOpacity>
          ) : (
            <TouchableOpacity style={styles.stopButton} onPress={stopRecording}>
              <Text style={styles.buttonText}>⏹️ Stop Recording</Text>
            </TouchableOpacity>
          )}

          {analysis && analysis.success && (
            <View style={styles.resultsContainer}>
              <Text style={styles.score}>
                Score: {analysis.analysis?.overall_score || 0}/10 🎉
              </Text>
              <Text style={styles.encouragement}>
                {analysis.feedback?.encouragement || 'Great job!'}
              </Text>
              
              <View style={styles.wordsContainer}>
                {(analysis.analysis?.word_analysis || []).map((wordData, index) => (
                  <TouchableOpacity
                    key={index}
                    style={[
                      styles.wordButton,
                      { 
                        backgroundColor: wordData.status === 'correct' ? '#90EE90' : '#FFB6C1' 
                      }
                    ]}
                    onPress={() => 
                      wordData.status === 'incorrect' && playPronunciation(wordData.expected || wordData.word)
                    }
                  >
                    <Text style={styles.wordText}>{wordData.word}</Text>
                    {wordData.status === 'incorrect' && <Text>🔊</Text>}
                  </TouchableOpacity>
                ))}
              </View>
            </View>
          )}
        </>
      )}
    </View>
  );
};

// Configuration constants
const API_BASE_URL = 'http://localhost:8000'; // Change to your server URL

const styles = StyleSheet.create({
  container: { 
    flex: 1, 
    padding: 20, 
    backgroundColor: '#F8F9FA' 
  },
  title: { 
    fontSize: 24, 
    fontWeight: 'bold', 
    textAlign: 'center', 
    marginBottom: 20 
  },
  readingText: { 
    fontSize: 20, 
    textAlign: 'center', 
    marginBottom: 30, 
    lineHeight: 30,
    fontFamily: Platform.OS === 'ios' ? 'Helvetica' : 'Roboto'
  },
  primaryButton: { 
    backgroundColor: '#4CAF50', 
    padding: 15, 
    borderRadius: 10, 
    marginBottom: 10 
  },
  recordButton: { 
    backgroundColor: '#FF6B6B', 
    padding: 15, 
    borderRadius: 10, 
    marginBottom: 10 
  },
  stopButton: { 
    backgroundColor: '#FF4757', 
    padding: 15, 
    borderRadius: 10, 
    marginBottom: 10 
  },
  buttonText: { 
    color: 'white', 
    fontSize: 18, 
    textAlign: 'center', 
    fontWeight: 'bold' 
  },
  resultsContainer: { 
    marginTop: 20 
  },
  score: { 
    fontSize: 22, 
    fontWeight: 'bold', 
    textAlign: 'center', 
    marginBottom: 10 
  },
  encouragement: { 
    fontSize: 16, 
    textAlign: 'center', 
    marginBottom: 20, 
    color: '#666' 
  },
  wordsContainer: { 
    flexDirection: 'row', 
    flexWrap: 'wrap', 
    justifyContent: 'center' 
  },
  wordButton: { 
    margin: 5, 
    padding: 10, 
    borderRadius: 5, 
    minWidth: 60,
    alignItems: 'center'
  },
  wordText: { 
    fontSize: 16, 
    textAlign: 'center' 
  }
});

export default ReadingAssistant;
```

---

## �🔧 **Technical Notes**

- **Audio Format**: WAV files, 16kHz sample rate recommended
- **Network**: Handle slow connections gracefully  
- **Permissions**: Request microphone access properly (updated for SDK 54)
- **Caching**: Cache TTS audio for offline replay
- **Performance**: Optimize for older devices
- **Accessibility**: Support screen readers, large text
- **SDK Compatibility**: Always use `npx expo install` instead of `npm install` for Expo packages

---

## 📋 **Deliverables**

1. **UI/UX Designs** - Figma/Sketch mockups
2. **Working Prototype** - Basic functionality  
3. **API Integration** - All endpoints connected
4. **Testing Plan** - Comprehensive test cases
5. **Documentation** - Setup and usage guides

---

## 🎯 **COMPLETE API ENDPOINTS REFERENCE**

### 📚 **Content Management**
| Endpoint | Method | Purpose |
|----------|---------|---------|
| `/after-school/reading-assistant/content` | GET | Get reading materials by grade level |
| `/after-school/reading-assistant/content` | POST | Create custom reading content |
| `/after-school/reading-assistant/content/generate` | POST | AI-generate reading content |
| `/after-school/reading-assistant/content/{content_id}` | GET | Get specific content by ID |

### 🎤 **Session Management** 
| Endpoint | Method | Purpose |
|----------|---------|---------|
| `/after-school/reading-assistant/sessions/start` | POST | **Start reading session** |
| `/after-school/reading-assistant/sessions/{session_id}/complete` | POST | Complete reading session |
| `/after-school/reading-assistant/audio/upload` | POST | **🎯 MAIN FEATURE - Analyze reading audio** |

### 🔊 **Pronunciation Features (TTS)**
| Endpoint | Method | Purpose |
|----------|---------|---------|
| `/after-school/reading-assistant/pronunciation/word` | POST | **🎯 Get word pronunciation audio** |
| `/after-school/reading-assistant/pronunciation/sentence` | POST | Get sentence pronunciation audio |
| `/after-school/reading-assistant/pronunciation/feedback-words` | POST | Get pronunciation for multiple words |
| `/after-school/reading-assistant/pronunciation-audio/{filename}` | GET | **Serve pronunciation audio files** |

### 📊 **Progress & Analytics**
| Endpoint | Method | Purpose |
|----------|---------|---------|
| `/after-school/reading-assistant/progress` | GET | Get student reading progress |
| `/after-school/reading-assistant/dashboard` | GET | Get comprehensive student dashboard |
| `/after-school/reading-assistant/goals` | GET | Get reading goals |
| `/after-school/reading-assistant/goals` | POST | Create reading goals |
| `/after-school/reading-assistant/recommendations` | GET | Get recommended content |

### 🔧 **Utility Endpoints**
| Endpoint | Method | Purpose |
|----------|---------|---------|
| `/after-school/reading-assistant/health` | GET | Health check endpoint |
| `/after-school/reading-assistant/debug-ai` | POST | Debug AI responses (development only) |

---

## 🎯 **CORE MOBILE APP ENDPOINTS**

For mobile app implementation, focus on these **essential endpoints**:

### 1️⃣ **Load Content**
```javascript
GET /after-school/reading-assistant/content?grade_level=K&limit=10
```

### 2️⃣ **Start Session** 
```javascript
POST /after-school/reading-assistant/sessions/start
Body: { "student_id": 123, "content_id": 1 }
```

### 3️⃣ **Analyze Reading** ⭐ **MAIN FEATURE**
```javascript
POST /after-school/reading-assistant/audio/upload
Body: FormData with audio_file, session_id, expected_text
```

### 4️⃣ **Get Pronunciation** ⭐ **TTS FEATURE** 
```javascript
POST /after-school/reading-assistant/pronunciation/word
Body: { "word": "cat", "speed": "slow" }
```

### 5️⃣ **Track Progress**
```javascript
GET /after-school/reading-assistant/progress?student_id=123
```

---

## 🔗 **Additional Helper Endpoints**

### **Get Sentence Pronunciation**
```javascript
POST /after-school/reading-assistant/pronunciation/sentence
Body: { "sentence": "The big cat runs fast", "speed": "slow", "pause_between_words": true }
```

### **Get Multiple Word Pronunciations**
```javascript
POST /after-school/reading-assistant/pronunciation/feedback-words  
Body: { "words": ["cat", "fast", "big"], "speed": "slow" }
```

### **Student Dashboard Data**
```javascript
GET /after-school/reading-assistant/dashboard?student_id=123
// Returns comprehensive progress, achievements, recent sessions
```

### **Get Recommendations**
```javascript
GET /after-school/reading-assistant/recommendations?student_id=123&limit=5
// Returns recommended reading content based on student level
```

---

---

## 🔧 **Common Issues & Solutions**

### ❌ **Expo SDK Version Conflicts**

**Problem**: "Project is incompatible with this version of Expo Go"

**Solutions**:
```bash
# Solution 1: Upgrade project to match Expo Go
npx expo upgrade

# Solution 2: Use development build (recommended)
npx expo install expo-dev-client
npx expo run:android

# Solution 3: Use web version for testing
npx expo start --web
```

### ❌ **Audio Recording Issues**

**Problem**: Recording fails or no audio captured

**Solutions**:
```jsx
// Check permissions first
const [permissionResponse, requestPermission] = Audio.usePermissions();

// Configure audio mode properly
await Audio.setAudioModeAsync({
  allowsRecordingIOS: true,
  playsInSilentModeIOS: true,
});

// Use correct recording options for SDK 54
const { recording } = await Audio.Recording.createAsync(
  Audio.RecordingOptionsPresets.HIGH_QUALITY
);
```

### ❌ **Network Connection Issues**

**Problem**: API calls failing

**Solutions**:
```jsx
// Use correct server URL
const API_BASE_URL = __DEV__ 
  ? 'http://localhost:8000'  // Development
  : 'https://your-server.com';  // Production

// Add proper error handling
try {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }
  const data = await response.json();
} catch (error) {
  Alert.alert('Connection Error', 'Please check your internet connection');
}
```

### 🚀 **Quick Deployment Options**

**For Testing:**
- Use Expo Go with compatible SDK version
- Use web version: `npx expo start --web`
- Use Expo Development Build

**For Production:**
- Build standalone app: `npx expo build`
- Use EAS Build: `npx eas build`
- Export for manual deployment: `npx expo export`

---

**This reading assistant will help K-3 students improve their reading skills through AI-powered feedback and interactive pronunciation help! 🎓📚✨**

**ALL 18 ENDPOINTS ARE DOCUMENTED ABOVE FOR COMPLETE INTEGRATION** 🚀

### 📱 **Next Steps:**
1. ✅ Backend is fully functional and tested
2. � Choose your mobile development approach (Expo/React Native)
3. 📱 Follow the setup guide above to resolve SDK compatibility
4. 🎯 Implement the core features using the provided code examples
5. �🚀 Deploy and start helping K-3 students learn to read!