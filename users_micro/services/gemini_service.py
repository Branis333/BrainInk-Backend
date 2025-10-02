import os
import json
import asyncio
import tempfile
import mimetypes
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import re
import google.generativeai as genai
from pydantic import BaseModel
import httpx
from urllib.parse import quote_plus, urlencode

# Configuration for Gemini API
class GeminiConfig:
    def __init__(self):
        # Try GEMINI_API_KEY first, then fall back to GOOGLE_API_KEY
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY environment variable not set")

        # Prefer Gemini 2.5 Flash by default; allow override via GEMINI_MODEL
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-latest")
        # Allow opting into paid models explicitly; default to free-only
        self.allow_paid = os.getenv("ALLOW_PAID_MODELS", "false").lower() in ("1", "true", "yes")

        print(f"🔑 Configuring Gemini AI with API key: {self.api_key[:10]}...{self.api_key[-4:]}")
        print(f"🤖 Requested model: {self.model_name} | allow_paid={self.allow_paid}")
        genai.configure(api_key=self.api_key)

        # Choose a supported model (respecting free-only unless ALLOW_PAID_MODELS=true)
        chosen = self._choose_supported_model(preferred_first=self.model_name)
        if chosen != self.model_name:
            print(f"🔁 Using fallback model: {chosen}")
        self.model_name = chosen
        self.model = genai.GenerativeModel(self.model_name)

    def _choose_supported_model(self, preferred_first: Optional[str] = None) -> str:
        """Pick a supported model that can handle generateContent (multimodal if possible).
        Enforce free-only models unless ALLOW_PAID_MODELS=true.
        Free-preferred order:
          1) preferred_first (if allowed by policy)
          2) gemini-2.5-flash-latest, gemini-2.5-flash
          3) gemini-2.0-flash-latest, gemini-2.0-flash
          4) gemini-1.5-flash-latest, gemini-1.5-flash, gemini-1.5-flash-8b
        If paid models are allowed, extend with:
          - gemini-1.5-pro-latest, gemini-1.0-pro-vision-latest, gemini-pro-vision
        If none are available, choose the first model that supports generateContent.
        """
        try:
            models = list(genai.list_models())
        except Exception as e:
            # As a last resort, return a commonly available default
            print(f"⚠️ list_models() failed: {e}; using default 'gemini-1.5-flash-latest'")
            return "gemini-1.5-flash-latest"

        def normalize(name: str) -> str:
            return name.replace("models/", "") if name else name

        def supports_generate(model_obj) -> bool:
            methods = getattr(model_obj, 'supported_generation_methods', None) or getattr(model_obj, 'generation_methods', None) or []
            # Prefer new API method name if present; otherwise accept any generate* method
            return any("generate" in str(m).lower() for m in methods)

        available = {normalize(getattr(m, 'name', '')): m for m in models if supports_generate(m)}

        # Define allowed sets
        free_allowed = {
            "gemini-2.5-flash-latest", "gemini-2.5-flash",
            "gemini-2.0-flash-latest", "gemini-2.0-flash",
            "gemini-1.5-flash-latest", "gemini-1.5-flash", "gemini-1.5-flash-8b",
        }
        paid_allowed = {"gemini-1.5-pro-latest", "gemini-1.0-pro-vision-latest", "gemini-pro-vision"}

        # Filter availability if paid models aren't allowed
        if not self.allow_paid:
            available = {k: v for k, v in available.items() if k in free_allowed}

        # Preferred order list
        preferred = [p for p in [
            preferred_first,
            os.getenv("GEMINI_MODEL"),
            "gemini-2.5-flash-latest", "gemini-2.5-flash",
            "gemini-2.0-flash-latest", "gemini-2.0-flash",
            "gemini-1.5-flash-latest", "gemini-1.5-flash", "gemini-1.5-flash-8b",
        ] if p]
        if self.allow_paid:
            preferred.extend(["gemini-1.5-pro-latest", "gemini-1.0-pro-vision-latest", "gemini-pro-vision"])

        for name in preferred:
            if name in available:
                return name
            # Also check for names missing the models/ prefix in the list
            if f"models/{name}" in (getattr(m, 'name', '') for m in models):
                return name

        # If none of our preferred are available, fall back to the first available
        if available:
            return next(iter(available.keys()))

        # Ultimate fallback
        return "gemini-1.5-flash-latest"

    @staticmethod
    def is_quota_error(exc: Exception) -> bool:
        text = str(exc).lower()
        return ("quota" in text) or ("429" in text) or ("rate limit" in text)

# Data structures for course generation
class CourseBlock(BaseModel):
    week: int
    block_number: int
    title: str
    description: str
    learning_objectives: List[str]
    content: str
    duration_minutes: int
    resources: List[Dict[str, str]]  # [{"type": "video", "title": "...", "url": "..."}]
    assignments: List[Dict[str, Any]]

class GeneratedCourse(BaseModel):
    title: str
    subject: str
    description: str
    age_min: int
    age_max: int
    difficulty_level: str
    total_weeks: int
    blocks_per_week: int
    textbook_source: str
    blocks: List[CourseBlock]
    overall_assignments: List[Dict[str, Any]]

class GeminiService:
    def __init__(self):
        self.config = GeminiConfig()
    
    def _safe_parse_json(self, text: str) -> Dict[str, Any]:
        """Parse JSON from Gemini response text robustly.
        - Strips ```json fences
        - Attempts direct json.loads
        - Falls back to slicing first {...} block
        Returns a dict or raises ValueError.
        """
        import json as _json
        if text is None:
            raise ValueError("Empty response text")
        t = text.strip()
        # Strip code fences if present
        if t.startswith("```json") and t.endswith("```"):
            t = t[7:-3].strip()
        elif t.startswith("```") and t.endswith("```"):
            t = t[3:-3].strip()
        # Try direct parse
        try:
            return _json.loads(t)
        except Exception:
            pass
        # Try to find the first JSON object substring
        start = t.find('{')
        end = t.rfind('}')
        if start != -1 and end != -1 and end > start:
            candidate = t[start:end+1]
            try:
                return _json.loads(candidate)
            except Exception:
                pass
        # As last resort, attempt to replace single quotes and parse
        try:
            return _json.loads(t.replace("'", '"'))
        except Exception as e:
            raise ValueError(f"Failed to parse JSON from response: {str(e)}")
        
    async def analyze_textbook_and_generate_course(
        self, 
        textbook_content: str, 
        course_title: str,
        subject: str,
        target_age_range: tuple,
        total_weeks: int,
        blocks_per_week: int,
        difficulty_level: str = "intermediate"
    ) -> GeneratedCourse:
        """
        Analyze textbook content and generate course progressively, block by block
        This prevents quota issues by processing one block at a time with delays
        """
        
        try:
            # Progressive block-by-block course generation
            print(f"🎯 Starting progressive course generation: {total_weeks} weeks × {blocks_per_week} blocks")
            
            # Step 1: Analyze textbook structure and create course outline
            course_outline = await self._analyze_textbook_structure(
                textbook_content, course_title, subject, target_age_range, 
                total_weeks, blocks_per_week, difficulty_level
            )
            
            print(f"📋 Course outline created: {course_outline['title']}")
            print(f"📚 Content sections identified: {len(course_outline.get('content_sections', []))}")
            
            # Step 2: Generate blocks progressively
            total_blocks = total_weeks * blocks_per_week
            generated_blocks = []
            
            print(f"🔄 Generating {total_blocks} blocks progressively...")
            
            for block_num in range(1, total_blocks + 1):
                week_num = ((block_num - 1) // blocks_per_week) + 1
                block_in_week = ((block_num - 1) % blocks_per_week) + 1
                
                print(f"⏳ Generating Block {block_num}/{total_blocks} (Week {week_num}, Block {block_in_week})")
                
                # Generate individual block
                block_data = await self._generate_single_block(
                    textbook_content, course_outline, week_num, block_in_week, 
                    block_num, total_blocks, subject, target_age_range, difficulty_level
                )
                
                generated_blocks.append(block_data)
                
                # Add delay between blocks to avoid rate limiting
                if block_num < total_blocks:
                    print(f"⏱️  Waiting 3 seconds before next block...")
                    await asyncio.sleep(3)
            
            print(f"✅ All {len(generated_blocks)} blocks generated successfully!")
            
            # Step 3: Generate overall course assignments
            print(f"📝 Generating overall course assignments...")
            overall_assignments = await self._generate_overall_assignments(
                course_outline, generated_blocks, total_weeks
            )
            
            # Step 4: Assemble final course data
            course_data = {
                "title": course_outline["title"],
                "subject": course_outline["subject"],
                "description": course_outline["description"],
                "age_min": course_outline["age_min"],
                "age_max": course_outline["age_max"],
                "difficulty_level": course_outline["difficulty_level"],
                "total_weeks": total_weeks,
                "blocks_per_week": blocks_per_week,
                "textbook_source": course_outline.get("textbook_source", "Uploaded textbook"),
                "blocks": generated_blocks,
                "overall_assignments": overall_assignments
            }
            
            print(f"🎉 Course generation complete: '{course_data['title']}'")
            return GeneratedCourse(**course_data)
            
        except Exception as e:
            raise Exception(f"Failed to generate course: {str(e)}")

    async def _analyze_textbook_structure(
        self, textbook_content: str, course_title: str, subject: str, 
        target_age_range: tuple, total_weeks: int, blocks_per_week: int, difficulty_level: str
    ) -> Dict[str, Any]:
        """
        Analyze textbook structure and create a course outline
        This is a lightweight analysis that doesn't consume many tokens
        """
        age_min, age_max = target_age_range
        
        # Check if textbook_content is a Gemini file URI
        if textbook_content.startswith("GEMINI_FILE_URI:"):
            gemini_file_uri = textbook_content.replace("GEMINI_FILE_URI:", "")
            uploaded_file = genai.get_file(gemini_file_uri)
            
            structure_prompt = f"""
            Analyze the uploaded textbook file and create a high-level course structure outline.
            
            **CRITICAL FILTERING INSTRUCTIONS:**
            - SKIP any "Table of Contents", "Course Outline", "Syllabus", or "Index" pages
            - SKIP any "Chapter Summary" or "Overview" sections
            - SKIP any "Learning Outcomes" or "Objectives" lists that appear before actual content
            - ONLY analyze the ACTUAL LESSON CONTENT pages (chapters, sections with substantive material)
            - Look for the main body text, explanations, examples, and educational content
            - Ignore preface, foreword, introduction pages, and appendices
            
            COURSE REQUIREMENTS:
            - Title: {course_title}
            - Subject: {subject}
            - Target Age: {age_min}-{age_max} years
            - Duration: {total_weeks} weeks ({blocks_per_week} blocks per week = {total_weeks * blocks_per_week} total blocks)
            - Difficulty: {difficulty_level}
            
            Create a JSON outline with this structure:
            {{
                "title": "{course_title}",
                "subject": "{subject}",
                "description": "Brief course description (1-2 sentences)",
                "age_min": {age_min},
                "age_max": {age_max},
                "difficulty_level": "{difficulty_level}",
                "textbook_source": "Brief description of the textbook",
                "content_sections": [
                    {{
                        "section_title": "Section 1 Title",
                        "topics": ["Topic 1", "Topic 2", "Topic 3"],
                        "estimated_blocks": 2,
                        "difficulty": "beginner|intermediate|advanced"
                    }},
                    {{
                        "section_title": "Section 2 Title", 
                        "topics": ["Topic 4", "Topic 5"],
                        "estimated_blocks": 3,
                        "difficulty": "intermediate"
                    }}
                ],
                "learning_progression": "How topics build upon each other",
                "key_concepts": ["Main concept 1", "Main concept 2", "Main concept 3"]
            }}
            
            INSTRUCTIONS:
            - Identify main sections/chapters in the textbook (CONTENT ONLY, not ToC)
            - Map content to the {total_weeks * blocks_per_week} blocks needed
            - Ensure logical progression through material
            - Keep response concise and focused on structure
            - Remember: EXTRACT FROM ACTUAL CONTENT, NOT FROM TABLE OF CONTENTS
            """
            
            response = await asyncio.to_thread(
                self.config.model.generate_content,
                [uploaded_file, structure_prompt],
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=512,  # Reduced for free tier
                    response_mime_type="application/json"
                )
            )
        else:
            # Handle direct text content - filter out ToC and outline sections
            # Try to detect and skip table of contents
            filtered_content = textbook_content
            
            # Simple filtering: skip content that looks like a table of contents
            toc_markers = [
                "table of contents", "contents", "course outline", "syllabus",
                "chapter 1.", "chapter 2.", "chapter 3.", "week 1", "week 2",
                "learning outcomes", "overview"
            ]
            
            lines = textbook_content.split('\n')
            content_start_idx = 0
            
            # Look for where actual content begins (after ToC/outline)
            for i, line in enumerate(lines[:100]):  # Check first 100 lines
                line_lower = line.lower().strip()
                # If we find dense paragraph text, assume content has started
                if len(line) > 100 and not any(marker in line_lower for marker in toc_markers):
                    content_start_idx = max(0, i - 5)  # Start a bit before
                    break
            
            if content_start_idx > 0:
                filtered_content = '\n'.join(lines[content_start_idx:])
                print(f"📝 Filtered out first {content_start_idx} lines (likely ToC/outline)")
            
            structure_prompt = f"""
            Analyze the following textbook content and create a high-level course structure outline.
            
            **CRITICAL FILTERING INSTRUCTIONS:**
            - This content may start with a Table of Contents or Course Outline - SKIP IT
            - Look for and analyze only the ACTUAL LESSON CONTENT
            - Ignore any chapter summaries or overview pages
            - Focus on substantive educational material
            
            TEXTBOOK CONTENT:
            {filtered_content[:2000]}...
            
            COURSE REQUIREMENTS:
            - Title: {course_title}
            - Subject: {subject}
            - Target Age: {age_min}-{age_max} years
            - Duration: {total_weeks} weeks ({blocks_per_week} blocks per week = {total_weeks * blocks_per_week} total blocks)
            - Difficulty: {difficulty_level}
            
            Create a JSON outline with the same structure as above.
            Remember: Extract structure from ACTUAL CONTENT, not from any table of contents.
            """
            
            response = await asyncio.to_thread(
                self.config.model.generate_content,
                structure_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=512,
                    response_mime_type="application/json"
                )
            )
        
        return json.loads(response.text)

    async def _generate_single_block(
        self, textbook_content: str, course_outline: Dict, week_num: int, 
        block_in_week: int, block_num: int, total_blocks: int, subject: str, 
        target_age_range: tuple, difficulty_level: str
    ) -> Dict[str, Any]:
        """
        Generate a single course block based on textbook content and course outline
        """
        age_min, age_max = target_age_range
        
        # Determine which content section this block should cover
        content_sections = course_outline.get("content_sections", [])
        blocks_per_section = max(1, total_blocks // len(content_sections)) if content_sections else 1
        section_index = min((block_num - 1) // blocks_per_section, len(content_sections) - 1)
        current_section = content_sections[section_index] if content_sections else {"section_title": f"Week {week_num} Content", "topics": []}
        
        if textbook_content.startswith("GEMINI_FILE_URI:"):
            gemini_file_uri = textbook_content.replace("GEMINI_FILE_URI:", "")
            uploaded_file = genai.get_file(gemini_file_uri)
            
            block_prompt = f"""
            Generate a detailed learning block based on the uploaded textbook content.
            
            **CRITICAL CONTENT FILTERING:**
            - SKIP and IGNORE any "Table of Contents", "Course Outline", "Index", or "Syllabus" pages
            - SKIP any "Chapter Overview", "Summary", or "Learning Outcomes" pages that come BEFORE actual content
            - ONLY extract content from the ACTUAL LESSON PAGES (substantive educational material)
            - Look for explanations, examples, diagrams, and main body text
            - If you encounter outline/ToC content, skip ahead to find the real chapter content
            - DO NOT include meta-information about the course structure in the lesson content
            
            BLOCK CONTEXT:
            - Block {block_num} of {total_blocks} (Week {week_num}, Block {block_in_week})
            - Target Section: {current_section.get('section_title', 'General Content')}
            - Section Topics: {', '.join(current_section.get('topics', []))}
            - Subject: {subject}
            - Target Age: {age_min}-{age_max}
            - Difficulty: {difficulty_level}
            
            COURSE CONTEXT:
            Course Title: {course_outline.get('title', 'Course')}
            Course Description: {course_outline.get('description', '')}
            Previous Learning: {"First block" if block_num == 1 else f"Building on previous {block_num-1} blocks"}
            
            Generate a JSON block with this exact structure:
            {{
                "week": {week_num},
                "block_number": {block_in_week},
                "title": "Specific block title from textbook content",
                "description": "What students will learn in this block",
                "learning_objectives": [
                    "Specific objective 1 from textbook",
                    "Specific objective 2 from textbook",
                    "Specific objective 3 from textbook"
                ],
                "content": "Detailed lesson content extracted from textbook (400-600 words)",
                "duration_minutes": 45,
                "visual_elements": ["Any diagrams/images referenced", "Charts or illustrations"],
                "resources": [
                    {{"type": "article", "title": "Resource Title", "url": "placeholder", "search_query": "specific search terms"}},
                    {{"type": "video", "title": "Video Title", "url": "placeholder", "search_query": "YouTube search terms"}}
                ],
                "assignments": [
                    {{
                        "title": "Block Assignment Title",
                        "description": "Assignment based on block content",
                        "type": "homework",
                        "duration_minutes": 30,
                        "points": 100,
                        "rubric": "Clear grading criteria",
                        "due_days_after_block": 3
                    }}
                ]
            }}
            
            IMPORTANT:
            - Focus ONLY on content for THIS specific block
            - Extract relevant ACTUAL LESSON CONTENT from the textbook (NOT outlines or ToC)
            - Ensure age-appropriate language and complexity
            - Build on previous blocks if this is not the first block
            - Make it comprehensive but focused
            - VERIFY you're extracting from actual educational content, not meta-pages
            """
            
            response = await asyncio.to_thread(
                self.config.model.generate_content,
                [uploaded_file, block_prompt],
                generation_config=genai.types.GenerationConfig(
                    temperature=0.6,
                    max_output_tokens=1024,  # Reduced for free tier
                    response_mime_type="application/json"
                )
            )
        else:
            # Handle direct text content - extract relevant portion
            content_chunk_size = len(textbook_content) // total_blocks
            start_pos = (block_num - 1) * content_chunk_size
            end_pos = min(start_pos + content_chunk_size + 500, len(textbook_content))  # Overlap for context
            content_chunk = textbook_content[start_pos:end_pos]
            
            block_prompt = f"""
            Generate a detailed learning block based on this textbook content section.
            
            TEXTBOOK CONTENT (Section {block_num}):
            {content_chunk}
            
            BLOCK CONTEXT:
            - Block {block_num} of {total_blocks} (Week {week_num}, Block {block_in_week})
            - Subject: {subject}
            - Target Age: {age_min}-{age_max}
            - Difficulty: {difficulty_level}
            
            Generate the same JSON structure as above...
            """
            
            response = await asyncio.to_thread(
                self.config.model.generate_content,
                block_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.6,
                    max_output_tokens=1024,
                    response_mime_type="application/json"
                )
            )
        
        block_data = json.loads(response.text)
        
        # Ensure correct week and block numbers
        block_data["week"] = week_num
        block_data["block_number"] = block_in_week
        
        # Replace placeholder URLs with actual URLs
        if "resources" in block_data and block_data["resources"]:
            print(f"🔗 Generating actual resource URLs for block {block_num}...")
            enhanced_resources = []
            
            for resource in block_data["resources"]:
                resource_type = resource.get("type", "article")
                search_query = resource.get("search_query", resource.get("title", ""))
                
                if resource_type == "video":
                    # Generate actual YouTube URL
                    youtube_links = await self.generate_youtube_links(search_query, count=1)
                    if youtube_links:
                        enhanced_resources.append({
                            "type": "video",
                            "title": youtube_links[0].get("title", resource.get("title")),
                            "url": youtube_links[0].get("url"),
                            "search_query": search_query
                        })
                    else:
                        enhanced_resources.append(resource)
                else:
                    # Generate actual article URL
                    article_links = await self.generate_article_links(search_query, subject, count=1)
                    if article_links:
                        enhanced_resources.append({
                            "type": "article",
                            "title": article_links[0].get("title", resource.get("title")),
                            "url": article_links[0].get("url"),
                            "search_query": search_query
                        })
                    else:
                        enhanced_resources.append(resource)
                
                # Small delay to avoid rate limiting
                await asyncio.sleep(0.5)
            
            block_data["resources"] = enhanced_resources
            print(f"✅ Enhanced {len(enhanced_resources)} resources with actual URLs")
        
        return block_data

    async def _generate_overall_assignments(
        self, course_outline: Dict, generated_blocks: List[Dict], total_weeks: int
    ) -> List[Dict[str, Any]]:
        """
        Generate overall course assignments (midterms, finals, projects)
        """
        print(f"📋 Creating overall course assignments...")
        
        assignments_prompt = f"""
        Create overall course assignments based on the course content.
        
        COURSE CONTEXT:
        Title: {course_outline.get('title', 'Course')}
        Subject: {course_outline.get('subject', 'Subject')}
        Total Weeks: {total_weeks}
        Total Blocks: {len(generated_blocks)}
        Key Concepts: {', '.join(course_outline.get('key_concepts', []))}
        
        GENERATED BLOCKS SUMMARY:
        {chr(10).join([f"Week {block['week']}, Block {block['block_number']}: {block.get('title', 'Block')}" for block in generated_blocks[:5]])}
        {"... (and more blocks)" if len(generated_blocks) > 5 else ""}
        
        Create 2-3 major assignments in JSON format:
        [
            {{
                "title": "Midterm Assessment",
                "description": "Comprehensive assessment covering the first half of the course",
                "type": "assessment",
                "week_assigned": {total_weeks // 2},
                "duration_minutes": 60,
                "points": 200,
                "rubric": "Detailed rubric covering key concepts",
                "due_days_after_assignment": 7
            }},
            {{
                "title": "Final Project",
                "description": "Capstone project demonstrating mastery of course objectives",
                "type": "project", 
                "week_assigned": {max(1, total_weeks - 2)},
                "duration_minutes": 120,
                "points": 300,
                "rubric": "Project evaluation criteria",
                "due_days_after_assignment": 14
            }}
        ]
        """
        
        try:
            response = await asyncio.to_thread(
                self.config.model.generate_content,
                assignments_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.4,
                    max_output_tokens=512,
                    response_mime_type="application/json"
                )
            )
            
            return json.loads(response.text)
        except Exception as e:
            print(f"⚠️ Failed to generate overall assignments, using defaults: {str(e)}")
            # Fallback assignments
            return [
                {
                    "title": "Midterm Assessment",
                    "description": f"Comprehensive assessment covering the first half of {course_outline.get('title', 'the course')}",
                    "type": "assessment",
                    "week_assigned": total_weeks // 2,
                    "duration_minutes": 60,
                    "points": 200,
                    "rubric": "Knowledge demonstration, application, and analysis",
                    "due_days_after_assignment": 7
                },
                {
                    "title": "Final Project",
                    "description": f"Capstone project demonstrating mastery of {course_outline.get('subject', 'course')} objectives",
                    "type": "project",
                    "week_assigned": max(1, total_weeks - 2),
                    "duration_minutes": 120,
                    "points": 300,
                    "rubric": "Project completeness, creativity, and understanding demonstration",
                    "due_days_after_assignment": 14
                }
            ]

    def _create_course_generation_prompt(
        self, textbook_content: str, course_title: str, subject: str, 
        target_age_range: tuple, total_weeks: int, blocks_per_week: int, difficulty_level: str
    ) -> str:
        """Create a comprehensive prompt for course generation"""
        
        age_min, age_max = target_age_range
        
        return f"""
        You are an expert educational content creator. Analyze the following textbook content and create a comprehensive, structured course.

        TEXTBOOK CONTENT:
        {textbook_content[:4000]}... # Truncated for prompt efficiency

        COURSE REQUIREMENTS:
        - Title: {course_title}
        - Subject: {subject}
        - Target Age: {age_min}-{age_max} years
        - Duration: {total_weeks} weeks
        - Structure: {blocks_per_week} blocks per week
        - Difficulty: {difficulty_level}

        Create a JSON response with this exact structure:
        {{
            "title": "{course_title}",
            "subject": "{subject}",
            "description": "Comprehensive course description (2-3 sentences)",
            "age_min": {age_min},
            "age_max": {age_max},
            "difficulty_level": "{difficulty_level}",
            "total_weeks": {total_weeks},
            "blocks_per_week": {blocks_per_week},
            "textbook_source": "Source textbook information",
            "blocks": [
                {{
                    "week": 1,
                    "block_number": 1,
                    "title": "Block title",
                    "description": "What this block covers",
                    "learning_objectives": ["Objective 1", "Objective 2", "Objective 3"],
                    "content": "Detailed lesson content from textbook (200-400 words)",
                    "duration_minutes": 45,
                    "resources": [
                        {{"type": "article", "title": "Resource Title", "url": "placeholder_url", "search_query": "specific search terms"}},
                        {{"type": "video", "title": "Video Title", "url": "placeholder_url", "search_query": "YouTube search terms"}},
                        {{"type": "interactive", "title": "Activity Title", "url": "placeholder_url", "search_query": "educational resource search"}}
                    ],
                    "assignments": [
                        {{
                            "title": "Assignment Title",
                            "description": "Assignment description",
                            "type": "homework|quiz|project|assessment",
                            "duration_minutes": 30,
                            "points": 100,
                            "rubric": "Grading criteria",
                            "due_days_after_block": 3
                        }}
                    ]
                }}
            ],
            "overall_assignments": [
                {{
                    "title": "Midterm Assessment",
                    "description": "Comprehensive assessment covering weeks 1-{total_weeks//2}",
                    "type": "assessment",
                    "week_assigned": {total_weeks//2},
                    "duration_minutes": 60,
                    "points": 200,
                    "rubric": "Comprehensive rubric",
                    "due_days_after_assignment": 7
                }}
            ]
        }}

        IMPORTANT GUIDELINES:
        1. Base ALL content on the provided textbook
        2. Create {total_weeks * blocks_per_week} blocks total
        3. Each block should have 2-4 learning objectives
        4. Include varied resource types (articles, videos, interactive content)
        5. Create realistic search queries for finding resources
        6. Assignments should test understanding of block content
        7. Progress logically through the textbook material
        8. Ensure age-appropriate language and complexity
        9. Include hands-on activities and real-world applications
        10. Create assessment rubrics that are specific and measurable

        Generate comprehensive, detailed content that will create an engaging learning experience.
        """

    def _create_course_generation_prompt_for_file(
        self, uploaded_file, course_title: str, subject: str, 
        target_age_range: tuple, total_weeks: int, blocks_per_week: int, difficulty_level: str
    ) -> str:
        """Create a comprehensive prompt for course generation from uploaded files"""
        
        age_min, age_max = target_age_range
        
        return f"""
        You are an expert educational content creator with multimodal analysis capabilities. 
        Analyze the uploaded textbook file comprehensively and create a structured course.
        
        📚 **MULTIMODAL ANALYSIS INSTRUCTIONS:**
        - Read ALL text content from the document (including text in images)
        - Analyze any images, diagrams, charts, or visual content
        - Extract information from tables, figures, and captions
        - Understand the document structure and organization
        - Process any embedded media or visual elements
        - Handle scanned pages or image-based text
        
        🎯 **COURSE REQUIREMENTS:**
        - Title: {course_title}
        - Subject: {subject}
        - Target Age: {age_min}-{age_max} years
        - Duration: {total_weeks} weeks
        - Structure: {blocks_per_week} blocks per week
        - Difficulty: {difficulty_level}

        📖 **CONTENT ANALYSIS GUIDELINES:**
        1. Extract key concepts from ALL content (text + visual)
        2. Identify chapter/section structure from the document
        3. Recognize learning progression and dependencies
        4. Note any visual examples, diagrams, or illustrations
        5. Extract exercises, examples, and practice problems
        6. Understand the pedagogical approach used
        7. Identify vocabulary and key terms
        8. Note any assessment criteria or evaluation methods

        Create a JSON response with this exact structure:
        {{
            "title": "{course_title}",
            "subject": "{subject}",
            "description": "Comprehensive course description based on the analyzed content (2-3 sentences)",
            "age_min": {age_min},
            "age_max": {age_max},
            "difficulty_level": "{difficulty_level}",
            "total_weeks": {total_weeks},
            "blocks_per_week": {blocks_per_week},
            "textbook_source": "Information extracted from the document metadata and content",
            "blocks": [
                {{
                    "week": 1,
                    "block_number": 1,
                    "title": "Block title derived from textbook content",
                    "description": "What this block covers based on the source material",
                    "learning_objectives": ["Objective 1 from content", "Objective 2 from content", "Objective 3 from content"],
                    "content": "Detailed lesson content extracted and synthesized from textbook (300-500 words)",
                    "duration_minutes": 45,
                    "visual_elements": ["Description of relevant images/diagrams", "Charts or tables referenced"],
                    "resources": [
                        {{"type": "article", "title": "Resource Title", "url": "placeholder_url", "search_query": "specific search terms based on content"}},
                        {{"type": "video", "title": "Video Title", "url": "placeholder_url", "search_query": "YouTube search terms for topic"}},
                        {{"type": "interactive", "title": "Activity Title", "url": "placeholder_url", "search_query": "educational resource search"}}
                    ],
                    "assignments": [
                        {{
                            "title": "Assignment Title based on content",
                            "description": "Assignment description derived from textbook exercises",
                            "type": "homework|quiz|project|assessment",
                            "duration_minutes": 30,
                            "points": 100,
                            "rubric": "Grading criteria based on textbook standards",
                            "due_days_after_block": 3
                        }}
                    ]
                }}
            ],
            "overall_assignments": [
                {{
                    "title": "Comprehensive Assessment",
                    "description": "Assessment covering material from the analyzed textbook",
                    "type": "assessment",
                    "week_assigned": {total_weeks//2},
                    "duration_minutes": 60,
                    "points": 200,
                    "rubric": "Comprehensive rubric based on textbook evaluation methods",
                    "due_days_after_assignment": 7
                }}
            ],
            "document_insights": {{
                "total_pages_analyzed": "Number of pages processed",
                "visual_elements_found": "Count of images/diagrams/charts",
                "main_topics_identified": ["Topic 1", "Topic 2", "Topic 3"],
                "complexity_indicators": ["Vocabulary level", "Concept difficulty", "Prerequisites"]
            }}
        }}

        🔍 **ADVANCED PROCESSING REQUIREMENTS:**
        1. Base ALL content on the uploaded document - extract from text AND images
        2. Create {total_weeks * blocks_per_week} blocks total
        3. Each block should have 2-4 learning objectives derived from content
        4. Include information about visual elements found in the document
        5. Reference specific sections, chapters, or page content
        6. Create assignments based on exercises found in the textbook
        7. Progress logically through the document's organization
        8. Ensure age-appropriate language while preserving academic content
        9. Include hands-on activities inspired by textbook examples
        10. Create assessment rubrics that align with textbook standards

        📊 **MULTIMODAL PROCESSING:**
        - Extract text from images using OCR capabilities
        - Understand diagrams and their educational context
        - Process mathematical equations and formulas
        - Analyze charts, graphs, and data visualizations
        - Interpret scientific illustrations and technical drawings
        - Read text from screenshots or scanned pages

        Generate comprehensive, detailed content that fully utilizes the multimodal analysis of the uploaded textbook file.
        """

    async def _enhance_course_with_resources(self, course_data: Dict) -> Dict:
        """
        Enhance the course with actual resource links using search queries
        """
        enhanced_course = course_data.copy()
        
        # Process each block to find actual resources
        for block in enhanced_course["blocks"]:
            enhanced_resources = []
            
            for resource in block["resources"]:
                if resource["type"] == "video":
                    # Generate YouTube search URL
                    search_query = resource.get("search_query", resource["title"])
                    youtube_url = f"https://www.youtube.com/results?search_query={search_query.replace(' ', '+')}"
                    resource["url"] = youtube_url
                    
                elif resource["type"] == "article":
                    # Generate Google search URL for educational articles
                    search_query = resource.get("search_query", resource["title"])
                    search_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}+educational+article"
                    resource["url"] = search_url
                    
                elif resource["type"] == "interactive":
                    # Generate search for interactive educational content
                    search_query = resource.get("search_query", resource["title"])
                    interactive_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}+interactive+educational+tool"
                    resource["url"] = interactive_url
                
                enhanced_resources.append(resource)
            
            block["resources"] = enhanced_resources
        
        return enhanced_course

    async def generate_youtube_links(self, topic: str, count: int = 3) -> List[Dict[str, str]]:
        """
        Generate actual YouTube video links for educational content using YouTube Data API or scraping
        """
        youtube_api_key = os.getenv("YOUTUBE_API_KEY")
        links = []
        
        # Search variations for better coverage
        search_queries = [
            f"{topic} educational tutorial",
            f"{topic} explained simply", 
            f"learn {topic} step by step",
            f"{topic} for students",
            f"{topic} crash course"
        ]
        
        try:
            if youtube_api_key:
                # Use YouTube Data API v3 if available
                async with httpx.AsyncClient(timeout=10.0) as client:
                    for i, query in enumerate(search_queries[:count]):
                        try:
                            params = {
                                "part": "snippet",
                                "q": query,
                                "type": "video",
                                "maxResults": 1,
                                "key": youtube_api_key,
                                "videoEmbeddable": "true",
                                "videoLicense": "any",
                                "order": "relevance"
                            }
                            
                            response = await client.get(
                                "https://www.googleapis.com/youtube/v3/search",
                                params=params
                            )
                            
                            if response.status_code == 200:
                                data = response.json()
                                if data.get("items"):
                                    item = data["items"][0]
                                    video_id = item["id"]["videoId"]
                                    snippet = item["snippet"]
                                    
                                    links.append({
                                        "title": snippet.get("title", f"Educational Video: {topic}"),
                                        "url": f"https://www.youtube.com/watch?v={video_id}",
                                        "type": "video",
                                        "description": snippet.get("description", "")[:200],
                                        "thumbnail": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
                                        "channel": snippet.get("channelTitle", ""),
                                        "search_query": query
                                    })
                        except Exception as e:
                            print(f"⚠️ YouTube API error for query '{query}': {e}")
                            continue
            else:
                # Fallback: Use YouTube search URLs that open directly to search results
                # This still provides working links even without API
                print("ℹ️ No YOUTUBE_API_KEY found, using search URLs")
                for i, query in enumerate(search_queries[:count]):
                    search_url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
                    links.append({
                        "title": f"🎥 {topic} - Educational Videos",
                        "url": search_url,
                        "type": "video_search",
                        "description": f"Search results for: {query}",
                        "search_query": query
                    })
            
            # If we didn't get enough links, fill with search URLs
            while len(links) < count and len(links) < len(search_queries):
                query = search_queries[len(links)]
                links.append({
                    "title": f"🎥 {topic} - Video {len(links) + 1}",
                    "url": f"https://www.youtube.com/results?search_query={quote_plus(query)}",
                    "type": "video_search",
                    "description": f"YouTube search: {query}",
                    "search_query": query
                })
        
        except Exception as e:
            print(f"❌ Error generating YouTube links: {e}")
            # Ultimate fallback
            for i in range(count):
                if i < len(search_queries):
                    query = search_queries[i]
                    links.append({
                        "title": f"Educational Video: {topic} ({i+1})",
                        "url": f"https://www.youtube.com/results?search_query={quote_plus(query)}",
                        "type": "video",
                        "description": f"YouTube search for {query}",
                        "search_query": query
                    })
        
        return links[:count]

    async def generate_article_links(self, topic: str, subject: str, count: int = 3) -> List[Dict[str, str]]:
        """
        Generate actual educational article links from reputable sources
        """
        links = []
        
        # Define educational sources with their search patterns
        educational_sources = [
            {
                "name": "Wikipedia",
                "search_url": "https://en.wikipedia.org/wiki/{}",
                "direct_url": "https://en.wikipedia.org/wiki/Special:Search?search={}",
                "icon": "📚"
            },
            {
                "name": "Britannica",
                "search_url": "https://www.britannica.com/search?query={}",
                "direct_url": "https://www.britannica.com",
                "icon": "📖"
            },
            {
                "name": "National Geographic Education",
                "search_url": "https://education.nationalgeographic.org/search/?q={}",
                "direct_url": "https://education.nationalgeographic.org",
                "icon": "🌍"
            },
            {
                "name": "Academic Search",
                "search_url": "https://scholar.google.com/scholar?q={}+education",
                "direct_url": "https://scholar.google.com",
                "icon": "🔬"
            }
        ]
        
        try:
            # Create search queries
            search_terms = [
                f"{topic} {subject}",
                f"{topic} explained",
                f"{topic} tutorial {subject}"
            ]
            
            # Try to get actual URLs from educational sources
            for i, search_term in enumerate(search_terms[:count]):
                if i < len(educational_sources):
                    source = educational_sources[i]
                    # Format the search term for URL
                    formatted_term = quote_plus(search_term)
                    
                    # For Wikipedia, try direct article link first
                    if source["name"] == "Wikipedia":
                        # Try direct article name
                        article_name = topic.replace(" ", "_")
                        url = f"https://en.wikipedia.org/wiki/{article_name}"
                    else:
                        url = source["search_url"].format(formatted_term)
                    
                    links.append({
                        "title": f"{source['icon']} {topic} - {source['name']}",
                        "url": url,
                        "type": "article",
                        "description": f"Educational resource from {source['name']}",
                        "source": source["name"],
                        "search_query": search_term
                    })
            
            # Fill remaining slots with Google Scholar or general educational searches
            while len(links) < count:
                search_term = f"{topic} {subject} education"
                formatted_term = quote_plus(search_term)
                
                links.append({
                    "title": f"📄 {topic} - Educational Resources",
                    "url": f"https://scholar.google.com/scholar?q={formatted_term}",
                    "type": "article",
                    "description": f"Academic articles and educational resources about {topic}",
                    "source": "Google Scholar",
                    "search_query": search_term
                })
        
        except Exception as e:
            print(f"❌ Error generating article links: {e}")
            # Fallback to basic search links
            search_variations = [
                f"{topic} {subject} educational article",
                f"{topic} explained {subject}",
                f"learn about {topic} {subject}"
            ]
            
            for i, variation in enumerate(search_variations[:count]):
                links.append({
                    "title": f"Article: {topic} in {subject} ({i+1})",
                    "url": f"https://www.google.com/search?q={quote_plus(variation)}",
                    "type": "article",
                    "description": f"Educational article search for {variation}",
                    "search_query": variation
                })
        
        return links[:count]

    async def create_assignment_from_content(self, content: str, block_title: str, learning_objectives: List[str]) -> Dict[str, Any]:
        """
        Create a detailed assignment based on lesson content
        """
        assignment_prompt = f"""
        Create a detailed assignment based on this lesson content:
        
        BLOCK TITLE: {block_title}
        LEARNING OBJECTIVES: {', '.join(learning_objectives)}
        CONTENT: {content[:1000]}...
        
        Generate a JSON assignment with this structure:
        {{
            "title": "Assignment title",
            "description": "Detailed assignment description (what students need to do)",
            "type": "homework",
            "instructions": "Step-by-step instructions",
            "duration_minutes": 45,
            "points": 100,
            "rubric": "Detailed grading rubric with criteria",
            "due_days_after_block": 3,
            "submission_format": "What format students should submit (PDF, document, etc.)",
            "learning_outcomes": ["What students will demonstrate", "Skills they'll practice"]
        }}
        
        Make the assignment engaging, practical, and directly related to the learning objectives.
        """
        
        try:
            response = await asyncio.to_thread(
                self.config.model.generate_content,
                assignment_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.6,
                    max_output_tokens=1024,
                    response_mime_type="application/json"
                )
            )
            
            return json.loads(response.text)
            
        except Exception as e:
            # Fallback assignment if generation fails
            return {
                "title": f"Assignment: {block_title}",
                "description": f"Complete exercises related to {block_title}",
                "type": "homework",
                "instructions": "Follow the lesson content and complete all exercises.",
                "duration_minutes": 30,
                "points": 100,
                "rubric": "Completion (50%), Accuracy (30%), Understanding (20%)",
                "due_days_after_block": 3,
                "submission_format": "PDF document",
                "learning_outcomes": learning_objectives[:2]
            }

    async def grade_submission(
        self,
        submission_content: str,
        assignment_title: str,
        assignment_description: str,
        rubric: str,
        max_points: int = 100,
        submission_type: str = "homework"
    ) -> Dict[str, Any]:
        """
        Grade a student submission using Gemini AI
        
        This comprehensive grading function provides:
        - Detailed feedback and corrections
        - Numeric scoring based on rubric
        - Strengths and improvement areas
        - Specific recommendations for better performance
        """
        
        grading_prompt = f"""
        You are an expert educational assessor. Grade this student submission with detailed analysis.

        ASSIGNMENT DETAILS:
        Title: {assignment_title}
        Description: {assignment_description}
        Type: {submission_type}
        Maximum Points: {max_points}
        
        GRADING RUBRIC:
        {rubric}
        
        STUDENT SUBMISSION:
        {submission_content}
        
        Provide a comprehensive assessment in JSON format:
        {{
            "score": 85,
            "percentage": 85.0,
            "grade_letter": "B+",
            "overall_feedback": "Comprehensive overall assessment of the work",
            "detailed_feedback": "Detailed analysis of strengths and weaknesses",
            "strengths": [
                "Specific strength 1",
                "Specific strength 2", 
                "Specific strength 3"
            ],
            "improvements": [
                "Specific area for improvement 1",
                "Specific area for improvement 2",
                "Specific area for improvement 3"
            ],
            "corrections": [
                "Specific correction or error found",
                "Another correction needed",
                "Additional feedback point"
            ],
            "rubric_breakdown": {{
                "criteria_1": {{"score": 20, "max": 25, "feedback": "Specific feedback"}},
                "criteria_2": {{"score": 18, "max": 25, "feedback": "Specific feedback"}},
                "criteria_3": {{"score": 22, "max": 25, "feedback": "Specific feedback"}},
                "criteria_4": {{"score": 25, "max": 25, "feedback": "Specific feedback"}}
            }},
            "recommendations": [
                "Specific recommendation for future work",
                "Study suggestion or resource",
                "Practice activity suggestion"
            ],
            "time_spent_minutes": 15,
            "effort_level": "high|medium|low",
            "understanding_demonstrated": "excellent|good|fair|needs_improvement"
        }}
        
        GRADING GUIDELINES:
        1. Be thorough but constructive in feedback
        2. Provide specific examples from the submission
        3. Score fairly based on the rubric criteria
        4. Offer actionable improvement suggestions
        5. Recognize effort and good attempts even if incorrect
        6. Be encouraging while maintaining academic standards
        7. Focus on learning outcomes and skill development
        """
        
        try:
            response = await asyncio.to_thread(
                self.config.model.generate_content,
                grading_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,  # Lower temperature for more consistent grading
                    max_output_tokens=2048,
                    response_mime_type="application/json"
                )
            )
            # Robust JSON parsing
            grade_result = self._safe_parse_json(response.text)
            
            # Ensure score consistency
            if "score" in grade_result and "percentage" not in grade_result:
                try:
                    score_val = float(grade_result.get("score", 0))
                    grade_result["percentage"] = (score_val / max_points) * 100 if max_points else score_val
                except Exception:
                    grade_result["percentage"] = None
            
            # Add metadata
            grade_result["graded_by"] = "Gemini AI"
            grade_result["graded_at"] = datetime.utcnow().isoformat()
            grade_result["max_points"] = max_points
            
            return grade_result
            
        except Exception as e:
            # Fallback grading if AI fails
            return {
                "score": max_points * 0.7,  # Default to 70%
                "percentage": 70.0,
                "grade_letter": "C+",
                "overall_feedback": "Submission received and reviewed. AI grading temporarily unavailable.",
                "detailed_feedback": f"Error in AI grading: {str(e)}. Please review manually.",
                "strengths": ["Submission completed on time"],
                "improvements": ["AI grading unavailable - please consult instructor"],
                "corrections": [],
                "recommendations": ["Resubmit when AI grading is available"],
                "graded_by": "Fallback System",
                "graded_at": datetime.utcnow().isoformat(),
                "max_points": max_points,
                "error": str(e)
            }

    async def grade_bulk_submissions(
        self,
        submissions: List[Dict[str, Any]],
        assignment_title: str,
        assignment_description: str,
        rubric: str,
        max_points: int = 100
    ) -> Dict[str, Any]:
        """
        Grade multiple student submissions in bulk using Gemini AI
        
        This function efficiently processes multiple submissions while maintaining
        individual detailed feedback for each student.
        """
        
        print(f"🤖 Starting bulk Gemini AI grading for {len(submissions)} submissions")
        
        grading_results = []
        successful_grades = 0
        failed_grades = 0
        
        for i, submission in enumerate(submissions):
            try:
                print(f"📝 Grading submission {i+1}/{len(submissions)}: {submission.get('student_name', 'Unknown')}")
                
                # Grade individual submission
                grade_result = await self.grade_submission(
                    submission_content=submission.get("content", "No content provided"),
                    assignment_title=assignment_title,
                    assignment_description=assignment_description,
                    rubric=rubric,
                    max_points=max_points,
                    submission_type=submission.get("submission_type", "homework")
                )
                
                # Add submission metadata
                grade_result.update({
                    "submission_id": submission.get("submission_id"),
                    "user_id": submission.get("user_id"),
                    "student_name": submission.get("student_name", "Unknown"),
                    "success": True
                })
                
                grading_results.append(grade_result)
                successful_grades += 1
                
                # Add small delay to avoid rate limiting
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"❌ Failed to grade submission for {submission.get('student_name', 'Unknown')}: {str(e)}")
                
                # Add failed submission to results
                grading_results.append({
                    "submission_id": submission.get("submission_id"),
                    "user_id": submission.get("user_id"), 
                    "student_name": submission.get("student_name", "Unknown"),
                    "success": False,
                    "error": str(e),
                    "score": 0,
                    "percentage": 0.0,
                    "overall_feedback": "Grading failed due to technical error"
                })
                failed_grades += 1
        
        # Create batch summary
        batch_summary = {
            "total_submissions": len(submissions),
            "successfully_graded": successful_grades,
            "failed_grades": failed_grades,
            "success_rate": (successful_grades / len(submissions)) * 100 if submissions else 0,
            "average_score": None,
            "grade_distribution": {}
        }
        
        # Calculate statistics for successful grades
        successful_results = [r for r in grading_results if r.get("success", False)]
        if successful_results:
            scores = [r["percentage"] for r in successful_results]
            batch_summary["average_score"] = sum(scores) / len(scores)
            
            # Grade distribution
            grade_ranges = {"A (90-100)": 0, "B (80-89)": 0, "C (70-79)": 0, "D (60-69)": 0, "F (0-59)": 0}
            for score in scores:
                if score >= 90:
                    grade_ranges["A (90-100)"] += 1
                elif score >= 80:
                    grade_ranges["B (80-89)"] += 1
                elif score >= 70:
                    grade_ranges["C (70-79)"] += 1
                elif score >= 60:
                    grade_ranges["D (60-69)"] += 1
                else:
                    grade_ranges["F (0-59)"] += 1
            
            batch_summary["grade_distribution"] = grade_ranges
        
        print(f"✅ Bulk grading complete: {successful_grades}/{len(submissions)} successful")
        
        return {
            "status": "completed",
            "batch_summary": batch_summary,
            "student_results": grading_results,
            "graded_by": "Gemini AI Bulk Processor",
            "processed_at": datetime.utcnow().isoformat()
        }

    async def grade_submission_from_file(
        self,
        file_bytes: bytes,
        filename: str,
        assignment_title: str,
        assignment_description: str,
        rubric: str,
        max_points: int = 100,
        submission_type: str = "homework",
    ) -> Dict[str, Any]:
        """
        Grade a student submission by uploading the PDF/image document directly to Gemini.

        This uses Gemini's native file processing (incl. OCR for image-based PDFs) and applies
        the same grading rubric used by grade_submission(). Returns a normalized JSON payload.
        """
        try:
            # Upload file and get Gemini file URI
            gemini_file_uri = await self.upload_file_to_gemini(file_bytes, filename)
            uploaded_file = genai.get_file(gemini_file_uri)

            grading_prompt = f"""
            You are an expert educational assessor. Read the attached submission file in full
            (including running OCR on any images/scanned pages) and grade it with detailed analysis.

            ASSIGNMENT DETAILS:
            Title: {assignment_title}
            Description: {assignment_description}
            Type: {submission_type}
            Maximum Points: {max_points}

            GRADING RUBRIC:
            {rubric}

            Provide a comprehensive assessment in JSON format with these keys:
            {{
                "score": 85,
                "percentage": 85.0,
                "grade_letter": "B+",
                "overall_feedback": "Overall feedback text",
                "detailed_feedback": "Detailed analysis text",
                "strengths": ["..."],
                "improvements": ["..."],
                "corrections": ["..."],
                "recommendations": ["..."],
                "rubric_breakdown": {{"criteria_1": {{"score": 20, "max": 25, "feedback": "..."}}}}
            }}
            """

            response = await asyncio.to_thread(
                self.config.model.generate_content,
                [uploaded_file, grading_prompt],
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=2048,
                    response_mime_type="application/json",
                ),
            )

            # Robust JSON parsing
            grade_result = self._safe_parse_json(response.text)

            # Normalize score fields
            if "percentage" not in grade_result and "score" in grade_result:
                try:
                    score_val = float(grade_result.get("score", 0))
                    grade_result["percentage"] = (score_val / max_points) * 100 if max_points else score_val
                except Exception:
                    grade_result["percentage"] = None

            grade_result["graded_by"] = "Gemini AI"
            grade_result["graded_at"] = datetime.utcnow().isoformat()
            grade_result["max_points"] = max_points

            return grade_result

        except Exception as e:
            # Fallback payload to avoid blowing up the caller
            return {
                "score": None,
                "percentage": None,
                "grade_letter": None,
                "overall_feedback": None,
                "detailed_feedback": None,
                "strengths": [],
                "improvements": [],
                "corrections": [],
                "recommendations": [],
                "graded_by": "Gemini AI",
                "graded_at": datetime.utcnow().isoformat(),
                "max_points": max_points,
                "error": str(e),
            }

    async def extract_text_from_pdf_content(self, pdf_content: str) -> str:
        """
        Extract and process text content from PDF for grading
        This is a placeholder - in production you'd use proper PDF processing
        """
        try:
            # For now, assume pdf_content is already text extracted from PDF
            # In production, integrate with proper PDF text extraction library
            
            if not pdf_content or len(pdf_content.strip()) < 10:
                return "No readable content found in submission"
            
            # Clean up the content
            cleaned_content = re.sub(r'\s+', ' ', pdf_content)  # Normalize whitespace
            cleaned_content = cleaned_content.strip()
            
            # Limit content length for processing
            if len(cleaned_content) > 5000:
                cleaned_content = cleaned_content[:5000] + "... [Content truncated for processing]"
            
            return cleaned_content
            
        except Exception as e:
            return f"Error extracting content from PDF: {str(e)}"

    async def analyze_assignment_difficulty(
        self,
        assignment_description: str,
        target_age: int,
        subject: str
    ) -> Dict[str, Any]:
        """
        Analyze assignment difficulty and suggest improvements
        """
        
        analysis_prompt = f"""
        Analyze this assignment for appropriateness and difficulty level.
        
        ASSIGNMENT: {assignment_description}
        TARGET AGE: {target_age}
        SUBJECT: {subject}
        
        Provide analysis in JSON format:
        {{
            "difficulty_level": "beginner|intermediate|advanced",
            "age_appropriate": true,
            "estimated_completion_time": 45,
            "cognitive_load": "low|medium|high",
            "suggestions": [
                "Specific improvement suggestion",
                "Another helpful tip"
            ],
            "strengths": [
                "What works well in this assignment"
            ],
            "potential_challenges": [
                "What students might struggle with"
            ]
        }}
        """
        
        try:
            response = await asyncio.to_thread(
                self.config.model.generate_content,
                analysis_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.4,
                    max_output_tokens=1024,
                    response_mime_type="application/json"
                )
            )
            
            return json.loads(response.text)
            
        except Exception as e:
            return {
                "difficulty_level": "intermediate",
                "age_appropriate": True,
                "estimated_completion_time": 30,
                "cognitive_load": "medium",
                "suggestions": ["AI analysis unavailable"],
                "strengths": ["Assignment created successfully"],
                "potential_challenges": [f"Analysis error: {str(e)}"]
            }

    async def upload_file_to_gemini(self, file_content: bytes, filename: str, mime_type: str = None) -> str:
        """
        Upload file directly to Gemini using the File API for native processing
        This allows Gemini to read PDFs with images, scanned documents, and mixed content directly
        """
        try:
            import tempfile
            
            # Determine MIME type if not provided
            if not mime_type:
                file_extension = Path(filename).suffix.lower()
                mime_types = {
                    '.pdf': 'application/pdf',
                    '.txt': 'text/plain',
                    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    '.doc': 'application/msword',
                    '.png': 'image/png',
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.gif': 'image/gif',
                    '.webp': 'image/webp'
                }
                mime_type = mime_types.get(file_extension, 'application/octet-stream')
            
            # Create temporary file for Gemini upload
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name
            
            try:
                # Upload file to Gemini
                print(f"📤 Uploading {filename} to Gemini AI for native processing...")
                uploaded_file = genai.upload_file(path=temp_file_path, display_name=filename)
                
                print(f"✅ File uploaded successfully: {uploaded_file.name}")
                print(f"📋 MIME type: {uploaded_file.mime_type}")
                print(f"📊 File size: {uploaded_file.size_bytes} bytes")
                
                # Wait for file processing to complete
                import time
                while uploaded_file.state.name == "PROCESSING":
                    print("⏳ Waiting for file processing...")
                    time.sleep(2)
                    uploaded_file = genai.get_file(uploaded_file.name)
                
                if uploaded_file.state.name == "FAILED":
                    raise Exception(f"File processing failed: {uploaded_file.error}")
                
                print(f"🎉 File processing complete! State: {uploaded_file.state.name}")
                return uploaded_file.name  # Return the file URI for Gemini
                
            finally:
                # Clean up temporary file
                os.unlink(temp_file_path)
                
        except Exception as e:
            raise Exception(f"Error uploading file '{filename}' to Gemini: {str(e)}")

    async def process_uploaded_textbook_file(self, file_content: bytes, filename: str) -> str:
        """
        Process uploaded textbook file using Gemini's native capabilities
        Returns the Gemini file URI for direct use in prompts
        
        This method leverages Gemini's multimodal capabilities to:
        - Read PDFs with images and scanned content
        - Process Word documents with embedded media
        - Handle mixed content (text + images)
        - Extract text from image-based documents
        """
        try:
            # Get file extension and validate
            file_extension = Path(filename).suffix.lower()
            
            # For text files, we can still extract content directly for faster processing
            if file_extension == '.txt' and len(file_content) < 100000:  # < 100KB
                try:
                    text_content = file_content.decode('utf-8', errors='ignore')
                    if len(text_content.strip()) >= 100:
                        print(f"📝 Processing text file directly: {len(text_content)} characters")
                        return text_content
                except UnicodeDecodeError:
                    pass  # Fall through to Gemini processing
            
            # For all other files or large text files, use Gemini's native processing
            print(f"🤖 Using Gemini native processing for {filename}")
            gemini_file_uri = await self.upload_file_to_gemini(file_content, filename)
            
            # Return a special marker that indicates this is a Gemini file reference
            return f"GEMINI_FILE_URI:{gemini_file_uri}"
            
        except Exception as e:
            raise Exception(f"Error processing file '{filename}': {str(e)}")

    def validate_textbook_file(self, filename: str, file_size: int) -> Dict[str, Any]:
        """
        Validate uploaded textbook file for Gemini native processing
        Supports documents, images, and multimodal content
        """
        # File size limit (50MB for Gemini processing)
        MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB (increased for native processing)
        
        # Allowed file types - expanded for Gemini's multimodal capabilities
        ALLOWED_EXTENSIONS = {
            # Document formats
            '.txt', '.pdf', '.doc', '.docx',
            # Image formats (for textbook pages, diagrams, etc.)
            '.png', '.jpg', '.jpeg', '.gif', '.webp'
        }
        
        file_extension = Path(filename).suffix.lower()
        
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "file_type": file_extension,
            "size_mb": round(file_size / (1024 * 1024), 2),
            "processing_method": "gemini_native"
        }
        
        # Check file size
        if file_size > MAX_FILE_SIZE:
            validation_result["valid"] = False
            validation_result["errors"].append(f"File size ({validation_result['size_mb']}MB) exceeds maximum allowed size (50MB)")
        
        # Check file extension
        if file_extension not in ALLOWED_EXTENSIONS:
            validation_result["valid"] = False
            validation_result["errors"].append(f"File type '{file_extension}' not supported. Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}")
        
        # Informational messages for different file types
        if file_extension == '.pdf':
            validation_result["warnings"].append("PDF will be processed using Gemini's native capabilities - supports text, images, and scanned content")
        elif file_extension in ['.doc', '.docx']:
            validation_result["warnings"].append("Word document will be processed natively - supports embedded images and complex formatting")
        elif file_extension in ['.png', '.jpg', '.jpeg', '.gif', '.webp']:
            validation_result["warnings"].append("Image file will be processed using Gemini's OCR and visual analysis capabilities")
            validation_result["file_category"] = "image"
        elif file_extension == '.txt':
            validation_result["warnings"].append("Text file will be processed directly for optimal performance")
            validation_result["file_category"] = "text"
        
        return validation_result

    # ===============================
    # READING ASSISTANT AI METHODS
    # ===============================
    
    async def generate_text(self, prompt: str, **kwargs) -> str:
        """Generate text using Gemini AI - core method for reading assistant"""
        try:
            generation_config = genai.types.GenerationConfig(
                temperature=kwargs.get('temperature', 0.7),
                max_output_tokens=kwargs.get('max_tokens', 1024),
                response_mime_type=kwargs.get('response_format', 'text/plain')
            )
            
            response = await asyncio.to_thread(
                self.config.model.generate_content,
                prompt,
                generation_config=generation_config
            )
            
            return response.text
            
        except Exception as e:
            print(f"❌ Gemini text generation error: {e}")
            raise Exception(f"AI text generation failed: {str(e)}")
    
    async def generate_reading_content_ai(
        self,
        reading_level: str,
        difficulty_level: str,
        content_type: str,
        topic: str = None,
        word_count: int = 20,
        phonics_focus: List[str] = None
    ) -> Dict[str, Any]:
        """Generate age-appropriate reading content for students"""
        
        phonics_focus = phonics_focus or ["basic phonics"]
        topic = topic or "everyday activities"
        
        prompt = f"""
        Create engaging reading content for early learners.
        
        SPECIFICATIONS:
        - Reading Level: {reading_level}
        - Difficulty: {difficulty_level}  
        - Content Type: {content_type}
        - Topic: {topic}
        - Target Word Count: {word_count}
        - Phonics Focus: {', '.join(phonics_focus)}
        
        REQUIREMENTS:
        1. Use age-appropriate vocabulary and sentence structure
        2. Include repetitive patterns for building confidence
        3. Focus on sight words and phonics patterns specified
        4. Make content engaging and relatable to children
        5. Ensure proper punctuation for reading practice
        
        READING LEVEL GUIDELINES:
        - KINDERGARTEN: 3-8 words per sentence, simple CVC words
        - GRADE_1: 5-12 words per sentence, basic compound words  
        - GRADE_2: 8-18 words per sentence, more complex vocabulary
        - GRADE_3: 10-25 words per sentence, chapter-like content
        
        Return ONLY a JSON object with this exact structure:
        {{
            "title": "Content title",
            "content": "The reading text content", 
            "vocabulary_words": {{"word1": "definition1", "word2": "definition2"}},
            "learning_objectives": ["objective1", "objective2"],
            "phonics_focus": {phonics_focus},
            "word_count": {word_count},
            "estimated_reading_time": 60
        }}
        """
        
        try:
            response = await self.generate_text(
                prompt, 
                response_format="application/json",
                temperature=0.8
            )
            
            # Clean and parse JSON response
            json_text = response.strip()
            if json_text.startswith('```json'):
                json_text = json_text[7:-3].strip()
            elif json_text.startswith('```'):
                json_text = json_text[3:-3].strip()
                
            return json.loads(json_text)
            
        except Exception as e:
            print(f"❌ Reading content generation failed: {e}")
            raise Exception(f"Failed to generate reading content: {str(e)}")
    
    async def analyze_speech_performance(
        self,
        expected_text: str,
        transcribed_text: str,
        reading_level: str
    ) -> Dict[str, Any]:
        """Analyze student's reading performance with STRICT pronunciation analysis"""
        
        import re
        from difflib import SequenceMatcher
        
        # Normalize texts for comparison (remove punctuation, lowercase)
        def normalize(text: str) -> str:
            return re.sub(r'[^\w\s]', '', text.lower().strip())
        
        expected_normalized = normalize(expected_text)
        transcribed_normalized = normalize(transcribed_text)
        
        # Quick check: If texts are identical, student read perfectly!
        if expected_normalized == transcribed_normalized:
            print("🎉 Perfect reading detected - texts match exactly!")
            expected_words = expected_text.strip().split()
            return {
                "accuracy_score": 1.0,
                "overall_feedback": "Perfect! You read every word correctly!",
                "word_feedback": [
                    {
                        "word": word,
                        "expected": word,
                        "said": word,
                        "pronunciation_score": 1.0,
                        "sound_errors": [],
                        "feedback": f"Perfect! You said '{word}' correctly."
                    }
                    for word in expected_words
                ],
                "suggestions": ["Keep up the great work!", "Try reading more challenging content"],
                "correctly_read_words": expected_words,
                "incorrectly_read_words": [],
                "needs_practice_words": [],
                "encouragement": f"Excellent work! You got all {len(expected_words)} words correct!"
            }
        
        # Check similarity to avoid safety filter
        similarity = SequenceMatcher(None, expected_normalized, transcribed_normalized).ratio()
        print(f"📊 Text similarity: {similarity*100:.1f}%")
        
        # Always use local analysis to avoid safety filter issues (Gemini blocks educational content)
        print("⚡ Using local word-by-word analysis (avoiding Gemini safety filter)")
        return self._local_word_analysis(expected_text, transcribed_text)
        
        prompt = f"""
        You are a reading pronunciation specialist analyzing a student's reading performance.

        IMPORTANT: This is an EDUCATIONAL ANALYSIS for a young student learning to read.
        
        TASK: Compare what the student said versus what they should have said.
        
        TEXTS TO COMPARE:
        - Expected (what should be read): "{expected_text}"
        - Transcribed (what student said): "{transcribed_text}"
        - Reading Level: {reading_level}
        
        ANALYSIS RULES:
        1. Compare word-by-word
        2. If words match exactly → score 1.0 (perfect)
        3. If words are close → score 0.7-0.9 (minor differences)
        4. If words are different → score 0.0-0.6 (needs practice)
        5. Provide helpful educational feedback for each word
        
        Return a JSON object analyzing each word:
        {{
            "accuracy_score": 0.85,
            "overall_feedback": "Great reading! Most words were correct.",
            "word_feedback": [
                {{
                    "word": "example",
                    "expected": "example", 
                    "said": "example",
                    "pronunciation_score": 1.0,
                    "sound_errors": [],
                    "feedback": "Perfect!"
                }}
            ],
            "suggestions": ["Keep practicing!"],
            "correctly_read_words": ["list", "of", "correct", "words"],
            "incorrectly_read_words": ["words", "to", "practice"],
            "needs_practice_words": ["specific", "problem", "words"],
            "encouragement": "You're doing great!"
        }}
        """
        
        try:
            response = await self.generate_text(
                prompt,
                response_format="application/json",
                temperature=0.6
            )
            
            # Clean and parse JSON response
            json_text = response.strip()
            if json_text.startswith('```json'):
                json_text = json_text[7:-3].strip()
            elif json_text.startswith('```'):
                json_text = json_text[3:-3].strip()
                
            return json.loads(json_text)
            
        except Exception as e:
            print(f"❌ Speech analysis failed: {e}")
            raise Exception(f"Failed to analyze speech performance: {str(e)}")
    
    async def generate_personalized_recommendations(
        self,
        student_profile: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Generate personalized reading content recommendations"""
        
        prompt = f"""
        Generate personalized reading recommendations for a student.
        
        STUDENT PROFILE:
        - Reading Level: {student_profile.get('reading_level', 'KINDERGARTEN')}
        - Current Accuracy: {student_profile.get('current_accuracy', 0.8)}
        - Struggle Areas: {student_profile.get('struggle_areas', [])}
        - Interests: {student_profile.get('interests', [])}
        - Recently Completed: {len(student_profile.get('completed_content_ids', []))} items
        
        Create 3-5 content recommendations that:
        1. Match the student's reading level
        2. Address their struggle areas
        3. Incorporate their interests
        4. Provide appropriate challenge level
        5. Build on their strengths
        
        Return ONLY a JSON array:
        [
            {{
                "title": "Content Title",
                "content_type": "story",
                "topic": "animals",
                "difficulty_justification": "Perfect for practicing short vowels",
                "why_recommended": "Based on your interest in animals and need to practice CVC words",
                "expected_benefit": "Will help improve pronunciation of short vowel sounds"
            }}
        ]
        """
        
        try:
            response = await self.generate_text(
                prompt,
                response_format="application/json", 
                temperature=0.7
            )
            
            # Clean and parse JSON response
            json_text = response.strip()
            if json_text.startswith('```json'):
                json_text = json_text[7:-3].strip()
            elif json_text.startswith('```'):
                json_text = json_text[3:-3].strip()
                
            return json.loads(json_text)
            
        except Exception as e:
            print(f"❌ Recommendation generation failed: {e}")
            return []  # Return empty list as fallback
    
    def _local_word_analysis(self, expected_text: str, transcribed_text: str) -> Dict[str, Any]:
        """
        Perform local word-by-word analysis to avoid Gemini safety filter on near-perfect readings.
        Uses phonics pattern analysis to provide educational feedback with pronunciation guides.
        """
        import re
        from difflib import SequenceMatcher
        
        def get_pronunciation_guide(word: str) -> str:
            """Generate phonetic pronunciation guide for a word"""
            word_lower = word.lower()
            
            # Common word pronunciations
            pronunciation_map = {
                'the': 'THUH (like "thuh")',
                'sky': 'SKY (sounds like "skai")',
                'leaf': 'LEEF (long "ee" sound)',
                'see': 'SEE (sounds like the letter "E")',
                'tree': 'TREE (sounds like "tree")',
                'sun': 'SUN (rhymes with "fun")',
                'run': 'RUN (rhymes with "sun")',
                'big': 'BIG (sounds like "big")',
                'slide': 'SLIDE (sounds like "slyde")',
                'through': 'THROO (with "th" sound, like "threw")',
                'play': 'PLAY (sounds like "plei")',
                'say': 'SAY (sounds like "sei")',
                'day': 'DAY (sounds like "dei")',
                'eat': 'EET (long "ee" sound)',
                'read': 'REED (long "ee" sound)',
            }
            
            if word_lower in pronunciation_map:
                return pronunciation_map[word_lower]
            
            # Pattern-based pronunciation
            if 'ee' in word_lower:
                return f'{word.upper()} (with long "ee" sound like "tree")'
            elif 'ea' in word_lower:
                return f'{word.upper()} (with long "e" sound like "eat")'
            elif 'ay' in word_lower or 'ai' in word_lower:
                return f'{word.upper()} (with long "a" sound like "play")'
            elif 'oo' in word_lower:
                return f'{word.upper()} (with "oo" sound like "moon")'
            elif word_lower.endswith('y'):
                return f'{word.upper()} (ends with "ee" sound like "happy")'
            else:
                return f'{word.upper()}'
        
        def analyze_phonics_error(expected_word: str, spoken_word: str) -> tuple[list, str]:
            """Analyze the phonetic/phonics difference between expected and spoken words"""
            exp_clean = expected_word.lower()
            sp_clean = spoken_word.lower()
            
            sound_errors = []
            
            # Get pronunciation guide for the correct word
            pronunciation = get_pronunciation_guide(expected_word)
            feedback = f"You said '{spoken_word}'. Say it like: {pronunciation}"
            
            # Add specific phonics hints
            if 'ee' in exp_clean:
                sound_errors.append("vowel_pattern_ee")
                feedback += f" - The 'ee' makes a long E sound."
            elif 'ea' in exp_clean:
                sound_errors.append("vowel_pattern_ea")
                feedback += f" - The 'ea' makes a long E sound."
            elif 'ay' in exp_clean:
                sound_errors.append("vowel_pattern_ay")
                feedback += f" - The 'ay' makes a long A sound."
            elif 'ai' in exp_clean:
                sound_errors.append("vowel_pattern_ai")
                feedback += f" - The 'ai' makes a long A sound."
            elif exp_clean.endswith('y') and len(exp_clean) > 2:
                sound_errors.append("y_ending")
                feedback += f" - Words ending in 'y' often sound like 'ee'."
            
            # Check for missing consonants
            if exp_clean.startswith('th') and not sp_clean.startswith('th'):
                sound_errors.append("missing_th")
                feedback += " - Don't forget the 'TH' sound at the start!"
            elif len(sp_clean) > len(exp_clean):
                sound_errors.append("added_letters")
                feedback = f"You said '{spoken_word}' but the word is shorter. Say it like: {pronunciation}"
            elif len(sp_clean) < len(exp_clean):
                sound_errors.append("missing_letters")
                feedback = f"You said '{spoken_word}' but you're missing part. Say it like: {pronunciation}"
            
            return sound_errors, feedback
        
        # Split into words (preserve punctuation context)
        expected_words = expected_text.strip().split()
        transcribed_words = transcribed_text.strip().split()
        
        word_feedback = []
        correct_count = 0
        incorrect_words = []
        needs_practice = []
        
        max_len = max(len(expected_words), len(transcribed_words))
        
        for i in range(max_len):
            expected_word = expected_words[i] if i < len(expected_words) else ""
            spoken_word = transcribed_words[i] if i < len(transcribed_words) else ""
            
            # Normalize for comparison (remove punctuation)
            expected_clean = re.sub(r'[^\w]', '', expected_word.lower())
            spoken_clean = re.sub(r'[^\w]', '', spoken_word.lower())
            
            # Calculate word similarity
            if expected_clean == spoken_clean:
                # Perfect match
                score = 1.0
                correct_count += 1
                feedback_text = f"✅ Perfect!"
                sound_errors = []
            elif not spoken_clean:
                # Word was skipped
                score = 0.0
                incorrect_words.append(expected_word)
                needs_practice.append(expected_word)
                pronunciation = get_pronunciation_guide(expected_word)
                feedback_text = f"⚠️ You skipped this word. Say it like: {pronunciation}"
                sound_errors = ["word_skipped"]
            elif not expected_clean:
                # Extra word spoken
                score = 0.0
                feedback_text = f"⚠️ This word isn't in the text. You added '{spoken_word}'."
                sound_errors = ["extra_word"]
            else:
                # Analyze phonics/pronunciation error
                sound_errors, feedback_text = analyze_phonics_error(expected_word, spoken_word)
                
                # Calculate similarity score
                word_similarity = SequenceMatcher(None, expected_clean, spoken_clean).ratio()
                score = word_similarity
                
                # Add to practice list
                if score < 1.0:
                    needs_practice.append(expected_word)
                    if score < 0.7:
                        incorrect_words.append(expected_word)
            
            word_feedback.append({
                "word": expected_word,
                "expected": expected_word,
                "said": spoken_word,
                "pronunciation_score": score,
                "sound_errors": sound_errors,
                "feedback": feedback_text
            })
        
        accuracy_score = correct_count / len(expected_words) if expected_words else 0.0
        
        print(f"📊 Local analysis: {correct_count}/{len(expected_words)} words correct ({accuracy_score*100:.1f}%)")
        
        return {
            "accuracy_score": accuracy_score,
            "overall_feedback": f"Good job! You got {correct_count} out of {len(expected_words)} words correct.",
            "word_feedback": word_feedback,
            "suggestions": [
                f"Practice saying: {', '.join(needs_practice[:3])}" if needs_practice else "Keep reading aloud every day!"
            ],
            "correctly_read_words": [w["expected"] for w in word_feedback if w["pronunciation_score"] >= 0.8],
            "incorrectly_read_words": incorrect_words,
            "needs_practice_words": needs_practice,
            "encouragement": "Great effort! Keep practicing and you'll get even better!"
        }

# Singleton instance
gemini_service = GeminiService()