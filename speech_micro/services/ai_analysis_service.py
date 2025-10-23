import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

# Import Gemini service for AI analysis
from services.gemini_service import GeminiService

class MeetingType(str, Enum):
    DEBATE = "debate"
    MEETING = "meeting"
    DISCUSSION = "discussion"

@dataclass
class Speaker:
    id: str
    name: str
    role: str = "participant"
    speaking_time: float = 0.0
    word_count: int = 0
    argument_points: List[str] = None
    
    def __post_init__(self):
        if self.argument_points is None:
            self.argument_points = []

@dataclass
class TranscriptionSegment:
    speaker_id: str
    text: str
    timestamp: datetime
    confidence: float
    duration: float
    segment_number: int

@dataclass
class DebateAnalysis:
    overall_summary: str
    key_arguments: Dict[str, List[str]]  # speaker_id -> arguments
    argument_strength: Dict[str, float]  # speaker_id -> strength score
    speaking_time_analysis: Dict[str, float]  # speaker_id -> speaking time
    debate_flow: List[str]  # Chronological flow of arguments
    winner_analysis: Optional[str] = None  # For debates
    improvement_suggestions: Dict[str, List[str]] = None  # speaker_id -> suggestions
    
    def __post_init__(self):
        if self.improvement_suggestions is None:
            self.improvement_suggestions = {}

class AIAnalysisService:
    def __init__(self):
        self.gemini_service = GeminiService()
        
    async def analyze_session(
        self, 
        session_id: str,
        segments: List[Dict],
        meeting_type: MeetingType = MeetingType.DISCUSSION,
        speakers: List[Speaker] = None,
        session_full_text: str = None
    ) -> DebateAnalysis:
        """
        Analyze a complete transcription session for debate/meeting insights
        """
        
        # Use session_full_text if provided, otherwise combine segments
        if session_full_text and session_full_text.strip():
            full_text = session_full_text.strip()
            print(f"Using provided session_full_text: '{full_text[:100]}...'")
        else:
            # Combine all transcription text from segments
            full_text = self._combine_segments(segments)
            print(f"Combined segments into full_text: '{full_text[:100]}...'")
        
        if not full_text.strip():
            return DebateAnalysis(
                overall_summary="No meaningful content detected",
                key_arguments={},
                argument_strength={},
                speaking_time_analysis={},
                debate_flow=[]
            )
        
        # Default speakers if none provided
        if not speakers:
            speakers = [Speaker(id="speaker_1", name="Participant 1")]
        
        # Create analysis prompt based on meeting type
        if meeting_type == MeetingType.DEBATE:
            analysis = await self._analyze_debate(full_text, speakers)
        elif meeting_type == MeetingType.MEETING:
            analysis = await self._analyze_meeting(full_text, speakers)
        else:
            analysis = await self._analyze_discussion(full_text, speakers)
        
        return analysis
    
    def _combine_segments(self, segments: List[Dict]) -> str:
        """Combine all transcription segments into one text"""
        combined_text = ""
        for segment in segments:
            if segment.get("text"):
                combined_text += segment["text"] + " "
        return combined_text.strip()
    
    async def _analyze_debate(self, text: str, speakers: List[Speaker]) -> DebateAnalysis:
        """Analyze text specifically for debate format"""
        
        # Detect if this is actually a multi-speaker debate or single speaker
        speaker_count = len(speakers)
        actual_speakers = self._detect_actual_speakers_in_text(text, speakers)
        
        if len(actual_speakers) <= 1:
            # Handle single speaker scenario
            debate_prompt = f"""
            Analyze the following single-speaker transcript as if it contains multiple viewpoints or arguments:

            TRANSCRIPT:
            {text}

            SPEAKER: {speakers[0].name if speakers else "Speaker"}

            Since this appears to be a single speaker, analyze the different arguments, viewpoints, or positions they present. Treat different topics or opposing viewpoints mentioned as separate "sides" to evaluate.

            Provide analysis in JSON format:
            {{
                "overall_summary": "Summary of the main topics and arguments presented",
                "key_arguments": {{
                    "{speakers[0].id if speakers else 'speaker_1'}": ["main argument 1", "main argument 2", "main argument 3"]
                }},
                "argument_strength": {{
                    "{speakers[0].id if speakers else 'speaker_1'}": 0.80
                }},
                "debate_flow": ["First topic/argument", "Second topic/argument", "Conclusion"],
                "winner_analysis": "Since this is a single speaker, evaluate the overall effectiveness of their presentation: (1) Clarity and organization of thoughts, (2) Logical flow of arguments, (3) Use of evidence and examples, (4) Persuasive delivery, (5) Coverage of different viewpoints. Assess whether they presented a compelling case and addressed potential counterarguments effectively. Rate their overall performance and communication effectiveness.",
                "improvement_suggestions": {{
                    "{speakers[0].id if speakers else 'speaker_1'}": ["suggestion 1", "suggestion 2", "suggestion 3"]
                }}
            }}
            """
        else:
            # Multi-speaker debate analysis
            debate_prompt = f"""
            Analyze the following debate transcript as an expert debate judge. Provide detailed analysis:

            DEBATE TRANSCRIPT:
            {text}

            SPEAKERS: {[f"{s.name} (ID: {s.id})" for s in speakers]}

            Please provide analysis in the following JSON format:
            {{
                "overall_summary": "Brief summary of the debate topic and outcome",
                "key_arguments": {{
                    {', '.join([f'"{s.id}": ["argument 1", "argument 2", ...]' for s in actual_speakers])}
                }},
                "argument_strength": {{
                    {', '.join([f'"{s.id}": 0.85' for s in actual_speakers])}
                }},
                "debate_flow": ["Opening statement by X", "Counter-argument by Y", ...],
                "winner_analysis": "Comprehensive analysis comparing all speakers. Evaluate each speaker's performance based on: (1) Strength and logical consistency of arguments, (2) Quality of evidence and examples provided, (3) Rhetorical effectiveness and presentation skills, (4) Ability to address opposing viewpoints, (5) Overall persuasiveness and conviction. Provide a clear determination of who performed best and why, including specific examples from their arguments. DECLARE A CLEAR WINNER with specific reasoning.",
                "improvement_suggestions": {{
                    {', '.join([f'"{s.id}": ["suggestion 1", "suggestion 2"]' for s in actual_speakers])}
                }}
            }}

            IMPORTANT: For winner_analysis, provide a detailed comparative analysis that:
            - Compares each speaker's strongest arguments
            - Identifies who provided better evidence/examples
            - Evaluates rhetorical skills and presentation
            - Determines who was more persuasive overall
            - Declares a clear winner with specific reasoning
            - If it's very close, explain what tipped the balance
            """
        
        try:
            # Get AI analysis
            response = self.gemini_service.generate_content(debate_prompt)
            
            # Parse JSON response
            analysis_data = self._parse_ai_response(response)
            
            # Calculate speaking time (estimate based on word count)
            speaking_time = self._estimate_speaking_time(text, speakers)
            
            return DebateAnalysis(
                overall_summary=analysis_data.get("overall_summary", "Analysis not available"),
                key_arguments=analysis_data.get("key_arguments", {}),
                argument_strength=analysis_data.get("argument_strength", {}),
                speaking_time_analysis=speaking_time,
                debate_flow=analysis_data.get("debate_flow", []),
                winner_analysis=analysis_data.get("winner_analysis"),
                improvement_suggestions=analysis_data.get("improvement_suggestions", {})
            )
            
        except Exception as e:
            print(f"Error in debate analysis: {e}")
            return self._create_fallback_analysis(text, speakers, MeetingType.DEBATE)
    
    async def _analyze_meeting(self, text: str, speakers: List[Speaker]) -> DebateAnalysis:
        """Analyze text for meeting format"""
        
        meeting_prompt = f"""
        Analyze the following meeting transcript as an expert meeting facilitator:

        MEETING TRANSCRIPT:
        {text}

        SPEAKERS: {[f"{s.name} (ID: {s.id})" for s in speakers]}

        Provide analysis in JSON format:
        {{
            "overall_summary": "Summary of meeting topics and decisions",
            "key_arguments": {{
                "speaker_1": ["key point 1", "key point 2"],
                "speaker_2": ["key point 1", "key point 2"]
            }},
            "argument_strength": {{
                "speaker_1": 0.80,
                "speaker_2": 0.75
            }},
            "debate_flow": ["Agenda item 1 discussed", "Decision made on X", ...],
            "improvement_suggestions": {{
                "speaker_1": ["More specific examples needed", "Clarify timeline"],
                "speaker_2": ["Provide data to support claims"]
            }}
        }}

        Focus on:
        1. Clarity of communication
        2. Contribution to meeting objectives
        3. Collaborative effectiveness
        4. Action items and decisions
        """
        
        try:
            response = self.gemini_service.generate_content(meeting_prompt)
            analysis_data = self._parse_ai_response(response)
            speaking_time = self._estimate_speaking_time(text, speakers)
            
            return DebateAnalysis(
                overall_summary=analysis_data.get("overall_summary", "Meeting analysis not available"),
                key_arguments=analysis_data.get("key_arguments", {}),
                argument_strength=analysis_data.get("argument_strength", {}),
                speaking_time_analysis=speaking_time,
                debate_flow=analysis_data.get("debate_flow", []),
                improvement_suggestions=analysis_data.get("improvement_suggestions", {})
            )
            
        except Exception as e:
            print(f"Error in meeting analysis: {e}")
            return self._create_fallback_analysis(text, speakers, MeetingType.MEETING)
    
    async def _analyze_discussion(self, text: str, speakers: List[Speaker]) -> DebateAnalysis:
        """Analyze text for general discussion"""
        
        discussion_prompt = f"""
        Analyze the following discussion transcript as an expert conversation analyst:

        DISCUSSION TRANSCRIPT:
        {text}

        SPEAKERS: {[f"{s.name} (ID: {s.id})" for s in speakers]}

        Provide analysis in JSON format:
        {{
            "overall_summary": "Summary of the discussion topics and key insights",
            "key_arguments": {{
                "speaker_1": ["key point 1", "key point 2"],
                "speaker_2": ["key point 1", "key point 2"]
            }},
            "argument_strength": {{
                "speaker_1": 0.80,
                "speaker_2": 0.75
            }},
            "debate_flow": ["Discussion point 1", "Follow-up by X", "Clarification by Y", ...],
            "winner_analysis": "If there are multiple speakers, analyze who made the most valuable contributions to the discussion. Consider: (1) Quality and originality of ideas presented, (2) Clarity of communication, (3) Ability to build on others' ideas, (4) Practical insights and solutions offered, (5) Overall contribution to moving the discussion forward. If it's a single speaker or purely informational, note that no competitive analysis is applicable.",
            "improvement_suggestions": {{
                "speaker_1": ["suggestion 1", "suggestion 2"],
                "speaker_2": ["suggestion 1", "suggestion 2"]
            }}
        }}

        Focus on:
        1. Main topics covered
        2. Individual contributions and insights
        3. Communication effectiveness and clarity
        4. Collaborative vs competitive elements
        5. Areas for improvement
        6. Overall value of contributions
        """
        
        try:
            response = self.gemini_service.generate_content(discussion_prompt)
            analysis_data = self._parse_ai_response(response)
            speaking_time = self._estimate_speaking_time(text, speakers)
            
            return DebateAnalysis(
                overall_summary=analysis_data.get("overall_summary", "Discussion analysis not available"),
                key_arguments=analysis_data.get("key_arguments", {}),
                argument_strength=analysis_data.get("argument_strength", {}),
                speaking_time_analysis=speaking_time,
                debate_flow=analysis_data.get("debate_flow", []),
                winner_analysis=analysis_data.get("winner_analysis"),
                improvement_suggestions=analysis_data.get("improvement_suggestions", {})
            )
            
        except Exception as e:
            print(f"Error in discussion analysis: {e}")
            return self._create_fallback_analysis(text, speakers, MeetingType.DISCUSSION)
    
    def _parse_ai_response(self, response: str) -> Dict:
        """Parse AI response, handling various formats"""
        try:
            # Try to find JSON in the response
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx != -1 and end_idx != 0:
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)
            else:
                # Fallback: create basic structure
                return {
                    "overall_summary": response[:200] + "..." if len(response) > 200 else response,
                    "key_arguments": {},
                    "argument_strength": {},
                    "debate_flow": [],
                    "improvement_suggestions": {}
                }
                
        except json.JSONDecodeError:
            print("Failed to parse AI response as JSON")
            return {
                "overall_summary": "AI analysis parsing failed",
                "key_arguments": {},
                "argument_strength": {},
                "debate_flow": [],
                "improvement_suggestions": {}
            }
    
    def _estimate_speaking_time(self, text: str, speakers: List[Speaker]) -> Dict[str, float]:
        """Estimate speaking time based on word count (rough estimate)"""
        total_words = len(text.split())
        words_per_minute = 150  # Average speaking rate
        total_time = total_words / words_per_minute
        
        # For now, distribute equally among speakers
        # In a real implementation, you'd use speaker diarization
        speaking_time = {}
        if speakers:
            time_per_speaker = total_time / len(speakers)
            for speaker in speakers:
                speaking_time[speaker.id] = round(time_per_speaker, 2)
        
        return speaking_time
    
    def _create_fallback_analysis(self, text: str, speakers: List[Speaker], meeting_type: MeetingType) -> DebateAnalysis:
        """Create basic analysis when AI analysis fails"""
        word_count = len(text.split())
        speaking_time = self._estimate_speaking_time(text, speakers)
        
        return DebateAnalysis(
            overall_summary=f"Analysis of {meeting_type.value} with {word_count} words total. AI analysis unavailable.",
            key_arguments={speaker.id: [f"Participated in {meeting_type.value}"] for speaker in speakers},
            argument_strength={speaker.id: 0.5 for speaker in speakers},
            speaking_time_analysis=speaking_time,
            debate_flow=[f"{meeting_type.value.title()} took place with multiple participants"],
            improvement_suggestions={speaker.id: ["Detailed analysis unavailable"] for speaker in speakers}
        )

    async def create_ai_user_summary(self, analysis: DebateAnalysis, meeting_type: MeetingType) -> Dict[str, Any]:
        """
        Create a summary as if from an AI participant that was observing the meeting/debate
        """
        
        ai_summary_prompt = f"""
        You are an AI assistant that was observing a {meeting_type.value}. Based on the following analysis, 
        create a comprehensive summary as if you were a participant taking notes:

        ANALYSIS DATA:
        - Summary: {analysis.overall_summary}
        - Key Arguments: {analysis.key_arguments}
        - Speaking Time: {analysis.speaking_time_analysis}
        - Debate Flow: {analysis.debate_flow}
        - Winner Analysis: {analysis.winner_analysis}
        - Improvement Suggestions: {analysis.improvement_suggestions}

        Create a response in JSON format:
        {{
            "ai_observation": "Overall observation as an AI participant",
            "key_takeaways": ["takeaway 1", "takeaway 2", ...],
            "speaker_performance": {{
                "speaker_id": {{
                    "strengths": ["strength 1", "strength 2"],
                    "areas_for_improvement": ["improvement 1", "improvement 2"],
                    "score": 8.5
                }}
            }},
            "meeting_effectiveness": 8.0,
            "recommendations": ["recommendation 1", "recommendation 2"]
        }}
        """
        
        try:
            response = self.gemini_service.generate_content(ai_summary_prompt)
            ai_data = self._parse_ai_response(response)
            
            return {
                "ai_user_id": "ai_observer",
                "ai_name": "AI Meeting Assistant",
                "timestamp": datetime.utcnow().isoformat(),
                "meeting_type": meeting_type.value,
                "analysis": ai_data
            }
            
        except Exception as e:
            print(f"Error creating AI summary: {e}")
            return {
                "ai_user_id": "ai_observer", 
                "ai_name": "AI Meeting Assistant",
                "timestamp": datetime.utcnow().isoformat(),
                "meeting_type": meeting_type.value,
                "analysis": {
                    "ai_observation": "AI analysis temporarily unavailable",
                    "key_takeaways": ["Meeting analysis pending"],
                    "speaker_performance": {},
                    "meeting_effectiveness": 5.0,
                    "recommendations": ["Detailed analysis will be available shortly"]
                }
            }
    
    def _detect_actual_speakers_in_text(self, text: str, speakers: List[Speaker]) -> List[Speaker]:
        """Detect which speakers are actually present in the text"""
        if not text or not speakers:
            return speakers[:1] if speakers else []
        
        text_lower = text.lower()
        active_speakers = []
        
        # For now, we'll assume if we have multiple speakers configured
        # and the text has certain patterns, it's multi-speaker
        speaker_indicators = [
            "speaker a", "speaker b", "speaker 1", "speaker 2",
            "john", "jane", "first speaker", "second speaker",
            "on one side", "on the other hand", "counterpoint",
            "my opponent", "the other person", "they argue"
        ]
        
        # Check if text contains multiple speaker patterns
        found_indicators = sum(1 for indicator in speaker_indicators if indicator in text_lower)
        
        if found_indicators >= 2 and len(speakers) >= 2:
            return speakers
        else:
            return speakers[:1] if speakers else []
